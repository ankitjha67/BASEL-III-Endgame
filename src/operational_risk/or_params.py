"""Operational risk regulatory parameters — US ERBA NPR §__.150 (12 CFR 217.150).

Parameters for the standardized operational risk capital requirement in
Subpart E of the capital rule as re-proposed by the Federal Reserve in
March 2026 ("ERBA NPR").  The US rule is a business-indicator-only
measure:

    RWA_op = 12.5 x BIC                                   §__.150(a)
    BIC    = piecewise-linear function of BI              §__.150(b)
    BI     = ILDC + noninterest component                 §__.150(c)(1)
    ILDC   = min(Avg3y|TII - TIE|, 0.0225 x Avg3y IEA)
             + Avg3y dividend income                      §__.150(c)(1)(i)
    NIC    = Avg3y( |total noninterest income
                     + realized G/L on HTM securities
                     + realized G/L on AFS debt securities
                     - noninterest expense for BI
                     - 0.7 x (service-line income
                              - service-line expense for BI)|
                    + total operational losses )          §__.150(c)(1)(ii)

There is NO internal loss multiplier in the US rule (ERBA NPR preamble
p. 197, fn. 216: "equivalent to setting the internal loss multiplier
equal to one").  BCBS d424 constructs that the US rule does not use
(services component, financial component, loss component, ILM) are kept
only in the clearly marked "BCBS d424 reference only" section at the end
of this file and are never called by the production calculation path.

Units:
    All flow and stock amounts are in USD millions ($M) per CLAUDE.md.
    The only exception is the per-event loss collection threshold, which
    is an absolute dollar amount and is explicitly suffixed ``_USD``.

References:
    - ERBA NPR (March 2026) rule text §__.150 (pp. 783-788) and §__.101
      definitions (pp. 675-684); 12 CFR Part 217 Subpart E.
    - ERBA NPR preamble Section IV.D, pp. 193-216 (Table 3 p. 210).
    - §__.4 inflation indexing of dollar thresholds (CPI-W).
    - BCBS d424 (Dec 2017) "Minimum capital requirements for operational
      risk" — comparison only.

# TODO: VERIFY — paragraph lettering below §__.150(c)(1) (averaging
# conventions, loss event data requirements) is cited descriptively where
# the transcription does not give the exact paragraph designator.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import Enum
from typing import NamedTuple

# =========================================================================
#  §__.150(a) — RWA conversion
# =========================================================================

# RWA for operational risk = 12.5 x business indicator component.
# ERBA NPR §__.150(a); preamble p. 197 fn. 215 (12.5 = 1 / 8%).
RWA_CONVERSION_FACTOR: float = 12.5


# =========================================================================
#  §__.150(b) — Business Indicator Component (BIC)
# =========================================================================

# Dollar thresholds separating the three marginal-coefficient tiers.
# ERBA NPR §__.150(b), Table 3 (preamble p. 210).  Both thresholds are
# indexed to inflation under §__.4 (CPI-W); the values here are the
# unadjusted amounts stated in the proposal and must be updated when the
# agencies publish an indexed figure.  Units: $M.
BIC_THRESHOLD_1_USD_M: float = 1_000.0       # $1 billion
BIC_THRESHOLD_2_USD_M: float = 30_000.0      # $30 billion

# Marginal coefficients per tier — §__.150(b).
BIC_MARGINAL_COEFFICIENT_TIER_1: float = 0.12   # BI <= $1B
BIC_MARGINAL_COEFFICIENT_TIER_2: float = 0.15   # $1B < BI <= $30B
BIC_MARGINAL_COEFFICIENT_TIER_3: float = 0.18   # BI > $30B

# Closed-form intercepts exactly as written in §__.150(b) / Table 3.
# fn. 230: $120 million = 0.12 x $1 billion;
#          $4.47 billion = 0.12 x $1 billion + 0.15 x ($30 billion - $1 billion).
BIC_TIER_2_INTERCEPT_USD_M: float = (
    BIC_MARGINAL_COEFFICIENT_TIER_1 * BIC_THRESHOLD_1_USD_M
)   # = 120.0 ($120 million)
BIC_TIER_3_INTERCEPT_USD_M: float = (
    BIC_TIER_2_INTERCEPT_USD_M
    + BIC_MARGINAL_COEFFICIENT_TIER_2
    * (BIC_THRESHOLD_2_USD_M - BIC_THRESHOLD_1_USD_M)
)   # = 4_470.0 ($4.47 billion)


class BICBucket(NamedTuple):
    """A single BIC marginal-coefficient tier per ERBA NPR §__.150(b).

    Attributes:
        ceiling_usd_m: Upper bound of the tier in $M (``inf`` for the last).
        marginal_coefficient: Coefficient applied to BI within this tier.
        bucket_label: Human-readable label for reporting.
    """
    ceiling_usd_m: float
    marginal_coefficient: float
    bucket_label: str


BIC_BUCKETS: list[BICBucket] = [
    BICBucket(
        BIC_THRESHOLD_1_USD_M,
        BIC_MARGINAL_COEFFICIENT_TIER_1,
        "Tier 1: BI <= $1B (12%)",
    ),
    BICBucket(
        BIC_THRESHOLD_2_USD_M,
        BIC_MARGINAL_COEFFICIENT_TIER_2,
        "Tier 2: $1B < BI <= $30B (15%)",
    ),
    BICBucket(
        float("inf"),
        BIC_MARGINAL_COEFFICIENT_TIER_3,
        "Tier 3: BI > $30B (18%)",
    ),
]

# Flat (ceiling_usd_m, coefficient) list retained for backward compatibility.
BIC_COEFFICIENTS: list[tuple[float, float]] = [
    (b.ceiling_usd_m, b.marginal_coefficient) for b in BIC_BUCKETS
]


# =========================================================================
#  Internal Loss Multiplier — NOT part of the US rule
# =========================================================================

# ERBA NPR §__.150(a) defines RWA_op = 12.5 x BIC with no multiplier.
# Preamble p. 197 fn. 216: this is "equivalent to setting the internal
# loss multiplier equal to one".  The constant exists only so that
# downstream reporting fields that still carry an ILM column are
# populated with the regulatory value; the calculator never multiplies
# by anything else (see OpRiskResult validator in or_calculator.py).
ILM: float = 1.0


# =========================================================================
#  §__.150(c)(1)(i) — Interest, lease, and dividend component (ILDC)
# =========================================================================

# Cap on the interest input: 2.25 percent of three-year average
# interest-earning assets.  ERBA NPR §__.150(c)(1)(i); preamble p. 202.
ILDC_INTEREST_CAP_RATE: float = 0.0225

# Note on leases (preamble pp. 202-203, Question 85): under the US rule
# finance-lease income is already part of "total interest income" as
# reported on FR Y-9C Schedule HI / Call Report Schedule RI, and operating
# lease income and expense fall in the noninterest component.  There is
# therefore no separate lease input in the US formula.


# =========================================================================
#  §__.150(c)(1)(ii) — Noninterest component: service-line netting factor
# =========================================================================

class ServiceLine(Enum):
    """Activities whose net income receives the 0.7 reduction — §__.101.

    INVESTMENT_MANAGEMENT: asset management, wealth management and private
        banking, including professional management of mutual funds and
        institutional accounts and portfolio management / advisory services
        for individuals.
    INVESTMENT_SERVICES: asset servicing (custody, fund services, securities
        lending, liquidity services, collateral management, record keeping
        for 401(k) and employee benefit plans excluding funding or guarantee
        products), issuer services (corporate trust, shareowner services,
        depository receipts) and other investment services (clearing).
    NON_LENDING_TREASURY_SERVICES: cash management, global payments and
        deposit services; excludes any lending or card activities (trade
        finance and corporate/commercial cards are out of scope — preamble
        p. 206 fn. 227).
    """
    INVESTMENT_MANAGEMENT = "INVESTMENT_MANAGEMENT"
    INVESTMENT_SERVICES = "INVESTMENT_SERVICES"
    NON_LENDING_TREASURY_SERVICES = "NON_LENDING_TREASURY_SERVICES"


# Factor applied to (service-line noninterest income - service-line
# noninterest expense for BI) and SUBTRACTED inside the absolute value of
# the noninterest component, so that only 30 percent of the NET income
# from investment management, investment services and non-lending treasury
# services contributes to BI.  ERBA NPR §__.150(c)(1)(ii); preamble
# pp. 203-207 (calibration: op-loss/income ratio for these lines is
# ~32 percent of the all-business-line ratio).
SERVICES_NET_INCOME_FACTOR: float = 0.7

# Backward-compatible alias.  The factor was previously documented as
# applying to investment management only; under §__.150(c)(1)(ii) it
# applies to all three service lines in ``ServiceLine``.
NIC_INVESTMENT_MANAGEMENT_FACTOR: float = SERVICES_NET_INCOME_FACTOR

# The noninterest component nets income and expense (one-step netting,
# preamble p. 204) — kept as a documented flag for governance checks.
NIC_USE_NET_BASIS: bool = True

# Items EXCLUDED from "noninterest expense for BI" — §__.101 definition
# and preamble pp. 203-204, 208-209.  Listed for data-lineage / validation
# documentation; the input model expects the caller to supply the
# already-exclusive figure.
NONINTEREST_EXPENSE_FOR_BI_EXCLUSIONS: tuple[str, ...] = (
    "salaries and employee benefits",
    "expenses of premises and fixed assets",
    "goodwill impairment losses",
    "amortization expense and impairment losses for other intangible assets",
    "expenses relating to non-financial services received by the banking "
    "organization (e.g. outsourced logistics, HR, IT; administrative "
    "expenses such as utilities, telecommunications, travel, office supplies)",
    "total operational losses (added back separately in the noninterest "
    "component)",
    "loss provisions and reversals of provisions, except those relating to "
    "operational loss events",
    "changes in goodwill; applicable income taxes",
)


# =========================================================================
#  Averaging conventions — §__.150(c)
# =========================================================================

# Every BI input is the average over the three most recent
# four-calendar-quarter periods (preamble pp. 199-200).
BI_AVERAGING_PERIODS: int = 3
QUARTERS_PER_PERIOD: int = 4

# Interest-earning assets: sum of the twelve most recent quarter-end
# values divided by twelve (§__.150(c); preamble p. 200).
IEA_AVERAGING_QUARTERS: int = BI_AVERAGING_PERIODS * QUARTERS_PER_PERIOD   # 12

# Legacy names retained for backward compatibility.
BI_AVERAGING_YEARS: int = BI_AVERAGING_PERIODS
AVERAGING_QUARTERS: int = IEA_AVERAGING_QUARTERS


# =========================================================================
#  Operational loss event data — §__.150 / §__.101
# =========================================================================

class LossEventType(Enum):
    """The seven operational loss event types defined in §__.101.

    INTERNAL_FRAUD: an act involving at least one internal party of a type
        intended to defraud, misappropriate property, or circumvent
        regulations, the law, or company policy (excluding diversity- or
        discrimination-type events).
    EXTERNAL_FRAUD: an act by a third party of a type intended to defraud,
        misappropriate property, or circumvent the law.  Retail credit card
        losses arising from non-contractual, third-party-initiated fraud
        (e.g. identity theft) are external fraud operational losses, not
        credit losses.
    EMPLOYMENT_PRACTICES: employment practices and workplace safety — an
        act inconsistent with employment, health or safety laws or
        agreements, payment of personal injury claims, or diversity- or
        discrimination-type events.
    CLIENTS_PRODUCTS: clients, products and business practices — an
        unintentional or negligent failure to meet a professional
        obligation to specific clients, or the nature or design of a
        product.
    DAMAGE_PHYSICAL: damage to physical assets — loss or damage to physical
        assets from natural disaster or other events.
    BUSINESS_DISRUPTION: business disruption and system failures.
    EXECUTION_DELIVERY: execution, delivery and process management — failed
        transaction processing or process management, or losses arising
        from relations with trade counterparties and vendors.
    """
    INTERNAL_FRAUD = "INTERNAL_FRAUD"
    EXTERNAL_FRAUD = "EXTERNAL_FRAUD"
    EMPLOYMENT_PRACTICES = "EMPLOYMENT_PRACTICES"
    CLIENTS_PRODUCTS = "CLIENTS_PRODUCTS"
    DAMAGE_PHYSICAL = "DAMAGE_PHYSICAL"
    BUSINESS_DISRUPTION = "BUSINESS_DISRUPTION"
    EXECUTION_DELIVERY = "EXECUTION_DELIVERY"


# Event type to which retail credit-card third-party fraud losses are
# assigned — §__.101 "operational loss event" / "external fraud".
RETAIL_CARD_THIRD_PARTY_FRAUD_EVENT_TYPE: LossEventType = (
    LossEventType.EXTERNAL_FRAUD
)

# Mandatory per-event collection threshold for operational loss event
# data: $20,000 (absolute USD, indexed under §__.4).  ERBA NPR §__.150;
# preamble p. 195 (FR Y-14Q collection basis).  This replaces the BCBS
# d424 EUR 20,000 threshold.
LOSS_COLLECTION_THRESHOLD_USD: float = 20_000.0

# Backward-compatible alias.
LOSS_THRESHOLD_USD: float = LOSS_COLLECTION_THRESHOLD_USD

# Loss event data must cover ten years, including the loss history of
# acquired or merged entities for the relevant period — ERBA NPR §__.150;
# preamble p. 201.
LOSS_DATA_YEARS: int = 10


# =========================================================================
#  Data quality parameters (BCBS 239 / SR 11-7 governance)
# =========================================================================

# Minimum data completeness ratio for BI inputs (95%).
MIN_DATA_COMPLETENESS: float = 0.95

# Maximum acceptable variance between reported and recalculated BI (1%).
MAX_RECONCILIATION_VARIANCE: float = 0.01

# Net interest margin above which input data is flagged for review.
NIM_REVIEW_THRESHOLD: float = 0.10


# =========================================================================
#  FFIEC reporting thresholds (unchanged context parameters)
# =========================================================================

# Category I bank threshold (total assets >= $250B or FBO criteria), $M.
CATEGORY_I_ASSET_THRESHOLD: float = 250_000.0

# G-SIB designation threshold (Method 1 score >= 130 basis points).
GSIB_SCORE_THRESHOLD: float = 130.0


# =========================================================================
#  Helper functions — production path
# =========================================================================

def compute_bic(business_indicator: float) -> float:
    """Compute the Business Indicator Component per ERBA NPR §__.150(b).

    Marginal form: 12 percent of BI up to $1 billion, 15 percent of BI
    above $1 billion and up to $30 billion, 18 percent of BI above
    $30 billion (preamble pp. 209-210).  Mathematically identical to the
    closed form in :func:`compute_bic_closed_form`.

    Args:
        business_indicator: Business Indicator in $M.

    Returns:
        BIC in $M.

    Raises:
        ValueError: If ``business_indicator`` is negative.

    Reference:
        ERBA NPR §__.150(b); Table 3 (preamble p. 210).
    """
    if business_indicator < 0:
        raise ValueError(
            f"Business Indicator cannot be negative: {business_indicator}"
        )

    bic = 0.0
    remaining = business_indicator
    prev_ceiling = 0.0

    for ceiling, coefficient in BIC_COEFFICIENTS:
        bucket_size = min(remaining, ceiling - prev_ceiling)
        if bucket_size <= 0:
            break
        bic += bucket_size * coefficient
        remaining -= bucket_size
        prev_ceiling = ceiling

    return bic


def compute_bic_closed_form(business_indicator: float) -> float:
    """Compute BIC in the piecewise closed form written in §__.150(b).

    ::

        BIC = 0.12 x BI                              if BI <= $1B
        BIC = $120M  + 0.15 x (BI - $1B)             if $1B < BI <= $30B
        BIC = $4.47B + 0.18 x (BI - $30B)            if BI > $30B

    Args:
        business_indicator: Business Indicator in $M.

    Returns:
        BIC in $M.

    Raises:
        ValueError: If ``business_indicator`` is negative.

    Reference:
        ERBA NPR §__.150(b); Table 3 and fn. 230 (preamble p. 210).
    """
    if business_indicator < 0:
        raise ValueError(
            f"Business Indicator cannot be negative: {business_indicator}"
        )
    if business_indicator <= BIC_THRESHOLD_1_USD_M:
        return BIC_MARGINAL_COEFFICIENT_TIER_1 * business_indicator
    if business_indicator <= BIC_THRESHOLD_2_USD_M:
        return BIC_TIER_2_INTERCEPT_USD_M + BIC_MARGINAL_COEFFICIENT_TIER_2 * (
            business_indicator - BIC_THRESHOLD_1_USD_M
        )
    return BIC_TIER_3_INTERCEPT_USD_M + BIC_MARGINAL_COEFFICIENT_TIER_3 * (
        business_indicator - BIC_THRESHOLD_2_USD_M
    )


def average_over_periods(values: Sequence[float]) -> float:
    """Average a BI input over the three most recent four-quarter periods.

    Args:
        values: Exactly ``BI_AVERAGING_PERIODS`` annual (four-quarter)
            amounts in $M, oldest first.

    Returns:
        Simple arithmetic mean in $M.

    Raises:
        ValueError: If the number of values is not ``BI_AVERAGING_PERIODS``.

    Reference:
        ERBA NPR §__.150(c) (three-year averaging); preamble pp. 199-200.
    """
    if len(values) != BI_AVERAGING_PERIODS:
        raise ValueError(
            f"Expected {BI_AVERAGING_PERIODS} annual values, got {len(values)}"
        )
    return sum(values) / BI_AVERAGING_PERIODS


def average_interest_earning_assets(quarter_end_values: Sequence[float]) -> float:
    """Average interest-earning assets from quarter-end balances.

    Avg3y(IEA) = sum of the twelve most recent quarter-end values / 12.

    Args:
        quarter_end_values: Exactly ``IEA_AVERAGING_QUARTERS`` quarter-end
            balances in $M, oldest first.

    Returns:
        Average interest-earning assets in $M.

    Raises:
        ValueError: If the number of values is not ``IEA_AVERAGING_QUARTERS``
            or any value is negative.

    Reference:
        ERBA NPR §__.150(c); preamble p. 200.
    """
    if len(quarter_end_values) != IEA_AVERAGING_QUARTERS:
        raise ValueError(
            f"Expected {IEA_AVERAGING_QUARTERS} quarter-end values, "
            f"got {len(quarter_end_values)}"
        )
    if any(v < 0 for v in quarter_end_values):
        raise ValueError("Interest-earning assets cannot be negative")
    return sum(quarter_end_values) / IEA_AVERAGING_QUARTERS


def aggregate_quarterly_losses_to_periods(
    quarterly_losses: Sequence[float],
) -> list[float]:
    """Sum quarterly operational losses into four-quarter period totals.

    Total operational losses for a four-calendar-quarter period are the
    sum of the quarterly operational losses in that period.

    Args:
        quarterly_losses: Exactly ``IEA_AVERAGING_QUARTERS`` (12) quarterly
            loss totals in $M, oldest first.

    Returns:
        ``BI_AVERAGING_PERIODS`` period totals in $M, oldest first.

    Raises:
        ValueError: If the count is wrong or any value is negative.

    Reference:
        ERBA NPR §__.150(c)(1)(ii) (total operational losses definition).
    """
    if len(quarterly_losses) != IEA_AVERAGING_QUARTERS:
        raise ValueError(
            f"Expected {IEA_AVERAGING_QUARTERS} quarterly loss values, "
            f"got {len(quarterly_losses)}"
        )
    if any(v < 0 for v in quarterly_losses):
        raise ValueError("Operational losses cannot be negative")
    return [
        sum(quarterly_losses[i * QUARTERS_PER_PERIOD:(i + 1) * QUARTERS_PER_PERIOD])
        for i in range(BI_AVERAGING_PERIODS)
    ]


def compute_ilm(loss_component: float = 0.0, bic: float = 0.0) -> float:
    """Return the multiplier applied to BIC under the US rule — always 1.0.

    ERBA NPR §__.150(a) contains no internal loss multiplier.  The
    arguments are accepted only so that legacy call sites keep working;
    they are ignored.  For the BCBS d424 formula see
    :func:`compute_bcbs_reference_ilm`.

    Args:
        loss_component: Ignored.
        bic: Ignored.

    Returns:
        ``ILM`` (1.0).

    Reference:
        ERBA NPR §__.150(a); preamble p. 197 fn. 216.
    """
    return ILM


# =========================================================================
#  BCBS d424 reference only — NOT used in the US calculation
# =========================================================================
#
# The functions and constants below reproduce the Basel Committee's
# standardised approach (BCBS d424, OPE25) so that the US requirement can
# be benchmarked against it (SR 11-7 benchmarking).  Nothing in
# ``or_calculator.py`` calls them.

# BCBS d424 OPE25.5-25.6: ILM = ln(exp(1) - 1 + (LC/BIC)^0.8), LC = 15 x
# average annual operational losses over 10 years.
BCBS_ILM_EXPONENT: float = 0.8
BCBS_LC_MULTIPLIER: float = 15.0

# Legacy names (reference only).
ILM_EXPONENT: float = BCBS_ILM_EXPONENT
LC_MULTIPLIER: float = BCBS_LC_MULTIPLIER
LC_BI_THRESHOLD: float = BIC_THRESHOLD_1_USD_M


def compute_bcbs_reference_ilm(loss_component: float, bic: float) -> float:
    """BCBS d424 internal loss multiplier — reference / benchmarking only.

    ILM = ln(exp(1) - 1 + (LC / BIC)^0.8).  Not applied under ERBA NPR
    §__.150 (preamble Question 84, pp. 198-199).

    Args:
        loss_component: BCBS loss component in $M.
        bic: Business Indicator Component in $M.

    Returns:
        The BCBS ILM value, or 1.0 when BIC or LC is non-positive.

    Reference:
        BCBS d424 OPE25.5-25.6 — comparison only.
    """
    if bic <= 0 or loss_component <= 0:
        return 1.0
    return math.log(
        math.exp(1.0) - 1.0 + (loss_component / bic) ** BCBS_ILM_EXPONENT
    )


def compute_loss_component(
    average_annual_losses: float,
    business_indicator: float,
) -> float:
    """BCBS d424 loss component — reference / benchmarking only.

    LC = 15 x average annual operational losses, relevant under BCBS only
    for banks in bucket 2 or 3 (BI > the first threshold).  Not used in
    the US calculation.

    Args:
        average_annual_losses: Average annual operational losses in $M.
        business_indicator: Business Indicator in $M.

    Returns:
        BCBS loss component in $M (0.0 for bucket-1 BI).

    Reference:
        BCBS d424 OPE25.5 — comparison only.
    """
    if business_indicator <= LC_BI_THRESHOLD:
        return 0.0
    return BCBS_LC_MULTIPLIER * max(average_annual_losses, 0.0)
