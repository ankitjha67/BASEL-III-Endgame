# Singapore: MAS Notice 637 Part VIII, Market Risk (FRTB): parameter reference

**Source.** MAS Notice 637, *Notice on Risk Based Capital Adequacy Requirements for Banks Incorporated in Singapore*, version effective 1 January 2026, Part VIII:

| Division | Content | Paragraphs |
|---|---|---|
| 1 | Market RWA, method choice, SSA(MR) approval | 8.1.1 to 8.1.42 |
| 2 | SA(MR): SBM, DRC and RRAO | 8.2.1 to 8.2.218, Tables 8-1 to 8-15 |
| 3 | IMA | 8.3.1 to 8.3.245A, Tables 8-16 to 8-25 |
| 4 | SSA(MR) | 8.4.1 to 8.4.85, Annex 8E Tables 8E-1 to 8E-4 |

**How the text was read.** All values were transcribed from the extracted text of the Notice. The formulas were printed as math glyphs, and the extraction kept them legible. No page had to be rendered.

**Citations.** Citations give MAS paragraph and table numbers. MAS Division 2 transposes Basel MAR20 to MAR23 almost word for word. Where a MAS value equals the Basel value, the Basel paragraph follows in brackets, `[MARxx.yy]`.

**Implementation.** The code is in `src/jurisdictions/sg/frtb/`.

## 0. MAS deviations from Basel MAR

| # | MAS 637 | Basel | Effect in the engine |
|---|---|---|---|
| 1 | 8.2.92(a): GIRR weights "**must**" be divided by √2 for EUR, USD, GBP, AUD, JPY, SEK, CAD **and SGD**. The list is fixed. | MAR21.44: the bank "may" divide by √2, for the listed currencies plus "the domestic reporting currency of a bank" | The √2 reduction is mandatory. A reporting currency outside the list (for example CHF) gets no reduction. |
| 2 | 8.2.92(c): the 1.6% inflation and cross-currency basis weight is also divided by √2 for those currencies | MAR21.44 is ambiguous; the BCBS engine applies √2 to Table 1 only (TODO) | √2 applies to all GIRR delta weights of the listed currencies |
| 3 | 8.2.95: cross-currency bases (over USD or EUR) in the same bucket on different curves: 99.90%. 8.2.96: onshore/offshore curves may be simple-summed | MAR21.49: 0% between cross-currency bases | 99.90% (TODO: VERIFY against 8.2.98(c)) |
| 4 | 8.2.140: FX 15% "**must**" be divided by √2 for the specified pairs and their first-order crosses | MAR21.88: "may" | Mandatory |
| 5 | Table 8-3, buckets 2/10: "PSEs, education". Credit quality is set by the Table 7M-1 grade ("3" or better vs "4" or worse / not rated) | MAR21.51: "Local government, government-backed non-financials, education, public administration"; IG vs HY & NR | Same mapping (`LOCAL_GOVERNMENT` maps to bucket 2/10) |
| 6 | 8.2.184(b)(ii): **0%** DRC weight for central governments, central banks, BIS/IMF/ECB/EU/ESM/EFSF, PSEs and MDBs "that attract a 0% risk weight under the SA(CR)" | MAR22.7: national discretion | Mandatory. CQG "1" sovereigns get 0% automatically; other cases use flags. |
| 7 | 8.2.183: DRC buckets are (a) companies, (b) central governments, central banks and MDBs, (c) PSEs | MAR22.22: corporates / sovereigns / local governments and municipalities | MDB flag maps to bucket (b) |
| 8 | 8.2.196(b)(i): securitisation DRC weight = banking-book weight "divided by 12.5" | MAR22.34: "based on the corresponding risk weights" | Settles the BCBS TODO. The number is the same as 8%. |
| 9 | 8.2.165 to 8.2.166, 8.2.184(b)(iii) to (iv): funds treated as unrated equity get 15% (LGD 100%). Funds with a high-yield mandate use a mandate-fill weight | No fund rule in MAR22 | 15%. The high-yield mandate case uses a 100% placeholder (TODO). |
| 10 | 8.2.215: the listed/CCP exclusion applies "despite paragraph 8.2.210(b)" only. Instruments under 8.2.210(c) to (f) (behavioural prepayment, no maturity, no strike/barrier, multiple strikes/barriers) stay in scope | MAR23.7 excludes listed/CCP from all "other residual risk" | Flag `rrao_8_2_210_c_to_f` |
| 11 | Table 8-25: SGD is an IR specified currency (10 days). Equity repo and dividend rows are listed (large cap 20, small cap 60) | MAR33.12 Table 2 | IMA LH dictionary |
| 12 | 8.1.18(a): SSA(MR) approval screens market RWA against S$200 million and 2% of total RWA | MAR40.1: no numeric screen | `ssa_eligibility_screen` |
| 13 | 8.4.36(b)(i): 0% specific risk on a qualifying equity index | MAR40.43: 8% specific on all | SSA equity |
| 14 | Annex 8E para 1.4: 0% specific risk for Singapore Government / MAS paper in SGD funded in SGD, for domestic-currency CQG ≤ 3 sovereigns, and for 0%-weighted PSEs | No equivalent | `SGSSADebtPosition.zero_specific_risk` |
| 15 | Table 8-22 prints the backtesting **add-on** (0.20 to 0.50) | MAR32.9 prints the multiplier (1.70 to 2.00) | Same m_c |

## 1. Structure, aggregation and scenarios

| Item | Text | Citation |
|---|---|---|
| Market RWA | "12.5 times of … its market risk capital requirements using the SA(MR)" (also the IMA aggregation and the SSA(MR)), plus the Pillar 1 RWA surcharge, fund net short positions and CVA RWA | 8.1.1 [MAR20.1] |
| SA(MR) | "the sum of the following 3 components: (a) … SBM … (b) … DRC … (c) … RRAO" | 8.2.1 [MAR20.4] |
| Net sensitivity | offset "all sensitivities of opposite direction to the same risk factor, irrespective of the instruments" | 8.2.10(b), 8.2.11(b) |
| WS | WS_k = RW_k s_k | 8.2.10(d), 8.2.11(d) |
| Within bucket | K_b = √max(0, Σ_k WS_k² + Σ_k Σ_{k≠l} ρ_kl WS_k WS_l) | 8.2.10(e), 8.2.11(e) [MAR21.4(4)] |
| Across buckets | √(Σ_b K_b² + Σ_b Σ_{b≠c} γ_bc S_b S_c), S_b = Σ_k WS_k | 8.2.10(f), 8.2.11(f) |
| Alternative | if the sum is negative: S_b = max[min(Σ_k WS_k, K_b), −K_b] | 8.2.10(g), 8.2.11(g) [MAR21.4(5)(b)] |
| CVR | CVR_k^± = −Σ_i {V_i(x_k^{RW(curv)±}) − V_i(x_k) ∓ RW_k^{curv} × s_ik}. s_ik is the delta for FX/equity; for GIRR/CSR/commodity it is the sum over all tenors of the curve | 8.2.12(b) [MAR21.5(2)] |
| Curvature bucket | K_b = max(K_b⁺, K_b⁻); K_b^± = √max(0, Σ_k max(CVR_k^±, 0)² + Σ_k Σ_{l≠k} ρ_kl CVR_k^± CVR_l^± ψ(CVR_k^±, CVR_l^±)); ψ = 0 if both are negative, else 1. Tie: K_b⁺ if Σ CVR⁺ > Σ CVR⁻, K_b⁻ if Σ CVR⁺ < Σ CVR⁻ | 8.2.12(d) [MAR21.5(3)] |
| Curvature across | √max(0, Σ_b K_b² + Σ_b Σ_{c≠b} γ_bc S_b S_c ψ(S_b, S_c)); S_b = Σ CVR of the selected side | 8.2.12(e) [MAR21.5(4)] |
| Medium | ρ_kl, γ_bc "specified in paragraphs 8.2.91 to 8.2.157" | 8.2.14(a) |
| High | ρ and γ "multiplying … by 1.25, subject to a cap at 100%" | 8.2.14(b) [MAR21.6(2)] |
| Low | ρ_low = max(2 × ρ − 100%; 75% × ρ); γ_low = max(2 × γ − 100%; 75% × γ) | 8.2.14(c) [MAR21.6(3)] |
| SBM | per scenario, sum delta + vega + curvature over all risk classes, then take "the largest aggregate capital requirement from the 3 correlation scenarios" | 8.2.8(f) [MAR21.7] |
| No floor | no floor on the risk weights of 8.2.10(d), 8.2.11(d) or 8.2.12(b) | 8.2.9 |

## 2. GIRR

| Item | Text | Citation |
|---|---|---|
| Delta tenors | 0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30 years | 8.2.16(a) |
| Inflation / xccy | one flat curve per inflation rate, and per cross-currency basis over USD or EUR | 8.2.16(b) to (c), 8.2.22 |
| Buckets | "each currency as a separate delta risk bucket" | 8.2.91 [MAR21.41] |
| √2 | "divide the risk weights in Table 8-1 by the square root of 2 … for … EUR, USD, GBP, AUD, JPY, SEK, CAD and SGD"; also the 1.6% inflation and xccy weight for the same currencies | 8.2.92(a), (c) |
| Inflation / xccy RW | 1.6% (currencies not listed) | 8.2.92(d) [MAR21.43] |
| Same tenor, different curve | 99.90% | 8.2.93(a) [MAR21.45] |
| Different tenor, same curve | Table 8-2 | 8.2.93(b) [MAR21.46] |
| Different tenor and curve | Table 8-2 × 99.90% | 8.2.93(c) [MAR21.47] |
| Table 8-2 generator | max(e^(−θ·\|T_k − T_l\|/min(T_k; T_l)); 40%), θ = 3% (e.g. 1y vs 5y = 88.69%; with a different curve 88.60%) | fn 657 to 658 |
| Inflation | same curve: sum; different inflation curves: 99.90% | 8.2.94 |
| Xccy | different curves: 99.90%; onshore/offshore over the same base may be simple-summed | 8.2.95, 8.2.96 |
| Inflation vs yield | 40% | 8.2.97 [MAR21.48] |
| Xccy vs yield / inflation / another xccy | 0% | 8.2.98 [MAR21.49] |
| γ | 50% | 8.2.99 [MAR21.50] |
| Curvature | all risk-free curves of a currency form one factor; no curvature for inflation or xccy; shock = highest bucket RW (the 0.25y weight) | 8.2.27, 8.2.29, 8.2.153 fn 674 |

**Table 8-1** (GIRR delta risk weights, in percentage points):

| 0.25y | 0.5y | 1y | 2y | 3y | 5y | 10y | 15y | 20y | 30y |
|---|---|---|---|---|---|---|---|---|---|
| 1.7% | 1.7% | 1.6% | 1.3% | 1.2% | 1.1% | 1.1% | 1.1% | 1.1% | 1.1% |

**Table 8-2** (same bucket, different tenor, same curve):

| | 0.25 | 0.5 | 1 | 2 | 3 | 5 | 10 | 15 | 20 | 30 |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.25 | 100.0% | 97.0% | 91.4% | 81.1% | 71.9% | 56.6% | 40.0% | 40.0% | 40.0% | 40.0% |
| 0.5 | 97.0% | 100.0% | 97.0% | 91.4% | 86.1% | 76.3% | 56.6% | 41.9% | 40.0% | 40.0% |
| 1 | 91.4% | 97.0% | 100.0% | 97.0% | 94.2% | 88.7% | 76.3% | 65.7% | 56.6% | 41.9% |
| 2 | 81.1% | 91.4% | 97.0% | 100.0% | 98.5% | 95.6% | 88.7% | 82.3% | 76.3% | 65.7% |
| 3 | 71.9% | 86.1% | 94.2% | 98.5% | 100.0% | 98.0% | 93.2% | 88.7% | 84.4% | 76.3% |
| 5 | 56.6% | 76.3% | 88.7% | 95.6% | 98.0% | 100.0% | 97.0% | 94.2% | 91.4% | 86.1% |
| 10 | 40.0% | 56.6% | 76.3% | 88.7% | 93.2% | 97.0% | 100.0% | 98.5% | 97.0% | 94.2% |
| 15 | 40.0% | 41.9% | 65.7% | 82.3% | 88.7% | 94.2% | 98.5% | 100.0% | 99.0% | 97.0% |
| 20 | 40.0% | 40.0% | 56.6% | 76.3% | 84.4% | 91.4% | 97.0% | 99.0% | 100.0% | 98.5% |
| 30 | 40.0% | 40.0% | 41.9% | 65.7% | 76.3% | 86.1% | 94.2% | 97.0% | 98.5% | 100.0% |

## 3. CSR non-securitisation

| Item | Text | Citation |
|---|---|---|
| Tenors | 0.5, 1, 3, 5, 10 years; curve per issuer (bond or CDS) | 8.2.30 |
| Other sector | names "cannot be assigned to a specific sector" go to bucket 16 | 8.2.100 |
| Index | "more than 75%" of constituents (by weight) in one sector: that sector bucket (1 to 16); otherwise 17/18. Quality: "75% or more" of constituents CQG "3" or better gives bucket 17 / the upper block | 8.2.102, 8.2.104(c) |
| Quality | ECAI rating per 7.3.30. With IRBA approval, an internal rating may be mapped to Table 7M-1; otherwise "not rated" | 8.2.104(a) to (b) |
| Covered bonds | CQG "1": may use 1.5% | 8.2.107 [MAR21.53 fn 288] |
| ρ (1 to 15) | ρ_name 100% / 35%; ρ_tenor 100% / 65%; ρ_basis 100% / 99.90% (bond vs CDS). Example: 35% × 65% × 99.90% = 22.73% | 8.2.108, fn 661 [MAR21.54] |
| ρ (17 to 18) | name 80%; tenor 65%; basis 99.90% | 8.2.109 [MAR21.55] |
| Bucket 16 | K_b = Σ_k \|WS_k\| | 8.2.110 [MAR21.56] |
| γ | γ = γ_rating × γ_sector. γ_rating = 50% when both buckets are in 1 to 15 with different credit quality, else 100%. CQG ≥ 4 and unrated count as the same quality. γ_sector = 100% for the same sector, else Table 8-5 | 8.2.111 to 8.2.112 [MAR21.57] |

**Table 8-3** (CSR non-securitisation buckets):

| Bucket | Credit quality | Sector |
|---|---|---|
| 1 / 9 | CQG "3" or better / CQG "4" or worse or not rated | Sovereigns (central governments, central banks, BIS, IMF, ECB, EU, ESM, EFSF) and MDBs |
| 2 / 10 | as above | PSEs, education |
| 3 / 11 | as above | Financial Institutions |
| 4 / 12 | as above | Basic materials, energy, industrials, agriculture, manufacturing, mining and quarrying |
| 5 / 13 | as above | Consumer goods and services, transportation and storage, administrative and support service activities |
| 6 / 14 | as above | Technology, telecommunications |
| 7 / 15 | as above | Health care, utilities, professional and technical activities |
| 8 | CQG "3" or better | Covered bonds |
| 16 | n/a | Other sector |
| 17 | CQG "3" or better | Qualified indices |
| 18 | CQG "4" or worse or not rated | Qualified indices |

**Table 8-4** (risk weights, same for all tenors):

| Bucket | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RW | 0.5% | 1.0% | 5.0% | 3.0% | 3.0% | 2.0% | 1.5% | 2.5% | 2.0% | 4.0% | 12.0% | 7.0% | 8.5% | 5.5% | 5.0% | 12.0% | 1.5% | 5.0% |

**Table 8-5** (γ_sector):

| | 2/10 | 3/11 | 4/12 | 5/13 | 6/14 | 7/15 | 8 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1/9 | 75% | 10% | 20% | 25% | 20% | 15% | 10% | 0% | 45% | 45% |
| 2/10 | | 5% | 15% | 20% | 15% | 10% | 10% | 0% | 45% | 45% |
| 3/11 | | | 5% | 15% | 20% | 5% | 20% | 0% | 45% | 45% |
| 4/12 | | | | 20% | 25% | 5% | 5% | 0% | 45% | 45% |
| 5/13 | | | | | 25% | 5% | 15% | 0% | 45% | 45% |
| 6/14 | | | | | | 5% | 20% | 0% | 45% | 45% |
| 7/15 | | | | | | | 5% | 0% | 45% | 45% |
| 8 | | | | | | | | 0% | 45% | 45% |
| 16 | | | | | | | | | 0% | 0% |
| 17 | | | | | | | | | | 75% |

## 4. CSR securitisation: CTP

| Item | Text | Citation |
|---|---|---|
| Buckets | the Table 8-3 structure "except … buckets 17 and 18" | 8.2.114 |
| Index | more than 75% in one sector: buckets 1 to 15; otherwise bucket 16 | 8.2.114A |
| ρ | name 35%, tenor 65%, basis **99.00%** | 8.2.116 [MAR21.60] |
| Bucket 16 | Σ\|WS\| | 8.2.117 |
| γ | as in 8.2.111 | 8.2.118 |

**Table 8-6** (CTP risk weights):

| Bucket | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RW | 4.0% | 4.0% | 8.0% | 5.0% | 4.0% | 3.0% | 2.0% | 6.0% | 13.0% | 13.0% | 16.0% | 10.0% | 12.0% | 12.0% | 12.0% | 13.0% |

## 5. CSR securitisation: non-CTP

**Table 8-7** (buckets). Sectors run in this order: RMBS prime, RMBS mid-prime, RMBS sub-prime, CMBS, ABS student loans, ABS credit cards, ABS auto loans, CLO non-CTP.

| Buckets | Seniority and credit quality |
|---|---|
| 1 to 8 | Senior, CQG "3" or better |
| 9 to 16 | Subordinated, CQG "3" or better |
| 17 to 24 | CQG "4" or worse or not rated |
| 25 | Other sector (8.2.121(b)) |

**Table 8-8** (risk weights):

| Bucket | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RW | 0.9% | 1.5% | 2.0% | 2.0% | 0.8% | 1.2% | 1.2% | 1.4% | 1.125% | 1.875% | 2.5% | 2.5% | 1% |

| Bucket | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RW | 1.5% | 1.5% | 1.75% | 1.575% | 2.625% | 3.5% | 3.5% | 1.4% | 2.1% | 2.1% | 2.45% | 3.5% |

| Item | Text | Citation |
|---|---|---|
| ρ | ρ_tranche 100% for the same tranche ("more than 80% overlap in notional terms"), else 40%; ρ_tenor 80%; ρ_basis 99.90% | 8.2.123 [MAR21.68] |
| Bucket 25 | Σ\|WS\|, added to the result for buckets 1 to 24 | 8.2.124, 8.2.125(b) [MAR21.69, 21.71] |
| γ | 0% across buckets 1 to 24 | 8.2.125(a) [MAR21.70] |

## 6. Equity

**Table 8-9** (buckets):

| Bucket | Market cap | Economy | Sector |
|---|---|---|---|
| 1 / 5 | Large | EME / Advanced | Consumer goods and services, transportation and storage, administrative and support service activities, healthcare, utilities |
| 2 / 6 | Large | EME / Advanced | Telecommunications, industrials |
| 3 / 7 | Large | EME / Advanced | Basic materials, energy, agriculture, manufacturing, mining and quarrying |
| 4 / 8 | Large | EME / Advanced | Financial institutions, real estate activities, technology |
| 9 | Small | EME | All sectors of buckets 1 to 4 |
| 10 | Small | Advanced | All sectors of buckets 5 to 8 |
| 11 | n/a | n/a | Other sector |
| 12 | Large cap, advanced economy indices (non-sector specific) | | |
| 13 | Other equity indices (non-sector specific) | | |

**Table 8-10** (spot and repo risk weights):

| Bucket | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Spot | 55% | 60% | 45% | 55% | 30% | 35% | 40% | 50% | 70% | 50% | 70% | 15% | 25% |
| Repo | 0.55% | 0.60% | 0.45% | 0.55% | 0.30% | 0.35% | 0.40% | 0.50% | 0.70% | 0.50% | 0.70% | 0.15% | 0.25% |

| Item | Text | Citation |
|---|---|---|
| Large cap | market cap ≥ USD 2 billion, counting the issuer and its listed subsidiaries but not related corporations | 8.2.129(a) [MAR21.74] |
| Advanced economies | Canada, the United States, Mexico, the euro area, the United Kingdom, Norway, Sweden, Denmark and Switzerland, Japan, Australia, New Zealand, Singapore or Hong Kong SAR | 8.2.129(b) [MAR21.75] |
| Index | more than 75% in one sector: buckets 1 to 11, with "75% or more" large / advanced for size and economy; otherwise 12 if ≥ 75% of constituents are large cap and advanced economy, else 13 | 8.2.128 |
| ρ | spot vs repo, same name: 99.90%; spot vs spot: 15% (buckets 1 to 4), 25% (5 to 8), 7.5% (9), 12.5% (10), 80% (12, 13); repo vs repo: the same values; spot vs repo, different names: those values × 99.90% | 8.2.131 [MAR21.78] |
| Bucket 11 | Σ\|WS\| | 8.2.132 |
| γ | 15% (both buckets in 1 to 10); 0% (either is 11); 75% (12 and 13); 45% otherwise | 8.2.133 [MAR21.80] |

## 7. Commodity

**Table 8-11** (buckets and risk weights):

| Bucket | Commodity bucket | RW |
|---|---|---|
| 1 | Energy: solid combustibles | 30% |
| 2 | Energy: liquid combustibles | 35% |
| 3 | Energy: electricity and carbon trading | 60% |
| 4 | Freight | 80% |
| 5 | Metals: non-precious | 40% |
| 6 | Gaseous combustibles | 45% |
| 7 | Precious metals (including gold) | 20% |
| 8 | Grains and oilseed | 35% |
| 9 | Livestock and dairy | 25% |
| 10 | Soft commodity and other agricultural commodity | 35% |
| 11 | Other commodity | 50% |

**Table 8-12** (ρ_cty, by bucket 1 to 11): 55%, 95%, 40%, 80%, 60%, 65%, 55%, 45%, 15%, 40%, 15%.

| Item | Text | Citation |
|---|---|---|
| Tenors | 0, 0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30 years; by delivery location | 8.2.42 |
| ρ | ρ_cty × ρ_tenor (99%) × ρ_basis (99.90% across delivery locations). Example: Brent vs WTI = 95% × 99.00% × 99.90% = 93.96% | 8.2.135, fn 666 [MAR21.83] |
| γ | 20% (both buckets in 1 to 10); 0% if either is bucket 11 | 8.2.137 [MAR21.85] |

## 8. FX

| Item | Text | Citation |
|---|---|---|
| Bucket | "a currency pair for each currency … expressed against the reporting currency, or base currency" | 8.2.138 [MAR21.86] |
| RW | 15% | 8.2.139 [MAR21.87] |
| √2 | "must apply a risk weight of 15% divided by the square root of 2" for USD/EUR, USD/JPY, USD/GBP, USD/AUD, USD/CAD, USD/CHF, USD/MXN, USD/CNY, USD/NZD, USD/RUB, USD/HKD, USD/SGD, USD/TRY, USD/KRW, USD/SEK, USD/ZAR, USD/INR, USD/NOK, USD/BRL, and first-order crosses (e.g. EUR/AUD) | 8.2.140, fn 668 |
| γ | 60% | 8.2.141 [MAR21.89] |
| Curvature | instruments not referencing the reporting/base currency: CVR divided by 1.5; or, with approval, all instruments | 8.2.152 [MAR21.98] |

## 9. Vega and curvature

**Table 8-13** (vega):

| Risk class | LH (days) | RW |
|---|---|---|
| GIRR | 60 | 100% |
| CSR non-sec / CTP / non-CTP | 120 | 100% |
| Equity, vega buckets 1 to 8, 12, 13 | 20 | 77.78% |
| Equity, vega buckets 9 to 11 | 60 | 100% |
| Commodity | 120 | 100% |
| FX | 40 | 100% |

The weights come from fn 669: RW_k = min(RW_σ · √LH_risk class / √10; 100%), with RW_σ = 55%.

| Item | Text | Citation |
|---|---|---|
| Option-maturity tenors | 0.5, 1, 3, 5, 10 years (GIRR also uses the underlying residual maturity). Options with no maturity map to 10 years | 8.2.23 to 8.2.25, 8.2.70 |
| GIRR ρ | min(ρ_option maturity · ρ_underlying maturity; 1), with ρ = e^(−α·\|T_k − T_l\|/min(T_k; T_l)) and α = 1% | 8.2.145 [MAR21.93] |
| Other ρ | min(ρ_DELTA · ρ_option maturity; 1). ρ_DELTA uses only the dimensions vega shares with delta: name (CSR), tranche (sec non-CTP), commodity | 8.2.146 to 8.2.147 [MAR21.94] |
| Other bucket | Σ\|WS\| | 8.2.148 |
| γ | the delta γ; sec non-CTP bucket 25 added by simple sum | 8.2.149 |
| Curvature RW | FX and equity: the delta RW. GIRR/CSR/commodity: the highest delta RW of the bucket | 8.2.151, 8.2.153 |
| Curvature ρ | the square of the delta ρ (CSR: ρ_name; sec: ρ_tranche; commodity: ρ_cty) | 8.2.154 to 8.2.155 [MAR21.100] |
| Other bucket | K_b = max(Σ max(CVR_k⁺, 0), Σ max(CVR_k⁻, 0)) | 8.2.156 |
| Curvature γ | γ² (e.g. GIRR 50%² = 25%) | 8.2.157, fn 676 [MAR21.101] |

## 10. DRC

| Item | Text | Citation |
|---|---|---|
| Components | non-securitisations; securitisations (non-CTP); securitisations (CTP). No diversification across components | 8.2.159, 8.2.162 fn 679 |
| Gross JTD | JTD(long) = max(LGD × notional + P&L, 0); JTD(short) = min(LGD × notional + P&L, 0). Notional is signed (long +); a P&L loss is negative | 8.2.170, 8.2.172 [MAR22.11] |
| LGD | equity and subordinated debt 100%; senior 75%; covered bonds 25%; no LGD where the value is not linked to recovery; JTD = 0 where a derivative unwinds with no default exposure | 8.2.171, 8.2.174 [MAR22.12 to 22.13] |
| Maturity | weight = residual maturity / 1 year below 1 year; floor 1/4 (3 months); none at ≥ 1 year; cash equity is 3 months or > 1 year; derivatives use the derivative's maturity | 8.2.176 to 8.2.179 [MAR22.15 to 22.18] |
| Offsetting | long vs short of the same reference entity, "where the short exposure has the same or lower seniority" | 8.2.180 [MAR22.19] |
| Buckets | companies; central governments, central banks and MDBs; PSEs | 8.2.183 |
| Bucket DRC | DRC_b = max[(Σ_{i∈Long} RW_i · netJTD_i) − HBR · (Σ_{i∈Short} RW_i · \|netJTD_i\|); 0] | 8.2.184 [MAR22.25] |
| HBR | Σ netJTD_long / (Σ netJTD_long + Σ\|netJTD_short\|), unweighted, over the bucket | 8.2.184(c) [MAR22.23] |
| RW | Table 8-14. **0%** for central governments, central banks, the 7.3.46 entities, PSEs or MDBs at 0% under SA(CR). Unrated-equity funds 15%. Funds with a high-yield mandate use the mandate fill (8.2.166). "The same risk weight for instruments of the same credit quality across all 3 buckets" | 8.2.184(b), 8.2.185 |
| Aggregate | sum of the bucket DRC | 8.2.187 [MAR22.26] |

**Table 8-14** (default risk weights):

| AAA | AA | A | BBB | BB | B | CCC | Unrated | Defaulted |
|---|---|---|---|---|---|---|---|---|
| 0.5% | 2% | 3% | 6% | 15% | 30% | 50% | 15% | 100% |

The SA(CR) 0% cases (paras 7.3.42 to 7.3.51) are:

- Table 7-1: central government or central bank with CQG "1".
- 7.3.43: Singapore Government / MAS in SGD, funded in SGD.
- 7.3.46: BIS, IMF, ECB, EU, ESM, EFSF.
- 7.3.48 and Table 7-3: PSEs treated as the central government where that government has CQG "1".
- 7.3.51: qualifying MDBs.

**Securitisations (non-CTP).**

- JTD = market value (8.2.189).
- No offsetting across pools or across tranches (8.2.191). The same tranche may be offset across maturities, and perfect replications are allowed (8.2.192).
- Buckets follow Table 8-15 (46 buckets):
  - bucket 1: "Companies (excluding small businesses)", all regions;
  - buckets 2 to 12 (Asia), 13 to 23 (Europe), 24 to 34 (North America) and 35 to 45 (all other), each region in this asset-class order: ABCP, auto loans and leases, RMBS, credit cards, CMBS, CLO, CDO-squared, small businesses, student loans, other retail, other wholesale;
  - bucket 46: Others.
- RW_i = "the risk weight that would apply … in the banking book … divided by 12.5", with a one-year tranche maturity. The DRC of a non-derivative exposure is capped at its fair value (8.2.196(b)).
- The bucket formula and HBR are as for non-securitisations, per bucket. The total is the sum over buckets (8.2.196 to 8.2.197).

**CTP.**

- JTD = market value (8.2.199).
- An Nth-to-default instrument has attachment (N − 1)/Total names and detachment N/Total names (8.2.200).
- Offsetting is allowed within the same index family, series and tranche, and for replications. It is not allowed across tranches, series or families (8.2.202 to 8.2.204).
- Each index is its own bucket (8.2.205 to 8.2.206).
- RW: 8.2.196(b) for securitisation exposures; 8.2.184(b) for hedging non-securitisations (8.2.207).
- DRC_b = (Σ_{Long} RW_i · netJTD_i) − HBR_CTP · (Σ_{Short} RW_i · \|netJTD_i\|), with HBR_CTP taken across all buckets (8.2.208).
- Contribution_b = max[DRC_b, 0] + 0.5 × min[DRC_b, 0], and DRC_CTP = max(Σ_b Contribution_b, 0). Example (fn 705): 100 − 0.5 × 100 = 50 (8.2.209).

## 11. RRAO

| Item | Text | Citation |
|---|---|---|
| Scope | (a) exotic underlyings (fn 706: longevity, weather, natural disasters, future realised volatility); (b) other residual risks: payoffs not replicable by vanilla options, and CTP instruments other than hedges; (c) behavioural prepayment options; (d) options without maturity; (e) options without strike and barrier; (f) options with multiple strikes or barriers | 8.2.210 |
| Not in scope solely for | cheapest-to-deliver, smile, correlation from multi-underlying plain-vanilla European/American options, dividend risk where the underlying is not solely dividends | 8.2.212 |
| Exclusions | back-to-back (8.2.214); "Despite paragraph 8.2.210(b) … exclude any instrument that is listed or eligible for central clearing"; exotic underlyings stay in scope (8.2.215) | 8.2.214 to 8.2.215 |
| Capital | gross notional × 1.0% (exotic, 8.2.210(a)); × 0.1% (8.2.210(b) to (f)) | 8.2.217 [MAR23.8] |

## 12. IMA scalars

| Item | Value | Citation |
|---|---|---|
| ES | daily, 97.5th percentile, one-tailed | 8.3.182 [MAR33.3] |
| LH scaling | ES = √((ES_T(P))² + Σ_{j≥2} (ES_T(P, j) · √((LH_j − LH_{j−1})/T))²), T = 10 | 8.3.184 [MAR33.4] |
| Table 8-24 | LH_j = 10, 20, 40, 60, 120 days | 8.3.184 |
| Reduced set | ≥ 75% of full-set ES (12-week average); history back to 2007 | 8.3.186 |
| IMCC | ρ · IMCC(C) + (1 − ρ) · Σ_i IMCC(C_i), ρ = 0.5; IMCC(C_i) = ES_R,S,i × max(ES_F,C,i / ES_R,C,i, 1) | 8.3.199 to 8.3.200 [MAR33.15] |
| NMRF LH | max(Table 8-25 LH, 20 days) | 8.3.206 |
| SES | √Σ ISES²_NM,i + √Σ ISES²_NM,j + √((ρ · Σ SES_NM,k)² + (1 − ρ²) · Σ SES²_NM,k), ρ = 0.6 | 8.3.212 [MAR33.17] |
| C_A | max{IMCC_{t−1} + SES_{t−1}, m_c × IMCC_avg + SES_avg}, with 60-day averages; m_c = 1.5 + m_b + m_q | 8.3.242 [MAR33.41 to 33.42] |
| ACR_total | min{IMA_G,A + C_S + C_U, SA_all desks} + max{0, IMA_G,A − SA_G,A} | 8.3.243 [MAR33.43] |
| C_S | k × max{0, SA_G,A − IMA_G,A}, k = 0.5 × Σ_{i∈A} SA_i / Σ_{i∈G,A} SA_i | 8.3.244 [MAR33.45] |
| Desk backtesting | more than 12 exceptions (99%) or more than 30 (97.5%) puts the desk out of the IMA | 8.3.164 [MAR32.19] |
| PLA (Table 8-23) | Green: Spearman > 0.8 and KS < 0.09. Red: Spearman < 0.7 or KS > 0.12. Amber otherwise | 8.3.175 [MAR32.42] |

**Table 8-22** (backtesting add-on m_b):

| Exceptions | 0 to 4 | 5 | 6 | 7 | 8 | 9 | 10 or more |
|---|---|---|---|---|---|---|---|
| Zone | Green | Amber | Amber | Amber | Amber | Amber | Red |
| m_b | 0 | 0.20 | 0.26 | 0.33 | 0.38 | 0.42 | 0.50 |

**Table 8-25** (liquidity horizon n, in days):

- **Interest rate:** EUR, USD, GBP, AUD, JPY, SEK, CAD and SGD 10; other currencies 20; volatility 60; other types 60.
- **Credit spread:** sovereign IG 20; sovereign HY 40; corporate IG 40; corporate HY 60; volatility 120; other 120.
- **Equity:**
  - price: large cap 10, small cap 20;
  - volatility: large cap 20, small cap 60;
  - repo: large cap 20, small cap 60;
  - dividends: large cap 20, small cap 60;
  - other 60.
- **FX:** specified pairs (the 8.2.140 pairs plus EUR/JPY, EUR/GBP, EUR/CHF, JPY/AUD, and first-order crosses) 10; unspecified pairs 20; volatility 40; other 40.
- **Commodity:**
  - energy and carbon 20; precious and non-ferrous metals 20; other 60;
  - volatilities: 60 / 60 / 120;
  - other types 120.

## 13. SSA(MR)

| Item | Text | Citation |
|---|---|---|
| Formula | Capital = (CR_IRR × 1.3) + (CR_EQ × 3.5) + (CR_FX × 1.2) + (CR_COMM × 1.9) | 8.4.2 [MAR40.2] |
| Approval | for a portfolio that is "small and simple". The Authority considers market RWA > S$200 million or > 2% of total RWA, complexity, G-SIB status, IMA use and CTP holdings | 8.1.18 |
| IR specific risk | Table 8E-1 on net positions; securitisations at banking-book RW / 12.5 | 8.4.18 |
| IR general | maturity method (Table 8E-2, Table 8E-4) or, with approval, the duration method (Table 8E-3) | 8.4.20 to 8.4.25 |
| Equity | specific risk 0% for qualifying indices (Annex 8H), 8% otherwise; general 8% per country portfolio; +2% on qualifying indices; arbitrage 2% per side | 8.4.36 to 8.4.40 |
| FX | 8% × (max(Σ net long, Σ\|net short\|) + \|gold\|). Exempt with approval if business ≤ 100% and NOP ≤ 2% of Eligible Total Capital | 8.4.41 to 8.4.42 |
| Commodity | simplified: 15% of net + 3% of gross. Ladder: 1.5% spread, 0.6% carry, 15% residual | 8.4.59 to 8.4.60 |
| Options | simplified approach: currency and gold options 8%, commodity options 15% | 8.4.66 to 8.4.67 |

**Table 8E-1** (specific risk, positions other than securitisations):

| Category | CQG | Residual maturity | Charge |
|---|---|---|---|
| Government | 1 | n/a | 0.00% |
| Government | 2 or 3 | ≤ 6 months | 0.25% |
| Government | 2 or 3 | 6 to 24 months | 1.00% |
| Government | 2 or 3 | > 24 months | 1.60% |
| Government | 4 or 5 | n/a | 8.00% |
| Government | 6 | n/a | 12.00% |
| Government | unrated | n/a | 8.00% |
| Qualifying | n/a | ≤ 6 months | 0.25% |
| Qualifying | n/a | 6 to 24 months | 1.00% |
| Qualifying | n/a | > 24 months | 1.60% |
| Others | 4 | n/a | 8.00% |
| Others | 5 or 6 | n/a | 12.00% |
| Others | unrated | n/a | 8.00% |

Annex 8E para 1.4 sets a 0% charge for:

- Singapore Government or MAS securities in SGD, funded in SGD;
- other central governments with CQG ≤ 3, in domestic currency, funded in that currency;
- PSEs at 0% under SA(CR).

**Table 8E-2** (maturity bands; general risk charge and assumed change in yield):

| Band | Coupon ≥ 3% | Coupon < 3% | Charge | Δy |
|---|---|---|---|---|
| 1 | ≤ 1m | ≤ 1m | 0.00% | 1.00 |
| 2 | 1 to 3m | 1 to 3m | 0.20% | 1.00 |
| 3 | 3 to 6m | 3 to 6m | 0.40% | 1.00 |
| 4 | 6 to 12m | 6 to 12m | 0.70% | 1.00 |
| 5 | 1 to 2y | 1.0 to 1.9y | 1.25% | 0.90 |
| 6 | 2 to 3y | 1.9 to 2.8y | 1.75% | 0.80 |
| 7 | 3 to 4y | 2.8 to 3.6y | 2.25% | 0.75 |
| 8 | 4 to 5y | 3.6 to 4.3y | 2.75% | 0.75 |
| 9 | 5 to 7y | 4.3 to 5.7y | 3.25% | 0.70 |
| 10 | 7 to 10y | 5.7 to 7.3y | 3.75% | 0.65 |
| 11 | 10 to 15y | 7.3 to 9.3y | 4.50% | 0.60 |
| 12 | 15 to 20y | 9.3 to 10.6y | 5.25% | 0.60 |
| 13 | > 20y | 10.6 to 12y | 6.00% | 0.60 |
| 14 | n/a | 12 to 20y | 8.00% | 0.60 |
| 15 | n/a | > 20y | 12.50% | 0.60 |

Zones: bands 1 to 4 are zone 1, bands 5 to 7 zone 2, bands 8 to 15 zone 3.

**Table 8E-4** (matching factors):

| Item | Factor |
|---|---|
| Maturity band | 10% |
| Duration band | 5% |
| Within zone 1 | 40% |
| Within zone 2 | 30% |
| Within zone 3 | 30% |
| Adjacent zones | 40% |
| Zones 1 and 3 | 100% |

## 14. Open items (TODO: VERIFY)

1. **8.2.95 vs 8.2.98(c).** 8.2.95 sets 99.90% between cross-currency basis curves of the same bucket. 8.2.98(c) sets 0% between a cross-currency basis and "another cross-currency basis". The engine applies 99.90% to any two different xccy curves of one currency.
2. **8.2.166 (high-yield fund mandates).** The effective average RW depends on mandate limits, which are not an engine input. The placeholder is 100% (Defaulted, the highest weight in Table 8-14).
