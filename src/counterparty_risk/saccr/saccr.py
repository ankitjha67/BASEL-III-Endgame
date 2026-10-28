"""SA-CCR — Standardized Approach for Counterparty Credit Risk.

Calculates Exposure at Default (EAD) for OTC derivatives, securities
financing transactions, and long-settlement transactions per CRE52.

Key formula
-----------
    EAD = alpha * (RC + PFE)

Where:
    alpha   = 1.4 (financial), 1.0 (commercial end-users, 2026 rule)
    RC      = Replacement Cost
    PFE     = Potential Future Exposure = multiplier * AddOn_aggregate

References
----------
- CRE52: Standardised approach to counterparty credit risk
- CRE52.30-52.38: Replacement cost
- CRE52.39-52.72: PFE / add-on calculation
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field, field_validator, model_validator

from typing import Callable

from src.counterparty_risk.saccr.saccr_params import (
    ALPHA_FINANCIAL,
    ALPHA_NON_FINANCIAL,
    CREDIT_ASSET_CLASSES,
    PFE_FLOOR,
    SACCR_ASSET_CLASS_PARAMS,
    SUPERVISORY_DISCOUNT_RATE,
    SUPERVISORY_DURATION_FLOOR,
    SACCRAssetClass,
    AssetClassParams,
    IRMaturityBucket,
    ir_maturity_bucket,
    mpor_scaling_factor,
    unmargined_maturity_factor,
)

MaturityFactorFn = Callable[["SACCRTrade"], float]


def _unit_maturity_factor(trade: "SACCRTrade") -> float:
    """Maturity factor of 1.0 (used when callers aggregate without context)."""
    return 1.0

logger = logging.getLogger(__name__)


# ============================================================================
#  Pydantic Models
# ============================================================================


class SACCRTrade(BaseModel):
    """A single derivative trade within a netting set.

    Attributes
    ----------
    trade_id : str
        Unique identifier for the trade.
    asset_class : str
        SA-CCR asset class key (e.g. "IR", "FX", "CREDIT_IG").
    notional : float
        Trade notional in reporting currency.
    mtm_value : float
        Current mark-to-market value (positive = in-the-money).
    start_years : float
        Start date of the contract in years from today (0 for spot).
    end_years : float
        End date of the contract in years from today.
    is_long : bool
        True if the bank has a long position in the primary risk factor.
    underlying : str
        Reference entity / index / currency pair / commodity name.
    netting_set : str
        Netting set identifier this trade belongs to.
    delta_override : float | None
        Optional explicit supervisory delta.  When None, delta is
        inferred from is_long (+1 / -1).
    """

    trade_id: str
    asset_class: str
    notional: float = Field(gt=0)
    mtm_value: float = 0.0
    start_years: float = Field(ge=0, default=0.0)
    end_years: float = Field(gt=0)
    is_long: bool = True
    underlying: str = ""
    netting_set: str = ""
    delta_override: Optional[float] = Field(default=None, ge=-1.0, le=1.0)

    @field_validator("asset_class")
    @classmethod
    def _validate_asset_class(cls, v: str) -> str:
        v = v.upper()
        valid = {ac.value for ac in SACCRAssetClass}
        if v not in valid:
            raise ValueError(
                f"Invalid asset class '{v}'. Must be one of {sorted(valid)}"
            )
        return v

    @model_validator(mode="after")
    def _check_dates(self) -> "SACCRTrade":
        if self.end_years <= self.start_years:
            raise ValueError(
                f"end_years ({self.end_years}) must be > start_years "
                f"({self.start_years}) for trade {self.trade_id}"
            )
        return self

    @property
    def saccr_asset_class(self) -> SACCRAssetClass:
        """Return the parsed SACCRAssetClass enum."""
        return SACCRAssetClass(self.asset_class)

    @property
    def supervisory_delta(self) -> float:
        """Supervisory delta per CRE52.43.

        +1 for long, -1 for short (linear trades).  Can be overridden
        via ``delta_override`` for options.
        """
        if self.delta_override is not None:
            return self.delta_override
        return 1.0 if self.is_long else -1.0


class SACCRNettingSet(BaseModel):
    """A netting set of derivative trades for SA-CCR.

    Attributes
    ----------
    netting_set_id : str
        Unique identifier for the netting set.
    trades : list[SACCRTrade]
        Trades within this netting set.
    collateral : float
        Net collateral held / posted (C).  Positive = bank holds collateral.
    is_margined : bool
        Whether the netting set has a margin agreement.
    threshold : float
        Threshold (TH) under the margin agreement.
    mta : float
        Minimum transfer amount.
    mpor : int
        Margin period of risk in business days.
    is_financial : bool
        True for financial counterparties (alpha = 1.4).
    nica : float
        Net Independent Collateral Amount.
    """

    netting_set_id: str
    trades: list[SACCRTrade] = Field(min_length=1)
    collateral: float = 0.0
    is_margined: bool = False
    threshold: float = 0.0
    mta: float = 0.0
    mpor: int = Field(default=10, gt=0)
    is_financial: bool = True
    nica: float = 0.0

    @model_validator(mode="after")
    def _validate_trade_netting(self) -> "SACCRNettingSet":
        """Warn if trades reference different netting sets."""
        ns_ids = {t.netting_set for t in self.trades if t.netting_set}
        if ns_ids and len(ns_ids) > 1:
            logger.warning(
                "Netting set %s contains trades referencing multiple "
                "netting set IDs: %s",
                self.netting_set_id,
                ns_ids,
            )
        return self

    @property
    def portfolio_mtm(self) -> float:
        """Sum of MTM values across all trades (V)."""
        return sum(t.mtm_value for t in self.trades)

    @property
    def alpha(self) -> float:
        """Alpha multiplier."""
        return ALPHA_FINANCIAL if self.is_financial else ALPHA_NON_FINANCIAL


class SACCRResult(BaseModel):
    """Result of SA-CCR EAD calculation for a netting set.

    Attributes
    ----------
    ead : float
        Exposure at Default = alpha * (RC + PFE).
    replacement_cost : float
        Replacement cost (RC).
    pfe : float
        Potential Future Exposure.
    multiplier : float
        PFE multiplier.
    addon_aggregate : float
        Aggregate add-on before multiplier.
    alpha : float
        Alpha multiplier applied.
    addon_by_asset_class : dict[str, float]
        Add-on broken down by asset class.
    trade_level_details : list[dict]
        Per-trade adjusted notional and delta details.
    """

    ead: float
    replacement_cost: float
    pfe: float
    multiplier: float
    addon_aggregate: float
    alpha: float
    addon_by_asset_class: dict[str, float] = Field(default_factory=dict)
    trade_level_details: list[dict] = Field(default_factory=list)


# ============================================================================
#  Core Calculation Functions
# ============================================================================


def supervisory_duration(start_years: float, end_years: float) -> float:
    """Compute supervisory duration SD per ERBA NPR § __.114(i)(2)(i)(A).

    .. math::

        SD = \\max\\left(\\frac{e^{-0.05 S} - e^{-0.05 E}}{0.05},\\; 0.04\\right)

    where S and E are measured in years (business days / 250) and the
    floor of 0.04 corresponds to ten business days.

    Parameters
    ----------
    start_years : float
        Start date in years from today (zero if already started).
    end_years : float
        End date in years from today.

    Returns
    -------
    float
        Supervisory duration, floored at 0.04.
    """
    sd = (
        math.exp(-SUPERVISORY_DISCOUNT_RATE * start_years)
        - math.exp(-SUPERVISORY_DISCOUNT_RATE * end_years)
    ) / SUPERVISORY_DISCOUNT_RATE
    return max(sd, SUPERVISORY_DURATION_FLOOR)


def adjusted_notional(trade: SACCRTrade) -> float:
    """Compute the adjusted (effective) notional for a trade.

    d_i = notional * SD_i

    For IR and Credit trades, the adjusted notional uses supervisory
    duration.  For other asset classes, it is simply the notional.

    Parameters
    ----------
    trade : SACCRTrade

    Returns
    -------
    float
        Adjusted notional d_i.
    """
    ac = trade.saccr_asset_class

    if ac == SACCRAssetClass.IR or ac in CREDIT_ASSET_CLASSES:
        sd = supervisory_duration(trade.start_years, trade.end_years)
        return trade.notional * sd

    # FX, Equity, Commodity — use notional directly
    return trade.notional


def trade_level_addon(
    trade: SACCRTrade,
    maturity_factor: float = 1.0,
) -> float:
    """Compute the trade-level effective notional per ERBA NPR § __.114(i)(1).

    adjusted derivative contract amount = delta_i * d_i * MF_i

    (The supervisory factor is applied at the hedging-set level.)  This is
    the *signed* contribution; the absolute add-on is obtained after
    aggregation within hedging sets.

    Parameters
    ----------
    trade : SACCRTrade
    maturity_factor : float
        MF_i per § __.114(i)(4): sqrt(1.5 * MPOR / 250) for margined
        contracts, sqrt(min(M, 250) / 250) for unmargined contracts.

    Returns
    -------
    float
        delta_i * d_i * MF_i (can be negative for short trades).
    """
    return trade.supervisory_delta * adjusted_notional(trade) * maturity_factor


# ============================================================================
#  Hedging-set aggregation
# ============================================================================


def _aggregate_ir_addon(
    trades: list[SACCRTrade],
    mf_fn: MaturityFactorFn = _unit_maturity_factor,
) -> float:
    """Aggregate add-on for Interest Rate asset class.

    IR uses three maturity buckets (end date < 1y, 1-5y, > 5y).  Within
    each bucket, effective notionals are summed.  Across buckets, partial
    offsetting is allowed per ERBA NPR § __.114(h)(1) Formula 1.

    Parameters
    ----------
    trades : list[SACCRTrade]
        All IR trades in the netting set.
    mf_fn : callable
        Returns the maturity factor MF_i for a trade.

    Returns
    -------
    float
        IR add-on.
    """
    params = SACCR_ASSET_CLASS_PARAMS[SACCRAssetClass.IR]
    sf = params.supervisory_factor

    # Group by currency (hedging set) then by maturity bucket
    by_currency: dict[str, dict[IRMaturityBucket, float]] = defaultdict(
        lambda: defaultdict(float)
    )

    for t in trades:
        ccy = t.underlying.upper() if t.underlying else "USD"
        bucket = ir_maturity_bucket(t.end_years)
        by_currency[ccy][bucket] += trade_level_addon(t, mf_fn(t))

    total_addon = 0.0

    for ccy, buckets in by_currency.items():
        d1 = buckets.get(IRMaturityBucket.BUCKET_1, 0.0)
        d2 = buckets.get(IRMaturityBucket.BUCKET_2, 0.0)
        d3 = buckets.get(IRMaturityBucket.BUCKET_3, 0.0)

        # CRE52.50: effective notional for the hedging set
        # D = sqrt(D1^2 + D2^2 + D3^2 + 1.4*D1*D2 + 1.4*D2*D3 + 0.6*D1*D3)
        variance = (
            d1**2
            + d2**2
            + d3**2
            + 1.4 * d1 * d2
            + 1.4 * d2 * d3
            + 0.6 * d1 * d3
        )
        effective_notional = math.sqrt(max(variance, 0.0))
        total_addon += sf * effective_notional

    return total_addon


def _aggregate_single_entity_addon(
    trades: list[SACCRTrade],
    asset_class: SACCRAssetClass,
    mf_fn: MaturityFactorFn = _unit_maturity_factor,
) -> float:
    """Aggregate add-on for equity and commodity hedging sets.

    Per ERBA NPR § __.114(h)(3)-(4), within each hedging set the systematic
    and idiosyncratic components are separated using the supervisory
    correlation rho:

    AddOn = SF * sqrt( (rho * sum(EN_k))^2 + (1-rho^2) * sum(EN_k^2) )

    Parameters
    ----------
    trades : list[SACCRTrade]
        Trades of the given asset class.
    asset_class : SACCRAssetClass
    mf_fn : callable
        Returns the maturity factor MF_i for a trade.

    Returns
    -------
    float
        Asset-class level add-on.
    """
    params = SACCR_ASSET_CLASS_PARAMS[asset_class]
    sf = params.supervisory_factor
    rho = params.correlation

    # Group by underlying (hedging set / entity)
    by_entity: dict[str, float] = defaultdict(float)
    for t in trades:
        entity = t.underlying if t.underlying else "__UNKNOWN__"
        by_entity[entity] += trade_level_addon(t, mf_fn(t))

    entity_notionals = list(by_entity.values())

    # Systematic component: rho * sum(EN_k)
    systematic_sum = sum(entity_notionals)
    systematic = (rho * systematic_sum) ** 2

    # Idiosyncratic component: (1 - rho^2) * sum(EN_k^2)
    idiosyncratic = (1.0 - rho**2) * sum(en**2 for en in entity_notionals)

    effective_notional = math.sqrt(max(systematic + idiosyncratic, 0.0))
    return sf * effective_notional


def _aggregate_credit_addon(
    trades: list[SACCRTrade],
    mf_fn: MaturityFactorFn = _unit_maturity_factor,
) -> float:
    """Aggregate add-on for the single credit hedging set per § __.114(h)(3).

    All credit derivative contracts in a netting set form ONE hedging set
    (§ __.114(b) hedging set (iii)).  Each reference entity k carries its
    own supervisory factor SF_k and correlation rho_k from Table 2 to
    § __.114 (single-name IG/spec/sub-spec rho 50%; index rho 80%):

    AddOn = sqrt( (sum_k rho_k * AddOn_k)^2 + sum_k (1 - rho_k^2) * AddOn_k^2 ),
    AddOn_k = SF_k * sum_{i in k} delta_i * d_i * MF_i

    Parameters
    ----------
    trades : list[SACCRTrade]
        All credit trades in the netting set.
    mf_fn : callable
        Returns the maturity factor MF_i for a trade.

    Returns
    -------
    float
        Credit hedging-set add-on.
    """
    by_entity: dict[str, float] = defaultdict(float)
    rho_by_entity: dict[str, float] = {}

    for t in trades:
        ac = t.saccr_asset_class
        params = SACCR_ASSET_CLASS_PARAMS[ac]
        entity = t.underlying if t.underlying else "__UNKNOWN__"
        by_entity[entity] += params.supervisory_factor * trade_level_addon(t, mf_fn(t))
        rho_by_entity[entity] = params.correlation

    systematic = sum(rho_by_entity[k] * v for k, v in by_entity.items()) ** 2
    idiosyncratic = sum(
        (1.0 - rho_by_entity[k] ** 2) * v**2 for k, v in by_entity.items()
    )
    return math.sqrt(max(systematic + idiosyncratic, 0.0))


def _aggregate_fx_addon(
    trades: list[SACCRTrade],
    mf_fn: MaturityFactorFn = _unit_maturity_factor,
) -> float:
    """Aggregate add-on for FX asset class per ERBA NPR § __.114(h)(2).

    FX hedging sets are per currency pair; the hedging set amount is the
    absolute value of the sum of adjusted derivative contract amounts.

    Parameters
    ----------
    trades : list[SACCRTrade]
    mf_fn : callable
        Returns the maturity factor MF_i for a trade.

    Returns
    -------
    float
    """
    params = SACCR_ASSET_CLASS_PARAMS[SACCRAssetClass.FX]
    sf = params.supervisory_factor

    # Group by currency pair (hedging set)
    by_pair: dict[str, float] = defaultdict(float)
    for t in trades:
        pair = t.underlying.upper() if t.underlying else "UNKNOWN"
        by_pair[pair] += trade_level_addon(t, mf_fn(t))

    total = 0.0
    for pair_en in by_pair.values():
        total += sf * abs(pair_en)

    return total


# ============================================================================
#  SA-CCR Calculator
# ============================================================================


class SACCRCalculator:
    """SA-CCR calculator for a netting set.

    Computes EAD = alpha * (RC + PFE) following the full SA-CCR methodology.

    Usage
    -----
    >>> calc = SACCRCalculator()
    >>> ns = SACCRNettingSet(netting_set_id="NS1", trades=[...])
    >>> result = calc.calculate(ns)
    >>> result.ead
    1234567.89
    """

    # ------------------------------------------------------------------
    #  Replacement Cost
    # ------------------------------------------------------------------

    def _replacement_cost(self, ns: SACCRNettingSet) -> float:
        """Compute replacement cost RC.

        For unmargined netting sets:
            RC = max(V - C, 0)

        For margined netting sets:
            RC = max(V - C, TH + MTA - NICA, 0)

        Parameters
        ----------
        ns : SACCRNettingSet

        Returns
        -------
        float
            Replacement cost.
        """
        v = ns.portfolio_mtm
        c = ns.collateral

        if not ns.is_margined:
            rc = max(v - c, 0.0)
        else:
            rc = max(v - c, ns.threshold + ns.mta - ns.nica, 0.0)

        logger.debug(
            "RC for %s: V=%.2f, C=%.2f, margined=%s -> RC=%.2f",
            ns.netting_set_id,
            v,
            c,
            ns.is_margined,
            rc,
        )
        return rc

    # ------------------------------------------------------------------
    #  Add-on Aggregate
    # ------------------------------------------------------------------

    def _addon_by_asset_class(
        self, ns: SACCRNettingSet
    ) -> dict[str, float]:
        """Compute add-on for each asset class present in the netting set.

        Returns
        -------
        dict[str, float]
            Mapping of asset-class name to its add-on value.
        """
        # Maturity factor per § __.114(i)(4): margined sets use the MPOR
        # based factor; unmargined contracts use remaining maturity.
        if ns.is_margined:
            margined_mf = mpor_scaling_factor(ns.mpor)

            def mf_fn(t: SACCRTrade) -> float:
                return margined_mf
        else:

            def mf_fn(t: SACCRTrade) -> float:
                return unmargined_maturity_factor(t.end_years)

        # Group trades by asset class
        trades_by_ac: dict[SACCRAssetClass, list[SACCRTrade]] = defaultdict(list)
        for t in ns.trades:
            trades_by_ac[SACCRAssetClass(t.asset_class)].append(t)

        addons: dict[str, float] = {}

        # All credit categories form a single hedging set (§ __.114(b)).
        credit_trades = [
            t for ac, ts in trades_by_ac.items() if ac in CREDIT_ASSET_CLASSES for t in ts
        ]
        if credit_trades:
            addons["CREDIT"] = _aggregate_credit_addon(credit_trades, mf_fn)
            logger.debug("AddOn[CREDIT] = %.2f", addons["CREDIT"])

        for ac, ac_trades in trades_by_ac.items():
            if ac in CREDIT_ASSET_CLASSES:
                continue
            if ac == SACCRAssetClass.IR:
                addon = _aggregate_ir_addon(ac_trades, mf_fn)
            elif ac == SACCRAssetClass.FX:
                addon = _aggregate_fx_addon(ac_trades, mf_fn)
            elif ac in (
                SACCRAssetClass.EQUITY_SINGLE,
                SACCRAssetClass.EQUITY_INDEX,
                SACCRAssetClass.COMMODITY_ELEC,
                SACCRAssetClass.COMMODITY_OTHER,
            ):
                addon = _aggregate_single_entity_addon(ac_trades, ac, mf_fn)
            else:
                logger.warning("Unhandled asset class %s, skipping.", ac)
                addon = 0.0

            addons[ac.value] = addon
            logger.debug("AddOn[%s] = %.2f", ac.value, addon)

        return addons

    def _addon_aggregate(self, ns: SACCRNettingSet) -> float:
        """Total add-on across all asset classes.

        Add-ons are summed across asset classes (no cross-class netting).

        Parameters
        ----------
        ns : SACCRNettingSet

        Returns
        -------
        float
        """
        addons = self._addon_by_asset_class(ns)
        # Maturity factors (margined MPOR-based or unmargined) are applied
        # at trade level inside _addon_by_asset_class per § __.114(i)(4).
        return sum(addons.values())

    # ------------------------------------------------------------------
    #  PFE Multiplier
    # ------------------------------------------------------------------

    def _multiplier(
        self, ns: SACCRNettingSet, addon_aggregate: float
    ) -> float:
        """Compute the PFE multiplier per CRE52.41.

        multiplier = min(1, Floor + (1 - Floor) * exp(V / (2*(1-Floor)*AddOn)))

        The multiplier reduces PFE when the netting set has negative MTM
        or excess collateral.

        Parameters
        ----------
        ns : SACCRNettingSet
        addon_aggregate : float

        Returns
        -------
        float
            Multiplier in [Floor, 1.0].
        """
        v = ns.portfolio_mtm
        c = ns.collateral

        if addon_aggregate <= 0.0:
            return 1.0

        numerator = v - c
        denominator = 2.0 * (1.0 - PFE_FLOOR) * addon_aggregate

        if denominator <= 0.0:
            return 1.0

        exponent = numerator / denominator
        # Clamp exponent to avoid overflow
        exponent = max(min(exponent, 50.0), -50.0)

        raw = PFE_FLOOR + (1.0 - PFE_FLOOR) * math.exp(exponent)
        multiplier = min(raw, 1.0)

        logger.debug(
            "PFE multiplier for %s: V-C=%.2f, addon=%.2f -> mult=%.4f",
            ns.netting_set_id,
            numerator,
            addon_aggregate,
            multiplier,
        )
        return multiplier

    # ------------------------------------------------------------------
    #  Trade-level details
    # ------------------------------------------------------------------

    def _trade_details(self, ns: SACCRNettingSet) -> list[dict]:
        """Produce per-trade calculation details.

        Returns
        -------
        list[dict]
            One dict per trade with intermediate values.
        """
        details: list[dict] = []
        for t in ns.trades:
            adj_not = adjusted_notional(t)
            sd = supervisory_duration(t.start_years, t.end_years)
            delta = t.supervisory_delta
            eff_not = delta * adj_not

            ac = SACCRAssetClass(t.asset_class)
            params = SACCR_ASSET_CLASS_PARAMS[ac]

            details.append(
                {
                    "trade_id": t.trade_id,
                    "asset_class": t.asset_class,
                    "underlying": t.underlying,
                    "notional": t.notional,
                    "mtm_value": t.mtm_value,
                    "supervisory_duration": round(sd, 6),
                    "adjusted_notional": round(adj_not, 2),
                    "supervisory_delta": round(delta, 4),
                    "effective_notional": round(eff_not, 2),
                    "supervisory_factor": params.supervisory_factor,
                    "correlation": params.correlation,
                }
            )
        return details

    # ------------------------------------------------------------------
    #  Main entry point
    # ------------------------------------------------------------------

    def calculate(self, netting_set: SACCRNettingSet) -> SACCRResult:
        """Calculate SA-CCR EAD for a netting set.

        EAD = alpha * (RC + PFE)
        PFE = multiplier * AddOn_aggregate

        Parameters
        ----------
        netting_set : SACCRNettingSet
            The netting set containing trades, collateral, and margining info.

        Returns
        -------
        SACCRResult
            Full calculation result with EAD breakdown.
        """
        rc = self._replacement_cost(netting_set)

        addons_by_ac = self._addon_by_asset_class(netting_set)
        addon_agg = sum(addons_by_ac.values())

        mult = self._multiplier(netting_set, addon_agg)
        pfe = mult * addon_agg
        alpha = netting_set.alpha
        ead = alpha * (rc + pfe)

        details = self._trade_details(netting_set)

        logger.info(
            "SA-CCR %s: EAD=%.2f (alpha=%.1f, RC=%.2f, PFE=%.2f, "
            "mult=%.4f, addon=%.2f)",
            netting_set.netting_set_id,
            ead,
            alpha,
            rc,
            pfe,
            mult,
            addon_agg,
        )

        return SACCRResult(
            ead=round(ead, 2),
            replacement_cost=round(rc, 2),
            pfe=round(pfe, 2),
            multiplier=round(mult, 6),
            addon_aggregate=round(addon_agg, 2),
            alpha=alpha,
            addon_by_asset_class={
                k: round(v, 2) for k, v in addons_by_ac.items()
            },
            trade_level_details=details,
        )

    # ------------------------------------------------------------------
    #  Batch processing
    # ------------------------------------------------------------------

    def calculate_batch(
        self, netting_sets: list[SACCRNettingSet]
    ) -> list[SACCRResult]:
        """Calculate SA-CCR EAD for multiple netting sets.

        Parameters
        ----------
        netting_sets : list[SACCRNettingSet]

        Returns
        -------
        list[SACCRResult]
        """
        return [self.calculate(ns) for ns in netting_sets]

    def calculate_portfolio_ead(
        self, netting_sets: list[SACCRNettingSet]
    ) -> dict:
        """Calculate portfolio-level EAD with summary statistics.

        Parameters
        ----------
        netting_sets : list[SACCRNettingSet]

        Returns
        -------
        dict
            Portfolio-level summary including total EAD and breakdowns.
        """
        results = self.calculate_batch(netting_sets)

        total_ead = sum(r.ead for r in results)
        total_rc = sum(r.replacement_cost for r in results)
        total_pfe = sum(r.pfe for r in results)

        # Aggregate add-on by asset class across netting sets
        agg_addon_by_ac: dict[str, float] = defaultdict(float)
        for r in results:
            for ac, val in r.addon_by_asset_class.items():
                agg_addon_by_ac[ac] += val

        return {
            "portfolio_ead": round(total_ead, 2),
            "total_replacement_cost": round(total_rc, 2),
            "total_pfe": round(total_pfe, 2),
            "netting_set_count": len(netting_sets),
            "trade_count": sum(len(ns.trades) for ns in netting_sets),
            "addon_by_asset_class": {
                k: round(v, 2) for k, v in sorted(agg_addon_by_ac.items())
            },
            "netting_set_results": [
                {
                    "netting_set_id": ns.netting_set_id,
                    "ead": r.ead,
                    "rc": r.replacement_cost,
                    "pfe": r.pfe,
                    "alpha": r.alpha,
                }
                for ns, r in zip(netting_sets, results)
            ],
        }

    # ------------------------------------------------------------------
    #  Sensitivity / what-if
    # ------------------------------------------------------------------

    def ead_sensitivity_to_mtm(
        self,
        netting_set: SACCRNettingSet,
        mtm_shifts: list[float] | None = None,
    ) -> list[dict]:
        """Compute EAD sensitivity to parallel MTM shifts.

        Parameters
        ----------
        netting_set : SACCRNettingSet
            Base netting set.
        mtm_shifts : list[float] | None
            List of additive MTM shifts to apply.  Defaults to
            [-0.20, -0.10, 0, 0.10, 0.20] as fractions of total notional.

        Returns
        -------
        list[dict]
            EAD at each shift level.
        """
        if mtm_shifts is None:
            total_notional = sum(t.notional for t in netting_set.trades)
            mtm_shifts = [
                frac * total_notional for frac in [-0.20, -0.10, 0, 0.10, 0.20]
            ]

        results: list[dict] = []
        for shift in mtm_shifts:
            # Create shifted trades
            shifted_trades = []
            per_trade_shift = shift / len(netting_set.trades)
            for t in netting_set.trades:
                shifted = t.model_copy(
                    update={"mtm_value": t.mtm_value + per_trade_shift}
                )
                shifted_trades.append(shifted)

            shifted_ns = netting_set.model_copy(
                update={"trades": shifted_trades}
            )
            r = self.calculate(shifted_ns)
            results.append(
                {
                    "mtm_shift": round(shift, 2),
                    "ead": r.ead,
                    "rc": r.replacement_cost,
                    "pfe": r.pfe,
                    "multiplier": r.multiplier,
                }
            )

        return results

    def ead_sensitivity_to_collateral(
        self,
        netting_set: SACCRNettingSet,
        collateral_levels: list[float] | None = None,
    ) -> list[dict]:
        """Compute EAD sensitivity to collateral amount.

        Parameters
        ----------
        netting_set : SACCRNettingSet
        collateral_levels : list[float] | None
            Collateral values to test.  Defaults to [0, 25%, 50%, 75%, 100%]
            of the portfolio MTM.

        Returns
        -------
        list[dict]
        """
        if collateral_levels is None:
            base_mtm = abs(netting_set.portfolio_mtm) or 1.0
            collateral_levels = [
                frac * base_mtm for frac in [0.0, 0.25, 0.50, 0.75, 1.0]
            ]

        results: list[dict] = []
        for c_level in collateral_levels:
            shifted_ns = netting_set.model_copy(
                update={"collateral": c_level}
            )
            r = self.calculate(shifted_ns)
            results.append(
                {
                    "collateral": round(c_level, 2),
                    "ead": r.ead,
                    "rc": r.replacement_cost,
                    "pfe": r.pfe,
                    "multiplier": r.multiplier,
                }
            )

        return results
