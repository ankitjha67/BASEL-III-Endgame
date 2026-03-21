# Basel III Endgame Capital Calculation Engine

## Project Overview
Production-grade regulatory capital calculation engine implementing the Basel III
Endgame rules (US Federal Reserve final rule). Covers Market Risk (FRTB),
Credit Risk, Operational Risk, CVA Risk, and the Output Floor.

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

## Build Phases
- **Phase 1**: Market Risk → FRTB → SBM → GIRR (Delta, Vega, Curvature)
- **Phase 2**: SBM → CSR, Equity, Commodity, FX
- **Phase 3**: DRC + RRAO
- **Phase 4**: Credit Risk (SA-CR)
- **Phase 5**: Operational Risk + CVA Risk + Output Floor

## Key Conventions
- Python 3.11+, type hints everywhere, numpy/pandas for numerics
- All monetary values in USD unless specified
- Regulatory references use MAR21/MAR22 notation (Basel Committee)
- Every module has docstrings with regulatory paragraph references
- Tests use pytest with parametrize for multiple scenarios
- Risk weights and correlations in config/regulatory_params.json

## Commands
- `pytest tests/ -v` — run all tests
- `pytest tests/market_risk/frtb/sbm/ -v` — run GIRR tests
- `python -m mypy src/ --strict` — type checking
- `python -m ruff check src/` — linting

## Current Phase: Phase 1 — GIRR
GIRR = General Interest Rate Risk under FRTB SBM.
Components: Delta, Vega, Curvature risk charges.
Buckets: One per currency. Tenors: 0.25Y–30Y.
Three correlation scenarios: Low, Medium, High.
