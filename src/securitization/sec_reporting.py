"""Securitization Reporting — SEC1-SEC4 Pillar 3 Templates.

Generates regulatory disclosure reports for securitization exposures
under the Basel III Endgame framework, including:

- SEC1: Securitisation exposures in the banking book
- SEC2: Securitisation exposures in the trading book
- SEC3: Securitisation exposures in the banking book by approach
- SEC4: Securitisation exposures in the banking book by risk weight band

All monetary amounts in USD millions ($M) unless otherwise stated.

References:
    - BCBS d424 CRE40: Securitisation framework
    - Pillar 3 disclosure requirements: SEC1-SEC4 templates
    - FFIEC 101 Schedule A: Risk-weighted assets
    - US Basel III Endgame March 2026 Re-Proposal, Section IV
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from src.securitization.sec_framework import (
    SecResult,
    SecuritizationCalculator,
    SecuritizationPool,
    SecuritizationTranche,
)
from src.securitization.sec_params import (
    PILLAR3_SEC_TEMPLATES,
    SEC4_RW_BANDS,
    SecApproach,
    SecPoolAssetType,
)


# =========================================================================
#  SEC1 — Banking Book Exposures
# =========================================================================

class SEC1Row(BaseModel):
    """Single row in the SEC1 Pillar 3 template.

    SEC1 discloses securitization exposures by role (originator,
    investor, sponsor) and exposure type.

    Reference:
        Pillar 3 SEC1 template; CRE40.
    """
    row_number: int = Field(description="SEC1 row number")
    exposure_type: str = Field(description="Exposure type (e.g., RMBS, CLO)")
    role: str = Field(
        default="INVESTOR",
        description="Role: ORIGINATOR, INVESTOR, or SPONSOR"
    )
    outstanding_notional_usd_m: float = Field(
        description="Outstanding notional in $M"
    )
    ead_usd_m: float = Field(description="Exposure at default in $M")
    rwa_usd_m: float = Field(description="Risk-weighted assets in $M")
    capital_charge_usd_m: float = Field(
        description="Capital charge (RWA * 8%) in $M"
    )
    number_of_positions: int = Field(
        default=0, description="Number of securitization positions"
    )


class SEC1Report(BaseModel):
    """Complete SEC1 Pillar 3 report.

    Reference:
        Pillar 3 SEC1 template.
    """
    template_id: str = Field(default="SEC1")
    template_description: str = Field(
        default=PILLAR3_SEC_TEMPLATES.get("SEC1", "")
    )
    reporting_date: str = Field(description="Reporting date")
    entity_name: str = Field(description="Reporting entity")
    rows: list[SEC1Row] = Field(default_factory=list)
    total_notional_usd_m: float = Field(default=0.0)
    total_ead_usd_m: float = Field(default=0.0)
    total_rwa_usd_m: float = Field(default=0.0)
    total_capital_usd_m: float = Field(default=0.0)


# =========================================================================
#  SEC2 — Trading Book Exposures
# =========================================================================

class SEC2Row(BaseModel):
    """Single row in the SEC2 Pillar 3 template.

    SEC2 discloses securitization exposures in the trading book.

    Reference:
        Pillar 3 SEC2 template; CRE40.
    """
    row_number: int = Field(description="SEC2 row number")
    exposure_type: str = Field(description="Exposure type")
    is_ctp: bool = Field(
        default=False, description="Whether CTP position"
    )
    notional_usd_m: float = Field(description="Notional in $M")
    rwa_usd_m: float = Field(description="RWA in $M")
    capital_charge_usd_m: float = Field(description="Capital charge in $M")


class SEC2Report(BaseModel):
    """Complete SEC2 Pillar 3 report.

    Reference:
        Pillar 3 SEC2 template.
    """
    template_id: str = Field(default="SEC2")
    template_description: str = Field(
        default=PILLAR3_SEC_TEMPLATES.get("SEC2", "")
    )
    reporting_date: str = Field(description="Reporting date")
    entity_name: str = Field(description="Reporting entity")
    rows: list[SEC2Row] = Field(default_factory=list)
    total_notional_usd_m: float = Field(default=0.0)
    total_rwa_usd_m: float = Field(default=0.0)
    total_capital_usd_m: float = Field(default=0.0)


# =========================================================================
#  SEC3 — By Approach
# =========================================================================

class SEC3Row(BaseModel):
    """Single row in the SEC3 Pillar 3 template.

    SEC3 breaks down securitization exposures by approach used
    (SEC-IRBA, SEC-ERBA, SEC-SA).

    Reference:
        Pillar 3 SEC3 template; CRE40.3-40.5.
    """
    row_number: int = Field(description="SEC3 row number")
    approach: str = Field(description="Approach: SEC-IRBA, SEC-ERBA, SEC-SA")
    ead_usd_m: float = Field(description="EAD under this approach in $M")
    rwa_usd_m: float = Field(description="RWA under this approach in $M")
    capital_charge_usd_m: float = Field(description="Capital charge in $M")
    number_of_positions: int = Field(
        default=0, description="Number of positions"
    )
    average_rw: float = Field(
        default=0.0, description="Average risk weight"
    )


class SEC3Report(BaseModel):
    """Complete SEC3 Pillar 3 report.

    Reference:
        Pillar 3 SEC3 template.
    """
    template_id: str = Field(default="SEC3")
    template_description: str = Field(
        default=PILLAR3_SEC_TEMPLATES.get("SEC3", "")
    )
    reporting_date: str = Field(description="Reporting date")
    entity_name: str = Field(description="Reporting entity")
    rows: list[SEC3Row] = Field(default_factory=list)
    total_ead_usd_m: float = Field(default=0.0)
    total_rwa_usd_m: float = Field(default=0.0)
    total_capital_usd_m: float = Field(default=0.0)


# =========================================================================
#  SEC4 — By Risk Weight Band
# =========================================================================

class SEC4Row(BaseModel):
    """Single row in the SEC4 Pillar 3 template.

    SEC4 classifies securitization exposures by risk weight band.

    Reference:
        Pillar 3 SEC4 template; CRE40.44-46.
    """
    row_number: int = Field(description="SEC4 row number")
    rw_band: str = Field(description="Risk weight band label")
    rw_low: float = Field(description="Lower bound of RW band")
    rw_high: float = Field(description="Upper bound of RW band")
    ead_usd_m: float = Field(description="EAD in this band in $M")
    rwa_usd_m: float = Field(description="RWA in this band in $M")
    number_of_positions: int = Field(
        default=0, description="Number of positions in this band"
    )


class SEC4Report(BaseModel):
    """Complete SEC4 Pillar 3 report.

    Reference:
        Pillar 3 SEC4 template.
    """
    template_id: str = Field(default="SEC4")
    template_description: str = Field(
        default=PILLAR3_SEC_TEMPLATES.get("SEC4", "")
    )
    reporting_date: str = Field(description="Reporting date")
    entity_name: str = Field(description="Reporting entity")
    rows: list[SEC4Row] = Field(default_factory=list)
    total_ead_usd_m: float = Field(default=0.0)
    total_rwa_usd_m: float = Field(default=0.0)
    deduction_ead_usd_m: float = Field(
        default=0.0,
        description="EAD of positions at 1250% (deducted)"
    )


# =========================================================================
#  Report Generator
# =========================================================================

class SecReportGenerator:
    """Generates securitization regulatory reports (SEC1-SEC4).

    Produces Pillar 3 disclosure templates from securitization
    calculation results.

    Usage::

        calc = SecuritizationCalculator()
        result = calc.calculate(tranches, pool)
        gen = SecReportGenerator("Bank Name")
        sec3 = gen.generate_sec3(result, tranches, "2026-03-31")
        sec4 = gen.generate_sec4(result, tranches, "2026-03-31")

    Reference:
        Pillar 3 SEC1-SEC4 templates; CRE40.
    """

    def __init__(self, entity_name: str) -> None:
        """Initialize the report generator.

        Args:
            entity_name: Name of the reporting entity.
        """
        self._entity_name = entity_name

    def generate_sec1(
        self,
        result: SecResult,
        tranches: list[SecuritizationTranche],
        pools: list[SecuritizationPool],
        reporting_date: str,
        role: str = "INVESTOR",
    ) -> SEC1Report:
        """Generate SEC1 Pillar 3 report — banking book exposures.

        Groups securitization exposures by underlying asset type.

        Args:
            result: SecResult from the calculator.
            tranches: List of tranches.
            pools: List of pools.
            reporting_date: Reporting date string.
            role: Role of the institution (ORIGINATOR, INVESTOR, SPONSOR).

        Returns:
            Complete SEC1 report.

        Reference:
            Pillar 3 SEC1 template.
        """
        to_m = 1e-6

        # Build pool lookup
        pool_map = {p.pool_id: p for p in pools}

        # Group by asset type
        by_type: dict[str, list[SecuritizationTranche]] = {}
        for t in tranches:
            pool = pool_map.get(t.pool_id)
            asset_type = pool.asset_type if pool else "MIXED"
            by_type.setdefault(asset_type, []).append(t)

        rows: list[SEC1Row] = []
        total_notional = 0.0
        total_ead = 0.0
        total_rwa = 0.0
        total_capital = 0.0

        for i, (asset_type, type_tranches) in enumerate(sorted(by_type.items()), 1):
            notional = sum(t.notional for t in type_tranches)
            rwa = sum(
                result.rwa_by_tranche.get(t.tranche_id, 0.0)
                for t in type_tranches
            )
            capital = rwa * 0.08  # 8% minimum capital ratio

            rows.append(SEC1Row(
                row_number=i,
                exposure_type=asset_type,
                role=role,
                outstanding_notional_usd_m=notional * to_m,
                ead_usd_m=notional * to_m,  # Simplified: EAD = notional
                rwa_usd_m=rwa * to_m,
                capital_charge_usd_m=capital * to_m,
                number_of_positions=len(type_tranches),
            ))

            total_notional += notional
            total_ead += notional
            total_rwa += rwa
            total_capital += capital

        return SEC1Report(
            reporting_date=reporting_date,
            entity_name=self._entity_name,
            rows=rows,
            total_notional_usd_m=total_notional * to_m,
            total_ead_usd_m=total_ead * to_m,
            total_rwa_usd_m=total_rwa * to_m,
            total_capital_usd_m=total_capital * to_m,
        )

    def generate_sec3(
        self,
        result: SecResult,
        tranches: list[SecuritizationTranche],
        reporting_date: str,
    ) -> SEC3Report:
        """Generate SEC3 Pillar 3 report — by approach.

        Groups securitization exposures by calculation approach
        (SEC-IRBA, SEC-ERBA, SEC-SA).

        Args:
            result: SecResult from the calculator.
            tranches: List of tranches.
            reporting_date: Reporting date string.

        Returns:
            Complete SEC3 report.

        Reference:
            Pillar 3 SEC3 template; CRE40.3-40.5.
        """
        to_m = 1e-6

        # Group by approach
        by_approach: dict[str, list[SecuritizationTranche]] = {}
        for t in tranches:
            approach = result.approach_used.get(t.tranche_id, "SEC-SA")
            by_approach.setdefault(approach, []).append(t)

        rows: list[SEC3Row] = []
        total_ead = 0.0
        total_rwa = 0.0
        total_capital = 0.0

        for i, (approach, approach_tranches) in enumerate(sorted(by_approach.items()), 1):
            ead = sum(t.notional for t in approach_tranches)
            rwa = sum(
                result.rwa_by_tranche.get(t.tranche_id, 0.0)
                for t in approach_tranches
            )
            capital = rwa * 0.08
            avg_rw = rwa / ead if ead > 0 else 0.0

            rows.append(SEC3Row(
                row_number=i,
                approach=approach,
                ead_usd_m=ead * to_m,
                rwa_usd_m=rwa * to_m,
                capital_charge_usd_m=capital * to_m,
                number_of_positions=len(approach_tranches),
                average_rw=avg_rw,
            ))

            total_ead += ead
            total_rwa += rwa
            total_capital += capital

        return SEC3Report(
            reporting_date=reporting_date,
            entity_name=self._entity_name,
            rows=rows,
            total_ead_usd_m=total_ead * to_m,
            total_rwa_usd_m=total_rwa * to_m,
            total_capital_usd_m=total_capital * to_m,
        )

    def generate_sec4(
        self,
        result: SecResult,
        tranches: list[SecuritizationTranche],
        reporting_date: str,
    ) -> SEC4Report:
        """Generate SEC4 Pillar 3 report — by risk weight band.

        Classifies securitization exposures into risk weight bands
        for regulatory disclosure.

        Args:
            result: SecResult from the calculator.
            tranches: List of tranches.
            reporting_date: Reporting date string.

        Returns:
            Complete SEC4 report.

        Reference:
            Pillar 3 SEC4 template; CRE40.44-46.
        """
        to_m = 1e-6

        # Initialize band accumulators
        band_ead: dict[str, float] = {band[2]: 0.0 for band in SEC4_RW_BANDS}
        band_rwa: dict[str, float] = {band[2]: 0.0 for band in SEC4_RW_BANDS}
        band_count: dict[str, int] = {band[2]: 0 for band in SEC4_RW_BANDS}

        for t in tranches:
            rw = result.rw_by_tranche.get(t.tranche_id, 0.0)
            tranche_rwa = result.rwa_by_tranche.get(t.tranche_id, 0.0)

            for low, high, label in SEC4_RW_BANDS:
                if low == high == 12.50:
                    if rw >= 12.50:
                        band_ead[label] += t.notional
                        band_rwa[label] += tranche_rwa
                        band_count[label] += 1
                        break
                elif low <= rw < high:
                    band_ead[label] += t.notional
                    band_rwa[label] += tranche_rwa
                    band_count[label] += 1
                    break

        rows: list[SEC4Row] = []
        total_ead = 0.0
        total_rwa = 0.0
        deduction_ead = 0.0

        for i, (low, high, label) in enumerate(SEC4_RW_BANDS, 1):
            ead = band_ead[label]
            rwa = band_rwa[label]
            count = band_count[label]

            rows.append(SEC4Row(
                row_number=i,
                rw_band=label,
                rw_low=low,
                rw_high=high,
                ead_usd_m=ead * to_m,
                rwa_usd_m=rwa * to_m,
                number_of_positions=count,
            ))

            total_ead += ead
            total_rwa += rwa
            if low == high == 12.50:
                deduction_ead += ead

        return SEC4Report(
            reporting_date=reporting_date,
            entity_name=self._entity_name,
            rows=rows,
            total_ead_usd_m=total_ead * to_m,
            total_rwa_usd_m=total_rwa * to_m,
            deduction_ead_usd_m=deduction_ead * to_m,
        )
