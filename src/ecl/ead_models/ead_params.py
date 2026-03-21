"""EAD Model Parameters — CCF and off-balance sheet conversion factors.

References:
    - BCBS d424 CRE32.22-32.26: IRB EAD
    - ERBA NPR pp. 130-140: SA-CR CCF values
    - ASC 326-20-30-6: CECL contractual term
"""

from __future__ import annotations


# =========================================================================
#  Supervisory Credit Conversion Factors (SA-CR)
#  Reference: ERBA NPR pp. 130-140, 12 CFR 217.33
# =========================================================================

SA_CCF: dict[str, float] = {
    "unconditionally_cancellable": 0.10,
    "commitments_lt_1y": 0.20,
    "commitments_gte_1y": 0.40,
    "transaction_related_contingencies": 0.20,
    "trade_related_contingencies": 0.20,
    "note_issuance_facilities": 0.50,
    "direct_credit_substitutes": 1.00,
    "repo_style_transactions": 1.00,
    "asset_sale_with_recourse": 1.00,
    "forward_asset_purchases": 1.00,
    "securities_lending": 1.00,
    "other_commitments": 0.40,
}
"""Standardized Approach CCFs per ERBA NPR / 12 CFR 217.33.

CCF converts off-balance sheet notional to credit-equivalent exposure.
EAD = drawn + CCF * undrawn for revolving facilities.
"""


# =========================================================================
#  IRB Foundation CCF Benchmarks
#  Reference: BCBS d424 CRE32.23
# =========================================================================

IRB_CCF: dict[str, float] = {
    "unconditionally_cancellable": 0.40,
    "commitments": 0.75,
    "direct_credit_substitutes": 1.00,
    "nif_ruf": 0.75,
    "short_term_self_liquidating": 0.20,
    "other_off_balance_sheet": 0.75,
}
"""Foundation IRB CCFs per BCBS d424 CRE32.23.

Used as benchmarks for internal CCF model calibration.
"""


# =========================================================================
#  Prepayment and Drawdown Parameters
# =========================================================================

DEFAULT_PREPAYMENT_RATES: dict[str, float] = {
    "corporate_revolving": 0.05,
    "corporate_term": 0.10,
    "retail_mortgage": 0.08,
    "retail_revolving": 0.15,
    "sme": 0.07,
    "cre": 0.06,
}
"""Annual prepayment rates by product type.

Used to adjust EAD for expected contractual cash flows.
Reference: ASC 326-20-30-6.
"""

DEFAULT_DRAWDOWN_RATES: dict[str, float] = {
    "corporate_revolving": 0.60,
    "retail_credit_card": 0.70,
    "retail_heloc": 0.50,
    "sme_revolving": 0.55,
    "construction": 0.80,
}
"""Expected drawdown rates for undrawn commitments (at default).

Represents the fraction of undrawn commitment expected to be drawn
by the time of default. Calibrated from internal default data.
Reference: BCBS d350 §6.2.
"""
