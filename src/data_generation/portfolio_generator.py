"""Portfolio Generator — Synthetic portfolio data for a $3.2T Category I G-SIB.

Generates realistic credit, trading, counterparty, and securitization portfolios
with fixed random seeds for reproducibility.

All amounts in USD millions ($M).

References:
    - FR Y-14A Schedule H: Loan-level data
    - FR Y-14Q Schedule L: Counterparty data
    - FFIEC 101 Schedule A: RWA by exposure type
    - ERBA NPR pp. 100-130: Exposure classification
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# =========================================================================
#  Data Models
# =========================================================================

@dataclass
class CreditExposure:
    """Single credit exposure in the loan portfolio.

    Reference: FR Y-14A Schedule H.
    """
    exposure_id: str
    counterparty_name: str
    exposure_type: str  # SOVEREIGN, CORPORATE_IG, CORPORATE_HY, RETAIL_MTG, CRE, etc.
    rating: str
    sector: str
    ead: float  # $M
    risk_weight: float
    rwa: float  # $M
    maturity_years: float
    is_defaulted: bool = False
    collateral_value: float = 0.0
    collateral_type: str = ""
    ltv: float = 0.0


@dataclass
class CreditPortfolio:
    """Aggregated credit portfolio.

    Reference: FFIEC 101 Schedule A.
    """
    exposures: list[CreditExposure] = field(default_factory=list)
    total_ead: float = 0.0
    total_rwa: float = 0.0
    count: int = 0

    def summary_by_type(self) -> dict[str, dict[str, float]]:
        """Summarize portfolio by exposure type."""
        summary: dict[str, dict[str, float]] = {}
        for exp in self.exposures:
            if exp.exposure_type not in summary:
                summary[exp.exposure_type] = {"ead": 0.0, "rwa": 0.0, "count": 0}
            summary[exp.exposure_type]["ead"] += exp.ead
            summary[exp.exposure_type]["rwa"] += exp.rwa
            summary[exp.exposure_type]["count"] += 1
        return summary


@dataclass
class TradingPosition:
    """Single trading book position for FRTB.

    Reference: BCBS d457, ERBA NPR pp. 300-310.
    """
    position_id: str
    risk_class: str  # GIRR, CSR_NONSEC, EQUITY, COMMODITY, FX
    instrument_type: str
    notional: float  # $M
    currency: str = "USD"
    tenor: str = ""
    delta_sensitivity: float = 0.0
    vega_sensitivity: float = 0.0
    curvature_sensitivity: float = 0.0
    bucket: str = ""
    issuer: str = ""


@dataclass
class TradingBookPortfolio:
    """Aggregated trading book.

    Reference: BCBS d457 MAR10.
    """
    positions: list[TradingPosition] = field(default_factory=list)
    total_notional: float = 0.0

    def summary_by_risk_class(self) -> dict[str, float]:
        """Summarize notional by FRTB risk class."""
        summary: dict[str, float] = {}
        for pos in self.positions:
            summary[pos.risk_class] = summary.get(pos.risk_class, 0.0) + pos.notional
        return summary


@dataclass
class CounterpartyExposure:
    """Counterparty exposure for SA-CCR.

    Reference: ERBA NPR pp. 200-230, 12 CFR 217.132.
    """
    counterparty_id: str
    counterparty_name: str
    counterparty_type: str  # BANK, CORPORATE, SOVEREIGN, CCP
    rating: str
    netting_set_id: str
    replacement_cost: float  # $M
    pfe: float  # $M, potential future exposure
    ead: float  # $M
    alpha: float  # 1.4 financial, 1.0 commercial
    risk_weight: float
    rwa: float  # $M
    cva_charge: float = 0.0


@dataclass
class CounterpartyPortfolio:
    """Aggregated counterparty exposure portfolio.

    Reference: FR Y-14Q Schedule L.
    """
    exposures: list[CounterpartyExposure] = field(default_factory=list)
    total_ead: float = 0.0
    total_rwa: float = 0.0


@dataclass
class SecuritizationTranche:
    """Single securitization tranche.

    Reference: ERBA NPR pp. 160-180.
    """
    tranche_id: str
    deal_name: str
    asset_type: str  # RMBS, CMBS, CLO, ABS_AUTO, ABS_CARD
    approach: str  # SEC_ERBA, SEC_SA
    rating: str
    attachment: float
    detachment: float
    notional: float  # $M
    risk_weight: float
    rwa: float  # $M
    is_stc: bool = False


@dataclass
class SecuritizationPortfolio:
    """Aggregated securitization portfolio.

    Reference: FFIEC 101 Schedule A line 6.
    """
    tranches: list[SecuritizationTranche] = field(default_factory=list)
    total_notional: float = 0.0
    total_rwa: float = 0.0


# =========================================================================
#  Portfolio Generator
# =========================================================================

class PortfolioGenerator:
    """Synthetic portfolio generator for a $3.2T Category I G-SIB.

    Generates reproducible portfolios using fixed random seeds.
    Portfolio composition reflects typical large US bank:
    - Credit: ~$1.8T (sovereign 28%, IG corp 22%, HY corp 6%, retail 28%, CRE 6%, other 10%)
    - Trading: ~$500B notional across all FRTB risk classes
    - Counterparty: ~500 counterparties, ~$200B EAD
    - Securitization: ~$50B across RMBS, CMBS, CLO

    Reference: FR Y-9C, FR Y-14A, FFIEC 101.
    """

    def __init__(self, seed: int = 42) -> None:
        """Initialize with fixed random seed for reproducibility.

        Args:
            seed: Random seed for numpy.

        Reference: SR 11-7 — reproducibility requirement.
        """
        self.rng = np.random.default_rng(seed)

    def generate_credit_portfolio(self) -> CreditPortfolio:
        """Generate credit portfolio (~$1.8T across exposure types).

        Composition per FFIEC 101 Schedule A:
        - US Treasuries: $500B at 0% RW
        - Agency MBS: $300B at 20% RW
        - IG Corporate: $400B at 65% RW
        - HY Corporate: $100B at 100% RW
        - Retail Mortgage: $250B at 50% avg RW
        - Retail Revolving: $80B at 45% RW (transactor)
        - CRE: $100B at 150% RW
        - Other: $70B at 100% RW

        Returns:
            CreditPortfolio with individual exposures.

        Reference: FFIEC 101 Schedule A, ERBA NPR.
        """
        exposures: list[CreditExposure] = []
        config = [
            ("SOVEREIGN", "AAA", "government", 500_000.0, 0.00, 20),
            ("AGENCY_MBS", "AA+", "government", 300_000.0, 0.20, 15),
            ("CORPORATE_IG", "A", "corporate", 200_000.0, 0.65, 50),
            ("CORPORATE_IG", "BBB", "corporate", 200_000.0, 0.65, 60),
            ("CORPORATE_HY", "BB", "corporate", 60_000.0, 1.00, 30),
            ("CORPORATE_HY", "B", "corporate", 40_000.0, 1.00, 20),
            ("RETAIL_MORTGAGE", "BBB", "residential", 250_000.0, 0.50, 100),
            ("RETAIL_REVOLVING", "BBB", "retail", 80_000.0, 0.45, 200),
            ("CRE", "BBB-", "cre", 100_000.0, 1.50, 40),
            ("OTHER", "BBB", "other", 70_000.0, 1.00, 30),
        ]

        exp_id = 0
        for exp_type, rating, sector, total_ead, rw, n_exposures in config:
            avg_ead = total_ead / n_exposures
            for i in range(n_exposures):
                exp_id += 1
                ead = avg_ead * (0.5 + self.rng.random())
                maturity = 1.0 + self.rng.random() * 9.0
                ltv = self.rng.random() * 0.8 if "MORTGAGE" in exp_type or "CRE" in exp_type else 0.0
                is_defaulted = self.rng.random() < 0.005  # 0.5% default rate

                exposures.append(CreditExposure(
                    exposure_id=f"CR-{exp_id:06d}",
                    counterparty_name=f"{exp_type}-{i+1}",
                    exposure_type=exp_type,
                    rating="D" if is_defaulted else rating,
                    sector=sector,
                    ead=ead,
                    risk_weight=rw,
                    rwa=ead * rw,
                    maturity_years=maturity,
                    is_defaulted=is_defaulted,
                    ltv=ltv,
                ))

        total_ead = sum(e.ead for e in exposures)
        total_rwa = sum(e.rwa for e in exposures)
        return CreditPortfolio(
            exposures=exposures,
            total_ead=total_ead,
            total_rwa=total_rwa,
            count=len(exposures),
        )

    def generate_trading_portfolio(self) -> TradingBookPortfolio:
        """Generate trading book (~$500B notional across FRTB risk classes).

        Composition:
        - GIRR: $200B (IR swaps, govies, futures)
        - CSR Non-Sec: $120B (corporate bonds, CDS)
        - Equity: $80B (stocks, equity derivatives)
        - Commodity: $50B (commodity futures, swaps)
        - FX: $50B (FX forwards, options)

        Returns:
            TradingBookPortfolio.

        Reference: BCBS d457 MAR10, ERBA NPR pp. 300-310.
        """
        positions: list[TradingPosition] = []
        pos_id = 0

        risk_class_config = [
            ("GIRR", 200_000.0, 40, ["IR_SWAP", "GOVT_BOND", "IR_FUTURE"]),
            ("CSR_NONSEC", 120_000.0, 30, ["CORP_BOND", "CDS", "INDEX_CDS"]),
            ("EQUITY", 80_000.0, 25, ["STOCK", "EQUITY_OPTION", "EQUITY_FUTURE"]),
            ("COMMODITY", 50_000.0, 15, ["COMMODITY_FUTURE", "COMMODITY_SWAP"]),
            ("FX", 50_000.0, 20, ["FX_FORWARD", "FX_OPTION"]),
        ]

        currencies = ["USD", "EUR", "GBP", "JPY", "CHF"]
        tenors = ["3M", "6M", "1Y", "2Y", "3Y", "5Y", "10Y", "30Y"]

        for risk_class, total_notional, n_positions, instrument_types in risk_class_config:
            avg_notional = total_notional / n_positions
            for i in range(n_positions):
                pos_id += 1
                notional = avg_notional * (0.3 + self.rng.random() * 1.4)
                delta = notional * (self.rng.random() - 0.5) * 0.01
                vega = notional * self.rng.random() * 0.005
                curv = notional * self.rng.random() * 0.001

                positions.append(TradingPosition(
                    position_id=f"TB-{pos_id:05d}",
                    risk_class=risk_class,
                    instrument_type=self.rng.choice(instrument_types),
                    notional=notional,
                    currency=self.rng.choice(currencies),
                    tenor=self.rng.choice(tenors),
                    delta_sensitivity=delta,
                    vega_sensitivity=vega,
                    curvature_sensitivity=curv,
                    bucket=str(self.rng.integers(1, 15)),
                ))

        total_notional = sum(p.notional for p in positions)
        return TradingBookPortfolio(
            positions=positions,
            total_notional=total_notional,
        )

    def generate_counterparty_portfolio(self) -> CounterpartyPortfolio:
        """Generate counterparty exposures (~500 counterparties, ~$200B EAD).

        Mix: 60% financial (alpha=1.4), 40% commercial (alpha=1.0).

        Returns:
            CounterpartyPortfolio.

        Reference: ERBA NPR pp. 200-230, 12 CFR 217.132.
        """
        exposures: list[CounterpartyExposure] = []
        financial_count = 300
        commercial_count = 200
        ratings = ["AA", "A", "BBB", "BB", "B"]
        rating_rws = {"AA": 0.20, "A": 0.50, "BBB": 0.75, "BB": 1.00, "B": 1.50}

        for i in range(financial_count):
            rating = self.rng.choice(ratings[:3])  # Financials tend to be IG
            rc = self.rng.random() * 500.0
            pfe = rc * (0.3 + self.rng.random() * 0.7)
            ead = (rc + pfe) * 1.4  # alpha = 1.4 for financial
            rw = rating_rws[rating]
            exposures.append(CounterpartyExposure(
                counterparty_id=f"FIN-{i+1:04d}",
                counterparty_name=f"Financial-{i+1}",
                counterparty_type="BANK" if i < 100 else "CORPORATE",
                rating=rating,
                netting_set_id=f"NS-FIN-{i+1:04d}",
                replacement_cost=rc,
                pfe=pfe,
                ead=ead,
                alpha=1.4,
                risk_weight=rw,
                rwa=ead * rw,
            ))

        for i in range(commercial_count):
            rating = self.rng.choice(ratings[1:4])
            rc = self.rng.random() * 200.0
            pfe = rc * (0.2 + self.rng.random() * 0.5)
            ead = (rc + pfe) * 1.0  # alpha = 1.0 for commercial
            rw = rating_rws[rating]
            exposures.append(CounterpartyExposure(
                counterparty_id=f"COM-{i+1:04d}",
                counterparty_name=f"Commercial-{i+1}",
                counterparty_type="CORPORATE",
                rating=rating,
                netting_set_id=f"NS-COM-{i+1:04d}",
                replacement_cost=rc,
                pfe=pfe,
                ead=ead,
                alpha=1.0,
                risk_weight=rw,
                rwa=ead * rw,
            ))

        total_ead = sum(e.ead for e in exposures)
        total_rwa = sum(e.rwa for e in exposures)
        return CounterpartyPortfolio(
            exposures=exposures,
            total_ead=total_ead,
            total_rwa=total_rwa,
        )

    def generate_securitization_portfolio(self) -> SecuritizationPortfolio:
        """Generate securitization book (~$50B across RMBS, CMBS, CLO).

        Returns:
            SecuritizationPortfolio.

        Reference: ERBA NPR pp. 160-180.
        """
        tranches: list[SecuritizationTranche] = []
        tranche_id = 0

        deals = [
            ("RMBS-2024-1", "RMBS", 15_000.0),
            ("RMBS-2024-2", "RMBS", 10_000.0),
            ("CMBS-2024-1", "CMBS", 8_000.0),
            ("CLO-2024-1", "CLO", 10_000.0),
            ("CLO-2024-2", "CLO", 7_000.0),
        ]

        tranche_specs = [
            ("Senior", "AAA", 0.20, 1.00, 0.15),
            ("Mezzanine", "A", 0.08, 0.20, 0.40),
            ("Junior", "BBB", 0.03, 0.08, 0.80),
            ("Equity", "BB", 0.00, 0.03, 2.50),
        ]

        for deal_name, asset_type, deal_size in deals:
            for tranche_name, rating, attach, detach, rw in tranche_specs:
                tranche_id += 1
                notional = deal_size * (detach - attach)
                tranches.append(SecuritizationTranche(
                    tranche_id=f"SEC-{tranche_id:04d}",
                    deal_name=deal_name,
                    asset_type=asset_type,
                    approach="SEC_ERBA",
                    rating=rating,
                    attachment=attach,
                    detachment=detach,
                    notional=notional,
                    risk_weight=rw,
                    rwa=notional * rw,
                    is_stc="RMBS" in asset_type,
                ))

        total_notional = sum(t.notional for t in tranches)
        total_rwa = sum(t.rwa for t in tranches)
        return SecuritizationPortfolio(
            tranches=tranches,
            total_notional=total_notional,
            total_rwa=total_rwa,
        )

    def generate_all(self) -> dict[str, object]:
        """Generate all portfolio components.

        Returns:
            Dictionary with all portfolios.

        Reference: FR Y-9C, FR Y-14A.
        """
        return {
            "credit": self.generate_credit_portfolio(),
            "trading": self.generate_trading_portfolio(),
            "counterparty": self.generate_counterparty_portfolio(),
            "securitization": self.generate_securitization_portfolio(),
        }
