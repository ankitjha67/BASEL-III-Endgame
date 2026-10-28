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
| P1 | `girr_params.TENORS`, `core/enums.GIRRTenor` | **RESOLVED (2026-10-28)** — reduced to the ten ERBA NPR §__.208(b)(1) vertices (7Y / 25Y removed). Specified-currency list aligned to §__.209(b)(1) (USD, AUD, CAD, EUR, JPY, SEK, GBP; CHF removed) and the sqrt(2) direction corrected: Table 1 is the base, specified currencies are *divided* by sqrt(2). Curvature now curve-level with ρ = 99.8 % cross-curve; inflation / xccy curvature rejected. |
| P2 | `csr_nonsec_params.DELTA_RISK_WEIGHTS` | **RESOLVED (2026-10-28)** — re-mapped to the 20 buckets of ERBA NPR §__.209(b)(2) Table 3 (IG / speculative / sub-speculative, Financials IG 5.0 %, spec financials 12 %, other 12 %, indices 1.5 % / 5 %), fixed 35 % / 65 % / 99.9 % intra-bucket ρ, Table 4 γ_sector × γ_rating. Remaining `TODO: VERIFY`: sub-speculative PSE / financials mapped to buckets 10 / 11. |
| P3 | `equity_params.EQUITY_DELTA_RW` / `_INTRA_CORR` | **RESOLVED (2026-10-28)** — re-mapped to the 13 buckets of ERBA NPR §__.209(b)(5) Table 8 (4 EM + 4 liquid-market large cap, EM / liquid small cap, other sector, 2 index); repo RW = spot / 100; ρ 15 / 25 / 7.5 / 12.5 / 80 %, bucket 11 Σ\|WS\|; γ 15 % / 45 % / 75 % / 0 %; vega RW 77.78 % / 100 % (Table 11). FX (`fx_params`) aligned in the same pass: 19-currency specified list, RW 15 % ÷ √2 for specified pairs, optional ÷1.5 curvature election. |
| P4 | `commodity_params.COMMODITY_DELTA_RW` | **RESOLVED (2026-10-28)** — re-mapped to the 12 buckets of ERBA NPR §__.209(b)(6) Table 9 (incl. freight 80 %, carbon 60 %, index bucket 12 at 30 %); Table 10 ρ_cty; flat 99 % tenor ρ, 99.9 % basis ρ; γ 20 % (0 % with bucket 11); energy-group 40 % rule removed. |
| P5 | `csr_sec_params.CSR_SEC_NON_CTP_RW` | **RESOLVED (2026-10-28)** — re-mapped to the 25 buckets of ERBA NPR §__.209(b)(4) Table 7 (senior IG / non-senior IG / spec & sub-spec × 8 asset types + other); ρ = ρ_tranche (40 %) × ρ_tenor (80 %) × ρ_basis (99.9 %); γ_bc = 0 %. |
| P6 | `csr_sec_params.CSR_SEC_CTP_RW` | **RESOLVED (2026-10-28)** — re-mapped to the 16 buckets of ERBA NPR §__.209(b)(3) Table 5 (2–16 % RWs); ρ = 35 % / 65 % / 99 %; γ = γ_rating × γ_sector (Table 6). Remaining `TODO: VERIFY`: sub-speculative PSEs mapped to bucket 9. |
| P7 | `drc_params.DRC_SEC_RISK_WEIGHTS_*` | **RESOLVED (2026-10-28)** — DRC-sec RW = banking-book SEC-SA RW × 8 % per ERBA NPR §__.210(c)(3)(iii) (15 % → 1.2 %); rating×seniority table retained only behind an explicit `legacy_rating_table=True` opt-in. Non-sec DRC re-mapped to the §__.210 credit-quality buckets in the same pass. |
| P8 | `cva_params.BA_CVA_*` | **RESOLVED (2026-10-28)** — rewritten to ERBA NPR §__.222: K = 0.65·(0.25·K_unhedged + 0.75·K_hedged), SCVA = (1/α)·RW·Σ M·EAD·DF, Table 1 sector × IG/spec/sub-spec weights, hedge terms SNH/IH/HMA. SA-CVA rewritten to §__.224–§__.225. The "ERBA NPR p. 281/282" citations in the old code did not correspond to the NPR text. |
| P9 | `gsib_params.STWF_MATURITY_BUCKETS` | Single weight vector (25/10/3/1 %). 12 CFR 217.406(b) is a 4×4 grid of funding-category × maturity. |
| P10 | `sec_params.CONCENTRATION_*` | **RESOLVED (2026-10-28)** — removed; ERBA NPR §__.133 specifies SEC-SA completely with no concentration add-on. |

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
| I2 | `output/Deliverable_2_FINAL.docx` vs `NPR_2023_vs_2026` / `Four_Way` / code | **FINDING REVERSED (2026-10-28)** — the ERBA NPR Table 5 to §__.111 prescribes 20/25/30/40/50/70 % over six LTV bands. Deliverable 2 was right; the code and the other two documents carried the 2023 NPR 40–90 % schedule and have been corrected. |
| I3 | `Deliverable_2` vs `NPR_2023_vs_2026` | Confirmed against Table 2 to §__.111: Grade A meeting §__.111(d)(2) (CET1 ≥ 14 % and leverage ≥ 5 %, or CBLR) = **30 %**, Grade A otherwise 40 %. Deliverable 2 reversed the two; corrected in the 2026-10-28 document regeneration. The "HC ≥ $3B" qualifier has no basis in the NPR text. |
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

1. ~~Decide whether to re-map P2–P7 to the BCBS bucket taxonomies~~ Superseded: P2–P7 re-mapped to the ERBA NPR tables (2026-10-28), which are the governing US text. (breaking
   change to enums/tests) or to document the project taxonomy as a
   deliberate simplification.
2. ~~Confirm the BA-CVA calibration (P8).~~ Done 2026-10-28 (P8 resolved against §__.222).
3. ~~Remove GIRR 7Y/25Y (P1) or add a vertex-mapping step.~~ Done 2026-10-28 (P1 resolved).
4. Regenerate `Deliverable_2_FINAL.docx` to correct I2/I3; correct or
   source the 23.003 figure (I4).
5. Replace stress-test provision rates with published CCAR loss rates.

---
---

# Part 2 — Reconciliation against the March 2026 ERBA NPR text

**Date:** 2026-10-28  
**Sources read end to end:**
1. OCC NR 2026-16a attachment — *Regulatory Capital Rules: Category I and II Banking
   Organizations; Banking Organizations with Significant Trading Activity* (OCC / Board / FDIC
   NPR, 1,241 pp.). Preamble sections I–XI and the complete common rule text (Subpart E
   § __.100–§ __.162, Subpart F § __.201–§ __.225, Parts 217/324 Subparts A–D/G amendments).
   The rule-text transcription used for the reconciliation is committed as
   `docs/ERBA_NPR_2026_parameter_reference.md`.
2. ISDA, *US Basel III Endgame: Trading and Capital Markets Impact — 2026 Update* (6 pp.):
   QIS results (FRTB-SA +89 %, IMA/SA blend +30 %, DRC ≈ 51 % of FRTB capital, CVA RWA ≈ $168 bn,
   CCR RWA 0.77× current) and industry recommendations. The ISDA note contains no rule
   parameters; it was used only to check impact statements in the project documents.

## 2.1 Headline

The engine had been built largely from BCBS d424 / d457 and from the July 2023 NPR. The
March 2026 NPR text differs from both in many places. **Every parameter table in the engine was
re-derived from the 2026 rule text**; the material corrections are listed below. Part 1 finding
I2 is **reversed**: the Deliverable 2 residential-mortgage column (20–70 %) was correct and the
code (40–90 %, the 2023 NPR schedule) was wrong.

## 2.2 Corrections by module (old → new, with NPR citation)

### Credit risk (SA) — `src/credit_risk/sa/`, `src/reference_data/regulatory_lookups.py`, `src/main_v4_poc.py`
| Item | Was | Now (ERBA NPR) |
|---|---|---|
| Residential mortgage RW (not dependent on cash flows) | 40/45/50/60/70/80/90 % over seven LTV bands | **20/25/30/40/50/70 %** over six bands (≤50/≤60/≤80/≤90/≤100/>100) — Table 5 to § __.111 |
| Residential mortgage dependent on cash flows | not modelled | 30/35/45/60/75/105 % — Table 6 |
| Other / past-due residential | not modelled | 100 % (not dependent) / 150 % — § __.111(f)(7)–(8) |
| Regulatory CRE not dependent on cash flows | not modelled (LTV table applied to all CRE) | LTV ≤ 60 %: min(60 %, borrower RW); else borrower RW — Table 7 |
| ADC (non-HVCRE) | 150 % (100 % if "pre-sold ADC") | **100 %**; HVCRE 150 %; pre-sold construction 50 %; statutory multifamily 50 % — § __.111(f)(1)–(4) |
| Bank exposures | CRC-of-home-sovereign table 20/50/100/150 % with a general ≤ 3-month 20 % preference | **Grade A 30 % (§ (d)(2) criteria) / 40 %, Grade B 75 %, Grade C 150 %**; 20/50/150 % only for foreign-bank trade-related contingent items ≤ 3 m; home-sovereign floor — Table 2 to § __.111 |
| Sovereign CRC 6 | 150 % | **100 %** (CRC 4–6) — Table 1; OECD-no-CRC 0 %, non-OECD 100 %, default 150 % added |
| Foreign PSEs | US 20/50 % applied to all | Tables 3–4 by home-country CRC |
| Corporate SME | 85 % | **100 %** — no SME weight in § __.111(h); project finance 130 %/100 % and object finance 100 % added |
| Publicly traded equity | 250 % | **300 %** — § __.141(b)(5); full 0/20/100/250/300/400/600 ladder implemented; FRB stock 0 %, FHLB/Farmer Mac 20 % |
| GSE class | absent | 20 %; subordinated 150 % (FHLB/Farmer Mac 20 %) — § __.111(c) |
| Commitments ≤ 1 year CCF | 20 % | **40 % regardless of maturity** — § __.112(b)(3) |
| Collateral haircuts (`crm.py`) | BCBS-style 0.5–10 %, gold 15 %, equities 15/25 % | Table 1 to § __.115 (sovereign 0.5–4 %, IG 2–20 % by five maturity bands, senior sec 4–24 %, main-index equities & gold 20 %, other 30 %); multi-collateral E* with the 0.4·net + 0.6·gross/√N terms — § __.115(b) |

### Counterparty credit risk — `src/counterparty_risk/saccr/`
| Item | Was | Now |
|---|---|---|
| Credit supervisory factors | single-name IG 0.38 %, spec 0.54 % (BCBS rating ladder) | **IG 0.46 %, speculative 1.3 %, sub-speculative 6.0 % (ρ 50 %); index IG 0.38 %, spec 1.06 % (ρ 80 %)** — Table 2 to § __.114; all credit trades aggregated in ONE hedging set |
| Margined maturity factor | 1.5·√(MPOR/250) applied to the netting-set add-on | **√(1.5·MPOR/250)** applied per trade — § __.114(i)(4)(i) |
| Unmargined maturity factor | absent (1.0) | √(min(M, 1y)/1y), M ≥ 10 business days — § __.114(i)(4)(ii) |
| Supervisory duration floor | none | 0.04 (ten business days) — § __.114(i)(2)(i)(A) |

### Capital — `src/capital/capital_components.py`
| Item | Was | Now |
|---|---|---|
| MSA threshold deduction | MSAs still tested against the 10 %/15 % thresholds | MSAs removed from both tests; all MSAs 250 % — NPR p. 40, § __.111(j)(4)(i) |

### Securitization — `src/securitization/`
| Item | Was | Now |
|---|---|---|
| SEC-ERBA (external ratings) | used whenever a rating was supplied, attributed to "ERBA NPR Tables 2-5" | **Off by default**; the US proposal has no external-ratings approach (Dodd-Frank § 939A) and "ERBA" means *expanded risk-based approach*. Retained for BCBS comparison only |
| Concentration add-on | 6 pp per obligor below N = 6 | **removed** — § __.133 specifies SEC-SA completely |
| Look-through / NPL | absent | constants added (senior look-through floor 15 %; NPL senior 100 % with ≥ 50 % discount) — § __.132(k)–(l) |

### Operational risk — `src/operational_risk/`
| Item | Was | Now |
|---|---|---|
| BI structure | BCBS ILDC + SC (max of fee income/expense) + FC | **Two components**: ILDC = min(Avg3y|NII|, 2.25 %·Avg3y IEA) + dividends; noninterest component = Avg3y(|noninterest income + realized HTM/AFS gains − noninterest expense for BI − 0.7·(net income from investment management, investment services and non-lending treasury services)| + total operational losses) — § __.150(c) |
| 0.7 factor scope | investment management only | investment management **+ investment services + non-lending treasury services** |
| ILM | "1.0" constant with formula available | no multiplier term exists; result validator rejects any ILM ≠ 1 — § __.150(a) |
| Loss collection threshold | $22,000 (EUR 20,000 proxy) | **$20,000**, CPI-W indexed — § __.150(d)(2)(i)(A) |

### CVA — `src/cva_risk/`
| Item | Was | Now |
|---|---|---|
| BA-CVA | rating-based weights "ERBA NPR p. 282", α = 1, no 0.65 scalar, hedge "discount factors" 0.5/0.25, M clipped to [1, 5] | **K = 0.65·(0.25·K_unhedged + 0.75·K_hedged)**, SCVA = (1/α)·RW·Σ M·EAD·DF, DF = (1 − e^(−0.05M))/(0.05M), Table 1 to § __.222 sector × IG/spec/sub-spec weights, r_hc 100/80/50 %, HMA, index hedges × 0.7 — § __.222 |
| SA-CVA | 10 invented buckets, 0.30 cross-type correlation, vega 0.55 × delta | 6 delta / 5 vega risk classes with Tables 1–9 to § __.225, R = 0.01, m_CVA = 1, S_b always capped — § __.224–§ __.225 |
| Scope | "all OTC + SFTs" | derivatives that are not cleared / client-facing; SFTs excluded; $1 T OTC notional threshold — § __.201(b)(2), § __.202 |

### FRTB sensitivities-based method — `src/market_risk/frtb/sbm/`
| Item | Was | Now (ERBA NPR § __.208–§ __.209) |
|---|---|---|
| GIRR delta vertices | 12 (incl. 7Y, 25Y) | **10**: 0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30 y — § __.208(b)(1) |
| GIRR √2 treatment | table treated as the low-volatility value; "high-vol" currencies × √2; CHF included | Table 1 is the base; **USD, AUD, CAD, EUR, JPY, SEK, GBP ÷ √2** (USD 0.25y = 1.7 %/√2) — § __.209(b)(1)(iv) |
| GIRR curvature ρ | tenor-level delta ρ squared | 100 % same curve / 99.8 % different curves; no inflation/xccy curvature — § __.209(d)(3)(i) |
| FX reduced RW | never applied (22 USD/EUR-centric pairs incl. RUB) | any pair of the 19 listed currencies ÷ √2 (EURUSD 15 %/√2); curvature ÷ 1.5 election added — § __.209(b)(7), (d)(2)(i)(A) |
| CSR non-sec buckets | 18 sector × IG/HY, RWs 0.5–3.5 % (financials IG 1 %) | **20 US buckets** by IG / speculative / sub-speculative: 0.5, 1.0, 5.0, 3.0, 3.0, 2.0, 1.5, 1.5, 3.0, 4.0, 12.0, 7.0, 8.5, 5.5, 5.0, 2.5, 7.0, 12.0, 1.5, 5.0 % — Table 3 |
| CSR non-sec correlations | ρ_name 0.50–0.80 by sector, GIRR tenor formula, heuristic γ 0.25–0.75 | ρ_name 35 % (80 % indices), ρ_tenor 65 %, ρ_basis 99.9 %; bucket 18 Σ\|WS\|; γ = γ_rating (50 %) × γ_sector Table 4 (e.g. γ(1,2) 75 %, γ(1,11) 5 %, γ(19,20) 75 %, γ(18,·) 0) |
| CSR non-sec tenors | 12 GIRR vertices | 0.5, 1, 3, 5, 10 y — § __.208(c) |
| CSR sec non-CTP | 8 buckets, γ 25 % | **25 buckets** (senior/non-senior IG, spec; 8 asset types + other) 0.80–3.50 %; ρ_tranche 100/40 %, ρ_tenor 100/80 %; **γ = 0** — Table 7 |
| CSR sec CTP | 5 buckets, γ 20 % | **16 buckets** 2–16 %; ρ_name 35 %, ρ_tenor 65 %, ρ_basis 99 %; γ_rating × Table 6 — Table 5 |
| Equity buckets 5–10 | AE large cap 25/25/30/20/25 %, "all small cap" 70 % | liquid-market large cap 30/35/40/50 %, small cap EM 70 % / liquid 50 %, other sector 70 % (Σ\|WS\|) — Table 8 |
| Equity repo-rate RW | absent | spot RW / 100 (0.55 %, 0.60 %, …); spot–repo ρ 99.9 % |
| Equity intra ρ | 15 % (1–5), 25 % (6–10), 7.5 % (11) | 15 % (1–4), 25 % (5–8), 7.5 % (9), 12.5 % (10), 80 % (12–13) |
| Equity inter-bucket γ | 15 % flat (75 % for 12–13) | 15 % within 1–10; 0 % with 11; 75 % between 12 and 13; **45 % index vs sector** |
| Equity vega RW | 55 % | **77.78 %** for buckets 1–8, 12, 13; 100 % for 9–11 — Table 11 |
| Commodity buckets | 11 (distillates / base metals taxonomy) | **12** per Table 9: 30/35/60/80/40/45/20/35/25/35/50/30 %; ρ_cty 55/95/40/80/60/65/55/45/15/40/15/50 % |
| Commodity tenor ρ / γ | exp(−0.01·Δ/min); γ 40 % within "energy" | flat 99 %; γ 20 % (0 % with bucket 11) |

### FRTB default risk charge — `src/market_risk/frtb/drc/`
| Item | Was | Now (ERBA NPR § __.210) |
|---|---|---|
| Risk-weight key | external rating AAA…CCC (0.5–50 %) | **credit quality × bucket**: non-US sovereign 0.6 %, PSE & GSE 2.1 %, corporate 4.1 % (IG); 22 % speculative; 50 % sub-speculative; defaulted 100 % — Table 1 to § __.210 |
| Buckets | corporate / sovereign / local government | non-US sovereign, PSE & GSE, corporate, defaulted; **US Treasury, supranationals and MDBs excluded** |
| LGD | 25 % "senior secured", 75 % senior, 100 % sub/equity | + 75 % GSE unguaranteed, 50 % US PSE, 25 % GSE-guaranteed and covered bonds, 0 % not linked to recovery — § __.210(b)(1)(iv) |
| Same-obligor offsetting | same seniority only | short seniority ≤ long seniority; UMBS offset across GSEs |
| Cash equity maturity | instrument maturity | 1-year default or 3-month election; hedged equity takes the derivative's maturity |
| Sec non-CTP exposure / RW | LGD 100 % × notional; rating × seniority table 0.4–100 % | market value; **RW = banking-book SEC-SA RW × 8 %** (legacy table only behind an explicit opt-in); in-bucket HBR; fair-value cap; asset class × region buckets |
| CTP | 50 % hedge benefit applied to shorts within each bucket | single HBR across all indices; unfloored bucket amounts; **total = max(Σ[max(DRC_b,0) + 0.5·min(DRC_b,0)], 0)**; nth-to-default A/D = (N−1)/N over total names |

## 2.3 Project documents (`output/*.docx`, README, migration guide)
(Populated from the document reconciliation.)

## 2.4 Items the NPR text does not settle (kept as `# TODO: VERIFY`)
* Mapping of "unrated" internal grades: the NPR has no unrated category; the engine maps
  UNRATED to speculative grade pending the bank's internal grade assignment.
* Sub-speculative PSE / financial CSR positions: Table 3 to § __.209 labels buckets 9–11
  "speculative grade" and gives no separate sub-speculative bucket; the engine maps them to
  buckets 10/11.
* DRC securitization risk weights require the banking-book SEC-SA risk weight as an input
  (RW_DRC = RW_SEC × 8 %); the legacy rating table is available only behind an explicit switch.
* G-SIB surcharge parameters (Method 2 coefficients, 1.2× factor, 20 bp bands) come from the
  separate G-SIB NPR, which was not part of this review.
