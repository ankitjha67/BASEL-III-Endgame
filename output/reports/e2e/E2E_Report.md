# End-to-end run and smoke test

Entity: First National Banking Corp (synthetic)  
Reporting date: 2026-06-30  
Seed: 20260319  
Result: **17/17 stages passed**

All amounts in $M. Synthetic, seeded portfolio; figures illustrate the engine and are not a real bank.

## Smoke tests

| # | Stage | Status | Time (s) | Headline |
|---|---|---|---|---|
| 1 | Portfolio generation | PASS | 0.01 | 565 credit exposures ($1,763,400M EAD), 130 trading positions |
| 2 | SA credit risk (§ __.111) | PASS | 0.01 | EAD $1,924,996M  RWA $792,369M  density 41.2% |
| 3 | Off-balance sheet CCFs (§ __.112) | PASS | 0.01 | notional $903,275M  EAD $273,315M  RWA $168,602M |
| 4 | SA-CCR (§ __.114) | PASS | 0.13 | 300 netting sets  notional $5,740,825M  EAD $230,659M  RWA $143,616M |
| 5 | CVA (§ __.222) | PASS | 0.00 | BA-CVA-REDUCED K $10,113M  RWA $126,417M  (300 counterparties) |
| 6 | Securitization SEC-SA (§ __.133) | PASS | 0.00 | 15 tranches  exposure $48,500M  RWA $64,780M |
| 7 | Operational risk (§ __.150) | PASS | 0.00 | BI $83,980M  BIC $14,186M  RWA $177,330M  ILM 1.0 |
| 8 | FRTB SBM + DRC + RRAO | PASS | 0.53 | 167 sensitivities  SBM $16,260M  DRC $136M  RRAO $80M  RWA $205,949M |
| 9 | ECL / CECL | PASS | 0.01 | 530 loans  EAD $981,325M  ECL $16,624M  coverage 1.69% |
| 10 | RWA aggregation | PASS | 0.00 | total RWA $1,701,564M  (credit 70%, market 12%, op 10%, CVA 7%) |
| 11 | Capital stack | PASS | 0.00 | CET1 $208,000M  T1 $232,000M  Total $278,624M |
| 12 | G-SIB surcharge | PASS | 0.00 | Method 1 512bp (2.9%) | Method 2 386bp (2.2%) -> 2.9% (METHOD_1) |
| 13 | Ratios, buffers, PCA | PASS | 0.00 | CET1 12.22%  T1 13.63%  Total 16.37%  SLR 5.91%  PCA WELL_CAPITALIZED |
| 14 | Large exposures (SCCL) | PASS | 0.00 | 30 counterparties, 23 reportable, 1 limit breaches, largest 18.4% of T1 |
| 15 | CCAR stress test | PASS | 0.00 | severely adverse min CET1 6.71% (Q9), SCB 5.51%, pass=True |
| 16 | Fed reports (Y-9C, 101, Y-15, Y-14) | PASS | 0.00 | reports: FR_Y_9C, FFIEC_101, FR_Y_15, FR_Y_14 | cross-validation 3/4 | DQ pass=False |
| 17 | Pillar 3 disclosures | PASS | 0.00 | 5 templates: OV1, KM1, MR1, LR1, LR2 | not produced: MR2, MR3, MR4 |

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
| G-SIB surcharge | surcharge between 1.0% and 5.0% | yes | 0.029 in [0.010, 0.050] |
| Ratios, buffers, PCA | CET1 ratio (CLAUDE.md 10-15%) | yes | 0.1222 in [0.1000, 0.1500] |
| Ratios, buffers, PCA | SLR (CLAUDE.md 5-7%) | yes | 0.0591 in [0.0500, 0.0700] |
| Large exposures (SCCL) | counterparties assessed | yes | 40 in [40, 40] |
| CCAR stress test | severely adverse min CET1 >= 4.5% | yes | 0.0671 in [0.0450, 0.2000] |
| CCAR stress test | SCB floor 2.5% | yes | 0.0551 in [0.0250, 0.1000] |
| Fed reports (Y-9C, 101, Y-15, Y-14) | four Fed reports generated | yes | 4 in [4, 10] |
| Pillar 3 disclosures | Pillar 3 templates produced | yes | 5 in [4, 40] |

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
| stress capital buffer | 3.20% |
| gsib surcharge | 2.90% |
| PCA category | WELL_CAPITALIZED |
| Meets minimums / buffers | True / True |

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

Method 1 512 bp -> 2.9%; Method 2 386 bp -> 2.2%; binding METHOD_1: **2.9%**.

## CCAR stress test (9 quarters)

| Scenario | Start CET1 | Min CET1 | Quarter of min | Peak-to-trough |
|---|---|---|---|---|
| BASELINE | 12.22% | 12.43% | Q1 | -0.21% |
| ADVERSE | 12.22% | 10.20% | Q9 | 2.02% |
| SEVERELY_ADVERSE | 12.22% | 6.71% | Q9 | 5.51% |

Stress capital buffer 5.51%; overall pass True.

## Regulatory reports

Generated: FR_Y_9C, FFIEC_101, FR_Y_15, FR_Y_14. Overall data-quality pass: False.

| Cross-validation check | Passed | Detail |
|---|---|---|
| Total RWA: FR Y-9C vs FFIEC 101 | True | RWA deviation: $0.00M |
| Credit Risk RWA: FR Y-9C vs FFIEC 101 | True | Credit Risk RWA deviation: $0.00M |
| CET1 ratio consistency: Part I vs Part II | True | CET1 ratio deviation: 0.000000 |
| G-SIB surcharge: FR Y-9C vs FR Y-15 | False | Surcharge deviation: 0.0060 |
