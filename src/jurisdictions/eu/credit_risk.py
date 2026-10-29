"""EU CRR3 standardised approach for credit risk (SA-CR).

Implements Part Three, Title II, Chapter 2 of Regulation (EU) No 575/2013 as
amended by Regulation (EU) 2024/1623 (CRR3), together with the CCFs of
Article 111 / Annex I, the Financial Collateral Comprehensive Method
(Articles 223-224, 228), unfunded-protection substitution (Article 235), the
supporting factors retained by CRR3 (Articles 501 and 501a) and the CRR3
transitional provisions that act on SA risk weights (Articles 495a, 495b(3),
495d) or on the output-floor S-TREA only (Article 465(3) and (5)).

Exposure classes (Article 112) are reached from the jurisdiction-neutral
:class:`~src.jurisdictions.base.AssetClass`. Regime-specific inputs that the
neutral model does not carry are read from ``SAExposure.flags``:

=================================== =====================================================
flag                                meaning (citation)
=================================== =====================================================
``eu_ecb``                          exposure to the ECB -- 0 % (Art. 114(3))
``eu_member_state``                 EU Member State sovereign / RGLA (Art. 114(4), 115(5))
``eu_international_org``            Article 118 international organisation -- 0 %
``eu_mdb_listed``                   Article 117(2) MDB -- 0 %
``eu_rgla``                         PSE input is a regional government / local authority (Art. 115)
``eu_treated_as_sovereign``         RGLA/PSE treated as its sovereign (Art. 115(2), 116(4))
``eu_not_domestic_currency``        institution exposure not in the obligor's domestic currency
                                    -- sovereign floor of Art. 121(3) last subparagraph
``eu_payroll_pension_loan``         Article 123(5) 35 % loan
``eu_erm2_pair``                    euro / ERM II pair -- no mismatch multiplier (Art. 123a(3))
``eu_re_counterparty_corporate``    RE obligor is a corporate (default False for RRE, True for CRE)
``eu_ipre_qualifying_natural_person`` Art. 124(2)(a)(ii)(2)-(4) condition met (natural person <= 4
                                    units, housing co-operative, public housing)
``eu_ipre_hard_test_met``           Art. 125(2)/126(2) third subparagraph loss-rate derogation
``eu_junior_lien_unknown_ranking``  Art. 124(6) 1,25 multiplier on IPRE junior liens
``eu_object_finance_high_quality``  Art. 495b(3) transitional 80 % object finance
``eu_infrastructure_501a``          Art. 501a criteria met (0,75; excludes the 80 % PF weight)
``eu_long_term_equity``             Art. 133(4) second subparagraph long-term holding (>= 3 years)
``eu_equity_central_bank``          Art. 133(6) 0 %
``eu_equity_grandfathered_495a3``   Art. 495a(3) grandfathered strategic participation
``eu_cash`` / ``eu_cash_in_collection`` / ``eu_gold``   Art. 134(3)-(4)
``eu_art5_10_exempt``               Art. 111(4) 0 % arrangement (Art. 5(10)(a)-(e))
``eu_collateral_fx_mismatch``       apply Hfx (Art. 223(2), 224 Table 4)
``eu_repo_style`` / ``eu_capital_market_txn``  liquidation period 5 / 10 days (Art. 224(2))
``eu_irb_pd_le_0_5pct``             IRB PD <= 0,5 % for the Art. 465(3) floor transitional
``eu_465_5_eligible``               Art. 465(5)/(8) met and Member State discretion exercised
=================================== =====================================================

References:
    - Regulation (EU) 2024/1623 (CRR3), Article 1 points (42)-(64), (112), (130),
      (134), (237), (242), (246)-(247), (255) and the Annex (Annex I)
    - Regulation (EU) No 575/2013 consolidated 09.07.2024 (unamended articles)

All monetary amounts in USD millions ($M) unless explicitly stated; EUR
thresholds of the Regulation are applied to the input amounts as stated
(the engine is currency-agnostic).
"""

from __future__ import annotations

from src.jurisdictions.base import (
    AssetClass,
    EquityType,
    Jurisdiction,
    OBSCategory,
    PFPhase,
    RatingBucket,
    RiskWeightResult,
    SAExposure,
    SCRAGrade,
)
from src.jurisdictions.eu import params as prm

_RE_CLASSES = (AssetClass.RESIDENTIAL_RE, AssetClass.COMMERCIAL_RE)
_CORPORATE_CLASSES = (
    AssetClass.CORPORATE,
    AssetClass.CORPORATE_SME,
    AssetClass.SPECIALISED_LENDING_PF,
    AssetClass.SPECIALISED_LENDING_OF,
    AssetClass.SPECIALISED_LENDING_CF,
)
_RETAIL_CLASSES = (
    AssetClass.RETAIL_REGULATORY,
    AssetClass.RETAIL_TRANSACTOR,
    AssetClass.RETAIL_OTHER,
)


def _flag(e: SAExposure, key: str, default: bool = False) -> bool:
    """Read a documented regime flag from ``SAExposure.flags`` (module docstring table)."""
    return bool(e.flags.get(key, default))


def _cqs(rating: RatingBucket) -> int | None:
    """Credit quality step for a rating bucket, ``None`` if unrated (Article 136)."""
    return prm.CQS_OF_RATING.get(rating)


# =========================================================================
#  Exposure-class risk weights
# =========================================================================


def sovereign_rw(e: SAExposure) -> tuple[float, str]:
    """Central government / central bank risk weight -- Article 114 (consolidated) and Article 118.

    ECB 0 % (114(3)); Member State domestic-currency 0 % (114(4)); Article 118
    international organisations 0 %; rated per Table 1 (114(2)); unrated 100 % (114(1)).
    """
    if _flag(e, "eu_ecb"):
        return prm.SOVEREIGN_RW_ECB, "CRR Art. 114(3)"
    if _flag(e, "eu_international_org"):
        return prm.INTERNATIONAL_ORG_RW, "CRR Art. 118"
    if _flag(e, "eu_member_state") and e.domestic_currency_funded:
        return prm.SOVEREIGN_RW_MS_DOMESTIC, "CRR Art. 114(4)"
    cqs = _cqs(e.rating)
    if cqs is None:
        return prm.SOVEREIGN_RW_UNRATED, "CRR Art. 114(1)"
    return prm.SOVEREIGN_RW_BY_CQS[cqs], "CRR Art. 114(2) Table 1"


def sovereign_rw_for_rating(rating: RatingBucket) -> float:
    """Risk weight of a sovereign with the given rating -- Article 114(1)-(2)."""
    cqs = _cqs(rating)
    return prm.SOVEREIGN_RW_UNRATED if cqs is None else prm.SOVEREIGN_RW_BY_CQS[cqs]


def pse_rw(e: SAExposure) -> tuple[float, str]:
    """RGLA / PSE risk weight -- Articles 115 and 116 (CRR3 points (45)-(46)).

    Treated as sovereign (115(2), 116(4)); Member State RGLA in domestic currency
    20 % (115(5)); rated per Article 115(-1) Table 1 (116(2) for PSEs); unrated by
    the sovereign's CQS per Table 2 (115(1) / 116(1)), 100 % if the sovereign is
    unrated; unrated PSE with original maturity <= 3 months 20 % (116(3)).
    """
    if _flag(e, "eu_treated_as_sovereign"):
        rw = sovereign_rw_for_rating(e.sovereign_rating)
        if _flag(e, "eu_member_state") and e.domestic_currency_funded:
            rw = prm.SOVEREIGN_RW_MS_DOMESTIC
        return rw, "CRR Art. 115(2) / 116(4) (treated as central government)"
    is_rgla = _flag(e, "eu_rgla")
    if is_rgla and _flag(e, "eu_member_state") and e.domestic_currency_funded:
        return prm.RGLA_RW_MS_DOMESTIC, "CRR Art. 115(5)"
    cqs = _cqs(e.rating)
    if cqs is not None:
        cite = "CRR Art. 115(-1) Table 1" if is_rgla else "CRR Art. 116(2) -> 115(-1) Table 1"
        return prm.RGLA_RW_RATED_BY_CQS[cqs], cite
    if (
        not is_rgla
        and e.original_maturity_months is not None
        and e.original_maturity_months <= prm.PSE_SHORT_TERM_MAX_MONTHS
    ):
        return prm.PSE_RW_SHORT_TERM, "CRR Art. 116(3)"
    sov_cqs = _cqs(e.sovereign_rating)
    if sov_cqs is None:
        rw = (
            prm.RGLA_RW_UNRATED_SOVEREIGN_UNRATED
            if is_rgla
            else prm.PSE_RW_UNRATED_SOVEREIGN_UNRATED
        )
        return rw, "CRR Art. 115(1) / 116(1) (sovereign unrated)"
    table = prm.RGLA_RW_UNRATED_BY_SOVEREIGN_CQS if is_rgla else prm.PSE_RW_UNRATED_BY_SOVEREIGN_CQS
    return table[sov_cqs], "CRR Art. 115(1) / 116(1) Table 2"


def mdb_rw(e: SAExposure) -> tuple[float, str]:
    """Multilateral development bank risk weight -- Article 117 (CRR3 point (47)) and Article
    118."""
    if _flag(e, "eu_mdb_listed"):
        return prm.MDB_RW_LISTED, "CRR Art. 117(2)"
    if _flag(e, "eu_international_org"):
        return prm.INTERNATIONAL_ORG_RW, "CRR Art. 118"
    cqs = _cqs(e.rating)
    if cqs is None:
        return prm.MDB_RW_UNRATED, "CRR Art. 117(1) (unrated)"
    return prm.MDB_RW_RATED_BY_CQS[cqs], "CRR Art. 117(1) Table 1"


def _short_term_cqs(e: SAExposure) -> int | None:
    """CQS of a short-term credit assessment (Article 131; mapping flagged TODO: VERIFY in
    params)."""
    if e.short_term_rating is None:
        return None
    return prm.SHORT_TERM_RATING_CQS[e.short_term_rating.value]


def _institution_is_short_term(e: SAExposure) -> bool:
    """Short-term test of Articles 120(2) and 121(3)(a): original maturity <= 3 months, or <= 6
    months trade."""
    m = e.original_maturity_months
    if m is None:
        return False
    if m <= prm.INSTITUTION_SHORT_TERM_MAX_MONTHS:
        return True
    return e.is_trade_related and m <= prm.INSTITUTION_TRADE_SHORT_TERM_MAX_MONTHS


def institution_rw(e: SAExposure) -> tuple[float, str]:
    """Institution risk weight -- Articles 120, 121 (CRR3 points (49)-(50)) and 131.

    Rated: Table 1 (120(1)); short-term Table 2 (120(2)); a short-term credit
    assessment governs the short-term exposure under Article 120(3)/131 Table 7.
    Unrated (SCRA, Article 121): Grade A 40 % (30 % if CET1 >= 14 % and leverage
    >= 5 %), Grade B 75 %, Grade C 150 %; short-term 20/50/150 %. An exposure not
    graded A or B is Grade C (121(1)(c)). Foreign-currency exposures are floored at
    the sovereign's risk weight except self-liquidating trade items <= 1 year
    (121(3) last subparagraph).
    """
    short_term = _institution_is_short_term(e)
    st_cqs = _short_term_cqs(e)
    cqs = _cqs(e.rating)
    if short_term and st_cqs is not None:
        return prm.SHORT_TERM_ASSESSMENT_RW_BY_CQS[st_cqs], "CRR Art. 120(3) / 131 Table 7"
    if cqs is not None:
        if short_term:
            return prm.INSTITUTION_RW_RATED_SHORT_TERM_BY_CQS[cqs], "CRR Art. 120(2) Table 2"
        return prm.INSTITUTION_RW_RATED_BY_CQS[cqs], "CRR Art. 120(1) Table 1"
    grade = (e.scra_grade or SCRAGrade.C).value
    if short_term:
        rw = prm.INSTITUTION_SCRA_RW_SHORT_TERM[grade]
        cite = "CRR Art. 121(3)(a) Table 1 (short-term)"
    elif grade == "A" and e.scra_grade_a_enhanced:
        rw, cite = prm.INSTITUTION_SCRA_RW_GRADE_A_ENHANCED, "CRR Art. 121(3)(b)"
    else:
        rw, cite = prm.INSTITUTION_SCRA_RW[grade], "CRR Art. 121(3)(c) Table 1"
    trade_le_1y = e.is_trade_related and (e.original_maturity_months or 99.0) <= 12.0
    if _flag(e, "eu_not_domestic_currency") and not trade_le_1y:
        floor = sovereign_rw_for_rating(e.sovereign_rating)
        if floor > rw:
            return floor, cite + " floored at sovereign RW (Art. 121(3) last subpara.)"
    return rw, cite


def covered_bond_rw(e: SAExposure) -> tuple[float, str]:
    """Covered bond risk weight -- Article 129(4)-(5) (CRR3 point (59)).

    Rated covered bonds per Table 1; unrated from the issuing institution's senior
    unsecured RW (the exposure's institution fields describe the issuer).
    """
    cqs = _cqs(e.rating)
    if e.covered_bond_rated and cqs is not None:
        return prm.COVERED_BOND_RW_RATED_BY_CQS[cqs], "CRR Art. 129(4) Table 1"
    issuer = e.model_copy(
        update={
            "rating": RatingBucket.UNRATED if e.covered_bond_rated else e.rating,
            "original_maturity_months": None,
            "is_trade_related": False,
        }
    )
    issuer_rw, _ = institution_rw(issuer)
    return prm.COVERED_BOND_RW_FROM_ISSUER_RW[
        round(issuer_rw, 4)
    ], f"CRR Art. 129(5) (issuer RW {issuer_rw:.0%})"


def corporate_rw(e: SAExposure) -> tuple[float, str]:
    """Corporate (incl. SME) risk weight -- Article 122 (CRR3 point (51)) and Article 131.

    Rated per Table 1 (20/50/75/100/150/150 %); unrated 100 % (122(2)). There is no
    85 % SME weight in the EU: SME relief comes from the Article 501 supporting factor.
    """
    st_cqs = _short_term_cqs(e)
    if st_cqs is not None:
        return prm.SHORT_TERM_ASSESSMENT_RW_BY_CQS[st_cqs], "CRR Art. 131 Table 7"
    cqs = _cqs(e.rating)
    if cqs is None:
        return prm.CORPORATE_RW_UNRATED, "CRR Art. 122(2)"
    return prm.CORPORATE_RW_RATED_BY_CQS[cqs], "CRR Art. 122(1) Table 1"


def specialised_lending_rw(e: SAExposure, year: int) -> tuple[float, str]:
    """Specialised lending risk weight -- Article 122a (CRR3 point (52)) and Article 495b(3).

    Rated (directly applicable assessment) per Table 1; unrated object/commodities
    finance 100 %; project finance pre-operational 130 %, operational 100 %, high-quality
    operational 80 % provided Article 501a is not applied. Unrated high-quality object
    finance may receive 80 % until 31 December 2032 (495b(3)), again only without 501a.
    A missing project phase is treated as pre-operational (conservative).
    """
    cqs = _cqs(e.rating)
    if cqs is not None:
        return prm.SL_RW_RATED_BY_CQS[cqs], "CRR Art. 122a(2) Table 1"
    no_501a = not _flag(e, "eu_infrastructure_501a")
    if e.asset_class == AssetClass.SPECIALISED_LENDING_OF:
        if (
            _flag(e, "eu_object_finance_high_quality")
            and no_501a
            and year <= prm.SL_OF_HIGH_QUALITY_TRANSITIONAL_END_YEAR
        ):
            return prm.SL_RW_OF_HIGH_QUALITY_TRANSITIONAL, "CRR Art. 495b(3)"
        return prm.SL_RW_OBJECT_FINANCE, "CRR Art. 122a(3)(a)"
    if e.asset_class == AssetClass.SPECIALISED_LENDING_CF:
        return prm.SL_RW_COMMODITIES_FINANCE, "CRR Art. 122a(3)(b)"
    phase = e.pf_phase or PFPhase.PRE_OPERATIONAL
    if phase == PFPhase.PRE_OPERATIONAL:
        return prm.SL_RW_PF_PRE_OPERATIONAL, "CRR Art. 122a(3)(c)(i)"
    if phase == PFPhase.HIGH_QUALITY_OPERATIONAL and no_501a:
        return prm.SL_RW_PF_OPERATIONAL_HIGH_QUALITY, "CRR Art. 122a(3)(c)(ii)"
    return prm.SL_RW_PF_OPERATIONAL, "CRR Art. 122a(3)(c)(iii)"


def _retail_criteria_met(e: SAExposure) -> bool:
    """Article 123(1) retail criteria (incl. the EUR 1 million aggregate limit of point (b))."""
    if not e.meets_regulatory_retail_criteria:
        return False
    agg = e.aggregate_retail_exposure_to_obligor
    return agg is None or agg <= prm.RETAIL_MAX_AGGREGATE_EUR_M


def retail_rw(e: SAExposure) -> tuple[float, str]:
    """Retail risk weight -- Article 123 (CRR3 point (53)).

    75 % (123(3)); transactors 45 % (123(3)); payroll/pension-backed loans 35 %
    (123(5)); natural persons failing the 123(1) criteria 100 % (123(4)); SMEs failing
    them fall back to the corporate treatment (Article 122(2), 100 % unrated).
    """
    if e.asset_class == AssetClass.RETAIL_OTHER or not _retail_criteria_met(e):
        if e.is_sme and e.asset_class != AssetClass.RETAIL_OTHER:
            rw, cite = corporate_rw(e)
            return rw, cite + " (SME not meeting Art. 123(1))"
        return prm.RETAIL_NON_QUALIFYING_NATURAL_PERSON_RW, "CRR Art. 123(4)"
    if _flag(e, "eu_payroll_pension_loan"):
        return prm.RETAIL_PAYROLL_PENSION_LOAN_RW, "CRR Art. 123(5)"
    if e.asset_class == AssetClass.RETAIL_TRANSACTOR or e.is_transactor:
        return prm.RETAIL_TRANSACTOR_RW, "CRR Art. 123(3) (transactor)"
    return prm.RETAIL_RW, "CRR Art. 123(3)"


def _re_counterparty_rw(e: SAExposure) -> tuple[float, str]:
    """Risk weight 'as an exposure to the counterparty' -- Articles 124(1)(a), 125(1), 126(1).

    Corporate obligors per Article 122; natural persons / SMEs per Article 123 (75 % if
    the retail criteria are met, else 100 %). The RRE default is a natural person and
    the CRE default a corporate (flag ``eu_re_counterparty_corporate`` overrides).
    """
    default_corp = e.asset_class == AssetClass.COMMERCIAL_RE
    if _flag(e, "eu_re_counterparty_corporate", default_corp):
        return corporate_rw(e)
    if e.meets_regulatory_retail_criteria:
        return prm.RETAIL_RW, "CRR Art. 123(3)"
    return prm.RETAIL_NON_QUALIFYING_NATURAL_PERSON_RW, "CRR Art. 123(4)"


def _property_value(e: SAExposure, gross_exposure: float) -> float | None:
    """Property value: the input value, else implied by the LTV (Article 124(6) ETV = gross /
    value)."""
    if e.property_value is not None and e.property_value > 0:
        return e.property_value
    if e.ltv is not None and e.ltv > 0 and gross_exposure > 0:
        return gross_exposure / e.ltv
    return None


def _etv(e: SAExposure, gross_exposure: float) -> float:
    """Exposure-to-value ratio -- Article 124(6); unknown ETV -> top bucket (conservative)."""
    if e.ltv is not None:
        return e.ltv
    if e.property_value:
        return gross_exposure / e.property_value
    return float("inf")


def _band_rw(etv: float, bands: tuple[tuple[float, float], ...]) -> tuple[float, bool]:
    """Look up an ETV band (upper bounds inclusive); returns (RW, is_lowest_bucket)."""
    for idx, (upper, rw) in enumerate(bands):
        if etv <= upper:
            return rw, idx == 0
    return bands[-1][1], False


def loan_splitting_rw(
    e: SAExposure,
    exposure_amount: float,
    secured_rw: float,
    share: float = prm.RE_SECURED_SHARE_OF_PROPERTY_VALUE,
) -> tuple[float, list[str]]:
    """Blended RW under the loan-splitting approach -- Articles 125(1) and 126(1).

    The part up to ``share`` (55 %) of the property value takes ``secured_rw``
    (20 % RRE / 60 % CRE); the remainder takes the counterparty risk weight.
    Without a property value or LTV the whole exposure is weighted as unsecured.
    Senior / pari-passu liens held by third parties are not modelled (the
    neutral model does not carry their amounts) -- the institution is assumed
    to hold the first lien (Article 124(3)(b)).
    """
    cp_rw, cp_cite = _re_counterparty_rw(e)
    notes = [f"remainder weighted as counterparty: {cp_cite}"]
    if exposure_amount <= 0:
        return secured_rw, notes
    pv = _property_value(e, exposure_amount)
    if pv is None:
        notes.append("no property value / LTV: whole exposure weighted as unsecured (conservative)")
        return cp_rw, notes
    secured = min(exposure_amount, share * pv)
    blended = (secured * secured_rw + (exposure_amount - secured) * cp_rw) / exposure_amount
    notes.append(f"secured part {secured:.4f} of {exposure_amount:.4f} at {secured_rw:.0%}")
    return blended, notes


def _is_ipre(e: SAExposure) -> bool:
    """IPRE test: repayment materially dependent on property cash flows (Art. 124(2))."""
    return e.is_cash_flow_dependent


def _rre_ipre_treated_as_non_ipre(e: SAExposure) -> bool:
    """Article 124(2)(a)(ii): RRE IPRE treated under Article 125(1) (primary residence etc.)."""
    return e.is_owner_occupied or _flag(e, "eu_ipre_qualifying_natural_person")


def real_estate_rw(e: SAExposure, exposure_amount: float) -> tuple[float, str, list[str]]:
    """Immovable-property risk weight -- Articles 124-126 (CRR3 point (55)).

    * Not meeting Art. 124(3): non-IPRE -> counterparty RW, IPRE -> 150 % (124(1)).
    * RRE non-IPRE (and IPRE meeting 124(2)(a)(ii)) -> loan-splitting 20 % up to 55 % (125(1)).
    * RRE IPRE -> Table 1 of 125(2) by ETV; CRE non-IPRE -> 60 % up to 55 % (126(1));
      CRE IPRE -> Table 1 of 126(2). The loss-rate 'hard test' derogation routes IPRE
      to paragraph 1 (flag ``eu_ipre_hard_test_met``).
    * IPRE junior lien with unknown ranking: x1,25 unless lowest bucket, capped at 150 % (124(6)).
    """
    residential = e.asset_class == AssetClass.RESIDENTIAL_RE
    ipre = _is_ipre(e)
    if not e.is_regulatory_real_estate:
        if ipre:
            return prm.RE_NON_QUALIFYING_IPRE_RW, "CRR Art. 124(1)(b)", []
        rw, cite = _re_counterparty_rw(e)
        return rw, f"CRR Art. 124(1)(a) -> {cite}", []
    if residential:
        if not ipre or _rre_ipre_treated_as_non_ipre(e) or _flag(e, "eu_ipre_hard_test_met"):
            rw, notes = loan_splitting_rw(e, exposure_amount, prm.RRE_SECURED_PART_RW)
            return rw, "CRR Art. 125(1) (loan-splitting)", notes
        bands, cite = prm.RRE_IPRE_ETV_BANDS, "CRR Art. 125(2) Table 1"
    else:
        if not ipre or _flag(e, "eu_ipre_hard_test_met"):
            rw, notes = loan_splitting_rw(e, exposure_amount, prm.CRE_SECURED_PART_RW)
            return rw, "CRR Art. 126(1) (loan-splitting)", notes
        bands, cite = prm.CRE_IPRE_ETV_BANDS, "CRR Art. 126(2) Table 1"
    rw, lowest = _band_rw(_etv(e, exposure_amount), bands)
    lien_notes: list[str] = []
    if _flag(e, "eu_junior_lien_unknown_ranking") and not lowest:
        rw = min(rw * prm.IPRE_JUNIOR_LIEN_MULTIPLIER, prm.RE_NON_QUALIFYING_IPRE_RW)
        lien_notes.append("junior-lien multiplier 1,25 capped at 150 % (Art. 124(6))")
    return rw, cite, lien_notes


def adc_rw(e: SAExposure) -> tuple[float, str]:
    """Land acquisition, development and construction -- Article 126a (CRR3 point (56))."""
    if e.is_adc_presold_or_equity_at_risk:
        return prm.ADC_RESIDENTIAL_QUALIFYING_RW, "CRR Art. 126a(2)"
    return prm.ADC_RW, "CRR Art. 126a(1)"


def defaulted_rw(e: SAExposure) -> tuple[float, str]:
    """Exposures in default -- Article 127.

    Non-IPRE RRE/CRE 100 % (127(3), CRR3); otherwise 150 % where specific credit
    risk adjustments are < 20 % of the unsecured part, 100 % otherwise (127(1),
    consolidated). ``specific_provision_pct`` is read as the CRA share of the
    unsecured part before adjustments.
    """
    if e.asset_class in _RE_CLASSES and not _is_ipre(e) and e.is_regulatory_real_estate:
        return prm.DEFAULTED_NON_IPRE_RE_RW, "CRR Art. 127(3)"
    if e.specific_provision_pct < prm.DEFAULTED_PROVISION_THRESHOLD:
        return prm.DEFAULTED_RW_LOW_PROVISIONS, "CRR Art. 127(1)(a)"
    return prm.DEFAULTED_RW_HIGH_PROVISIONS, "CRR Art. 127(1)(b)"


def equity_rw(e: SAExposure, year: int) -> tuple[float, str]:
    """Equity risk weight with the CRR3 phase-in -- Articles 133, 48(4) and 495a.

    Final weights: 250 % (133(3)); 400 % speculative unlisted unless a long-term
    holding (133(4)); 100 % legislative programmes (133(5)); 0 % central banks (133(6));
    250 % for non-deducted significant FSE holdings (48(4)). Until 2029 the higher
    of the 8 July 2024 weight (100 % general / 150 % high-risk, capped at 250 % for
    133(3)) and the 495a(1)/(2) schedules applies; 495a(3) grandfathering keeps the
    legacy 100 %.
    """
    etype = e.equity_type or EquityType.GENERAL
    if _flag(e, "eu_equity_central_bank"):
        return prm.EQUITY_RW_CENTRAL_BANK, "CRR Art. 133(6)"
    if etype == EquityType.SIGNIFICANT_FI:
        return prm.EQUITY_RW_NOT_DEDUCTED_FSE, "CRR Art. 48(4)"
    if etype == EquityType.LEGISLATIVE_PROGRAMME:
        return prm.EQUITY_RW_LEGISLATIVE_PROGRAMME, "CRR Art. 133(5)"
    speculative = etype == EquityType.SPECULATIVE_UNLISTED and not _flag(e, "eu_long_term_equity")
    if _flag(e, "eu_equity_grandfathered_495a3"):
        return prm.EQUITY_LEGACY_RW_GENERAL, "CRR Art. 495a(3) (grandfathered, legacy Art. 133(2))"
    if speculative:
        final, schedule, cite = (
            prm.EQUITY_RW_SPECULATIVE_UNLISTED,
            prm.EQUITY_PHASE_IN_SPECULATIVE,
            "133(4)",
        )
        legacy = prm.EQUITY_LEGACY_RW_HIGH_RISK
        sched_cite = "495a(2)"
    else:
        final, schedule, cite = prm.EQUITY_RW_GENERAL, prm.EQUITY_PHASE_IN_GENERAL, "133(3)"
        legacy = min(prm.EQUITY_LEGACY_RW_GENERAL, prm.EQUITY_LEGACY_RW_CAP_495A1)
        sched_cite = "495a(1)"
    if year < prm.OUTPUT_FLOOR_FIRST_YEAR:
        return legacy, "pre-CRR3 legacy weight (Art. 133(2)/128 as applicable on 8 July 2024)"
    if year in schedule:
        return max(
            legacy, schedule[year]
        ), f"CRR Art. {sched_cite} ({year} phase-in of Art. {cite})"
    return final, f"CRR Art. {cite}"


def other_assets_rw(e: SAExposure) -> tuple[float, str]:
    """Other items -- Article 134 (paragraph 3 replaced by CRR3) and Article 113(5)."""
    if _flag(e, "eu_cash"):
        return prm.OTHER_ITEMS_CASH_RW, "CRR Art. 134(3)"
    if _flag(e, "eu_cash_in_collection"):
        return prm.OTHER_ITEMS_CASH_IN_COLLECTION_RW, "CRR Art. 134(3)"
    if _flag(e, "eu_gold"):
        return prm.OTHER_ITEMS_GOLD_RW, "CRR Art. 134(4)"
    return prm.OTHER_ITEMS_TANGIBLE_RW, "CRR Art. 134(1)-(2) / 113(5)"


def currency_mismatch_applies(e: SAExposure) -> bool:
    """Article 123a: natural-person retail / RRE exposures not in the currency of the income.

    Applies to retail classes (other than SMEs) and to residential RE where the
    obligor is not a corporate; not to euro / ERM II pairs (123a(3)).
    """
    if e.currency_matches_borrower_income or _flag(e, "eu_erm2_pair"):
        return False
    if e.asset_class in _RETAIL_CLASSES:
        return not e.is_sme
    if e.asset_class == AssetClass.RESIDENTIAL_RE:
        return not e.is_sme and not _flag(e, "eu_re_counterparty_corporate")
    return False


def apply_currency_mismatch(rw: float) -> float:
    """Article 123a(1): RW x 1,5 capped at 150 %."""
    return min(rw * prm.CURRENCY_MISMATCH_MULTIPLIER, prm.CURRENCY_MISMATCH_RW_CAP)


def obligor_risk_weight(
    e: SAExposure, year: int, exposure_amount: float
) -> tuple[float, str, str, list[str]]:
    """Risk weight of the obligor before CRM substitution and supporting factors.

    Returns ``(rw, regime_exposure_class, citation, notes)``; the currency-mismatch
    multiplier of Article 123a is included. Dispatches on the Article 112 class.
    """
    notes: list[str] = []
    ac = e.asset_class
    if e.is_defaulted or ac == AssetClass.DEFAULTED:
        rw, cite = defaulted_rw(e)
        cls = "Art. 112(j) exposures in default"
    elif ac == AssetClass.SOVEREIGN:
        rw, cite = sovereign_rw(e)
        cls = "Art. 112(a) central governments or central banks"
    elif ac == AssetClass.PSE:
        rw, cite = pse_rw(e)
        cls = "Art. 112(b) RGLA" if _flag(e, "eu_rgla") else "Art. 112(c) public sector entities"
    elif ac == AssetClass.MDB:
        rw, cite = mdb_rw(e)
        cls = "Art. 112(d)/(e) MDBs / international organisations"
    elif ac == AssetClass.BANK:
        rw, cite = institution_rw(e)
        cls = "Art. 112(f) institutions"
    elif ac == AssetClass.COVERED_BOND:
        rw, cite = covered_bond_rw(e)
        cls = "Art. 112(l) covered bonds"
    elif ac in (AssetClass.CORPORATE, AssetClass.CORPORATE_SME):
        rw, cite = corporate_rw(e)
        cls = "Art. 112(g) corporates"
    elif ac in (
        AssetClass.SPECIALISED_LENDING_PF,
        AssetClass.SPECIALISED_LENDING_OF,
        AssetClass.SPECIALISED_LENDING_CF,
    ):
        rw, cite = specialised_lending_rw(e, year)
        cls = "Art. 112(g) corporates -- specialised lending (Art. 122a)"
    elif ac == AssetClass.SUBORDINATED_DEBT:
        rw, cite = prm.SUBORDINATED_DEBT_RW, "CRR Art. 128(2)"
        cls = "Art. 112(k) subordinated debt exposures"
    elif ac == AssetClass.EQUITY:
        rw, cite = equity_rw(e, year)
        cls = "Art. 112(p) equity exposures"
    elif ac in _RETAIL_CLASSES:
        rw, cite = retail_rw(e)
        cls = "Art. 112(h) retail exposures"
    elif ac in _RE_CLASSES:
        rw, cite, notes = real_estate_rw(e, exposure_amount)
        cls = "Art. 112(i) secured by mortgages on immovable property"
    elif ac == AssetClass.LAND_ADC:
        rw, cite = adc_rw(e)
        cls = "Art. 112(i) ADC exposures"
    elif ac == AssetClass.OTHER_ASSETS:
        rw, cite = other_assets_rw(e)
        cls = "Art. 112(q) other items"
    else:  # pragma: no cover - every AssetClass is handled above
        rw, cite, cls = prm.RESIDUAL_RW, "CRR Art. 113(5)", "residual"
    if currency_mismatch_applies(e):
        rw = apply_currency_mismatch(rw)
        cite += "; x1,5 currency mismatch (Art. 123a)"
    return rw, cls, cite, notes


# =========================================================================
#  Credit conversion factors -- Article 111 / Annex I / Article 495d
# =========================================================================


def ucc_transitional_factor(year: int) -> float:
    """Article 495d(1): factor on the bucket-5 percentage (0 % to 2029, then 25/50/75 %, 100 %
    from 2033)."""
    if year < min(prm.UCC_TRANSITIONAL_FACTOR):
        return prm.UCC_TRANSITIONAL_FACTOR[min(prm.UCC_TRANSITIONAL_FACTOR)]
    return prm.UCC_TRANSITIONAL_FACTOR.get(year, 1.0)


def obs_bucket(e: SAExposure) -> int:
    """Annex I bucket for the exposure's off-balance-sheet category.

    A missing category is treated as bucket 1 (Annex I 1(e), conservative); a
    transaction-related contingent flagged as trade-related falls in bucket 4 (4(a)(i)).
    """
    cat = e.obs_category or OBSCategory.OTHER_100
    if cat == OBSCategory.TRANSACTION_RELATED_CONTINGENT and e.is_trade_related:
        return prm.TRADE_FINANCE_CONTINGENT_BUCKET
    return prm.OBS_BUCKET[cat]


def ccf(e: SAExposure, year: int) -> tuple[float, str]:
    """Credit conversion factor -- Article 111(2) and (4), Annex I, Article 495d.

    Buckets 1-5 carry 100/50/40/20/10 %; bucket 5 is multiplied by the 495d factor.
    """
    if e.off_balance_notional <= 0 and e.obs_category is None:
        return 0.0, "no off-balance-sheet amount"
    if _flag(e, "eu_art5_10_exempt"):
        return prm.CCF_ARTICLE_5_10_EXEMPT, "CRR Art. 111(4) second subpara."
    bucket = obs_bucket(e)
    pct = prm.CCF_BY_BUCKET[bucket]
    if bucket == 5:
        factor = ucc_transitional_factor(year)
        return (
            pct * factor,
            f"CRR Art. 111(2)(e) x Art. 495d factor {factor:.0%} (Annex I bucket 5)",
        )
    return pct, f"CRR Art. 111(2) Annex I bucket {bucket}"


# =========================================================================
#  CRM -- Financial Collateral Comprehensive Method and substitution
# =========================================================================


def _maturity_band(years: float) -> str:
    """Residual-maturity band of Article 224(1) Table 1."""
    if years <= 1:
        return "M1"
    if years <= 3:
        return "M3"
    if years <= 5:
        return "M5"
    if years <= 10:
        return "M10"
    return "M10P"


def liquidation_period(e: SAExposure) -> int:
    """Liquidation period in business days -- Article 224(2): 20 secured lending, 5 repo, 10
    capital market."""
    if _flag(e, "eu_repo_style"):
        return prm.LIQUIDATION_PERIOD_REPO
    if _flag(e, "eu_capital_market_txn"):
        return prm.LIQUIDATION_PERIOD_CAPITAL_MARKET
    return prm.LIQUIDATION_PERIOD_SECURED_LENDING


def supervisory_haircut(key: str | None, days: int) -> float | None:
    """Supervisory volatility adjustment Hc -- Article 224(1) Tables 1-3 (CRR3 point (130)).

    Keys: ``CASH``, ``GOLD``, ``MAIN_INDEX_EQUITY``, ``OTHER_LISTED_EQUITY``;
    debt as ``<SOV|OTH|SEC>_<CQS1|CQS2_3>_<years>`` (e.g. ``SOV_CQS1_7``) or
    ``SOV_CQS4``; short-term assessments as ``ST_<SOV|OTH|SEC>_<CQS1|CQS2_3>``.
    Returns ``None`` for an unrecognised key (collateral then not recognised).
    """
    if key is None:
        return None
    col = prm.LIQUIDATION_PERIOD_INDEX[days]
    if key in prm.HAIRCUT_OTHER:
        return prm.HAIRCUT_OTHER[key][col]
    parts = key.split("_")
    try:
        if parts[0] == "ST":
            issuer, cqs = parts[1], "_".join(parts[2:])
            return prm.HAIRCUT_SHORT_TERM_DEBT[(issuer, cqs)][col]
        issuer = parts[0]
        if parts[1] == "CQS4":
            return prm.HAIRCUT_DEBT[(issuer, "CQS4", "ALL")][col]
        if parts[1] == "CQS1":
            cqs, years = "CQS1", float(parts[2])
        else:
            cqs, years = "CQS2_3", float(parts[3])
        return prm.HAIRCUT_DEBT[(issuer, cqs, _maturity_band(years))][col]
    except (KeyError, IndexError, ValueError):
        return None


def fccm_exposure(e: SAExposure, ccf_value: float) -> tuple[float, list[str]]:
    """Exposure value after the FCCM -- Articles 223(2)-(5), 224 and 228.

    E is the on-balance amount plus 100 % of the off-balance item (223(4)(a)).
    E* = max(0, E(1+He) - C(1-Hc-Hfx)) with He = 0 for loans; for off-balance
    items the Article 111 CCF applies to E* (228). E* is allocated pro rata
    between the drawn and undrawn parts.
    """
    notes: list[str] = []
    on, off = e.on_balance_amount, e.off_balance_notional
    plain = on + ccf_value * off
    c = e.financial_collateral_value
    if c <= 0:
        return plain, notes
    days = liquidation_period(e)
    hc = supervisory_haircut(e.collateral_haircut_class, days)
    if hc is None:
        notes.append("collateral not recognised: missing/unknown haircut class (conservative)")
        return plain, notes
    hfx = (
        prm.HAIRCUT_FX[prm.LIQUIDATION_PERIOD_INDEX[days]]
        if _flag(e, "eu_collateral_fx_mismatch")
        else 0.0
    )
    gross = on + off
    if gross <= 0:
        return 0.0, notes
    e_star = max(0.0, gross - c * (1.0 - hc - hfx))
    on_star = e_star * on / gross
    off_star = e_star * off / gross
    notes.append(f"FCCM: Hc={hc:.5f}, Hfx={hfx:.5f}, {days}-day, E*={e_star:.4f} (Art. 223(5))")
    return on_star + ccf_value * off_star, notes


def guarantor_risk_weight(e: SAExposure, year: int) -> float | None:
    """Risk weight of the protection provider for substitution -- Article 235.

    Built from ``guarantor_asset_class`` and ``guarantor_rating``; ``None`` if absent.
    """
    if e.guarantor_asset_class is None or e.guarantee_amount <= 0:
        return None
    g = SAExposure(
        exposure_id=f"{e.exposure_id}-guarantor",
        asset_class=e.guarantor_asset_class,
        rating=e.guarantor_rating,
        on_balance_amount=1.0,
        sovereign_rating=e.sovereign_rating,
        domestic_currency_funded=e.domestic_currency_funded,
        flags={
            k: v
            for k, v in e.flags.items()
            if k in ("eu_member_state", "eu_mdb_listed", "eu_international_org", "eu_ecb")
        },
    )
    rw, _, _, _ = obligor_risk_weight(g, year, 1.0)
    return rw


# =========================================================================
#  Supporting factors -- Articles 501 and 501a
# =========================================================================


def is_sme(e: SAExposure) -> bool:
    """SME test -- Article 5, point (9): annual turnover not exceeding EUR 50 million."""
    if e.annual_turnover is not None:
        return e.annual_turnover <= prm.SME_TURNOVER_THRESHOLD_EUR_M
    return e.is_sme or e.asset_class == AssetClass.CORPORATE_SME


def sme_supporting_factor(e_star: float) -> float:
    """Article 501(1) factor: [min(E*, 2.5)*0,7619 + max(E*-2.5, 0)*0,85] / E* (EUR millions)."""
    if e_star <= 0:
        return prm.SME_SF_FACTOR_BELOW
    below = min(e_star, prm.SME_SF_THRESHOLD_EUR_M) * prm.SME_SF_FACTOR_BELOW
    above = max(e_star - prm.SME_SF_THRESHOLD_EUR_M, 0.0) * prm.SME_SF_FACTOR_ABOVE
    return (below + above) / e_star


def supporting_factor(e: SAExposure, exposure_amount: float) -> tuple[float, str]:
    """Supporting factor applied to RWEA -- Articles 501 (SME) and 501a (infrastructure).

    501a (x0,75): corporate / specialised lending, non-defaulted, criteria met.
    501: non-defaulted SME exposures in the retail, corporate or immovable-property
    classes excluding ADC (501(2)(a) as amended by CRR3); E* is the total owed by
    the SME group (``aggregate_retail_exposure_to_obligor`` if given, else the
    exposure). Where both could apply only the 501a factor is used.
    # TODO: VERIFY -- the Regulation does not state whether Articles 501 and 501a
    # can be combined on one exposure; the engine applies only one (conservative).
    """
    if e.is_defaulted or e.asset_class in (AssetClass.DEFAULTED, AssetClass.LAND_ADC):
        return 1.0, ""
    if _flag(e, "eu_infrastructure_501a") and e.asset_class in _CORPORATE_CLASSES:
        return prm.INFRASTRUCTURE_SF, "Art. 501a infrastructure supporting factor 0,75"
    eligible = e.asset_class in _CORPORATE_CLASSES + _RETAIL_CLASSES + _RE_CLASSES
    if eligible and is_sme(e):
        e_star = e.aggregate_retail_exposure_to_obligor or exposure_amount
        f = sme_supporting_factor(e_star)
        return f, f"Art. 501 SME supporting factor {f:.4f} (E*={e_star:.4f})"
    return 1.0, ""


# =========================================================================
#  Output-floor (S-TREA) transitional risk weights -- Article 465(3), (5), (9)
# =========================================================================


def floor_transitional_rw(
    e: SAExposure, year: int, exposure_amount: float
) -> tuple[float, str] | None:
    """S-TREA-only transitional risk weights of Article 465.

    * 465(3): unrated corporates with IRB PD <= 0,5 % -> 65 % until 2032.
    * 465(5)/(9): Member State discretion for RRE meeting 465(8): 10 % up to 55 % of
      the property value until 2032; 45 % on the remainder up to 80 % until 2029,
      then 52,5 / 60 / 67,5 % in 2030-2032; balance at the counterparty RW.
    Returns ``None`` when no transitional applies.
    """
    if e.is_defaulted:
        return None
    if (
        e.asset_class in (AssetClass.CORPORATE, AssetClass.CORPORATE_SME)
        and e.rating == RatingBucket.UNRATED
        and _flag(e, "eu_irb_pd_le_0_5pct")
        and year <= prm.FLOOR_UNRATED_CORPORATE_END_YEAR
    ):
        return prm.FLOOR_UNRATED_CORPORATE_RW, "CRR Art. 465(3)"
    if (
        e.asset_class == AssetClass.RESIDENTIAL_RE
        and _flag(e, "eu_465_5_eligible")
        and year <= prm.FLOOR_RRE_SECURED_END_YEAR
        and exposure_amount > 0
        and (not _is_ipre(e) or _rre_ipre_treated_as_non_ipre(e))
        and e.is_regulatory_real_estate
    ):
        pv = _property_value(e, exposure_amount)
        if pv is None:
            return None
        part_a = min(exposure_amount, prm.RE_SECURED_SHARE_OF_PROPERTY_VALUE * pv)
        part_b = min(exposure_amount, prm.FLOOR_RRE_REMAINDER_SHARE * pv) - part_a
        rest = exposure_amount - part_a - part_b
        cp_rw, _ = _re_counterparty_rw(e)
        rw_b = prm.FLOOR_RRE_REMAINDER_RW[max(year, min(prm.FLOOR_RRE_REMAINDER_RW))]
        blended = (
            part_a * prm.FLOOR_RRE_SECURED_RW + part_b * rw_b + rest * cp_rw
        ) / exposure_amount
        return blended, f"CRR Art. 465(5)/(9) ({year}: 10 % / {rw_b:.1%})"
    return None


# =========================================================================
#  Assembly
# =========================================================================


def assign_risk_weight(
    e: SAExposure, year: int, for_output_floor: bool = False
) -> RiskWeightResult:
    """Full SA-CR assignment for one exposure -- Articles 111-134, 223-235, 501-501a.

    Steps: CCF (Art. 111) -> FCCM exposure value (Art. 223/228) -> obligor RW
    (Art. 114-134, 123a) -> substitution for the guaranteed part (Art. 235, only
    where beneficial) -> supporting factor on RWEA (Art. 501/501a). With
    ``for_output_floor`` the Article 465(3)/(5) S-TREA transitionals replace the
    obligor RW and, for 465(5)(b), the SME supporting factor is not applied.
    """
    ccf_value, ccf_cite = ccf(e, year)
    exposure, notes = fccm_exposure(e, ccf_value)
    rw, cls, cite, rw_notes = obligor_risk_weight(e, year, exposure)
    notes = notes + rw_notes + [f"CCF: {ccf_cite}"]
    floor_rre = False
    if for_output_floor:
        tr = floor_transitional_rw(e, year, exposure)
        if tr is not None:
            rw, cite = tr
            floor_rre = e.asset_class == AssetClass.RESIDENTIAL_RE
            notes.append("output-floor S-TREA transitional applied")
    rwa = exposure * rw
    g_rw = guarantor_risk_weight(e, year)
    if g_rw is not None and g_rw < rw and exposure > 0:
        covered = min(e.guarantee_amount, exposure)
        rwa = covered * g_rw + (exposure - covered) * rw
        notes.append(f"Art. 235 substitution: {covered:.4f} at guarantor RW {g_rw:.0%}")
    factor, sf_note = supporting_factor(e, exposure)
    if floor_rre and factor != 1.0:
        factor, sf_note = 1.0, "Art. 501 not applied (Art. 465(5)(b) condition)"
    if factor != 1.0:
        rwa *= factor
    if sf_note:
        notes.append(sf_note)
    eff_rw = rwa / exposure if exposure > 0 else rw
    return RiskWeightResult(
        exposure_id=e.exposure_id,
        jurisdiction=Jurisdiction.EU,
        regime_exposure_class=cls,
        risk_weight=eff_rw,
        ccf=ccf_value,
        exposure_amount=exposure,
        rwa=rwa,
        citation=cite,
        notes=notes,
    )
