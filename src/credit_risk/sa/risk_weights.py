"""SA-CR Risk Weight Tables and Lookup Logic per the March 2026 US ERBA NPR.

Implements the risk weights of the expanded risk-based approach (ERBA) for
general credit risk, 12 CFR 217.111 (common rule text § __.111, ERBA NPR
pp. 686-700), together with the definitions in § __.101 (pp. 675-684).

The US framework prohibits use of external credit ratings (Dodd-Frank
Act § 939A) and instead relies on:

  - Country Risk Classifications (CRC) / OECD membership for sovereigns
    and foreign public sector entities (Tables 1, 3 and 4 to § __.111)
  - Grade A / B / C classification of bank exposures based on the obligor's
    investment-grade status and capital ratios (Table 2 to § __.111)
  - Internal investment-grade determination for corporates (§ __.111(h)(1))
  - LTV ratios and cash-flow dependence for real estate (Tables 5-8)
  - Exposure sub-type classification for equity exposures (§ __.141)

All risk weights are expressed as decimals (0.20 = 20 percent).

References:
    - ERBA NPR (OCC/Board/FDIC, March 2026), common rule text § __.101,
      § __.111, § __.141 (pp. 675-700, 775-783)
    - 12 CFR Part 217, Subpart E (Board), 12 CFR Part 3 (OCC), Part 324 (FDIC)
    - Basel Committee CRE20 (international standard, where the US aligns)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.credit_risk.sa.exposure_classes import (
    CRESubType,
    EquitySubType,
    ExposureClass,
    PSEObligationType,
    get_cre_ltv_bucket,
    get_resi_mortgage_ltv_bucket,
    is_qualifying_mdb,
)


# =========================================================================
#  Sovereign Risk Weights -- Table 1 to § __.111 (ERBA NPR p. 686)
# =========================================================================

SOVEREIGN_RW: dict[int, float] = {
    0: 0.00,   # CRC 0-1: 0%
    1: 0.00,
    2: 0.20,   # CRC 2: 20%
    3: 0.50,   # CRC 3: 50%
    4: 1.00,   # CRC 4-6: 100%
    5: 1.00,
    6: 1.00,
    7: 1.50,   # CRC 7: 150%
}
"""Sovereign risk weights by OECD Country Risk Classification.

Table 1 to § __.111 (ERBA NPR p. 686): CRC 0-1 → 0%; CRC 2 → 20%;
CRC 3 → 50%; CRC 4-6 → 100%; CRC 7 → 150%.  The table is identical to
Table 1 to § __.32 of the current standardized approach (NPR p. 54 fn 80).
"""

SOVEREIGN_OECD_NO_CRC_RW: float = 0.00
"""OECD member sovereign with no CRC: 0% (§ __.111(a)(5))."""

SOVEREIGN_NON_OECD_NO_CRC_RW: float = 1.00
"""Non-OECD sovereign with no CRC: 100% (§ __.111(a)(4))."""

SOVEREIGN_DEFAULT_RW: float = 1.50
"""Sovereign default (event within previous five years): 150% (§ __.111(a)(6))."""

US_CONDITIONAL_GUARANTEE_RW: float = 0.20
"""Portion conditionally guaranteed by the US government/FDIC/NCUA: 20%
(§ __.111(a)(1)(ii))."""

# US government entities that always receive 0% risk weight (§ __.111(a)(1)(i))
US_SOVEREIGN_ENTITIES: frozenset[str] = frozenset({
    "US_TREASURY",
    "US_GOVERNMENT",
    "FEDERAL_RESERVE",
    "GNMA",         # Government National Mortgage Association
    "SBA",          # Small Business Administration (guaranteed portion)
    "FDIC",         # Federal Deposit Insurance Corporation
    "PPP",          # Paycheck Protection Program covered loans (§ __.111(a)(1)(iii))
})
"""US government entities unconditionally assigned 0% risk weight."""


# =========================================================================
#  Supranational / MDB / GSE -- § __.111(b)-(c)
# =========================================================================

MDB_QUALIFYING_RW: float = 0.00
"""Specified supranational entities and MDBs: 0% (§ __.111(b))."""

MDB_NON_QUALIFYING_RW: float = 1.00
"""Non-qualifying MDB treated as a corporate exposure: 100%."""

GSE_RW: float = 0.20
"""Exposure to a GSE that is not equity or subordinated: 20% (§ __.111(c)(1))."""

GSE_SUBORDINATED_RW: float = 1.50
"""Subordinated exposure to a GSE: 150% (§ __.111(c)(2))."""

GSE_FHLB_FARMER_MAC_SUBORDINATED_RW: float = 0.20
"""Subordinated exposure to a Federal Home Loan Bank or Farmer Mac: 20%
(§ __.111(c)(3))."""


# =========================================================================
#  Bank Exposures -- Table 2 to § __.111 (ERBA NPR p. 688-690)
# =========================================================================

class BankGrade(str, Enum):
    """Bank exposure grades per § __.101 definitions (ERBA NPR pp. 675-677).

    GRADE_A: obligor is investment grade and meets the higher of its
        minimum-plus-buffer requirements or the well-capitalized thresholds.
    GRADE_B: obligor is investment or speculative grade and meets the higher
        of its minimum requirements or the adequately-capitalized thresholds.
    GRADE_C: any bank exposure that is neither Grade A nor Grade B.

    A bank exposure is NOT Grade A or B if the obligor's capital ratios were
    not publicly disclosed within the previous 6 months, the external auditor
    issued an adverse opinion / going-concern doubt within 12 months, or (for
    a foreign bank) home-country capital standards are not broadly consistent
    with the Basel Accord.
    """

    GRADE_A = "A"
    GRADE_B = "B"
    GRADE_C = "C"


BANK_RW_BY_GRADE: dict[BankGrade, float] = {
    BankGrade.GRADE_A: 0.40,   # Grade A, otherwise (not meeting (d)(2))
    BankGrade.GRADE_B: 0.75,
    BankGrade.GRADE_C: 1.50,
}
"""Base risk weights for bank exposures, Table 2 to § __.111.

Grade A "otherwise" 40%; Grade B 75%; Grade C 150%.  A Grade A exposure
meeting the criteria in § __.111(d)(2) receives 30% (see
:data:`BANK_GRADE_A_ENHANCED_RW`).
"""

BANK_GRADE_A_ENHANCED_RW: float = 0.30
"""Grade A bank exposure meeting § __.111(d)(2): 30%.

(d)(2) is met when the obligor is a qualifying community banking
organization using the CBLR framework, OR its most recent ratios are at
least: CET1 14% and SLR 5% (Category I-III DI), CET1 14% and tier 1
leverage 5% (other DI), net worth 9% (credit union), CET1 14% and
leverage 5% under home-country rules (foreign bank).
"""

BANK_GRADE_A_ENHANCED_CET1_THRESHOLD: float = 0.14
"""CET1 ratio threshold for the 30% Grade A risk weight (§ __.111(d)(2)(ii))."""

BANK_GRADE_A_ENHANCED_LEVERAGE_THRESHOLD: float = 0.05
"""Leverage (SLR or tier 1 leverage) threshold for the 30% Grade A risk
weight (§ __.111(d)(2)(ii))."""

BANK_CREDIT_UNION_NET_WORTH_THRESHOLD: float = 0.09
"""Credit union net worth ratio threshold for the 30% Grade A risk weight."""

BANK_SHORT_TERM_TRADE_RW_BY_GRADE: dict[BankGrade, float] = {
    BankGrade.GRADE_A: 0.20,
    BankGrade.GRADE_B: 0.50,
    BankGrade.GRADE_C: 1.50,
}
"""Table 2 to § __.111, second row: risk weight for a FOREIGN bank exposure
that is a self-liquidating, trade-related contingent item arising from the
movement of goods with a maturity of three months or less.  Grade A (both
columns) 20%; Grade B 50%; Grade C 150%.  The ERBA NPR provides NO general
short-term preferential risk weight for bank exposures.
"""

BANK_SHORT_TERM_TRADE_MAX_MATURITY_YEARS: float = 0.25
"""Three-month maturity ceiling for the trade-related row of Table 2."""

BANK_SUBORDINATED_RW: float = 1.50
"""Bank exposure that is subordinated or a covered debt instrument (TLAC)
not deducted from capital: 150% (§ __.111(d)(4)(ii))."""


# =========================================================================
#  Public Sector Entities -- § __.111(e), Tables 3 and 4 (pp. 690-692)
# =========================================================================

PSE_GENERAL_OBLIGATION_RW: float = 0.20
"""US PSE general obligation: 20% (§ __.111(e)(1)(i))."""

PSE_REVENUE_OBLIGATION_RW: float = 0.50
"""US PSE revenue obligation: 50% (§ __.111(e)(1)(ii))."""

FOREIGN_PSE_GO_RW: dict[int, float] = {
    0: 0.20, 1: 0.20,          # CRC 0-1: 20%
    2: 0.50,                   # CRC 2: 50%
    3: 1.00,                   # CRC 3: 100%
    4: 1.50, 5: 1.50, 6: 1.50, 7: 1.50,   # CRC 4-7: 150%
}
"""Table 3 to § __.111 -- non-US PSE general obligations by home-country CRC."""

FOREIGN_PSE_REVENUE_RW: dict[int, float] = {
    0: 0.50, 1: 0.50,          # CRC 0-1: 50%
    2: 1.00, 3: 1.00,          # CRC 2-3: 100%
    4: 1.50, 5: 1.50, 6: 1.50, 7: 1.50,   # CRC 4-7: 150%
}
"""Table 4 to § __.111 -- non-US PSE revenue obligations by home-country CRC."""

FOREIGN_PSE_OECD_NO_CRC_GO_RW: float = 0.20
FOREIGN_PSE_OECD_NO_CRC_REVENUE_RW: float = 0.50
FOREIGN_PSE_NON_OECD_NO_CRC_RW: float = 1.00
FOREIGN_PSE_SOVEREIGN_DEFAULT_RW: float = 1.50


# =========================================================================
#  Residential Real Estate -- Tables 5 and 6 to § __.111 (pp. 692-693)
# =========================================================================

RESI_MORTGAGE_RW: dict[str, float] = {
    "0-50":   0.20,   # LTV <= 50%
    "50-60":  0.25,   # 50% < LTV <= 60%
    "60-80":  0.30,   # 60% < LTV <= 80%
    "80-90":  0.40,   # 80% < LTV <= 90%
    "90-100": 0.50,   # 90% < LTV <= 100%
    "100+":   0.70,   # LTV > 100%
}
"""Table 5 to § __.111 -- regulatory residential real estate exposures NOT
dependent on the cash flows generated by the real estate (ERBA NPR p. 692):
20% / 25% / 30% / 40% / 50% / 70% for LTV ≤50 / ≤60 / ≤80 / ≤90 / ≤100 /
>100 percent.  (The July 2023 NPR's 40-90% schedule was withdrawn.)
"""

RESI_MORTGAGE_CF_DEPENDENT_RW: dict[str, float] = {
    "0-50":   0.30,
    "50-60":  0.35,
    "60-80":  0.45,
    "80-90":  0.60,
    "90-100": 0.75,
    "100+":   1.05,
}
"""Table 6 to § __.111 -- regulatory residential real estate exposures that
ARE dependent on the cash flows generated by the real estate (p. 693):
30% / 35% / 45% / 60% / 75% / 105%.  A mortgage secured by the borrower's
principal residence is deemed NOT dependent on cash flows (§ __.101).
"""

OTHER_RESIDENTIAL_NOT_CF_DEPENDENT_RW: float = 1.00
"""Residential mortgage that is not a *regulatory* residential real estate
exposure and is not dependent on cash flows: 100% (§ __.111(f)(7))."""

OTHER_REAL_ESTATE_RW: float = 1.50
"""Other real estate exposure (does not meet regulatory RRE/CRE criteria):
150% (§ __.111(f)(7))."""

PAST_DUE_RESIDENTIAL_NOT_CF_DEPENDENT_RW: float = 1.00
"""90+ days past due / nonaccrual residential mortgage not dependent on
cash flows: 100% (§ __.111(f)(8)); all other past-due real estate 150%."""


# =========================================================================
#  Commercial Real Estate -- Tables 7 and 8 to § __.111 (p. 693)
# =========================================================================

CRE_NOT_CF_DEPENDENT_LOW_LTV_CAP: float = 0.60
"""Table 7 to § __.111: regulatory CRE not dependent on real estate cash
flows with LTV ≤ 60% receives the LESSER of 60% and the borrower's risk
weight; LTV > 60% receives the borrower's risk weight (100% if the borrower
risk weight cannot be determined)."""

CRE_NOT_CF_DEPENDENT_LTV_THRESHOLD: float = 0.60

CRE_BORROWER_RW_DEFAULT: float = 1.00
"""Borrower risk weight to use when it cannot be determined (§ __.111(f)(6)(i))."""

CRE_INCOME_PRODUCING_RW: dict[str, float] = {
    "0-60":  0.70,    # LTV <= 60%
    "60-80": 0.90,    # 60% < LTV <= 80%
    "80+":   1.10,    # LTV > 80%
}
"""Table 8 to § __.111 -- regulatory CRE exposures dependent on the cash
flows generated by the real estate: 70% / 90% / 110%."""

CRE_ADC_RW: float = 1.00
"""ADC exposure that is NOT an HVCRE exposure: 100% (§ __.111(f)(4))."""

HVCRE_RW: float = 1.50
"""High-volatility commercial real estate exposure: 150% (§ __.111(f)(3))."""

CRE_PRESOLD_CONSTRUCTION_RW: float = 0.50
"""Pre-sold construction loan: 50%; 100% if the purchase contract is
cancelled (§ __.111(f)(2))."""

CRE_PRESOLD_CONSTRUCTION_CANCELLED_RW: float = 1.00

CRE_STATUTORY_MULTIFAMILY_RW: float = 0.50
"""Statutory multifamily mortgage: 50% (§ __.111(f)(1))."""

CRE_LAND_RW: float = CRE_ADC_RW
"""Land development and other land loans are ADC exposures by definition
(§ __.101): 100% unless HVCRE (150%)."""

# Retained for backwards compatibility with callers that still pass the
# pre-NPR "pre-sold ADC" flag; the NPR term is "pre-sold construction loan".
CRE_ADC_PRESOLD_RW: float = CRE_PRESOLD_CONSTRUCTION_RW


# =========================================================================
#  Retail -- § __.111(g) (p. 694)
# =========================================================================

RETAIL_RW: float = 0.75
"""Regulatory retail exposure that is not a transactor: 75% (§ __.111(g)(1)(i)).

Regulatory retail (§ __.101): revolving credit / line of credit / term loan
or lease to a natural person or SME, with aggregate retail exposure to the
obligor and affiliates ≤ $1 million (indexed under § __.4).
"""

RETAIL_TRANSACTOR_RW: float = 0.45
"""Transactor exposure: 45% (§ __.111(g)(1)(ii)).

Transactor (§ __.101): credit facility where the balance has been repaid in
full at each scheduled repayment date for the previous 12 months, or an
overdraft facility with no drawdown over the previous 12 months.
"""

RETAIL_OTHER_RW: float = 1.00
"""Retail exposure that is not a regulatory retail exposure: 100%
(§ __.111(g)(2))."""

REGULATORY_RETAIL_AGGREGATE_LIMIT: float = 1_000_000.0
"""$1 million aggregate retail exposure limit (§ __.101; indexed per § __.4)."""

SME_REVENUE_THRESHOLD: float = 50_000_000.0
"""$50 million annual revenue threshold defining an SME (§ __.101; indexed)."""


# =========================================================================
#  Corporate -- § __.111(h) (pp. 694-698)
# =========================================================================

CORPORATE_IG_RW: float = 0.65
"""Investment-grade corporate exposure that is not subordinated: 65%
(§ __.111(h)(1)).  Investment grade may be determined ONLY through an
internal credit risk rating system meeting § __.111(h)(1)(i)-(v)
(Dodd-Frank § 939A -- no external ratings)."""

CORPORATE_STANDARD_RW: float = 1.00
"""All other corporate exposures: 100% (§ __.111(h))."""

CORPORATE_SME_RW: float = CORPORATE_STANDARD_RW
"""SME corporate exposures: 100%.

The ERBA NPR (§ __.111(h)) contains NO preferential risk weight for SME
corporates.  The 85% SME weight in BCBS CRE20.47 was not adopted; SMEs
benefit only if the exposure meets the regulatory retail criteria
(aggregate ≤ $1 million → 75% / 45%).  Constant retained so that legacy
callers using ``ExposureClass.CORPORATE_SME`` receive the correct 100%.
"""

CORPORATE_OBJECT_FINANCE_RW: float = 1.00
"""Corporate exposure financing equipment or physical commodities where
repayment depends on the physical assets: 100% (§ __.111(h)(2))."""

PROJECT_FINANCE_OPERATIONAL_RW: float = 1.00
"""Project finance operational phase exposure: 100% (§ __.111(h)(3)(i))."""

PROJECT_FINANCE_PREOPERATIONAL_RW: float = 1.30
"""Project finance exposure not in the operational phase: 130%
(§ __.111(h)(3)(ii))."""

QCCP_CASH_COLLATERAL_SEGREGATED_RW: float = 0.02
"""Cash collateral posted to a QCCP under § __.116(b)(3)(i)(A) or (c)(3)(i):
2% (§ __.111(h)(4))."""

QCCP_CASH_COLLATERAL_NON_SEGREGATED_RW: float = 0.04
"""Cash collateral posted to a QCCP under § __.116(b)(3)(i)(B): 4%."""

SUBORDINATED_DEBT_RW: float = 1.50
"""Corporate / bank / GSE subordinated exposure, including preferred stock
that is not an equity exposure, and covered debt instruments: 150%
(§ __.111(h)(5), (d)(4)(ii), (c)(2))."""


# =========================================================================
#  Past due -- § __.111(i)
# =========================================================================

DEFAULTED_RW: float = 1.50
"""Exposure 90 days or more past due or on nonaccrual (other than sovereign
or real estate): 150% (§ __.111(i)).  Real estate: § __.111(f)(8)."""


# =========================================================================
#  Equity -- § __.141 simple risk-weight approach (pp. 777-779)
# =========================================================================

EQUITY_SOVEREIGN_RW: float = 0.00
"""Equity exposure to a sovereign, supranational, MDB or other 0% entity
(including a Federal Reserve Bank): 0% (§ __.141(b)(1))."""

EQUITY_FRB_STOCK_RW: float = EQUITY_SOVEREIGN_RW
"""Federal Reserve Bank stock: equity exposure to the US central bank, whose
credit exposures receive 0% under § __.111(a)(1) → 0% (§ __.141(b)(1))."""

EQUITY_PSE_FHLB_FARMER_MAC_RW: float = 0.20
"""Equity exposure to a PSE, Federal Home Loan Bank or Farmer Mac: 20%
(§ __.141(b)(2))."""

EQUITY_COMMUNITY_DEV_RW: float = 1.00
"""Community development investment under 12 U.S.C. 24 (Eleventh): 100%
(§ __.141(b)(3)(i))."""

EQUITY_NON_SIGNIFICANT_RW: float = 1.00
"""Non-significant equity exposures up to 10% of total capital in aggregate:
100% (§ __.141(b)(3)(iii))."""

EQUITY_NON_SIGNIFICANT_CAPITAL_LIMIT: float = 0.10
"""Aggregate adjusted carrying value limit (10% of total capital) for the
100% bucket (§ __.141(b)(3)(iii))."""

EQUITY_SIGNIFICANT_FI_RW: float = 2.50
"""Significant investment in the capital of an unconsolidated financial
institution in the form of common stock not deducted under § __.22(d)(2):
250% (§ __.141(b)(4))."""

EQUITY_PUBLIC_TRADED_RW: float = 3.00
"""Publicly traded equity exposure (including the ineffective portion of a
hedge pair): 300% (§ __.141(b)(5))."""

EQUITY_NON_PUBLIC_RW: float = 4.00
"""Equity exposure that is not publicly traded: 400% (§ __.141(b)(6))."""

EQUITY_SPECULATIVE_RW: float = EQUITY_NON_PUBLIC_RW
"""Non-publicly-traded 'speculative' equity: 400% (§ __.141(b)(6))."""

EQUITY_VENTURE_CAPITAL_RW: float = EQUITY_NON_PUBLIC_RW
"""Venture capital / private equity (not publicly traded): 400%."""

EQUITY_INVESTMENT_FIRM_LEVERAGED_RW: float = 6.00
"""Equity exposure to an investment firm that would be a traditional
securitization but for paragraph (8) of that definition and has greater
than immaterial leverage: 600% (§ __.141(b)(7))."""

EQUITY_OTHER_RW: float = EQUITY_NON_PUBLIC_RW
"""Residual: an equity exposure that cannot be placed in a lower bucket is,
by § __.141(b)(6), a non-publicly-traded exposure → 400%."""

EQUITY_FUND_MIN_RW: float = 0.20
"""Minimum risk weight for an equity exposure to an investment fund under
any look-through approach: 20% (§ __.142(a)(1))."""

EQUITY_COMMITMENT_CF_CONDITIONAL: float = 0.40
"""Conversion factor for conditional equity commitments (§ __.140(b)(3)(i))."""

EQUITY_COMMITMENT_CF_UNCONDITIONAL: float = 1.00
"""Conversion factor for unconditional equity commitments (§ __.140(b)(3)(ii))."""

EQUITY_RW_BY_SUBTYPE: dict[EquitySubType, float] = {
    EquitySubType.SOVEREIGN_MDB: EQUITY_SOVEREIGN_RW,
    EquitySubType.FEDERAL_RESERVE_STOCK: EQUITY_FRB_STOCK_RW,
    EquitySubType.PSE_FHLB_FARMER_MAC: EQUITY_PSE_FHLB_FARMER_MAC_RW,
    EquitySubType.COMMUNITY_DEVELOPMENT: EQUITY_COMMUNITY_DEV_RW,
    EquitySubType.NON_SIGNIFICANT: EQUITY_NON_SIGNIFICANT_RW,
    EquitySubType.SIGNIFICANT_FI_NOT_DEDUCTED: EQUITY_SIGNIFICANT_FI_RW,
    EquitySubType.PUBLIC_TRADED: EQUITY_PUBLIC_TRADED_RW,
    EquitySubType.SPECULATIVE: EQUITY_SPECULATIVE_RW,
    EquitySubType.VENTURE_CAPITAL: EQUITY_VENTURE_CAPITAL_RW,
    EquitySubType.INVESTMENT_FIRM_LEVERAGED: EQUITY_INVESTMENT_FIRM_LEVERAGED_RW,
    EquitySubType.OTHER: EQUITY_OTHER_RW,
}
"""Equity risk weights by sub-type per § __.141(b)."""


# =========================================================================
#  Other assets -- § __.111(j)-(k) (pp. 698-700)
# =========================================================================

CASH_RW: float = 0.00
"""Cash owned and held or in transit, allocated gold bullion offset by gold
liabilities, and CCP cash-settlement exposures: 0% (§ __.111(j)(1))."""

CASH_ITEMS_IN_COLLECTION_RW: float = 0.20
"""Cash items in the process of collection: 20% (§ __.111(j)(2))."""

DTA_CARRYBACK_RW: float = 1.00
"""DTAs arising from temporary differences realizable through NOL
carrybacks: 100% (§ __.111(j)(3))."""

DTA_TEMPORARY_DIFFERENCE_RW: float = 2.50
"""DTAs from temporary differences not realizable through carrybacks, to
the extent not deducted: 250% (§ __.111(j)(4)(ii))."""

MSA_RW: float = 2.50
"""Mortgage servicing assets: 250% (§ __.111(j)(4)(i)).

The 2026 proposal removes the CET1 threshold deduction for MSAs; all MSAs
are risk weighted at 250% and MSAs are excluded from the 15% aggregate
threshold calculation (NPR p. 40).
"""

OTHER_RW: float = 1.00
"""All assets not specifically assigned a different risk weight and not
deducted from capital: 100% (§ __.111(j)(5))."""

POLICY_LOAN_RW: float = 0.20
"""Insurance policy loans held by a holding company: 20% (§ __.111(k)(2))."""

NON_GUARANTEED_SEPARATE_ACCOUNT_RW: float = 0.00
"""Assets in a non-guaranteed separate account: 0% (§ __.111(k)(1)(ii))."""


# =========================================================================
#  Risk Weight Lookup Data Class
# =========================================================================

class RiskWeightInput(BaseModel):
    """Input parameters for risk weight determination under § __.111.

    Encapsulates all the attributes needed to look up the correct ERBA
    risk weight for an exposure.
    """

    exposure_class: ExposureClass = Field(
        description="SA-CR exposure class for the exposure",
    )
    country_risk_class: Optional[int] = Field(
        default=0,
        ge=0,
        le=7,
        description=(
            "OECD Country Risk Classification (0-7) of the sovereign or of "
            "the bank's / PSE's home country; None if no CRC is assigned"
        ),
    )
    is_oecd_member: bool = Field(
        default=True,
        description="OECD membership of the (home-country) sovereign when no CRC exists",
    )
    is_sovereign_default: bool = Field(
        default=False,
        description="Sovereign default event now or within the previous five years",
    )
    is_us_sovereign: bool = Field(
        default=False,
        description="Whether the sovereign is the US government / central bank / agency",
    )
    is_us_entity: bool = Field(
        default=True,
        description="Whether a PSE / bank obligor is organized in the United States",
    )
    bank_grade: BankGrade = Field(
        default=BankGrade.GRADE_A,
        description=(
            "Grade A / B / C of a bank exposure per § __.101. Default assumes "
            "an investment-grade, well-capitalized obligor (Grade A, 40%)"
        ),
    )
    bank_meets_enhanced_criteria: bool = Field(
        default=False,
        description=(
            "Grade A obligor meets § __.111(d)(2): CBLR bank, or CET1 >= 14% "
            "and leverage >= 5% (credit union net worth >= 9%) -> 30%"
        ),
    )
    is_short_term_trade_related: bool = Field(
        default=False,
        description=(
            "Foreign bank exposure that is a self-liquidating, trade-related "
            "contingent item from the movement of goods, maturity <= 3 months"
        ),
    )
    is_local_currency: bool = Field(
        default=False,
        description=(
            "Exposure to a foreign bank denominated in the local currency "
            "(exempts the exposure from the home-sovereign risk-weight floor)"
        ),
    )
    is_subordinated: bool = Field(
        default=False,
        description="Subordinated exposure or covered debt instrument (150%)",
    )
    is_investment_grade: bool = Field(
        default=False,
        description="Internal-rating-based investment-grade status for corporates",
    )
    is_project_finance: bool = Field(
        default=False,
        description="Corporate exposure is a project finance exposure",
    )
    is_project_finance_operational: bool = Field(
        default=False,
        description="Project finance exposure is in the operational phase",
    )
    ltv_ratio: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Loan-to-value ratio for real estate exposures",
    )
    is_dependent_on_cash_flows: bool = Field(
        default=False,
        description=(
            "Real estate exposure whose repayment is dependent on the cash "
            "flows generated by the real estate (§ __.101)"
        ),
    )
    is_regulatory_real_estate: bool = Field(
        default=True,
        description=(
            "Exposure meets the regulatory residential / commercial real "
            "estate criteria of § __.101 (prudent underwriting, first lien, "
            "valuation under § __.5, not restructured)"
        ),
    )
    borrower_risk_weight: Optional[float] = Field(
        default=None,
        ge=0.0,
        description=(
            "Risk weight applicable to the borrower under § __.111, used for "
            "regulatory CRE not dependent on cash flows (Table 7)"
        ),
    )
    is_past_due: bool = Field(
        default=False,
        description="90 days or more past due or on nonaccrual",
    )
    pse_obligation_type: Optional[PSEObligationType] = Field(
        default=None,
        description="General vs. revenue obligation for PSE exposures",
    )
    mdb_code: Optional[str] = Field(
        default=None,
        description="MDB identifier for qualifying check",
    )
    equity_sub_type: Optional[EquitySubType] = Field(
        default=None,
        description="Sub-type for equity exposures",
    )
    cre_sub_type: Optional[CRESubType] = Field(
        default=None,
        description="Sub-type for CRE exposures",
    )
    maturity_years: float = Field(
        default=2.5,
        ge=0.0,
        description="Remaining maturity in years (used for the trade-related bank row)",
    )
    is_presold_adc: bool = Field(
        default=False,
        description=(
            "Legacy flag: pre-sold construction loan (50%).  Prefer "
            "cre_sub_type=CRESubType.PRESOLD_CONSTRUCTION"
        ),
    )
    is_purchase_contract_cancelled: bool = Field(
        default=False,
        description="Pre-sold construction loan whose purchase contract was cancelled (100%)",
    )
    is_fhlb_or_farmer_mac: bool = Field(
        default=False,
        description="GSE obligor is a Federal Home Loan Bank or Farmer Mac",
    )


# =========================================================================
#  Risk Weight Lookup Functions
# =========================================================================

def get_sovereign_risk_weight(
    country_risk_class: Optional[int],
    is_us_sovereign: bool = False,
    is_oecd_member: bool = True,
    is_sovereign_default: bool = False,
) -> float:
    """Determine the risk weight for a sovereign exposure per § __.111(a).

    Args:
        country_risk_class: CRC 0-7, or None if the sovereign has no CRC.
        is_us_sovereign: US government, central bank or agency (always 0%).
        is_oecd_member: OECD membership, used only when no CRC exists.
        is_sovereign_default: Sovereign default now or within five years.

    Returns:
        Risk weight as a decimal.

    References:
        ERBA NPR § __.111(a)(1)-(6), Table 1 to § __.111 (pp. 686-688).
    """
    if is_us_sovereign:
        return 0.00
    if is_sovereign_default:
        return SOVEREIGN_DEFAULT_RW
    if country_risk_class is None:
        return SOVEREIGN_OECD_NO_CRC_RW if is_oecd_member else SOVEREIGN_NON_OECD_NO_CRC_RW
    return SOVEREIGN_RW.get(country_risk_class, SOVEREIGN_DEFAULT_RW)


def get_bank_risk_weight(
    grade: BankGrade = BankGrade.GRADE_A,
    meets_enhanced_criteria: bool = False,
    is_short_term_trade_related: bool = False,
    maturity_years: float = 2.5,
    is_subordinated: bool = False,
    is_us_entity: bool = True,
    is_local_currency: bool = False,
    home_sovereign_risk_weight: Optional[float] = None,
) -> float:
    """Determine the risk weight for a bank exposure per § __.111(d).

    Table 2 to § __.111: Grade A 30% (if § __.111(d)(2) criteria met) or
    40%; Grade B 75%; Grade C 150%.  A foreign-bank, self-liquidating,
    trade-related contingent item with maturity ≤ 3 months receives
    20% / 20% / 50% / 150%.  Subordinated bank exposures and covered debt
    instruments receive 150% (§ __.111(d)(4)(ii)).

    Per § __.111(d)(3) an exposure to a FOREIGN bank may not receive a risk
    weight lower than that of its home sovereign unless the exposure is in
    local currency or is a short-term trade-related contingent item.

    Args:
        grade: Grade A / B / C classification of the obligor.
        meets_enhanced_criteria: Grade A obligor meets (d)(2) (30%).
        is_short_term_trade_related: Trade-related contingent item.
        maturity_years: Remaining maturity (trade row requires ≤ 0.25y).
        is_subordinated: Subordinated / covered debt instrument.
        is_us_entity: Obligor is a US depository institution / credit union.
        is_local_currency: Exposure in the foreign bank's local currency.
        home_sovereign_risk_weight: Risk weight of the foreign bank's home
            sovereign (floor), if known.

    Returns:
        Risk weight as a decimal.

    References:
        ERBA NPR § __.111(d), Table 2 to § __.111 (pp. 688-690).
    """
    if is_subordinated:
        return BANK_SUBORDINATED_RW

    trade_row = (
        is_short_term_trade_related
        and not is_us_entity
        and maturity_years <= BANK_SHORT_TERM_TRADE_MAX_MATURITY_YEARS
    )
    if trade_row:
        rw = BANK_SHORT_TERM_TRADE_RW_BY_GRADE[grade]
    elif grade == BankGrade.GRADE_A and meets_enhanced_criteria:
        rw = BANK_GRADE_A_ENHANCED_RW
    else:
        rw = BANK_RW_BY_GRADE[grade]

    # § __.111(d)(3): home-sovereign floor for foreign banks
    if (
        not is_us_entity
        and home_sovereign_risk_weight is not None
        and not is_local_currency
        and not trade_row
    ):
        rw = max(rw, home_sovereign_risk_weight)
    return rw


def get_corporate_risk_weight(
    is_investment_grade: bool = False,
    is_sme: bool = False,
    is_subordinated: bool = False,
    is_project_finance: bool = False,
    is_project_finance_operational: bool = False,
) -> float:
    """Determine the risk weight for a corporate exposure per § __.111(h).

    Order of precedence follows § __.111(h): subordinated 150%; project
    finance 130% / 100%; investment grade 65%; otherwise 100%.  The
    ``is_sme`` flag has no effect (no SME preferential weight in the NPR).

    References:
        ERBA NPR § __.111(h)(1)-(5) (pp. 694-698).
    """
    if is_subordinated:
        return SUBORDINATED_DEBT_RW
    if is_project_finance:
        return (
            PROJECT_FINANCE_OPERATIONAL_RW
            if is_project_finance_operational
            else PROJECT_FINANCE_PREOPERATIONAL_RW
        )
    if is_investment_grade:
        return CORPORATE_IG_RW
    return CORPORATE_STANDARD_RW


def get_residential_mortgage_risk_weight(
    ltv_ratio: float,
    is_dependent_on_cash_flows: bool = False,
    is_regulatory_real_estate: bool = True,
    is_past_due: bool = False,
) -> float:
    """Determine the risk weight for a residential mortgage exposure.

    Tables 5 and 6 to § __.111 apply to *regulatory* residential real estate
    exposures.  A residential mortgage that does not meet the regulatory
    criteria receives 100% (not dependent on cash flows) or 150%
    (§ __.111(f)(7)).  Past-due residential mortgages receive 100% (not
    dependent) or 150% (§ __.111(f)(8)).

    Args:
        ltv_ratio: Current LTV ratio as a decimal (e.g., 0.80 for 80%).
        is_dependent_on_cash_flows: Repayment depends on real estate cash flows.
        is_regulatory_real_estate: Meets the § __.101 regulatory RRE criteria.
        is_past_due: 90+ days past due or on nonaccrual.

    References:
        ERBA NPR § __.111(f)(5), (7), (8); Tables 5-6 (pp. 692-694).
    """
    if is_past_due:
        return (
            OTHER_REAL_ESTATE_RW
            if is_dependent_on_cash_flows
            else PAST_DUE_RESIDENTIAL_NOT_CF_DEPENDENT_RW
        )
    if not is_regulatory_real_estate:
        return (
            OTHER_REAL_ESTATE_RW
            if is_dependent_on_cash_flows
            else OTHER_RESIDENTIAL_NOT_CF_DEPENDENT_RW
        )
    bucket = get_resi_mortgage_ltv_bucket(ltv_ratio)
    table = RESI_MORTGAGE_CF_DEPENDENT_RW if is_dependent_on_cash_flows else RESI_MORTGAGE_RW
    return table[bucket]


def get_cre_risk_weight(
    cre_sub_type: CRESubType | None = None,
    ltv_ratio: float | None = None,
    is_presold_adc: bool = False,
    is_dependent_on_cash_flows: bool | None = None,
    borrower_risk_weight: float | None = None,
    is_regulatory_real_estate: bool = True,
    is_past_due: bool = False,
    is_purchase_contract_cancelled: bool = False,
) -> float:
    """Determine the risk weight for a commercial real estate exposure.

    Dispatch per § __.111(f):

    * statutory multifamily mortgage → 50%
    * pre-sold construction loan → 50% (100% if contract cancelled)
    * HVCRE → 150%; other ADC (incl. land loans) → 100%
    * regulatory CRE dependent on cash flows → Table 8 (70/90/110%)
    * regulatory CRE not dependent on cash flows → Table 7
      (LTV ≤ 60%: min(60%, borrower RW); LTV > 60%: borrower RW)
    * other real estate → 150%; past due → 150%

    ``CRESubType.INCOME_PRODUCING`` is interpreted as "dependent on the
    cash flows generated by the real estate" unless
    ``is_dependent_on_cash_flows`` is given explicitly.

    References:
        ERBA NPR § __.111(f)(1)-(8), Tables 7-8 (pp. 692-694).
    """
    if cre_sub_type == CRESubType.STATUTORY_MULTIFAMILY:
        return CRE_STATUTORY_MULTIFAMILY_RW
    if cre_sub_type == CRESubType.PRESOLD_CONSTRUCTION or is_presold_adc:
        return (
            CRE_PRESOLD_CONSTRUCTION_CANCELLED_RW
            if is_purchase_contract_cancelled
            else CRE_PRESOLD_CONSTRUCTION_RW
        )
    if cre_sub_type == CRESubType.HVCRE:
        return HVCRE_RW
    if cre_sub_type in (CRESubType.ADC, CRESubType.LAND):
        return CRE_ADC_RW
    if is_past_due or cre_sub_type == CRESubType.OTHER_REAL_ESTATE or not is_regulatory_real_estate:
        return OTHER_REAL_ESTATE_RW

    dependent = (
        is_dependent_on_cash_flows
        if is_dependent_on_cash_flows is not None
        else cre_sub_type in (None, CRESubType.INCOME_PRODUCING)
    )
    if dependent:
        if ltv_ratio is None:
            return CRE_INCOME_PRODUCING_RW["80+"]
        bucket = get_cre_ltv_bucket(ltv_ratio)
        return CRE_INCOME_PRODUCING_RW[bucket]

    # Table 7: not dependent on cash flows
    borrower_rw = (
        borrower_risk_weight if borrower_risk_weight is not None else CRE_BORROWER_RW_DEFAULT
    )
    if ltv_ratio is not None and ltv_ratio <= CRE_NOT_CF_DEPENDENT_LTV_THRESHOLD:
        return min(CRE_NOT_CF_DEPENDENT_LOW_LTV_CAP, borrower_rw)
    return borrower_rw


def get_equity_risk_weight(
    equity_sub_type: EquitySubType | None = None,
) -> float:
    """Determine the risk weight for an equity exposure per § __.141(b).

    Args:
        equity_sub_type: The equity sub-classification.

    Returns:
        Risk weight as a decimal (0%, 20%, 100%, 250%, 300%, 400%, 600%).

    References:
        ERBA NPR § __.141(b)(1)-(7) (pp. 777-779).
    """
    if equity_sub_type is not None:
        return EQUITY_RW_BY_SUBTYPE.get(equity_sub_type, EQUITY_OTHER_RW)
    return EQUITY_OTHER_RW


def get_pse_risk_weight(
    obligation_type: PSEObligationType | None = None,
    is_us_entity: bool = True,
    country_risk_class: Optional[int] = None,
    is_oecd_member: bool = True,
    is_sovereign_default: bool = False,
) -> float:
    """Determine the risk weight for a PSE exposure per § __.111(e).

    US PSEs: general obligation 20%, revenue obligation 50%.  Foreign PSEs:
    Table 3 (general obligation) / Table 4 (revenue obligation) by the CRC
    of the PSE's home country, or OECD status when no CRC exists.

    References:
        ERBA NPR § __.111(e)(1)-(6), Tables 3-4 (pp. 690-692).
    """
    revenue = obligation_type == PSEObligationType.REVENUE_OBLIGATION
    if is_us_entity:
        return PSE_REVENUE_OBLIGATION_RW if revenue else PSE_GENERAL_OBLIGATION_RW
    if is_sovereign_default:
        return FOREIGN_PSE_SOVEREIGN_DEFAULT_RW
    if country_risk_class is None:
        if not is_oecd_member:
            return FOREIGN_PSE_NON_OECD_NO_CRC_RW
        return FOREIGN_PSE_OECD_NO_CRC_REVENUE_RW if revenue else FOREIGN_PSE_OECD_NO_CRC_GO_RW
    table = FOREIGN_PSE_REVENUE_RW if revenue else FOREIGN_PSE_GO_RW
    return table.get(country_risk_class, FOREIGN_PSE_SOVEREIGN_DEFAULT_RW)


def get_gse_risk_weight(
    is_subordinated: bool = False,
    is_fhlb_or_farmer_mac: bool = False,
) -> float:
    """Determine the risk weight for a GSE exposure per § __.111(c).

    References:
        ERBA NPR § __.111(c)(1)-(3) (p. 688).
    """
    if is_subordinated:
        return GSE_FHLB_FARMER_MAC_SUBORDINATED_RW if is_fhlb_or_farmer_mac else GSE_SUBORDINATED_RW
    return GSE_RW


def get_mdb_risk_weight(mdb_code: str | None = None) -> float:
    """Determine the risk weight for an MDB exposure per § __.111(b).

    Args:
        mdb_code: The MDB identifier for qualifying status check.

    Returns:
        0% for specified supranationals / MDBs, else 100% (corporate).
    """
    if is_qualifying_mdb(mdb_code):
        return MDB_QUALIFYING_RW
    return MDB_NON_QUALIFYING_RW


def get_risk_weight(rw_input: RiskWeightInput) -> float:
    """Master risk weight lookup for any ERBA credit exposure class.

    Dispatches to the appropriate risk weight function based on the
    exposure class and its characteristics.

    Args:
        rw_input: Complete set of parameters for risk weight determination.

    Returns:
        Risk weight as a decimal (e.g., 0.20 for 20%, 1.50 for 150%).

    Raises:
        ValueError: If required parameters are missing for the exposure class.

    References:
        ERBA NPR § __.111 and § __.141 (pp. 686-700, 777-779).
    """
    ec = rw_input.exposure_class

    if ec == ExposureClass.SOVEREIGN:
        return get_sovereign_risk_weight(
            rw_input.country_risk_class,
            rw_input.is_us_sovereign,
            rw_input.is_oecd_member,
            rw_input.is_sovereign_default,
        )

    if ec == ExposureClass.PUBLIC_SECTOR_ENTITY:
        return get_pse_risk_weight(
            rw_input.pse_obligation_type,
            is_us_entity=rw_input.is_us_entity,
            country_risk_class=rw_input.country_risk_class,
            is_oecd_member=rw_input.is_oecd_member,
            is_sovereign_default=rw_input.is_sovereign_default,
        )

    if ec == ExposureClass.MULTILATERAL_DEV_BANK:
        return get_mdb_risk_weight(rw_input.mdb_code)

    if ec == ExposureClass.GSE:
        return get_gse_risk_weight(
            is_subordinated=rw_input.is_subordinated,
            is_fhlb_or_farmer_mac=rw_input.is_fhlb_or_farmer_mac,
        )

    if ec == ExposureClass.BANK:
        home_rw: Optional[float] = None
        if not rw_input.is_us_entity:
            home_rw = get_sovereign_risk_weight(
                rw_input.country_risk_class,
                False,
                rw_input.is_oecd_member,
                rw_input.is_sovereign_default,
            )
        return get_bank_risk_weight(
            grade=rw_input.bank_grade,
            meets_enhanced_criteria=rw_input.bank_meets_enhanced_criteria,
            is_short_term_trade_related=rw_input.is_short_term_trade_related,
            maturity_years=rw_input.maturity_years,
            is_subordinated=rw_input.is_subordinated,
            is_us_entity=rw_input.is_us_entity,
            is_local_currency=rw_input.is_local_currency,
            home_sovereign_risk_weight=home_rw,
        )

    if ec in (ExposureClass.CORPORATE, ExposureClass.CORPORATE_SME):
        return get_corporate_risk_weight(
            is_investment_grade=rw_input.is_investment_grade,
            is_subordinated=rw_input.is_subordinated,
            is_project_finance=rw_input.is_project_finance,
            is_project_finance_operational=rw_input.is_project_finance_operational,
        )

    if ec == ExposureClass.RETAIL:
        return RETAIL_RW

    if ec == ExposureClass.RETAIL_TRANSACTOR:
        return RETAIL_TRANSACTOR_RW

    if ec == ExposureClass.RETAIL_OTHER:
        return RETAIL_OTHER_RW

    if ec == ExposureClass.RESIDENTIAL_MORTGAGE:
        if rw_input.ltv_ratio is None and rw_input.is_regulatory_real_estate and not rw_input.is_past_due:
            raise ValueError(
                "ltv_ratio is required for residential mortgage exposures"
            )
        return get_residential_mortgage_risk_weight(
            rw_input.ltv_ratio if rw_input.ltv_ratio is not None else 0.0,
            is_dependent_on_cash_flows=rw_input.is_dependent_on_cash_flows,
            is_regulatory_real_estate=rw_input.is_regulatory_real_estate,
            is_past_due=rw_input.is_past_due,
        )

    if ec == ExposureClass.COMMERCIAL_REAL_ESTATE:
        return get_cre_risk_weight(
            cre_sub_type=rw_input.cre_sub_type or CRESubType.INCOME_PRODUCING,
            ltv_ratio=rw_input.ltv_ratio,
            is_presold_adc=rw_input.is_presold_adc,
            is_dependent_on_cash_flows=(
                rw_input.is_dependent_on_cash_flows
                if rw_input.cre_sub_type == CRESubType.REGULATORY_CRE
                else None
            ),
            borrower_risk_weight=rw_input.borrower_risk_weight,
            is_regulatory_real_estate=rw_input.is_regulatory_real_estate,
            is_past_due=rw_input.is_past_due,
            is_purchase_contract_cancelled=rw_input.is_purchase_contract_cancelled,
        )

    if ec == ExposureClass.HIGH_VOLATILITY_CRE:
        return HVCRE_RW

    if ec == ExposureClass.EQUITY:
        return get_equity_risk_weight(rw_input.equity_sub_type)

    if ec == ExposureClass.SUBORDINATED_DEBT:
        return SUBORDINATED_DEBT_RW

    if ec == ExposureClass.DEFAULTED:
        return DEFAULTED_RW

    if ec == ExposureClass.CASH:
        return CASH_RW

    if ec == ExposureClass.MSA:
        return MSA_RW

    if ec == ExposureClass.OTHER:
        return OTHER_RW

    # Fallback (should not be reached with complete enum coverage)
    return OTHER_RW


# =========================================================================
#  Risk Weight Summary Table (for reporting)
# =========================================================================

class RiskWeightSchedule(BaseModel):
    """Complete risk weight schedule for SA-CR reporting.

    Provides a structured summary of all applicable risk weights for
    regulatory reporting and internal governance (ERBA NPR § __.111).
    """

    sovereign_rw: dict[int, float] = Field(default_factory=lambda: dict(SOVEREIGN_RW))
    bank_rw: dict[str, float] = Field(
        default_factory=lambda: {
            "GRADE_A_ENHANCED": BANK_GRADE_A_ENHANCED_RW,
            **{f"GRADE_{g.value}": rw for g, rw in BANK_RW_BY_GRADE.items()},
        }
    )
    bank_short_term_trade_rw: dict[str, float] = Field(
        default_factory=lambda: {
            f"GRADE_{g.value}": rw for g, rw in BANK_SHORT_TERM_TRADE_RW_BY_GRADE.items()
        }
    )
    resi_mortgage_rw: dict[str, float] = Field(
        default_factory=lambda: dict(RESI_MORTGAGE_RW)
    )
    resi_mortgage_cf_dependent_rw: dict[str, float] = Field(
        default_factory=lambda: dict(RESI_MORTGAGE_CF_DEPENDENT_RW)
    )
    cre_income_producing_rw: dict[str, float] = Field(
        default_factory=lambda: dict(CRE_INCOME_PRODUCING_RW)
    )
    corporate_ig_rw: float = CORPORATE_IG_RW
    corporate_standard_rw: float = CORPORATE_STANDARD_RW
    corporate_sme_rw: float = CORPORATE_SME_RW
    project_finance_preoperational_rw: float = PROJECT_FINANCE_PREOPERATIONAL_RW
    retail_rw: float = RETAIL_RW
    retail_transactor_rw: float = RETAIL_TRANSACTOR_RW
    retail_other_rw: float = RETAIL_OTHER_RW
    equity_rw: dict[str, float] = Field(
        default_factory=lambda: {k.value: v for k, v in EQUITY_RW_BY_SUBTYPE.items()}
    )
    defaulted_rw: float = DEFAULTED_RW
    subordinated_debt_rw: float = SUBORDINATED_DEBT_RW
    msa_rw: float = MSA_RW
    cash_rw: float = CASH_RW
    other_rw: float = OTHER_RW
    hvcre_rw: float = HVCRE_RW
    cre_adc_rw: float = CRE_ADC_RW
    gse_rw: float = GSE_RW
