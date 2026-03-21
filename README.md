# Basel III Endgame 2026 — Regulatory Capital Engine

Production-grade regulatory capital calculation engine implementing the US Federal Reserve's
March 2026 Re-Proposal for Category I and II banking organizations (ERBA + Revised SA + G-SIB Surcharge).

**Model ID**: FNBC-BIII-2026-001
**Target Institution**: $3.2T Category I US G-SIB
**Language**: Python 3.11+ | **Size**: ~49,000 lines across 12+ modules

## Regulatory Basis

| Document | Pages | Coverage |
|---|---|---|
| ERBA NPR | 1,241 | SA-CR, FRTB, OpRisk, CVA, Capital |
| SA NPR | 436 | Standardized Approach detail |
| G-SIB NPR | 128 | Surcharge methodology (Method 1/2) |
| BCBS d457 | — | Market risk (FRTB) framework |
| BCBS d424 | — | Basel III finalising reforms |

## Architecture

```
src/
├── core/                    # Base classes, enums, Pydantic models, exceptions
├── market_risk/
│   └── frtb/
│       ├── sbm/             # Sensitivities-Based Method
│       │   ├── girr.py      # General Interest Rate Risk (delta/vega/curvature)
│       │   ├── csr.py       # Credit Spread Risk (Non-Sec, Sec CTP/Non-CTP)
│       │   ├── equity.py    # Equity Risk
│       │   ├── commodity.py # Commodity Risk
│       │   └── fx.py        # Foreign Exchange Risk
│       ├── drc/             # Default Risk Charge
│       ├── rrao/            # Residual Risk Add-On
│       └── calculator.py    # Master FRTB calculator
├── credit_risk/             # SA-CR risk weights, exposure classification, CRM
├── counterparty_risk/       # SA-CCR (alpha=1.4/1.0), netting, margin
├── cva_risk/                # SA-CVA, BA-CVA capital charges
├── operational_risk/        # SMA: BIC (12%/15%/18%), ILM=1.0 per US proposal
├── securitization/          # SEC-ERBA, SEC-SA, tranche capital
├── capital/                 # CET1/AT1/T2 components, RWA aggregation, ratios
│   └── gsib/               # G-SIB surcharge (20bp bands, 0.1% increments)
├── ecl/                     # Expected Credit Loss (CECL/IFRS 9)
│   ├── pd_models/          # TTC/PIT PD, term structures, migration matrices
│   ├── lgd_models/         # Downturn LGD, collateral, cure rates
│   ├── ead_models/         # CCF, undrawn commitments, off-balance sheet
│   └── staging/            # IFRS 9 three-stage model, SICR assessment
├── irb/                     # IRB risk weights (comparison only, not for RWA)
├── stress_testing/          # CCAR/DFAST scenarios, 9-quarter capital projection
├── pillar2/                 # ICAAP, IRRBB (EVE/NII), buffer calculator
├── pillar3/                 # Disclosure templates (OV1, KM1, CC1/CC2, CR, MR, OR, LR)
├── reporting/               # FR Y-9C, FFIEC 101, FR Y-15, FR Y-14A/Q
├── reference_data/          # Counterparty registry, instrument classification
├── data_generation/         # Synthetic portfolio and financial statement generators
└── utils/                   # Math helpers, aggregation, BCBS 239 lineage
tests/                       # Mirror of src/ with pytest tests (~6,700 lines)
config/                      # Regulatory parameters (JSON/YAML)
```

## Key US 2026 Re-Proposal Provisions

These deviate from the BCBS standard and are implemented as specified:

| Parameter | US 2026 Value | BCBS Standard |
|---|---|---|
| Output Floor (72.5%) | **NOT applied** | Applied |
| ILM (Operational Risk) | **1.0** (not applied) | Calculated |
| MSA Deduction | **250% RW** (not deducted) | Deducted |
| Retail Transactor RW | **45%** | 75% |
| Corporate IG RW | **65%** (self-assessment) | External rating based |
| G-SIB Surcharge Bands | **20bp / 0.1%** | 100bp / 0.5% |
| G-SIB Method 2 | **1.2x downward** factor | Standard |
| SA-CCR Alpha | **1.4** (financial) / **1.0** (commercial) | 1.4 |
| BIC Thresholds | **$1B / $30B** | Same |
| BIC Coefficients | **12% / 15% / 18%** | Same |
| FRTB Threshold | **$5B** (4-quarter avg) | $1B |

## Modules

### Market Risk — FRTB
- **SBM**: All 7 risk classes (GIRR, CSR Non-Sec, CSR Sec CTP/Non-CTP, Equity, Commodity, FX)
- **DRC**: Default risk charge for non-securitization, securitization CTP/non-CTP
- **RRAO**: Residual risk add-on (exotic/other classification)
- Three correlation scenarios (Low/Medium/High) per MAR21.6

### Credit Risk — SA-CR
- 61 exposure types with full risk weight assignment
- Credit Risk Mitigation (CRM): substitution, double-default, haircuts
- Exposure classification engine (Dodd-Frank §939A — no external ratings)

### Capital Stack
- **CET1**: Common stock, surplus, retained earnings, AOCI, regulatory deductions
- **Threshold Deductions**: 10% individual / 15% aggregate (MSA → 250% RW per US 2026)
- **AT1**: Non-cumulative preferred, trust preferred (grandfathered)
- **Tier 2**: Subordinated debt (5-year straight-line amortization), general allowance (1.25% cap)
- **RWA Aggregation**: Credit + Market (×12.5) + OpRisk (×12.5) + CVA (×12.5)
- **Capital Ratios**: CET1, Tier 1, Total Capital, SLR, PCA classification
- **Buffer Stack**: CCB/SCB + CCyB + G-SIB surcharge, MDA trigger zones

### G-SIB Surcharge
- **Method 1**: BCBS substitutability-based (12 indicators, 5 categories × 20% weight)
- **Method 2**: US-specific STWF approach (1.2x downward coefficient adjustment)
- **Final surcharge**: Higher of Method 1 vs Method 2
- **Band mapping**: 20bp score ranges → 0.1% surcharge increments

### Expected Credit Loss (ECL)
- **PD Models**: TTC calibration (22-grade scale), PIT adjustment (4 macro regimes), migration matrices
- **LGD Models**: Supervisory LGD, collateral recovery, downturn add-ons, workout, cure rates
- **EAD Models**: SA-CR CCFs, undrawn commitment drawdown, off-balance sheet
- **Staging**: IFRS 9 three-stage (SICR: PD increase, rating downgrade, 30 DPD backstop, watchlist)
- **ECL Calculator**: PD × LGD × EAD × DF, probability-weighted multi-scenario

### Stress Testing
- **Scenarios**: Baseline, Adverse, Severely Adverse (13-quarter macro paths)
- **Severely Adverse**: GDP -8.5%, unemployment 10%, HPI -25%, equity -55%
- **Capital Projector**: 9-quarter waterfall (PPNR - provisions - losses - actions = CET1)
- **SCB**: max(2.5%, peak-to-trough CET1 decline + 4 quarters dividends)

### Pillar 2 — Supervisory Review
- **ICAAP**: 8 Pillar 2A risk categories (concentration, IRRBB, pension, model, etc.)
- **IRRBB**: EVE and NII under 6 prescribed scenarios per BCBS d368
- **Buffer Calculator**: Full stack (CET1 min + CCB/SCB + CCyB + G-SIB + P2A)

### Pillar 3 — Disclosure
16 templates: OV1, KM1, CC1, CC2, CR1-CR5, MR1-MR4, OR1, LR1-LR2

### Fed Reporting
- **FR Y-9C**: Schedule HC-R (17 line items), data quality validation
- **FFIEC 101**: Schedule A — RWA by exposure type (lines 1a-16b)
- **FR Y-15**: 12 systemic indicators, Method 1/2 scores
- **FR Y-14A/Q**: 9-quarter capital projections, stress scenarios

### Data Quality — BCBS 239
- Completeness, accuracy, range, consistency, referential integrity checks
- Full lineage trail with SHA-256 hashing for audit
- Quality scoring across all modules

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run specific module tests
pytest tests/market_risk/frtb/sbm/ -v     # FRTB SBM tests
pytest tests/capital/ -v                    # Capital stack tests
pytest tests/ecl/ -v                        # ECL tests
pytest tests/stress_testing/ -v             # Stress testing
pytest tests/test_integration.py -v         # End-to-end integration

# Type checking
python -m mypy src/ --strict

# Linting
python -m ruff check src/
```

## Development With Claude Code

```bash
claude  # Opens Claude Code in this directory
# Claude Code reads CLAUDE.md for project context and build instructions
```

To build a specific phase:
```
"Build Phase N"  → Claude reads CLAUDE.md, checks existing files, builds to full depth
```

## Model Governance (SR 11-7)

- All model assumptions documented with regulatory citations
- Data transformations logged to BCBS 239 lineage trail
- Data quality checks: completeness, accuracy, range, referential integrity
- Backtesting support: Kupiec test for VaR, migration matrix validation
- Every calculation traceable to a specific regulatory provision (ERBA NPR page, BCBS section)

## Target Capital Ratios (Category I G-SIB)

| Metric | Target Range | Regulatory Minimum |
|---|---|---|
| CET1 Ratio | 10-15% | 4.5% + buffers |
| Tier 1 Ratio | 12-17% | 6.0% + buffers |
| Total Capital Ratio | 14-19% | 8.0% + buffers |
| SLR | 5-7% | 3% (5% eSLR) |
| SCB | >= 2.5% | 2.5% floor |

## License

Proprietary — Internal use only.
