"""FX risk regulatory parameters -- US ERBA NPR (March 2026) §__.208-§__.209.

All risk weights, correlations, and regulatory constants for the FX risk
class under the FRTB Sensitivities-Based Method, as written in the March
2026 Federal Reserve re-proposal, 12 CFR 217 Subpart F:

* §__.208(b)   -- FX risk factors: spot rate of each currency pair against
                  the reporting currency (base-currency approach with
                  approval).
* §__.209(b)(7) -- FX delta risk weight (15%), the specified-currency list
                  whose pairs may divide the risk weight by sqrt(2), and the
                  uniform 60% correlation.
* §__.209 Table 11 and the curvature paragraph -- vega risk weight 100%;
  curvature risk weight = delta risk weight, with the optional division of
  the FX curvature risk position by 1.5 for options that do not reference
  the reporting currency.

FX has NO bucket structure -- all currency-pair sensitivities are
aggregated in a single correlation matrix with uniform rho = 60%.
(BCBS d457 MAR21.21-21.22 / MAR21.87-21.88 given as cross-references only.)
"""
from __future__ import annotations

import math
import re

from src.core.enums import CorrelationScenario

# ---------------------------------------------------------------------------
# Delta risk weight -- ERBA NPR §__.209(b)(7) (BCBS MAR21.87)
# 15% for every currency pair (base value before any sqrt(2) reduction)
# ---------------------------------------------------------------------------
FX_DELTA_RW: float = 0.15

# ---------------------------------------------------------------------------
# Specified currencies -- ERBA NPR §__.209(b)(7)
# A currency pair formed from any two currencies on this list MAY have its
# delta risk weight divided by sqrt(2).  The US list is currency-based, not
# pair-based (unlike the illustrative pair list in BCBS MAR21.88 footnote).
# ---------------------------------------------------------------------------
FX_SPECIFIED_CURRENCIES: set[str] = {
    "USD", "AUD", "BRL", "CAD", "CNY", "EUR", "HKD", "INR", "JPY", "MXN",
    "NZD", "NOK", "SGD", "ZAR", "KRW", "SEK", "CHF", "TRY", "GBP",
}

# Divisor applied to the 15% risk weight for specified-currency pairs
# (ERBA NPR §__.209(b)(7): "may divide ... by the square root of 2").
FX_SPECIFIED_PAIR_RW_DIVISOR: float = math.sqrt(2)  # ~1.4142

# The sqrt(2) reduction is optional ("may").  This module-level election
# controls the default behaviour of :func:`get_fx_delta_rw`; the firm's
# documented policy election should be reflected here.  Default: apply.
APPLY_FX_SPECIFIED_PAIR_REDUCTION: bool = True

# ---------------------------------------------------------------------------
# Intra-bucket correlation -- ERBA NPR §__.209(b)(7) (BCBS MAR21.88)
# FX has a single "bucket" -- all pairs correlated at rho = 60%
# ---------------------------------------------------------------------------
FX_INTRA_CORR: float = 0.60

# ---------------------------------------------------------------------------
# Vega parameters -- ERBA NPR §__.209 Table 11 (BCBS MAR21.92-93)
# ---------------------------------------------------------------------------
FX_VEGA_RW: float = 1.0  # 100%
FX_VEGA_LIQUIDITY_HORIZON: int = 40  # Business days (informational; RW capped at 100%)
FX_VEGA_ALPHA: float = 0.01  # alpha = 1% in exp(-alpha * |T_k - T_l| / min(T_k, T_l))

# ---------------------------------------------------------------------------
# Curvature parameters -- ERBA NPR §__.209 (curvature paragraph)
#   * Curvature risk weight for FX = delta risk weight (relative shift of
#     the spot rate), see get_fx_curvature_rw().
#   * The curvature risk position (CVR) of an FX option that does NOT
#     reference the reporting currency MAY be divided by 1.5.  This is an
#     election; default is OFF.  (BCBS MAR21.99 cross-reference.)
#   * Intra-bucket curvature correlation = delta correlation squared;
#     no inter-bucket step (single bucket).
# ---------------------------------------------------------------------------
FX_CURVATURE_NON_REPORTING_CCY_DIVISOR: float = 1.5
APPLY_FX_CURVATURE_NON_REPORTING_CCY_DIVISOR: bool = False

_PAIR_SPLIT_RE = re.compile(r"[^A-Za-z]+")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def parse_currency_pair(currency_pair: str) -> tuple[str, str] | None:
    """Split a currency-pair identifier into its two ISO 4217 codes.

    Accepts ``"EURUSD"``, ``"EUR/USD"``, ``"EUR-USD"``, ``"EUR_USD"`` and
    ``"eur usd"`` (case-insensitive).  Anything that does not resolve to
    exactly two three-letter codes returns ``None``.

    Args:
        currency_pair: Currency pair identifier.

    Returns:
        ``(base, quote)`` upper-cased, or ``None`` when unparseable.
    """
    if not currency_pair:
        return None
    parts = [p for p in _PAIR_SPLIT_RE.split(currency_pair.strip()) if p]
    if len(parts) == 1 and len(parts[0]) == 6:
        parts = [parts[0][:3], parts[0][3:]]
    if len(parts) != 2 or any(len(p) != 3 for p in parts):
        return None
    return parts[0].upper(), parts[1].upper()


def is_specified_fx_pair(currency_pair: str) -> bool:
    """Return whether BOTH legs of *currency_pair* are specified currencies.

    ERBA NPR §__.209(b)(7): the sqrt(2) reduction is available for any
    currency pair formed from two currencies on the specified list.

    Args:
        currency_pair: Currency pair identifier (see
            :func:`parse_currency_pair` for accepted formats).

    Returns:
        ``True`` when both currencies are on :data:`FX_SPECIFIED_CURRENCIES`.
    """
    parsed = parse_currency_pair(currency_pair)
    if parsed is None:
        return False
    base, quote = parsed
    return base in FX_SPECIFIED_CURRENCIES and quote in FX_SPECIFIED_CURRENCIES


def get_fx_delta_rw(
    currency_pair: str | None = None,
    apply_reduction: bool | None = None,
) -> float:
    """Get the FX delta risk weight for a currency pair.

    ERBA NPR §__.209(b)(7): 15% for every pair; a pair whose two currencies
    are both on the specified list may use ``15% / sqrt(2)`` (= 10.607%).
    Example: EUR/USD -> 0.15/sqrt(2); USD/RUB -> 0.15.

    Args:
        currency_pair: Currency pair identifier (e.g. ``"EURUSD"`` or
            ``"EUR/USD"``).  ``None`` or an unparseable value returns the
            unreduced 15%.
        apply_reduction: Override the module-level election
            :data:`APPLY_FX_SPECIFIED_PAIR_REDUCTION`.  ``None`` uses the
            module default.

    Returns:
        Risk weight as a decimal.
    """
    if apply_reduction is None:
        apply_reduction = APPLY_FX_SPECIFIED_PAIR_REDUCTION
    if apply_reduction and currency_pair is not None and is_specified_fx_pair(currency_pair):
        return FX_DELTA_RW / FX_SPECIFIED_PAIR_RW_DIVISOR
    return FX_DELTA_RW


def get_fx_curvature_rw(
    currency_pair: str | None = None,
    apply_reduction: bool | None = None,
) -> float:
    """Get the FX curvature shock size (relative spot shift) for a pair.

    ERBA NPR §__.209 (curvature): for FX the curvature risk weight equals
    the delta risk weight, including the sqrt(2) reduction where elected.

    Args:
        currency_pair: Currency pair identifier.
        apply_reduction: See :func:`get_fx_delta_rw`.

    Returns:
        Curvature shock as a decimal.
    """
    return get_fx_delta_rw(currency_pair, apply_reduction)


def references_reporting_currency(currency_pair: str, reporting_currency: str) -> bool:
    """Return whether *currency_pair* has *reporting_currency* as one leg.

    Used for the optional division of the FX curvature risk position by 1.5
    (ERBA NPR §__.209 curvature paragraph), which is available only for
    options that do NOT reference the reporting currency.  An unparseable
    pair is conservatively treated as referencing the reporting currency.

    Args:
        currency_pair: Currency pair identifier.
        reporting_currency: ISO 4217 reporting currency (e.g. ``"USD"``).

    Returns:
        ``True`` if the reporting currency is one leg of the pair (or the
        pair cannot be parsed).
    """
    parsed = parse_currency_pair(currency_pair)
    if parsed is None:
        return True
    return reporting_currency.upper() in parsed


def apply_correlation_scenario(
    rho: float,
    scenario: CorrelationScenario,
    is_inter_bucket: bool = False,
) -> float:
    """Apply the correlation scenario adjustment per ERBA NPR §__.206(c).

    +---------+--------------------------------------+
    | Scenario| Adjusted correlation                 |
    +=========+======================================+
    | LOW     | max(2*rho - 1, 0.75*rho)             |
    +---------+--------------------------------------+
    | MEDIUM  | rho (no change)                      |
    +---------+--------------------------------------+
    | HIGH    | min(1.0, 1.25*rho)                   |
    +---------+--------------------------------------+

    (BCBS MAR21.6.)

    Args:
        rho: Base correlation value.
        scenario: One of LOW / MEDIUM / HIGH.
        is_inter_bucket: Whether this is an inter-bucket correlation.

    Returns:
        Scenario-adjusted correlation.
    """
    if scenario == CorrelationScenario.MEDIUM:
        return rho
    elif scenario == CorrelationScenario.HIGH:
        return min(1.0, 1.25 * rho)
    else:  # LOW
        return max(2 * rho - 1, 0.75 * rho)


def build_fx_correlation_matrix(
    n: int,
    scenario: CorrelationScenario,
) -> "numpy.ndarray":
    """Build the correlation matrix for FX delta sensitivities.

    ERBA NPR §__.209(b)(7): a single bucket with uniform correlation
    rho = 60% between all currency pairs, adjusted by the scenario.

    Args:
        n: Number of FX sensitivities.
        scenario: Correlation scenario (LOW / MEDIUM / HIGH).

    Returns:
        numpy ndarray of shape (n, n).
    """
    import numpy as np

    rho = apply_correlation_scenario(FX_INTRA_CORR, scenario)

    corr = np.full((n, n), rho, dtype=np.float64)
    np.fill_diagonal(corr, 1.0)
    return corr
