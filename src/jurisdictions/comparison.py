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
- the capital requirement -- regime ``capital_requirements``.

Held common across regimes and labelled as such in the result: market-risk
RWA (US FRTB-SA engine) and securitisation RWA (US SEC-SA engine). The
jurisdictional FRTB and securitisation calibrations are not part of the
RegimeCalculator contract.

Currency: each regime's monetary thresholds are stated in its own currency
(EUR, GBP, SGD, CAD). Inputs in USD are converted to the regime currency
with the ECB euro reference rates of 31 December 2024 -- the same date and
EUR/USD rate (1.0389) the Federal Reserve used for the 2025 aggregate global
indicator amounts (FR Doc. 2025-22964) -- and results are converted back.

All amounts in USD millions ($M) unless stated otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

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
            exposure_id=str(e.exposure_id),  # type: ignore[attr-defined] counterparty=str(e.counterparty_name),  # type: ignore[attr-defined]
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
    securitisation_rwa: float
    standardised_rwa: float
    modelled_rwa: float | None = None
    floor_applies: bool = False
    floor_factor: float = 0.0
    floor_add_on: float = 0.0
    total_rwa: float
    cet1_ratio: float
    tier1_ratio: float
    total_capital_ratio: float
    leverage_ratio: float
    cet1_requirement: float
    cet1_surplus: float
    leverage_requirement: float
    citations: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ComparisonResult(BaseModel):
    """All regimes side by side."""

    year: int
    fx_source: str = FX_SOURCE
    common_components: list[str] = Field(default_factory=list)
    regimes: list[RegimeComparison] = Field(default_factory=list)

    def table(self) -> list[dict[str, object]]:
        """Flat rows for reporting."""
        return [
            r.model_dump(exclude={"credit_rwa_by_class", "citations", "notes"})
            for r in self.regimes
        ]


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


def run_comparison(
    book: ReferenceBook,
    year: int,
    market_rwa_usd: float,
    securitisation_rwa_usd: float,
    capital_usd: dict[str, float],
    leverage_exposure_usd: float,
    gsib_method1_score_bps: float,
    us_gsib_rate: float,
    us_scb: float,
    regimes: dict[Jurisdiction, RegimeCalculator] | None = None,
) -> ComparisonResult:
    """Run the reference bank through every regime.

    Args:
        book: Reference inputs (USD $M).
        year: Reporting year (drives transitional schedules).
        market_rwa_usd: Market-risk RWA, held common (US FRTB-SA engine).
        securitisation_rwa_usd: Securitisation RWA, held common (US SEC-SA engine).
        capital_usd: {"cet1", "tier1", "total"} capital amounts ($M).
        leverage_exposure_usd: Leverage exposure measure ($M).
        gsib_method1_score_bps: BCBS-methodology score, used for the G-SIB
            bucket outside the US (BCBS SCO40 / RBC40 bucket table).
        us_gsib_rate: US surcharge rate (decimal) from 12 CFR 217.403.
        us_scb: US stress capital buffer (decimal).
        regimes: Calculators to use (default: :func:`default_regimes`).

    The bank uses standardised approaches everywhere, so pre-floor RWA equals
    standardised RWA and the floor cannot bind; :func:`floor_sensitivity`
    shows how it would bind for an internal-models bank.

    Returns:
        ComparisonResult.
    """
    from src.jurisdictions.bcbs.capital_stack import gsib_bucket_from_score, gsib_hla

    regimes = regimes or default_regimes(year)
    hla = gsib_hla(gsib_bucket_from_score(gsib_method1_score_bps))
    rows: list[RegimeComparison] = []
    for j, reg in regimes.items():
        ccy = REGIME_CURRENCY[j]
        k = usd_to_local(ccy)
        back = 1.0 / k
        notes: list[str] = []
        local = [scale_exposure(e, k) for e in book.exposures]
        cr = reg.credit_rwa(local)
        cls_of = {e.exposure_id: e.asset_class.value for e in book.exposures}
        by_class: dict[str, float] = {}
        for li in cr.line_items:
            by_class[cls_of[li.exposure_id]] = (
                by_class.get(cls_of[li.exposure_id], 0.0) + li.rwa * back
            )

        ccr_ead = ccr_rwa = 0.0
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
        sa_total = credit_rwa + ccr_rwa + cva_rwa + op_rwa + market_rwa_usd + securitisation_rwa_usd

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
                market_rwa=market_rwa_usd,
                securitisation_rwa=securitisation_rwa_usd,
                standardised_rwa=sa_total,
                modelled_rwa=modelled,
                floor_applies=fl.applies,
                floor_factor=fl.floor_factor,
                floor_add_on=fl.add_on * back,
                total_rwa=total,
                cet1_ratio=cet1,
                tier1_ratio=capital_usd["tier1"] / total,
                total_capital_ratio=capital_usd["total"] / total,
                leverage_ratio=capital_usd["tier1"] / leverage_exposure_usd,
                cet1_requirement=req.cet1_requirement,
                cet1_surplus=cet1 - req.cet1_requirement,
                leverage_requirement=req.leverage_minimum + req.leverage_buffer,
                citations={"output_floor": fl.citation, "op_risk": op.citation, **req.citations},
                notes=notes,
            )
        )
    return ComparisonResult(
        year=year,
        common_components=[
            "market risk RWA (US FRTB-SA engine)",
            "securitisation RWA (US SEC-SA engine)",
            "capital resources and leverage exposure measure",
        ],
        regimes=rows,
    )
