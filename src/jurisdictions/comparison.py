"""Cross-jurisdiction capital comparison: one bank, six rulebooks.

Runs the same synthetic balance sheet through every :class:`RegimeCalculator`
(BCBS, US, UK, EU, Singapore, Canada) and reports, per regime, the
components that each rulebook calibrates differently:

- SA credit RWA (risk weights, CCFs, CRM) -- regime ``credit_rwa``;
- counterparty credit risk -- regime ``saccr_ead`` (alpha, multiplier) on
  common replacement-cost / add-on inputs, risk-weighted with the regime's
  counterparty weight;
- CVA -- regime ``ba_cva_capital`` (sector risk weights, discount scalar);
- operational risk -- regime ``operational_risk`` (BIC thresholds in the
  regime's own currency, ILM policy);
- the output floor -- regime ``output_floor`` for the chosen year (the
  reference bank is a standardised-approach bank, so the floor cannot bind;
  :func:`floor_sensitivity` applies each regime's floor schedule to
  hypothetical modelled/standardised RWA ratios);
- the capital requirement -- regime ``capital_requirements``;
- market risk -- each regime's :class:`MarketRiskCalculator` (SBM risk weights,
  correlations and scenario rule, DRC, RRAO) on one regime-neutral trading
  book (:func:`src.data_generation.frtb_inputs.trading_positions_to_neutral_frtb`);
- securitisation -- each regime's ``securitisation`` hierarchy (the US NPR
  allows SEC-SA only; BCBS, UK, EU, Singapore and Canada use SEC-ERBA for
  rated positions, subject to their own ordering rules);
- CCP exposures, the leverage exposure measure and large-exposure limits --
  each regime's Pillar 1 calculators (``src/jurisdictions/<cc>/pillar1``).

Held common across regimes: capital resources (CET1, Tier 1, total) and the
synthetic inputs themselves. Market-risk amounts stay in USD in every regime
(the bank's reporting currency is set to USD in each FRTB calculator), so the
GIRR specified-currency and FX liquid-pair reductions are applied to the same
currency set. If the reference book carries no trading book, securitisation
tranches or leverage inputs, the caller's common amounts are used instead and
listed in ``common_components``.

Currency: each regime's monetary thresholds are stated in its own currency
(EUR, GBP, SGD, CAD). Inputs in USD are converted to the regime currency
with the ECB euro reference rates of 31 December 2024 -- the same date and
EUR/USD rate (1.0389) the Federal Reserve used for the 2025 aggregate global
indicator amounts (FR Doc. 2025-22964) -- and results are converted back.

All amounts in USD millions ($M) unless stated otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

import numpy as np
from pydantic import BaseModel, Field

from src.jurisdictions.base import (
    AssetClass,
    EquityType,
    Jurisdiction,
    OBSCategory,
    OpRiskInputs,
    PFPhase,
    RatingBucket,
    RegimeCalculator,
    SACCRNettingSetInput,
    SAExposure,
    SCRAGrade,
)
from src.jurisdictions.frtb_base import (
    DRCPositionInput,
    FRTBSensitivity,
    MarketRiskCalculator,
    RRAOPositionInput,
)
from src.jurisdictions.pillar1_base import (
    CCPExposureInput,
    LargeExposureInput,
    LeverageInputs,
    SecTrancheInput,
)

# =========================================================================
#  Currency
# =========================================================================

ECB_EUR_REFERENCE_RATES_20241231: Final[dict[str, float]] = {
    "USD": 1.0389,
    "GBP": 0.82918,
    "CAD": 1.4948,
    "SGD": 1.4164,
}
"""ECB euro foreign exchange reference rates, 31 Dec 2024 (units of currency per EUR)."""

FX_SOURCE: Final[str] = (
    "ECB euro foreign exchange reference rates, 31 December 2024 (EUR/USD 1.0389, as used in "
    "FR Doc. 2025-22964)"
)

REGIME_CURRENCY: Final[dict[Jurisdiction, str]] = {
    Jurisdiction.BCBS: "EUR",
    Jurisdiction.US: "USD",
    Jurisdiction.UK: "GBP",
    Jurisdiction.EU: "EUR",
    Jurisdiction.SG: "SGD",
    Jurisdiction.CA: "CAD",
}
"""Currency in which each regime states its monetary thresholds."""


def usd_to_local(currency: str) -> float:
    """Units of ``currency`` per USD from the 31 Dec 2024 ECB reference rates."""
    usd_per_eur = ECB_EUR_REFERENCE_RATES_20241231["USD"]
    if currency == "USD":
        return 1.0
    if currency == "EUR":
        return 1.0 / usd_per_eur
    return ECB_EUR_REFERENCE_RATES_20241231[currency] / usd_per_eur


_MONETARY_FIELDS: Final[tuple[str, ...]] = (
    "on_balance_amount",
    "off_balance_notional",
    "annual_turnover",
    "aggregate_retail_exposure_to_obligor",
    "property_value",
    "financial_collateral_value",
    "guarantee_amount",
)


def scale_exposure(e: SAExposure, k: float) -> SAExposure:
    """Copy of an exposure with every monetary field multiplied by ``k``."""
    upd = {f: getattr(e, f) * k for f in _MONETARY_FIELDS if getattr(e, f) is not None}
    return e.model_copy(update=upd)


def scale_op_inputs(op: OpRiskInputs, k: float) -> OpRiskInputs:
    """Copy of BI inputs with every amount multiplied by ``k``."""
    data = op.model_dump()
    return OpRiskInputs(**{name: [v * k for v in vals] for name, vals in data.items()})


# =========================================================================
#  Reference portfolio
# =========================================================================

_RATING_BUCKET: Final[dict[str, RatingBucket]] = {
    "AAA": RatingBucket.AAA_TO_AA_MINUS,
    "AA+": RatingBucket.AAA_TO_AA_MINUS,
    "AA": RatingBucket.AAA_TO_AA_MINUS,
    "AA-": RatingBucket.AAA_TO_AA_MINUS,
    "A+": RatingBucket.A_PLUS_TO_A_MINUS,
    "A": RatingBucket.A_PLUS_TO_A_MINUS,
    "A-": RatingBucket.A_PLUS_TO_A_MINUS,
    "BBB+": RatingBucket.BBB_PLUS_TO_BBB_MINUS,
    "BBB": RatingBucket.BBB_PLUS_TO_BBB_MINUS,
    "BBB-": RatingBucket.BBB_PLUS_TO_BBB_MINUS,
    "BB+": RatingBucket.BB_PLUS_TO_BB_MINUS,
    "BB": RatingBucket.BB_PLUS_TO_BB_MINUS,
    "BB-": RatingBucket.BB_PLUS_TO_BB_MINUS,
    "B+": RatingBucket.B_PLUS_TO_B_MINUS,
    "B": RatingBucket.B_PLUS_TO_B_MINUS,
    "B-": RatingBucket.B_PLUS_TO_B_MINUS,
}

_INDIVIDUAL_FLAGS: Final[dict[str, bool]] = {
    "counterparty_is_individual": True,  # BCBS CRE20.86 real-estate counterparty
    "obligor_is_natural_person": True,  # UK Art 124H
    "obligor_is_individual": True,  # SG 7.3
    "ca_counterparty_individual": True,  # OSFI Ch.4
    "ca_primary_residence": True,
    "eu_ipre_qualifying_natural_person": True,
}
"""Each regime's flag for an individual (natural-person) residential borrower."""

_CORPORATE_RE_FLAGS: Final[dict[str, bool]] = {
    "counterparty_is_corporate": True,
    "ca_counterparty_corporate": True,
    "eu_re_counterparty_corporate": True,
}


@dataclass
class ReferenceBook:
    """Synthetic bank inputs for the comparison (USD $M)."""

    exposures: list[SAExposure]
    netting_sets: list[
        tuple[SACCRNettingSetInput, AssetClass, RatingBucket, SCRAGrade | None, str, str, float]
    ]
    """(inputs, counterparty class, rating, SCRA grade, CVA sector, CVA quality, maturity)."""
    op_inputs: OpRiskInputs
    frtb_sensitivities: list[FRTBSensitivity] = field(default_factory=list)
    drc_positions: list[DRCPositionInput] = field(default_factory=list)
    rrao_positions: list[RRAOPositionInput] = field(default_factory=list)
    sec_tranches: list[SecTrancheInput] = field(default_factory=list)
    ccp_exposures: list[CCPExposureInput] = field(default_factory=list)
    leverage: LeverageInputs | None = None
    large_exposures: list[LargeExposureInput] = field(default_factory=list)

    @property
    def has_trading_book(self) -> bool:
        """True when the book carries FRTB inputs."""
        return bool(self.frtb_sensitivities or self.drc_positions or self.rrao_positions)


def build_reference_book(
    credit_exposures: list[object],
    saccr_rows: list[dict[str, object]],
    op_inputs: OpRiskInputs,
    seed: int = 20260319,
) -> ReferenceBook:
    """Map the engine's synthetic portfolio into jurisdiction-neutral inputs.

    Args:
        credit_exposures: ``PortfolioGenerator.generate_credit_portfolio().exposures``.
        saccr_rows: SA-CCR netting-set rows (keys ``netting_set_id``, ``rc``,
            ``pfe``, ``multiplier``, ``mtm``, ``collateral``, ``counterparty_type``,
            ``commercial_end_user``, ``maturity``).
        op_inputs: Business-indicator inputs (USD $M).
        seed: Seed for the synthetic attributes added here.

    Returns:
        ReferenceBook.
    """
    rng = np.random.default_rng(seed)
    out: list[SAExposure] = []
    for i, e in enumerate(credit_exposures):
        t = e.exposure_type  # type: ignore[attr-defined]
        ead = float(e.ead)  # type: ignore[attr-defined]
        rating = str(e.rating)  # type: ignore[attr-defined]
        mat = float(e.maturity_years)  # type: ignore[attr-defined]
        common = dict(
            exposure_id=str(e.exposure_id),  # type: ignore[attr-defined]
            counterparty=str(e.counterparty_name),  # type: ignore[attr-defined]
            on_balance_amount=ead,
            residual_maturity_years=mat,
            is_defaulted=bool(e.is_defaulted),
        )  # type: ignore[attr-defined]
        if t == "SOVEREIGN":
            out.append(
                SAExposure(
                    asset_class=AssetClass.SOVEREIGN,
                    rating=RatingBucket.AAA_TO_AA_MINUS,
                    sovereign_rating=RatingBucket.AAA_TO_AA_MINUS,
                    oecd_crc=0,
                    flags={"is_us_sovereign": True},
                    **common,
                )
            )
        elif t == "AGENCY_MBS":
            out.append(
                SAExposure(
                    asset_class=AssetClass.PSE,
                    sovereign_rating=RatingBucket.AAA_TO_AA_MINUS,
                    rating=RatingBucket.AAA_TO_AA_MINUS,
                    oecd_crc=0,
                    **common,
                )
            )
        elif t in ("CORPORATE_IG", "CORPORATE_HY"):
            ig = t == "CORPORATE_IG"
            # one corporate in four is unrated (relies on the IG assessment where permitted)
            unrated = rng.random() < 0.25
            out.append(
                SAExposure(
                    asset_class=AssetClass.CORPORATE,
                    is_investment_grade=ig,
                    rating=RatingBucket.UNRATED
                    if unrated
                    else _RATING_BUCKET.get(rating, RatingBucket.BBB_PLUS_TO_BBB_MINUS),
                    flags={"ca_unrated_ig_identification": True},
                    **common,
                )
            )
        elif t == "RETAIL_MORTGAGE":
            ltv = 0.30 + 0.65 * (float(e.ltv) / 0.8)  # type: ignore[attr-defined]
            out.append(
                SAExposure(
                    asset_class=AssetClass.RESIDENTIAL_RE,
                    ltv=ltv,
                    property_value=ead / ltv,
                    flags=dict(_INDIVIDUAL_FLAGS),
                    **common,
                )
            )
        elif t == "RETAIL_REVOLVING":
            transactor = i % 2 == 0
            out.append(
                SAExposure(
                    asset_class=AssetClass.RETAIL_TRANSACTOR
                    if transactor
                    else AssetClass.RETAIL_REGULATORY,
                    is_transactor=transactor,
                    aggregate_retail_exposure_to_obligor=0.05,
                    flags=dict(_INDIVIDUAL_FLAGS),
                    **common,
                )
            )
        elif t == "CRE":
            ltv = 0.30 + 0.65 * (float(e.ltv) / 0.8)  # type: ignore[attr-defined]
            out.append(
                SAExposure(
                    asset_class=AssetClass.COMMERCIAL_RE,
                    ltv=ltv,
                    property_value=ead / ltv,
                    is_cash_flow_dependent=True,
                    flags=dict(_CORPORATE_RE_FLAGS),
                    **common,
                )
            )
        else:
            out.append(SAExposure(asset_class=AssetClass.OTHER_ASSETS, **common))

    # Interbank book: rated banks, with SCRA grades for regimes that use them
    for i in range(80):
        grades = (SCRAGrade.A, SCRAGrade.A, SCRAGrade.B, SCRAGrade.C)
        grade = grades[int(rng.choice(len(grades), p=[0.45, 0.35, 0.17, 0.03]))]
        rb = {
            SCRAGrade.A: RatingBucket.A_PLUS_TO_A_MINUS,
            SCRAGrade.B: RatingBucket.BBB_PLUS_TO_BBB_MINUS,
            SCRAGrade.C: RatingBucket.BB_PLUS_TO_BB_MINUS,
        }[grade]
        out.append(
            SAExposure(
                exposure_id=f"BK-{i:04d}",
                asset_class=AssetClass.BANK,
                counterparty=f"Bank-{i}",
                on_balance_amount=float(rng.uniform(500, 3_500)),
                rating=rb,
                scra_grade=grade,
                scra_grade_a_enhanced=bool(i % 3 == 0 and grade == SCRAGrade.A),
                residual_maturity_years=float(rng.uniform(0.5, 4.0)),
                original_maturity_months=24.0,
                sovereign_rating=RatingBucket.AAA_TO_AA_MINUS,
            )
        )

    # Undrawn corporate commitments (off-balance sheet)
    for i in range(120):
        cat = OBSCategory.COMMITMENT_OTHER if i % 4 else OBSCategory.UNCONDITIONALLY_CANCELLABLE
        ig = bool(i % 3)
        out.append(
            SAExposure(
                exposure_id=f"OBS-{i:04d}",
                asset_class=AssetClass.CORPORATE,
                counterparty=f"Corp-OBS-{i}",
                off_balance_notional=float(rng.uniform(1_000, 4_000)),
                obs_category=cat,
                commitment_original_maturity_years=(0.5, 3.0, 5.0)[i % 3],
                is_investment_grade=ig,
                rating=RatingBucket.BBB_PLUS_TO_BBB_MINUS
                if ig
                else RatingBucket.BB_PLUS_TO_BB_MINUS,
                flags={
                    "commitment_unconditionally_cancellable": cat
                    == OBSCategory.UNCONDITIONALLY_CANCELLABLE
                },
                residual_maturity_years=3.0,
            )
        )

    # SME corporates, project finance, equities, covered bonds
    for i in range(40):
        out.append(
            SAExposure(
                exposure_id=f"SME-{i:04d}",
                asset_class=AssetClass.CORPORATE_SME,
                is_sme=True,
                counterparty=f"SME-{i}",
                on_balance_amount=float(rng.uniform(5, 40)),
                annual_turnover=float(rng.uniform(5, 40)),
                residual_maturity_years=3.0,
                is_investment_grade=False,
            )
        )
    for i, phase in enumerate(
        [PFPhase.PRE_OPERATIONAL, PFPhase.OPERATIONAL, PFPhase.HIGH_QUALITY_OPERATIONAL] * 6
    ):
        out.append(
            SAExposure(
                exposure_id=f"PF-{i:04d}",
                asset_class=AssetClass.SPECIALISED_LENDING_PF,
                counterparty=f"PF-{i}",
                on_balance_amount=float(rng.uniform(300, 1_200)),
                pf_phase=phase,
                residual_maturity_years=8.0,
            )
        )
    for i, et in enumerate(
        [EquityType.PUBLICLY_TRADED, EquityType.GENERAL, EquityType.SPECULATIVE_UNLISTED] * 5
    ):
        out.append(
            SAExposure(
                exposure_id=f"EQ-{i:04d}",
                asset_class=AssetClass.EQUITY,
                counterparty=f"EQ-{i}",
                on_balance_amount=float(rng.uniform(200, 900)),
                equity_type=et,
                flags={"higher_risk_equity": et == EquityType.SPECULATIVE_UNLISTED},
            )
        )
    for i in range(10):
        out.append(
            SAExposure(
                exposure_id=f"CB-{i:04d}",
                asset_class=AssetClass.COVERED_BOND,
                counterparty=f"CB-{i}",
                on_balance_amount=float(rng.uniform(500, 2_000)),
                covered_bond_rated=True,
                rating=RatingBucket.AAA_TO_AA_MINUS,
                scra_grade=SCRAGrade.A,
                residual_maturity_years=5.0,
            )
        )

    # Derivative netting sets: common RC and add-on from the engine's SA-CCR
    counterparty_profile = {
        "BANK": (AssetClass.BANK, RatingBucket.A_PLUS_TO_A_MINUS, SCRAGrade.A, "FINANCIAL", "IG"),
        "FINANCIAL": (
            AssetClass.CORPORATE,
            RatingBucket.BBB_PLUS_TO_BBB_MINUS,
            None,
            "FINANCIAL",
            "IG",
        ),
        "CORPORATE": (
            AssetClass.CORPORATE,
            RatingBucket.BBB_PLUS_TO_BBB_MINUS,
            None,
            "OTHER",
            "IG",
        ),
        "SOVEREIGN": (AssetClass.SOVEREIGN, RatingBucket.AAA_TO_AA_MINUS, None, "SOVEREIGN", "IG"),
    }
    ns: list[
        tuple[SACCRNettingSetInput, AssetClass, RatingBucket, SCRAGrade | None, str, str, float]
    ] = []
    for r in saccr_rows:
        cls, rb, grade, sector, quality = counterparty_profile[str(r["counterparty_type"])]
        mult = float(r["multiplier"]) or 1.0
        ns.append(
            (
                SACCRNettingSetInput(
                    netting_set_id=str(r["netting_set_id"]),
                    replacement_cost=float(r["rc"]),
                    aggregate_addon=float(r["pfe"]) / mult,
                    mtm=float(r.get("mtm", 0.0)),
                    net_collateral=float(r.get("collateral", 0.0)),
                    is_margined=bool(r.get("margined", False)),
                    counterparty_is_nonfinancial=bool(r["commercial_end_user"]),
                ),
                cls,
                rb,
                grade,
                sector,
                quality,
                float(r["maturity"]),
            )
        )
    return ReferenceBook(out, ns, op_inputs)


SecDealSpec = tuple[str, float, float, float]
"""(deal id, pool size $M, pool SA capital charge K_SA, delinquent share W)."""

SecTrancheSpec = tuple[str, float, float, bool, str | None]
"""(tranche suffix, attachment A, detachment D, is senior, external rating or None)."""


def reference_securitisations(
    deals: list[SecDealSpec],
    tranches: list[SecTrancheSpec],
    n_effective: float,
    maturity_years: float,
) -> list[SecTrancheInput]:
    """Investor tranches of each deal as regime-neutral inputs.

    K_SA and W are the pool parameters of CRE44.2-44.3 (ERBA NPR § __.133(b));
    the exposure amount is the tranche thickness times the pool size; the
    rating drives SEC-ERBA where a regime uses it (CRE42; CRR Art. 263).
    """
    out: list[SecTrancheInput] = []
    for deal, size, k_sa, w in deals:
        for name, a, d, senior, rating in tranches:
            out.append(
                SecTrancheInput(
                    tranche_id=f"{deal}-{name}",
                    exposure_amount=size * (d - a),
                    attachment=a,
                    detachment=d,
                    is_senior=senior,
                    maturity_years=maturity_years,
                    k_sa=k_sa,
                    w=w,
                    n_effective=n_effective,
                    external_rating=rating,
                )
            )
    return out


def banking_book_large_exposures(exposures: list[SAExposure]) -> list[LargeExposureInput]:
    """Aggregate banking-book exposures by counterparty for the large-exposure test.

    Exposure value = on-balance amount + off-balance notional, i.e. before
    credit conversion factors (an upper bound of the LEX30.11 measure, which
    applies the SA CCFs floored at 10%). Sovereign exposures are flagged
    exempt (LEX30.33); each regime may apply further exemptions of its own.
    Derivative exposures are added per regime in :func:`run_comparison`
    from the regime's own SA-CCR EAD.
    """
    agg: dict[str, list[object]] = {}
    for e in exposures:
        key = e.counterparty or e.exposure_id
        amount = e.on_balance_amount + (e.off_balance_notional or 0.0)
        if key in agg:
            agg[key][0] = float(agg[key][0]) + amount  # type: ignore[arg-type]
        else:
            agg[key] = [amount, e.asset_class]
    return [
        LargeExposureInput(
            counterparty_id=k,
            exposure_value=float(v[0]),  # type: ignore[arg-type]
            counterparty_asset_class=v[1],  # type: ignore[arg-type]
            is_exempt=v[1] == AssetClass.SOVEREIGN,
        )
        for k, v in agg.items()
        if float(v[0]) > 0.0  # type: ignore[arg-type]
    ]


# =========================================================================
#  Results
# =========================================================================


class RegimeComparison(BaseModel):
    """One regime's view of the reference bank (USD $M; ratios decimal)."""

    jurisdiction: Jurisdiction
    regime_name: str
    currency: str
    fx_usd_to_local: float
    credit_exposure: float
    credit_rwa: float
    credit_rwa_by_class: dict[str, float] = Field(default_factory=dict)
    ccr_ead: float
    ccr_rwa: float
    cva_rwa: float
    op_business_indicator: float
    op_ilm: float
    op_rwa: float
    market_rwa: float
    market_sbm: float = 0.0
    market_drc: float = 0.0
    market_rrao: float = 0.0
    market_binding_scenario: str = ""
    market_by_class: dict[str, float] = Field(default_factory=dict)
    securitisation_exposure: float = 0.0
    securitisation_rwa: float
    securitisation_rows: list[dict[str, object]] = Field(default_factory=list)
    ccp_rwa: float = 0.0
    standardised_rwa: float
    modelled_rwa: float | None = None
    floor_applies: bool = False
    floor_factor: float = 0.0
    floor_add_on: float = 0.0
    total_rwa: float
    cet1_ratio: float
    tier1_ratio: float
    total_capital_ratio: float
    leverage_exposure: float = 0.0
    leverage_exclusions: float = 0.0
    leverage_ratio: float
    large_exposures_reportable: int = 0
    large_exposure_breaches: list[str] = Field(default_factory=list)
    large_exposure_max_pct_tier1: float = 0.0
    cet1_requirement: float
    cet1_surplus: float
    leverage_requirement: float
    citations: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


TABLE_EXCLUDED_FIELDS: Final[set[str]] = {
    "credit_rwa_by_class",
    "market_by_class",
    "securitisation_rows",
    "large_exposure_breaches",
    "citations",
    "notes",
}
"""Nested fields left out of the flat report table."""


class ComparisonResult(BaseModel):
    """All regimes side by side."""

    year: int
    fx_source: str = FX_SOURCE
    common_components: list[str] = Field(default_factory=list)
    regimes: list[RegimeComparison] = Field(default_factory=list)

    def table(self) -> list[dict[str, object]]:
        """Flat rows for reporting."""
        return [r.model_dump(exclude=TABLE_EXCLUDED_FIELDS) for r in self.regimes]


# =========================================================================
#  Engine
# =========================================================================


def default_regimes(year: int) -> dict[Jurisdiction, RegimeCalculator]:
    """One configured calculator per jurisdiction for a reporting year."""
    from datetime import date

    from src.jurisdictions.bcbs import BCBSRegime
    from src.jurisdictions.ca import CARegime
    from src.jurisdictions.eu import EURegime
    from src.jurisdictions.sg import SGRegime
    from src.jurisdictions.uk import UKRegime
    from src.jurisdictions.us import USRegime

    return {
        Jurisdiction.BCBS: BCBSRegime(),
        Jurisdiction.US: USRegime(),
        Jurisdiction.UK: UKRegime(year=year, irb_firm=True, corporate_ig_permission=True),
        Jurisdiction.EU: EURegime(year=year),
        Jurisdiction.SG: SGRegime(is_dsib=True, as_of=date(year, 1, 1)),
        Jurisdiction.CA: CARegime(),
    }


def default_market_regimes() -> dict[Jurisdiction, MarketRiskCalculator]:
    """One FRTB calculator per jurisdiction, each with USD as the reporting currency.

    The reference bank reports in USD, so USD is the domestic currency for the
    GIRR specified-currency reduction and the FX reporting currency in every
    regime (MAR21.44, MAR21.88; UK and EU Art. 325ae(3) / 325av; OSFI CAR
    Ch. 9; MAS Notice 637 Annex 8).
    """
    import importlib

    from src.jurisdictions.bcbs.frtb import BCBSMarketRisk
    from src.jurisdictions.ca.frtb import CAMarketRisk
    from src.jurisdictions.eu.frtb import EUMarketRisk
    from src.jurisdictions.uk.frtb import UKMarketRisk
    from src.jurisdictions.us import USMarketRisk

    out: dict[Jurisdiction, MarketRiskCalculator] = {
        Jurisdiction.BCBS: BCBSMarketRisk(),
        Jurisdiction.US: USMarketRisk(),
        Jurisdiction.UK: UKMarketRisk(domestic_currency="USD"),
        Jurisdiction.EU: EUMarketRisk(domestic_currency="USD"),
        Jurisdiction.CA: CAMarketRisk(reporting_currency="USD"),
    }
    try:
        sg = importlib.import_module("src.jurisdictions.sg.frtb")
        out[Jurisdiction.SG] = sg.SGMarketRisk(reporting_currency="USD")
    except ImportError:
        pass  # SG FRTB package absent: run_comparison falls back to market_rwa_usd
    return out


def default_pillar1_regimes(year: int) -> dict[Jurisdiction, Any]:
    """Securitisation, CCP, leverage and large-exposure calculators per jurisdiction.

    Amounts are passed in USD; the EU calculator converts its EUR 150 million
    institution floor (CRR Art. 395(1)) at the ECB 31 Dec 2024 rate.
    """
    from src.jurisdictions.bcbs.pillar1 import BCBSPillar1
    from src.jurisdictions.ca.pillar1 import CAPillar1
    from src.jurisdictions.eu.pillar1 import EUPillar1
    from src.jurisdictions.sg.pillar1 import SGPillar1
    from src.jurisdictions.uk.pillar1 import UKPillar1
    from src.jurisdictions.us import USPillar1

    return {
        Jurisdiction.BCBS: BCBSPillar1(),
        Jurisdiction.US: USPillar1(),
        Jurisdiction.UK: UKPillar1(),
        Jurisdiction.EU: EUPillar1(
            year=year,
            reporting_currency="USD",
            reporting_ccy_per_eur=ECB_EUR_REFERENCE_RATES_20241231["USD"],
        ),
        Jurisdiction.SG: SGPillar1(),
        Jurisdiction.CA: CAPillar1(reporting_currency="USD"),
    }


FLOOR_SENSITIVITY_RATIOS: Final[tuple[float, ...]] = (0.50, 0.60, 0.70)
"""Hypothetical modelled-to-standardised RWA ratios for the output-floor what-if.

Not regulatory parameters and not model outputs: a scenario grid showing
how each regime's floor schedule would bite on an internal-models bank whose
modelled RWA is this fraction of its standardised RWA."""


class FloorSensitivityRow(BaseModel):
    """Output-floor add-on for one regime, year and hypothetical modelled/SA ratio."""

    jurisdiction: Jurisdiction
    year: int
    modelled_to_sa: float
    floor_factor: float
    floor_applies: bool
    standardised_rwa: float
    modelled_rwa: float
    floored_rwa: float
    add_on: float
    citation: str


def floor_sensitivity(
    result: ComparisonResult,
    years: tuple[int, ...],
    ratios: tuple[float, ...] = FLOOR_SENSITIVITY_RATIOS,
    regimes: dict[Jurisdiction, RegimeCalculator] | None = None,
) -> list[FloorSensitivityRow]:
    """Apply each regime's own output-floor rule to hypothetical modelled RWA.

    For each regime, year and ratio r: modelled = r x standardised RWA (the
    regime's own SA total from ``result``); the regime's ``output_floor``
    returns the floored RWA. Amounts are converted to the regime currency for
    the call and back to USD.
    """
    rows: list[FloorSensitivityRow] = []
    for year in years:
        regs = regimes or default_regimes(year)
        for r in result.regimes:
            reg = regs[r.jurisdiction]
            k = r.fx_usd_to_local
            for ratio in ratios:
                modelled = ratio * r.standardised_rwa
                fl = reg.output_floor(modelled * k, r.standardised_rwa * k, year)
                rows.append(
                    FloorSensitivityRow(
                        jurisdiction=r.jurisdiction,
                        year=year,
                        modelled_to_sa=ratio,
                        floor_factor=fl.floor_factor,
                        floor_applies=fl.applies,
                        standardised_rwa=r.standardised_rwa,
                        modelled_rwa=modelled,
                        floored_rwa=fl.floored_rwa / k,
                        add_on=fl.add_on / k,
                        citation=fl.citation,
                    )
                )
    return rows


def _market_result(
    reg: MarketRiskCalculator, book: ReferenceBook
) -> tuple[float, float, float, float, str, dict[str, float], str]:
    """(RWA, SBM, DRC, RRAO, binding scenario, SBM by class, citation) of one regime."""
    r = reg.market_risk(book.frtb_sensitivities, book.drc_positions, book.rrao_positions)
    by_class = {c.risk_class.value: c.total for c in r.sbm_by_class if c.total}
    cite = "; ".join(f"{k}: {v}" for k, v in r.citations.items())
    return r.rwa, r.sbm_total, r.drc_total, r.rrao, r.binding_scenario, by_class, cite


def run_comparison(
    book: ReferenceBook,
    year: int,
    *,
    capital_usd: dict[str, float],
    gsib_method1_score_bps: float,
    us_gsib_rate: float,
    us_scb: float,
    market_rwa_usd: float | None = None,
    securitisation_rwa_usd: float | None = None,
    leverage_exposure_usd: float | None = None,
    reporting_bank_is_gsib: bool = True,
    regimes: dict[Jurisdiction, RegimeCalculator] | None = None,
    market_regimes: dict[Jurisdiction, MarketRiskCalculator] | None = None,
    pillar1_regimes: dict[Jurisdiction, Any] | None = None,
) -> ComparisonResult:
    """Run the reference bank through every regime.

    Args:
        book: Reference inputs (USD $M).
        year: Reporting year (drives transitional schedules).
        capital_usd: {"cet1", "tier1", "total"} capital amounts ($M), held common.
        gsib_method1_score_bps: BCBS-methodology score, used for the G-SIB
            bucket outside the US (BCBS SCO40 / RBC40 bucket table).
        us_gsib_rate: US surcharge rate (decimal) from 12 CFR 217.403.
        us_scb: US stress capital buffer (decimal).
        market_rwa_usd: Common market-risk RWA, used only when the book has no
            trading book.
        securitisation_rwa_usd: Common securitisation RWA, used only when the
            book has no securitisation tranches.
        leverage_exposure_usd: Common leverage exposure measure, used only when
            the book has no leverage inputs.
        reporting_bank_is_gsib: Drives the G-SIB-to-G-SIB large-exposure limit.
        regimes: Credit / op-risk / floor / capital calculators
            (default: :func:`default_regimes`).
        market_regimes: FRTB calculators (default: :func:`default_market_regimes`).
        pillar1_regimes: Securitisation / CCP / leverage / large-exposure
            calculators (default: :func:`default_pillar1_regimes`).

    The bank uses standardised approaches everywhere, so pre-floor RWA equals
    standardised RWA and the floor cannot bind; :func:`floor_sensitivity`
    shows how it would bind for an internal-models bank.

    Returns:
        ComparisonResult.
    """
    from src.jurisdictions.bcbs.capital_stack import gsib_bucket_from_score, gsib_hla

    if not book.has_trading_book and market_rwa_usd is None:
        raise ValueError("book has no trading book: pass market_rwa_usd")
    if not book.sec_tranches and securitisation_rwa_usd is None:
        raise ValueError("book has no securitisation tranches: pass securitisation_rwa_usd")
    if book.leverage is None and leverage_exposure_usd is None:
        raise ValueError("book has no leverage inputs: pass leverage_exposure_usd")

    regimes = regimes or default_regimes(year)
    if book.has_trading_book:
        market_regimes = market_regimes or default_market_regimes()
    if book.sec_tranches or book.leverage or book.ccp_exposures or book.large_exposures:
        pillar1_regimes = pillar1_regimes or default_pillar1_regimes(year)
    hla = gsib_hla(gsib_bucket_from_score(gsib_method1_score_bps))
    tier1 = capital_usd["tier1"]
    fallbacks: list[str] = []
    rows: list[RegimeComparison] = []
    for j, reg in regimes.items():
        ccy = REGIME_CURRENCY[j]
        k = usd_to_local(ccy)
        back = 1.0 / k
        notes: list[str] = []
        citations: dict[str, str] = {}
        local = [scale_exposure(e, k) for e in book.exposures]
        cr = reg.credit_rwa(local)
        cls_of = {e.exposure_id: e.asset_class.value for e in book.exposures}
        by_class: dict[str, float] = {}
        for li in cr.line_items:
            by_class[cls_of[li.exposure_id]] = (
                by_class.get(cls_of[li.exposure_id], 0.0) + li.rwa * back
            )

        ccr_ead = ccr_rwa = 0.0
        ns_ead: list[tuple[str, float, AssetClass]] = []
        cva_cps: list[dict[str, float | str | bool]] = []
        for nsi, cls, rb, grade, sector, quality, mat in book.netting_sets:
            local_ns = nsi.model_copy(
                update={
                    "replacement_cost": nsi.replacement_cost * k,
                    "aggregate_addon": nsi.aggregate_addon * k,
                    "mtm": nsi.mtm * k,
                    "net_collateral": nsi.net_collateral * k,
                }
            )
            sr = reg.saccr_ead(local_ns)
            cp = SAExposure(
                exposure_id=f"CCR-{nsi.netting_set_id}",
                asset_class=cls,
                rating=rb,
                scra_grade=grade,
                sovereign_rating=RatingBucket.AAA_TO_AA_MINUS,
                on_balance_amount=sr.ead,
                residual_maturity_years=mat,
                oecd_crc=0,
                is_investment_grade=True,
                flags={"is_us_sovereign": True},
            )
            ccr_ead += sr.ead * back
            ccr_rwa += reg.risk_weight(cp).rwa * back
            ns_ead.append((nsi.netting_set_id, sr.ead * back, cls))
            cva_cps.append(
                {
                    "id": nsi.netting_set_id,
                    "ead": sr.ead,
                    "maturity": mat,
                    "sector": sector,
                    "credit_quality": quality,
                    "commercial_end_user": nsi.counterparty_is_nonfinancial,
                }
            )
        cva = reg.ba_cva_capital(cva_cps)
        cva_rwa = float(cva["rwa"]) * back

        op = reg.operational_risk(scale_op_inputs(book.op_inputs, k))
        op_rwa = op.rwa * back
        credit_rwa = cr.total_rwa * back

        # ---- market risk (regime FRTB calculator, USD reporting currency)
        sbm = drc = rrao = 0.0
        scenario = ""
        mkt_by_class: dict[str, float] = {}
        if book.has_trading_book and market_regimes is not None and j in market_regimes:
            market_rwa, sbm, drc, rrao, scenario, mkt_by_class, mcite = _market_result(
                market_regimes[j], book
            )
            citations["market_risk"] = mcite
        elif market_rwa_usd is not None:
            market_rwa = market_rwa_usd
            notes.append("market-risk RWA held common (caller-supplied)")
            if book.has_trading_book:
                fallbacks.append(f"market risk RWA for {j.value} (caller-supplied; no calculator)")
        else:
            raise ValueError(f"no market-risk calculator for {j.value} and no market_rwa_usd")

        # ---- securitisation, CCP, leverage, large exposures (regime Pillar 1)
        p1 = (pillar1_regimes or {}).get(j)
        sec_rows: list[dict[str, object]] = []
        sec_exposure = 0.0
        if book.sec_tranches and p1 is not None:
            sec_rwa = 0.0
            for t in book.sec_tranches:
                sr_row = p1.securitisation(t)
                sec_rwa += sr_row.rwa
                sec_exposure += t.exposure_amount
                sec_rows.append(
                    {
                        "tranche": t.tranche_id,
                        "approach": sr_row.approach.value,
                        "risk_weight": sr_row.risk_weight,
                        "rwa": sr_row.rwa,
                        "citation": sr_row.citation,
                    }
                )
            citations["securitisation"] = sec_rows[0]["citation"] if sec_rows else ""  # type: ignore[assignment]
        elif securitisation_rwa_usd is not None:
            sec_rwa = securitisation_rwa_usd
            notes.append("securitisation RWA held common (caller-supplied)")
            if book.sec_tranches:
                fallbacks.append(
                    f"securitisation RWA for {j.value} (caller-supplied; no calculator)"
                )
        else:
            raise ValueError(f"no securitisation calculator for {j.value} and no common RWA")

        ccp_rwa = 0.0
        if p1 is not None:
            for c in book.ccp_exposures:
                cres = p1.ccp_exposure(c)
                ccp_rwa += cres.total_rwa
                citations[f"ccp:{c.ccp_id}"] = cres.citation

        if book.leverage is not None and p1 is not None:
            lev = p1.leverage_exposure(book.leverage)
            lev_exposure, lev_excl = lev.total_exposure, lev.exclusions
            citations.update({f"leverage:{a}": b for a, b in lev.citations.items()})
        else:
            lev_exposure, lev_excl = float(leverage_exposure_usd or 0.0), 0.0
            notes.append("leverage exposure measure held common (caller-supplied)")

        le_reportable = 0
        le_breaches: list[str] = []
        le_max = 0.0
        if book.large_exposures and p1 is not None:
            le_inputs = list(book.large_exposures)
            for ns_id, ead, cls in ns_ead:
                le_inputs.append(
                    LargeExposureInput(
                        counterparty_id=ns_id,
                        exposure_value=ead,
                        counterparty_asset_class=cls,
                        counterparty_is_gsib=cls == AssetClass.BANK,
                        is_exempt=cls == AssetClass.SOVEREIGN,
                    )
                )
            exempt = {x.counterparty_id for x in le_inputs if x.is_exempt}
            for row in p1.large_exposures(le_inputs, tier1, reporting_bank_is_gsib):
                le_reportable += int(row.reportable)
                if row.breach:
                    le_breaches.append(row.counterparty_id)
                if row.counterparty_id not in exempt:
                    le_max = max(le_max, row.exposure_value / tier1)

        sa_total = credit_rwa + ccr_rwa + cva_rwa + op_rwa + market_rwa + sec_rwa + ccp_rwa
        modelled = None
        fl = reg.output_floor(sa_total * k, sa_total * k, year)
        total = fl.floored_rwa * back
        notes += fl.notes

        if j == Jurisdiction.US:
            req = reg.capital_requirements(
                systemic_bucket_or_rate=us_gsib_rate, stress_buffer=us_scb
            )
        else:
            req = reg.capital_requirements(systemic_bucket_or_rate=hla)
            notes.append(
                f"G-SIB higher-loss-absorbency {hla:.1%} from BCBS bucket of a "
                f"{gsib_method1_score_bps:.0f} bp score"
            )
        cet1 = capital_usd["cet1"] / total
        rows.append(
            RegimeComparison(
                jurisdiction=j,
                regime_name=reg.regime_name,
                currency=ccy,
                fx_usd_to_local=k,
                credit_exposure=cr.total_exposure * back,
                credit_rwa=credit_rwa,
                credit_rwa_by_class=by_class,
                ccr_ead=ccr_ead,
                ccr_rwa=ccr_rwa,
                cva_rwa=cva_rwa,
                op_business_indicator=op.business_indicator * back,
                op_ilm=op.ilm,
                op_rwa=op_rwa,
                market_rwa=market_rwa,
                market_sbm=sbm,
                market_drc=drc,
                market_rrao=rrao,
                market_binding_scenario=scenario,
                market_by_class=mkt_by_class,
                securitisation_exposure=sec_exposure,
                securitisation_rwa=sec_rwa,
                securitisation_rows=sec_rows,
                ccp_rwa=ccp_rwa,
                standardised_rwa=sa_total,
                modelled_rwa=modelled,
                floor_applies=fl.applies,
                floor_factor=fl.floor_factor,
                floor_add_on=fl.add_on * back,
                total_rwa=total,
                cet1_ratio=cet1,
                tier1_ratio=tier1 / total,
                total_capital_ratio=capital_usd["total"] / total,
                leverage_exposure=lev_exposure,
                leverage_exclusions=lev_excl,
                leverage_ratio=tier1 / lev_exposure,
                large_exposures_reportable=le_reportable,
                large_exposure_breaches=le_breaches,
                large_exposure_max_pct_tier1=le_max,
                cet1_requirement=req.cet1_requirement,
                cet1_surplus=cet1 - req.cet1_requirement,
                leverage_requirement=req.leverage_minimum + req.leverage_buffer,
                citations={
                    "output_floor": fl.citation,
                    "op_risk": op.citation,
                    **citations,
                    **req.citations,
                },
                notes=notes,
            )
        )
    common = ["capital resources (CET1, Tier 1, total capital)"]
    if not book.has_trading_book:
        common.append("market risk RWA (caller-supplied)")
    if not book.sec_tranches:
        common.append("securitisation RWA (caller-supplied)")
    if book.leverage is None:
        common.append("leverage exposure measure (caller-supplied)")
    common += fallbacks
    return ComparisonResult(year=year, common_components=common, regimes=rows)
