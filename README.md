# Basel III Endgame 2026 — Regulatory Capital Engine

Production-grade regulatory capital calculation engine implementing the US Federal Reserve's
March 2026 re-proposal (ERBA + Revised SA + G-SIB Surcharge).

## Coverage
- 12 calculation modules (~49,000 lines target)
- 61 ERBA exposure types with full risk weight assignment
- SA-CCR with 5 asset class add-ons
- FRTB SBM (7 risk classes × 3 correlation scenarios) + DRC + RRAO + IMA
- Operational risk (BIC with ILM=1)
- CVA risk (BA-CVA + SA-CVA)
- ECL/CECL (3-stage, 18 segments, macro scenarios)
- G-SIB surcharge (Method 1 + Method 2 with 1.2× adjustment)
- Fed reporting: FR Y-9C, FFIEC 101, FR Y-15, Pillar 3

## Quick Start
```bash
pip install -r requirements.txt
python -m src.main
```

## Development With Claude Code
```bash
claude  # Opens Claude Code in this directory
# Claude Code reads CLAUDE.md for project context
```
