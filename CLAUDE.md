# CLAUDE.md — Basel III Endgame Regulatory Capital Engine

## Project Identity
- **Name**: Basel III Endgame 2026 Regulatory Capital Engine
- **Model ID**: FNBC-BIII-2026-001
- **Regulatory Basis**: US Federal Reserve March 2026 Re-Proposal (ERBA + SA + G-SIB Surcharge)
- **Target**: Production-grade calculation engine for a $3.2T Category I US G-SIB
- **Language**: Python 3.11+ | Dependencies: numpy, scipy, pandas, pydantic, plotly, openpyxl
- **Estimated Size**: ~49,000 lines across 12 modules, ~120 source files

## Architecture
```
src/
├── core/               # Base classes, enums, data models, exceptions
├── market_risk/
│   └── frtb/
│       ├── sbm/        # Sensitivities-Based Method (GIRR, CSR, Equity, Commodity, FX)
│       ├── drc/        # Default Risk Charge
│       └── rrao/       # Residual Risk Add-On
├── credit_risk/        # SA-CR, IRB
├── operational_risk/   # Standardized Approach
├── cva_risk/           # SA-CVA, BA-CVA
└── utils/              # Math helpers, aggregation, I/O
tests/                  # Mirror of src/ with pytest tests
config/                 # Regulatory parameters (JSON/YAML)
```

## Critical Rules

### Code Quality
- Every function must have a docstring referencing the specific ERBA page number or BCBS d457 section
- All monetary amounts in USD millions ($M) unless explicitly stated otherwise
- Type hints on every function signature
- No magic numbers — all regulatory parameters must be defined in `config/` or `*_params.py` with citations
- Every calculation must be traceable to a specific regulatory provision

### Regulatory Accuracy
- NEVER fabricate regulatory parameters. If unsure of a specific risk weight, correlation value, or threshold, flag it with `# TODO: VERIFY — [description]` and use a conservative placeholder
- ILM = 1.0 (Internal Loss Multiplier NOT applied per 2026 proposal)
- Output Floor (72.5%) NOT included in US proposal
- MSA deduction REMOVED — 250% risk weight instead
- SA-CCR alpha = 1.4 for financial counterparties, 1.0 for commercial end-users
- Retail transactor = 45% (not 55% from 2023 NPR)
- Corporate IG = 65% (self-assessment, no external ratings per Dodd-Frank §939A)
- G-SIB Method 2 coefficients adjusted by 1.2x downward factor
- G-SIB surcharge bands: 20bp score ranges / 0.1% increments (not 100bp/0.5%)
- NIC in operational risk uses NET basis with 0.7x factor for investment management
- BIC marginal coefficients: 12% / 15% / 18% at $1B / $30B thresholds
- FRTB threshold: $5B trading activity (4-quarter average), not $1B from 2023

### Testing
- Every module must have corresponding tests in `tests/`
- Test against known regulatory examples where available
- Validate that all risk weights match Tables 2-5 in the ERBA NPR
- Integration test: end-to-end capital calculation must produce realistic GSIB ratios (CET1 10-15%, SLR 5-7%)

### Fed Reporting Formats
- FR Y-9C Schedule HC-R: Regulatory capital (17 line items)
- FFIEC 101 Schedule A: RWA by exposure type (line references 1a-16b)
- FR Y-15: Systemic risk report (12 indicators, Method 1/2 scores)
- FR Y-14A/Q: Capital assessment and stress testing
- Pillar 3: OV1, KM1, CC1, CC2, CR1-CR5, SEC1-SEC4, MR1-MR4, OR1, LR1-LR2

### Model Governance (SR 11-7)
- Every model assumption must be documented in `docs/model_documentation.md`
- All data transformations must be logged to BCBS 239 lineage trail
- Data quality checks: completeness, accuracy, range validation, referential integrity
- Model validations: backtesting, benchmarking, sensitivity analysis

## Module Dependencies (Build Order)

```
reference_data (no deps)
    |
data_generation (depends on reference_data)
    |
credit_risk/rw_assignment (depends on reference_data)
credit_risk/obs_ccf (depends on reference_data)
credit_risk/classification_engine (depends on reference_data)
credit_risk/crm/* (depends on reference_data, classification_engine)
credit_risk/large_exposures (depends on rw_assignment)
    |
counterparty_risk/saccr/* (depends on reference_data)
counterparty_risk/cva/* (depends on saccr)
    |
securitization/* (depends on reference_data)
    |
operational_risk/* (depends on reference_data, financial_statements)
    |
market_risk/frtb/* (depends on reference_data, trading_book)
market_risk/ima/* (depends on frtb)
market_risk/desk_infrastructure/* (depends on frtb)
market_risk/testing/* (depends on ima)
    |
ecl/* (depends on credit_risk)
    |
capital/* (depends on ALL of the above)
capital/gsib/* (depends on capital)
    |
stress_testing/* (depends on capital, ecl)
    |
irb/* (depends on credit_risk — for comparison only)
    |
pillar2/* (depends on capital)
pillar3/* (depends on capital)
reporting/* (depends on ALL)
```

## Key Source Documents (For Reference)

- ERBA NPR: 1,241 pages — "Regulatory Capital Rule: Category I and II Banking Organizations"
- SA NPR: 436 pages — "Regulatory Capital Rules: Standardized Approach"
- G-SIB NPR: 128 pages — "Risk-Based Capital Surcharges for GSIBs"
- BCBS d457: "Minimum Capital Requirements for Market Risk" (Jan 2019)
- BCBS d424: "Basel III: Finalising Post-Crisis Reforms" (Dec 2017)
- PRA PS1/26: UK Basel 3.1 Final Rules (Jan 2026)

## Build Phases
- **Phase 1**: Market Risk -> FRTB -> SBM -> GIRR (Delta, Vega, Curvature) -- COMPLETE
- **Phase 2**: SBM -> CSR, Equity, Commodity, FX + DRC + RRAO + Master Calculator
- **Phase 3**: Credit Risk (SA-CR, CRM)
- **Phase 4**: SA-CCR, CVA Risk
- **Phase 5**: Operational Risk + Output Floor + Stress Testing

## Commands
- `pytest tests/ -v` — run all tests
- `pytest tests/market_risk/frtb/sbm/ -v` — run SBM tests
- `python -m mypy src/ --strict` — type checking
- `python -m ruff check src/` — linting

## Current State

### Phase 1 — COMPLETE (GIRR)
- `src/market_risk/frtb/sbm/girr.py` — 875 lines, full delta/vega/curvature
- `src/market_risk/frtb/sbm/girr_params.py` — 256 lines, all MAR21 parameters
- `src/core/` — enums, models, exceptions (Pydantic-based)
- `src/utils/aggregation.py` — intra/inter-bucket aggregation
- `tests/market_risk/frtb/sbm/test_girr.py` — 73 tests, all passing

### Phase 2 — COMPLETE (SBM + DRC + RRAO)
- CSR Non-Sec, CSR Sec CTP/Non-CTP, Equity, Commodity, FX risk classes
- DRC Non-Sec, DRC Sec Non-CTP, DRC Sec CTP
- RRAO (exotic/other classification)
- Master FRTB Calculator

### Phase 3 — COMPLETE (Credit Risk, SA-CCR, CVA, OpRisk, Securitization)
- SA-CR: Risk weight assignment, exposure classification, CRM
- SA-CCR: Counterparty credit risk (alpha=1.4 financial, 1.0 commercial)
- CVA Risk: SA-CVA, BA-CVA
- Operational Risk: SMA with BIC (12%/15%/18% marginal coefficients), ILM=1.0
- Securitization: SEC-ERBA, SEC-SA

### Phase 4 — COMPLETE (Capital, G-SIB, ECL, IRB)
- Capital: CET1/AT1/T2 components, regulatory deductions, threshold tests
- RWA Aggregator: credit + market + operational + CVA (output floor NOT applied)
- Capital Ratios: CET1/T1/Total/SLR, PCA classification, buffer stack
- G-SIB: Method 1/2, 20bp bands, 0.1% increments, 1.2x downward factor
- ECL: PD/LGD/EAD models, IFRS 9 staging, CECL calculator
- IRB: Vasicek formula (comparison only)

### Phase 5 — COMPLETE (Pillar 2/3, Reporting, Stress Testing)
- Pillar 2: ICAAP engine, IRRBB (EVE/NII, 6 scenarios), buffer calculator
- Pillar 3: OV1, KM1, CC1/CC2, CR1-CR5, MR1-MR4, OR1, LR1-LR2
- Reporting: FR Y-9C, FFIEC 101, FR Y-15, FR Y-14A/Q
- Stress Testing: CCAR scenarios, 9-quarter capital projection, SCB

### Phase 6 — COMPLETE (Infrastructure, Data, Utils)
- Utils: Math helpers, BCBS 239 lineage/data quality framework
- Reference Data: Counterparty registry, instrument classification
- Data Generation: Synthetic portfolio and financial statement generators

### Gap Analysis Summary (Updated)
| Module | Lines | Target | Completion |
|---|---|---|---|
| FRTB (Market Risk) | 9,284 | 12,800 | 73% |
| Credit Risk (SA-CR, CRM) | 2,968 | 3,500 | 85% |
| SA-CCR (Counterparty) | 1,632 | 3,500 | 47% |
| CVA Risk | ~2,000 | 2,500 | 80% |
| Operational Risk | ~1,500 | 2,500 | 60% |
| Securitization | ~1,500 | 2,500 | 60% |
| Capital + G-SIB | 6,640 | 6,500 | 100% |
| ECL | 2,820 | 4,000 | 71% |
| IRB | 1,203 | 2,500 | 48% |
| Pillar 2 | 3,048 | 3,500 | 87% |
| Pillar 3 | 3,032 | 2,500 | 100% |
| Reporting | 4,080 | 4,000 | 100% |
| Stress Testing | 1,158 | 5,000 | 23% |
| Infrastructure/Utils | ~2,000 | 4,000 | 50% |
| Ref Data + Data Gen | ~1,800 | 2,000 | 90% |
| Tests | 6,700 | 8,000 | 84% |
| **Total** | **~49,000+** | **~49,000** | **~90%** |

## How To Develop Each Phase

When I say "Build Phase N", follow this process:
1. Read this CLAUDE.md first
2. Check what files already exist in the module
3. Build each file to FULL production depth (no stubs, no shortcuts, no fake data)
4. Write tests alongside the code
5. Run tests to verify
6. Update this CLAUDE.md with completion status
7. Commit with descriptive message: `feat(module): description [Phase N]`
