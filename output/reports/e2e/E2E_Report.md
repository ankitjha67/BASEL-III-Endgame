# End-to-end run and smoke test

Entity: First National Banking Corp (synthetic)  
Reporting date: 2026-06-30  
Seed: 20260319  
Result: **18/18 stages passed**

All amounts in $M. Synthetic, seeded portfolio; figures illustrate the engine and are not a real bank.

## Smoke tests

| # | Stage | Status | Time (s) | Headline |
|---|---|---|---|---|
| 1 | Portfolio generation | PASS | 0.01 | 565 credit exposures ($1,763,400M EAD), 130 trading positions |
| 2 | SA credit risk (§ __.111) | PASS | 0.01 | EAD $1,924,996M  RWA $792,369M  density 41.2% |
| 3 | Off-balance sheet CCFs (§ __.112) | PASS | 0.01 | notional $903,275M  EAD $273,315M  RWA $168,602M |
| 4 | SA-CCR (§ __.114) | PASS | 0.12 | 300 netting sets  notional $5,740,825M  EAD $230,659M  RWA $143,616M |
| 5 | CVA (§ __.222) | PASS | 0.00 | BA-CVA-REDUCED K $10,113M  RWA $126,417M  (300 counterparties) |
| 6 | Securitization SEC-SA (§ __.133) | PASS | 0.00 | 15 tranches  exposure $48,500M  RWA $64,780M |
| 7 | Operational risk (§ __.150) | PASS | 0.00 | BI $83,980M  BIC $14,186M  RWA $177,330M  ILM 1.0 |
| 8 | FRTB SBM + DRC + RRAO | PASS | 0.60 | 167 sensitivities  SBM $16,260M  DRC $136M  RRAO $80M  RWA $205,949M |
| 9 | ECL / CECL | PASS | 0.01 | 530 loans  EAD $981,325M  ECL $16,624M  coverage 1.69% |
| 10 | RWA aggregation | PASS | 0.00 | total RWA $1,701,564M  (credit 70%, market 12%, op 10%, CVA 7%) |
| 11 | Capital stack | PASS | 0.00 | CET1 $208,000M  T1 $232,000M  Total $278,624M |
| 12 | G-SIB surcharge | PASS | 0.00 | proposal: M1 388bp (2.0%) | M2 664bp (3.4%) -> 3.4% (METHOD_2); current rule M2 779bp -> 4.0% |
| 13 | CCAR stress test | PASS | 0.00 | severely adverse min CET1 6.71% (Q9), SCB 5.51%, pass=True |
| 14 | Ratios, buffers, PCA | PASS | 0.00 | CET1 12.22%  T1 13.63%  Total 16.37%  SLR 5.91%  PCA WELL_CAPITALIZED |
| 15 | Large exposures (SCCL) | PASS | 0.00 | 30 counterparties, 23 reportable, 1 limit breaches, largest 18.4% of T1 |
| 16 | Fed reports (Y-9C, 101, Y-15, Y-14) | PASS | 0.00 | reports: FR_Y_9C, FFIEC_101, FR_Y_15, FR_Y_14 | cross-validation 4/4 | DQ pass=True |
| 17 | Pillar 3 disclosures | PASS | 0.00 | 5 templates: OV1, KM1, MR1, LR1, LR2 |
| 18 | Multi-jurisdiction comparison | PASS | 0.26 | BCBS CET1 11.5% | US CET1 13.1% | UK CET1 12.7% | EU CET1 12.2% | SG CET1 11.6% | CA CET1 11.7% |

### Plausibility and regulatory checks

| Stage | Check | OK | Detail |
|---|---|---|---|
| Portfolio generation | credit EAD $M | yes | 1,763,400 in [1,000,000, 3,000,000] |
| Portfolio generation | trading positions | yes | 130 in [50, 1,000] |
| SA credit risk (§ __.111) | on-balance RWA density | yes | 0.41 in [0.20, 0.70] |
| SA credit risk (§ __.111) | resi LTV<=50% RW (Table 5) | yes | 0.20 in [0.20, 0.20] |
| SA credit risk (§ __.111) | bank Grade B RW (Table 2) | yes | 0.75 in [0.75, 0.75] |
| Off-balance sheet CCFs (§ __.112) | OBS CCF-weighted EAD / notional | yes | 0.30 in [0.10, 0.60] |
| Off-balance sheet CCFs (§ __.112) | commitment <=1y CCF = 40% (§ __.112(b)(3)) | yes | 0.40 in [0.40, 0.40] |
| SA-CCR (§ __.114) | EAD / notional | yes | 0.040 in [0.002, 0.200] |
| SA-CCR (§ __.114) | alpha of commercial end-user sets = 1.0 | yes | 1.0 in [1.0, 1.0] |
| SA-CCR (§ __.114) | alpha of financial sets = 1.4 | yes | 1.4 in [1.4, 1.4] |
| CVA (§ __.222) | CVA RWA / CCR EAD | yes | 0.55 in [0.05, 1.50] |
| CVA (§ __.222) | RWA = 12.5 x K | yes | 12.50 in [12.50, 12.50] |
| Securitization SEC-SA (§ __.133) | senior tranche RW floor 15% | yes | 0.15 in [0.15, 0.30] |
| Securitization SEC-SA (§ __.133) | only SEC-SA used (US rule) | yes | 1 in [1, 1] |
| Operational risk (§ __.150) | BIC = $4.47B + 18% x (BI - $30B) | yes | 14,186 in [14,186, 14,187] |
| Operational risk (§ __.150) | RWA = 12.5 x BIC (no ILM) | yes | 12.50 in [12.50, 12.50] |
| FRTB SBM + DRC + RRAO | FRTB capital $M | yes | 16,476 in [1,000, 60,000] |
| FRTB SBM + DRC + RRAO | RRAO = 1.0% exotic + 0.1% other | yes | 80 in [80, 80] |
| ECL / CECL | allowance coverage | yes | 0.0169 in [0.0020, 0.0600] |
| RWA aggregation | total RWA $M | yes | 1,701,564 in [800,000, 2,500,000] |
| RWA aggregation | output floor not applied | yes | 0 in [0, 0] |
| Capital stack | CET1 $M | yes | 208,000 in [120,000, 280,000] |
| Capital stack | MSAs not deducted (250% RW instead) | yes | 0 in [0, 0] |
| G-SIB surcharge | surcharge between 1.0% and 5.0% | yes | 0.034 in [0.010, 0.050] |
| G-SIB surcharge | identified as GSIB (method 1 >= 130 bp) | yes | 388 in [130, 2000] |
| G-SIB surcharge | proposal lowers method 2 score vs current rule | yes | 0.853 in [0.000, 1.000] |
| CCAR stress test | severely adverse min CET1 >= 4.5% | yes | 0.0671 in [0.0450, 0.2000] |
| CCAR stress test | SCB floor 2.5% | yes | 0.0551 in [0.0250, 0.1000] |
| Ratios, buffers, PCA | CET1 ratio (CLAUDE.md 10-15%) | yes | 0.1222 in [0.1000, 0.1500] |
| Ratios, buffers, PCA | SLR (CLAUDE.md 5-7%) | yes | 0.0591 in [0.0500, 0.0700] |
| Ratios, buffers, PCA | SCB in buffer stack = stress-test SCB | yes | 0.0551 in [0.0551, 0.0551] |
| Large exposures (SCCL) | counterparties assessed | yes | 40 in [40, 40] |
| Fed reports (Y-9C, 101, Y-15, Y-14) | four Fed reports generated | yes | 4 in [4, 10] |
| Pillar 3 disclosures | Pillar 3 templates produced | yes | 5 in [4, 40] |
| Multi-jurisdiction comparison | six regimes computed | yes | 6 in [6, 6] |
| Multi-jurisdiction comparison | US: no output floor | yes | 0 in [0, 0] |
| Multi-jurisdiction comparison | EU floor factor 2027 (Art. 465(1)) | yes | 0.600 in [0.600, 0.600] |
| Multi-jurisdiction comparison | UK floor factor 2027 (Art. 92(5)) | yes | 0.600 in [0.600, 0.600] |
| Multi-jurisdiction comparison | CA floor factor (CAR Ch.1 1.5.1) | yes | 0.675 in [0.675, 0.675] |
| Multi-jurisdiction comparison | fully phased BCBS/EU/UK/SG floor 72.5% | yes | 0.725 in [0.725, 0.725] |
| Multi-jurisdiction comparison | UK/EU op-risk ILM = 1 (UK rule 5.9; CRR Art. 312) | yes | 1.00 in [1.00, 1.00] |

## Risk-weighted assets (FFIEC 101 Schedule A view)

| Component | RWA | Share |
|---|---|---|
| Credit risk (incl. OBS, CCR, securitization, 250% items) | 1,191,868 | 70.0% |
| Market risk (FRTB SA) | 205,949 | 12.1% |
| Operational risk (12.5 x BIC) | 177,330 | 10.4% |
| CVA risk | 126,417 | 7.4% |
| **Total** | **1,701,564** | 100% |

## Capital and ratios (FR Y-9C HC-R view)

| Item | Value |
|---|---|
| CET1 capital | 208,000 |
| Tier 1 capital | 232,000 |
| Tier 2 capital | 46,624 |
| Total capital | 278,624 |
| CET1 ratio | 12.22% |
| Tier 1 ratio | 13.63% |
| Total capital ratio | 16.37% |
| Supplementary leverage ratio | 5.91% |
| stress capital buffer | 5.51% |
| gsib surcharge | 3.40% |
| PCA category | WELL_CAPITALIZED |
| Meets minimums / buffers | True / False |

## Market risk (FRTB standardized)

| Charge | $M |
|---|---|
| girr charge | 4,436.5 |
| csr nonsec charge | 9,712.2 |
| equity charge | 905.8 |
| commodity charge | 930.7 |
| fx charge | 275.0 |
| sbm total | 16,260.2 |
| drc total | 135.7 |
| rrao total | 80.0 |
| total capital charge | 16,475.9 |

## Operational risk (§ __.150)

BI 83,980 = ILDC 51,733 + noninterest component 32,247; BIC 14,186; RWA 177,330; ILM 1.0.

## CVA (§ __.222)

Approach BA-CVA-REDUCED; K_unhedged 15,559; K 10,113; RWA 126,417 over 300 counterparties with total EAD 230,659.

## G-SIB surcharge

Method 1 388 bp -> 2.0%; Method 2 664 bp -> 3.4%; binding METHOD_2: **3.4%**.

## CCAR stress test (9 quarters)

| Scenario | Start CET1 | Min CET1 | Quarter of min | Peak-to-trough |
|---|---|---|---|---|
| BASELINE | 12.22% | 12.43% | Q1 | -0.21% |
| ADVERSE | 12.22% | 10.20% | Q9 | 2.02% |
| SEVERELY_ADVERSE | 12.22% | 6.71% | Q9 | 5.51% |

Stress capital buffer 5.51%; overall pass True.

## Regulatory reports

Generated: FR_Y_9C, FFIEC_101, FR_Y_15, FR_Y_14. Overall data-quality pass: True.

| Cross-validation check | Passed | Detail |
|---|---|---|
| Total RWA: FR Y-9C vs FFIEC 101 | True | RWA deviation: $0.00M |
| Credit Risk RWA: FR Y-9C vs FFIEC 101 | True | Credit Risk RWA deviation: $0.00M |
| CET1 ratio consistency: Part I vs Part II | True | CET1 ratio deviation: 0.000000 |
| G-SIB surcharge: FR Y-9C vs FR Y-15 | True | Surcharge deviation: 0.0000 |

## Multi-jurisdiction comparison (2027; end-state rules 2030)

Same synthetic bank under each rulebook. Held common: market risk RWA (US FRTB-SA engine); securitisation RWA (US SEC-SA engine); capital resources and leverage exposure measure.
FX: ECB euro foreign exchange reference rates, 31 December 2024 (EUR/USD 1.0389, as used in FR Doc. 2025-22964). The bank uses standardised approaches, so no output floor binds; see the floor what-if below (US proposal: no floor).

| Regime | SA credit RWA | CCR RWA | CVA RWA | Op RWA (ILM) | Total RWA | Floor factor | CET1 | CET1 req. | Surplus | Leverage req. |
|---|---|---|---|---|---|---|---|---|---|---|
| BCBS | 901,803 | 172,165 | 127,321 | 332,125 (1.30) | 1,804,143 | 70.0% | 11.53% | 9.00% | +2.53% | 4.00% |
| US | 871,269 | 127,420 | 127,321 | 190,350 (1.00) | 1,587,089 | none | 13.11% | 13.41% | -0.31% | 5.00% |
| UK | 873,951 | 137,790 | 105,594 | 255,796 (1.00) | 1,643,860 | 60.0% | 12.65% | 9.00% | +3.65% | 4.00% |
| EU | 884,032 | 172,165 | 127,321 | 256,348 (1.00) | 1,710,595 | 60.0% | 12.16% | 9.00% | +3.16% | 4.00% |
| SG | 895,989 | 172,165 | 127,321 | 331,503 (1.30) | 1,797,708 | 65.0% | 11.57% | 11.00% | +0.57% | 3.00% |
| CA | 876,268 | 172,165 | 127,321 | 332,088 (1.30) | 1,778,572 | 67.5% | 11.69% | 9.00% | +2.69% | 3.50% |

End-state rules (2030: transitionals such as equity phase-ins and the EU UCC CCF have run off):

| Regime | Total RWA | CET1 | vs 2027 |
|---|---|---|---|
| BCBS | 1,804,143 | 11.53% | +0 |
| US | 1,587,089 | 13.11% | +0 |
| UK | 1,652,581 | 12.59% | +8,721 |
| EU | 1,720,837 | 12.09% | +10,242 |
| SG | 1,803,522 | 11.53% | +5,814 |
| CA | 1,778,572 | 11.69% | +0 |

Output-floor what-if: floor add-on ($M) for a hypothetical internal-models bank whose modelled RWA is 50/60/70% of its standardised RWA (scenario grid, not model output):

| Regime | Year | Floor | 50% | 60% | 70% |
|---|---|---|---|---|---|
| BCBS | 2027 | 70.0% | 360,829 | 180,414 | 0 |
| US | 2027 | none | 0 | 0 | 0 |
| UK | 2027 | 60.0% | 164,386 | 0 | 0 |
| EU | 2027 | 60.0% | 171,060 | 0 | 0 |
| SG | 2027 | 65.0% | 269,656 | 89,885 | 0 |
| CA | 2027 | 67.5% | 311,250 | 133,393 | 0 |
| BCBS | 2030 | 72.5% | 405,932 | 225,518 | 45,104 |
| US | 2030 | none | 0 | 0 | 0 |
| UK | 2030 | 72.5% | 369,868 | 205,482 | 41,096 |
| EU | 2030 | 72.5% | 384,884 | 213,824 | 42,765 |
| SG | 2030 | 72.5% | 404,484 | 224,713 | 44,943 |
| CA | 2030 | 67.5% | 311,250 | 133,393 | 0 |

SA credit RWA by exposure class ($M):

| Class | BCBS | US | UK | EU | SG | CA |
|---|---|---|---|---|---|---|
| BANK | 55,157 | 71,157 | 55,157 | 55,157 | 55,157 | 55,157 |
| COMMERCIAL_RE | 88,299 | 88,299 | 103,351 | 88,299 | 88,299 | 88,299 |
| CORPORATE | 477,118 | 423,632 | 445,893 | 471,036 | 477,118 | 449,107 |
| CORPORATE_SME | 719 | 845 | 719 | 709 | 719 | 719 |
| COVERED_BOND | 1,141 | 4,563 | 1,141 | 1,141 | 1,141 | 2,281 |
| EQUITY | 21,747 | 24,114 | 13,026 | 13,026 | 15,933 | 21,747 |
| OTHER_ASSETS | 66,157 | 66,157 | 66,157 | 66,157 | 66,157 | 66,157 |
| PSE | 53,023 | 53,023 | 53,023 | 53,023 | 53,023 | 53,023 |
| RESIDENTIAL_RE | 74,546 | 74,546 | 71,587 | 71,587 | 74,546 | 75,882 |
| RETAIL_REGULATORY | 29,178 | 29,178 | 29,178 | 29,178 | 29,178 | 29,178 |
| RETAIL_TRANSACTOR | 17,801 | 17,801 | 17,801 | 17,801 | 17,801 | 17,801 |
| SOVEREIGN | 0 | 0 | 0 | 0 | 0 | 0 |
| SPECIALISED_LENDING_PF | 16,919 | 17,955 | 16,919 | 16,919 | 16,919 | 16,919 |
