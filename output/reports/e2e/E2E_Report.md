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
| 4 | SA-CCR (§ __.114) | PASS | 0.17 | 300 netting sets  notional $5,740,825M  EAD $230,659M  RWA $143,616M |
| 5 | CVA (§ __.222) | PASS | 0.00 | BA-CVA-REDUCED K $10,113M  RWA $126,417M  (300 counterparties) |
| 6 | Securitization SEC-SA (§ __.133) | PASS | 0.00 | 15 tranches  exposure $48,500M  RWA $51,346M |
| 7 | Operational risk (§ __.150) | PASS | 0.00 | BI $83,980M  BIC $14,186M  RWA $177,330M  ILM 1.0 |
| 8 | FRTB SBM + DRC + RRAO | PASS | 0.61 | 167 sensitivities  SBM $16,142M  DRC $136M  RRAO $80M  RWA $204,466M |
| 9 | ECL / CECL | PASS | 0.01 | 530 loans  EAD $981,325M  ECL $16,624M  coverage 1.69% |
| 10 | RWA aggregation | PASS | 0.00 | total RWA $1,686,647M  (credit 70%, market 12%, op 11%, CVA 7%) |
| 11 | Capital stack | PASS | 0.00 | CET1 $208,000M  T1 $232,000M  Total $278,624M |
| 12 | G-SIB surcharge | PASS | 0.00 | proposal: M1 388bp (2.0%) | M2 664bp (3.4%) -> 3.4% (METHOD_2); current rule M2 779bp -> 4.0% |
| 13 | CCAR stress test | PASS | 0.00 | severely adverse min CET1 6.77% (Q9), SCB 5.56%, pass=True |
| 14 | Ratios, buffers, PCA | PASS | 0.00 | CET1 12.33%  T1 13.76%  Total 16.52%  SLR 5.91%  PCA WELL_CAPITALIZED |
| 15 | Large exposures (SCCL) | PASS | 0.00 | 30 counterparties, 23 reportable, 1 limit breaches, largest 18.4% of T1 |
| 16 | Fed reports (Y-9C, 101, Y-15, Y-14) | PASS | 0.00 | reports: FR_Y_9C, FFIEC_101, FR_Y_15, FR_Y_14 | cross-validation 4/4 | DQ pass=True |
| 17 | Pillar 3 disclosures | PASS | 0.00 | 5 templates: OV1, KM1, MR1, LR1, LR2 |
| 18 | Multi-jurisdiction comparison | PASS | 0.65 | BCBS CET1 11.7% | US CET1 13.2% | UK CET1 12.8% | EU CET1 12.1% | SG CET1 11.7% | CA CET1 11.8% |

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
| FRTB SBM + DRC + RRAO | FRTB capital $M | yes | 16,357 in [1,000, 60,000] |
| FRTB SBM + DRC + RRAO | RRAO = 1.0% exotic + 0.1% other | yes | 80 in [80, 80] |
| ECL / CECL | allowance coverage | yes | 0.0169 in [0.0020, 0.0600] |
| RWA aggregation | total RWA $M | yes | 1,686,647 in [800,000, 2,500,000] |
| RWA aggregation | output floor not applied | yes | 0 in [0, 0] |
| Capital stack | CET1 $M | yes | 208,000 in [120,000, 280,000] |
| Capital stack | MSAs not deducted (250% RW instead) | yes | 0 in [0, 0] |
| G-SIB surcharge | surcharge between 1.0% and 5.0% | yes | 0.034 in [0.010, 0.050] |
| G-SIB surcharge | identified as GSIB (method 1 >= 130 bp) | yes | 388 in [130, 2000] |
| G-SIB surcharge | proposal lowers method 2 score vs current rule | yes | 0.853 in [0.000, 1.000] |
| CCAR stress test | severely adverse min CET1 >= 4.5% | yes | 0.0677 in [0.0450, 0.2000] |
| CCAR stress test | SCB floor 2.5% | yes | 0.0556 in [0.0250, 0.1000] |
| Ratios, buffers, PCA | CET1 ratio (CLAUDE.md 10-15%) | yes | 0.1233 in [0.1000, 0.1500] |
| Ratios, buffers, PCA | SLR (CLAUDE.md 5-7%) | yes | 0.0591 in [0.0500, 0.0700] |
| Ratios, buffers, PCA | SCB in buffer stack = stress-test SCB | yes | 0.0556 in [0.0556, 0.0556] |
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
| Multi-jurisdiction comparison | US adapter FRTB RWA / stage-10 FRTB RWA | yes | 0.994 in [0.950, 1.050] |
| Multi-jurisdiction comparison | US securitisation: SEC-SA / 1,250% only (§ __.133) | yes | 1 in [1, 1] |
| Multi-jurisdiction comparison | US adapter sec RWA = stage-8 SEC-SA RWA | yes | 51,346 in [51,345, 51,346] |
| Multi-jurisdiction comparison | UK leverage excludes central bank claims (Art 429a(A1)-(A2)) | yes | 320,000 in [320,000, 320,000] |
| Multi-jurisdiction comparison | no large-exposure limit breaches | yes | 0 in [0, 0] |

## Risk-weighted assets (FFIEC 101 Schedule A view)

| Component | RWA | Share |
|---|---|---|
| Credit risk (incl. OBS, CCR, securitization, 250% items) | 1,178,433 | 69.9% |
| Market risk (FRTB SA) | 204,466 | 12.1% |
| Operational risk (12.5 x BIC) | 177,330 | 10.5% |
| CVA risk | 126,417 | 7.5% |
| **Total** | **1,686,647** | 100% |

## Capital and ratios (FR Y-9C HC-R view)

| Item | Value |
|---|---|
| CET1 capital | 208,000 |
| Tier 1 capital | 232,000 |
| Tier 2 capital | 46,624 |
| Total capital | 278,624 |
| CET1 ratio | 12.33% |
| Tier 1 ratio | 13.76% |
| Total capital ratio | 16.52% |
| Supplementary leverage ratio | 5.91% |
| stress capital buffer | 5.56% |
| gsib surcharge | 3.40% |
| PCA category | WELL_CAPITALIZED |
| Meets minimums / buffers | True / False |

## Market risk (FRTB standardized)

| Charge | $M |
|---|---|
| girr charge | 4,427.7 |
| csr nonsec charge | 9,712.2 |
| equity charge | 902.8 |
| commodity charge | 856.8 |
| fx charge | 242.1 |
| sbm total | 16,141.6 |
| drc total | 135.7 |
| rrao total | 80.0 |
| total capital charge | 16,357.3 |

## Operational risk (§ __.150)

BI 83,980 = ILDC 51,733 + noninterest component 32,247; BIC 14,186; RWA 177,330; ILM 1.0.

## CVA (§ __.222)

Approach BA-CVA-REDUCED; K_unhedged 15,559; K 10,113; RWA 126,417 over 300 counterparties with total EAD 230,659.

## G-SIB surcharge

Method 1 388 bp -> 2.0%; Method 2 664 bp -> 3.4%; binding METHOD_2: **3.4%**.

## CCAR stress test (9 quarters)

| Scenario | Start CET1 | Min CET1 | Quarter of min | Peak-to-trough |
|---|---|---|---|---|
| BASELINE | 12.33% | 12.54% | Q1 | -0.21% |
| ADVERSE | 12.33% | 10.29% | Q9 | 2.04% |
| SEVERELY_ADVERSE | 12.33% | 6.77% | Q9 | 5.56% |

Stress capital buffer 5.56%; overall pass True.

## Regulatory reports

Generated: FR_Y_9C, FFIEC_101, FR_Y_15, FR_Y_14. Overall data-quality pass: True.

| Cross-validation check | Passed | Detail |
|---|---|---|
| Total RWA: FR Y-9C vs FFIEC 101 | True | RWA deviation: $0.00M |
| Credit Risk RWA: FR Y-9C vs FFIEC 101 | True | Credit Risk RWA deviation: $0.00M |
| CET1 ratio consistency: Part I vs Part II | True | CET1 ratio deviation: 0.000000 |
| G-SIB surcharge: FR Y-9C vs FR Y-15 | True | Surcharge deviation: 0.0000 |

## Multi-jurisdiction comparison (2027; end-state rules 2030)

Same synthetic bank under each rulebook. Held common: capital resources (CET1, Tier 1, total capital).
FX: ECB euro foreign exchange reference rates, 31 December 2024 (EUR/USD 1.0389, as used in FR Doc. 2025-22964). The bank uses standardised approaches, so no output floor binds; see the floor what-if below (US proposal: no floor).

| Regime | SA credit RWA | CCR RWA | CVA RWA | Op RWA (ILM) | Market RWA | Sec. RWA | CCP RWA | Total RWA | Floor factor | CET1 | CET1 req. | Surplus |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BCBS | 901,803 | 172,165 | 127,321 | 332,125 (1.30) | 206,233 | 35,554 | 7,378 | 1,782,579 | 70.0% | 11.67% | 9.00% | +2.67% |
| US | 871,269 | 127,420 | 127,321 | 190,350 (1.00) | 203,177 | 51,346 | 7,378 | 1,578,260 | none | 13.18% | 13.46% | -0.28% |
| UK | 873,951 | 137,790 | 105,594 | 255,796 (1.00) | 206,391 | 34,554 | 7,378 | 1,621,453 | 60.0% | 12.83% | 9.00% | +3.83% |
| EU | 884,032 | 172,165 | 127,321 | 256,348 (1.00) | 230,301 | 34,554 | 7,378 | 1,712,099 | 60.0% | 12.15% | 9.00% | +3.15% |
| SG | 895,989 | 172,165 | 127,321 | 331,503 (1.30) | 206,233 | 35,554 | 7,378 | 1,776,143 | 65.0% | 11.71% | 11.00% | +0.71% |
| CA | 876,268 | 172,165 | 127,321 | 332,088 (1.30) | 206,233 | 35,554 | 7,778 | 1,757,407 | 67.5% | 11.84% | 9.00% | +2.84% |

Market risk (FRTB standardised approach, $M capital; one regime-neutral trading book, USD reporting currency):

| Regime | SBM | Binding scenario | DRC | RRAO | RWA | GIRR | CSR | Equity | Commodity | FX |
|---|---|---|---|---|---|---|---|---|---|---|
| BCBS | 16,414 | LOW | 4 | 80 | 206,233 | 4,427 | 9,787 | 903 | 1,060 | 237 |
| US | 16,142 | LOW | 33 | 80 | 203,177 | 4,428 | 9,712 | 903 | 857 | 242 |
| UK | 16,415 | LOW | 16 | 80 | 206,391 | 4,428 | 9,787 | 903 | 1,060 | 237 |
| EU | 18,340 | LOW | 4 | 80 | 230,301 | 6,268 | 9,787 | 903 | 1,060 | 322 |
| SG | 16,414 | LOW | 4 | 80 | 206,233 | 4,427 | 9,787 | 903 | 1,060 | 237 |
| CA | 16,414 | LOW | 4 | 80 | 206,233 | 4,427 | 9,787 | 903 | 1,060 | 237 |

Securitisation risk weights by tranche (approach / RW; US: SEC-SA only, other regimes use SEC-ERBA for rated tranches subject to their hierarchy):

| Tranche | BCBS | US | UK | EU | SG | CA |
|---|---|---|---|---|---|---|
| RMBS-1-SNR | SEC_ERBA 20% | SEC_SA 15% | SEC_SA 15% | SEC_SA 15% | SEC_ERBA 20% | SEC_ERBA 20% |
| RMBS-1-MEZ | SEC_ERBA 158% | SEC_SA 46% | SEC_ERBA 158% | SEC_ERBA 158% | SEC_ERBA 158% | SEC_ERBA 158% |
| RMBS-1-JNR | SEC_ERBA 722% | SEC_SA 801% | SEC_ERBA 722% | SEC_ERBA 722% | SEC_ERBA 722% | SEC_ERBA 722% |
| RMBS-2-SNR | SEC_ERBA 20% | SEC_SA 15% | SEC_SA 15% | SEC_SA 15% | SEC_ERBA 20% | SEC_ERBA 20% |
| RMBS-2-MEZ | SEC_ERBA 158% | SEC_SA 45% | SEC_ERBA 158% | SEC_ERBA 158% | SEC_ERBA 158% | SEC_ERBA 158% |
| RMBS-2-JNR | SEC_ERBA 722% | SEC_SA 796% | SEC_ERBA 722% | SEC_ERBA 722% | SEC_ERBA 722% | SEC_ERBA 722% |
| CMBS-1-SNR | SEC_ERBA 20% | SEC_SA 15% | SEC_ERBA 20% | SEC_ERBA 20% | SEC_ERBA 20% | SEC_ERBA 20% |
| CMBS-1-MEZ | SEC_ERBA 158% | SEC_SA 619% | SEC_ERBA 158% | SEC_ERBA 158% | SEC_ERBA 158% | SEC_ERBA 158% |
| CMBS-1-JNR | SEC_ERBA 722% | RW_1250 1250% | SEC_ERBA 722% | SEC_ERBA 722% | SEC_ERBA 722% | SEC_ERBA 722% |
| CLO-1-SNR | SEC_ERBA 20% | SEC_SA 15% | SEC_ERBA 20% | SEC_ERBA 20% | SEC_ERBA 20% | SEC_ERBA 20% |
| CLO-1-MEZ | SEC_ERBA 158% | SEC_SA 566% | SEC_ERBA 158% | SEC_ERBA 158% | SEC_ERBA 158% | SEC_ERBA 158% |
| CLO-1-JNR | SEC_ERBA 722% | RW_1250 1250% | SEC_ERBA 722% | SEC_ERBA 722% | SEC_ERBA 722% | SEC_ERBA 722% |
| CLO-2-SNR | SEC_ERBA 20% | SEC_SA 15% | SEC_ERBA 20% | SEC_ERBA 20% | SEC_ERBA 20% | SEC_ERBA 20% |
| CLO-2-MEZ | SEC_ERBA 158% | SEC_SA 671% | SEC_ERBA 158% | SEC_ERBA 158% | SEC_ERBA 158% | SEC_ERBA 158% |
| CLO-2-JNR | SEC_ERBA 722% | RW_1250 1250% | SEC_ERBA 722% | SEC_ERBA 722% | SEC_ERBA 722% | SEC_ERBA 722% |

Leverage and large exposures:

| Regime | Exposure measure | Exclusions | Leverage ratio | Requirement | LE reportable | LE breaches | Largest non-exempt (% T1) |
|---|---|---|---|---|---|---|---|
| BCBS | 3,753,093 | 0 | 6.18% | 4.00% | 15 | 0 | 12.4% |
| US | 3,751,421 | 0 | 6.18% | 5.00% | 15 | 0 | 12.4% |
| UK | 3,433,093 | 320,000 | 6.76% | 4.00% | 920 | 0 | 12.4% |
| EU | 3,753,093 | 0 | 6.18% | 4.00% | 878 | 0 | 12.4% |
| SG | 3,753,093 | 0 | 6.18% | 3.00% | 15 | 0 | 12.4% |
| CA | 3,753,093 | 0 | 6.18% | 4.00% | 15 | 0 | 12.4% |

End-state rules (2030: transitionals such as equity phase-ins and the EU UCC CCF have run off):

| Regime | Total RWA | CET1 | vs 2027 |
|---|---|---|---|
| BCBS | 1,782,579 | 11.67% | +0 |
| US | 1,578,260 | 13.18% | +0 |
| UK | 1,630,174 | 12.76% | +8,721 |
| EU | 1,722,341 | 12.08% | +10,242 |
| SG | 1,781,957 | 11.67% | +5,814 |
| CA | 1,757,407 | 11.84% | +0 |

Output-floor what-if: floor add-on ($M) for a hypothetical internal-models bank whose modelled RWA is 50/60/70% of its standardised RWA (scenario grid, not model output):

| Regime | Year | Floor | 50% | 60% | 70% |
|---|---|---|---|---|---|
| BCBS | 2027 | 70.0% | 356,516 | 178,258 | 0 |
| US | 2027 | none | 0 | 0 | 0 |
| UK | 2027 | 60.0% | 162,145 | 0 | 0 |
| EU | 2027 | 60.0% | 171,210 | 0 | 0 |
| SG | 2027 | 65.0% | 266,421 | 88,807 | 0 |
| CA | 2027 | 67.5% | 307,546 | 131,806 | 0 |
| BCBS | 2030 | 72.5% | 401,080 | 222,822 | 44,564 |
| US | 2030 | none | 0 | 0 | 0 |
| UK | 2030 | 72.5% | 364,827 | 202,682 | 40,536 |
| EU | 2030 | 72.5% | 385,222 | 214,012 | 42,802 |
| SG | 2030 | 72.5% | 399,632 | 222,018 | 44,404 |
| CA | 2030 | 67.5% | 307,546 | 131,806 | 0 |

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
