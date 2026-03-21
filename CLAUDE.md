# CLAUDE.md — Basel III Endgame Regulatory Capital Engine

## Project Identity
- **Name**: Basel III Endgame 2026 Regulatory Capital Engine
- **Model ID**: FNBC-BIII-2026-001
- **Regulatory Basis**: US Federal Reserve March 2026 Re-Proposal (ERBA + SA + G-SIB Surcharge)
- **Target**: Production-grade calculation engine for a $3.2T Category I US G-SIB
- **Language**: Python 3.11+ | Dependencies: numpy, scipy, pandas, plotly, openpyxl
- **Estimated Size**: ~49,000 lines across 12 modules, ~120 source files

## Critical Rules

### Code Quality
- Every function must have a docstring referencing the specific ERBA page number or BCBS d457 section
- All monetary amounts in USD millions ($M) unless explicitly stated otherwise
- CamelCase for all variable names, function names, class names (Senior Management UX requirement)
- Type hints on every function signature
- No magic numbers — all regulatory parameters must be defined in `src/reference_data/` with citations
- Every calculation must be traceable to a specific regulatory provision

### Regulatory Accuracy
- NEVER fabricate regulatory parameters. If unsure of a specific risk weight, correlation value, or threshold, flag it with `# TODO: VERIFY — [description]` and use a conservative placeholder
- ILM = 1.0 (Internal Loss Multiplier NOT applied per 2026 proposal)
- Output Floor (72.5%) NOT included in US proposal
- MSA deduction REMOVED — 250% risk weight instead
- SA-CCR alpha = 1.4 for financial counterparties, 1.0 for commercial end-users
- Retail transactor = 45% (not 55% from 2023 NPR)
- Corporate IG = 65% (self-assessment, no external ratings per Dodd-Frank §939A)
- G-SIB Method 2 coefficients adjusted by 1.2× downward factor
- G-SIB surcharge bands: 20bp score ranges / 0.1% increments (not 100bp/0.5%)
- NIC in operational risk uses NET basis with 0.7× factor for investment management
- BIC marginal coefficients: 12% / 15% / 18% at $1B / $30B thresholds
- FRTB threshold: $5B trading activity (4-quarter average), not $1B from 2023

### Testing
- Every module must have corresponding tests in `tests/`
- Test against known regulatory examples where available
- Validate that all risk weights match Tables 2-5 in the ERBA NPR
- Integration test: end-to-end capital calculation must produce realistic GSIB ratios (CET1 10-15%, SLR 5-7%)

### Color Coding (RAG Status)
- 🟢 Green: Within limit, healthy, no concern
- 🟡 Amber: Near threshold (>80% of limit), watch item
- 🔴 Red: Breach, above limit, requires immediate action
- Apply RAG to: capital ratios vs requirements, large exposures vs 25% T1 limit, ECL coverage ratios, P&L attribution test results, backtesting exceptions

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
    ↓
data_generation (depends on reference_data)
    ↓
credit_risk/rw_assignment (depends on reference_data)
credit_risk/obs_ccf (depends on reference_data)
credit_risk/classification_engine (depends on reference_data)
credit_risk/crm/* (depends on reference_data, classification_engine)
credit_risk/large_exposures (depends on rw_assignment)
    ↓
counterparty_risk/saccr/* (depends on reference_data)
counterparty_risk/cva/* (depends on saccr)
    ↓
securitization/* (depends on reference_data)
    ↓
operational_risk/* (depends on reference_data, financial_statements)
    ↓
market_risk/frtb/* (depends on reference_data, trading_book)
market_risk/ima/* (depends on frtb)
market_risk/desk_infrastructure/* (depends on frtb)
market_risk/testing/* (depends on ima)
    ↓
ecl/* (depends on credit_risk)
    ↓
capital/* (depends on ALL of the above)
capital/gsib/* (depends on capital)
    ↓
stress_testing/* (depends on capital, ecl)
    ↓
irb/* (depends on credit_risk — for comparison only)
    ↓
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

## Current State

### Completed (From Prior Chat Sessions)
- V7 regulatory analysis document (1,943 paragraphs covering all 3 NPRs)
- Interview briefing document
- 3,225-word reusable master prompt
- v4 calculation engine (1,033 lines — proof of concept, NOT production)
- FRTB Phase 1A: Prescribed parameters and aggregation framework (829 lines)
- FRTB Phase 1B: Position generation and basic calculation (333 lines)
- Full gap analysis identifying 96 individual items across 12 modules

### Gap Analysis Summary
| Module | Current Lines | Needed Lines | Completion |
|---|---|---|---|
| FRTB | 1,162 | 12,800 | 9.1% |
| CRM | 0 | 2,500 | 0% |
| SA-CCR | 60 | 3,500 | 1.7% |
| Stress Testing | 0 | 5,000 | 0% |
| Credit Classification | 80 | 3,500 | 2.3% |
| ECL | 30 | 4,000 | 0.8% |
| CVA | 15 | 2,500 | 0.6% |
| Securitization | 30 | 2,500 | 1.2% |
| IRB | 0 | 2,500 | 0% |
| Pillar 2 | 0 | 3,500 | 0% |
| Pillar 3 | 30 | 2,500 | 1.2% |
| Infrastructure | 40 | 4,000 | 1.0% |
| **Total** | **~1,450** | **~49,000** | **~3%** |

## How To Develop Each Phase

When I say "Build Phase N", follow this process:
1. Read this CLAUDE.md first
2. Check what files already exist in the module
3. Build each file to FULL production depth (no stubs, no shortcuts, no fake data)
4. Write tests alongside the code
5. Run tests to verify
6. Update this CLAUDE.md with completion status
7. Commit with descriptive message: `feat(module): description [Phase N]`
