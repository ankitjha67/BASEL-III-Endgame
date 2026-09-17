# End-to-End Audit — Code, Claims & Formulas

**Date:** 2026-09-17  
**Scope:** All `src/` modules, all `tests/`, `CLAUDE.md`, and the three
generated Word deliverables in `output/`.  
**Method:** Full test run; independent re-derivation of every core formula
against BCBS d457 (MAR21–23), BCBS d424 (CRE20/22/31/32/40/52, MAR50/51,
OpRisk §5), 12 CFR 217/252, and the project's own regulatory rules in
`CLAUDE.md`; numeric spot-checks of each suspected defect; cross-check of
document tables against code constants.

---

## 1. Headline

| Area | Result |
|---|---|
| Test suite (before audit) | 926 passed |
| Test suite (after fixes) | 931 passed (5 new regulatory tests added) |
| Formula defects found | **8** (all corrected in this commit) |
| Parameter tables that deviate from BCBS text | **9** (flagged `# TODO: VERIFY`, not rewritten) |
| Document / code inconsistencies | **4** (reported; documents not regenerated) |
| `CLAUDE.md` claims corrected | line counts, completion %, test counts |

**Direction of the formula defects:** 7 of 8 biased capital **downward**
(less conservative). Fixing them raises computed charges; no client-facing
numbers should be relied on from prior runs of the affected modules.

---

## 2. Formula defects — corrected

| # | Module | Defect | Regulatory text | Impact (illustrative) | Fix |
|---|---|---|---|---|---|
| F1 | `irb/irb_calculator.py` `compute_maturity_adjustment` | Used `1 + (M−2.5)b/(1−1.5b)`. A prior "test fix" changed the correct formula to satisfy a wrong test expectation (MA = 1 at M = 2.5). | BCBS d424 CRE31.6 / Basel II ¶272: `MA = (1 + (M−2.5)b) / (1 − 1.5b)` | PD 1 %, M 2.5 y: code 1.000 vs BCBS 1.260 → K understated 26 % | Formula restored; test rewritten to closed form |
| F2 | All six SBM classes (`girr/csr_nonsec/csr_sec/equity/commodity/fx.py`) — curvature intra-bucket | Diagonal term was `Σ CVR_k` (linear) added to a quadratic cross term under the square root. | MAR21.5(4): `K_b = √max(0, Σ max(CVR_k,0)² + Σ_{k≠l} ρ²·CVR_k·CVR_l·ψ)` | Two +50 000 CVRs, ρ = 1: code 70 711 vs BCBS 100 000 (−29 %) | Diagonal replaced with `Σ max(CVR_k,0)²` in all six |
| F3 | `utils/aggregation.py` + per-class `_inter_bucket_aggregation` in `csr_nonsec/equity/commodity.py` | `S_b` capped to `[−K_b, K_b]` **unconditionally**. | MAR21.4(4)–(5): first pass uses uncapped `S_b`; cap applies **only if** the radicand is negative | Two buckets, K_b 17.32, S_b 20, γ 0.5: code 30.0 vs BCBS 31.6 (−5 %) | Two-pass logic implemented in all four places |
| F4 | `drc/drc_nonsec.py` `_compute_hbr` | `HBR = max(ΣJTD⁺ + ΣJTD⁻, 0) / ΣJTD⁺` | MAR22.17: `HBR = ΣnetJTD_long / (ΣnetJTD_long + Σ|netJTD_short|)` | Long 100, short 50: code 0.50 vs BCBS 0.667 → shorts over-recognised | Formula corrected |
| F5 | `drc/drc_params.py` `LGD_VALUES` | Subordinated LGD 75 % | MAR22.12: equity **and non-senior debt** 100 %; senior 75 %; covered 25 % | Subordinated JTD understated 25 % | Set to 1.00; test updated |
| F6 | `saccr/saccr_params.py` | Credit single-name ρ = 0.8 | CRE52.72 Table 2: single-name credit ρ = **0.5**; index ρ = 0.8 | Over-states diversification within credit hedging sets | ρ = 0.5 for `CREDIT_IG/SPEC`; TODO for missing index classes |
| F7 | `securitization/sec_framework.py` `_compute_k_g` | `K_G = RWA / EAD` (a risk-weight density) | CRE40.48: `K_G = (RWA × 8 %) / EAD` (a capital requirement) | 50 %-RW pool: code 0.50 vs BCBS 0.04 → tranches misclassified against K_A | Corrected; new `MINIMUM_CAPITAL_RATIO` constant |
| F8 | `securitization/sec_framework.py` `_ssfa_risk_weight` | Returned `K_SSFA` as the risk weight; no straddle case | CRE40.51: `RW = 12.5 × K_SSFA(A,D)` when A ≥ K_A; CRE40.52 thickness-weighted blend of 1250 % and `12.5 × K_SSFA(K_A,D)` when A < K_A < D | Off by factor 12.5 (masked by floors in tests) | Both cases implemented; 2 closed-form tests added |

F7 and F8 interacted (K_G 12.5× too high, RW 12.5× too low) but do **not**
cancel because the SSFA exponent is non-linear in K_A.

---

## 3. Parameter tables that deviate from BCBS — flagged, not rewritten

These were implemented to the project's own written specification, which
in several places does not match the BCBS tables. Per `CLAUDE.md`
("NEVER fabricate regulatory parameters … flag with `# TODO: VERIFY`") each
now carries an in-source marker quoting the BCBS values. Re-mapping them
changes bucket taxonomies, public enums and many tests, so it is left as
an explicit decision for the owner.

| # | File / constant | Deviation |
|---|---|---|
| P1 | `girr_params.TENORS`, `core/enums.GIRRTenor` | 12 vertices; MAR21.8 prescribes **10** (no 7Y, 25Y). RWs on the extra vertices equal neighbours (1.1 %), so numerical effect is small. |
| P2 | `csr_nonsec_params.DELTA_RISK_WEIGHTS` | 18 buckets as sector×IG/HY pairs at 0.5–3.5 %. MAR21.13 Table 4 is a different taxonomy with Financials IG **5.0 %**, Financials HY **12 %**, Other 12 %, index buckets 1.5 %/5 %, etc. |
| P3 | `equity_params.EQUITY_DELTA_RW` / `_INTRA_CORR` | 5 EM + 5 AE + small + 2 index. MAR21.17 Table 8 is 4 EM + 4 AE + EM-small + AE-small + Other + 2 index; buckets 5–10 RWs differ (e.g. AE financials 50 %, not 20 %). |
| P4 | `commodity_params.COMMODITY_DELTA_RW` | Bucket definitions (light/middle/heavy distillates, base metals) do not match MAR21.19 Table 10 (freight 80 %, gaseous combustibles 35 %, …). |
| P5 | `csr_sec_params.CSR_SEC_NON_CTP_RW` | 8 buckets; MAR21.16 Table 6 has 25 (senior/non-senior × IG/HY × asset type). |
| P6 | `csr_sec_params.CSR_SEC_CTP_RW` | 5 buckets; MAR21.15 uses the 16-bucket CSR taxonomy with 2–16 % RWs. |
| P7 | `drc_params.DRC_SEC_RISK_WEIGHTS_*` | Rating×seniority table (0.4 %–64 %). MAR22.29 defines DRC-sec RW as **banking-book SEC RW ÷ 12.5** (AAA senior 15 % → 1.2 %). |
| P8 | `cva_params.BA_CVA_*` | Rating-based weights; α = 1.0; no `DF_c`; no `DS = 0.65`. MAR50.14/50.17 (rev. 2020) use a sector×IG/HY table, `SCR = (1/1.4)·RW·M·EAD·DF`, and a 0.65 discount scalar. Code cites ERBA p.281 — unverified. |
| P9 | `gsib_params.STWF_MATURITY_BUCKETS` | Single weight vector (25/10/3/1 %). 12 CFR 217.406(b) is a 4×4 grid of funding-category × maturity. |
| P10 | `sec_params.CONCENTRATION_*` | A "6 % per obligor below N = 6" SEC-SA add-on has no CRE40 source. Retained, flagged. |

Verified **correct** against source (no action): GIRR RWs/θ/floor/γ,
GIRR vega (100 %), FX 15 %/0.6, DRC non-sec RW table, DRC maturity
weighting, SA-CCR SFs, SD formula, IR 3-bucket aggregation, PFE multiplier,
RC (margined/unmargined), α 1.4/1.0, BIC 12/15/18 % at $1B/$30B, ILDC
2.25 % cap, ILM formula, SA-CR risk weights per `CLAUDE.md`, capital
minimums/CCB, threshold deductions (10 %/15 %), MSA 250 %, Tier 2
amortisation, G-SIB 20 bp/0.1 % bands and 130 bp threshold, SSFA exponent.

---

## 4. Internal inconsistencies (code ↔ code, doc ↔ doc)

| # | Where | Issue |
|---|---|---|
| I1 | `capital/capital_params.lookup_gsib_surcharge` vs `capital/gsib/gsib_calculator.score_to_surcharge` | Below 130 bp the first returns **0 %** ("not a G-SIB"), the second returns **1.0 %** ("designated minimum"). Both are defensible for different questions; callers must not mix them. Docstring note added. |
| I2 | `output/Deliverable_2_FINAL.docx` vs `NPR_2023_vs_2026` / `Four_Way` / code | Deliverable 2 shows US residential-mortgage LTV RWs of 20/25/…/40 % (these are the **BCBS** values). Code and the other two documents use 40/45/50/60/70/80/90 %. Deliverable 2's US column is wrong. |
| I3 | `Deliverable_2` vs `NPR_2023_vs_2026` | Bank Grade A: Deliverable 2 says "HC ≥ $3B: 40 % / Other: 30 %"; NPR doc (and the project brief) say Highly-Capitalised = **30 %**. Reversed in Deliverable 2. |
| I4 | `NPR_2023_vs_2026_Comparison.docx` | States "STWF coefficient 23.003". Code uses 350 ÷ 1.2 = 291.67 (12 CFR 217.406(c) base coefficient 350). 23.003 is unsupported by code or rule text. |

---

## 5. `CLAUDE.md` claims corrected

| Claim | Was | Actual (`wc -l`) |
|---|---|---|
| FRTB lines | 10,850 | 9,169 |
| Credit Risk lines | 4,600 | 4,378 |
| SA-CCR lines | 1,632 | 1,171 |
| Source total | "~54,000+" | 47,628 (below the 49,000 target) |
| Tests | "10,500+ lines" | 11,788 lines / 931 tests |
| Completion | "100 %" everywhere | Replaced with status + pointers to this report |

---

## 6. Other observations (no change made)

* Curvature inputs are pre-computed `CVR_k`; the engine does not compute
  up/down shocks itself. Acceptable interface, but documented nowhere in
  `CLAUDE.md`.
* Stress-testing provision rates (2.0 %/1.0 %) were **calibrated to make
  a "well-capitalised bank passes" test succeed**, not sourced from CCAR
  results. They should be treated as illustrative.
* ECL, Pillar 2/3, Reporting, Large Exposures and OBS/CCF modules were
  reviewed for formula content and found consistent with their cited
  sources; they are parameter-light and mostly structural.
* `utils/aggregation.curvature_aggregation` is a stub (`max(ΣCVR,0)`) that
  no module calls. Should be removed or implemented.

---

## 7. Recommended next steps (owner decision)

1. Decide whether to re-map P2–P7 to the BCBS bucket taxonomies (breaking
   change to enums/tests) or to document the project taxonomy as a
   deliberate simplification.
2. Confirm the BA-CVA calibration (P8) against ERBA NPR p.281 text.
3. Remove GIRR 7Y/25Y (P1) or add a vertex-mapping step.
4. Regenerate `Deliverable_2_FINAL.docx` to correct I2/I3; correct or
   source the 23.003 figure (I4).
5. Replace stress-test provision rates with published CCAR loss rates.
