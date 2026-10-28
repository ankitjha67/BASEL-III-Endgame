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
- The authority for every US parameter is the regulatory TEXT of the March 2026 ERBA NPR
  (OCC NR 2026-16a, 1,241 pp.; common rule text pp. 674-988). A verbatim transcription of
  every table and formula in that text is kept in `docs/ERBA_NPR_2026_parameter_reference.md`;
  cite the section (e.g. "ERBA NPR § __.111 Table 5") in docstrings. "ERBA" in the US rule means
  *expanded risk-based approach* (NOT the BCBS external-ratings-based securitization approach).
- ILM = 1.0 — more precisely, operational risk RWA = 12.5 × BIC with NO loss multiplier term (§ __.150(a))
- Output Floor (72.5%) NOT included in US proposal; no IRB/IMM for credit or counterparty risk
- MSA deduction REMOVED — 250% risk weight instead; MSAs are excluded from the 10%/15% threshold tests
- SA-CCR alpha = 1.4; 1.0 for commercial end-user netting sets (§ __.114(e)(4)). Credit SFs by credit
  quality: single-name IG 0.46% / spec 1.3% / sub-spec 6.0% (ρ 50%), index IG 0.38% / spec 1.06% (ρ 80%);
  margined MF = √(1.5·MPOR/250); unmargined MF = √(min(M,1y)/1y); SD floor 0.04
- Retail transactor = 45% (not 55% from 2023 NPR); regulatory retail 75% (≤ $1M aggregate); other retail 100%
- Corporate IG = 65% (internal rating system, no external ratings per Dodd-Frank §939A); project finance
  130% pre-operational / 100% operational; subordinated 150%; NO SME 85% weight in the US proposal
- Residential mortgages (Table 5 to § __.111): 20/25/30/40/50/70% for LTV ≤50/≤60/≤80/≤90/≤100/>100
  (six bands); 30/35/45/60/75/105% if dependent on real-estate cash flows (Table 6). The 2023 NPR's
  40-90% schedule is withdrawn.
- Bank exposures (Table 2 to § __.111): Grade A 30% (CET1 ≥ 14% & leverage ≥ 5%, or CBLR) else 40%;
  Grade B 75%; Grade C 150%; no general short-term preference (20/50% only for foreign-bank
  trade-related contingent items ≤ 3 months)
- CCFs (§ __.112): 10% unconditionally cancelable; 40% ALL other commitments regardless of maturity;
  20% short-term trade; 50% transaction-related / NIF / RUF; 100% guarantees, repos, forwards
- Equity SRWA (§ __.141): 0% sovereign/FRB stock; 20% PSE/FHLB/Farmer Mac; 100% non-significant ≤ 10%
  of total capital; 250% significant FI; 300% publicly traded; 400% non-public; 600% leveraged funds
- Securitization: SEC-SA ONLY (p = 0.5, 1.5 resec; floors 15% / 100%; 1,250% cap; straddle blend);
  no SEC-ERBA, no STC; DRC-sec RW = banking-book SEC RW × 8%
- CVA: BA-CVA K = 0.65·(0.25·K_unhedged + 0.75·K_hedged), SCVA = (1/α)·RW·M·EAD·DF with the sector ×
  IG/spec/sub-spec Table 1 to § __.222; SA-CVA m_CVA = 1, R = 0.01; scope = Cat I/II HCs, their
  market-risk DI subs, and market-risk banks with ≥ $1T OTC notional
- FRTB SBM: GIRR 10 vertices (no 7Y/25Y), RW ÷ √2 for USD/AUD/CAD/EUR/JPY/SEK/GBP; CSR non-sec 20
  US buckets by IG/spec/sub-spec; equity Table 8 with index-vs-sector γ 45%; commodity 12 buckets;
  FX 15% (÷ √2 liquid pairs); vega RW 100% except equity large-cap/indices 77.78%
- FRTB DRC (§ __.210): four buckets (non-US sovereign 0.6%, PSE/GSE 2.1%, corporate 4.1% IG; 22%
  speculative; 50% sub-speculative; 100% defaulted); LGD 100/75/50 (US PSE)/25 (covered, GSE-guaranteed);
  HBR = long/(long+|short|); CTP total = max(Σ[max(DRC_b,0) + 0.5·min(DRC_b,0)], 0)
- FRTB IMA: m_c 1.5 (ladder to 2.0), ES 97.5%, ω 0.5, SES ρ_b 0.36, PLA KS 0.09/0.12 (3-year transition)
- G-SIB Method 2 coefficients adjusted by 1.2x downward factor (separate G-SIB NPR — not covered by the ERBA NPR text)
- G-SIB surcharge bands: 20bp score ranges / 0.1% increments (not 100bp/0.5%)
- Operational risk BI noninterest component uses the NET basis with the 0.7x factor applied to
  investment management, investment services AND non-lending treasury services (§ __.150(c)(1)(ii));
  ILDC caps net interest at 2.25% of interest-earning assets; loss-data threshold $20,000
- BIC marginal coefficients: 12% / 15% / 18% at $1B / $30B thresholds (CPI-W indexed)
- FRTB threshold: $5B trading activity (4-quarter average) or 10% of total assets, not $1B from 2023

### Testing
- Every module must have corresponding tests in `tests/`
- Test against known regulatory examples where available
- Validate that all credit risk weights match Tables 1-8 to § __.111 of the ERBA NPR
  (sovereign, bank, foreign PSE, residential and commercial real estate)
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
- DRC Non-Sec (MAR22.1-22.23)
- DRC Sec Non-CTP (MAR22.24-22.34): LGD=100%, no netting, rating+seniority RWs
- DRC Sec CTP (MAR22.35-22.46): same-tranche netting, 50% hedge benefit ratio
- RRAO (exotic/other classification)
- Master FRTB Calculator

### Phase 3 — COMPLETE (Credit Risk, SA-CCR, CVA, OpRisk, Securitization)
- SA-CR: Risk weight assignment, exposure classification, CRM
- OBS/CCF: Off-balance sheet credit conversion factors (12 CFR 217.33), 12 categories
- Large Exposures: Single-counterparty credit limits (12 CFR 252 Subpart J), 15%/25% T1
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

### Gap Analysis Summary (Reconciled to the March 2026 ERBA NPR text, 2026-10-28 — actual `wc -l` counts)
| Module | Src Lines | Target | Status |
|---|---|---|---|
| FRTB (Market Risk) | 10,916 | 12,800 | SBM tables re-mapped to Tables 1-11 to § __.209; DRC to § __.210 |
| Credit Risk (SA-CR, CRM, LE, OBS) | 5,112 | 4,500 | Tables 1-8 to § __.111, § __.112 CCFs, § __.115 haircuts |
| SA-CCR (Counterparty) | 1,374 | 3,500 | Table 2 to § __.114, maturity factors, SD floor |
| CVA Risk | 3,214 | 2,500 | § __.222 BA-CVA, § __.224-225 SA-CVA |
| Operational Risk | 1,945 | 2,500 | § __.150 two-component BI, no ILM |
| Securitization | 1,763 | 2,500 | SEC-SA only (§ __.133); BCBS SEC-ERBA/STC comparison-only |
| Capital + G-SIB | 6,737 | 6,500 | MSAs out of threshold tests; G-SIB per separate NPR (not reviewed) |
| ECL | 2,820 | 4,000 | Implemented (not governed by the NPR) |
| IRB | 1,224 | 2,500 | Implemented (comparison only) |
| Pillar 2 | 3,048 | 3,500 | Implemented |
| Pillar 3 | 3,032 | 2,500 | Implemented |
| Reporting | 4,080 | 4,000 | Implemented |
| Stress Testing | 1,169 | 5,000 | Implemented (provision rates calibrated, not sourced) |
| Utils | 843 | 4,000 | Implemented |
| Ref Data + Data Gen | 2,054 | 2,000 | Lookup tables aligned to § __.111 |
| Core | 820 | — | Enums re-mapped to NPR bucket taxonomies |
| **Src total** | **51,185** | **~49,000** | — |
| Tests | 14,321 lines / 1,374 tests | 8,000 | All passing |

Regulatory-accuracy status is tracked in `docs/AUDIT_REPORT.md` (Part 1: formula audit;
Part 2: reconciliation against the ERBA NPR text). The verbatim transcription of the NPR
tables is `docs/ERBA_NPR_2026_parameter_reference.md`. Every parameter the NPR text does
not settle carries a `# TODO: VERIFY` marker in source.

## How To Develop Each Phase

When I say "Build Phase N", follow this process:
1. Read this CLAUDE.md first
2. Check what files already exist in the module
3. Build each file to FULL production depth (no stubs, no shortcuts, no fake data)
4. Write tests alongside the code
5. Run tests to verify
6. Update this CLAUDE.md with completion status
7. Commit with descriptive message: `feat(module): description [Phase N]`
