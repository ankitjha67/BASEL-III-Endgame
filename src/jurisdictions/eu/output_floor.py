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

The Directive-side transitional on the interaction of the floor with Pillar 2
and the combined buffer (the "OF-ADJ" mechanism and the CET1-based caps that
CRD VI introduced) is NOT in the source texts. # TODO: VERIFY -- the Directive
(EU) 2024/1619 amendments to Articles 104a and 128-131 CRD are needed to model
them; the engine reports the Regulation-level floor only.

References:
    - Regulation (EU) 2024/1623, Article 1 points (28) and (237); Article 2
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


def sec_sa_p_factor_for_s_trea(article: str, year: int) -> float | None:
    """SEC-SA p factor in S-TREA -- Article 465(13): 0,25 (Art. 262) / 0,5 (Art. 261) until 2032.

    Returns ``None`` after 2032 (the ordinary Article 261/262 p applies).
    """
    if year > prm.FLOOR_SEC_P_END_YEAR:
        return None
    return prm.FLOOR_SEC_P_FACTOR[article]
