# Canada: OSFI CAR 2026 Chapter 9, Market Risk (FRTB): parameter reference

Source: OSFI *Capital Adequacy Requirements (CAR) Guideline 2026*, Chapter 9, Market Risk ("valid until the end of the reporting period on January 31, 2027"). The source was the plain text of the OSFI web page; table structures were checked against the raw HTML. Each OSFI paragraph ends with its Basel cross-reference in brackets, which is reproduced here as `[MARxx.yy]`.

**Paragraph numbers (¶).** The web text does not print OSFI paragraph numbers. The numbers below come from the text's own cross-references, which fix a one-to-one mapping inside section 9.5:

- ¶(107+n) = MAR20.n
- ¶(112+n) = MAR21.n
- ¶(213+n) = MAR22.n
- ¶(258+n) = MAR23.n

Twenty internal references were checked against this mapping, for example:

- "paragraph 163" = CSR Table 3 = MAR21.51
- "Table 15 in paragraph 237" = MAR22.24
- "paragraph 211" = GIRR curvature risk weight = MAR21.99
- "paragraph 266" = RRAO calculation = MAR23.8

For section 9.6 (IMA), only the section and the Basel reference are cited.

**Formulas.** The flattened text drops radicals and fraction bars. Where a formula below shows √ or a fraction bar, it was restored from the identical Basel formula and that source is cited.

**Scope.** Chapter 9 eligibility reads: "These requirements apply only to internationally active institutions … All institutions designated by OSFI as … D-SIBs shall meet the requirements of this chapter."

CAR 9.1.2.2 [MAR11.7] reads: "an institution may choose between two broad methodologies: the standardized approach and internal models approach (IMA)". CAR Ch.1 s.1.3.2 [RBC20.9] lists only "The standardized approach, as described in section 9.5; or The internal models approach set out in section 9.6". **The Basel simplified standardised approach (MAR40) is not in CAR.** Section 7 of this document transcribes MAR40 from the Basel Framework for comparison only.

## 1. Structure and correlation scenarios

| Item | Text | Citation |
|---|---|---|
| RWA | "determined by multiplying the capital requirements … by 12.5" | 9.5.1.1 ¶108 [MAR20.1] |
| Structure | "simple sum of three components: … sensitivities-based method, the default risk capital (DRC) requirement and the residual risk add-on (RRAO)" | 9.5.1.2 ¶110 [MAR20.4] |
| Delta / vega WS | WS_k = RW_k · s_k | ¶116(3) [MAR21.4] |
| Within bucket | K_b = √max(0, Σ_k WS_k² + Σ_k Σ_{k≠l} ρ_kl WS_k WS_l) | ¶116(4) [MAR21.4] |
| Across buckets | Delta = √(Σ_b K_b² + Σ_b Σ_{c≠b} γ_bc S_b S_c), S_b = Σ_k WS_k | ¶116(5) [MAR21.4] |
| Alternative S_b | if the sum is negative: S_b = max[min(Σ_k WS_k, K_b), −K_b] | ¶116(5)(b) [MAR21.4] |
| CVR | CVR_k± = −Σ_i {V_i(x_k^{RW(curv)±}) − V_i(x_k) ∓ RW_k^{curv} · s_ik} | ¶117(2) [MAR21.5] |
| Curvature within bucket | K_b = max(K_b⁺, K_b⁻); K_b± = √max(0, Σ_k max(CVR_k±, 0)² + Σ_{l≠k} Σ_k ρ_kl CVR_k± CVR_l± ψ(CVR_k±, CVR_l±)); ψ = 0 if both negative, else 1; tie: upward if Σ CVR⁺ > Σ CVR⁻, else downward | ¶117(3) [MAR21.5] |
| Curvature across buckets | √max(0, Σ_b K_b² + Σ_{c≠b} Σ_b γ_bc S_b S_c ψ(S_b, S_c)), S_b = Σ CVR of the selected scenario | ¶117(4) [MAR21.5] |
| Medium scenario | ρ_kl, γ_bc as specified | ¶118(1) [MAR21.6] |
| High scenario | "uniformly multiplied by 1.25, … subject to a cap at 100%" | ¶118(2) [MAR21.6] |
| Low scenario | ρ_low = max(2 × ρ − 100%; 75% × ρ), same for γ | ¶118(3) [MAR21.6] |
| Aggregation | "For each of three correlation scenarios, the institution must simply sum up the separately calculated delta, vega and curvature capital requirements for all risk classes …"; "The sensitivities-based method capital requirement is the largest capital requirement from the three scenarios." | ¶119 [MAR21.7] |

The engine takes one binding scenario on the portfolio total (¶119(1)–(2)) and reports each risk class at that scenario. This matches MAR21.7.

## 2. Delta risk factors, buckets, risk weights, correlations

### 2.1 GIRR (¶120, ¶153–162)

Tenors (¶120(1)): 0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30 years. Sensitivities are assigned to tenors "by linear interpolation" (footnote 28).

**Table 1: Delta GIRR risk weights [MAR21.42]** (¶154)

| Tenor | 0.25 | 0.5 | 1 | 2 | 3 | 5 | 10 | 15 | 20 | 30 |
|---|---|---|---|---|---|---|---|---|---|---|
| RW | 1.7% | 1.7% | 1.6% | 1.3% | 1.2% | 1.1% | 1.1% | 1.1% | 1.1% | 1.1% |

- ¶155 [MAR21.43]: "The risk weight for the inflation risk factor and the cross-currency basis risk factors, respectively, is set at 1.6%."
- ¶156 [MAR21.44]: "For EUR, USD, GBP, AUD, JPY, SEK, CAD as well as the domestic reporting currency of an institution, the above risk weights may, at the discretion of the institution, be divided by the square root of 2."
- ¶157 [MAR21.45]: same bucket, same tenor, different curves: 99.90%.

**Table 2: ρ_kl, same bucket, different tenor, same curve [MAR21.46]** (¶158)

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

- Footnote 38: Table 2 = max[e^(−θ·|T_k − T_l| / min{T_k; T_l}); 40%], θ = 3%. The tests check every cell against this formula.
- ¶159 [MAR21.47]: different tenor and different curves: Table 2 value × 99.90%. Footnote 39 example: 88.69% · 0.999 = 88.60%. "The 99.90% correlation also applies to different inflation curves in the same currency."
- ¶160 [MAR21.48]: inflation curve vs a yield-curve tenor: 40%.
- ¶161 [MAR21.49]: cross-currency basis curve vs a yield-curve tenor, the inflation curve, or another cross-currency basis curve: 0%.
- ¶162 [MAR21.50]: γ_bc = 50% across GIRR buckets (currencies).

### 2.2 CSR non-securitisation (¶163–169)

**Table 3: Buckets [MAR21.51]** (¶163)

| Bucket | Credit quality | Sector |
|---|---|---|
| 1 / 9 | IG / HY & NR | Sovereigns including central banks, multilateral development institutions |
| 2 / 10 | IG / HY & NR | Local government, government-backed non-financials, education, public administration |
| 3 / 11 | IG / HY & NR | Financials including government-backed financials |
| 4 / 12 | IG / HY & NR | Basic materials, energy, industrials, agriculture, manufacturing, mining and quarrying |
| 5 / 13 | IG / HY & NR | Consumer goods and services, transportation and storage, administrative and support service activities |
| 6 / 14 | IG / HY & NR | Technology, telecommunications |
| 7 / 15 | IG / HY & NR | Health care, utilities, professional and technical activities |
| 8 | IG | Covered bonds (footnote 40: as defined in paragraphs 26–28 of OSFI Guideline B-2) |
| 16 | N/A | Other sector (footnote 41: credit quality not differentiating) |
| 17 | IG | Qualified Indices |
| 18 | HY | Qualified Indices |

OSFI-specific text in ¶163:

- "instruments issued by the following entities shall receive the same treatment as instruments issued by the Government of Canada: all provincial and territorial governments and agents of the federal, provincial or territorial government whose debts are, by virtue of their enabling legislation, obligations of the parent government."
- "Non-tranched MBS issued by government sponsored-entities (GSEs), such as Fannie and Freddie, are assigned to bucket 2 … with a risk weight of 1.0%." The LGD is 75% unless the security qualifies as a covered bond.
- Internal-rating mapping is allowed "subject to OSFI's approval".

¶164 [MAR21.52]: an issuer that cannot be assigned to a sector goes to bucket 16.

**Table 4: CSR non-securitisation risk weights [MAR21.53]** (¶165)

| Bucket | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RW | 0.5% | 1.0% | 5.0% | 3.0% | 3.0% | 2.0% | 1.5% | 2.5%* | 2.0% | 4.0% | 12.0% | 7.0% | 8.5% | 5.5% | 5.0% | 12.0% | 1.5% | 5.0% |

\*Footnote 42: "For covered bonds that are rated AA- or higher, the applicable risk weight may at the discretion of the institution be 1.5%."

Correlations:

- ¶166 [MAR21.54], buckets 1–15: ρ_kl = ρ(name) · ρ(tenor) · ρ(basis).
  - ρ(name) = 1 for the same name, else 35%.
  - ρ(tenor) = 1 for the same tenor, else 65%.
  - ρ(basis) = 1 for the same curve, else 99.90%.
  - Footnote 43 example: 35% · 65% · 99.90% = 22.73%.
- ¶167 [MAR21.55], buckets 17–18: ρ(name) = 80%; tenor and basis as above.
- ¶168 [MAR21.56], bucket 16: K_b = Σ_k |WS_k| (same for vega). For curvature: K_b = max(Σ_k max(CVR_k⁺, 0), Σ_k max(CVR_k⁻, 0)).
- ¶169 [MAR21.57]: γ_bc = γ(rating) · γ(sector).
  - γ(rating) = 50% when both buckets are in 1–15 and in different rating categories, else 1.
  - γ(sector) = 1 for the same sector, else Table 5.

**Table 5: γ_bc(sector) [MAR21.57]** (upper triangle as printed; blank diagonal)

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

### 2.3 CSR securitisation, CTP (¶170–173)

The CTP uses the Table 3 buckets and correlation structure without index buckets 17–18 (¶170 [MAR21.58]).

**Table 6: CTP risk weights [MAR21.59]** (¶171)

| Bucket | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RW | 4.0% | 4.0% | 8.0% | 5.0% | 4.0% | 3.0% | 2.0% | 6.0% | 13.0% | 13.0% | 16.0% | 10.0% | 12.0% | 12.0% | 12.0% | 13.0% |

- ¶172 [MAR21.60]: ρ(basis) = 99.00% for different curves; name and tenor as in ¶166–167.
- ¶173 [MAR21.61]: γ_bc as for non-securitisation.
- Footnote 35: an index CTP instrument goes to the sector bucket of at least 75% of its constituents; otherwise to bucket 16.

### 2.4 CSR securitisation, non-CTP (¶174–183)

**Table 7: Buckets [MAR21.62]** (¶174)

| Buckets | Credit quality | Sector order |
|---|---|---|
| 1–8 | Senior IG | RMBS Prime, RMBS Mid-prime, RMBS Sub-prime, CMBS, ABS Student loans, ABS Credit cards, ABS Auto, CLO non-CTP |
| 9–16 | Non-senior IG | same order |
| 17–24 | High yield & non-rated | same order |
| 25 | N/A | Other sector (footnote 44) |

**Table 8: Risk weights, buckets 1–8 [MAR21.64]** (¶176)

| Bucket | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| RW | 0.9% | 1.5% | 2.0% | 2.0% | 0.8% | 1.2% | 1.2% | 1.4% |

- ¶177 [MAR21.65]: buckets 9–16 = buckets 1–8 × 1.25 ("1.25 × 0.9% = 1.125%").
- ¶178 [MAR21.66]: buckets 17–24 = buckets 1–8 × 1.75 ("1.75 × 0.9% = 1.575%").
- ¶179 [MAR21.67]: bucket 25 = 3.5%.
- ¶180 [MAR21.68]: ρ = ρ(tranche) · ρ(tenor) · ρ(basis).
  - ρ(tranche) = 1 for the same tranche (more than 80% overlap in notional terms), else 40%.
  - ρ(tenor) = 1 for the same tenor, else 80%.
  - ρ(basis) = 1 for the same curve, else 99.90%.
- ¶181 [MAR21.69]: bucket 25 aggregated as Σ|WS_k|; curvature as in ¶168.
- ¶182 [MAR21.70]: γ_bc = 0% across buckets 1–24.
- ¶183 [MAR21.71]: bucket 25 and the aggregate of buckets 1–24 are "simply summed".

### 2.5 Equity (¶184–192)

**Table 9: Buckets [MAR21.72]** (¶184)

| Bucket | Market cap | Economy | Sector |
|---|---|---|---|
| 1 | Large | Emerging | Consumer goods and services, transportation and storage, administrative and support service activities, healthcare, utilities |
| 2 | Large | Emerging | Telecommunications, industrials |
| 3 | Large | Emerging | Basic materials, energy, agriculture, manufacturing, mining and quarrying |
| 4 | Large | Emerging | Financials including government-backed financials, real estate activities, technology |
| 5–8 | Large | Advanced | as 1–4 |
| 9 | Small | Emerging | All sectors under 1–4 |
| 10 | Small | Advanced | All sectors under 5–8 |
| 11 | N/A | N/A | Other sector (footnote 45) |
| 12 | Large | Advanced | Equity indices (non-sector specific) |
| 13 | N/A | N/A | Other equity indices (non-sector specific) |

- ¶186 [MAR21.74]: "Large market cap is defined as a market capitalization equal to or greater than **CAD 2.5 billion**." The Basel text says USD 2 billion.
- ¶187 [MAR21.75]: advanced economies are Canada, the United States, Mexico, the euro area, the non-euro western European countries (UK, Norway, Sweden, Denmark, Switzerland), Japan, Oceania (Australia, New Zealand), Singapore and Hong Kong SAR.
- ¶143(5) [MAR21.31]: no look-through for an equity index requires total constituent market cap "no less than **CAD $50 billion**". The Basel text says USD 40 billion. ¶143(2)–(4): at least 20 constituents; no single constituent above 25%; largest 10% of constituents below 60%.
- ¶145 [MAR21.33]: 75% rules for index bucket mapping.

**Table 10: Equity risk weights [MAR21.77]** (¶189)

| Bucket | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Spot | 55% | 60% | 45% | 55% | 30% | 35% | 40% | 50% | 70% | 50% | 70% | 15% | 25% |
| Repo | 0.55% | 0.60% | 0.45% | 0.55% | 0.30% | 0.35% | 0.40% | 0.50% | 0.70% | 0.50% | 0.70% | 0.15% | 0.25% |

¶190 [MAR21.78], within-bucket ρ:

- Spot vs repo of the same issuer: 99.90%.
- Spot vs spot:
  - 15% in buckets 1–4
  - 25% in buckets 5–8
  - 7.5% in bucket 9
  - 12.5% in bucket 10
  - 80% in buckets 12 and 13
- Repo vs repo: same values as spot vs spot.
- Spot vs repo of different issuers: the spot-vs-spot value × 99.90%.

Other rules:

- ¶191 [MAR21.79]: bucket 11 aggregated as Σ|WS|; curvature as in ¶168.
- ¶192 [MAR21.80]: γ_bc is
  - 15% when both buckets are in 1–10;
  - 0% when either bucket is 11;
  - 75% between buckets 12 and 13;
  - 45% otherwise.

### 2.6 Commodity (¶193–197)

Tenors (¶125): 0, 0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30 years.

**Tables 11 and 12 [MAR21.82–21.83]** (¶194–195)

| Bucket | Commodity bucket | RW | ρ(cty) |
|---|---|---|---|
| 1 | Energy: solid combustibles | 30% | 55% |
| 2 | Energy: liquid combustibles | 35% | 95% |
| 3 | Energy: electricity and carbon trading | 60% | 40% |
| 4 | Freight | 80% | 80% |
| 5 | Metals: non-precious | 40% | 60% |
| 6 | Gaseous combustibles | 45% | 65% |
| 7 | Precious metals (including gold) | 20% | 55% |
| 8 | Grains and oilseed | 35% | 45% |
| 9 | Livestock and dairy | 25% | 15% |
| 10 | Softs and other agriculturals | 35% | 40% |
| 11 | Other commodity | 50% | 15% |

- ¶195: ρ = ρ(cty) · ρ(tenor) · ρ(basis), with ρ(tenor) 99.00% and ρ(basis) 99.90% (delivery location). Footnote 46 example: 95% · 99.00% · 99.90% = 93.96%.
- ¶197 [MAR21.85]: γ_bc = 20% within buckets 1–10; 0% when either bucket is 11.

### 2.7 FX (¶198–201)

- ¶198 [MAR21.86]: one bucket per exchange rate against the reporting currency.
- ¶199 [MAR21.87]: RW = 15%.
- ¶200 [MAR21.88]: the RW may be divided by √2 for the specified pairs and their first-order crosses. The specified pairs are USD/EUR, USD/JPY, USD/GBP, USD/AUD, USD/CAD, USD/CHF, USD/MXN, USD/CNY, USD/NZD, USD/RUB, USD/HKD, USD/SGD, USD/TRY, USD/KRW, USD/SEK, USD/ZAR, USD/INR, USD/NOK and USD/BRL.
- ¶201 [MAR21.89]: γ_bc = 60%.

## 3. Vega (¶202–207)

Vega maturities are 0.5, 1, 3, 5 and 10 years. GIRR vega also uses the residual maturity of the underlying, on the same grid. ¶138 [MAR21.26]: an option without a maturity goes to the longest tenor.

**Table 13: Liquidity horizon and vega risk weights [MAR21.92]** (¶204)

| Risk class | LH | RW |
|---|---|---|
| GIRR | 60 | 100% |
| CSR non-securitisations | 120 | 100% |
| CSR securitisations (CTP) | 120 | 100% |
| CSR securitisations (non-CTP) | 120 | 100% |
| Equity (large cap and indices) | 20 | 77.78% |
| Equity (small cap and other sector) | 60 | 100% |
| Commodity | 120 | 100% |
| FX | 40 | 100% |

- Footnote 47: RW_k = min[RW_σ · √(LH/10); 100%], RW_σ = 55%.
- ¶205 [MAR21.93], GIRR:
  - ρ(option maturity) = e^(−α·|T_k − T_l| / min{T_k; T_l}), α = 1%.
  - ρ(underlying maturity) uses the same formula on the underlying maturities.
  - ρ_kl = min[ρ(option maturity) · ρ(underlying maturity); 1].
- ¶206 [MAR21.94], other risk classes: ρ_kl = min[ρ(DELTA) · ρ(option maturity); 1]. ρ(DELTA) uses only the dimensions shared by delta and vega factors: name for CSR and CTP, tranche for non-CTP securitisation, commodity for commodity.
- ¶207 [MAR21.95]: γ_bc as for delta.

## 4. Curvature (¶208–213)

- ¶209 [MAR21.97]: the delta buckets are reused.
- ¶210 [MAR21.98]: for FX and equity, the curvature RW is the delta RW (a relative shift). For FX options that do not reference the reporting or base currency, CVR⁺ and CVR⁻ "may be divided by a scalar of 1.5".
- ¶211 [MAR21.99]: for GIRR, CSR and commodity, the curvature RW is a parallel shift equal to the highest delta RW of the bucket (for GIRR, the 0.25-year weight).
- ¶212 [MAR21.100]: curvature ρ_kl = (delta ρ_kl)². For CSR, only ρ(name) applies.
- ¶213 [MAR21.101]: curvature γ_bc = (delta γ_bc)², for example GIRR 50%² = 25%.
- The high and low scenarios apply to the squared parameters.
- There is no curvature for inflation, cross-currency basis (¶120(3)(b)) or equity repo (¶124(3)(b)).

## 5. Default risk capital (¶214–258)

| Item | Text | Citation |
|---|---|---|
| Sovereign treatment (OSFI) | "Exposures to the Canadian sovereign, central bank and Canadian public sector entities (PSEs) subject to a 0% risk weight in CAR Chapter 4 should be assigned a default risk weight of 0%. Exposures to the United States sovereign, central bank and US PSEs assigned a 0% risk weight by US regulators should be assigned a default risk weight of 0%. Exposures to Multilateral Development Banks (MDBs) subject to a 0% risk weight in CAR Chapter 4 should be assigned a default risk weight of 0%. Exposures to other investment grade sovereigns which are assigned a 0% default risk weight by their national regulatory authority should be assigned a default risk weight of 0.5%, provided the institution has a local presence (subsidiary or branch) in the country of the sovereign exposure and has funded the exposure in the local currency." | ¶220 [MAR22.7] |
| Gross JTD | JTD(long) = max(LGD × notional + P&L, 0); JTD(short) = min(LGD × notional + P&L, 0); P&L = market value − notional | ¶224 [MAR22.11] |
| LGD | equity and non-senior debt 100%; senior debt 75%; covered bonds 25%; no LGD multiplication when the price is not linked to the recovery rate; non-tranched GSE MBS 75% unless covered-bond-qualifying | ¶225 [MAR22.12] |
| Maturity | JTD under one year scaled by a fraction of a year; floor of three months; cash equity at either more than one year or three months | ¶228–231 [MAR22.15–22.18] |
| TRS mismatch (OSFI) | IG bond, or large-cap equity (> CAD 6.25 bn, footnote 53), hedging a TRS, or a bond forward hedging a Level 1 HQLA: "the mismatch … is capped at 40 days" | ¶233 [MAR22.20] |
| Offsetting | a short may offset a long of the same obligor when the short has the same or lower seniority | ¶232 [MAR22.19] |
| Buckets | corporates; sovereigns; local governments and municipalities | ¶235 [MAR22.22] |
| HBR | HBR = Σ net JTD_long / (Σ net JTD_long + Σ \|net JTD_short\|) | ¶236 [MAR22.23] |
| DRC_b | DRC_b = max[(Σ_{i∈Long} RW_i · net JTD_i) − HBR · (Σ_{i∈Short} RW_i · \|net JTD_i\|); 0] | ¶238 [MAR22.25] |
| Total | "simple sum of the bucket level capital requirements" | ¶239 [MAR22.26] |

**Table 15: Default risk weights [MAR22.24]** (¶237)

| AAA | AA | A | BBB | BB | B | CCC | Unrated | Defaulted |
|---|---|---|---|---|---|---|---|---|
| 0.5% | 2% | 3% | 6% | 15% | 30% | 50% | 15% | 100% |

¶237 also reads: "all provincial and territorial governments and agents … shall receive the same treatment as instruments issued by the Government of Canada for the purposes of the DRC."

Securitisation, non-CTP:

- ¶240 [MAR22.27]: JTD = market value; no LGD.
- ¶242–243 [MAR22.29–22.30]: offsetting only within the same tranche of the same pool.
- ¶244 [MAR22.31]: buckets are corporates (all regions), or one of 11 asset classes (ABCP; auto loans/leases; RMBS; credit cards; CMBS; CLO; CDO-squared; SME; student loans; other retail; other wholesale) × 4 regions (Asia, Europe, North America, all other).
- ¶247 [MAR22.34]: RW "based on the corresponding risk weights for banking book instruments … defined in Chapter 6", with a one-year maturity, "can be capped at the fair value".

CTP:

- ¶253 [MAR22.40]: each index is its own bucket.
- ¶256 [MAR22.43]: non-tranched products use Table 15; tranches use the banking-book RW.
- ¶257 [MAR22.44]: DRC_b = (Σ RW · net JTD_long) − HBR_ctp · (Σ RW · |net JTD_short|), with no floor. HBR_ctp is computed over all CTP positions.
- ¶258 [MAR22.45]: DRC_CTP = max[Σ_b (max[DRC_b, 0] + 0.5 × min[DRC_b, 0]), 0]. The text's example: +100 and −100 give 50.

## 6. RRAO (¶259–266)

- ¶265 [MAR23.7], exclusions:
  - back-to-back transactions are excluded;
  - "Any instrument that is listed and/or eligible for central clearing must be excluded from the RRAO for other residual risks";
  - listed or CCP-eligible instruments "with an exotic underlying must be included".
- ¶266 [MAR23.8]: RRAO = Σ gross notional × RW. The RW is 1.0% for an exotic underlying (¶261) and 0.1% for other residual risks (¶262).

## 7. Internal models approach (9.6)

| Item | Value | Citation |
|---|---|---|
| ES confidence | 97.5th percentile, one-tailed | 9.6.4.1 [MAR33.3] |
| Table 19 | LH_j = 10, 20, 40, 60, 120 days; T = 10 | 9.6.4.1 [MAR33.4] |
| Liquidity-adjusted ES | ES = √(ES_T(P)² + Σ_{j≥2} (ES_T(P, j) · √((LH_j − LH_{j−1}) / T))²); radicals restored from Basel PDF p.670 | 9.6.4.1 [MAR33.4] |
| Stressed ES | ES = ES_R,S × ES_F,C / ES_R,C, ratio floored at 1; reduced set must explain ≥ 75% | [MAR33.5–33.6] |
| IMCC | IMCC = ρ · IMCC(C) + (1 − ρ) · Σ IMCC(C_i), ρ = 0.5 | 9.6.4.2 [MAR33.15] |
| SES | SES = √Σ ISES_i² + √Σ ISES_j² + √((ρ · Σ SES_k)² + (1 − ρ²) · Σ SES_k²), ρ = 0.6; radicals restored from Basel PDF p.678 | 9.6.4.3 [MAR33.17] |
| NMRF LH | max(Table 20 LH, 20 days) | [MAR33.16] |
| C_A | max{IMCC_{t−1} + SES_{t−1}; m_c · IMCC_avg + SES_avg} | 9.6.4.6 [MAR33.41] |
| m_c | fixed at 1.5, plus a backtesting add-on of 0 to 0.5 | [MAR33.42] |
| ACR_total | min{IMA_G,A + surcharge + C_U; SA_all desks} + max{0; IMA_G,A − SA_G,A} | [MAR33.43] |
| PLA surcharge | k = 0.5 × Σ_{i∈A} SA_i / Σ_{i∈G,A} SA_i; surcharge = k · max{0, SA_G,A − IMA_G,A} | [MAR33.45] |
| Desk backtest | SA fallback at more than 12 exceptions (99%) or more than 30 exceptions (97.5%) | 9.6.3.1 [MAR32.19] |

**Table 17: Backtesting zones [MAR32.9]**

| Exceptions | 0–4 | 5 | 6 | 7 | 8 | 9 | 10+ |
|---|---|---|---|---|---|---|---|
| Zone | Green | Amber | Amber | Amber | Amber | Amber | Red |
| Multiplier | 1.50 | 1.70 | 1.76 | 1.83 | 1.88 | 1.92 | 2.00 |

**Table 18: PLA test thresholds [MAR32.42]**

| Zone | Spearman | KS |
|---|---|---|
| Amber thresholds | 0.80 | 0.09 (p = 0.264) |
| Red thresholds | 0.70 | 0.12 (p = 0.055) |

Green requires Spearman > 0.80 **and** KS < 0.09. Red applies when Spearman < 0.70 **or** KS > 0.12.

**Table 20: Liquidity horizon n [MAR33.12]**

| Category | n |
|---|---|
| Interest rate: specified currencies (EUR, USD, GBP, AUD, JPY, SEK, CAD and domestic) | 10 |
| Interest rate: unspecified currencies | 20 |
| Interest rate: volatility | 60 |
| Interest rate: other types | 60 |
| Credit spread: sovereign (IG) | 20 |
| Credit spread: sovereign (HY) | 40 |
| Credit spread: corporate (IG) | 40 |
| Credit spread: corporate (HY) | 60 |
| Credit spread: volatility | 120 |
| Credit spread: other types | 120 |
| Equity price (large cap) | 10 |
| Equity price (small cap) | 20 |
| Equity price (large cap): volatility | 20 |
| Equity price (small cap): volatility | 60 |
| Equity: other types | 60 |
| FX rate: specified currency pairs (footnote 71) | 10 |
| FX rate: currency pairs | 20 |
| FX: volatility | 40 |
| FX: other types | 40 |
| Energy and carbon emissions trading price | 20 |
| Precious metals and non-ferrous metals price | 20 |
| Other commodities price | 60 |
| Energy and carbon emissions trading price: volatility | 60 |
| Precious metals and non-ferrous metals price: volatility | 60 |
| Other commodities price: volatility | 120 |
| Commodity: other types | 120 |

Equity repo and dividend: 20 days for large cap, 60 days otherwise. Mono-currency and cross-currency basis: 10 days for specified currencies, 20 days for unspecified.

## 8. Basel MAR40 simplified standardised approach (NOT in CAR; comparison only)

Source: Basel Framework MAR40, version effective 1 January 2023.

- MAR40.2 (formula rendered from PDF p.688): Capital = CR_IRR · SF_IRR + CR_EQ · SF_EQ + CR_FX · SF_FX + CR_COMM · SF_COMM, with SF_IRR = 1.30, SF_EQ = 3.50, **SF_COMM = 1.90**, **SF_FX = 1.20**.
- MAR40.6 Table 1, specific risk:
  - Government: AAA to AA− 0%; A+ to BBB− 0.25% (≤ 6 months), 1.00% (> 6 to 24 months), 1.60% (> 24 months); BB+ to B− 8%; below B− 12%; unrated 8%.
  - Qualifying: 0.25% / 1.00% / 1.60% by the same maturity bands.
  - Other: BB+ to BB− 8%; below BB− 12%; unrated 8%.
- MAR40.14: securitisation specific risk = banking-book RW / 12.5.
- MAR40.26 Table 4, maturity method (coupon ≥ 3% | coupon < 3% | RW):

  | Coupon ≥ 3% | Coupon < 3% | RW |
  |---|---|---|
  | ≤ 1 month | ≤ 1 month | 0.00% |
  | 1–3 months | 1–3 months | 0.20% |
  | 3–6 months | 3–6 months | 0.40% |
  | 6–12 months | 6–12 months | 0.70% |
  | 1–2 years | 1.0–1.9 years | 1.25% |
  | 2–3 years | 1.9–2.8 years | 1.75% |
  | 3–4 years | 2.8–3.6 years | 2.25% |
  | 4–5 years | 3.6–4.3 years | 2.75% |
  | 5–7 years | 4.3–5.7 years | 3.25% |
  | 7–10 years | 5.7–7.3 years | 3.75% |
  | 10–15 years | 7.3–9.3 years | 4.50% |
  | 15–20 years | 9.3–10.6 years | 5.25% |
  | > 20 years | 10.6–12 years | 6.00% |
  | | 12–20 years | 8.00% |
  | | > 20 years | 12.50% |

- MAR40.27: vertical disallowance of 10%.
- MAR40.28 Table 5, horizontal disallowances: within zone 1: 40%; within zones 2 and 3: 30%; between adjacent zones: 40%; between zones 1 and 3: 100%. Zone 1 is 0–1 year; zone 2 is 1–4 years (1–3.6 years for coupons below 3%); zone 3 is beyond that.
- MAR40.23(1): 100% charge on the overall net position.
- Equity:
  - MAR40.43: 8% specific risk plus 8% general market risk.
  - MAR40.47: 2% on a diversified index (Table 8: index specific risk 2%).
- FX: MAR40.60–61: 8% × (max(Σ net long, Σ |net short|) + |gold|). The Table 9 example gives 26.8.
- Commodities:
  - MAR40.72–73, simplified approach: 15% of the net position plus 3% of the gross position.
  - MAR40.69–70, maturity ladder: 1.5% spread rate, 0.6% carry, 15% on the residual.
- Options:
  - MAR40.76 Table 11, simplified approach. The text's example gives 60.
  - MAR40.80, delta-plus: gamma impact = ½ · Γ · VU², with VU = 8% (equity, FX) or 15% (commodity); vega at ±25%.

## 9. Engine conventions and items flagged `TODO: VERIFY`

1. **GIRR √2 on inflation and cross-currency basis.** ¶156's "the above risk weights" comes straight after ¶155 (1.6%). The engine applies √2 only to the Table 1 weights, which is the conservative reading.
2. **DRC securitisation conversion.** Banking-book RW × 8% (the RWA-to-capital conversion) is not printed in ¶247 or ¶255. A missing RW is set to 1,250%, which becomes 100% after the conversion.
3. **AAA vs AA in Table 15.** The shared `RatingBucket` merges AAA..AA−. The engine defaults to AA (2%); AAA (0.5%) needs `flags['rating_aaa']`.
4. **¶233 40-day TRS mismatch cap.** Not applied automatically: the contract has no hedge-pairing input.
5. **MAR40 (comparison only).** The order of the cross-zone offsets (1–2, then 2–3, then 1–3) and the commodity ladder carry convention are not settled by the text.
