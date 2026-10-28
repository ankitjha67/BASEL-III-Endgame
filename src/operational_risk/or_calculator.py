"""Operational risk calculator — US ERBA NPR §__.150 (12 CFR 217.150).

Implements the standardized operational risk capital requirement of
Subpart E as re-proposed in March 2026:

    RWA_op = 12.5 x BIC                                    §__.150(a)
    BIC    = f(BI)  (12% / 15% / 18% marginal tiers)       §__.150(b)
    BI     = ILDC + noninterest component                  §__.150(c)(1)

    ILDC   = min( Avg3y(|TII - TIE|), 0.0225 x Avg3y(IEA) )
             + Avg3y(dividend income)                      §__.150(c)(1)(i)

    Noninterest component
           = Avg3y( |total noninterest income
                     + realized G/L on HTM securities
                     + realized G/L on AFS debt securities
                     - noninterest expense for BI
                     - 0.7 x (noninterest income from investment management,
                              investment services and non-lending treasury
                              services
                              - noninterest expense for BI from those
                                activities)|
                    + total operational losses )           §__.150(c)(1)(ii)

The US rule has no internal loss multiplier: the capital requirement is
the BIC itself (preamble p. 197 fn. 216).  The BCBS d424 services /
financial / loss components are NOT part of the US calculation and are
not implemented here (see the reference-only section of ``or_params``).

Averaging (§__.150(c); preamble pp. 199-200): every input is averaged over
the three most recent four-calendar-quarter periods.  The absolute values
in both components sit INSIDE the average, so inputs are accepted either
as three annual values (exact) or as a single pre-averaged figure (exact
only when the sign of the netted quantity is the same in all three
periods — the caller is responsible for that).  Interest-earning assets
may additionally be supplied as twelve quarter-end balances, and total
operational losses as twelve quarterly totals.

Inputs for an acquired or merged entity must be included for the periods
prior to the acquisition; divested activities may be excluded only with
prior agency approval (preamble pp. 201, 209).

Units: $M throughout.

Reference: ERBA NPR §__.150, §__.101; preamble Section IV.D pp. 193-216.
"""

from __future__ import annotations

from pydantic import (
    BaseModel,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from src.operational_risk.or_params import (
    BI_AVERAGING_PERIODS,
    BIC_BUCKETS,
    BIC_COEFFICIENTS,
    IEA_AVERAGING_QUARTERS,
    ILDC_INTEREST_CAP_RATE,
    ILM,
    LOSS_COLLECTION_THRESHOLD_USD,
    LOSS_DATA_YEARS,
    NIM_REVIEW_THRESHOLD,
    RWA_CONVERSION_FACTOR,
    SERVICES_NET_INCOME_FACTOR,
    LossEventType,
    ServiceLine,
    aggregate_quarterly_losses_to_periods,
    average_over_periods,
    compute_bic,
)

# A BI input: either a pre-computed three-year average, or the three
# annual (four-quarter) values, oldest first.
AnnualInput = float | list[float]


def _as_periods(value: AnnualInput, name: str) -> list[float]:
    """Expand a BI input to ``BI_AVERAGING_PERIODS`` period values.

    A scalar is broadcast to every period (it is already a three-year
    average); a list must hold exactly three annual values.

    Args:
        value: Scalar average or list of annual values, in $M.
        name: Field name for error messages.

    Returns:
        List of three period values in $M.

    Raises:
        ValueError: If a list does not have three entries.

    Reference:
        ERBA NPR §__.150(c) averaging convention.
    """
    if isinstance(value, (int, float)):
        return [float(value)] * BI_AVERAGING_PERIODS
    if len(value) != BI_AVERAGING_PERIODS:
        raise ValueError(
            f"{name}: expected {BI_AVERAGING_PERIODS} annual values, "
            f"got {len(value)}"
        )
    return [float(v) for v in value]


# =========================================================================
#  Input models
# =========================================================================

class ServiceLineData(BaseModel):
    """Noninterest income and expense for one §__.101 service line.

    Used for the 0.7 netting in the noninterest component.  Income is the
    noninterest income from the activity; expense is the portion of
    "noninterest expense for BI" attributable to the activity (so staff
    costs, premises, etc. are already excluded).

    Reference:
        ERBA NPR §__.150(c)(1)(ii); §__.101 definitions of investment
        management, investment services, non-lending treasury services.
    """
    service_line: ServiceLine = Field(description="Which §__.101 activity")
    noninterest_income: AnnualInput = Field(
        default=0.0,
        description="Noninterest income from the activity ($M; avg or 3 annual)",
    )
    noninterest_expense_for_bi: AnnualInput = Field(
        default=0.0,
        description=(
            "Noninterest expense for BI attributable to the activity "
            "($M; avg or 3 annual)"
        ),
    )


class BusinessIndicatorInputs(BaseModel):
    """Inputs to the business indicator per ERBA NPR §__.150(c)(1).

    Every monetary field is in $M and is either a single three-year
    average or a list of three annual (four-quarter) values, oldest first.
    Data sources: FR Y-9C Schedules HI/HC or Call Report Schedules RI/RC
    (preamble p. 200).

    Interest, lease and dividend component — §__.150(c)(1)(i):
        total_interest_income: Total interest income excluding dividend
            income (preamble fn. 219).
        total_interest_expense: Total interest expense (fn. 220).
        interest_earning_assets: §__.101 — gross outstanding loans and
            leases, interest-paying securities (HTM, AFS, trading),
            interest-bearing balances, federal funds sold and securities
            purchased under agreements to resell.  Accepts a scalar
            average, three annual averages, or twelve quarter-end
            balances (averaged as sum / 12).
        dividend_income: All dividends received on securities not
            consolidated in the banking organization's financial
            statements (fn. 222); added outside the 2.25 percent cap.

    Noninterest component — §__.150(c)(1)(ii):
        total_noninterest_income: Total noninterest income.
        realized_gains_losses_htm_securities: Realized gains (losses) on
            held-to-maturity securities (signed).
        realized_gains_losses_afs_debt_securities: Realized gains (losses)
            on available-for-sale debt securities (signed).
        noninterest_expense_for_bi: §__.101 — other noninterest expense
            EXCLUDING salaries and employee benefits, premises and fixed
            assets, goodwill impairment, amortization/impairment of other
            intangibles, expenses for non-financial services received, and
            operational losses.  Loss provisions/reversals are excluded
            except those relating to operational loss events.
        service_lines: Income and expense for investment management,
            investment services and non-lending treasury services.
        total_operational_losses: Sum of operational losses in each
            four-quarter period (scalar average, three annual totals, or
            twelve quarterly totals).  May be omitted and derived from
            ``OperationalLossData`` at calculation time.
    """
    total_interest_income: AnnualInput = Field(
        description="Total interest income excl. dividends ($M)"
    )
    total_interest_expense: AnnualInput = Field(
        description="Total interest expense ($M)"
    )
    interest_earning_assets: AnnualInput = Field(
        description="Interest-earning assets ($M; avg, 3 annual, or 12 quarter-ends)"
    )
    dividend_income: AnnualInput = Field(
        default=0.0, description="Dividend income ($M)"
    )
    total_noninterest_income: AnnualInput = Field(
        default=0.0, description="Total noninterest income ($M)"
    )
    realized_gains_losses_htm_securities: AnnualInput = Field(
        default=0.0, description="Realized G/L on HTM securities ($M, signed)"
    )
    realized_gains_losses_afs_debt_securities: AnnualInput = Field(
        default=0.0, description="Realized G/L on AFS debt securities ($M, signed)"
    )
    noninterest_expense_for_bi: AnnualInput = Field(
        default=0.0, description="Noninterest expense for BI per §__.101 ($M)"
    )
    service_lines: list[ServiceLineData] = Field(
        default_factory=list,
        description="IM / IS / NLTS income and expense for the 0.7 netting",
    )
    total_operational_losses: AnnualInput | None = Field(
        default=None,
        description="Total operational losses ($M; avg, 3 annual, or 12 quarterly)",
    )

    @field_validator(
        "total_interest_income",
        "total_interest_expense",
        "dividend_income",
        "total_noninterest_income",
        "realized_gains_losses_htm_securities",
        "realized_gains_losses_afs_debt_securities",
        "noninterest_expense_for_bi",
    )
    @classmethod
    def three_periods(cls, v: AnnualInput, info: ValidationInfo) -> AnnualInput:
        """Lists must contain exactly three annual values (§__.150(c))."""
        _as_periods(v, info.field_name or "input")
        return v

    @field_validator("interest_earning_assets")
    @classmethod
    def iea_shape_and_sign(cls, v: AnnualInput) -> AnnualInput:
        """IEA: non-negative; scalar, 3 annual averages or 12 quarter-ends."""
        values = [v] if isinstance(v, (int, float)) else list(v)
        if len(values) not in (1, BI_AVERAGING_PERIODS, IEA_AVERAGING_QUARTERS):
            raise ValueError(
                "interest_earning_assets must be a scalar, "
                f"{BI_AVERAGING_PERIODS} annual averages or "
                f"{IEA_AVERAGING_QUARTERS} quarter-end values"
            )
        if any(x < 0 for x in values):
            raise ValueError("Interest-earning assets cannot be negative")
        return v

    @field_validator("total_operational_losses")
    @classmethod
    def losses_shape_and_sign(cls, v: AnnualInput | None) -> AnnualInput | None:
        """Losses: non-negative; scalar, 3 annual totals or 12 quarterly."""
        if v is None:
            return v
        values = [v] if isinstance(v, (int, float)) else list(v)
        if len(values) not in (1, BI_AVERAGING_PERIODS, IEA_AVERAGING_QUARTERS):
            raise ValueError(
                "total_operational_losses must be a scalar, "
                f"{BI_AVERAGING_PERIODS} annual totals or "
                f"{IEA_AVERAGING_QUARTERS} quarterly totals"
            )
        if any(x < 0 for x in values):
            raise ValueError("Operational losses cannot be negative")
        return v

    @field_validator("service_lines")
    @classmethod
    def one_entry_per_service_line(
        cls, v: list[ServiceLineData]
    ) -> list[ServiceLineData]:
        """Each §__.101 service line may appear at most once."""
        seen: set[ServiceLine] = set()
        for entry in v:
            if entry.service_line in seen:
                raise ValueError(
                    f"Duplicate service line: {entry.service_line.value}"
                )
            seen.add(entry.service_line)
        return v

    # ---- period expansion helpers -------------------------------------

    def iea_periods(self) -> list[float]:
        """Interest-earning assets per period (annual average basis), $M.

        Twelve quarter-end balances are averaged four at a time; the
        three-year average of the result equals sum(12 values) / 12 as
        required by §__.150(c).
        """
        v = self.interest_earning_assets
        if isinstance(v, (int, float)):
            return [float(v)] * BI_AVERAGING_PERIODS
        if len(v) == IEA_AVERAGING_QUARTERS:
            per = IEA_AVERAGING_QUARTERS // BI_AVERAGING_PERIODS
            return [
                sum(v[i * per:(i + 1) * per]) / per
                for i in range(BI_AVERAGING_PERIODS)
            ]
        return [float(x) for x in v]

    def operational_loss_periods(self) -> list[float] | None:
        """Total operational losses per four-quarter period, $M (or None)."""
        v = self.total_operational_losses
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return [float(v)] * BI_AVERAGING_PERIODS
        if len(v) == IEA_AVERAGING_QUARTERS:
            return aggregate_quarterly_losses_to_periods(v)
        return [float(x) for x in v]

    def service_line_net_periods(self) -> tuple[list[float], list[float]]:
        """Aggregate service-line income and expense per period, $M.

        Returns:
            Tuple ``(income_periods, expense_periods)`` summed across the
            three §__.101 service lines.
        """
        income = [0.0] * BI_AVERAGING_PERIODS
        expense = [0.0] * BI_AVERAGING_PERIODS
        for sl in self.service_lines:
            inc = _as_periods(sl.noninterest_income, "service_line.noninterest_income")
            exp = _as_periods(
                sl.noninterest_expense_for_bi, "service_line.noninterest_expense_for_bi"
            )
            for i in range(BI_AVERAGING_PERIODS):
                income[i] += inc[i]
                expense[i] += exp[i]
        return income, expense


# Backward-compatible name.  Note the field set is the §__.150 one; the
# former BCBS-style fields (fee_income, net_trading_income, ...) are not
# inputs to the US calculation.
FinancialStatementData = BusinessIndicatorInputs


class OperationalLossData(BaseModel):
    """Operational loss event data per ERBA NPR §__.150 / §__.101.

    Loss data is not a capital input beyond the "total operational
    losses" term of the noninterest component, but the rule requires its
    collection (ten years, $20,000 per-event threshold, seven event types,
    including acquired entities) and it feeds Pillar 3 / FR Y-14Q.

    Attributes:
        annual_losses: Total operational losses per year in $M, oldest
            first; ideally ``LOSS_DATA_YEARS`` entries.
        losses_by_event_type: Aggregate losses by §__.101 event type ($M).
        total_loss_events: Count of events at or above the threshold.
        largest_single_loss: Largest single event in $M.
        includes_acquired_entities: Whether acquired / merged entities'
            history is included for the relevant period (required).
        collection_threshold_usd: Per-event collection threshold actually
            applied (absolute USD; must not exceed the regulatory
            $20,000 indexed threshold).
    """
    annual_losses: list[float] = Field(
        default_factory=list, description="Annual operational losses ($M)"
    )
    losses_by_event_type: dict[LossEventType, float] = Field(
        default_factory=dict, description="Losses by §__.101 event type ($M)"
    )
    total_loss_events: int = Field(
        default=0, description="Loss events at or above the threshold"
    )
    largest_single_loss: float = Field(
        default=0.0, description="Largest single loss event ($M)"
    )
    includes_acquired_entities: bool = Field(
        default=True,
        description="Acquired/merged entity history included (§__.150)",
    )
    collection_threshold_usd: float = Field(
        default=LOSS_COLLECTION_THRESHOLD_USD,
        description="Per-event collection threshold applied (absolute USD)",
    )

    @field_validator("annual_losses")
    @classmethod
    def losses_must_be_non_negative(cls, v: list[float]) -> list[float]:
        """Annual loss totals cannot be negative."""
        for i, loss in enumerate(v):
            if loss < 0:
                raise ValueError(f"Annual loss for year {i} cannot be negative: {loss}")
        return v

    @field_validator("collection_threshold_usd")
    @classmethod
    def threshold_not_above_regulatory(cls, v: float) -> float:
        """A bank may collect below, but not above, the $20,000 threshold."""
        if v > LOSS_COLLECTION_THRESHOLD_USD:
            raise ValueError(
                f"Collection threshold ${v:,.0f} exceeds the §__.150 "
                f"threshold of ${LOSS_COLLECTION_THRESHOLD_USD:,.0f}"
            )
        return v

    @property
    def data_years(self) -> int:
        """Number of years of loss data held."""
        return len(self.annual_losses)

    @property
    def meets_ten_year_requirement(self) -> bool:
        """Whether at least ``LOSS_DATA_YEARS`` years are held."""
        return self.data_years >= LOSS_DATA_YEARS

    def most_recent_period_losses(self) -> list[float]:
        """Losses for the three most recent years, oldest first ($M).

        Used to derive "total operational losses" for the noninterest
        component when it is not supplied on ``BusinessIndicatorInputs``.

        Raises:
            ValueError: If fewer than three years are held.
        """
        if self.data_years < BI_AVERAGING_PERIODS:
            raise ValueError(
                f"Need at least {BI_AVERAGING_PERIODS} years of loss data "
                f"to derive total operational losses; have {self.data_years}"
            )
        return list(self.annual_losses[-BI_AVERAGING_PERIODS:])


# Backward-compatible name.
LossComponentData = OperationalLossData


# =========================================================================
#  Output models
# =========================================================================

class BIComponentBreakdown(BaseModel):
    """Traceable breakdown of the business indicator ($M).

    Reference:
        ERBA NPR §__.150(c)(1)(i)-(ii).
    """
    # ILDC — §__.150(c)(1)(i)
    avg_abs_net_interest_income: float = Field(
        description="Avg3y(|total interest income - total interest expense|)"
    )
    avg_interest_earning_assets: float = Field(
        description="Avg3y(interest-earning assets)"
    )
    interest_cap: float = Field(
        description="0.0225 x Avg3y(interest-earning assets)"
    )
    interest_component: float = Field(
        description="min(Avg3y|TII - TIE|, cap)"
    )
    ildc_cap_applied: bool = Field(description="Whether the 2.25% cap binds")
    avg_dividend_income: float = Field(description="Avg3y(dividend income)")
    ildc: float = Field(description="interest_component + avg_dividend_income")
    # Noninterest component — §__.150(c)(1)(ii)
    avg_total_noninterest_income: float = Field(
        description="Avg3y(total noninterest income)"
    )
    avg_realized_gains_losses_htm: float = Field(
        description="Avg3y(realized G/L on HTM securities)"
    )
    avg_realized_gains_losses_afs_debt: float = Field(
        description="Avg3y(realized G/L on AFS debt securities)"
    )
    avg_noninterest_expense_for_bi: float = Field(
        description="Avg3y(noninterest expense for BI)"
    )
    avg_service_line_income: float = Field(
        description="Avg3y(IM + IS + NLTS noninterest income)"
    )
    avg_service_line_expense_for_bi: float = Field(
        description="Avg3y(IM + IS + NLTS noninterest expense for BI)"
    )
    avg_services_adjustment: float = Field(
        description="Avg3y(0.7 x (service-line income - service-line expense))"
    )
    avg_abs_net_noninterest: float = Field(
        description="Avg3y(|income + G/L - expense for BI - 0.7 x net services|)"
    )
    avg_total_operational_losses: float = Field(
        description="Avg3y(total operational losses)"
    )
    noninterest_component: float = Field(
        description="avg_abs_net_noninterest + avg_total_operational_losses"
    )
    period_abs_net_noninterest: list[float] = Field(
        default_factory=list,
        description="|netted noninterest| for each of the three periods",
    )


class OpRiskResult(BaseModel):
    """Result of the §__.150 operational risk calculation ($M).

    ``ilm`` is carried only for downstream report columns; it is fixed at
    1.0 and a validator rejects any other value, because §__.150(a) has
    no multiplier.

    Reference:
        ERBA NPR §__.150(a)-(c).
    """
    business_indicator: float = Field(
        description="BI = ILDC + noninterest component (§__.150(c)(1))"
    )
    ildc: float = Field(
        description="Interest, lease and dividend component (§__.150(c)(1)(i))"
    )
    noninterest_component: float = Field(
        description="Noninterest component (§__.150(c)(1)(ii))"
    )
    bic: float = Field(
        description="Business Indicator Component (§__.150(b))"
    )
    ilm: float = Field(
        default=ILM,
        description="No multiplier under §__.150(a); fixed at 1.0",
    )
    capital_charge: float = Field(
        description="Operational risk capital requirement = BIC"
    )
    rwa: float = Field(
        description="RWA_op = 12.5 x BIC (§__.150(a))"
    )
    capital_charge_by_bucket: dict[str, float] = Field(
        default_factory=dict,
        description="BIC contribution by marginal tier",
    )
    bi_component_breakdown: BIComponentBreakdown | None = Field(
        default=None, description="Detailed BI breakdown"
    )
    services_adjustment: float = Field(
        default=0.0,
        description="Avg3y(0.7 x net service-line income) subtracted in NIC",
    )
    bi_bucket: str = Field(default="", description="Marginal tier label")

    @model_validator(mode="after")
    def enforce_no_multiplier(self) -> OpRiskResult:
        """§__.150(a): capital = BIC exactly; no ILM may be applied."""
        if self.ilm != ILM:
            raise ValueError(
                f"ERBA NPR §__.150(a) has no internal loss multiplier; "
                f"ilm must be {ILM}, got {self.ilm}"
            )
        if abs(self.capital_charge - self.bic) > 1e-9 * max(1.0, abs(self.bic)):
            raise ValueError(
                "Operational risk capital must equal BIC under §__.150(a)"
            )
        return self


# =========================================================================
#  Calculator
# =========================================================================

class OpRiskCalculator:
    """Operational risk calculator per ERBA NPR §__.150.

    Flow:
        1. ILDC per §__.150(c)(1)(i)
        2. Noninterest component per §__.150(c)(1)(ii)
        3. BI = ILDC + noninterest component
        4. BIC via 12% / 15% / 18% tiers (§__.150(b))
        5. Capital = BIC; RWA = 12.5 x BIC (§__.150(a))

    Usage::

        calc = OpRiskCalculator()
        result = calc.calculate(inputs)
        print(f"OpRisk RWA: {result.rwa:,.0f} $M")

    Reference:
        ERBA NPR §__.150; preamble Section IV.D.
    """

    def __init__(self, loss_data: OperationalLossData | None = None) -> None:
        """Initialize the calculator.

        Args:
            loss_data: Optional loss event data, used to derive total
                operational losses when the inputs do not carry them.
        """
        self._loss_data = loss_data

    def calculate(
        self,
        inputs: BusinessIndicatorInputs,
        loss_data: OperationalLossData | None = None,
    ) -> OpRiskResult:
        """Calculate the operational risk capital requirement and RWA.

        Args:
            inputs: Business indicator inputs ($M).
            loss_data: Optional override for loss event data.

        Returns:
            OpRiskResult with full breakdown.

        Raises:
            ValueError: If total operational losses are available neither
                on ``inputs`` nor from loss data.

        Reference:
            ERBA NPR §__.150(a)-(c).
        """
        ld = loss_data or self._loss_data

        # 1. ILDC — §__.150(c)(1)(i)
        ildc, ildc_parts = self._compute_ildc(inputs)

        # 2. Noninterest component — §__.150(c)(1)(ii)
        nic, nic_parts = self._compute_noninterest_component(inputs, ld)

        # 3. BI — §__.150(c)(1)
        bi = ildc + nic

        # 4. BIC — §__.150(b)
        bic = compute_bic(bi)

        # 5. Capital = BIC; RWA = 12.5 x BIC — §__.150(a)
        capital = bic
        rwa = capital * RWA_CONVERSION_FACTOR

        breakdown = BIComponentBreakdown(**ildc_parts, **nic_parts)

        return OpRiskResult(
            business_indicator=bi,
            ildc=ildc,
            noninterest_component=nic,
            bic=bic,
            ilm=ILM,
            capital_charge=capital,
            rwa=rwa,
            capital_charge_by_bucket=self._bucket_breakdown(bi),
            bi_component_breakdown=breakdown,
            services_adjustment=nic_parts["avg_services_adjustment"],
            bi_bucket=self._determine_bi_bucket(bi),
        )

    def calculate_rwa(
        self,
        inputs: BusinessIndicatorInputs,
        loss_data: OperationalLossData | None = None,
    ) -> float:
        """Return only the operational risk RWA in $M (§__.150(a))."""
        return self.calculate(inputs, loss_data).rwa

    # ---- components ----------------------------------------------------

    @staticmethod
    def _compute_ildc(inputs: BusinessIndicatorInputs) -> tuple[float, dict]:  # type: ignore[type-arg]
        """Interest, lease and dividend component — §__.150(c)(1)(i).

        ILDC = min( Avg3y(|TII - TIE|), 0.0225 x Avg3y(IEA) ) + Avg3y(dividends)

        The absolute value is taken per four-quarter period before
        averaging; the cap is applied to the averaged figures.

        Args:
            inputs: Business indicator inputs.

        Returns:
            Tuple of (ILDC in $M, breakdown fields).
        """
        tii = _as_periods(inputs.total_interest_income, "total_interest_income")
        tie = _as_periods(inputs.total_interest_expense, "total_interest_expense")
        div = _as_periods(inputs.dividend_income, "dividend_income")

        avg_abs_nii = average_over_periods(
            [abs(a - b) for a, b in zip(tii, tie, strict=True)]
        )
        avg_iea = average_over_periods(inputs.iea_periods())
        cap = ILDC_INTEREST_CAP_RATE * avg_iea
        interest_component = min(avg_abs_nii, cap)
        avg_div = average_over_periods(div)
        ildc = interest_component + avg_div

        parts = {
            "avg_abs_net_interest_income": avg_abs_nii,
            "avg_interest_earning_assets": avg_iea,
            "interest_cap": cap,
            "interest_component": interest_component,
            "ildc_cap_applied": avg_abs_nii > cap,
            "avg_dividend_income": avg_div,
            "ildc": ildc,
        }
        return ildc, parts

    @staticmethod
    def _compute_noninterest_component(
        inputs: BusinessIndicatorInputs,
        loss_data: OperationalLossData | None,
    ) -> tuple[float, dict]:  # type: ignore[type-arg]
        """Noninterest component — §__.150(c)(1)(ii).

        For each four-quarter period t:
            X_t = total noninterest income_t
                  + realized G/L HTM_t + realized G/L AFS debt_t
                  - noninterest expense for BI_t
                  - 0.7 x (service-line income_t - service-line expense_t)
        Noninterest component = Avg3y( |X_t| + total operational losses_t )

        Args:
            inputs: Business indicator inputs.
            loss_data: Loss event data used when ``inputs`` has no
                ``total_operational_losses``.

        Returns:
            Tuple of (noninterest component in $M, breakdown fields).

        Raises:
            ValueError: If total operational losses cannot be determined.
        """
        n = BI_AVERAGING_PERIODS
        income = _as_periods(inputs.total_noninterest_income, "total_noninterest_income")
        htm = _as_periods(
            inputs.realized_gains_losses_htm_securities,
            "realized_gains_losses_htm_securities",
        )
        afs = _as_periods(
            inputs.realized_gains_losses_afs_debt_securities,
            "realized_gains_losses_afs_debt_securities",
        )
        expense = _as_periods(inputs.noninterest_expense_for_bi, "noninterest_expense_for_bi")
        sl_income, sl_expense = inputs.service_line_net_periods()

        losses = inputs.operational_loss_periods()
        if losses is None:
            if loss_data is None:
                raise ValueError(
                    "total_operational_losses is required by §__.150(c)(1)(ii); "
                    "supply it on BusinessIndicatorInputs or provide "
                    "OperationalLossData"
                )
            losses = loss_data.most_recent_period_losses()

        services_adj = [
            SERVICES_NET_INCOME_FACTOR * (sl_income[i] - sl_expense[i]) for i in range(n)
        ]
        abs_net = [
            abs(income[i] + htm[i] + afs[i] - expense[i] - services_adj[i])
            for i in range(n)
        ]
        avg_abs_net = average_over_periods(abs_net)
        avg_losses = average_over_periods(losses)
        nic = avg_abs_net + avg_losses

        parts = {
            "avg_total_noninterest_income": average_over_periods(income),
            "avg_realized_gains_losses_htm": average_over_periods(htm),
            "avg_realized_gains_losses_afs_debt": average_over_periods(afs),
            "avg_noninterest_expense_for_bi": average_over_periods(expense),
            "avg_service_line_income": average_over_periods(sl_income),
            "avg_service_line_expense_for_bi": average_over_periods(sl_expense),
            "avg_services_adjustment": average_over_periods(services_adj),
            "avg_abs_net_noninterest": avg_abs_net,
            "avg_total_operational_losses": avg_losses,
            "noninterest_component": nic,
            "period_abs_net_noninterest": abs_net,
        }
        return nic, parts

    # ---- reporting helpers --------------------------------------------

    @staticmethod
    def _bucket_breakdown(bi: float) -> dict[str, float]:
        """Split BIC by marginal tier for reporting — §__.150(b).

        Args:
            bi: Business Indicator in $M.

        Returns:
            Mapping of tier name to BIC contribution in $M.
        """
        breakdown: dict[str, float] = {}
        remaining = bi
        prev_ceiling = 0.0
        bucket_names = ["bucket_1_to_1B", "bucket_1B_to_30B", "bucket_above_30B"]

        for i, (ceiling, coefficient) in enumerate(BIC_COEFFICIENTS):
            bucket_size = min(remaining, ceiling - prev_ceiling)
            if bucket_size <= 0:
                break
            name = bucket_names[i] if i < len(bucket_names) else f"bucket_{i}"
            breakdown[name] = bucket_size * coefficient
            remaining -= bucket_size
            prev_ceiling = ceiling

        return breakdown

    @staticmethod
    def _determine_bi_bucket(bi: float) -> str:
        """Label of the marginal tier containing BI — §__.150(b)."""
        for bucket in BIC_BUCKETS:
            if bi <= bucket.ceiling_usd_m:
                return bucket.bucket_label
        return BIC_BUCKETS[-1].bucket_label

    # ---- data quality ----------------------------------------------------

    @staticmethod
    def validate_inputs(inputs: BusinessIndicatorInputs) -> list[str]:
        """BCBS 239 / SR 11-7 plausibility checks on §__.150 inputs.

        Args:
            inputs: Business indicator inputs.

        Returns:
            List of warning messages (empty if all checks pass).
        """
        warnings: list[str] = []

        avg_iea = average_over_periods(inputs.iea_periods())
        tii = _as_periods(inputs.total_interest_income, "total_interest_income")
        tie = _as_periods(inputs.total_interest_expense, "total_interest_expense")

        if avg_iea <= 0:
            warnings.append(
                "Average interest-earning assets is zero — the 2.25% cap in "
                "§__.150(c)(1)(i) forces the interest component to zero"
            )
        if any(x < 0 for x in tii):
            warnings.append("Total interest income is negative — verify data")
        if any(x < 0 for x in tie):
            warnings.append("Total interest expense is negative — verify data")
        if avg_iea > 0:
            nim = (
                average_over_periods([a - b for a, b in zip(tii, tie, strict=True)])
                / avg_iea
            )
            if abs(nim) > NIM_REVIEW_THRESHOLD:
                warnings.append(
                    f"Net interest margin ({nim:.2%}) exceeds "
                    f"{NIM_REVIEW_THRESHOLD:.0%} — verify data"
                )

        income = _as_periods(inputs.total_noninterest_income, "total_noninterest_income")
        expense = _as_periods(inputs.noninterest_expense_for_bi, "noninterest_expense_for_bi")
        sl_income, sl_expense = inputs.service_line_net_periods()

        if all(x == 0 for x in income) and all(x == 0 for x in expense):
            warnings.append(
                "Total noninterest income and noninterest expense for BI are "
                "both zero — verify noninterest component data completeness"
            )
        if any(sl_income[i] > income[i] for i in range(BI_AVERAGING_PERIODS)):
            warnings.append(
                "Service-line noninterest income exceeds total noninterest "
                "income in at least one period — verify §__.101 classification"
            )
        if any(sl_expense[i] > expense[i] for i in range(BI_AVERAGING_PERIODS)):
            warnings.append(
                "Service-line noninterest expense for BI exceeds total "
                "noninterest expense for BI in at least one period"
            )
        if inputs.total_operational_losses is None:
            warnings.append(
                "total_operational_losses not supplied — will be derived "
                "from OperationalLossData at calculation time"
            )

        return warnings

    # Backward-compatible name.
    validate_financial_data = validate_inputs
