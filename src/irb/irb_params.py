"""IRB Regulatory Parameters per BCBS d424 (Basel III: Finalising Post-Crisis Reforms).

Contains all supervisory parameters for the Internal Ratings-Based (IRB) approach
to credit risk capital requirements. This module is for COMPARISON PURPOSES ONLY
as the US Basel III Endgame 2026 re-proposal removes IRB for most exposures.

All parameters are sourced from BCBS d424 (December 2017) with specific paragraph
references. No magic numbers -- every value is cited.

References:
    - BCBS d424: "Basel III: Finalising Post-Crisis Reforms" (Dec 2017)
    - BCBS d424, CRE30-CRE36: IRB approach
    - BCBS d424, CRE31: Risk-weighted assets for corporate, sovereign, bank exposures
    - BCBS d424, CRE32: Risk-weighted assets for retail exposures
    - BCBS d424, CRE33: Rules for purchased receivables

Note:
    The US Federal Reserve's 2026 re-proposal eliminates IRB for most exposure
    classes. This module exists solely for:
    1. Comparing SA vs IRB RWA to quantify the output floor impact
    2. International regulatory analysis (non-US jurisdictions retain IRB)
    3. Historical comparison with pre-2026 US capital requirements
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple

from pydantic import BaseModel, Field


# =========================================================================
#  IRB Exposure Class Enumeration
# =========================================================================

class IRBExposureClass(Enum):
    """IRB exposure classes per BCBS d424 CRE30.3.

    The IRB framework classifies banking book exposures into broad
    classes with different risk characteristics and capital formulas.
    """
    CORPORATE = "CORPORATE"
    """Corporate exposures including SME corporates."""

    CORPORATE_SME = "CORPORATE_SME"
    """SME corporate exposures with revenue-based correlation adjustment."""

    BANK = "BANK"
    """Exposures to banks and other financial institutions."""

    SOVEREIGN = "SOVEREIGN"
    """Exposures to sovereign entities and central banks."""

    RETAIL_MORTGAGE = "RETAIL_MORTGAGE"
    """Residential mortgage exposures to individuals."""

    RETAIL_QUALIFYING_REVOLVING = "RETAIL_QRE"
    """Qualifying revolving retail exposures (credit cards, overdrafts)."""

    RETAIL_OTHER = "RETAIL_OTHER"
    """Other retail exposures not classified as mortgage or QRE."""

    EQUITY = "EQUITY"
    """Equity exposures under the IRB approach."""

    SPECIALIZED_LENDING = "SPECIALIZED_LENDING"
    """Project finance, object finance, commodities finance, IPRE, HVCRE."""


class IRBApproach(Enum):
    """IRB sub-approaches per BCBS d424 CRE30.5-30.7.

    Foundation IRB (F-IRB): Bank estimates PD; supervisory LGD, EAD, M.
    Advanced IRB (A-IRB): Bank estimates PD, LGD, EAD, M.
    """
    FOUNDATION = "F-IRB"
    """Foundation IRB: bank-estimated PD, supervisory LGD/EAD."""

    ADVANCED = "A-IRB"
    """Advanced IRB: bank-estimated PD, LGD, EAD, and M."""


class SpecializedLendingCategory(Enum):
    """Supervisory slotting categories for specialized lending.

    Per BCBS d424 CRE33, banks unable to meet IRB requirements for
    specialized lending may use supervisory slotting criteria.
    """
    STRONG = "STRONG"
    GOOD = "GOOD"
    SATISFACTORY = "SATISFACTORY"
    WEAK = "WEAK"
    DEFAULT = "DEFAULT"


# =========================================================================
#  Confidence Level and Scaling Factor
# =========================================================================

CONFIDENCE_LEVEL: float = 0.999
"""Confidence level for the IRB capital formula.

Per BCBS d424 CRE31.1: The IRB risk weight functions produce capital
requirements for unexpected losses (UL) at the 99.9th percentile of the
loss distribution.
"""

SCALING_FACTOR: float = 1.06
"""IRB scaling factor applied to RWA.

Per BCBS d424 CRE31.2: A scaling factor of 1.06 is applied to the
risk-weighted asset amounts for credit risk under the IRB approach.
"""


# =========================================================================
#  Asset Correlation Parameters -- Corporate, Sovereign, Bank
# =========================================================================

CORPORATE_CORRELATION_R_MIN: float = 0.12
"""Minimum asset correlation for corporate/sovereign/bank exposures.

Per BCBS d424 CRE31.6, para 44: R = 0.12 * (1 - EXP(-50*PD)) / (1 - EXP(-50))
+ 0.24 * [1 - (1 - EXP(-50*PD)) / (1 - EXP(-50))].
The lower bound of 0.12 applies when PD approaches 100%.
"""

CORPORATE_CORRELATION_R_MAX: float = 0.24
"""Maximum asset correlation for corporate/sovereign/bank exposures.

Per BCBS d424 CRE31.6, para 44: R_max = 0.24 applies when PD approaches 0%.
"""

CORPORATE_CORRELATION_K: float = 50.0
"""Exponential decay factor for the corporate correlation function.

Per BCBS d424 CRE31.6, para 44: k = 50 in the exponential weighting
function (1 - EXP(-50 * PD)) / (1 - EXP(-50)).
"""


# =========================================================================
#  SME Corporate Correlation Adjustment
# =========================================================================

SME_REVENUE_THRESHOLD_LOW: float = 5.0
"""Lower revenue threshold for SME adjustment ($M).

Per BCBS d424 CRE31.8, para 46: Revenue below EUR 5M is floored at EUR 5M
for the purpose of the firm-size correlation adjustment.
"""

SME_REVENUE_THRESHOLD_HIGH: float = 50.0
"""Upper revenue threshold for SME adjustment ($M).

Per BCBS d424 CRE31.8, para 46: The size adjustment applies to corporates
with annual sales (S) below EUR 50M.
"""

SME_CORRELATION_ADJUSTMENT_FACTOR: float = 0.04
"""Maximum firm-size correlation adjustment for SMEs.

Per BCBS d424 CRE31.8, para 46:
R_sme = R - 0.04 * (1 - (S - 5) / 45)
where S = max(5, min(annual_revenue, 50)).
The maximum reduction is 0.04 (4 percentage points) for S = 5.
"""


# =========================================================================
#  Asset Correlation Parameters -- Retail
# =========================================================================

# Residential Mortgage
RETAIL_MORTGAGE_R: float = 0.15
"""Fixed asset correlation for residential mortgage exposures.

Per BCBS d424 CRE32.5, para 48: The correlation R for residential
mortgage exposures is set at 0.15.
"""

# Qualifying Revolving Retail Exposures (QRE)
QRE_CORRELATION_R: float = 0.04
"""Fixed asset correlation for qualifying revolving retail exposures.

Per BCBS d424 CRE32.7, para 48: The correlation R for qualifying
revolving retail exposures (including credit cards) is set at 0.04.
"""

# Other Retail
OTHER_RETAIL_CORRELATION_R_MIN: float = 0.03
"""Minimum asset correlation for other retail exposures.

Per BCBS d424 CRE32.9, para 48: R = 0.03 * (1 - EXP(-35*PD)) / (1 - EXP(-35))
+ 0.16 * [1 - (1 - EXP(-35*PD)) / (1 - EXP(-35))].
"""

OTHER_RETAIL_CORRELATION_R_MAX: float = 0.16
"""Maximum asset correlation for other retail exposures.

Per BCBS d424 CRE32.9, para 48: R_max = 0.16 applies as PD -> 0.
"""

OTHER_RETAIL_CORRELATION_K: float = 35.0
"""Exponential decay factor for other retail correlation.

Per BCBS d424 CRE32.9, para 48: k = 35 in the exponential weighting.
"""


# =========================================================================
#  Maturity Adjustment Parameters
# =========================================================================

MATURITY_ADJUSTMENT_B_COEFFICIENTS: tuple[float, float] = (0.11852, -0.05478)
"""Coefficients for maturity adjustment b(PD) function.

Per BCBS d424 CRE31.6, para 44:
b(PD) = (0.11852 - 0.05478 * ln(PD))^2

The maturity adjustment accounts for the mark-to-market risk of
longer-maturity exposures.
"""

EFFECTIVE_MATURITY_MIN: float = 1.0
"""Minimum effective maturity (years) for F-IRB.

Per BCBS d424 CRE31.11, para 49: For F-IRB, a floor of 1 year applies
to effective maturity, except for certain short-term self-liquidating
trade finance transactions (which may use 0.25 years).
"""

EFFECTIVE_MATURITY_MAX: float = 5.0
"""Maximum effective maturity (years) for both F-IRB and A-IRB.

Per BCBS d424 CRE31.11, para 49: Effective maturity is capped at 5 years.
"""

EFFECTIVE_MATURITY_DEFAULT: float = 2.5
"""Default effective maturity (years) for F-IRB.

Per BCBS d424 CRE31.11, para 49: Under F-IRB, the effective maturity
is set to 2.5 years for all exposures, unless the bank uses the
explicit maturity treatment.
"""

SHORT_TERM_TRADE_FINANCE_M: float = 0.25
"""Effective maturity floor for short-term trade finance under F-IRB.

Per BCBS d424 CRE31.11: Certain repo-style transactions and
short-term self-liquidating trade finance exposures may use M = 0.25y.
"""


# =========================================================================
#  Supervisory LGD Estimates (Foundation IRB)
# =========================================================================

class SupervisoryLGD(BaseModel):
    """Supervisory LGD values for Foundation IRB per BCBS d424 CRE31.

    Under F-IRB, banks do not estimate their own LGD. Instead, these
    supervisory values are used.
    """
    senior_secured_financial: float = Field(
        default=0.45,
        description="Senior claims on banks, securities firms, insurance companies. "
                    "Per BCBS d424 CRE31.4."
    )
    senior_unsecured: float = Field(
        default=0.45,
        description="Senior unsecured claims on corporates/sovereigns. "
                    "Per BCBS d424 CRE31.4, para 43."
    )
    subordinated: float = Field(
        default=0.75,
        description="Subordinated claims. Per BCBS d424 CRE31.4, para 43."
    )

    # Collateralized LGD floors
    eligible_financial_collateral_lgd: float = Field(
        default=0.0,
        description="LGD for exposures fully secured by eligible financial "
                    "collateral. Per BCBS d424 CRE31.4."
    )
    eligible_receivables_lgd: float = Field(
        default=0.20,
        description="LGD for exposures secured by eligible receivables. "
                    "Per BCBS d424 CRE31.4."
    )
    eligible_cre_rre_lgd: float = Field(
        default=0.20,
        description="LGD for exposures secured by eligible CRE/RRE. "
                    "Per BCBS d424 CRE31.4."
    )
    other_physical_collateral_lgd: float = Field(
        default=0.25,
        description="LGD for exposures secured by other eligible physical "
                    "collateral. Per BCBS d424 CRE31.4."
    )


# Default instance for use in calculations
SUPERVISORY_LGD = SupervisoryLGD()
"""Default supervisory LGD instance with BCBS d424 CRE31.4 values."""


# =========================================================================
#  LGD Floors (A-IRB)
# =========================================================================

class LGDFloors(BaseModel):
    """Minimum LGD values under A-IRB per BCBS d424 CRE31.

    Under A-IRB, banks estimate their own LGD but must respect these
    regulatory floors. These floors were introduced in the Basel III
    finalization to address the risk of overly optimistic LGD estimates.
    """
    unsecured_corporate: float = Field(
        default=0.25,
        description="Floor LGD for unsecured corporate/bank/sovereign exposures. "
                    "Per BCBS d424 CRE31.4, para 43."
    )
    secured_financial_collateral: float = Field(
        default=0.0,
        description="Floor LGD for exposures secured by eligible financial "
                    "collateral. Per BCBS d424 CRE31.4."
    )
    secured_receivables: float = Field(
        default=0.10,
        description="Floor LGD for exposures secured by eligible receivables. "
                    "Per BCBS d424 CRE31.4."
    )
    secured_cre_rre: float = Field(
        default=0.10,
        description="Floor LGD for exposures secured by eligible CRE/RRE. "
                    "Per BCBS d424 CRE31.4."
    )
    secured_other_physical: float = Field(
        default=0.15,
        description="Floor LGD for exposures secured by other eligible physical "
                    "collateral. Per BCBS d424 CRE31.4."
    )

    # Retail LGD floors
    retail_mortgage: float = Field(
        default=0.05,
        description="Floor LGD for residential mortgage retail exposures. "
                    "Per BCBS d424 CRE32.3."
    )
    retail_qre_unsecured: float = Field(
        default=0.50,
        description="Floor LGD for unsecured qualifying revolving exposures. "
                    "Per BCBS d424 CRE32.7."
    )
    retail_qre_secured: float = Field(
        default=0.30,
        description="Floor LGD for secured qualifying revolving exposures. "
                    "Per BCBS d424 CRE32.7."
    )
    retail_other_unsecured: float = Field(
        default=0.30,
        description="Floor LGD for unsecured other retail exposures. "
                    "Per BCBS d424 CRE32.9."
    )
    retail_other_secured: float = Field(
        default=0.20,
        description="Floor LGD for secured other retail exposures. "
                    "Per BCBS d424 CRE32.9."
    )
    # TODO: VERIFY -- LGD floor for retail other secured by non-financial
    # collateral may differ from financial collateral secured.


# Default instance
LGD_FLOORS = LGDFloors()
"""Default LGD floor instance with BCBS d424 values."""


# =========================================================================
#  PD Floors
# =========================================================================

PD_FLOOR_CORPORATE: float = 0.0003
"""PD floor for corporate, bank, sovereign exposures: 0.03% (3 bps).

Per BCBS d424 CRE31.6, para 44: PD for non-defaulted exposures is
subject to a floor of 0.03%.
"""

PD_FLOOR_RETAIL_MORTGAGE: float = 0.0003
"""PD floor for residential mortgage retail exposures: 0.03%.

Per BCBS d424 CRE32.5: PD floor of 0.03% for residential mortgages.
"""

PD_FLOOR_RETAIL_QRE: float = 0.0005
"""PD floor for qualifying revolving retail exposures: 0.05%.

Per BCBS d424 CRE32.7: PD floor of 0.05% for QRE exposures.
"""

PD_FLOOR_RETAIL_OTHER: float = 0.0005
"""PD floor for other retail exposures: 0.05%.

Per BCBS d424 CRE32.9: PD floor of 0.05% for other retail.
"""

PD_DEFAULTED: float = 1.0
"""PD for defaulted exposures is 100%.

Per BCBS d424: Exposures that have defaulted are assigned PD = 100%.
"""


# =========================================================================
#  EAD Parameters (Foundation IRB)
# =========================================================================

CCF_FIRB: dict[str, float] = {
    "committed_unconditionally_cancellable": 0.10,
    "committed_maturity_le_1y": 0.40,
    "committed_maturity_gt_1y": 0.50,
    "nif_ruf": 0.50,
    "short_term_self_liquidating": 0.20,
    "unconditionally_cancellable": 0.10,
    "other_commitments": 0.40,
}
"""Credit Conversion Factors (CCF) for F-IRB off-balance-sheet exposures.

Per BCBS d424 CRE31.12-31.14: Supervisory CCFs for the Foundation
approach. Under F-IRB, banks do not estimate their own EAD for
off-balance-sheet exposures.

Note: Banks under A-IRB estimate their own CCF subject to regulatory floors.
"""


# =========================================================================
#  Supervisory Slotting Risk Weights (Specialized Lending)
# =========================================================================

SLOTTING_RISK_WEIGHTS: dict[SpecializedLendingCategory, float] = {
    SpecializedLendingCategory.STRONG: 0.70,
    SpecializedLendingCategory.GOOD: 0.90,
    SpecializedLendingCategory.SATISFACTORY: 1.15,
    SpecializedLendingCategory.WEAK: 2.50,
    SpecializedLendingCategory.DEFAULT: 0.0,
}
"""Supervisory slotting risk weights for specialized lending.

Per BCBS d424 CRE33.2: Banks that do not meet the requirements for the
estimation of PD for specialized lending exposures must map their
internal grades to these supervisory categories.

Note: Default category receives 0% RW because the EL component is fully
provisioned and deducted from capital.
"""

SLOTTING_RISK_WEIGHTS_HVCRE: dict[SpecializedLendingCategory, float] = {
    SpecializedLendingCategory.STRONG: 0.95,
    SpecializedLendingCategory.GOOD: 1.20,
    SpecializedLendingCategory.SATISFACTORY: 1.40,
    SpecializedLendingCategory.WEAK: 2.50,
    SpecializedLendingCategory.DEFAULT: 0.0,
}
"""Supervisory slotting risk weights for HVCRE specialized lending.

Per BCBS d424 CRE33.3: High-volatility commercial real estate receives
higher slotting risk weights than other specialized lending.
"""


# =========================================================================
#  Equity IRB Parameters
# =========================================================================

EQUITY_SIMPLE_RW_EXCHANGE_TRADED: float = 3.00
"""Simple risk weight for exchange-traded equity holdings: 300%.

Per BCBS d424 CRE34.3: Under the simple risk weight method for equity.
"""

EQUITY_SIMPLE_RW_OTHER: float = 4.00
"""Simple risk weight for other (non-exchange-traded) equity: 400%.

Per BCBS d424 CRE34.3: All other equity holdings receive 400%.
"""

EQUITY_SIMPLE_RW_PD_PA_MINIMUM: float = 2.00
"""Minimum risk weight under the PD/LGD approach for equities: 200%.

Per BCBS d424 CRE34: Equity exposures using the PD/LGD approach are
subject to a floor of 200%.
"""


# =========================================================================
#  Output Floor
# =========================================================================

OUTPUT_FLOOR_PERCENTAGE: float = 0.725
"""Basel III output floor: 72.5% of standardized RWA.

Per BCBS d424, para 4: The aggregate RWA under IRB must not be less than
72.5% of the RWA computed under the standardized approach.

IMPORTANT: This output floor is NOT applied in the US Basel III Endgame
2026 re-proposal. The US proposal instead eliminates IRB entirely for
most exposure classes, making the output floor moot. This parameter is
included for international comparison purposes only.
"""


# =========================================================================
#  EL Parameters
# =========================================================================

EL_PROVISION_OFFSET_CAP: float = 0.006
"""Maximum EL shortfall that can be offset by eligible provisions.

Per BCBS d424 CRE35.2: Excess eligible provisions over IRB-EL may be
included in Tier 2 capital up to 0.6% of IRB credit RWA.
"""


# =========================================================================
#  Parameter Lookup Helpers
# =========================================================================

class IRBParameterSet(NamedTuple):
    """Complete set of IRB parameters for a given exposure class.

    Bundles correlation bounds, PD floor, and maturity adjustment
    applicability for efficient lookup.
    """
    r_min: float
    r_max: float
    r_decay_k: float
    pd_floor: float
    fixed_correlation: bool
    maturity_adjustment_applies: bool


# Pre-built parameter sets for each exposure class
IRB_PARAMS: dict[IRBExposureClass, IRBParameterSet] = {
    IRBExposureClass.CORPORATE: IRBParameterSet(
        r_min=CORPORATE_CORRELATION_R_MIN,
        r_max=CORPORATE_CORRELATION_R_MAX,
        r_decay_k=CORPORATE_CORRELATION_K,
        pd_floor=PD_FLOOR_CORPORATE,
        fixed_correlation=False,
        maturity_adjustment_applies=True,
    ),
    IRBExposureClass.CORPORATE_SME: IRBParameterSet(
        r_min=CORPORATE_CORRELATION_R_MIN,
        r_max=CORPORATE_CORRELATION_R_MAX,
        r_decay_k=CORPORATE_CORRELATION_K,
        pd_floor=PD_FLOOR_CORPORATE,
        fixed_correlation=False,
        maturity_adjustment_applies=True,
    ),
    IRBExposureClass.BANK: IRBParameterSet(
        r_min=CORPORATE_CORRELATION_R_MIN,
        r_max=CORPORATE_CORRELATION_R_MAX,
        r_decay_k=CORPORATE_CORRELATION_K,
        pd_floor=PD_FLOOR_CORPORATE,
        fixed_correlation=False,
        maturity_adjustment_applies=True,
    ),
    IRBExposureClass.SOVEREIGN: IRBParameterSet(
        r_min=CORPORATE_CORRELATION_R_MIN,
        r_max=CORPORATE_CORRELATION_R_MAX,
        r_decay_k=CORPORATE_CORRELATION_K,
        pd_floor=PD_FLOOR_CORPORATE,
        fixed_correlation=False,
        maturity_adjustment_applies=True,
    ),
    IRBExposureClass.RETAIL_MORTGAGE: IRBParameterSet(
        r_min=RETAIL_MORTGAGE_R,
        r_max=RETAIL_MORTGAGE_R,
        r_decay_k=0.0,  # Not used -- fixed correlation
        pd_floor=PD_FLOOR_RETAIL_MORTGAGE,
        fixed_correlation=True,
        maturity_adjustment_applies=False,
    ),
    IRBExposureClass.RETAIL_QUALIFYING_REVOLVING: IRBParameterSet(
        r_min=QRE_CORRELATION_R,
        r_max=QRE_CORRELATION_R,
        r_decay_k=0.0,  # Not used -- fixed correlation
        pd_floor=PD_FLOOR_RETAIL_QRE,
        fixed_correlation=True,
        maturity_adjustment_applies=False,
    ),
    IRBExposureClass.RETAIL_OTHER: IRBParameterSet(
        r_min=OTHER_RETAIL_CORRELATION_R_MIN,
        r_max=OTHER_RETAIL_CORRELATION_R_MAX,
        r_decay_k=OTHER_RETAIL_CORRELATION_K,
        pd_floor=PD_FLOOR_RETAIL_OTHER,
        fixed_correlation=False,
        maturity_adjustment_applies=False,
    ),
}
"""Pre-built parameter sets indexed by IRB exposure class.

Provides efficient lookup of all parameters needed for IRB capital
calculation without repeated dictionary access.
"""
