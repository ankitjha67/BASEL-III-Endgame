"""UK PRA Basel 3.1 regulatory parameters -- PRA PS1/26, Appendix 1.

Every constant used by the ``src.jurisdictions.uk`` package is defined here,
transcribed from the PRA Rulebook: CRR Firms: (CRR) Instrument 2026
(PRA2026/1, made 13 January 2026, in force 1 January 2027), with the Part,
article/rule and page ("p. N" = page N of 492) of that instrument:

* Glossary Part (Annex A) -- SME, transactor exposure, higher risk equity exposure.
* Required Level of Own Funds (CRR) Part (Annex B) -- Article 92: minimum ratios,
  output floor (TREA = max{U-TREA; x * S-TREA + OF-ADJ}) and transitional x.
* Credit Risk: General Provisions (CRR) Part (Annex C) -- rules 4.2/4.3 equity
  transitional risk weights.
* Credit Risk: Standardised Approach (CRR) Part (Annex D) -- Articles 111-137.
* Credit Risk Mitigation (CRR) Part (Annex F) -- Articles 223-239.
* Credit Valuation Adjustment Risk Part (Annex K) -- Chapters 4, 6 and 7.
* Operational Risk Part (Annex L) -- rules 4.1, 5.2-5.9, 7.1.
* Counterparty Credit Risk (CRR) Part amendments (Annex R) -- Article 274(2), (2A).

Supplementary sources (PRA Rulebook web text as in force on 1 January 2027), used to close
items the instrument only cross-references:

* Capital Buffers Part -- rules 1.2 (combined buffer), 2.1, 3.1, 4.3.
* Counterparty Credit Risk (CRR) Part -- Articles 275, 278, 279a, 280-280f (SA-CCR).

Values stated in GBP in the rules are kept in GBP *millions* here (the engine
is currency-agnostic: UK inputs are taken already expressed in GBP millions).

Anything the instrument does not settle carries ``# TODO: VERIFY`` with the
location where the value would be found, and a conservative placeholder.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

# =========================================================================
#  Credit quality steps (CQS) -- CRR Article 136 / Implementing Reg. 2016/1799
#  (the base contract maps RatingBucket <-> CQS 1-6; see base.rating_bucket_from_cqs)
# =========================================================================


def _cqs_table(values: tuple[float, float, float, float, float, float]) -> Mapping[int, float]:
    """Freeze a CQS 1-6 risk-weight row (helper; no regulatory content)."""
    return MappingProxyType({i + 1: v for i, v in enumerate(values)})


# -------------------------------------------------------------------------
# Article 114 -- central governments or central banks (p. 35-36)
# -------------------------------------------------------------------------
SOVEREIGN_UNRATED_RW: Final[float] = 1.00
"""Art 114(1): 100% unless paragraphs 2-4 apply (p. 35)."""
SOVEREIGN_RW_TABLE_1: Final[Mapping[int, float]] = _cqs_table((0.00, 0.20, 0.50, 1.00, 1.00, 1.50))
"""Art 114(2) Table 1 (p. 36)."""
SOVEREIGN_UK_STERLING_RW: Final[float] = 0.00
"""Art 114(4): UK central government and Bank of England, denominated and funded in sterling
(p. 36)."""
SOVEREIGN_ECB_RW: Final[float] = 0.00
"""Art 114(3): European Central Bank 0% (p. 36)."""

ECA_MEIP_RW_TABLE_9: Final[Mapping[int, float]] = MappingProxyType(
    {0: 0.00, 1: 0.00, 2: 0.20, 3: 0.50, 4: 1.00, 5: 1.00, 6: 1.00, 7: 1.50}
)
"""Art 137(2) Table 9 (p. 70). The extracted header shows MEIP '0 ... 6' but eight risk
weights (0%, 0%, 20%, 50%, 100%, 100%, 100%, 150%); the eight MEIP categories 0-7 of
Art 137(1)(b) are assumed. # TODO: VERIFY -- confirm Table 9 column header against the PDF."""

# -------------------------------------------------------------------------
# Article 115 -- regional governments or local authorities (p. 36-37)
# -------------------------------------------------------------------------
RGLA_UNRATED_SOVEREIGN_BASED_TABLE_1A: Final[Mapping[int, float]] = _cqs_table(
    (0.20, 0.50, 1.00, 1.00, 1.00, 1.50)
)
"""Art 115(1)(a)(i) Table 1A: unrated RGLA, by CQS of its central government (p. 37)."""
RGLA_UNRATED_NO_SOVEREIGN_RATING_RW: Final[float] = 1.00
"""Art 115(1)(a)(ii): 100% where the central government is unrated (p. 36)."""
RGLA_RATED_TABLE_1B: Final[Mapping[int, float]] = _cqs_table((0.20, 0.50, 0.50, 1.00, 1.00, 1.50))
"""Art 115(1)(b) Table 1B: rated RGLA (p. 37)."""
RGLA_UK_STERLING_RW: Final[float] = 0.20
"""Art 115(5): UK RGLAs (other than devolved administrations) in sterling, 20% (p. 37)."""
# Art 115(2): Scottish Government, Welsh Government, Northern Ireland Executive are treated
# as exposures to the UK central government (Article 114) (p. 37).

# -------------------------------------------------------------------------
# Article 116 -- public sector entities (p. 37-38)
# -------------------------------------------------------------------------
PSE_UNRATED_SOVEREIGN_BASED_TABLE_2: Final[Mapping[int, float]] = _cqs_table(
    (0.20, 0.50, 1.00, 1.00, 1.00, 1.50)
)
"""Art 116(1)(a) Table 2: unrated PSE, by CQS of the central government (p. 38)."""
PSE_UNRATED_NO_SOVEREIGN_RATING_RW: Final[float] = 1.00
"""Art 116(1)(b): 100% where the central government is unrated (p. 37)."""
PSE_RATED_TABLE_2A: Final[Mapping[int, float]] = _cqs_table((0.20, 0.50, 0.50, 1.00, 1.00, 1.50))
"""Art 116(2) Table 2A: rated PSE (p. 38)."""
PSE_SHORT_TERM_RW: Final[float] = 0.20
"""Art 116(3): original maturity of three months or less, 20% (p. 38)."""
PSE_SHORT_TERM_MAX_MONTHS: Final[float] = 3.0
"""Art 116(3): 'three months or less' (p. 38)."""

# -------------------------------------------------------------------------
# Article 117 / 118 -- MDBs and international organisations (p. 38-39)
# -------------------------------------------------------------------------
MDB_RATED_TABLE_2B: Final[Mapping[int, float]] = _cqs_table((0.20, 0.30, 0.50, 1.00, 1.00, 1.50))
"""Art 117(1)(a) Table 2B (p. 39)."""
MDB_UNRATED_RW: Final[float] = 0.50
"""Art 117(1)(b): unrated MDB 50% (p. 39)."""
MDB_LISTED_RW: Final[float] = 0.00
"""Art 117(2): the 16 listed MDBs (IBRD ... AIIB) 0% (p. 39)."""
MDB_ZERO_RW_LIST: Final[tuple[str, ...]] = (
    "International Bank for Reconstruction and Development",
    "International Finance Corporation",
    "Inter-American Development Bank",
    "Asian Development Bank",
    "African Development Bank",
    "Council of Europe Development Bank",
    "Nordic Investment Bank",
    "Caribbean Development Bank",
    "European Bank for Reconstruction and Development",
    "European Investment Bank",
    "European Investment Fund",
    "Multilateral Investment Guarantee Agency",
    "International Finance Facility for Immunisation",
    "Islamic Development Bank",
    "International Development Association",
    "Asian Infrastructure Investment Bank",
)
"""Art 117(2)(a)-(p) (p. 39)."""
INTERNATIONAL_ORGANISATION_RW: Final[float] = 0.00
"""Art 118(1): EU, IMF, BIS, EFSF, ESM 0% (p. 39-40)."""

# -------------------------------------------------------------------------
# Articles 119-121 -- institutions (p. 40-43)
# -------------------------------------------------------------------------
INSTITUTION_RATED_TABLE_3: Final[Mapping[int, float]] = _cqs_table(
    (0.20, 0.30, 0.50, 1.00, 1.00, 1.50)
)
"""Art 120(1) Table 3: rated, original maturity > 3 months (p. 40)."""
INSTITUTION_RATED_SHORT_TERM_TABLE_4: Final[Mapping[int, float]] = _cqs_table(
    (0.20, 0.20, 0.20, 0.50, 0.50, 1.50)
)
"""Art 120(2)/(2A) Table 4: rated, original maturity <= 3 months, or <= 6 months arising
from the movement of goods (p. 41)."""
INSTITUTION_SHORT_TERM_ASSESSMENT_TABLE_4A: Final[Mapping[str, float]] = MappingProxyType(
    {"1": 0.20, "2": 0.50, "3": 1.00, "OTHERS": 1.50}
)
"""Art 120(2B) Table 4A: short-term credit assessment CQS 1/2/3/Others (p. 41)."""
INSTITUTION_SHORT_TERM_MAX_MONTHS: Final[float] = 3.0
"""Art 120(2) / 121(3): 'three months or less' (p. 40, 43)."""
INSTITUTION_TRADE_GOODS_MAX_MONTHS: Final[float] = 6.0
"""Art 120(2A) / 121(4): 'six months or less' and arising from the movement of goods (p. 40, 43)."""

INSTITUTION_SCRA_TABLE_5: Final[Mapping[str, float]] = MappingProxyType(
    {"A": 0.40, "B": 0.75, "C": 1.50}
)
"""Art 121(2) Table 5: unrated, original maturity > 3 months (p. 43)."""
INSTITUTION_SCRA_SHORT_TERM_TABLE_5A: Final[Mapping[str, float]] = MappingProxyType(
    {"A": 0.20, "B": 0.50, "C": 1.50}
)
"""Art 121(3)/(4) Table 5A: unrated, <= 3 months or <= 6 months goods-related (p. 43)."""
INSTITUTION_SCRA_GRADE_A_ENHANCED_RW: Final[float] = 0.30
"""Art 121(5): Grade A, > 3 months, CET1 ratio >= 14% and leverage ratio >= 5% -> 30% (p. 43)."""
INSTITUTION_SCRA_ENHANCED_CET1_MIN: Final[float] = 0.14
"""Art 121(5)(a) (p. 43)."""
INSTITUTION_SCRA_ENHANCED_LEVERAGE_MIN: Final[float] = 0.05
"""Art 121(5)(b) (p. 43)."""
INSTITUTION_SOVEREIGN_FLOOR_TRADE_MAX_YEARS: Final[float] = 1.0
"""Art 121(6)(b): the sovereign floor does not apply to self-liquidating trade-related
contingent items arising from the movement of goods with original maturity < 1 year (p. 43)."""

# -------------------------------------------------------------------------
# Article 122 -- corporates (p. 44-45)
# -------------------------------------------------------------------------
CORPORATE_RATED_TABLE_6: Final[Mapping[int, float]] = _cqs_table(
    (0.20, 0.50, 0.75, 1.00, 1.50, 1.50)
)
"""Art 122(2) Table 6 (p. 44). Note CQS3 = 75% (BCBS CRE20.42: 75% for BBB+ to BBB-)."""
CORPORATE_SHORT_TERM_TABLE_6A: Final[Mapping[str, float]] = MappingProxyType(
    {"1": 0.20, "2": 0.50, "3": 1.00, "OTHERS": 1.50}
)
"""Art 122(3) Table 6A (p. 44)."""
CORPORATE_UNRATED_RW: Final[float] = 1.00
"""Art 122(5): unrated corporate without the paragraph 6 permission, 100% (p. 44)."""
CORPORATE_UNRATED_IG_RW: Final[float] = 0.65
"""Art 122(6)(a): with PRA permission, assessed investment grade, 65% (p. 44)."""
CORPORATE_UNRATED_NON_IG_RW: Final[float] = 1.35
"""Art 122(6)(b): with PRA permission, assessed not investment grade, 135% (p. 45)."""
CORPORATE_SME_UNRATED_RW: Final[float] = 0.85
"""Art 122(11): unrated non-retail SME, 85% (p. 45)."""

SME_TURNOVER_THRESHOLD_GBP_M: Final[float] = 44.0
"""Glossary 'SME': annual turnover of not more than GBP 44 million (p. 9)."""

# -------------------------------------------------------------------------
# Article 122B -- specialised lending (p. 46-47)
# -------------------------------------------------------------------------
SL_OBJECT_FINANCE_RW: Final[float] = 1.00
"""Art 122B(2)(a) (p. 46)."""
SL_COMMODITIES_FINANCE_RW: Final[float] = 1.00
"""Art 122B(2)(b) (p. 46)."""
SL_PF_PRE_OPERATIONAL_RW: Final[float] = 1.30
"""Art 122B(2)(c): pre-operational phase 130% (p. 46)."""
SL_PF_OPERATIONAL_RW: Final[float] = 1.00
"""Art 122B(2)(c): operational phase 100% (p. 46)."""
SL_PF_HIGH_QUALITY_OPERATIONAL_RW: Final[float] = 0.80
"""Art 122B(4): operational and high quality per paragraph 5, 80% (p. 46)."""

# -------------------------------------------------------------------------
# Articles 123, 123A, 123B -- retail (p. 47-49)
# -------------------------------------------------------------------------
RETAIL_TRANSACTOR_RW: Final[float] = 0.45
"""Art 123(3)(a): regulatory retail transactor exposures 45% (p. 48)."""
RETAIL_REGULATORY_RW: Final[float] = 0.75
"""Art 123(3)(b): regulatory retail, non-transactor, 75% (p. 48)."""
RETAIL_OTHER_RW: Final[float] = 1.00
"""Art 123(3)(c): other retail 100% (p. 48)."""
RETAIL_PAYROLL_PENSION_LOAN_RW: Final[float] = 0.35
"""Art 123(4): loans to pensioners/permanent employees against salary/pension transfer, 35% (p.
48)."""
RETAIL_PAYROLL_MAX_INSTALMENT_SHARE: Final[float] = 0.20
"""Art 123(4)(c): instalments <= 20% of net monthly pension or salary (p. 48)."""
RETAIL_PAYROLL_MAX_MATURITY_YEARS: Final[float] = 10.0
"""Art 123(4)(d): original maturity <= 10 years (p. 48)."""
RETAIL_AGGREGATE_LIMIT_GBP_M: Final[float] = 0.88
"""Art 123(1)(b)(ii) / 123A(1)(b)(ii): total owed <= GBP 880,000 (excluding RRE) (p. 47-48)."""
TRANSACTOR_LOOKBACK_MONTHS: Final[int] = 12
"""Glossary 'transactor exposure': repaid in full / overdraft not drawn over previous 12 months
(p. 9)."""

CURRENCY_MISMATCH_MULTIPLIER: Final[float] = 1.5
"""Art 123B(1): 1.5x the applicable RW for unhedged retail and residential RE (p. 49)."""
CURRENCY_MISMATCH_RW_CAP: Final[float] = 1.50
"""Art 123B(1): subject to a maximum risk weight of 150% (p. 49)."""
CURRENCY_MISMATCH_HEDGE_COVERAGE: Final[float] = 0.90
"""Art 123B(2)(a)(ii): hedges must cover at least 90% of any instalment (p. 49)."""

# -------------------------------------------------------------------------
# Articles 124-124L -- real estate (p. 50-58)
# -------------------------------------------------------------------------
RRE_LOAN_SPLIT_SECURED_SHARE: Final[float] = 0.55
"""Art 124F(1)(a): the part of the exposure up to 55% of the property value (p. 55)."""
RRE_LOAN_SPLIT_SECURED_RW: Final[float] = 0.20
"""Art 124F(1)(a): 20% on the secured part (p. 55)."""
CRE_LOAN_SPLIT_SECURED_SHARE: Final[float] = 0.55
"""Art 124H(1)(a): the part up to 55% of the property value (p. 56)."""
CRE_LOAN_SPLIT_SECURED_RW: Final[float] = 0.60
"""Art 124H(1)(a): 60% on the secured part (natural person / SME obligor) (p. 56)."""
CRE_NON_CF_OTHER_OBLIGOR_FLOOR_RW: Final[float] = 0.60
"""Art 124H(3)(a): max(60%, min(counterparty RW, Art 124I RW)) for other obligors (p. 57)."""

RRE_CF_DEPENDENT_TABLE_6B: Final[tuple[tuple[float, float], ...]] = (
    (0.50, 0.30),
    (0.60, 0.35),
    (0.70, 0.40),
    (0.80, 0.50),
    (0.90, 0.60),
    (1.00, 0.75),
    (float("inf"), 1.05),
)
"""Art 124G(1) Table 6B: (upper LTV bound inclusive, RW) -- LTV <= 50% 30%; 50-60% 35%;
60-70% 40%; 70-80% 50%; 80-90% 60%; 90-100% 75%; > 100% 105% (p. 56)."""
RRE_CF_JUNIOR_MULTIPLIER: Final[float] = 1.25
"""Art 124G(2): x 1.25 where senior charges are not held by the institution and LTV > 50% (p.
56)."""
RRE_CF_JUNIOR_LTV_THRESHOLD: Final[float] = 0.50
"""Art 124G(2): 'if the LTV is more than 50%' (p. 56)."""

CRE_CF_DEPENDENT_TABLE: Final[tuple[tuple[float, float], ...]] = (
    (0.80, 1.00),
    (float("inf"), 1.10),
)
"""Art 124I(1)-(2): LTV <= 80% 100%; LTV > 80% 110% (p. 57)."""
CRE_CF_DEPENDENT_JUNIOR_TABLE: Final[tuple[tuple[float, float], ...]] = (
    (0.60, 1.00),
    (0.80, 1.25),
    (float("inf"), 1.375),
)
"""Art 124I(3): senior charges not held -- LTV <= 60% 100%; 60-80% 125%; > 80% 137.5% (p. 57)."""

OTHER_RE_CF_DEPENDENT_RW: Final[float] = 1.50
"""Art 124J(1): other (non-regulatory) RE materially dependent on cash flows, 150% (p. 57)."""
OTHER_CRE_NON_CF_FLOOR_RW: Final[float] = 0.60
"""Art 124J(3): other CRE not CF-dependent, max(60%, counterparty RW) (p. 57)."""

ADC_RW: Final[float] = 1.50
"""Art 124K(1): ADC exposures 150% (p. 58)."""
ADC_RESIDENTIAL_QUALIFYING_RW: Final[float] = 1.00
"""Art 124K(2): residential ADC with prudent underwriting and pre-sales/pre-leases or
substantial borrower equity at risk, 100% (p. 58)."""

RE_COUNTERPARTY_NATURAL_PERSON_RW: Final[float] = 0.75
"""Art 124L(1)(a): natural person(s) not an SME, 75% (p. 58)."""
RE_COUNTERPARTY_RETAIL_SME_RW: Final[float] = 0.75
"""Art 124L(1)(b): SME meeting the retail conditions if Art 123(2) disapplied, 75% (p. 58)."""
RE_COUNTERPARTY_OTHER_SME_RW: Final[float] = 0.85
"""Art 124L(1)(c): other SME, 85% (p. 58)."""
RE_COUNTERPARTY_SOCIAL_HOUSING_FLOOR_RW: Final[float] = 0.75
"""Art 124L(1)(d): social housing / housing co-operative, max(75%, unsecured RW) (p. 58)."""

PROPERTY_REVALUATION_DECLINE_TRIGGER: Final[float] = 0.10
"""Art 124D(5)(b): updated valuation if market-driven decrease > 10% (p. 52)."""
PROPERTY_REVALUATION_LARGE_LOAN_GBP_M: Final[float] = 2.6
"""Art 124D(5)(c): loan > GBP 2.6 million or 5% of own funds -> revalue after 3 years (p. 52)."""
PROPERTY_REVALUATION_LARGE_LOAN_OWN_FUNDS_SHARE: Final[float] = 0.05
"""Art 124D(5)(c) (p. 52)."""
PROPERTY_REVALUATION_LARGE_LOAN_YEARS: Final[int] = 3
"""Art 124D(5)(c) (p. 52)."""
PROPERTY_REVALUATION_MAX_YEARS: Final[int] = 5
"""Art 124D(5)(d): five years since the last qualifying valuation (p. 52)."""
SELF_BUILD_VALUATION_HAIRCUT: Final[float] = 0.8
"""Art 124D(9)(b)/(10): most recent (updated) valuation multiplied by 0.8 (p. 53)."""
THREE_PROPERTY_LIMIT: Final[int] = 3
"""Art 124E(2)-(3): no more than three qualifying properties (p. 54)."""

# -------------------------------------------------------------------------
# Articles 127-129 -- default, high risk, covered bonds (p. 59-62)
# -------------------------------------------------------------------------
DEFAULTED_LOW_PROVISION_RW: Final[float] = 1.50
"""Art 127(1)(a): specific CRAs < 20% of outstanding, 150% (p. 59)."""
DEFAULTED_HIGH_PROVISION_RW: Final[float] = 1.00
"""Art 127(1)(b): specific CRAs >= 20% of outstanding, 100% (p. 59)."""
DEFAULTED_PROVISION_THRESHOLD: Final[float] = 0.20
"""Art 127(1): the 20% specific credit risk adjustment test (p. 59)."""
DEFAULTED_RRE_NON_CF_RW: Final[float] = 1.00
"""Art 127(3): defaulted RRE not materially dependent on cash flows, 100% (p. 59)."""
HIGH_RISK_RW: Final[float] = 1.50
"""Art 128(1): exposures associated with particularly high risk, 150% (p. 59)."""

COVERED_BOND_RATED_TABLE_7: Final[Mapping[int, float]] = _cqs_table(
    (0.10, 0.20, 0.20, 0.50, 0.50, 1.00)
)
"""Art 129(4) Table 7 (p. 61)."""
COVERED_BOND_UNRATED_MAP: Final[Mapping[float, float]] = MappingProxyType(
    {0.20: 0.10, 0.30: 0.15, 0.40: 0.20, 0.50: 0.25, 0.75: 0.35, 1.00: 0.50, 1.50: 1.00}
)
"""Art 129(5)(a)-(d): issuer senior unsecured RW -> covered bond RW (p. 61-62)."""

# -------------------------------------------------------------------------
# Articles 132-134 -- CIUs, equity, subordinated debt, other items (p. 62-69)
# -------------------------------------------------------------------------
CIU_FALLBACK_RW: Final[float] = 12.50
"""Art 132(2): fall-back approach 1,250% (p. 62)."""
CIU_THIRD_PARTY_FACTOR: Final[float] = 1.2
"""Art 132(4): third-party calculation multiplied by 1.2 (p. 63)."""

EQUITY_RW: Final[float] = 2.50
"""Art 133(3): equity exposures 250% (p. 68)."""
EQUITY_HIGHER_RISK_RW: Final[float] = 4.00
"""Art 133(4): higher risk equity exposures 400% (p. 68)."""
EQUITY_SIGNIFICANT_FI_THRESHOLD_RW: Final[float] = 2.50
"""Art 133(6)(c) -> Own Funds (CRR) Part Art 48(4): 250% for amounts below the threshold (p. 68)."""
SUBORDINATED_DEBT_RW: Final[float] = 1.50
"""Art 133(5): subordinated debt / own funds instruments not equity exposures, 150% (p. 68)."""
HIGHER_RISK_EQUITY_MAX_BUSINESS_AGE_YEARS: Final[float] = 5.0
"""Glossary 'higher risk equity exposure': unlisted and business existed < five years (p. 5)."""

EQUITY_TRANSITIONAL_RW: Final[Mapping[int, float]] = MappingProxyType(
    {2027: 1.60, 2028: 1.90, 2029: 2.20}
)
"""Credit Risk: General Provisions (CRR) Part rule 4.2(1)-(3): non-higher-risk equity
160% / 190% / 220% for 2027 / 2028 / 2029 (p. 20). Applies to institutions without IRB
permission on 31 December 2026 (rule 4.1)."""
EQUITY_HIGHER_RISK_TRANSITIONAL_RW: Final[Mapping[int, float]] = MappingProxyType(
    {2027: 2.20, 2028: 2.80, 2029: 3.40}
)
"""Credit Risk: General Provisions (CRR) Part rule 4.3(1)-(3): higher risk equity
220% / 280% / 340% for 2027 / 2028 / 2029 (p. 21)."""

OTHER_TANGIBLE_ASSETS_RW: Final[float] = 1.00
"""Art 134(1) (p. 68)."""
OTHER_PREPAYMENTS_RW: Final[float] = 1.00
"""Art 134(2) (p. 68)."""
CASH_IN_COLLECTION_RW: Final[float] = 0.20
"""Art 134(3): cash items in the process of collection 20% (p. 68)."""
CASH_RW: Final[float] = 0.00
"""Art 134(3): cash in hand and equivalent cash items 0% (p. 68)."""
GOLD_BULLION_RW: Final[float] = 0.00
"""Art 134(4): gold bullion in own vaults / allocated, backed by bullion liabilities, 0% (p. 68)."""
RESIDUAL_RW: Final[float] = 1.00
"""Art 113(5): exposures with no calculation provided, 100% (p. 35)."""
NTH_TO_DEFAULT_RW_CAP: Final[float] = 12.50
"""Art 134(6): nth-to-default basket aggregation capped at 1,250% (p. 68)."""

SUPPORT_FACTOR: Final[float] = 1.0
"""SME supporting factor and infrastructure supporting factor (CRR Arts 501, 501a): no
Pillar 1 support factor appears anywhere in the instrument, and PS1/26 para 1.16 states that
the 'lending adjustments will ensure that the removal of existing Pillar 1 support factors
does not cause an increase in overall capital requirements'. The SME and infrastructure
lending adjustments are Pillar 2A (PS7/25), outside this instrument, so the Pillar 1 factor
is 1.0. # TODO: VERIFY -- size of the Pillar 2A SME/infrastructure lending adjustments
(PS7/25 / Pillar 2A statement of policy), not modelled here."""

# =========================================================================
#  Article 111 Table A1 -- conversion factors (p. 30-32)
# =========================================================================
CCF_FULL_RISK: Final[float] = 1.00
"""Table A1 row (1): credit-substitute guarantees, credit derivatives, acceptances,
endorsements, credit-substitute standby LCs; row (2): commitments with certain drawdown --
recourse transactions, outright forward purchases, repos, forward deposits, unpaid portion of
partly-paid shares (p. 30-31). Row (2) shares the 100% cell of row (1) in the PDF layout; this
reading is confirmed by row (5) ('not subject to a conversion factor of 10%, 50% or 100%')."""
CCF_OTHER_ISSUED_NON_CREDIT_SUBSTITUTE: Final[float] = 0.50
"""Table A1 row (3): other issued OBS items not having the character of credit substitutes (p.
31)."""
CCF_NIF_RUF_UK_MORTGAGE_COMMITMENT: Final[float] = 0.50
"""Table A1 row (4): NIFs/RUFs and UK residential mortgage commitments not at 10%/100% (p. 31)."""
CCF_OTHER_COMMITMENT: Final[float] = 0.40
"""Table A1 row (5): any other commitment not at 10%, 50% or 100% (p. 31)."""
CCF_TRADE_AND_PERFORMANCE: Final[float] = 0.20
"""Table A1 row (6): documentary credits and other self-liquidating transactions; warranties,
tender bonds, performance bonds, advance payment and retention guarantees and guarantees not
having the character of credit substitutes; non-credit-substitute standby LCs; shipping
guarantees, customs and tax bonds (p. 31)."""
CCF_UNCONDITIONALLY_CANCELLABLE: Final[float] = 0.10
"""Table A1 row (7): unconditionally cancellable commitments / automatic cancellation on
deterioration; retail credit lines cancellable to the extent consumer law allows (p. 32)."""
CCF_CRM_EXPOSURE_BASIS: Final[float] = 1.00
"""CRM Part Art 223(4)(a) / 235(1)(a)(i): off-balance sheet items at 100% of value when
measuring E for collateral and guarantee purposes (p. 201, 213)."""

# =========================================================================
#  Credit Risk Mitigation (CRR) Part -- Articles 223-239 (p. 200-219)
# =========================================================================
LIQUIDATION_PERIODS: Final[tuple[int, int, int]] = (20, 10, 5)
"""Art 224(1) Tables 1-4 columns: 20-, 10- and 5-day liquidation periods (p. 203-204)."""
LIQUIDATION_PERIOD_SECURED_LENDING: Final[int] = 20
"""Art 224(2)(a): secured lending transactions, 20 business days (p. 204)."""
LIQUIDATION_PERIOD_REPO: Final[int] = 5
"""Art 224(2)(b): repo / securities lending or borrowing, five business days (p. 205)."""
LIQUIDATION_PERIOD_CAPITAL_MARKET: Final[int] = 10
"""Art 224(2)(c): other capital market-driven transactions, 10 business days (p. 205)."""


def _hc(h20: float, h10: float, h5: float) -> Mapping[int, float]:
    """Freeze one haircut row keyed by liquidation period (helper; values are percentages / 100)."""
    return MappingProxyType({20: h20 / 100.0, 10: h10 / 100.0, 5: h5 / 100.0})


SUPERVISORY_HAIRCUTS: Final[Mapping[str, Mapping[int, float]]] = MappingProxyType(
    {
        # Table 1 -- rated debt securities; issuers in Art 197(1)(b)
        # (central governments / central banks)
        "SOV_CQS1_LE1Y": _hc(0.707, 0.5, 0.354),
        "SOV_CQS1_1_3Y": _hc(2.828, 2, 1.414),
        "SOV_CQS1_3_5Y": _hc(2.828, 2, 1.414),
        "SOV_CQS1_5_10Y": _hc(5.657, 4, 2.828),
        "SOV_CQS1_GT10Y": _hc(5.657, 4, 2.828),
        "SOV_CQS23_LE1Y": _hc(1.414, 1, 0.707),
        "SOV_CQS23_1_3Y": _hc(4.243, 3, 2.121),
        "SOV_CQS23_3_5Y": _hc(4.243, 3, 2.121),
        "SOV_CQS23_5_10Y": _hc(8.485, 6, 4.243),
        "SOV_CQS23_GT10Y": _hc(8.485, 6, 4.243),
        "SOV_CQS4_ALL": _hc(21.213, 15, 10.607),
        # Table 1 -- issuers in Art 197(1)(c)-(d) (other issuers: institutions, corporates, ...)
        "OTHER_CQS1_LE1Y": _hc(1.414, 1, 0.707),
        "OTHER_CQS1_1_3Y": _hc(4.243, 3, 2.121),
        "OTHER_CQS1_3_5Y": _hc(5.657, 4, 2.828),
        "OTHER_CQS1_5_10Y": _hc(8.485, 6, 4.243),
        "OTHER_CQS1_GT10Y": _hc(16.971, 12, 8.485),
        "OTHER_CQS23_LE1Y": _hc(2.828, 2, 1.414),
        "OTHER_CQS23_1_3Y": _hc(5.657, 4, 2.828),
        "OTHER_CQS23_3_5Y": _hc(8.485, 6, 4.243),
        "OTHER_CQS23_5_10Y": _hc(16.971, 12, 8.485),
        "OTHER_CQS23_GT10Y": _hc(28.284, 20, 14.142),
        # Table 1 -- securitisation positions meeting Art 197(1)(h)
        "SEC_CQS1_LE1Y": _hc(2.828, 2, 1.414),
        "SEC_CQS1_1_3Y": _hc(11.314, 8, 5.657),
        "SEC_CQS1_3_5Y": _hc(11.314, 8, 5.657),
        "SEC_CQS1_5_10Y": _hc(22.627, 16, 11.314),
        "SEC_CQS1_GT10Y": _hc(22.627, 16, 11.314),
        "SEC_CQS23_LE1Y": _hc(5.657, 4, 2.828),
        "SEC_CQS23_1_3Y": _hc(16.971, 12, 8.485),
        "SEC_CQS23_3_5Y": _hc(16.971, 12, 8.485),
        "SEC_CQS23_5_10Y": _hc(33.941, 24, 16.971),
        "SEC_CQS23_GT10Y": _hc(33.941, 24, 16.971),
        # Table 2 -- short-term credit assessments
        "SOV_ST_CQS1": _hc(0.707, 0.5, 0.354),
        "SOV_ST_CQS23": _hc(1.414, 1, 0.707),
        "OTHER_ST_CQS1": _hc(1.414, 1, 0.707),
        "OTHER_ST_CQS23": _hc(2.828, 2, 1.414),
        "SEC_ST_CQS1": _hc(2.828, 2, 1.414),
        "SEC_ST_CQS23": _hc(5.657, 4, 2.828),
        # Table 3 -- other collateral or exposure types
        "MAIN_INDEX_EQUITY": _hc(28.284, 20, 14.142),
        "OTHER_LISTED_EQUITY": _hc(42.426, 30, 21.213),
        "CASH": _hc(0, 0, 0),
        "GOLD": _hc(28.284, 20, 14.142),
    }
)
"""Art 224(1) Tables 1-3 (p. 203-204). Key = '<issuer>_<CQS>_<residual maturity>' where
issuer SOV = Art 197(1)(b), OTHER = Art 197(1)(c)-(d), SEC = securitisation per 197(1)(h).
CQS 4 is available only for sovereign issuers ('N/A' for the other columns). Art 224(6):
unrated institution debt meeting Art 197(4) uses the CQS 2-3 'OTHER' haircut. Art 224(4):
non-eligible securities lent/sold under SFTs use OTHER_LISTED_EQUITY. 'CASH' is 'cash and
cash assimilated instruments issued by the institution'."""

FX_MISMATCH_HAIRCUT: Final[Mapping[int, float]] = _hc(11.314, 8, 5.657)
"""Art 224(1) Table 4: volatility adjustment for currency mismatch (p. 204)."""

MATURITY_MISMATCH_T_STAR: Final[float] = 0.25
"""Art 239(2)-(3): t* = 0.25 (p. 218-219)."""
MATURITY_MISMATCH_T_CAP_YEARS: Final[float] = 5.0
"""Art 239(2)-(3) / 238(1): T capped at five years (p. 218)."""
MATURITY_MISMATCH_MIN_RESIDUAL_YEARS: Final[float] = 0.25
"""Art 237(1): protection with residual maturity < three months not eligible under mismatch (p.
217)."""
MATURITY_MISMATCH_MIN_ORIGINAL_YEARS: Final[float] = 1.0
"""Art 237(2)(a): original maturity of protection < one year not eligible under mismatch (p.
217)."""
CD_NO_RESTRUCTURING_HAIRCUT: Final[float] = 0.40
"""Art 233(2)(a): credit derivative without restructuring credit event, value reduced by 40%;
Art 233(2)(b) caps the value at 60% of exposure value (p. 212-213)."""

# =========================================================================
#  Required Level of Own Funds (CRR) Part -- Article 92 (p. 12-15)
# =========================================================================
CET1_MINIMUM: Final[float] = 0.045
"""Art 92(1)(a): CET1 capital ratio 4.5% (p. 12)."""
TIER1_MINIMUM: Final[float] = 0.06
"""Art 92(1)(b): Tier 1 capital ratio 6% (p. 12)."""
TOTAL_CAPITAL_MINIMUM: Final[float] = 0.08
"""Art 92(1)(c): total capital ratio 8% (p. 12)."""
OWN_FUNDS_TO_RWA_MULTIPLIER: Final[float] = 12.5
"""Art 92(4)(b): own funds requirements for points (b)-(e) multiplied by 12.5 (p. 15)."""

OUTPUT_FLOOR_FACTOR: Final[float] = 0.725
"""Art 92(2A)(a): x = 72.5% (p. 13)."""
OUTPUT_FLOOR_TRANSITIONAL: Final[Mapping[int, float]] = MappingProxyType(
    {2027: 0.60, 2028: 0.65, 2029: 0.70}
)
"""Art 92(5)(a)-(c): an institution 'may apply' x = 60% (2027), 65% (2028), 70% (2029) (p. 15)."""
OUTPUT_FLOOR_FIRST_YEAR: Final[int] = 2027
"""Instrument commencement F: all Annexes come into force on 1 January 2027 (p. 2)."""
OUTPUT_FLOOR_GCRA_CAP: Final[float] = 0.0125
"""Art 92(2A)(a) 'GCRA': general credit risk adjustments of up to 1.25% of the RWEA
calculated under paragraph 3A (p. 13)."""

# =========================================================================
#  Operational Risk Part (p. 427-431)
# =========================================================================
ILDC_IEA_CAP: Final[float] = 0.0225
"""Rule 5.3 table: interest component Min[Abs(II - IE); 2.25% x IEA] (p. 429)."""
BIC_BUCKETS_GBP_M: Final[tuple[tuple[float, float], ...]] = (
    (880.0, 0.12),
    (26_000.0, 0.15),
    (float("inf"), 0.18),
)
"""Rule 5.8 table: BI <= GBP 0.88bn 12%; 0.88bn < BI <= 26bn 15%; > 26bn 18% (p. 430).
Upper bounds are in GBP millions."""
ILM: Final[float] = 1.0
"""Rule 5.9: 'The Internal Loss Multiplier is equal to one.' (p. 430)."""
OPRISK_LOSS_THRESHOLD_GBP_M: Final[float] = 0.02
"""Rule 7.1(4): minimum loss-event threshold GBP 20,000 (p. 431)."""
OPRISK_LOSS_OBSERVATION_YEARS: Final[int] = 10
"""Rule 7.1(2): 10-year observation period (exceptionally >= 5 years) (p. 431)."""
OPRISK_LOSS_MIN_OBSERVATION_YEARS: Final[int] = 5
"""Rule 7.1(2) (p. 431)."""
BI_AVERAGING_YEARS: Final[int] = 3
"""Rule 5.4(1)-(2): three-year averages; absolute values of net items year by year first (p.
429)."""

# =========================================================================
#  Counterparty Credit Risk (CRR) Part -- Article 274 (p. 455-456)
# =========================================================================
SACCR_ALPHA: Final[float] = 1.4
"""Art 274(2): alpha = 1.4 (p. 456)."""
SACCR_ALPHA_NFC_PENSION: Final[float] = 1.0
"""Art 274(2): alpha = 1 for a non-financial counterparty, a pension scheme arrangement or an
entity established to compensate pension scheme members on default (p. 456)."""
SACCR_ALPHA_ADDON_TRANSITIONAL: Final[Mapping[int, float]] = MappingProxyType(
    {2027: 0.60, 2028: 0.40, 2029: 0.20}
)
"""Art 274(2A)(1): share of the 'alpha add-on' (EV at alpha 1.4 less EV at alpha 1, as at
1 January 2027) added for pre-2027 trades with CVA Part 7.1(1)(a)/(b) counterparties:
60% / 40% / 20% (p. 456)."""
SACCR_MULTIPLIER_FLOOR: Final[float] = 0.05
"""CCR Part Art 278(3): 'Floor_m = 5%'; y = 2 * (1 - Floor_m) * AggAddOn. The multiplier and z
formulas are images on the Rulebook page; their form min{1; Floor_m + (1 - Floor_m) *
exp(z / y)} for z < 0 (1 for z >= 0), z = CMV - NICA / CMV - VM - NICA / sum(CMV_i - NICA_i),
is taken from CRR Art 278(3), to which the rule corresponds (same Floor_m, y and NICA_i
definitions)."""
SACCR_SUPERVISORY_DISCOUNT_RATE: Final[float] = 0.05
"""CCR Part Art 279b(1)(a): 'R = the supervisory discount rate; R = 5%'."""
SACCR_MF_MARGINED_SCALAR: Final[float] = 1.5
"""CCR Part Art 279c(1)(b): MF = (3/2) * sqrt(MPOR / OneBusinessYear) (image on the Rulebook
page; form transcribed from CRR Art 279c(1)(b))."""
SACCR_MF_UNMARGINED_MIN_DAYS: Final[int] = 10
SACCR_BUSINESS_DAYS_PER_YEAR: Final[int] = 250
"""CCR Part Art 279c(1)(a): MF = sqrt(min{max{M; 10/OneBusinessYear}; 1}) (form transcribed from
CRR Art 279c(1)(a)). OneBusinessYear (business days in a year) is taken as 250 here --
TODO: VERIFY the firm's business-day convention."""
SACCR_CLIENT_CM_MPOR_DAYS: Final[int] = 5
"""CCR Part Art 279c(1)(b): client / clearing member MPOR minimum replaced by five business
days."""

SACCR_SUPERVISORY_VOLATILITY: Final[Mapping[str, float]] = MappingProxyType(
    {
        "INTEREST_RATE": 0.50,
        "FX": 0.15,
        "CREDIT_SINGLE": 1.00,
        "CREDIT_MULTI": 0.80,
        "EQUITY_SINGLE": 1.20,
        "EQUITY_MULTI": 0.75,
        "COMMODITY_ELECTRICITY": 1.50,
        "COMMODITY_OTHER": 0.70,
        "OTHER": 1.50,
    }
)
"""CCR Part Art 279a(1)(a) Table 1: supervisory volatilities."""
SACCR_HEDGING_SET_EPSILON: Final[Mapping[str, float]] = MappingProxyType(
    {"STANDARD": 1.0, "VOLATILITY": 5.0, "BASIS": 0.5}
)
"""CCR Part Art 280: epsilon = 1 (Art 277a(1)); 5 (Art 277a(2)(a) volatility / correlation
hedging sets); 0.5 (Art 277a(2)(b) basis hedging sets)."""
SACCR_SF_INTEREST_RATE: Final[float] = 0.005
"""CCR Part Art 280a(2): SF_IR = 0.5%."""
SACCR_IR_MATURITY_BUCKETS: Final[tuple[float, float]] = (1.0, 5.0)
"""CCR Part Art 280a(3) Table 2: bucket 1 (0, 1], bucket 2 (1, 5], bucket 3 > 5 years."""
SACCR_SF_FX: Final[float] = 0.04
"""CCR Part Art 280b(2): SF_FX = 4%."""
SACCR_SF_CREDIT_SINGLE_NAME: Final[Mapping[int, float]] = _cqs_table(
    (0.0038, 0.0042, 0.0054, 0.0106, 0.016, 0.06)
)
"""CCR Part Art 280c(5) Table 3: CQS 1-6 -> 0.38% / 0.42% / 0.54% / 1.06% / 1.6% / 6.0%."""
SACCR_SF_CREDIT_UNRATED_SA: Final[float] = 0.0054
SACCR_SF_CREDIT_UNRATED_HIGH_RISK: Final[float] = 0.016
"""CCR Part Art 280c(5)(a)(ii): SA firm, unrated issuer 0.54%; 1.6% where Art 128 (high risk)
applies to the issuer."""
SACCR_SF_CREDIT_INDEX: Final[Mapping[str, float]] = MappingProxyType(
    {"IG": 0.0038, "NON_IG": 0.0106}
)
"""CCR Part Art 280c(5) Table 4: quoted indices -- investment grade 0.38%, non-IG 1.06%."""
SACCR_RHO_SINGLE: Final[float] = 0.50
SACCR_RHO_MULTI: Final[float] = 0.80
"""CCR Part Art 280c(3) / 280d(3): correlation 50% single-name, 80% multi-name entities."""
SACCR_SF_EQUITY: Final[Mapping[str, float]] = MappingProxyType({"SINGLE": 0.32, "MULTI": 0.20})
"""CCR Part Art 280d(4): 32% single-name, 20% multi-name equity reference entities."""
SACCR_SF_COMMODITY: Final[Mapping[str, float]] = MappingProxyType(
    {"ELECTRICITY": 0.40, "OTHER": 0.18}
)
"""CCR Part Art 280e(5): 18% (excluding electricity); 40% electricity."""
SACCR_RHO_COMMODITY: Final[float] = 0.40
"""CCR Part Art 280e(4): commodity correlation 40%."""
SACCR_SF_OTHER: Final[float] = 0.08
"""CCR Part Art 280f(2): SF_Other = 8%."""

# =========================================================================
#  Credit Valuation Adjustment Risk Part (p. 394-425)
# =========================================================================
BA_CVA_DS: Final[float] = 0.65
"""Rule 4.2 / 4.5: DS_BA-CVA = 0.65 (p. 399, 401)."""
BA_CVA_RHO: Final[float] = 0.50
"""Rule 4.2 / 4.6: rho = 50% (p. 399, 402)."""
BA_CVA_BETA: Final[float] = 0.25
"""Rule 4.5: beta = 0.25 (p. 401)."""
BA_CVA_DISCOUNT_RATE: Final[float] = 0.05
"""Rule 4.3 DF_NS = (1 - exp(-0.05 M)) / (0.05 M) for non-IMM firms (p. 400)."""
BA_CVA_INDEX_RW_SCALAR: Final[float] = 0.7
"""Rule 4.8(1)-(2): index hedge RW x 0.7 (p. 403)."""

BA_CVA_RISK_WEIGHTS: Final[Mapping[str, Mapping[str, float]]] = MappingProxyType(
    {
        "SOVEREIGN": MappingProxyType({"IG": 0.005, "HY_NR": 0.020}),
        "LOCAL_GOVERNMENT": MappingProxyType({"IG": 0.010, "HY_NR": 0.040}),
        "FINANCIAL": MappingProxyType({"IG": 0.050, "HY_NR": 0.120}),
        "PENSION_FUND": MappingProxyType({"IG": 0.035, "HY_NR": 0.085}),
        "BASIC_MATERIALS": MappingProxyType({"IG": 0.030, "HY_NR": 0.070}),
        "CONSUMER": MappingProxyType({"IG": 0.030, "HY_NR": 0.085}),
        "TECHNOLOGY": MappingProxyType({"IG": 0.020, "HY_NR": 0.055}),
        "HEALTHCARE": MappingProxyType({"IG": 0.015, "HY_NR": 0.050}),
        "OTHER": MappingProxyType({"IG": 0.050, "HY_NR": 0.120}),
    }
)
"""Rule 4.4 table RW_C (p. 401): sovereigns incl. central banks and MDBs; local government,
government-backed non-financials, education and public administration; financials incl.
government-backed financials *excluding pension funds*; pension funds; basic materials,
energy, industrials, agriculture, manufacturing, mining and quarrying; consumer goods and
services, transportation and storage, administrative and support service activities;
technology, telecommunications; health care, utilities, professional and technical
activities; other sector."""

BA_CVA_HEDGE_CORRELATION: Final[Mapping[str, float]] = MappingProxyType(
    {
        "DIRECT": 1.00,
        "LEGALLY_RELATED": 0.80,
        "SECTOR_REGION": 0.50,
    }
)
"""Rule 4.10 table r_hc (p. 403)."""

CVA_ALTERNATIVE_APPROACH_NOTIONAL_GBP_M: Final[float] = 88_000.0
"""Rule 6.1(1): non-centrally cleared derivatives notional < GBP 88 billion (p. 422)."""
CVA_ALTERNATIVE_APPROACH_CCR_SHARE: Final[float] = 1.00
"""Rule 6.2: own funds requirement = 100% of the CCR own funds requirement (p. 422)."""

CVA_TRANSITIONAL_WEIGHTING_CAP: Final[Mapping[int, float]] = MappingProxyType(
    {2027: 0.70, 2028: 0.80, 2029: 0.90}
)
"""Rule 7.2 table: transitional weighting cap omega_t 70% / 80% / 90% (p. 424)."""
CVA_TRANSITIONAL_ELAPSED_T: Final[Mapping[int, int]] = MappingProxyType({2027: 2, 2028: 3, 2029: 4})
"""Rule 7.2: t = 2 on 1 January 2027, 3 on 1 January 2028, 4 on 1 January 2029 (p. 424)."""
CVA_TRANSITIONAL_OMEGA: Final[float] = 0.5
"""Rule 7.2: omega = 0.5 (p. 424)."""
CVA_TRANSITIONAL_HORIZON_YEARS: Final[float] = 5.0
"""Rule 7.2: time discount factor (5 - t) / 5 (p. 424)."""
CVA_TRANSITIONAL_END_YEAR: Final[int] = 2030
"""Rule 7.1: 'until 1 January 2030' (p. 423)."""

# =========================================================================
#  Capital Buffers Part (PRA Rulebook web text, in force 1 January 2027)
# =========================================================================
CAPITAL_CONSERVATION_BUFFER: Final[float] = 0.025
"""Capital Buffers Part rule 2.1: 'a capital conservation buffer of common equity tier 1 capital
equal to 2.5% of its total risk exposure amount'."""
COMBINED_BUFFER_COMPONENTS: Final[tuple[str, ...]] = (
    "capital conservation buffer",
    "countercyclical capital buffer",
    "G-SII buffer (if any)",
    "O-SII buffer (if any)",
)
"""Capital Buffers Part rule 1.2 'combined buffer' = the *sum* of (a)-(d): the G-SII and O-SII
buffers stack, and there is no systemic risk buffer component."""
MDA_QUARTILE_FACTORS: Final[tuple[float, float, float, float]] = (0.0, 0.2, 0.4, 0.6)
"""Capital Buffers Part rule 4.3(6)(a)-(d): MDA factor by quartile of the combined buffer
(first/lowest quartile 0; second 0.2; third 0.4; fourth/highest 0.6); quartile bounds per rule
4.3(7): combined buffer / 4 x (Q_n - 1) and combined buffer / 4 x Q_n."""
CCYB_MAXIMUM_PLACEHOLDER: Final[float] = 0.025
"""# TODO: VERIFY -- Capital Buffers Part rule 3.1 makes the CCyB the exposure-weighted average of
rates set by the FPC (UK and third countries, rule 3.1(4)-(8)); no maximum is stated in the
Part. 2.5% is the BCBS RBC30 upper bound used only as a sanity cap."""
SYSTEMIC_BUFFER_MAXIMUM_PLACEHOLDER: Final[float] = 0.035
"""# TODO: VERIFY -- the G-SII and O-SII buffer rates are firm-specific (set outside the Capital
Buffers Part); the caller passes them. 3.5% (BCBS RBC40 top bucket) is used only as a cap on
each rate."""

# =========================================================================
#  Leverage ratio requirement -- NOT in the supplied texts
# =========================================================================
LEVERAGE_RATIO_MINIMUM: Final[float] = 0.03
"""# TODO: VERIFY -- the minimum leverage ratio requirement is in the Leverage Ratio - Capital
Requirements and Buffers Part 3.1 (cross-referenced by SA Part Art 121(1A)(c), p. 42); neither
the instrument nor the supplied Leverage Ratio (CRR) Part (which defines only the exposure
measure, Arts 429-429g) contains it; placeholder = BCBS LEV20 'a 3% leverage ratio minimum'."""
LEVERAGE_BUFFER_SHARE_OF_SYSTEMIC: Final[float] = 0.50
"""# TODO: VERIFY -- the additional leverage ratio buffer is in Leverage Ratio - Capital
Requirements and Buffers Part 4A.1 (cross-referenced, p. 42), not supplied; placeholder = BCBS
LEV40.2 'set at 50% of a G-SIB's higher loss-absorbency' requirement."""
COUNTERCYCLICAL_LEVERAGE_BUFFER_SHARE: Final[float] = 0.0
"""# TODO: VERIFY -- countercyclical leverage ratio buffer (Leverage Ratio - Capital
Requirements and Buffers Part 4.1, cross-referenced p. 42) is not supplied; not applied (0)."""
