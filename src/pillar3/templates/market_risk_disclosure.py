"""Pillar 3 market-risk templates MR1-MR3 (Basel Framework DIS50).

Basel Framework DIS50 ("Market risk") prescribes:

- Template MR1 -- Market risk under the standardised approach (mandatory for
  banks with any market-risk capital under the SA; semiannual; 12 rows).
- Template MR2 -- Market risk for banks using the IMA (quarterly; 16 rows x
  columns a-g; row 8 IMCC, row 12 green/amber desk capital, row 16 total
  per MAR33.43).
- Template MR3 -- Market risk under the simplified standardised approach
  (semiannual; 6 rows x 4 columns).

The pre-FRTB templates ("MR2 RWA flow statements", "MR3 IMA values", "MR4
VaR backtesting") no longer exist in DIS50; VaR-vs-P&L backtesting is now
part of the MR2 narrative and its column e (backtesting exceptions).

All amounts in USD millions ($M). RWA = 12.5 x capital requirement
(RBC20.4 / ERBA NPR § __.10).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

RWA_PER_UNIT_CAPITAL: float = 12.5
"""RWA = capital requirement x 12.5 (Basel Framework RBC20.4)."""


# =========================================================================
#  MR1 -- Market risk under the standardised approach (DIS50, Template MR1)
# =========================================================================

MR1_ROWS: tuple[str, ...] = (
    "General interest rate risk",
    "Equity risk",
    "Commodity risk",
    "Foreign exchange risk",
    "Credit spread risk - non-securitisations",
    "Credit spread risk - securitisations (non-correlation trading portfolio)",
    "Credit spread risk - securitisation (correlation trading portfolio)",
    "Default risk - non-securitisations",
    "Default risk - securitisations (non-correlation trading portfolio)",
    "Default risk - securitisations (correlation trading portfolio)",
    "Residual risk add-on",
    "Total",
)
"""Row labels of Template MR1 (DIS50), rows 1-12, column a."""


class MR1Row(BaseModel):
    """One MR1 row: column a capital requirement (plus RWA for convenience)."""

    row_number: int
    description: str
    capital_charge: float = 0.0
    rwa: float = 0.0


class Pillar3MR1(BaseModel):
    """Template MR1 (DIS50). Linkage: [MR1 12/a] = [OV1 21/c]."""

    template_id: str = Field(default="MR1")
    reporting_date: date
    entity_name: str = ""
    rows: list[MR1Row] = Field(default_factory=list)
    total_sbm_charge: float = 0.0
    total_drc_charge: float = 0.0
    total_rrao_charge: float = 0.0
    total_capital_charge: float = 0.0
    total_rwa: float = 0.0


def build_mr1(
    girr_charge: float = 0.0,
    csr_nonsec_charge: float = 0.0,
    csr_sec_nonctp_charge: float = 0.0,
    csr_sec_ctp_charge: float = 0.0,
    equity_charge: float = 0.0,
    commodity_charge: float = 0.0,
    fx_charge: float = 0.0,
    drc_nonsec_charge: float = 0.0,
    drc_sec_nonctp_charge: float = 0.0,
    drc_sec_ctp_charge: float = 0.0,
    rrao_charge: float = 0.0,
    reporting_date: date = date(2026, 3, 31),
    entity_name: str = "",
) -> Pillar3MR1:
    """Build Template MR1 in the DIS50 row order.

    Row 12 (Total) is the sum of rows 1-11, i.e. the SA capital requirement
    of MAR20.1 (SBM + DRC + RRAO).

    Reference: Basel Framework DIS50, Template MR1.
    """
    values = (girr_charge, equity_charge, commodity_charge, fx_charge, csr_nonsec_charge,
              csr_sec_nonctp_charge, csr_sec_ctp_charge, drc_nonsec_charge,
              drc_sec_nonctp_charge, drc_sec_ctp_charge, rrao_charge)
    total = sum(values)
    rows = [MR1Row(row_number=i + 1, description=MR1_ROWS[i], capital_charge=v,
                   rwa=v * RWA_PER_UNIT_CAPITAL) for i, v in enumerate(values)]
    rows.append(MR1Row(row_number=12, description=MR1_ROWS[11], capital_charge=total,
                       rwa=total * RWA_PER_UNIT_CAPITAL))
    sbm = sum(values[:7])
    drc = sum(values[7:10])
    return Pillar3MR1(reporting_date=reporting_date, entity_name=entity_name, rows=rows,
                      total_sbm_charge=sbm, total_drc_charge=drc, total_rrao_charge=rrao_charge,
                      total_capital_charge=total, total_rwa=total * RWA_PER_UNIT_CAPITAL)


# =========================================================================
#  MR2 -- Market risk for banks using the IMA (DIS50, Template MR2)
# =========================================================================

class IMARiskMeasure(BaseModel):
    """Columns a-g of one MR2 row.

    a most recent; b/c/d average/high/low over the previous 60 days (ES, IMCC,
    SES) or 12 weeks (DRC); e number of backtesting exceptions (VaR 99.0%);
    f/g most recent and average at the previous quarter.
    """

    most_recent: float = 0.0
    average: float = 0.0
    high: float = 0.0
    low: float = 0.0
    backtesting_exceptions: Optional[int] = None
    prev_quarter_most_recent: float = 0.0
    prev_quarter_average: float = 0.0


class IMAInputs(BaseModel):
    """Inputs for Template MR2 (definitions per DIS50 MR2 instructions)."""

    unconstrained_es: IMARiskMeasure                      # row 1 (MAR33.1-33.12)
    es_girr: IMARiskMeasure = IMARiskMeasure()            # row 2
    es_equity: IMARiskMeasure = IMARiskMeasure()          # row 3
    es_commodity: IMARiskMeasure = IMARiskMeasure()       # row 4
    es_fx: IMARiskMeasure = IMARiskMeasure()              # row 5
    es_csr: IMARiskMeasure = IMARiskMeasure()             # row 6
    constrained_es: IMARiskMeasure                        # row 7 (MAR33.14)
    ses: IMARiskMeasure                                   # row 9 (MAR33.16-33.17)
    drc: IMARiskMeasure                                   # row 10 (MAR33.18)
    multiplier: float = Field(ge=1.5, description="m_c, MAR33.41 (1.5 plus backtesting add-on)")
    amber_desk_surcharge: float = 0.0                     # row 11 (MAR33.45)
    sa_ineligible_desks: float = 0.0                      # row 13 (= MR1 row 12)
    imcc_rho: float = Field(default=0.5, description="IMCC weight on unconstrained ES (MAR33.15)")
    ima_minus_sa_green_amber: float = 0.0                 # row 14 (IMA_G,A - SA_G,A, MAR33.45)
    sa_all_desks: float = 0.0                             # row 15 (MAR33.43, MAR11.8(1))


class MR2Row(BaseModel):
    """One MR2 row."""

    row_number: int
    description: str
    values: IMARiskMeasure = IMARiskMeasure()
    amount: float = 0.0
    """Single-value rows (11-16): the figure in column a."""


class Pillar3MR2(BaseModel):
    """Template MR2 (DIS50). Linkage: [MR2:16 - MR2:13] = [OV1 22/c]."""

    template_id: str = Field(default="MR2")
    reporting_date: date
    entity_name: str = ""
    rows: list[MR2Row] = Field(default_factory=list)
    imcc_most_recent: float = 0.0
    imcc_average: float = 0.0
    green_amber_capital: float = 0.0
    total_capital_charge: float = 0.0
    total_rwa: float = 0.0


def _imcc(rho: float, uncon: float, con: float) -> float:
    """IMCC = rho x unconstrained ES + (1 - rho) x constrained ES (MAR33.15; DIS50 MR2 row 8)."""
    return rho * uncon + (1.0 - rho) * con


def build_mr2(
    inputs: IMAInputs,
    reporting_date: date = date(2026, 3, 31),
    entity_name: str = "",
) -> Pillar3MR2:
    """Build Template MR2 for a bank using the IMA.

    Row 8 IMCC = 0.5 x unconstrained ES + 0.5 x constrained ES.
    Row 12 = max[8/a + 9/a; multiplier x 8/b + 9/b] + max[10/a; 10/b] + 11.
    Row 16 = min(12 + 13; 15) + max(0; 14).

    Reference: Basel Framework DIS50, Template MR2 definitions and
    instructions; MAR33.41-33.45.
    """
    i = inputs
    rho = i.imcc_rho
    imcc = IMARiskMeasure(
        most_recent=_imcc(rho, i.unconstrained_es.most_recent, i.constrained_es.most_recent),
        average=_imcc(rho, i.unconstrained_es.average, i.constrained_es.average),
        high=_imcc(rho, i.unconstrained_es.high, i.constrained_es.high),
        low=_imcc(rho, i.unconstrained_es.low, i.constrained_es.low),
        prev_quarter_most_recent=_imcc(rho, i.unconstrained_es.prev_quarter_most_recent,
                                       i.constrained_es.prev_quarter_most_recent),
        prev_quarter_average=_imcc(rho, i.unconstrained_es.prev_quarter_average,
                                   i.constrained_es.prev_quarter_average),
    )
    row12 = (max(imcc.most_recent + i.ses.most_recent, i.multiplier * imcc.average + i.ses.average)
             + max(i.drc.most_recent, i.drc.average) + i.amber_desk_surcharge)
    row16 = min(row12 + i.sa_ineligible_desks, i.sa_all_desks) + max(0.0, i.ima_minus_sa_green_amber)
    rows = [
        MR2Row(row_number=1, description="Unconstrained expected shortfall", values=i.unconstrained_es),
        MR2Row(row_number=2, description="ES - General interest rate risk", values=i.es_girr),
        MR2Row(row_number=3, description="ES - Equity risk", values=i.es_equity),
        MR2Row(row_number=4, description="ES - Commodity risk", values=i.es_commodity),
        MR2Row(row_number=5, description="ES - Foreign exchange risk", values=i.es_fx),
        MR2Row(row_number=6, description="ES - Credit spread risk", values=i.es_csr),
        MR2Row(row_number=7, description="Constrained expected shortfall", values=i.constrained_es),
        MR2Row(row_number=8, description="IMCC (0.5*Unconstrained ES+0.5*constrained risk class ES)",
               values=imcc),
        MR2Row(row_number=9, description="Capital requirement for non-modellable risk factors; SES",
               values=i.ses),
        MR2Row(row_number=10, description="Default risk capital requirement", values=i.drc),
        MR2Row(row_number=11, description="Capital surcharge for amber trading desks",
               amount=i.amber_desk_surcharge),
        MR2Row(row_number=12, description="Capital requirements for green and amber trading desks "
               "(including capital surcharge)", amount=row12),
        MR2Row(row_number=13, description="Total SA capital requirements for trading desks ineligible "
               "to use the IMA as reported in MR1", amount=i.sa_ineligible_desks),
        MR2Row(row_number=14, description="Difference in capital requirements under the IMA and SA for "
               "green and amber trading desks", amount=i.ima_minus_sa_green_amber),
        MR2Row(row_number=15, description="SA capital requirement for all trading desks (including "
               "those subject to IMA)", amount=i.sa_all_desks),
        MR2Row(row_number=16, description="Total market risk capital requirement: "
               "min(12+13; 15)+max(0,14)", amount=row16),
    ]
    return Pillar3MR2(reporting_date=reporting_date, entity_name=entity_name, rows=rows,
                      imcc_most_recent=imcc.most_recent, imcc_average=imcc.average,
                      green_amber_capital=row12, total_capital_charge=row16,
                      total_rwa=row16 * RWA_PER_UNIT_CAPITAL)


# =========================================================================
#  MR3 -- Market risk under the simplified standardised approach (DIS50)
# =========================================================================

MR3_ROWS: tuple[str, ...] = ("Interest rate risk", "Equity risk", "Commodity risk",
                             "Foreign exchange risk", "Securitisation", "Total")
MR3_COLUMNS: tuple[str, ...] = ("Outright products", "Options - Simplified approach",
                                "Options - Delta-plus method", "Options - Scenario approach")


class MR3Row(BaseModel):
    """One MR3 row: columns a-d (MAR40 capital requirements)."""

    row_number: int
    description: str
    outright: float = 0.0
    options_simplified: float = 0.0
    options_delta_plus: float = 0.0
    options_scenario: float = 0.0

    @property
    def total(self) -> float:
        """Row total across columns a-d."""
        return self.outright + self.options_simplified + self.options_delta_plus + self.options_scenario


class Pillar3MR3(BaseModel):
    """Template MR3 (DIS50)."""

    template_id: str = Field(default="MR3")
    reporting_date: date
    entity_name: str = ""
    rows: list[MR3Row] = Field(default_factory=list)
    total_capital_charge: float = 0.0
    total_rwa: float = 0.0


def build_mr3(
    by_risk: dict[str, tuple[float, float, float, float]],
    reporting_date: date = date(2026, 3, 31),
    entity_name: str = "",
) -> Pillar3MR3:
    """Build Template MR3 from MAR40 capital requirements by risk and product.

    Args:
        by_risk: {row label (rows 1-5 of MR3_ROWS): (outright, simplified,
            delta-plus, scenario)}.

    Reference: Basel Framework DIS50, Template MR3.
    """
    unknown = set(by_risk) - set(MR3_ROWS[:5])
    if unknown:
        raise ValueError(f"unknown MR3 rows: {sorted(unknown)}")
    rows: list[MR3Row] = []
    for n, label in enumerate(MR3_ROWS[:5], start=1):
        a, b, c, d = by_risk.get(label, (0.0, 0.0, 0.0, 0.0))
        rows.append(MR3Row(row_number=n, description=label, outright=a, options_simplified=b,
                           options_delta_plus=c, options_scenario=d))
    total = MR3Row(row_number=6, description="Total",
                   outright=sum(r.outright for r in rows),
                   options_simplified=sum(r.options_simplified for r in rows),
                   options_delta_plus=sum(r.options_delta_plus for r in rows),
                   options_scenario=sum(r.options_scenario for r in rows))
    rows.append(total)
    return Pillar3MR3(reporting_date=reporting_date, entity_name=entity_name, rows=rows,
                      total_capital_charge=total.total,
                      total_rwa=total.total * RWA_PER_UNIT_CAPITAL)
