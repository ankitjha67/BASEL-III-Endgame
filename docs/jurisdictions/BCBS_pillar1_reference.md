# BCBS Basel Framework — Pillar 1 Reference (Securitisation, SA-CVA, Leverage, Large Exposures, CCP)

Verbatim transcription of every table and formula implemented in `src/jurisdictions/bcbs/pillar1/`
(`BCBSPillar1`, `Jurisdiction.BCBS`).

**Sources**

| Short name | Document | Use |
|---|---|---|
| Framework | *The Basel Framework*, BIS consolidated standards, generated 29/10/2026 (1,429 pp.) | **Authority** |
| d424 | BCBS d424, *Basel III: Finalising post-crisis reforms*, December 2017 | Cross-check for MAR50 only |

Page numbers are the Framework's "n / 1429" footers. Equations that are images in the Framework were
read from the rendered PDF page (page cited). Where d424 differs, the Framework governs (§ 7).

---

## 1. Securitisation — general provisions (CRE40, pp. 348-391)

### 1.1 Tranche maturity — CRE40.22 (image, p. 353)

> "tranche maturity (M_T) is the tranche's remaining effective maturity in years ... In all cases,
> M_T will have a floor of one year and a cap of five years."

1. `M_T = Σ_t t·CF_t / Σ_t CF_t` (contractual cash flows; final legal maturity if unavailable)
2. `M_T = 1 + 80% · (M_L − 1)` (final legal maturity M_L)

CRE40.23: for commitments, maturity = contractual maturity of the commitment + longest maturity of
the assets exposed after a draw (caller's responsibility).

### 1.2 Due diligence — CRE40.31

> "Otherwise, the bank must assign a 1250% risk weight to any securitisation exposure for which it
> cannot perform the required level of due diligence."

### 1.3 Hierarchy — CRE40.41-40.48 (pp. 358-359)

| ¶ | Rule |
|---|---|
| 40.41 | "Securitisation exposures to which none of the approaches laid out in CRE40.42 to CRE40.48 can be applied must be assigned a 1250% risk weight." |
| 40.42 | "A bank must use the ... SEC-IRBA ... for a securitisation exposure of an IRB pool as defined in CRE40.15, unless otherwise determined by the supervisor." |
| 40.43 | "If a bank cannot use the SEC-IRBA, it must use the ... SEC-ERBA ... for a securitisation exposure to an SA pool ... provided that (1) the bank is located in a jurisdiction that permits use of the SEC-ERBA and (2) the exposure has an external credit assessment ... or there is an inferred rating ..." |
| 40.44 | SEC-IAA "for an unrated securitisation exposure (eg liquidity facilities and credit enhancements) to an SA pool within an ABCP programme", requires IRB approval for non-securitisation exposures. |
| 40.45 | "A bank that cannot use the SEC-ERBA or an SEC-IAA for its exposure to an SA pool may use the ... SEC-SA". |
| 40.46 | Mixed pools: SEC-IRBA where K_IRB can be calculated on at least 95%; `capital charge for mixed pool = d × K_IRB + (1 − d) × K_SA` (image, p. 359). |
| 40.47 | Below 95%: SA-pool hierarchy (CRE40.43-40.45). |
| 40.48 | "For resecuritisation exposures, banks must apply the SEC-SA, with the adjustments in CRE41.16. For ... non-performing loans ... the adjustments laid out in CRE45." |

### 1.4 Caps — CRE40.50-40.55

- **40.50** Senior look-through: "the senior securitisation exposure could receive a maximum risk
  weight equal to the exposure weighted-average risk weight applicable to the underlying exposures,
  provided that the bank has knowledge of the composition of the underlying exposures at all times."
  (1) SA or IRB pools: SA or IRB weighted-average RW; (2) mixed pools: SEC-IRBA uses SA for the SA
  part and IRB for the IRB part; SEC-SA / SEC-ERBA use the SA weighted-average RW.
  *Engine:* cap = 12.5 × K_SA (SEC-SA/ERBA/IAA) or 12.5 × K_IRB (SEC-IRBA), opt-in via
  `flags["senior_look_through_cap"]`.
- **40.51** "Where the risk weight cap results in a lower risk weight than the floor risk weight of
  15%, the risk weight resulting from the cap should be used."
- **40.52 / 40.53** Maximum capital requirement = capital of the underlying had they not been
  securitised (SEC-IRBA: any bank; SEC-ERBA/SA: originator or sponsor).
- **40.54** "The maximum aggregated capital requirement for a bank's securitisation exposures in the
  same transaction will be equal to K_P * P." P = largest proportion of interest held in any tranche;
  K_P = K_IRB (IRB pool), K_SA (SA pool), exposure-weighted mix (mixed pool).
  *Engine:* `apply_transaction_cap(rows, k_p, share_p, pool_exposure)` caps RWA at
  12.5 × K_P × P × pool exposure — **TODO: VERIFY** (scaling by the pool exposure amount is the
  engine's reading of "K_P * P").
- **41.19** "The caps described in CRE40.50 to CRE40.55 cannot be applied to resecuritisation exposures."

### 1.5 STC scope — CRE40.66-40.67, 40.94-40.95

- 40.66: "Only traditional securitisations including exposures to ABCP conduits ... fall within the
  scope of the simple, transparent and comparable (STC) framework." (Engine ignores `is_stc` on
  synthetic and resecuritisation positions and records a note.)
- 40.94 (Criterion D15) underlying RW limits: RRE value-weighted average ≤ 40%; regulatory CRE /
  other RE / land ADC individual ≤ 50%; regulatory retail individual ≤ 75%; other individual ≤ 100%.
- 40.95 (Criterion D16): single obligor ≤ 1% of the pool (2% under footnote 194 conditions).

(The engine takes `is_stc` from the caller; the criteria constants are in `params.py` for reference.)

---

## 2. SEC-SA (CRE41, pp. 392-396)

| ¶ | Text / formula |
|---|---|
| 41.2 | K_SA = weighted-average RW of the pool × 8% ("a weighted-average risk weight of 100% means that K_SA would equal 0.08"). |
| 41.6-41.7 | W = delinquent nominal / pool nominal; delinquent = 90+ dpd, bankruptcy/insolvency, foreclosure, REO, or in default per deal documents. |
| 41.8 (image p. 394) | `K_A = (1 − W) × K_SA + 0.5 W` |
| 41.9 (image p. 394) | delinquency unknown for ≤ 5%: `K_A = (EAD_subpool1 W known / EAD Total) × K_A^subpool1 + EAD_subpool2 W unknown / EAD Total` |
| 41.10 | unknown for more than 5%: 1250% |
| 41.11 (image p. 395) | `a = −(1/(p·K_A))`, `u = D − K_A`, `l = max(A − K_A; 0)`, `K_SSFA(K_A) = (e^{a·u} − e^{a·l}) / (a(u − l))` |
| 41.12 | p = 1 (not a resecuritisation) |
| 41.13 (image p. 395) | D ≤ K_A: 1250%; A ≥ K_A: `12.5 × K_SSFA`; A < K_A < D: `RW = [12.5 × (K_A − A)/(D − A)] + [12.5 × K_SSFA(K_A) × (D − K_A)/(D − A)]` |
| 41.15 | floor 15%; unrated junior below rated seniors: not lower than the next more senior rated exposure (not modelled — contract gap) |
| 41.16 | Resecuritisation: underlying capital via the securitisation framework; W = 0 for securitisation tranches in the pool; **p = 1.5** |
| 41.17 | Mixed resecuritisation pools: K_A per subset, nominal-weighted (caller supplies K_SA/W) |
| 41.18 | Resecuritisation floor **100%** |
| 41.21 | STC: **p = 0.5** |
| 41.22 | STC floors: **10% senior, 15% non-senior** |

---

## 3. SEC-ERBA (CRE42, pp. 397-403) and SEC-IAA (CRE43)

### 3.1 Table 1 (CRE42.2) and Table 3 (CRE42.12, STC) — short-term ratings

| External credit assessment | A-1/P-1 | A-2/P-2 | A-3/P-3 | All other ratings |
|---|---|---|---|---|
| Table 1 risk weight | 15% | 50% | 100% | 1250% |
| Table 3 (STC) risk weight | 10% | 30% | 60% | 1250% |

### 3.2 Table 2 (CRE42.4) and Table 4 (CRE42.13, STC) — long-term ratings

Columns: senior M_T = 1y, senior 5y, non-senior (thin) 1y, non-senior 5y.

| Rating | T2 S 1y | T2 S 5y | T2 NS 1y | T2 NS 5y | T4 S 1y | T4 S 5y | T4 NS 1y | T4 NS 5y |
|---|---|---|---|---|---|---|---|---|
| AAA | 15% | 20% | 15% | 70% | 10% | 10% | 15% | 40% |
| AA+ | 15% | 30% | 15% | 90% | 10% | 15% | 15% | 55% |
| AA | 25% | 40% | 30% | 120% | 15% | 20% | 15% | 70% |
| AA- | 30% | 45% | 40% | 140% | 15% | 25% | 25% | 80% |
| A+ | 40% | 50% | 60% | 160% | 20% | 30% | 35% | 95% |
| A | 50% | 65% | 80% | 180% | 30% | 40% | 60% | 135% |
| A- | 60% | 70% | 120% | 210% | 35% | 40% | 95% | 170% |
| BBB+ | 75% | 90% | 170% | 260% | 45% | 55% | 150% | 225% |
| BBB | 90% | 105% | 220% | 310% | 55% | 65% | 180% | 255% |
| BBB- | 120% | 140% | 330% | 420% | 70% | 85% | 270% | 345% |
| BB+ | 140% | 160% | 470% | 580% | 120% | 135% | 405% | 500% |
| BB | 160% | 180% | 620% | 760% | 135% | 155% | 535% | 655% |
| BB- | 200% | 225% | 750% | 860% | 170% | 195% | 645% | 740% |
| B+ | 250% | 280% | 900% | 950% | 225% | 250% | 810% | 855% |
| B | 310% | 340% | 1050% | 1050% | 280% | 305% | 945% | 945% |
| B- | 380% | 420% | 1130% | 1130% | 340% | 380% | 1015% | 1015% |
| CCC+/CCC/CCC- | 460% | 505% | 1250% | 1250% | 415% | 455% | 1250% | 1250% |
| Below CCC- | 1250% | 1250% | 1250% | 1250% | 1250% | 1250% | 1250% | 1250% |

### 3.3 Adjustments

- 42.5(1): "To account for tranche maturity, banks shall use linear interpolation between the risk
  weights for one and five years."
- 42.5(2) (image p. 399): `Risk weight = (risk weight from table after adjusting for maturity) × (1 − min(T, 50%))`,
  T = D − A, non-senior tranches only.
- 42.7: "The resulting risk weight is subject to a floor risk weight of 15%. In addition, the
  resulting risk weight should never be lower than the risk weight corresponding to a senior tranche
  of the same securitisation with the same rating and maturity."
- 42.11: under STC, CRE42.12, 42.13 and 42.14 apply **instead of** CRE42.2, 42.4 and **42.7** — so
  the senior-tranche comparison of 42.7 is not applied to STC positions.
- 42.14: STC floor 10% senior, 15% non-senior.
- CRE43.1 / 43.3: SEC-IAA internal assessments are "mapped to equivalent external ratings of an ECAI"
  and "assigned to the risk weight in the SEC-ERBA appropriate to the credit rating equivalent".

---

## 4. SEC-IRBA (CRE44, pp. 408-416)

| ¶ | Text / formula |
|---|---|
| 44.2 | K_IRB = IRB capital (incl. EL and dilution) / pool exposure amount |
| 44.14-44.15 | A, D definitions (outstanding-balance ratios, floored at zero) |
| 44.17 (image p. 413) | `p = max[0.3; (A + B/N + (C × K_IRB) + (D × LGD) + (E × M_T))]` |
| 44.18 | mixed retail/wholesale pool: subpool p weighted by nominal (caller) |
| 44.20 (image p. 413) | `N = (Σ_i EAD_i)² / Σ_i EAD_i²` |
| 44.21 (image p. 414) | `LGD = Σ_i LGD_i · EAD_i / Σ_i EAD_i` |
| 44.22 (image p. 414) | C1 ≤ 0.03: LGD = 0.50, `N = (C1·C_m + (C_m − C1)·max(1 − m·C1, 0)/(m − 1))^−1`; only C1: N = 1/C1 |
| 44.23 (image p. 414) | `K_SSFA(K_IRB) = (e^{a·u} − e^{a·l}) / (a(u − l))`, a = −1/(p·K_IRB), u = D − K_IRB, l = max(A − K_IRB, 0) |
| 44.24 (image p. 415) | D ≤ K_IRB: 1250%; A ≥ K_IRB: 12.5 × K_SSFA; else `RW = 12.5 × (K_IRB − A)/(D − A) + 12.5 × K_SSFA(K_IRB) × (D − K_IRB)/(D − A)` |
| 44.26 | floor 15% |
| 44.28 (image p. 415) | STC: `p = max[0.3; 0.5 × (A + B/N + (C × K_IRB) + (D × LGD) + (E × M_T))]` |
| 44.29 | STC floor 10% senior, 15% non-senior |

**Table 1 (CRE44.17) = Table 2 (CRE44.28)** — supervisory parameters

| Pool | Tranche | A | B | C | D | E |
|---|---|---|---|---|---|---|
| Wholesale | Senior, granular (N≥25) | 0 | 3.56 | -1.85 | 0.55 | 0.07 |
| Wholesale | Senior, non-granular (N<25) | 0.11 | 2.61 | -2.91 | 0.68 | 0.07 |
| Wholesale | Non-senior, granular (N≥25) | 0.16 | 2.87 | -1.03 | 0.21 | 0.07 |
| Wholesale | Non-senior, non-granular (N<25) | 0.22 | 2.35 | -2.46 | 0.48 | 0.07 |
| Retail | Senior | 0 | 0 | -7.48 | 0.71 | 0.24 |
| Retail | Non-senior | 0 | 0 | -5.78 | 0.55 | 0.27 |

---

## 5. NPL securitisations (CRE45, pp. 417-419)

- 45.1: NPL securitisation = W ≥ 90% at origination cut-off and on any later addition/removal.
- 45.3: SEC-IRBA precluded where K_IRB uses the foundation approach (`flags["kirb_foundation_approach"]`).
- 45.4: "The risk weight applicable to exposures to NPL securitisations according to SEC-IRBA (CRE44),
  SEC-SA (CRE41) or the look-through approach in CRE40.50 is floored at 100%."
- 45.5: where SEC-IRBA or SEC-SA must be used, "a bank may apply a risk weight of 100% to the senior
  tranche of an NPL securitisation provided that the NPL securitisation is a traditional
  securitisation and the sum of the non-refundable purchase price discounts (NRPPD) ... is equal to
  or higher than 50% of the outstanding balance of the pool" (`flags["npl_nrppd_at_least_50pct"]`).
- 45.7: CRE40.54 cap available to originators/sponsors, and investors using SEC-IRBA.

---

## 6. SA-CVA (MAR50.27-50.77, pp. 730-750)

### 6.1 Aggregation (images pp. 737-738)

- 50.41: "The multiplier m_CVA is set at 1." (supervisor may raise it)
- 50.51: `WS_k^CVA = RW_k · s_k^CVA`, `WS_k^Hdg = RW_k · s_k^Hdg`
- 50.52: `WS_k = WS_k^CVA − WS_k^Hdg`
- 50.53(1): `K_b = sqrt( (Σ_{k∈b} WS_k² + Σ_{k∈b} Σ_{l∈b, l≠k} ρ_kl WS_k WS_l) + R · Σ_{k∈b} (WS_k^Hdg)² )`, **R = 0.01**
- 50.53(2): `K = m_CVA · sqrt( Σ_b K_b² + Σ_b Σ_{c≠b} γ_bc S_b S_c )`
- 50.53(3): `S_b = max{−K_b; min(Σ_{k∈b} WS_k; K_b)}`
- 50.42-50.45: K_SA-CVA = Σ delta K over six risk classes + Σ vega K over five (no CCS vega).
- 50.1: RWA = 12.5 × capital requirement.

### 6.2 Interest rate (MAR50.54-50.58)

Buckets per currency; γ_bc = 0.5 (50.55). Specified currencies (reporting currency, USD, EUR, GBP,
AUD, CAD, SEK, JPY):

**Table 3** — RW: 1y 1.11%, 2y 0.93%, 5y 0.74%, 10y 0.74%, 30y 0.74%, inflation 1.11%.

**Table 4** — ρ_kl:

| | 1y | 2y | 5y | 10y | 30y | Inflation |
|---|---|---|---|---|---|---|
| 1y | 100% | 91% | 72% | 55% | 31% | 40% |
| 2y | | 100% | 87% | 72% | 45% | 40% |
| 5y | | | 100% | 91% | 68% | 40% |
| 10y | | | | 100% | 83% | 40% |
| 30y | | | | | 100% | 40% |
| Inflation | | | | | | 100% |

Other currencies (50.57): parallel curve shift and inflation, RW 1.58% each, ρ = 40%.
Vega (50.58): IR volatilities and inflation volatilities, RW 100%, ρ = 40%.

### 6.3 FX (MAR50.59-50.62)

Buckets per currency except the reporting currency; γ_bc = 0.6; delta RW 11%; vega RW 100%.

### 6.4 Counterparty credit spread (MAR50.63-50.65) — delta only

**Table 5** buckets: 1 a) sovereigns incl. central banks, MDBs; 1 b) local government,
government-backed non-financials, education, public administration; 2 financials incl.
government-backed financials; 3 basic materials, energy, industrials, agriculture, manufacturing,
mining and quarrying; 4 consumer goods and services, transportation and storage, administrative and
support service activities; 5 technology, telecommunications; 6 health care, utilities, professional
and technical activities; 7 other sector; 8 qualified indices.

**Table 6** γ_bc:

| | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| 1 | 100% | 10% | 20% | 25% | 20% | 15% | 0% | 45% |
| 2 | | 100% | 5% | 15% | 20% | 5% | 0% | 45% |
| 3 | | | 100% | 20% | 25% | 5% | 0% | 45% |
| 4 | | | | 100% | 25% | 5% | 0% | 45% |
| 5 | | | | | 100% | 5% | 0% | 45% |
| 6 | | | | | | 100% | 0% | 45% |
| 7 | | | | | | | 100% | 0% |
| 8 | | | | | | | | 100% |

Tenors 0.5, 1, 3, 5, 10 years (50.65(1)). **Table 7** RW (same for all tenors):

| Bucket | 1 a) | 1 b) | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| IG names | 0.5% | 1.0% | 5.0% | 3.0% | 3.0% | 2.0% | 1.5% | 5.0% | 1.5% |
| HY and NR names | 2.0% | 4.0% | 12.0% | 7.0% | 8.5% | 5.5% | 5.0% | 12.0% | 5.0% |

ρ_kl = ρ_tenor · ρ_name · ρ_quality (image p. 743):
- buckets 1-7: ρ_tenor 100% same tenor / 90%; ρ_name 100% same / 90% distinct but legally related /
  50% otherwise; ρ_quality 100% same (IG-IG or HY/NR-HY/NR) / 80%.
- bucket 8: ρ_tenor as above; ρ_name 100% same index and series / 90% same index distinct series /
  80% otherwise; ρ_quality 100% / 80%.

### 6.5 Reference credit spread (MAR50.66-50.69)

**Table 8**: 1-7 IG (sovereigns/MDBs; local government etc.; financials; basic materials...;
consumer...; technology/telecom; health care...), 8-14 HY and NR (same sectors), 15 other sector,
16 IG qualified indices, 17 HY qualified indices.

**Table 9** γ_bc (same credit quality):

| | 1/8 | 2/9 | 3/10 | 4/11 | 5/12 | 6/13 | 7/14 | 15 | 16 | 17 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1/8 | 100% | 75% | 10% | 20% | 25% | 20% | 15% | 0% | 45% | 45% |
| 2/9 | | 100% | 5% | 15% | 20% | 15% | 10% | 0% | 45% | 45% |
| 3/10 | | | 100% | 5% | 15% | 20% | 5% | 0% | 45% | 45% |
| 4/11 | | | | 100% | 20% | 25% | 5% | 0% | 45% | 45% |
| 5/12 | | | | | 100% | 25% | 5% | 0% | 45% | 45% |
| 6/13 | | | | | | 100% | 5% | 0% | 45% | 45% |
| 7/14 | | | | | | | 100% | 0% | 45% | 45% |
| 15 | | | | | | | | 100% | 0% | 0% |
| 16 | | | | | | | | | 100% | 75% |
| 17 | | | | | | | | | | 100% |

50.67(2): "For cross-bucket correlations γ_bc between buckets 1 to 14 of different credit quality
(ie IG and HY/NR), the correlations γ_bc specified in MAR50.67(1) are divided by 2."

**Table 10** RW (as printed): 1 0.5%, 2 1.0%, 3 5.0%, 4 3.0%, 5 3.0%, 6 2.0%, 7 1.5%, 8 2.0%,
9 4.0%, 10 12.0%, 11 7.0%, 12 8.5%, 13 5.5%, 14 5.0%, 15 12.0%, 16 1.5%, 17 5.0%.
Vega RW 100% (50.69(3)).

### 6.6 Equity (MAR50.70-50.73)

Large cap ≥ USD 2bn. **Table 11**: 1-4 large / emerging markets (1 consumer..., healthcare, utilities;
2 telecoms, industrials; 3 basic materials...; 4 financials, real estate, technology); 5-8 large /
advanced economies (same sector split); 9 small EM; 10 small advanced; 11 other sector;
12 qualified indices large cap advanced; 13 other qualified indices.

γ (50.71): 15% within 1-10; 75% between 12 and 13; 45% between 12 or 13 and 1-10; 0% with 11.

**Table 12** delta RW: 1 55%, 2 60%, 3 45%, 4 55%, 5 30%, 6 35%, 7 40%, 8 50%, 9 70%, 10 50%,
11 70%, 12 15%, 13 25%.

Vega (50.73(3)): "78% for large market capitalisation buckets and to 100% for the other buckets."
Engine: buckets 1-8 at 78%; **TODO: VERIFY** whether bucket 12 ("Large cap, advanced economies"
qualified indices) is a large-cap bucket — conservative placeholder 100%.

### 6.7 Commodity (MAR50.74-50.77)

**Table 13** buckets: 1 energy solid combustibles; 2 energy liquid combustibles; 3 electricity and
carbon trading; 4 freight; 5 metals non-precious; 6 gaseous combustibles; 7 precious metals
(including gold); 8 grains & oilseed; 9 livestock & dairy; 10 softs and other agriculturals;
11 other commodity. γ (50.75): 20% within 1-10; 0% with 11.

**Table 14** delta RW: 1 30%, 2 35%, 3 60%, 4 80%, 5 40%, 6 45%, 7 20%, 8 35%, 9 25%, 10 35%,
11 50%. Vega RW 100%.

---

## 7. Framework vs d424 (CVA chapter)

| Item | d424 (Dec 2017) | Framework MAR50 (July 2020 revisions) — used |
|---|---|---|
| m_CVA | 1.25 (para 40) | **1** (MAR50.41) |
| Cross-bucket aggregation | `K = m_CVA sqrt(ΣK_b² + ΣΣ γ K_b K_c)` (no S_b) | uses bounded S_b (MAR50.53(3)) |
| RCS bucket 8 delta RW | 3.0% | 2.0% (Table 10) |
| RCS vega RW | RW_σ·√12 with RW_σ = 55% | 100% (MAR50.69(3)) |
| RCS qualified-index buckets | none | 16 (IG), 17 (HY) |

---

## 8. Leverage ratio exposure measure (LEV30, pp. 790-810)

| ¶ | Rule |
|---|---|
| 30.2 | no recognition of collateral/CRM; no netting of assets and liabilities unless specified |
| 30.3 | Tier 1 deductions may be deducted from the exposure measure |
| 30.7 | national discretion: temporary exemption of central bank reserves in exceptional macroeconomic circumstances, with a commensurate recalibration of the minimum and disclosure |
| 30.8-30.9 | all balance sheet assets at accounting value less specific provisions |
| 30.14-30.16 (image p. 795) | `exposure measure = alpha × (RC + PFE)`, alpha = 1.4; `RC = max(V − CVM_r + CVM_p, 0)`; PFE per CRE52.20-52.76 with the multiplier fixed at one; margined maturity factor may be used; written options included |
| 30.22 | collateral received cannot reduce RC; multiplier fixed at one |
| 30.23 | gross up for derivative collateral provided that reduced balance sheet assets |
| 30.25 | eligible cash VM received reduces RC (not PFE) |
| 30.26 | clearing member need not recognise trade exposures to a QCCP where not obligated to reimburse the client |
| 30.31 | written credit derivatives: effective notional, less negative fair value in Tier 1, less eligible purchased protection on the same reference name |
| 30.37(1) | gross SFT assets; cash payables/receivables with the same counterparty netted only under three criteria |
| 30.37(2) (image p. 805) | `E* = max(0, Σ E_i − Σ C_i)` (qualifying MNA); `E_i* = max(0, E_i − C_i)` otherwise |
| 30.49 | 100% CCF: direct credit substitutes; forward asset purchases etc.; unsettled purchases (settlement-date accounting); other credit substitutes |
| 30.50 | 50%: NIFs and RUFs |
| 30.51 | 50%: transaction-related contingent items |
| 30.52 | 40%: commitments, regardless of maturity |
| 30.53 | 20%: short-term self-liquidating trade letters of credit |
| 30.54 | 10%: unconditionally cancellable commitments |
| 30.55 | lower of the two CCFs for commitments to provide an OBS item |
| 30.48 | provisions against OBS exposures may be deducted from the credit-equivalent amount (floored at zero) — not in the contract |

---

## 9. Large exposures (LEX10-LEX40, pp. 937-958)

| ¶ | Rule |
|---|---|
| LEX10.7 | only sovereigns (LEX30.31) are exempted counterparties |
| LEX10.8 | large exposure: "equal to or above 10% of the bank's Tier 1 capital" |
| LEX10.12 | control automatically if > 50% of voting rights |
| LEX10.18 | economic-interdependence check where exposures exceed 5% of Tier 1 |
| LEX20.1 | "must not be higher than 25% of the bank's Tier 1 capital at all times ... set at 15% for a G-SIB's exposures to another G-SIB" |
| LEX20.4 | report: all exposures ≥ 10% (after and before CRM), exempted exposures ≥ 10%, largest 20 |
| LEX30.6 | OBS: SA CCFs with a floor of 10% |
| LEX30.31 | sovereigns, central banks, PSEs treated as sovereigns exempt |
| LEX30.35 | intraday interbank exposures not subject to the framework (reporting or limit) |
| LEX30.38 | qualifying covered bonds: exposure value no less than 20% of nominal |
| LEX30.42-30.44 | look-through for underlying exposures ≥ 0.25% of Tier 1; unknown client |
| LEX30.48-30.49 | look-through value = pro rata share × min(tranche value, underlying nominal) |
| LEX30.54 | QCCP clearing exposures exempt, but reported |
| LEX30.55 | non-QCCP: clearing + non-clearing exposures, 25% limit |
| LEX30.57 Table 1 | trade exposures per CCR measures; segregated IM 0; non-segregated IM nominal; pre-funded DF nominal; unfunded DF 0; equity stakes nominal |
| LEX40.1 | G-SIB to G-SIB 15%, applied within 12 months of becoming a G-SIB |

---

## 10. CCP exposures (CRE54, pp. 483-494)

| ¶ | Rule |
|---|---|
| 54.1 fn 241 | 0% for prefunded default funds covering settlement-risk-only products |
| 54.6 | QCCP treatment for three months after a CCP ceases to qualify |
| 54.7 | clearing member trade exposure to a QCCP: **2%** |
| 54.8 | minimum MPOR 10 days for OTC trade exposures to CCPs |
| 54.12 | clearing member exposures to clients: bilateral, MPOR ≥ 5 days |
| 54.14-54.15 | client exposures: 2% where the two protection/portability conditions are met |
| 54.16 | **4%** where the client is not protected against joint default of the CM and another client |
| 54.17 | otherwise bilateral exposure to the clearing member |
| 54.20-54.21 | non-bankruptcy-remote posted collateral: 2% / 4%; custodian-held bankruptcy-remote collateral: 0 |
| 54.29 (image p. 491) | `K_CCP = Σ_{CM_i} EAD_i · RW · capital ratio`, RW = 20% (minimum, fn 244), capital ratio = 8% |
| 54.34 | SFT: `EAD_i = max(EBRM_i − IM_i − DF_i; 0)` |
| 54.36 (image p. 493) | `K_CM_i = max( K_CCP · DF_i^pref / (DF_CCP + DF_CM^pref) ; 8% · 2% · DF_i^pref )` (fn 245: 2% RW floor) |
| 54.40 | QCCP capital capped at the non-QCCP capital for the same exposures |
| 54.41 | non-QCCP trade exposures: SA risk weight by counterparty category |
| 54.42 | non-QCCP default fund (funded and unfunded): **1250%** |

Engine: RWA = 12.5 × K_CM_i. Non-QCCP trade RW uses CRE20.43 Table 10 (corporate) or, with
`flags["ccp_is_bank"]`, CRE20.18 Table 6 (bank ECRA); an unrated bank CCP needs an SCRA grade the
contract does not carry — **TODO: VERIFY**, conservative placeholder SCRA Grade C 150%.

---

## 11. Open items (TODO: VERIFY) and contract gaps

1. CRE40.54 maximum capital: scaling of "K_P * P" by the pool exposure amount (engine reading).
2. MAR50.73(3): vega RW of equity bucket 12 (placeholder 100%).
3. CRE54.41: unrated bank CCP (placeholder SCRA Grade C 150%).

Contract gaps (inputs that `pillar1_base.py` cannot carry — `flags` is `dict[str, bool]`):
mixed-pool share d (CRE40.46; use `mixed_pool_capital` to pre-blend K_IRB); unknown-delinquency share
(CRE41.9; use `k_a_partially_unknown_w`); next-senior rated RW for unrated juniors (CRE41.15); the
underlying-pool RW for the look-through cap when it differs from K_SA/K_IRB × 12.5 (CRE40.50);
resecuritisation subset K_A (CRE41.17); the clearing member's SA risk weight for CRE54.17 bilateral
client exposures; unfunded default fund commitments (CRE54.42); OBS provisions (LEV30.48) and
derivative collateral gross-up (LEV30.23) for leverage.
