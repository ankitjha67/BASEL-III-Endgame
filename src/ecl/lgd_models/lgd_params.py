"""LGD Model Parameters — Regulatory and calibration constants for LGD estimation.

References:
    - BCBS d424 CRE32.14-32.16: IRB supervisory LGD
    - BCBS d350 §5.1-5.3: LGD for ECL
    - Internal Model Documentation §4: LGD Calibration
"""

from __future__ import annotations


# =========================================================================
#  Supervisory LGD Values (IRB Foundation approach benchmarks)
#  Reference: BCBS d424 CRE32.14
# =========================================================================

SUPERVISORY_LGD: dict[str, float] = {
    "senior_unsecured": 0.45,
    "subordinated": 0.75,
    "senior_secured_financial_collateral": 0.0,
    "senior_secured_receivables": 0.20,
    "senior_secured_cre_rre": 0.20,
    "senior_secured_other_physical": 0.25,
}
"""Supervisory LGD values per BCBS d424 CRE32.14.

Used as benchmarks for internal LGD model calibration.
"""


# =========================================================================
#  Collateral Haircuts — per BCBS d424 CRE22.48-72
# =========================================================================

COLLATERAL_HAIRCUTS: dict[str, float] = {
    "cash": 0.00,
    "government_bonds_aaa_aa": 0.005,
    "government_bonds_a_bbb": 0.02,
    "corporate_bonds_aaa_aa": 0.02,
    "corporate_bonds_a_bbb": 0.06,
    "equities_main_index": 0.15,
    "equities_other": 0.25,
    "residential_property": 0.30,
    "commercial_property": 0.40,
    "receivables": 0.20,
    "other_physical": 0.40,
}
"""Supervisory collateral haircuts for secured LGD estimation.

Reference: BCBS d424 CRE22.48-72, ERBA NPR pp. 145-155.
"""


# =========================================================================
#  Downturn LGD Parameters
#  Reference: BCBS d350 §5.2, EBA GL/2019/03
# =========================================================================

DOWNTURN_LGD_ADD_ON: dict[str, float] = {
    "senior_unsecured": 0.08,
    "subordinated": 0.10,
    "secured_cre": 0.12,
    "secured_rre": 0.05,
    "secured_financial": 0.03,
    "secured_other": 0.10,
}
"""Downturn LGD add-ons above normal-period LGD.

Calibrated from peak-loss periods (2008-2010 GFC, 2020 COVID).
Reference: BCBS d350 §5.2.
"""

LGD_FLOOR: float = 0.10
"""Minimum LGD for secured exposures per BCBS d424 CRE32.15."""

LGD_CAP: float = 1.00
"""Maximum LGD. Reference: BCBS d350 §5.1."""


# =========================================================================
#  Cure Rate Parameters
#  Reference: BCBS d350 §5.3, Internal Model Doc §4.3
# =========================================================================

DEFAULT_CURE_RATES: dict[str, float] = {
    "corporate_ig": 0.15,
    "corporate_hy": 0.08,
    "sme": 0.05,
    "retail_mortgage": 0.25,
    "retail_revolving": 0.12,
    "retail_other": 0.10,
    "cre": 0.06,
    "sovereign": 0.20,
}
"""Probability that a defaulted exposure cures (returns to performing).

Calibrated from internal workout data (2010-2024 observation window).
Cure reduces effective LGD: Effective LGD = (1 - cure_rate) * workout_LGD.

Reference: BCBS d350 §5.3, Internal Model Doc §4.3.
"""


# =========================================================================
#  Workout Recovery Timing
# =========================================================================

AVERAGE_WORKOUT_PERIODS: dict[str, float] = {
    "corporate": 2.0,
    "sme": 1.5,
    "retail_mortgage": 3.0,
    "retail_revolving": 1.0,
    "cre": 2.5,
    "sovereign": 4.0,
}
"""Average workout period in years by asset class.

Used to discount recovery cash flows in workout LGD estimation.
Reference: Internal Model Doc §4.4.
"""

WORKOUT_DISCOUNT_RATE: float = 0.05
"""Discount rate for workout recovery cash flows (5% per annum).

Per IFRS 9 §B5.5.28, recovery cash flows are discounted at the
original effective interest rate. 5% is a representative average.
"""
