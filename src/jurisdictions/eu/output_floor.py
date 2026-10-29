"""EU CRR3 output floor -- Article 92(3)-(6) and the Article 465 transitional arrangements.

* Article 92(3): TREA = max{U-TREA; x * S-TREA}, x = 72,5 %. A Member State may
  waive the floor on an individual basis for subsidiaries of a domestic parent
  that applies it on a consolidated basis (92(3) second subparagraph).
* Article 465(1): x = 50 % (2025), 55 % (2026), 60 % (2027), 65 % (2028),
  70 % (2029); 72,5 % from 2030.
* Article 465(2): until 31 December 2029 institutions may apply
  TREA = min{max{U-TREA; x * S-TREA}; 125 % * U-TREA} (formula printed as an image
  in the OJ, p.172; transcribed in the parameter reference).
* Article 465(3)-(5), (9), (13): S-TREA-only transitionals (unrated corporates 65 %,
  RRE 10 %/45 %..67,5 %, SA-CCR alpha = 1, SEC-SA p factors) -- the risk-weight
  parts are implemented in :func:`src.jurisdictions.eu.credit_risk.floor_transitional_rw`.

Directive side (CRD VI, Directive (EU) 2024/1619, applicable from 11 January 2026,
Article 2(1)): the final Directive contains NO numerical output-floor phase-in of
its own -- the phase-in is Article 465(1) CRR. What it adds is:

* Article 104a(6) CRD (CRD VI Article 1 point (39)(b)): an institution is "bound by
  the output floor" when TREA under Article 92(3) first subparagraph exceeds the
  un-floored TREA under Article 92(4). When it becomes bound, (a) the NOMINAL amount
  of the Pillar 2 requirement (other than for excessive leverage) shall not increase
  as a result, (b) the competent authority reviews and removes double counting by the
  next SREP, and (c) point (a) lapses once that review is complete; 104a(8): no P2R
  that double-counts risks covered by the floor while bound.
* Article 104b(4a): the competent authority may review P2G when the floor binds.
* Articles 131(6)(c) and 133(8)(d): O-SII buffer (annual review) and SyRB on total
  exposures (biennial review) to be re-calibrated when the institution becomes bound.

:func:`bound_by_output_floor` and :func:`p2r_rate_freeze` implement 104a(6); the
buffer reviews are supervisory acts with no formula and are reported as notes.

References:
    - Regulation (EU) 2024/1623, Article 1 points (28) and (237); Article 2
    - Directive (EU) 2024/1619, Article 1 points (39), (40), (44)(b), (45)(b); Article 2(1)
"""

from __future__ import annotations

from src.jurisdictions.base import Jurisdiction, OutputFloorResult
from src.jurisdictions.eu import params as prm


def floor_factor(year: int) -> float:
    """Factor x for a reporting year -- Article 92(3) and Article 465(1).

    Years before 2025 return 0 (CRR3 applies from 1 January 2025, Article 2).
    """
    if year < prm.OUTPUT_FLOOR_FIRST_YEAR:
        return 0.0
    return prm.OUTPUT_FLOOR_TRANSITIONAL.get(year, prm.OUTPUT_FLOOR_FACTOR)


def cap_available(year: int) -> bool:
    """Article 465(2): the 125 % of U-TREA cap is available until 31 December 2029."""
    return prm.OUTPUT_FLOOR_FIRST_YEAR <= year <= prm.OUTPUT_FLOOR_CAP_END_YEAR


def total_risk_exposure_amount(
    u_trea: float,
    s_trea: float,
    year: int,
    apply_transitional_cap: bool = True,
    individual_basis_waiver: bool = False,
) -> OutputFloorResult:
    """TREA under Article 92(3) with the Article 465(1)-(2) transitionals.

    ``apply_transitional_cap`` exercises the Article 465(2) option (an institution
    choice, 'may'); ``individual_basis_waiver`` reflects the Member State
    derogation of Article 92(3) second subparagraph (TREA = U-TREA).
    """
    x = floor_factor(year)
    notes: list[str] = []
    if individual_basis_waiver:
        return OutputFloorResult(
            jurisdiction=Jurisdiction.EU,
            applies=False,
            floor_factor=x,
            pre_floor_rwa=u_trea,
            standardised_rwa=s_trea,
            floored_rwa=u_trea,
            add_on=0.0,
            citation="CRR Art. 92(3) second subparagraph (Member State individual-basis waiver)",
            notes=["floor applied at the consolidated level of the domestic parent"],
        )
    if x == 0.0:
        return OutputFloorResult(
            jurisdiction=Jurisdiction.EU,
            applies=False,
            floor_factor=0.0,
            pre_floor_rwa=u_trea,
            standardised_rwa=s_trea,
            floored_rwa=u_trea,
            add_on=0.0,
            citation="CRR3 Art. 2 (applies from 1 January 2025)",
            notes=["output floor not in force before 2025"],
        )
    floored = max(u_trea, x * s_trea)
    cite = "CRR Art. 92(3)" + (
        f"; Art. 465(1) x = {x:.1%}" if year in prm.OUTPUT_FLOOR_TRANSITIONAL else ""
    )
    if apply_transitional_cap and cap_available(year):
        cap = prm.OUTPUT_FLOOR_CAP_MULTIPLE * u_trea
        if floored > cap:
            notes.append(f"Art. 465(2) cap binding: TREA limited to 125 % of U-TREA ({cap:.2f})")
        floored = min(floored, cap)
        cite += "; Art. 465(2) cap"
    return OutputFloorResult(
        jurisdiction=Jurisdiction.EU,
        applies=True,
        floor_factor=x,
        pre_floor_rwa=u_trea,
        standardised_rwa=s_trea,
        floored_rwa=floored,
        add_on=floored - u_trea,
        citation=cite,
        notes=notes,
    )


def saccr_alpha_for_s_trea(year: int, u_trea_uses_imm: bool) -> float:
    """Alpha in S-TREA -- Article 465(4): 1 until 31 December 2029 where U-TREA uses the IMM,
    else 1,4."""
    if u_trea_uses_imm and year <= prm.FLOOR_SA_CCR_ALPHA_END_YEAR:
        return prm.FLOOR_SA_CCR_ALPHA_TRANSITIONAL
    return prm.SACCR_ALPHA


def bound_by_output_floor(trea: float, u_trea: float) -> bool:
    """CRD Article 104a(6) last subparagraph (CRD VI): bound when TREA > un-floored TREA."""
    return trea > u_trea


def p2r_rate_freeze(
    p2r_rate: float, u_trea: float, trea: float, review_completed: bool = False
) -> tuple[float, list[str]]:
    """P2R rate (non-leverage) once the floor binds -- CRD Article 104a(6)(a)-(c) (CRD VI).

    Until the competent authority completes the 104a(6)(b) review, the nominal P2R
    amount may not increase because the institution became bound: the rate applied to
    the floored TREA is scaled to p2r_rate x U-TREA / TREA. After the review (104a(6)(c))
    the rate the authority sets applies (returned unchanged here).
    """
    notes: list[str] = []
    if not bound_by_output_floor(trea, u_trea) or review_completed:
        return p2r_rate, notes
    notes.append(
        "CRD Art. 104a(6)(a): nominal P2R frozen at the un-floored amount pending the "
        "104a(6)(b) review; O-SII (131(6)(c)) and SyRB (133(8)(d)) calibrations to be reviewed"
    )
    return p2r_rate * u_trea / trea, notes


def sec_sa_p_factor_for_s_trea(article: str, year: int) -> float | None:
    """SEC-SA p factor in S-TREA -- Article 465(13): 0,25 (Art. 262) / 0,5 (Art. 261) until 2032.

    Returns ``None`` after 2032 (the ordinary Article 261/262 p applies).
    """
    if year > prm.FLOOR_SEC_P_END_YEAR:
        return None
    return prm.FLOOR_SEC_P_FACTOR[article]
