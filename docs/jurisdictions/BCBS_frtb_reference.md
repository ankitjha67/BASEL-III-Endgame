# BCBS Basel Framework — Market Risk (FRTB) Reference

Verbatim transcription of every market-risk table and formula implemented in
`src/jurisdictions/bcbs/frtb/`. This is the audit trail for `Jurisdiction.BCBS` market risk, the
baseline the other regimes' FRTB packages are compared against.

**Source.** *The Basel Framework*, BIS consolidated standards, generated 29/10/2026 (1,429 pp.):
MAR20 (pp. 563–566), MAR21 (pp. 566–618), MAR22 (pp. 618–633), MAR23 (pp. 633–637),
MAR32 (pp. 655–668), MAR33 (pp. 668–686), MAR40 (pp. 686–720). Page numbers are the
"n / 1429" footers. Equations printed as images were read from the rendered PDF page
(`pdftoppm`); the page is cited. BCBS d424 does not contain the market-risk standard and was not
needed. Paragraph numbers are the Framework's (e.g. "21.42" under MAR21 = MAR21.42).

**Table numbering.** The Framework numbers MAR21 tables in its own sequence: Table 1 GIRR RW,
Table 2 GIRR correlations, Table 3 CSR buckets, Table 4 CSR RW, Table 5 CSR γ_sector, Table 6 CTP
RW, Table 7 sec non-CTP buckets, Table 8 sec non-CTP RW, Table 9 equity buckets, Table 10 equity
RW, Table 11 commodity buckets/RW, Table 12 commodity ρ_cty, Table 13 vega LH/RW.

Amounts are in the reporting currency (millions). `TODO: VERIFY` items are listed in § 11.

---

## 1. Structure (MAR20)

- **MAR20.1** — RWA = capital requirement (MAR20–MAR23) × 12.5.
- **MAR20.4** — SA capital = SBM + DRC + RRAO (simple sum).
- **MAR20.5** — CTP: securitisation positions that are not re-securitisations, all reference
  entities single-name with a liquid two-way market, no retail / residential / commercial mortgage
  underlying, no SPE claims; plus non-securitisation hedges of such positions.

## 2. SBM aggregation formulas (MAR21.4–21.7)

Read from the rendered pp. 570–574.

- **MAR21.4(3)** WS_k = RW_k · s_k
- **MAR21.4(4)** K_b = √( max(0, Σ_k WS_k² + Σ_k Σ_{l≠k} ρ_kl WS_k WS_l) )
- **MAR21.4(5)(a)** S_b = Σ_k WS_k (bucket b), S_c = Σ_k WS_k (bucket c)
- **MAR21.4(5)(b)** if Σ_b K_b² + Σ_b Σ_{c≠b} γ_bc S_b S_c < 0:
  S_b = max[min(Σ_k WS_k, K_b), −K_b], S_c = max[min(Σ_k WS_k, K_c), −K_c]
- Delta (resp. vega) = √( Σ_b K_b² + Σ_b Σ_{c≠b} γ_bc S_b S_c )
- **MAR21.5(2)** CVR_k⁺ = −Σ_i { V_i(x_k^{RW(curv)+}) − V_i(x_k) − RW_k^{curv} · s_ik },
  CVR_k⁻ = −Σ_i { V_i(x_k^{RW(curv)−}) − V_i(x_k) + RW_k^{curv} · s_ik }
  (s_ik: delta of i; for GIRR, CSR, commodity the sum of deltas to all tenors of the curve).
- **MAR21.5(3)** K_b = max(K_b⁺, K_b⁻) with
  K_b^± = √( max(0, Σ_k max(CVR_k^±, 0)² + Σ_{l≠k} Σ_k ρ_kl CVR_k^± CVR_l^± ψ(CVR_k^±, CVR_l^±)) ).
  K_b = K_b⁺ → "upward scenario selected"; K_b = K_b⁻ → "downward"; if K_b⁺ = K_b⁻, upward if
  Σ CVR⁺ > Σ CVR⁻, otherwise downward. Selection may differ across the three correlation
  scenarios. ψ(x, y) = 0 if both negative, 1 otherwise.
- **MAR21.5(4)** S_b = Σ_k CVR_k⁺ if upward selected, Σ_k CVR_k⁻ otherwise;
  Curvature = √( max(0, Σ_b K_b² + Σ_{c≠b} Σ_b γ_bc S_b S_c ψ(S_b, S_c)) ).
  (No alternative S_b specification for curvature.)
- **MAR21.6** medium = prescribed ρ, γ; high = ×1.25 capped at 100%;
  low: ρ^low = max(2·ρ − 100%; 75%·ρ), γ^low = max(2·γ − 100%; 75%·γ) (p. 574).
- **MAR21.7** for each scenario sum delta, vega, curvature over all risk classes; SBM = largest
  of the three scenario totals (per desk when computing desk-level SA).

## 3. GIRR (MAR21.8, 21.41–21.50)

- Tenors (MAR21.8(1)): 0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30 years. Inflation and cross-currency
  basis: flat curves (MAR21.8(2)–(3)). Vega (MAR21.8(4)): option maturity and underlying residual
  maturity on 0.5, 1, 3, 5, 10 years. Curvature (MAR21.8(5)): one factor per currency, all curves
  shifted together; no curvature for inflation or cross-currency basis.
- **MAR21.41** each currency is a bucket.

**Table 1 (MAR21.42)** — delta GIRR risk weights

| Tenor | 0.25y | 0.5y | 1y | 2y | 3y | 5y | 10y | 15y | 20y | 30y |
|---|---|---|---|---|---|---|---|---|---|---|
| RW | 1.7% | 1.7% | 1.6% | 1.3% | 1.2% | 1.1% | 1.1% | 1.1% | 1.1% | 1.1% |

- **MAR21.43** inflation and cross-currency basis RW 1.6%.
- **MAR21.44** for specified currencies the above risk weights may, at the bank's discretion, be
  divided by √2. Footnote 283: EUR, USD, GBP, AUD, JPY, SEK, CAD and the domestic reporting
  currency.
- **MAR21.45** same bucket, same tenor, different curves: 99.90%. Onshore/offshore xccy basis may
  be aggregated by simple sum (bank choice).

**Table 2 (MAR21.46)** — ρ_kl, same bucket, different tenor, same curve

| | 0.25y | 0.5y | 1y | 2y | 3y | 5y | 10y | 15y | 20y | 30y |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.25y | 100.0% | 97.0% | 91.4% | 81.1% | 71.9% | 56.6% | 40.0% | 40.0% | 40.0% | 40.0% |
| 0.5y | 97.0% | 100.0% | 97.0% | 91.4% | 86.1% | 76.3% | 56.6% | 41.9% | 40.0% | 40.0% |
| 1y | 91.4% | 97.0% | 100.0% | 97.0% | 94.2% | 88.7% | 76.3% | 65.7% | 56.6% | 41.9% |
| 2y | 81.1% | 91.4% | 97.0% | 100.0% | 98.5% | 95.6% | 88.7% | 82.3% | 76.3% | 65.7% |
| 3y | 71.9% | 86.1% | 94.2% | 98.5% | 100.0% | 98.0% | 93.2% | 88.7% | 84.4% | 76.3% |
| 5y | 56.6% | 76.3% | 88.7% | 95.6% | 98.0% | 100.0% | 97.0% | 94.2% | 91.4% | 86.1% |
| 10y | 40.0% | 56.6% | 76.3% | 88.7% | 93.2% | 97.0% | 100.0% | 98.5% | 97.0% | 94.2% |
| 15y | 40.0% | 41.9% | 65.7% | 82.3% | 88.7% | 94.2% | 98.5% | 100.0% | 99.0% | 97.0% |
| 20y | 40.0% | 40.0% | 56.6% | 76.3% | 84.4% | 91.4% | 97.0% | 99.0% | 100.0% | 98.5% |
| 30y | 40.0% | 40.0% | 41.9% | 65.7% | 76.3% | 86.1% | 94.2% | 97.0% | 98.5% | 100.0% |

Footnote 284: the table is generated by a formula with θ = 3% (the formula is an image lost in
extraction and in the PDF render; the printed table is implemented).

- **MAR21.47** different tenor and different curve: Table 2 × 99.90% (FAQ: 99.90% between
  different inflation curves of a currency).
- **MAR21.48** inflation vs a yield-curve tenor: 40%.
- **MAR21.49** cross-currency basis vs yield curve, inflation, or another xccy curve: 0%.
- **MAR21.50** γ across currencies: 50%.

## 4. CSR non-securitisation (MAR21.9, 21.51–21.57)

Tenors 0.5, 1, 3, 5, 10 years (bond and CDS curves distinct; one curvature factor per issuer).

**Table 3 (MAR21.51)** — buckets

| Bucket | Credit quality | Sector |
|---|---|---|
| 1 | IG | Sovereigns including central banks, multilateral development banks |
| 2 | IG | Local government, government-backed non-financials, education, public administration |
| 3 | IG | Financials including government-backed financials |
| 4 | IG | Basic materials, energy, industrials, agriculture, manufacturing, mining and quarrying |
| 5 | IG | Consumer goods and services, transportation and storage, administrative and support service activities |
| 6 | IG | Technology, telecommunications |
| 7 | IG | Health care, utilities, professional and technical activities |
| 8 | IG | Covered bonds (LEX30.37, 30.39, 30.40) |
| 9–15 | HY & NR | Sectors of buckets 1–7 |
| 16 | Other sector (credit quality not differentiating) | |
| 17 | IG indices | |
| 18 | HY indices | |

**Table 4 (MAR21.53)** — RW (all tenors)

| Bucket | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RW | 0.5% | 1.0% | 5.0% | 3.0% | 3.0% | 2.0% | 1.5% | 2.5% | 2.0% | 4.0% | 12.0% | 7.0% | 8.5% | 5.5% | 5.0% | 12.0% | 1.5% | 5.0% |

Footnote 288: covered bonds rated AA- or higher may, at the bank's discretion, use 1.5%.

- **MAR21.54** buckets 1–15: ρ = ρ^(name) · ρ^(tenor) · ρ^(basis); ρ^(name) = 1 same name, else 35%;
  ρ^(tenor) = 1 same tenor, else 65%; ρ^(basis) = 1 same curve, else 99.90%.
- **MAR21.55** buckets 17–18: 80% / 65% / 99.90%.
- **MAR21.56** other-sector bucket 16: K_b = Σ_k |WS_k| (delta and vega);
  curvature K_b = max(Σ_k max(CVR_k⁺, 0), Σ_k max(CVR_k⁻, 0)) (p. 599).
- **MAR21.57** γ_bc = γ^(rating) · γ^(sector); γ^(rating) = 50% when both buckets are in 1–15 with
  different rating category, else 1; γ^(sector) = 1 for the same sector, else Table 5.

**Table 5 (MAR21.57)** — γ^(sector), different sectors

| Bucket | 1/9 | 2/10 | 3/11 | 4/12 | 5/13 | 6/14 | 7/15 | 8 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1/9 | | 75% | 10% | 20% | 25% | 20% | 15% | 10% | 0% | 45% | 45% |
| 2/10 | | | 5% | 15% | 20% | 15% | 10% | 10% | 0% | 45% | 45% |
| 3/11 | | | | 5% | 15% | 20% | 5% | 20% | 0% | 45% | 45% |
| 4/12 | | | | | 20% | 25% | 5% | 5% | 0% | 45% | 45% |
| 5/13 | | | | | | 25% | 5% | 15% | 0% | 45% | 45% |
| 6/14 | | | | | | | 5% | 20% | 0% | 45% | 45% |
| 7/15 | | | | | | | | 5% | 0% | 45% | 45% |
| 8 | | | | | | | | | 0% | 45% | 45% |
| 16 | | | | | | | | | | 0% | 0% |
| 17 | | | | | | | | | | | 75% |

## 5. CSR securitisation — CTP (MAR21.11, 21.58–21.61)

- **MAR21.58** same bucket and correlation structure as non-sec, without buckets 17–18 (FAQ: an
  index CTP goes to the sector bucket of ≥ 75% of its constituents, else bucket 16).

**Table 6 (MAR21.59)**

| Bucket | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RW | 4.0% | 4.0% | 8.0% | 5.0% | 4.0% | 3.0% | 2.0% | 6.0% | 13.0% | 13.0% | 16.0% | 10.0% | 12.0% | 12.0% | 12.0% | 13.0% |

- **MAR21.60** ρ^(basis) = 99.00% for different curves; ρ^(name), ρ^(tenor) as MAR21.54–21.55.
- **MAR21.61** γ as MAR21.57.

## 6. CSR securitisation — non-CTP (MAR21.10, 21.62–21.71)

**Table 7 (MAR21.62)** — buckets

| Bucket | Credit quality | Sector |
|---|---|---|
| 1 / 9 / 17 | Senior IG / Non-senior IG / HY & NR | RMBS – Prime |
| 2 / 10 / 18 | ″ | RMBS – Mid-prime |
| 3 / 11 / 19 | ″ | RMBS – Sub-prime |
| 4 / 12 / 20 | ″ | CMBS |
| 5 / 13 / 21 | ″ | ABS – Student loans |
| 6 / 14 / 22 | ″ | ABS – Credit cards |
| 7 / 15 / 23 | ″ | ABS – Auto |
| 8 / 16 / 24 | ″ | CLO non-CTP |
| 25 | Other sector | |

**Table 8 (MAR21.64)** — buckets 1–8

| Bucket | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| RW | 0.9% | 1.5% | 2.0% | 2.0% | 0.8% | 1.2% | 1.2% | 1.4% |

- **MAR21.65** buckets 9–16 = buckets 1–8 × 1.25 (bucket 9 = 1.25 × 0.9% = 1.125%).
- **MAR21.66** buckets 17–24 = buckets 1–8 × 1.75 (bucket 17 = 1.75 × 0.9% = 1.575%).
- **MAR21.67** bucket 25 = 3.5%.
- **MAR21.68** ρ = ρ^(tranche) · ρ^(tenor) · ρ^(basis): 1 same tranche (> 80% notional overlap)
  else 40%; 1 same tenor else 80%; 1 same curve else 99.90% (FAQ: no issuer factor).
- **MAR21.69** bucket 25: Σ|WS| (delta, vega); curvature max(Σ max(CVR⁺,0), Σ max(CVR⁻,0)).
- **MAR21.70** γ = 0% across buckets 1–24.
- **MAR21.71** bucket 25 capital and the aggregated buckets 1–24 capital are simply summed.

## 7. Equity (MAR21.12, 21.72–21.80)

**Table 9 (MAR21.72)** — buckets

| Bucket | Market cap | Economy | Sector |
|---|---|---|---|
| 1 | Large | EME | Consumer goods and services, transportation and storage, administrative and support service activities, healthcare, utilities |
| 2 | Large | EME | Telecommunications, industrials |
| 3 | Large | EME | Basic materials, energy, agriculture, manufacturing, mining and quarrying |
| 4 | Large | EME | Financials including government-backed financials, real estate activities, technology |
| 5–8 | Large | Advanced | As 1–4 |
| 9 | Small | EME | All sectors of buckets 1–4 |
| 10 | Small | Advanced | All sectors of buckets 5–8 |
| 11 | Other sector | | |
| 12 | Large market cap, advanced economy equity indices (non-sector specific) | | |
| 13 | Other equity indices (non-sector specific) | | |

- **MAR21.74** large cap ≥ USD 2 billion. **MAR21.75** advanced economies: Canada, US, Mexico,
  euro area, UK, Norway, Sweden, Denmark, Switzerland, Japan, Australia, New Zealand, Singapore,
  Hong Kong SAR. **MAR21.76(2)** unassignable issuers → bucket 11. **MAR21.33(2)(a)** index → 12 if
  ≥ 75% large cap and advanced economy, else 13.

**Table 10 (MAR21.77)**

| Bucket | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Spot RW | 55% | 60% | 45% | 55% | 30% | 35% | 40% | 50% | 70% | 50% | 70% | 15% | 25% |
| Repo RW | 0.55% | 0.60% | 0.45% | 0.55% | 0.30% | 0.35% | 0.40% | 0.50% | 0.70% | 0.50% | 0.70% | 0.15% | 0.25% |

- **MAR21.78** (1) spot vs repo, same issuer: 99.90%; (2) spot–spot: 15% (buckets 1–4), 25% (5–8),
  7.5% (9), 12.5% (10), 80% (12, 13); (3) repo–repo: same as (2); (4) spot vs repo, different
  issuers: (2) × 99.90%.
- **MAR21.79** bucket 11: Σ|WS| (delta, vega); curvature max(Σ max(CVR⁺,0), Σ max(CVR⁻,0)).
- **MAR21.80** γ: 15% within 1–10; 0% if either is 11; 75% between 12 and 13; 45% otherwise.

## 8. Commodity (MAR21.13, 21.81–21.85)

Tenors 0, 0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30 years; dimension also delivery location.

**Tables 11 (MAR21.82) and 12 (MAR21.83)**

| Bucket | Commodity bucket | RW | ρ^(cty) |
|---|---|---|---|
| 1 | Energy – solid combustibles | 30% | 55% |
| 2 | Energy – liquid combustibles | 35% | 95% |
| 3 | Energy – electricity and carbon trading | 60% | 40% |
| 4 | Freight | 80% | 80% |
| 5 | Metals – non-precious | 40% | 60% |
| 6 | Gaseous combustibles | 45% | 65% |
| 7 | Precious metals (including gold) | 20% | 55% |
| 8 | Grains and oilseed | 35% | 45% |
| 9 | Livestock and dairy | 25% | 15% |
| 10 | Softs and other agriculturals | 35% | 40% |
| 11 | Other commodity | 50% | 15% |

- **MAR21.83** ρ = ρ^(cty) · ρ^(tenor) · ρ^(basis); ρ^(cty) = 1 identical commodity else Table 12;
  ρ^(tenor) = 1 same tenor else 99.00%; ρ^(basis) = 1 same delivery location else 99.90%.
- **MAR21.85** γ: 20% within buckets 1–10; 0% if either is 11.

## 9. FX (MAR21.14, 21.86–21.89)

- **MAR21.86** one bucket per currency vs the reporting currency.
- **MAR21.87** RW 15%.
- **MAR21.88** may be divided by √2 for specified pairs and first-order crosses. Footnote 293:
  USD/EUR, USD/JPY, USD/GBP, USD/AUD, USD/CAD, USD/CHF, USD/MXN, USD/CNY, USD/NZD, USD/RUB,
  USD/HKD, USD/SGD, USD/TRY, USD/KRW, USD/SEK, USD/ZAR, USD/INR, USD/NOK, USD/BRL. Footnote 294:
  e.g. EUR/AUD is a first-order cross.
- **MAR21.89** γ = 60%.

## 10. Vega and curvature (MAR21.90–21.101)

**Table 13 (MAR21.92)**

| Risk class | LH (days) | Risk weight |
|---|---|---|
| GIRR | 60 | 100% |
| CSR non-securitisations | 120 | 100% |
| CSR securitisations (CTP) | 120 | 100% |
| CSR securitisations (non-CTP) | 120 | 100% |
| Equity (large cap and indices) | 20 | 77.78% |
| Equity (small cap and other sector) | 60 | 100% |
| Commodity | 120 | 100% |
| FX | 40 | 100% |

Footnote 295: RW_k determined from RW_σ = 55% and LH (formula image lost; consistent with
min(55% · √(LH/10), 100%)). FAQ: 20-day LH for buckets 1–8, 12, 13; 60-day for 9–11.

- **MAR21.93** (p. 615) GIRR vega: ρ = min[ρ^(option maturity) · ρ^(underlying maturity); 1],
  ρ^(option maturity) = e^(−α·|T_k − T_l| / min(T_k, T_l)), ρ^(underlying maturity) =
  e^(−α·|T_k^U − T_l^U| / min(T_k^U, T_l^U)), α = 1%.
- **MAR21.94** other classes: ρ = min[ρ^(DELTA) · ρ^(option maturity); 1]; FAQ: CSR uses name only,
  sec non-CTP tranche only, commodity commodity only.
- **MAR21.95** γ as for delta.
- **MAR21.98** FX and equity curvature RW = delta RW (relative shift); FX options not referencing
  the reporting currency: CVR may be divided by 1.5.
- **MAR21.99** GIRR, CSR, commodity: parallel shift by the highest delta RW of the bucket (GIRR:
  the 0.25-year RW). FAQ1: commodity shocks are relative (gold 20% → ×1.2 / ×0.8). FAQ2: CSR
  curvature factor may be floored at zero for the downward shock.
- **MAR21.100** curvature ρ = (delta ρ)²; for CSR (non-sec, CTP) only ρ^(name) applies (squared);
  scenarios applied to the squared parameter.
- **MAR21.101** curvature γ = (delta γ)² (e.g. GIRR 50%² = 25%).

## 11. Default risk capital (MAR22)

- **MAR22.4** no diversification between non-sec, sec non-CTP and CTP.
- **MAR22.7** sovereign / PSE / MDB zero default RW at national discretion.
- **MAR22.11** (p. 622) JTD(long) = max(LGD × notional + P&L, 0); JTD(short) = min(LGD × notional
  + P&L, 0); P&L = market value − notional.
- **MAR22.12** LGD: equity and non-senior debt 100%; senior debt 75%; covered bonds 25%; no LGD
  multiplication where price is not linked to recovery.
- **MAR22.13** long notional positive, short negative; P&L loss negative, gain positive; JTD = 0 if
  the contract can be unwound with no default exposure.

**Table 1 (MAR22.14)** — JTD components, long credit position

| Instrument | Notional | Bond-equivalent market value | P&L |
|---|---|---|---|
| Bond | Face value of bond | Market value of bond | Market value − face value |
| CDS | Notional of CDS | Notional of CDS + MtM value of CDS | − MtM value of CDS |
| Sold put option on a bond | Notional of option | Strike amount − \|MtM value of option\| | (Strike − \|MtM value of option\|) − Notional |
| Bought call option on a bond | 0 | MtM value of option | MtM value of option |

- **MAR22.15** JTD of exposures < 1 year and their hedges scaled by fraction of a year (gross JTD,
  footnote 296). **MAR22.16** cash equities: 3 months or > 1 year. **MAR22.17** derivative maturity
  governs. **MAR22.18** weighting floored at 1/4 (3 months).
- **MAR22.19** offset long/short of the same obligor where the short has the same or lower
  seniority; > 1 year fully offset; < 1 year weighted by maturity / 1 year.
- **MAR22.22** buckets: corporates; sovereigns; local governments and municipalities.
- **MAR22.23** (p. 627) HBR = Σ net JTD_long / (Σ net JTD_long + Σ |net JTD_short|).

**Table 2 (MAR22.24)** — default risk weights

| AAA | AA | A | BBB | BB | B | CCC | Unrated | Defaulted |
|---|---|---|---|---|---|---|---|---|
| 0.5% | 2% | 3% | 6% | 15% | 30% | 50% | 15% | 100% |

- **MAR22.25** (p. 628) DRC_b = max[(Σ_{i∈Long} RW_i · net JTD_i) − HBR · (Σ_{i∈Short} RW_i ·
  |net JTD_i|); 0]. **MAR22.26** simple sum across buckets.
- **MAR22.27** sec JTD = market value (no LGD). **MAR22.29–22.30** offsetting only within the same
  tranche of the same pool (identical except maturity); MAR22.15–22.18 scaling applies.
- **MAR22.31** buckets: corporates (excl. SME, all regions); else 11 asset classes (ABCP; auto
  loans/leases; RMBS; credit cards; CMBS; CLO; CDO-squared; SME; student loans; other retail; other
  wholesale) × 4 regions (Asia, Europe, North America, all other). **MAR22.32(2)** unassignable →
  "other bucket".
- **MAR22.33** HBR and MAR22.25 formula within bucket. **MAR22.34** RW based on banking-book RW
  (CRE40–CRE44) with one-year maturity; cash position capital may be capped at fair value.
  **MAR22.35** simple sum.
- **MAR22.36–22.37** CTP JTD = market value (tranches and non-tranched hedges). **MAR22.38**
  nth-to-default: attachment (N−1)/names, detachment N/names. **MAR22.39** offsetting across
  maturities for the same index family, series and tranche; no netting across tranches, series or
  families.
- **MAR22.40–22.41** each index is a bucket; bespokes go to their index bucket. **MAR22.43**
  non-tranched → Table 2; tranched → banking-book treatment (MAR22.42).
- **MAR22.44** (p. 633) DRC_b = (Σ_Long RW_i · net JTD_i) − HBR_ctp · (Σ_Short RW_i · |net JTD_i|),
  HBR_ctp over all CTP positions, no floor at bucket level.
- **MAR22.45** DRC_CTP = max[Σ_b (max[DRC_b, 0] + 0.5 × min[DRC_b, 0]), 0]; example +100 and −100
  → 100 − 0.5 × 100 = 50.

## 12. Residual risk add-on (MAR23)

- **MAR23.3** exotic underlying: not in scope of any SBM risk class or DRC (e.g. longevity,
  weather, natural disasters, future realised volatility).
- **MAR23.4** other residual risks: vega/curvature instruments not replicable as a finite linear
  combination of vanilla options on a single underlying; CTP instruments except eligible hedges.
- **MAR23.6** not by itself in scope: cheapest-to-deliver, smile, multi-underlying vanilla
  correlation, dividend risk of non-dividend derivatives, MAR21.31–21.32 index instruments.
- **MAR23.7** back-to-back transactions excluded; listed and/or CCP-eligible excluded from other
  residual risk; listed/CCP-eligible with exotic underlying included.
- **MAR23.8(2)** RRAO = Σ gross notional × RW; exotic 1.0%; other residual 0.1%.

## 13. Internal models approach (MAR32–MAR33)

**MAR32.9 Table 1** — backtesting zones (250 observations)

| Zone | Exceptions | Multiplier |
|---|---|---|
| Green | 0–4 | 1.50 |
| Amber | 5 / 6 / 7 / 8 / 9 | 1.70 / 1.76 / 1.83 / 1.88 / 1.92 |
| Red | 10 or more | 2.00 |

- **MAR32.19** desk to SA with > 12 exceptions at 99% or 30 at 97.5%.

**MAR32.42 Table 2** — PLA thresholds: green if Spearman > 0.80 and KS < 0.09 (p = 0.264);
red if Spearman < 0.70 or KS > 0.12 (p = 0.055); amber otherwise.

- **MAR33.3** ES at the 97.5th percentile, one-tailed. **MAR33.4** base horizon T = 10 days;
  Table 1 LH_j = 10, 20, 40, 60, 120 (the scaling equation is an image not legible in either the
  extraction or the render — see TODO). **MAR33.5(2)(b)** reduced set ≥ 75% of full ES.
  **MAR33.6** ES = ES_R,S × (ES_F,C / ES_R,C), ratio floored at 1.

**MAR33.12 Table 2** — liquidity horizon n (days), read from the rendered p. 674

| Risk factor category | n | Risk factor category | n |
|---|---|---|---|
| IR: specified currencies (EUR, USD, GBP, AUD, JPY, SEK, CAD, domestic) | 10 | Equity price (small cap): volatility | 60 |
| IR: unspecified currencies | 20 | Equity: other types | 60 |
| IR: volatility | 60 | FX rate: specified currency pairs | 10 |
| IR: other types | 60 | FX rate: currency pairs | 20 |
| Credit spread: sovereign (IG) | 20 | FX: volatility | 40 |
| Credit spread: sovereign (HY) | 40 | FX: other types | 40 |
| Credit spread: corporate (IG) | 40 | Energy and carbon emissions trading price | 20 |
| Credit spread: corporate (HY) | 60 | Precious metals and non-ferrous metals price | 20 |
| Credit spread: volatility | 120 | Other commodities price | 60 |
| Credit spread: other types | 120 | Energy and carbon emissions trading price: volatility | 60 |
| | | Precious metals and non-ferrous metals price: volatility | 60 |
| Equity price (large cap) | 10 | Other commodities price: volatility | 120 |
| Equity price (small cap) | 20 | Commodity: other types | 120 |
| Equity price (large cap): volatility | 20 | | |

Footnote 309: the MAR21.88 pairs plus EUR/JPY, EUR/GBP, EUR/CHF, JPY/AUD and first-order crosses.

- **MAR33.15** (p. 676) IMCC = ρ · IMCC(C) + (1 − ρ) · Σ_{i=1}^{B} IMCC(C_i), ρ = 0.5;
  IMCC(C) = ES_R,S · ES_F,C / ES_R,C; IMCC(C_i) = ES_R,S,i · ES_F,C,i / ES_R,C,i.
- **MAR33.16** NMRF LH = max(MAR33.12 LH, 20 days).
- **MAR33.17** (p. 678) SES = √(Σ_i ISES_NM,i²) + √(Σ_j ISES_NM,j²) +
  √((ρ · Σ_k SES_NM,k)² + (1 − ρ²) · Σ_k SES_NM,k²), ρ = 0.6.
- **MAR33.41** (p. 685) C_A = max{IMCC_{t−1} + SES_{t−1}; m_c · IMCC_avg + SES_avg}.
- **MAR33.42** m_c = 1.5 plus a backtesting plus (0 to 0.5) and qualitative add-ons.
- **MAR33.43** ACR_total = min{IMA_G,A + Capital surcharge + C_U; SA_all desks} +
  max{0; IMA_G,A − SA_G,A}, IMA_G,A = C_A + DRC.
- **MAR33.45** (p. 686) k = 0.5 × Σ_{i∈A} SA_i / Σ_{i∈G,A} SA_i; surcharge = k · max{0, SA_G,A −
  IMA_G,A}. **MAR33.46** RWA = 12.5 × capital.

## 14. Simplified standardised approach (MAR40)

- **MAR40.1** RWA = 12.5 × capital. **MAR40.2** (p. 688) capital = CR_IRR × SF_IRR + CR_EQ × SF_EQ +
  CR_FX × SF_FX + CR_COMM × SF_Comm; SF_IRR = 1.30, SF_EQ = 3.50, SF_COMM = 1.90, SF_FX = 1.20.

**MAR40.6 Table 1** — specific risk

| Category | External assessment | Charge |
|---|---|---|
| Government | AAA to AA– | 0% |
| Government | A+ to BBB– | 0.25% (≤ 6 months), 1.00% (> 6 and ≤ 24 months), 1.60% (> 24 months) |
| Government | BB+ to B– | 8.00% |
| Government | Below B– | 12.00% |
| Government | Unrated | 8.00% |
| Qualifying | | 0.25% / 1.00% / 1.60% by the same maturity bands |
| Other | BB+ to BB– | 8.00% |
| Other | Below BB– | 12.00% |
| Other | Unrated | 8.00% |

**MAR40.26 Table 4** — maturity method

| Coupon ≥ 3% | Coupon < 3% | RW | Assumed yield change |
|---|---|---|---|
| ≤ 1 month | ≤ 1 month | 0.00% | 1.00 |
| 1–3 months | 1–3 months | 0.20% | 1.00 |
| 3–6 months | 3–6 months | 0.40% | 1.00 |
| 6–12 months | 6–12 months | 0.70% | 1.00 |
| 1–2 years | 1.0–1.9 years | 1.25% | 0.90 |
| 2–3 years | 1.9–2.8 years | 1.75% | 0.80 |
| 3–4 years | 2.8–3.6 years | 2.25% | 0.75 |
| 4–5 years | 3.6–4.3 years | 2.75% | 0.75 |
| 5–7 years | 4.3–5.7 years | 3.25% | 0.70 |
| 7–10 years | 5.7–7.3 years | 3.75% | 0.65 |
| 10–15 years | 7.3–9.3 years | 4.50% | 0.60 |
| 15–20 years | 9.3–10.6 years | 5.25% | 0.60 |
| Over 20 years | 10.6–12 years | 6.00% | 0.60 |
| | 12–20 years | 8.00% | 0.60 |
| | Over 20 years | 12.50% | 0.60 |

- **MAR40.27** vertical disallowance 10% of the smaller offsetting side per band.
- **MAR40.28 Table 5** (p. 701) horizontal disallowances: within zone 1 (0–1 year) 40%, zone 2
  (1–4 years; 1–3.6 for low coupon) 30%, zone 3 (> 4 years) 30%; between adjacent zones 40%;
  between zones 1 and 3 100%.
- **MAR40.29** duration method: 5% vertical disallowance (not implemented).
- **MAR40.42–40.43** equity: specific risk 8% of gross, general 8% of net per national market;
  **MAR40.47** + 2% on net diversified index contracts; **MAR40.50** 4% (2% each side) for qualifying
  arbitrage.
- **MAR40.60–40.61** FX: 8% × (max(Σ net long, Σ |net short|) + |net gold|). Table 9 example:
  (+300, −200, gold 35) → 335 × 8% = 26.8.
- **MAR40.69–40.70 Table 10** commodity ladder bands 0–1m, 1–3m, 3–6m, 6–12m, 1–2y, 2–3y,
  > 3y; spread rate 1.5% on the sum of matched long and short; 0.6% per band carried forward; 15%
  on the final net position. **MAR40.72–40.73** simplified: 15% of net + 3% of gross.
- **MAR40.76 Table 11** options simplified approach: long cash + long put / short cash + long call:
  underlying MV × (specific + general charge) − in-the-money amount, floored at zero; long call /
  long put: lesser of underlying MV × charge and the option MV. Footnote 344: FX 8%, commodity 15%.
  Example: 1,000 × 16% − 100 = 60.

## 15. Engine choices and TODO: VERIFY items

| Item | Provision | Engine treatment |
|---|---|---|
| √2 for GIRR inflation / xccy RW | MAR21.44 ("the above risk weights") | **TODO: VERIFY** — applied to Table 1 only (conservative) |
| Securitisation DRC RW conversion | MAR22.34(1), MAR22.42 | **TODO: VERIFY** — banking-book RW × 8% (1/12.5) |
| MAR33.4 liquidity-adjusted ES equation | MAR33.4 (image) | **TODO: VERIFY** — reconstructed cascade √(ES_T(P)² + Σ_{j≥2}(ES_T(P,j)·√((LH_j − LH_{j−1})/T))²) |
| Table 2 GIRR footnote-284 formula | MAR21.46 fn 284 (image) | printed table used (no TODO; table is authoritative) |
| Vega RW formula | MAR21.92 fn 295 (image) | printed Table 13 used |
| AAA vs AA in DRC | MAR22.24 Table 2 | engine `RatingBucket` merges AAA..AA-; AA (2%) unless `flags['drc_aaa']` |
| Non-IG covered bond | MAR21.51 Table 3 | no HY covered-bond bucket; mapped to other sector 16 |
| Bucket-25 simple sum for vega/curvature | MAR21.71 (delta) | applied to vega and curvature too |
| Across-bucket sum still negative after alternative S_b | MAR21.4(5)(b) | floored at zero |
| Discretions | MAR21.44, 21.53 fn 288, 21.88, 22.7 | `BCBSFRTBOptions` (bank discretions exercised by default; MAR22.7 not) |
