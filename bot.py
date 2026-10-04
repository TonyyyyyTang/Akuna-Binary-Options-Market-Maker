"""Final V7B competition strategy, preserved with its original trading behavior.

The local models provide the contest interface for tests and post-competition runs.
See docs/retrospective.md for results and known limitations.
"""
from __future__ import annotations

import math
from collections import defaultdict

from model import (
    AJARAI_UNDERLYING_ID,
    FED_FUNDS_RATE_UNDERLYING_ID,
    THERIODIC_UNDERLYING_ID,
    BinaryOption,
    FokOrder,
    MarketHistory,
    MarketParameters,
    OrderType,
    Position,
    Quote,
    Underlying,
)


class MarketMaker:
    def __init__(
        self,
        underlying_initial_state: list[Underlying],
        option_initial_state: list[BinaryOption],
        cash_balance: float,
    ) -> None:
        self.underlying_state: list[Underlying] = underlying_initial_state
        self.active_option_state: list[BinaryOption] = option_initial_state
        self.cash_balance: float = cash_balance
        self.position: Position = Position()

        # warm_up 缺失或历史太短时使用的保守默认参数
        self.estimated_parameters: MarketParameters = MarketParameters(
            ajarai_drift=0.0,
            ajarai_idio_std_dev=0.02,
            ajarai_rate_beta=0.0,
            ajarai_sector_beta=1.0,
            rate_down_probability=0.25,
            rate_reversion_strength=0.05,
            rate_up_probability=0.25,
            sector_std_dev=0.02,
            theriodic_drift=0.0,
            theriodic_idio_std_dev=0.02,
            theriodic_rate_beta=0.0,
            theriodic_sector_beta=1.0,
            rate_step=0.25,
            rate_target=2.0,
        )

        # 后面决定报价宽度时会用到
        self.warmup_num_transitions: int = 0
        self.rate_move_count: int = 0
        self.model_ready: bool = False

        # grader 的 cash balance 不会自动同步到 self.cash_balance。
        # 我们自己维护一个 shadow cash。
        self.shadow_cash_balance: float = float(cash_balance)
        self.starting_cash_balance: float = float(cash_balance)

        # 必须分别记录 gross long / gross short，
        # 不能只记录净头寸。
        self.long_quantity_by_option_id: dict[int, int] = defaultdict(int)

        self.short_quantity_by_option_id: dict[int, int] = defaultdict(int)

        # 保存当前持仓对应的合约，方便到期结算。
        self.held_option_by_id: dict[int, BinaryOption] = {}

        # 固定的估计先验，防止每天重估时把昨天的估计
        # 再次当作先验，产生重复收缩。
        self._estimation_prior_parameters = self.estimated_parameters

        # 保存 warm-up 和之后每天观察到的底层数据。
        self._estimation_history_by_underlying_id: dict[
            int,
            list[float],
        ] = {underlying.underlying_id: [float(underlying.value)] for underlying in underlying_initial_state}

    def on_step_advance(
        self,
        new_underlying_state: list[Underlying],
        new_option_state: list[BinaryOption],
    ) -> None:
        new_values = {underlying.underlying_id: underlying.value for underlying in new_underlying_state}

        new_options_by_id = {option.option_id: option for option in new_option_state}

        held_option_ids = set(self.long_quantity_by_option_id) | set(self.short_quantity_by_option_id)

        for option_id in held_option_ids:
            previous_option = self.held_option_by_id.get(option_id)

            if previous_option is None:
                continue

            updated_option = new_options_by_id.get(option_id)

            # 上一步是1d，现在应当变成0d或从active列表消失。
            expires_now = previous_option.steps_until_expiry <= 1 and (
                updated_option is None or updated_option.steps_until_expiry == 0
            )

            if expires_now:
                valuation_option = updated_option if updated_option is not None else previous_option

                expiry_value = valuation_option.expiry_valuation(new_values)

                long_quantity = self.long_quantity_by_option_id.pop(
                    option_id,
                    0,
                )

                short_quantity = self.short_quantity_by_option_id.pop(
                    option_id,
                    0,
                )

                # long 到期 credit = q*Y
                # short 到期 credit = q*(1-Y)
                self.shadow_cash_balance += long_quantity * expiry_value + short_quantity * (1.0 - expiry_value)

                # 本地净仓位也归零
                self.position.option_quantity_by_option_id[option_id] = 0

                self.held_option_by_id.pop(
                    option_id,
                    None,
                )

            else:
                # 还没到期，保存更新后的合约期限。
                if updated_option is not None:
                    self.held_option_by_id[option_id] = updated_option
                else:
                    # 如果新列表没有提供它，保守地自行减一天。
                    self.held_option_by_id[option_id] = previous_option.advance_step()

        self.underlying_state = new_underlying_state

        self.active_option_state = new_option_state

        # 只在 $40 本金场景启用滚动参数重估。
        # $10 / $20 场景继续使用开局 warm-up 的静态估计，
        # 保留它们已经验证过的报价和排名。
        use_rolling_refit = self.starting_cash_balance >= 40.0 - 1e-12

        # 即使在 $40 场景更新参数，也不允许 ready/not-ready
        # 报价档位在交易过程中发生跳变。
        opening_model_ready = self.model_ready

        observed_values = {underlying.underlying_id: float(underlying.value) for underlying in new_underlying_state}

        tracked_ids = set(self._estimation_history_by_underlying_id)

        if use_rolling_refit and tracked_ids and tracked_ids.issubset(observed_values):
            for underlying_id in tracked_ids:
                self._estimation_history_by_underlying_id[underlying_id].append(observed_values[underlying_id])

            history_lengths = {len(values) for values in (self._estimation_history_by_underlying_id.values())}

            if len(history_lengths) == 1:
                refreshed_history = MarketHistory(
                    values_by_underlying_id={
                        underlying_id: tuple(values)
                        for underlying_id, values in (self._estimation_history_by_underlying_id.items())
                    }
                )

                self.warm_up(refreshed_history)

                # 冻结开局报价制度，只让 theo 吸收新数据。
                self.model_ready = opening_model_ready

    def on_trade(
        self,
        option: BinaryOption,
        price: float,
        quantity: int,
        counterparty_id: int,
    ) -> None:
        # 保留原模板的净仓位更新
        self.position.add_option_quantity(
            option.option_id,
            quantity,
        )

        # 保存最新版本的合约
        self.held_option_by_id[option.option_id] = option

        # grader 每次成交都立即扣最大可能损失
        self.shadow_cash_balance -= self._maximum_loss_for_trade(
            price=price,
            signed_quantity=quantity,
        )

        if quantity > 0:
            # maker 买入
            self.long_quantity_by_option_id[option.option_id] += quantity

        elif quantity < 0:
            # maker 卖出
            sold_quantity = -quantity

            self.short_quantity_by_option_id[option.option_id] += sold_quantity

    @property
    def name(self) -> str:  # type: ignore[empty-body]
        return "ZCtrader_V7B"

    def _underlying_values(self) -> dict[int, float]:
        return {underlying.underlying_id: underlying.value for underlying in self.underlying_state}

    def _normal_cdf(self, value: float) -> float:
        return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))

    def _fed_terminal_distribution(
        self,
        market_parameters: MarketParameters,
        steps: int,
        initial_rate: float,
    ) -> dict[float, float]:
        distribution: dict[float, float] = {initial_rate: 1.0}

        for _ in range(steps):
            next_distribution: defaultdict[float, float] = defaultdict(float)
            for rate, state_probability in distribution.items():
                up_probability, down_probability = market_parameters.tilted_rate_probabilities(rate)
                stay_probability = 1.0 - up_probability - down_probability

                up_rate = market_parameters.next_rate_value(rate, 1)
                down_rate = market_parameters.next_rate_value(rate, -1)

                next_distribution[up_rate] += state_probability * up_probability
                next_distribution[down_rate] += state_probability * down_probability
                next_distribution[rate] += state_probability * stay_probability

            distribution = dict(next_distribution)

        return distribution

    def _price_single_company_option(
        self,
        market_parameters: MarketParameters,
        option: BinaryOption,
        current_values: dict[int, float],
    ) -> float:

        leg = option.legs[0]
        company_id = leg.underlying_id

        # Choose parameters
        if company_id == AJARAI_UNDERLYING_ID:
            drift = market_parameters.ajarai_drift
            rate_beta = market_parameters.ajarai_rate_beta
            sector_beta = market_parameters.ajarai_sector_beta
            idio_std_dev = market_parameters.ajarai_idio_std_dev

        elif company_id == THERIODIC_UNDERLYING_ID:
            drift = market_parameters.theriodic_drift
            rate_beta = market_parameters.theriodic_rate_beta
            sector_beta = market_parameters.theriodic_sector_beta
            idio_std_dev = market_parameters.theriodic_idio_std_dev

        else:
            return 0.5

        steps = option.steps_until_expiry
        initial_rate = current_values[FED_FUNDS_RATE_UNDERLYING_ID]
        initial_company_value = current_values[company_id]

        if initial_company_value <= 0.0:
            return 1.0 if leg.weight * initial_company_value >= option.strike else 0.0

        terminal_rate_distribution = self._fed_terminal_distribution(
            market_parameters=market_parameters,
            steps=steps,
            initial_rate=initial_rate,
        )

        # company log return variance
        daily_variance = (sector_beta * market_parameters.sector_std_dev) ** 2 + idio_std_dev**2

        # n-day std
        terminal_std_dev = math.sqrt(steps * daily_variance)

        probability = 0.0

        # 对每个可能的到期 FED 分别计算公司事件概率
        for terminal_rate, rate_probability in terminal_rate_distribution.items():
            mean_log_value = (
                math.log(initial_company_value) + steps * drift + rate_beta * (terminal_rate - initial_rate)
            )

            # 原事件：
            # leg.weight * company_value >= strike

            if leg.weight > 0.0:
                # 除以正数，不等号方向不变：
                # company_value >= strike / weight
                threshold = option.strike / leg.weight

                # 公司估值始终为正，所以正数 >= 非正阈值
                if threshold <= 0.0:
                    conditional_probability = 1.0

                else:
                    log_threshold = math.log(threshold)

                    # 防止标准差为 0 时出现除以 0
                    if terminal_std_dev <= 1e-12:
                        conditional_probability = 1.0 if mean_log_value >= log_threshold else 0.0
                    else:
                        z_score = (mean_log_value - log_threshold) / terminal_std_dev

                        conditional_probability = self._normal_cdf(z_score)

            else:
                # 除以负数，不等号方向翻转：
                # company_value <= strike / weight
                threshold = option.strike / leg.weight

                # 正数不可能 <= 非正数
                if threshold <= 0.0:
                    conditional_probability = 0.0

                else:
                    log_threshold = math.log(threshold)

                    if terminal_std_dev <= 1e-12:
                        conditional_probability = 1.0 if mean_log_value <= log_threshold else 0.0
                    else:
                        z_score = (log_threshold - mean_log_value) / terminal_std_dev

                        conditional_probability = self._normal_cdf(z_score)

            # P(FED level) × P(event happens | FED level)
            probability += rate_probability * conditional_probability

        return max(0.0, min(1.0, probability))

    def _company_parameters(
        self,
        market_parameters: MarketParameters,
        company_id: int,
    ) -> tuple[float, float, float, float]:
        """
        返回：
        drift, rate_beta, sector_beta, idio_std_dev
        """

        if company_id == AJARAI_UNDERLYING_ID:
            return (
                market_parameters.ajarai_drift,
                market_parameters.ajarai_rate_beta,
                market_parameters.ajarai_sector_beta,
                market_parameters.ajarai_idio_std_dev,
            )

        return (
            market_parameters.theriodic_drift,
            market_parameters.theriodic_rate_beta,
            market_parameters.theriodic_sector_beta,
            market_parameters.theriodic_idio_std_dev,
        )

    def _price_company_comparison_option(
        self,
        market_parameters: MarketParameters,
        option: BinaryOption,
        current_values: dict[int, float],
    ) -> float:
        """
        定价两个公司、相反符号权重、strike=0 的比较合约。

        例如：
        THR - AJR >= 0
        AJR - THR >= 0
        2*THR - 3*AJR >= 0
        """

        # 进入这个方法前，我们已经确认 option 有且只有两个 legs。
        first_leg, second_leg = option.legs

        # 找出正权重和负权重的公司。
        # 不依赖 legs 原本的排列顺序。
        if first_leg.weight > 0.0:
            positive_leg = first_leg
            negative_leg = second_leg
        else:
            positive_leg = second_leg
            negative_leg = first_leg

        positive_company_id = positive_leg.underlying_id
        negative_company_id = negative_leg.underlying_id

        positive_initial_value = current_values[positive_company_id]

        negative_initial_value = current_values[negative_company_id]

        # 公司估值在题目模型中应该始终为正。
        # 这个分支用于防止意外出现 log(0)。
        if positive_initial_value <= 0.0 or negative_initial_value <= 0.0:
            return 0.5

        (
            positive_drift,
            positive_rate_beta,
            positive_sector_beta,
            positive_idio_std_dev,
        ) = self._company_parameters(
            market_parameters=market_parameters,
            company_id=positive_company_id,
        )

        (
            negative_drift,
            negative_rate_beta,
            negative_sector_beta,
            negative_idio_std_dev,
        ) = self._company_parameters(
            market_parameters=market_parameters,
            company_id=negative_company_id,
        )

        steps = option.steps_until_expiry

        initial_rate = current_values[FED_FUNDS_RATE_UNDERLYING_ID]

        terminal_rate_distribution = self._fed_terminal_distribution(
            market_parameters=market_parameters,
            steps=steps,
            initial_rate=initial_rate,
        )

        # 原事件：
        #
        # positive_weight * positive_company
        #     + negative_weight * negative_company >= 0
        #
        # 因为 negative_weight < 0，可以变为：
        #
        # positive_company / negative_company
        #     >= (-negative_weight) / positive_weight

        required_log_ratio = math.log((-negative_leg.weight) / positive_leg.weight)

        # 两家公司共享同一个 sector shock。
        # 所以在 log ratio 中，sector beta 是两者之差。
        daily_log_ratio_variance = (
            ((positive_sector_beta - negative_sector_beta) * market_parameters.sector_std_dev) ** 2
            + positive_idio_std_dev**2
            + negative_idio_std_dev**2
        )

        terminal_log_ratio_std_dev = math.sqrt(steps * daily_log_ratio_variance)

        probability = 0.0

        for terminal_rate, rate_probability in terminal_rate_distribution.items():
            mean_log_ratio = (
                math.log(positive_initial_value / negative_initial_value)
                + steps * (positive_drift - negative_drift)
                + (positive_rate_beta - negative_rate_beta) * (terminal_rate - initial_rate)
            )

            if terminal_log_ratio_std_dev <= 1e-12:
                conditional_probability = 1.0 if mean_log_ratio >= required_log_ratio else 0.0

            else:
                z_score = (mean_log_ratio - required_log_ratio) / terminal_log_ratio_std_dev

                conditional_probability = self._normal_cdf(z_score)

            probability += rate_probability * conditional_probability

        return max(
            0.0,
            min(1.0, probability),
        )

    def _linear_regression(
        self,
        x_values: list[float],
        y_values: list[float],
    ) -> tuple[float, float]:
        """
        拟合：

            y ≈ intercept + slope * x

        返回：
            intercept, slope
        """

        count = min(
            len(x_values),
            len(y_values),
        )

        if count == 0:
            return 0.0, 0.0

        mean_x = sum(x_values[:count]) / count
        mean_y = sum(y_values[:count]) / count

        denominator = sum((x_values[index] - mean_x) ** 2 for index in range(count))

        # x 没有变化时，无法估计 slope
        if denominator <= 1e-12:
            return mean_y, 0.0

        numerator = sum((x_values[index] - mean_x) * (y_values[index] - mean_y) for index in range(count))

        slope = numerator / denominator
        intercept = mean_y - slope * mean_x

        return intercept, slope

    def _maximum_loss_for_trade(
        self,
        price: float,
        signed_quantity: int,
    ) -> float:
        """
        signed_quantity > 0：maker 买入
        signed_quantity < 0：maker 卖出
        """

        if signed_quantity > 0:
            # 买入 q@p，最大损失是 q*p
            return max(
                0.0,
                price * signed_quantity,
            )

        if signed_quantity < 0:
            # 卖出 q@p，最大损失是 q*(1-p)
            sold_quantity = -signed_quantity

            return max(
                0.0,
                (1.0 - price) * sold_quantity,
            )

        return 0.0

    def price_option(self, option: BinaryOption) -> float:  # type: ignore[empty-body]
        # Pricing is separate from fills and has no cash or inventory side effects.
        return self.price_option_from_parameters(
            market_parameters=self.estimated_parameters,
            option=option,
        )

    def price_option_from_parameters(
        self,
        market_parameters: MarketParameters,
        option: BinaryOption,
    ) -> float:
        current_values = self._underlying_values()

        # 已经到期：直接判断事件是否成立
        if option.steps_until_expiry == 0:
            return option.expiry_valuation(current_values)

        # Version 1A：单腿 FED
        if len(option.legs) == 1 and option.legs[0].underlying_id == FED_FUNDS_RATE_UNDERLYING_ID:
            leg = option.legs[0]

            terminal_distribution = self._fed_terminal_distribution(
                market_parameters=market_parameters,
                steps=option.steps_until_expiry,
                initial_rate=current_values[FED_FUNDS_RATE_UNDERLYING_ID],
            )

            probability = sum(
                state_probability
                for terminal_rate, state_probability in terminal_distribution.items()
                if (leg.weight * terminal_rate >= option.strike)
            )

            return max(
                0.0,
                min(1.0, probability),
            )

        # Version 1B：单腿 AJR 或 THR
        if len(option.legs) == 1 and option.legs[0].underlying_id in (
            AJARAI_UNDERLYING_ID,
            THERIODIC_UNDERLYING_ID,
        ):
            return self._price_single_company_option(
                market_parameters=market_parameters,
                option=option,
                current_values=current_values,
            )

        # Version 1C：AJR/THR comparison
        if (
            len(option.legs) == 2
            and {leg.underlying_id for leg in option.legs}
            == {
                AJARAI_UNDERLYING_ID,
                THERIODIC_UNDERLYING_ID,
            }
            and (option.legs[0].weight * option.legs[1].weight < 0.0)
            and abs(option.strike) <= 1e-12
        ):
            return self._price_company_comparison_option(
                market_parameters=market_parameters,
                option=option,
                current_values=current_values,
            )

        # 其他一般多腿或非零 strike spread 暂不处理
        return 0.5

    def _supports_active_pricing(
        self,
        option: BinaryOption,
    ) -> bool:
        # 已实现的单腿 FED / AJR / THR
        if len(option.legs) == 1:
            return option.legs[0].underlying_id in (
                FED_FUNDS_RATE_UNDERLYING_ID,
                AJARAI_UNDERLYING_ID,
                THERIODIC_UNDERLYING_ID,
            )

        # 已实现的 AJR/THR、相反方向、strike=0 comparison
        if len(option.legs) == 2:
            underlying_ids = {leg.underlying_id for leg in option.legs}

            return (
                underlying_ids
                == {
                    AJARAI_UNDERLYING_ID,
                    THERIODIC_UNDERLYING_ID,
                }
                and (option.legs[0].weight * option.legs[1].weight < 0.0)
                and abs(option.strike) <= 1e-12
            )

        return False

    def _floor_to_cent(
        self,
        value: float,
    ) -> float:
        value = max(0.0, min(1.0, value))

        return math.floor(value * 100.0 + 1e-9) / 100.0

    def _ceil_to_cent(
        self,
        value: float,
    ) -> float:
        value = max(
            0.0,
            min(1.0, value),
        )

        return math.ceil(value * 100.0 - 1e-9) / 100.0

    def quote(
        self,
        option: BinaryOption,
        counterparty_id: int,
    ) -> Quote:
        zero_risk_quantity = 10

        safe_quote = Quote(
            bid_price=0.00,
            bid_quantity=zero_risk_quantity,
            offer_price=1.00,
            offer_quantity=zero_risk_quantity,
        )

        # 不支持的期权只报零风险边界价格。
        if not self._supports_active_pricing(option):
            return safe_quote

        fair_value = self.price_option(option)

        if not math.isfinite(fair_value):
            return safe_quote

        fair_value = max(
            0.0,
            min(1.0, fair_value),
        )

        is_40_dollar_session = self.starting_cash_balance >= 40.0 - 1e-12

        has_large_profit_cushion = self.shadow_cash_balance >= (self.starting_cash_balance - 1e-12)

        # --------------------------------------------------
        # 根据模型可信度和初始本金选择spread与风险容量
        # --------------------------------------------------

        if self.model_ready:
            if is_40_dollar_session:
                # This uses available collateral, not marked profit; see strategy notes.
                if has_large_profit_cushion:
                    half_spread = 0.02
                else:
                    # Widen when available collateral is below its starting level.
                    half_spread = 0.05

            elif self.starting_cash_balance >= 20.0 - 1e-12:
                half_spread = 0.04

            else:
                half_spread = 0.10

            # $10本金：25%
            # $20本金：30%
            # $40本金：40%
            if self.starting_cash_balance <= 10.0 + 1e-12:
                rfq_risk_fraction = 0.25

            elif self.starting_cash_balance >= 40.0 - 1e-12:
                rfq_risk_fraction = 0.40

            else:
                rfq_risk_fraction = 0.30

            rfq_cash_floor = (1.0 - rfq_risk_fraction) * self.starting_cash_balance

            maximum_side_risk = rfq_risk_fraction * self.starting_cash_balance

            capital_scaled_quantity = max(
                1,
                math.floor(2.0 * rfq_risk_fraction * self.starting_cash_balance + 1e-12),
            )

            # Minimum capacity for low-cost contracts; cash limits still apply.
            if self.starting_cash_balance <= 10.0 + 1e-12:
                minimum_active_capacity = 40
            else:
                minimum_active_capacity = 30

            maximum_active_quantity = max(
                minimum_active_capacity,
                capital_scaled_quantity,
            )

            maximum_absolute_position = max(
                minimum_active_capacity,
                capital_scaled_quantity,
            )

        else:
            # Conservative execution when the opening history is insufficient.
            half_spread = 0.25

            rfq_cash_floor = 0.95 * self.starting_cash_balance

            maximum_side_risk = 0.50
            maximum_active_quantity = 1
            maximum_absolute_position = 1

        # --------------------------------------------------
        # 根据theo生成bid和offer
        # --------------------------------------------------

        # Per-option reservation-price adjustment near the position limit.
        net_position = self.position.option_quantity_by_option_id.get(option.option_id, 0)

        position_utilization = max(
            -1.0,
            min(
                1.0,
                net_position / max(1, maximum_absolute_position),
            ),
        )

        stressed_utilization = max(
            0.0,
            min(
                1.0,
                (abs(position_utilization) - 0.75) / 0.25,
            ),
        )

        if position_utilization > 0.0:
            inventory_shift = -0.005 * stressed_utilization
        elif position_utilization < 0.0:
            inventory_shift = 0.005 * stressed_utilization
        else:
            inventory_shift = 0.0

        quote_center = max(
            0.0,
            min(1.0, fair_value + inventory_shift),
        )

        bid_price = self._floor_to_cent(quote_center - half_spread)

        offer_price = self._ceil_to_cent(quote_center + half_spread)

        is_40_dollar_session = self.starting_cash_balance >= 40.0 - 1e-12

        is_20_dollar_session = self.starting_cash_balance >= 20.0 - 1e-12 and self.starting_cash_balance < 40.0 - 1e-12

        is_single_leg_fed = len(option.legs) == 1 and option.legs[0].underlying_id == FED_FUNDS_RATE_UNDERLYING_ID

        is_short_dated_twenty_fed = (
            self.model_ready and is_20_dollar_session and is_single_leg_fed and option.steps_until_expiry <= 1
        )

        if is_short_dated_twenty_fed:
            # Historical capital-specific exception retained from the submission.
            short_fed_risk_fraction = 0.40

            rfq_cash_floor = (1.0 - short_fed_risk_fraction) * self.starting_cash_balance

            maximum_side_risk = short_fed_risk_fraction * self.starting_cash_balance

        available_rfq_risk = max(
            0.0,
            self.shadow_cash_balance - rfq_cash_floor,
        )

        # 一次RFQ只会成交其中一侧，所以bid和offer
        # 都可以分别使用这份风险容量。
        side_risk_budget = min(
            maximum_side_risk,
            available_rfq_risk,
        )

        # --------------------------------------------------
        # bid和offer分别设置单张风险门槛
        # --------------------------------------------------

        bid_per_contract_risk_cap = 0.50
        offer_per_contract_risk_cap = 0.50

        if is_40_dollar_session:
            # $40场景已经验证适合完整双边。
            bid_per_contract_risk_cap = 1.00
            offer_per_contract_risk_cap = 1.00

        elif is_short_dated_twenty_fed:
            # 只对$20、1日FED开放完整双边。
            bid_per_contract_risk_cap = 1.00
            offer_per_contract_risk_cap = 1.00

        if bid_price > bid_per_contract_risk_cap + 1e-12:
            bid_price = 0.00

        if 1.0 - offer_price > offer_per_contract_risk_cap + 1e-12:
            offer_price = 1.00

        # --------------------------------------------------
        # 计算bid一侧的quantity
        # --------------------------------------------------

        if bid_price == 0.00:
            # 在0买入没有最大亏损。
            bid_quantity = zero_risk_quantity

        else:
            bid_position_capacity = max(
                0,
                maximum_absolute_position - net_position,
            )

            # 买入每张的最大损失是bid_price。
            bid_risk_capacity = max(
                0,
                math.floor((side_risk_budget + 1e-12) / bid_price),
            )

            bid_quantity = min(
                maximum_active_quantity,
                bid_position_capacity,
                bid_risk_capacity,
            )

            if bid_quantity <= 0:
                bid_price = 0.00
                bid_quantity = zero_risk_quantity

        # --------------------------------------------------
        # 计算offer一侧的quantity
        # --------------------------------------------------

        if offer_price == 1.00:
            # 在1卖出没有最大亏损。
            offer_quantity = zero_risk_quantity

        else:
            offer_position_capacity = max(
                0,
                maximum_absolute_position + net_position,
            )

            offer_loss_per_contract = 1.0 - offer_price

            offer_risk_capacity = max(
                0,
                math.floor((side_risk_budget + 1e-12) / offer_loss_per_contract),
            )

            offer_quantity = min(
                maximum_active_quantity,
                offer_position_capacity,
                offer_risk_capacity,
            )

            if offer_quantity <= 0:
                offer_price = 1.00
                offer_quantity = zero_risk_quantity

        # 防止出现交叉报价。
        if bid_price >= offer_price:
            return safe_quote

        return Quote(
            bid_price=bid_price,
            bid_quantity=bid_quantity,
            offer_price=offer_price,
            offer_quantity=offer_quantity,
        )

    def respond_to_fok(
        self,
        option: BinaryOption,
        fok_order: FokOrder,
    ) -> bool:
        price = float(fok_order.price)
        quantity = fok_order.quantity

        if not math.isfinite(price) or price < 0.0 or price > 1.0 or quantity <= 0:
            return False

        # 零风险边界订单继续直接接受。
        if fok_order.order_type == OrderType.BUY and price == 1.0:
            return True

        if fok_order.order_type == OrderType.SELL and price == 0.0:
            return True

        is_ten_dollar_not_ready = not self.model_ready and self.starting_cash_balance <= 10.0 + 1e-12

        # 除$10探针外，其他not-ready FOK仍全部拒绝。
        if not self.model_ready and not is_ten_dollar_not_ready:
            return False

        fair_value = self.price_option(option)

        if not math.isfinite(fair_value):
            return False

        fair_value = max(
            0.0,
            min(1.0, fair_value),
        )

        if fok_order.order_type == OrderType.BUY:
            # 客户买入，我们卖出。
            maker_quantity = -quantity
            edge_per_contract = price - fair_value

        elif fok_order.order_type == OrderType.SELL:
            # 客户卖出，我们买入。
            maker_quantity = quantity
            edge_per_contract = fair_value - price

        else:
            return False

        # FOK不能部分接受，按整张订单计算最坏损失。
        full_order_maximum_loss = self._maximum_loss_for_trade(
            price,
            maker_quantity,
        )

        if not math.isfinite(full_order_maximum_loss) or full_order_maximum_loss < 0.0:
            return False

        cash_reserve = 0.50 * self.starting_cash_balance

        cash_above_reserve = max(
            0.0,
            self.shadow_cash_balance - cash_reserve,
        )

        if is_ten_dollar_not_ready:
            # Require a wide edge in the small-capital, short-history regime.
            experiment_loss_limit = 0.50

            experiment_cash_floor = max(
                0.0,
                self.starting_cash_balance - experiment_loss_limit,
            )

            cash_above_experiment_floor = max(
                0.0,
                self.shadow_cash_balance - experiment_cash_floor,
            )

            risk_budget = min(
                0.50,
                cash_above_reserve,
                cash_above_experiment_floor,
            )

            minimum_edge_per_contract = 0.25

        else:
            # Limit risky FOK participation relative to starting collateral.
            experiment_loss_limit = 0.10

            experiment_cash_floor = max(
                0.0,
                self.starting_cash_balance - experiment_loss_limit,
            )

            cash_above_experiment_floor = max(
                0.0,
                self.shadow_cash_balance - experiment_cash_floor,
            )

            risk_budget = min(
                0.25,
                0.02 * self.starting_cash_balance,
                cash_above_reserve,
                cash_above_experiment_floor,
            )

            minimum_edge_per_contract = 0.02

        return edge_per_contract + 1e-12 >= minimum_edge_per_contract and full_order_maximum_loss <= risk_budget + 1e-12

    def warm_up(
        self,
        market_history: MarketHistory,
    ) -> None:
        history = market_history.values_by_underlying_id

        required_ids = {
            FED_FUNDS_RATE_UNDERLYING_ID,
            AJARAI_UNDERLYING_ID,
            THERIODIC_UNDERLYING_ID,
        }

        # 即使历史不足10天，也先保存下来；
        # 后续每天的新数据可以让样本逐渐增长。
        if required_ids.issubset(history):
            self._estimation_history_by_underlying_id = {
                underlying_id: list(history[underlying_id]) for underlying_id in required_ids
            }

        # 历史缺失或太短时，保留默认参数
        if not required_ids.issubset(history) or market_history.num_days < 10:
            return

        rate_values = history[FED_FUNDS_RATE_UNDERLYING_ID]

        ajarai_values = history[AJARAI_UNDERLYING_ID]

        theriodic_values = history[THERIODIC_UNDERLYING_ID]

        # 之后要取 log，所以公司估值必须为正
        if any(value <= 0.0 for value in ajarai_values) or any(value <= 0.0 for value in theriodic_values):
            return

        transition_count = market_history.num_days - 1

        prior = self._estimation_prior_parameters

        self.warmup_num_transitions = transition_count

        # --------------------------------------------------
        # 1. FED 参数
        # --------------------------------------------------

        rate_changes = [
            round(
                rate_values[index + 1] - rate_values[index],
                10,
            )
            for index in range(transition_count)
        ]

        nonzero_rate_moves = sorted(abs(change) for change in rate_changes if abs(change) > 1e-9)

        self.rate_move_count = len(nonzero_rate_moves)

        if nonzero_rate_moves:
            # 正常情况下所有非零变化都等于 rate_step。
            # 取中位位置可以避免个别异常值。
            estimated_rate_step = round(
                nonzero_rate_moves[len(nonzero_rate_moves) // 2],
                2,
            )
        else:
            estimated_rate_step = prior.rate_step

        if estimated_rate_step <= 0.0:
            estimated_rate_step = 0.25

        # rate_target 和基础 up/down 概率不能从一条路径中
        # 分别唯一识别。这里选择历史平均利率作为等价 target，
        # 使估计集中在实际观察到的利率区域。
        rate_target = max(
            0.0,
            sum(rate_values[:transition_count]) / transition_count,
        )

        rate_predictors = [rate_target - rate_values[index] for index in range(transition_count)]

        up_indicators = [1.0 if rate_changes[index] > 1e-9 else 0.0 for index in range(transition_count)]

        (
            up_intercept,
            up_slope,
        ) = self._linear_regression(
            rate_predictors,
            up_indicators,
        )

        # FED=0 时，一次 down draw 仍然显示为 0，
        # 和真正的 stay 无法区分。
        # 所以下跌概率回归排除从 0 开始的样本。
        down_predictors: list[float] = []
        down_indicators: list[float] = []

        for index in range(transition_count):
            if rate_values[index] > 1e-12:
                down_predictors.append(rate_predictors[index])
                down_indicators.append(1.0 if rate_changes[index] < -1e-9 else 0.0)

        if down_predictors:
            (
                down_intercept,
                down_slope,
            ) = self._linear_regression(
                down_predictors,
                down_indicators,
            )
        else:
            down_intercept = prior.rate_down_probability
            down_slope = -prior.rate_reversion_strength

        # 理论上：
        #
        # up slope   = +reversion
        # down slope = -reversion
        raw_reversion = (up_slope - down_slope) / 2.0

        raw_reversion = max(
            0.0,
            min(1.0, raw_reversion),
        )

        raw_up_probability = max(
            0.001,
            min(0.999, up_intercept),
        )

        raw_down_probability = max(
            0.001,
            min(0.999, down_intercept),
        )

        # 向默认参数轻微收缩，防止短历史得到 0 或 1
        prior = self._estimation_prior_parameters

        rate_data_weight = transition_count / (transition_count + 20.0)

        rate_reversion = rate_data_weight * raw_reversion + (1.0 - rate_data_weight) * prior.rate_reversion_strength

        rate_up_probability = (
            rate_data_weight * raw_up_probability + (1.0 - rate_data_weight) * prior.rate_up_probability
        )

        rate_down_probability = (
            rate_data_weight * raw_down_probability + (1.0 - rate_data_weight) * prior.rate_down_probability
        )

        probability_sum = rate_up_probability + rate_down_probability

        if probability_sum > 0.999:
            scale = 0.999 / probability_sum
            rate_up_probability *= scale
            rate_down_probability *= scale

        # --------------------------------------------------
        # 2. 公司 drift 和 rate beta
        # --------------------------------------------------

        ajarai_log_returns = [
            math.log(ajarai_values[index + 1] / ajarai_values[index]) for index in range(transition_count)
        ]

        theriodic_log_returns = [
            math.log(theriodic_values[index + 1] / theriodic_values[index]) for index in range(transition_count)
        ]

        (
            _,
            raw_ajarai_rate_beta,
        ) = self._linear_regression(
            rate_changes,
            ajarai_log_returns,
        )

        (
            _,
            raw_theriodic_rate_beta,
        ) = self._linear_regression(
            rate_changes,
            theriodic_log_returns,
        )

        # FED 变化次数少时，rate beta 的估计很不稳定。
        # 因此向 0 收缩。
        beta_data_weight = self.rate_move_count / (self.rate_move_count + 5.0)

        ajarai_rate_beta = max(
            -2.0,
            min(
                2.0,
                raw_ajarai_rate_beta * beta_data_weight,
            ),
        )

        theriodic_rate_beta = max(
            -2.0,
            min(
                2.0,
                raw_theriodic_rate_beta * beta_data_weight,
            ),
        )

        mean_rate_change = sum(rate_changes) / transition_count

        ajarai_drift = sum(ajarai_log_returns) / transition_count - ajarai_rate_beta * mean_rate_change

        theriodic_drift = sum(theriodic_log_returns) / transition_count - theriodic_rate_beta * mean_rate_change

        # --------------------------------------------------
        # 3. 公司残差协方差
        # --------------------------------------------------

        ajarai_residuals = [
            ajarai_log_returns[index] - ajarai_drift - ajarai_rate_beta * rate_changes[index]
            for index in range(transition_count)
        ]

        theriodic_residuals = [
            theriodic_log_returns[index] - theriodic_drift - theriodic_rate_beta * rate_changes[index]
            for index in range(transition_count)
        ]

        degrees_of_freedom = max(
            1,
            transition_count - 2,
        )

        sample_ajarai_variance = sum(residual**2 for residual in ajarai_residuals) / degrees_of_freedom

        sample_theriodic_variance = sum(residual**2 for residual in theriodic_residuals) / degrees_of_freedom

        sample_residual_covariance = (
            sum(ajarai_residuals[index] * theriodic_residuals[index] for index in range(transition_count))
            / degrees_of_freedom
        )

        # 短样本时把方差向每日 2% 波动收缩，
        # 把 covariance 向 0 收缩。
        variance_data_weight = transition_count / (transition_count + 10.0)

        prior_variance = 0.02**2
        variance_floor = 0.002**2

        ajarai_variance = max(
            variance_floor,
            variance_data_weight * sample_ajarai_variance + (1.0 - variance_data_weight) * prior_variance,
        )

        theriodic_variance = max(
            variance_floor,
            variance_data_weight * sample_theriodic_variance + (1.0 - variance_data_weight) * prior_variance,
        )

        residual_covariance = variance_data_weight * sample_residual_covariance

        # 确保协方差矩阵合法
        covariance_limit = 0.98 * math.sqrt(ajarai_variance * theriodic_variance)

        residual_covariance = max(
            -covariance_limit,
            min(
                covariance_limit,
                residual_covariance,
            ),
        )

        # --------------------------------------------------
        # 4. 构造一组等价 MarketParameters
        # --------------------------------------------------
        #
        # history 只能识别：
        #
        # Var(AJR), Var(THR), Cov(AJR, THR)
        #
        # 无法唯一识别五个独立的 sector/idio 参数。
        # 下面的分解未必是真实结构，但会复原这三个矩。

        sector_std_dev = 1.0

        ajarai_sector_beta = math.sqrt(ajarai_variance)

        ajarai_idio_std_dev = 0.0

        theriodic_sector_beta = residual_covariance / ajarai_sector_beta

        theriodic_shared_variance = (theriodic_sector_beta * sector_std_dev) ** 2

        theriodic_idio_std_dev = math.sqrt(
            max(
                0.0,
                theriodic_variance - theriodic_shared_variance,
            )
        )

        # Final submission uses the unshrunk drift estimate. An earlier
        # shrinkage experiment was reverted after the development score fell.

        self.estimated_parameters = MarketParameters(
            ajarai_drift=ajarai_drift,
            ajarai_idio_std_dev=(ajarai_idio_std_dev),
            ajarai_rate_beta=ajarai_rate_beta,
            ajarai_sector_beta=(ajarai_sector_beta),
            rate_down_probability=(rate_down_probability),
            rate_reversion_strength=(rate_reversion),
            rate_up_probability=(rate_up_probability),
            sector_std_dev=sector_std_dev,
            theriodic_drift=theriodic_drift,
            theriodic_idio_std_dev=(theriodic_idio_std_dev),
            theriodic_rate_beta=(theriodic_rate_beta),
            theriodic_sector_beta=(theriodic_sector_beta),
            rate_step=estimated_rate_step,
            rate_target=rate_target,
        )

        self.model_ready = transition_count >= 20 and self.rate_move_count >= 3
