# Basel III Endgame Engine — Claude Code Migration Guide

## Step 1: Install Claude Code (If Not Already)

```bash
npm install -g @anthropic-ai/claude-code
```

Requires Node.js 18+. Verify:
```bash
claude --version
```

## Step 2: Create The GitHub Repo

```bash
# Create the repo on GitHub first via github.com/new
# Repo name: basel-iii-endgame-engine
# Then:

mkdir basel-iii-endgame-engine
cd basel-iii-endgame-engine
git init
```

## Step 3: Set Up Project Structure

```
basel-iii-endgame-engine/
├── CLAUDE.md                          # Claude Code instructions (CRITICAL)
├── README.md                          # Project overview
├── pyproject.toml                     # Python project config
├── requirements.txt                   # Dependencies
│
├── src/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── bank_profile.py            # Bank identity, thresholds, dates
│   │   ├── regulatory_params.py       # All prescribed parameters
│   │   └── model_governance.py        # SR 11-7 framework
│   │
│   ├── reference_data/
│   │   ├── __init__.py
│   │   ├── risk_weights.py            # 61 ERBA exposure types
│   │   ├── ccf_table.py               # 14 OBS CCF types
│   │   ├── saccr_params.py            # SA-CCR supervisory factors
│   │   ├── haircut_table.py           # Collateral supervisory haircuts
│   │   ├── frtb_params.py             # All FRTB prescribed RWs/correlations
│   │   └── gsib_indicators.py         # FR Y-15 systemic indicator definitions
│   │
│   ├── data_generation/
│   │   ├── __init__.py
│   │   ├── credit_portfolio.py        # Realistic GSIB credit book
│   │   ├── obs_portfolio.py           # Off-balance sheet items
│   │   ├── derivatives_portfolio.py   # SA-CCR derivative trades
│   │   ├── trading_book.py            # FRTB trading positions
│   │   ├── securitization_book.py     # Securitization tranches
│   │   └── financial_statements.py    # P&L, balance sheet for op risk
│   │
│   ├── credit_risk/
│   │   ├── __init__.py
│   │   ├── classification_engine.py   # Bank grade, IG, transactor, LTV, CF-dep
│   │   ├── rw_assignment.py           # Risk weight lookup and assignment
│   │   ├── obs_ccf.py                 # Off-balance sheet CCF application
│   │   ├── crm/
│   │   │   ├── __init__.py
│   │   │   ├── substitution.py        # Guarantee/credit derivative substitution
│   │   │   ├── collateral_haircut.py  # E* formula, supervisory haircuts
│   │   │   ├── simple_approach.py     # 20% floor simple approach
│   │   │   ├── prepaid_protection.py  # New 2026 prepaid credit protection
│   │   │   ├── mismatch.py            # Currency (8%) and maturity mismatch
│   │   │   └── netting.py             # Qualifying master netting agreements
│   │   └── large_exposures.py         # 25% Tier 1 limit, top-N, HHI
│   │
│   ├── counterparty_risk/
│   │   ├── __init__.py
│   │   ├── saccr/
│   │   │   ├── __init__.py
│   │   │   ├── replacement_cost.py    # RC for margined and unmargined
│   │   │   ├── pfe_addon.py           # 5 asset class add-ons
│   │   │   ├── hedging_sets.py        # Hedging set construction
│   │   │   ├── supervisory_delta.py   # Option delta (Black-Scholes)
│   │   │   ├── maturity_factor.py     # Maturity factor with MPOR
│   │   │   ├── multiplier.py          # PFE multiplier (0.05 floor)
│   │   │   ├── cross_product.py       # 2026 cross-product netting
│   │   │   └── qccp.py               # QCCP Kccp formula
│   │   └── cva/
│   │       ├── __init__.py
│   │       ├── ba_cva.py              # Basic Approach CVA
│   │       ├── sa_cva.py              # Standardized Approach CVA
│   │       ├── hedge_recognition.py   # CVA hedge eligibility
│   │       └── exemptions.py          # Client-cleared, FX, threshold
│   │
│   ├── securitization/
│   │   ├── __init__.py
│   │   ├── sec_sa.py                  # SEC-SA formula (Ka, A, D, W, p)
│   │   ├── pool_analysis.py           # Underlying pool Ka calculation
│   │   ├── operational_req.py         # Clean sale, risk retention, due diligence
│   │   ├── synthetic.py               # Synthetic securitization
│   │   └── npl.py                     # NPL securitization framework
│   │
│   ├── operational_risk/
│   │   ├── __init__.py
│   │   ├── business_indicator.py      # BI = ILDC + NIC (net basis, 0.7x)
│   │   ├── bic_calculation.py         # BIC marginal coefficients
│   │   ├── ilm.py                     # ILM (=1 for 2026, formula for comparison)
│   │   ├── loss_data.py               # Operational loss database ($20K threshold)
│   │   └── threshold_indexing.py      # CPI-W indexing mechanism
│   │
│   ├── market_risk/
│   │   ├── __init__.py
│   │   ├── frtb/
│   │   │   ├── __init__.py
│   │   │   ├── sbm/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── girr.py            # GIRR: curves, inflation, xccy basis
│   │   │   │   ├── csr_nonsec.py      # CSR non-sec: 18 buckets, name/tenor
│   │   │   │   ├── csr_sec.py         # CSR sec: non-CTP + CTP
│   │   │   │   ├── equity.py          # Equity: 13 buckets, dividend, repo
│   │   │   │   ├── commodity.py       # Commodity: curves, basis, grade
│   │   │   │   ├── fx.py              # FX: triangulation, specified pairs
│   │   │   │   ├── delta.py           # Delta aggregation engine
│   │   │   │   ├── vega.py            # Vega: expiry×tenor matrix
│   │   │   │   └── curvature.py       # Curvature: full repricing
│   │   │   ├── drc/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── drc_nonsec.py      # Non-sec DRC: JTD, netting, HBR
│   │   │   │   └── drc_sec.py         # Securitization DRC
│   │   │   ├── rrao.py                # RRAO: exotic/other/exempt
│   │   │   ├── aggregation.py         # Within-bucket + across-bucket + 3 scenarios
│   │   │   └── calculator.py          # Master FRTB calculator
│   │   ├── ima/
│   │   │   ├── __init__.py
│   │   │   ├── expected_shortfall.py  # ES at 97.5%, 5 liquidity horizons
│   │   │   ├── stressed_es.py         # Stressed period calibration
│   │   │   ├── nmrf.py                # Non-modellable risk factor ID
│   │   │   └── capital_multiplier.py  # m_c = 1.5 + backtesting add-on
│   │   ├── desk_infrastructure/
│   │   │   ├── __init__.py
│   │   │   ├── desk_definition.py     # Trading desk requirements
│   │   │   ├── boundary.py            # Banking/trading book boundary
│   │   │   ├── irt.py                 # Internal risk transfers
│   │   │   └── ipv.py                 # Independent price verification
│   │   ├── testing/
│   │   │   ├── __init__.py
│   │   │   ├── pla_test.py            # P&L attribution (Spearman + KL)
│   │   │   └── backtesting.py         # 250-day VaR backtesting
│   │   └── fund_treatment.py          # Look-through, mandate, fallback
│   │
│   ├── ecl/
│   │   ├── __init__.py
│   │   ├── pd_models/
│   │   │   ├── __init__.py
│   │   │   ├── pd_term_structure.py   # PD curves (marginal, cumulative)
│   │   │   ├── ttc_to_pit.py          # Through-the-cycle to point-in-time
│   │   │   └── macro_adjustment.py    # Macroeconomic scenario overlay
│   │   ├── lgd_models.py              # Downturn LGD, collateral recovery
│   │   ├── ead_models.py              # EAD with CCF for revolving
│   │   ├── stage_classification.py    # SICR triggers, stage migration
│   │   ├── ecl_calculation.py         # 3-stage ECL with discounting
│   │   ├── scenario_engine.py         # Base/upside/downside scenarios
│   │   └── management_overlay.py      # Qualitative adjustments
│   │
│   ├── capital/
│   │   ├── __init__.py
│   │   ├── cet1.py                    # CET1 components and deductions
│   │   ├── at1.py                     # Additional Tier 1
│   │   ├── tier2.py                   # Tier 2 including AACL
│   │   ├── rwa_aggregation.py         # Total RWA from all risk types
│   │   ├── ratios.py                  # CET1, T1, Total, SLR ratios
│   │   ├── buffers.py                 # SCB, CCyB, GSIB surcharge
│   │   └── gsib/
│   │       ├── __init__.py
│   │       ├── method1.py             # BCBS method 1 (5 categories, 12 indicators)
│   │       ├── method2.py             # US method 2 (fixed coefficients, 1.2x adj)
│   │       ├── stwf.py                # Short-term wholesale funding (20%)
│   │       ├── data_averaging.py      # Daily/monthly averaging (2026 change)
│   │       └── gdp_indexing.py        # Nominal GDP coefficient indexing
│   │
│   ├── irb/
│   │   ├── __init__.py
│   │   ├── vasicek.py                 # IRB capital formula
│   │   ├── asset_correlation.py       # R = f(PD) by exposure class
│   │   ├── maturity_adjustment.py     # Maturity adjustment factor
│   │   └── output_floor.py            # 72.5% floor (for comparison)
│   │
│   ├── stress_testing/
│   │   ├── __init__.py
│   │   ├── scenario_design.py         # Severely adverse, adverse, baseline
│   │   ├── ppnr_model.py             # Pre-provision net revenue
│   │   ├── credit_loss_model.py       # Stressed PD/LGD by segment
│   │   ├── market_loss_model.py       # Trading book stress losses
│   │   ├── capital_trajectory.py      # 9-quarter capital projection
│   │   └── scb_calculation.py         # Stress capital buffer derivation
│   │
│   ├── pillar2/
│   │   ├── __init__.py
│   │   ├── icaap.py                   # Internal capital adequacy assessment
│   │   ├── irrbb.py                   # Interest rate risk in banking book
│   │   ├── concentration_risk.py      # Credit concentration (HHI, top-N)
│   │   ├── climate_risk.py            # Transition and physical risk
│   │   └── reverse_stress.py          # Reverse stress testing
│   │
│   ├── pillar3/
│   │   ├── __init__.py
│   │   ├── cc1_cc2.py                 # Capital composition and reconciliation
│   │   ├── cr1_cr5.py                 # Credit risk disclosure tables
│   │   ├── sec1_sec4.py               # Securitization disclosure
│   │   ├── mr1_mr4.py                 # Market risk disclosure
│   │   ├── or1.py                     # Operational risk disclosure
│   │   ├── lr1_lr2.py                 # Leverage ratio disclosure
│   │   └── km1.py                     # Key metrics
│   │
│   └── reporting/
│       ├── __init__.py
│       ├── fr_y9c.py                  # FR Y-9C Schedule HC-R
│       ├── ffiec_101.py               # FFIEC 101 Schedule A
│       ├── fr_y15.py                  # FR Y-15 Systemic Risk Report
│       ├── fr_y14.py                  # FR Y-14A/Q Capital Assessment
│       └── dashboard.py               # Interactive HTML dashboard
│
├── tests/
│   ├── __init__.py
│   ├── test_credit_risk.py
│   ├── test_saccr.py
│   ├── test_frtb.py
│   ├── test_oprisk.py
│   ├── test_cva.py
│   ├── test_ecl.py
│   ├── test_capital.py
│   ├── test_gsib.py
│   └── test_integration.py           # End-to-end capital calculation
│
├── data/
│   ├── sample_credit_portfolio.csv
│   ├── sample_trading_book.csv
│   ├── sample_derivatives.csv
│   └── sample_financials.json
│
├── docs/
│   ├── model_documentation.md         # SR 11-7 model documentation
│   ├── methodology.md                 # Calculation methodology
│   ├── validation_report.md           # Independent validation
│   └── user_guide.md                  # How to run
│
└── output/
    ├── .gitkeep
    └── (generated reports go here)
```

## Step 4: Create CLAUDE.md (Most Important File)

This is the file Claude Code reads to understand your project.
Save it as `CLAUDE.md` in the project root.
Content is below — copy it exactly.

## Step 5: Launch Claude Code

Option A — Local development:
```bash
cd basel-iii-endgame-engine
claude
```

Option B — Cloud (for GitHub repo not cloned locally):
Open Claude Code Desktop → Environment selector → Cloud environments → Default
Then navigate to the repo.

## Step 6: First Commands In Claude Code

```
# Tell Claude Code to read the project structure
> Read CLAUDE.md and set up the project skeleton

# Start with Phase 1 (FRTB) since we have the most work there
> Build src/market_risk/frtb/sbm/girr.py — full GIRR implementation with
  yield curve construction, 10 tenor vertices, inflation risk factor,
  cross-currency basis, proper DV01 from bond cash flows, tenor interpolation,
  negative rate lambda floor. Reference BCBS d457 Table 3 and ERBA P265-270.

# Then
> Build src/market_risk/frtb/sbm/delta.py — the aggregation engine
> Build src/market_risk/frtb/drc/drc_nonsec.py — full DRC with maturity weighting
# etc.
```

## Step 7: Development Phases

Phase 1: FRTB (~12,800 lines)
Phase 2: CRM (~2,500 lines)
Phase 3: SA-CCR Full (~3,500 lines)
Phase 4: Stress Testing (~5,000 lines)
Phase 5: Credit Classification (~3,500 lines)
Phase 6: ECL Full (~4,000 lines)
Phase 7: CVA Full (~2,500 lines)
Phase 8: Securitization (~2,500 lines)
Phase 9: IRB (~2,500 lines)
Phase 10: Pillar 2 (~3,500 lines)
Phase 11: Pillar 3 (~2,500 lines)
Phase 12: Infrastructure (~4,000 lines)
