"""EU CRR3 operational risk -- Part Three, Title III (Articles 311a-324), CRR3 point (155).

The EU own funds requirement for operational risk is the business indicator
component alone (Article 312): the BCBS loss component and internal loss
multiplier (OPE25.9-25.10) are not transposed, which is equivalent to an ILM
of 1 for every institution. Loss data are still collected (Articles 316-321)
for supervisory and disclosure purposes (Article 446) but do not enter the
calculation.

Formulas (CRR3, OJ pp.105-107; Articles 313 and 314(2) are printed as images
and transcribed in ``docs/jurisdictions/EU_parameter_reference.md``):

* BI   = ILDC + SC + FC                                   (Art. 314(1))
* ILDC = min(IC, 0,0225 x AC) + DC                         (Art. 314(2))
* SC   = max(OI, OE) + max(FI, FE)                         (Art. 314(5))
* FC   = TC + BC                                           (Art. 314(6))
* BIC  = 0,12 BI                       if BI <= 1           (Art. 313, EUR bn)
         0,12 + 0,15 (BI - 1)          if 1 < BI <= 30
         4,47 + 0,18 (BI - 30)         if BI > 30
* RWA  = 12,5 x own funds requirement                     (Art. 92(6)(b))

Input mapping from :class:`~src.jurisdictions.base.OpRiskInputs` (three annual
observations, $M): IC = mean |interest income - interest expense|; AC = mean
interest-earning assets; DC = mean dividend income; OI/OE/FI/FE = means of the
corresponding lists; TC/BC = mean absolute trading / banking book P&L. The BI
thresholds are in EUR billions; inputs are taken to be in the reporting
currency already converted (the engine is currency-agnostic) and divided by
1 000 to express them in billions.

References:
    - Regulation (EU) 2024/1623, Article 1 point (155) (new Title III)
    - Regulation (EU) No 575/2013, Article 92(6)(b) as replaced by CRR3 point (28)
"""

from __future__ import annotations

from statistics import fmean

from src.jurisdictions.base import Jurisdiction, OpRiskInputs, OpRiskResult
from src.jurisdictions.eu import params as prm

_MILLIONS_PER_BILLION = 1000.0


def interest_leases_dividend_component(inputs: OpRiskInputs) -> tuple[float, dict[str, float]]:
    """ILDC = min(IC, 0,0225 x AC) + DC in $M -- Article 314(2).

    IC is the annual average of the absolute values of (interest income - interest
    expense) over the last three financial years; AC is the average of the
    year-end interest-bearing assets; DC the average dividend income.
    """
    pairs = zip(inputs.interest_income, inputs.interest_expense, strict=True)
    ic = fmean(abs(i - x) for i, x in pairs)
    ac = fmean(inputs.interest_earning_assets)
    dc = fmean(inputs.dividend_income)
    ildc = min(ic, prm.ILDC_ASSET_CAP * ac) + dc
    return ildc, {"IC": ic, "AC": ac, "DC": dc, "ILDC": ildc}


def services_component(inputs: OpRiskInputs) -> tuple[float, dict[str, float]]:
    """SC = max(OI, OE) + max(FI, FE) in $M, three-year averages -- Article 314(5)."""
    oi = fmean(inputs.other_operating_income)
    oe = fmean(inputs.other_operating_expense)
    fi = fmean(inputs.fee_income)
    fe = fmean(inputs.fee_expense)
    sc = max(oi, oe) + max(fi, fe)
    return sc, {"OI": oi, "OE": oe, "FI": fi, "FE": fe, "SC": sc}


def financial_component(inputs: OpRiskInputs) -> tuple[float, dict[str, float]]:
    """FC = TC + BC in $M, averages of absolute annual net P&L -- Article 314(6)."""
    tc = fmean(abs(v) for v in inputs.net_pnl_trading_book)
    bc = fmean(abs(v) for v in inputs.net_pnl_banking_book)
    fc = tc + bc
    return fc, {"TC": tc, "BC": bc, "FC": fc}


def business_indicator(inputs: OpRiskInputs) -> tuple[float, dict[str, float]]:
    """BI = ILDC + SC + FC in $M -- Article 314(1)."""
    ildc, c1 = interest_leases_dividend_component(inputs)
    sc, c2 = services_component(inputs)
    fc, c3 = financial_component(inputs)
    bi = ildc + sc + fc
    return bi, {**c1, **c2, **c3, "BI": bi}


def business_indicator_component(bi_millions: float) -> float:
    """BIC in $M from BI in $M -- Article 313 (piecewise formula in EUR billions).

    0,12 BI (BI <= 1); 0,12 + 0,15 (BI - 1) (1 < BI <= 30); 4,47 + 0,18 (BI - 30) (BI > 30).
    """
    bi = bi_millions / _MILLIONS_PER_BILLION
    if bi <= prm.BIC_BUCKET_1_UPPER_EUR_BN:
        bic_bn = prm.BIC_COEFF_1 * bi
    elif bi <= prm.BIC_BUCKET_2_UPPER_EUR_BN:
        bic_bn = prm.BIC_COEFF_1 * prm.BIC_BUCKET_1_UPPER_EUR_BN + prm.BIC_COEFF_2 * (
            bi - prm.BIC_BUCKET_1_UPPER_EUR_BN
        )
    else:
        bic_bn = prm.BIC_CONSTANT_BUCKET_3_EUR_BN + prm.BIC_COEFF_3 * (
            bi - prm.BIC_BUCKET_2_UPPER_EUR_BN
        )
    return bic_bn * _MILLIONS_PER_BILLION


def loss_data_required(bi_millions: float) -> bool:
    """Article 316(1): annual operational risk loss must be calculated where BI >= EUR 750
    million."""
    return bi_millions >= prm.OPRISK_LOSS_DATA_BI_THRESHOLD_EUR_M


def operational_risk(inputs: OpRiskInputs) -> OpRiskResult:
    """Operational risk requirement = BIC; RWA = 12,5 x BIC -- Articles 312, 313, 92(6)(b).

    The loss history is reported (10-year average, Article 318(1) window) but has no
    capital effect: the EU has no loss component (ILM reported as 1).
    """
    bi, comps = business_indicator(inputs)
    bic = business_indicator_component(bi)
    losses = inputs.annual_operational_losses[-prm.OPRISK_LOSS_WINDOW_YEARS :]
    if losses:
        comps["avg_annual_loss_10y_disclosure_only"] = fmean(losses)
    comps["loss_data_collection_required"] = 1.0 if loss_data_required(bi) else 0.0
    return OpRiskResult(
        jurisdiction=Jurisdiction.EU,
        business_indicator=bi,
        bic=bic,
        loss_component=None,
        ilm=prm.OPRISK_ILM,
        capital=bic,
        rwa=prm.OWN_FUNDS_TO_RWA * bic,
        citation="CRR Art. 312-314 (CRR3 point (155)); RWA x12,5 per Art. 92(6)(b)",
        components=comps,
    )
