# UK PRA Market Risk (FRTB) -- Parameter Reference (PS1/26)

**Source (authority):** PRA PS1/26 Appendix 1, *PRA Rulebook: CRR Firms: (CRR) Instrument 2026*
(PRA2026/1), in force **1 January 2027**. Page references are "p. N of 492" of that instrument
(page = the footer that closes the page; checked against the rendered PDF for Tables 2, 4, 5 and
the Article 325ad / 340 formulas). Parts used:

| Annex | Part | Pages |
|---|---|---|
| G | Market Risk: General Provisions (CRR) Part | 224-233 |
| H | Market Risk: Internal Model Approach (CRR) Part | 234-307 |
| I | Market Risk: Advanced Standardised Approach (CRR) Part | 310-361 |
| J | Market Risk: Simplified Standardised Approach (CRR) Part | 362-392 |

Text in quotation marks is copied from the instrument. Implementation: `src/jurisdictions/uk/frtb/`.
Items the text does not settle are listed at the end (**TODO: VERIFY**). Amounts stated in GBP
are carried in GBP millions.

---

## 1. Structure and approaches

**Art 325(1) (p. 226):** own funds requirements for market risk of all trading book positions and
non-trading book positions subject to FX or commodity risk under "(a) the advanced standardised
approach ...; (b) the simplified standardised approach referred to in paragraph 2, if it meets the
conditions set out in Article 325a; or (c) (i) during the IMA transitional period, the internal
model approach set out in ... Part 4.2 ... (ii) after the end of the IMA transitional period, the
internal model approach ...".

**Art 325c(2) (p. 313):** advanced standardised approach = "the sum of the following three
components: (i) the own funds requirement under the sensitivities-based method set out in Section 2;
(ii) the own funds requirement for residual risks set out in Section 4 ...; and (iii) the own funds
requirement for the default risk set out in Section 5".

**RWA:** Required Level of Own Funds (CRR) Part Art 92(4)(b): requirements multiplied by **12.5**
(p. 15).

---

## 2. Sensitivities-based method -- formulas (Annex I)

**Art 325f(6) (p. 315):** WS_k = RW_k · s_k.

**Art 325f(7) (p. 315):** "where the quantity within the square root function is floored at zero"
K_b = √( Σ_k WS_k² + Σ_k Σ_{l≠k} ρ_kl WS_k WS_l ).

**Art 325f(8) (p. 315-316):** risk class charge = √( Σ_b K_b² + Σ_b Σ_{c≠b} γ_bc S_b S_c ),
S_b = Σ_k WS_k; "where those values for S_b and S_c produce a negative number for the overall sum
... the institution shall calculate ... using an alternative specification whereby:
S_b = max[min(Σ_k WS_k, K_b), −K_b]; S_c = max[min(Σ_k WS_k, K_c), −K_c]".

**Art 325g(2) (p. 316):** CVR_k⁺ = −Σ_i CVR_ik⁺; CVR_k⁻ = −Σ_i CVR_ik⁻;
CVR_ik⁺ = V_i(x_k^{RW(Curvature)+}) − V_i(x_k) − RW_k^{Curvature} × s_ik;
CVR_ik⁻ = V_i(x_k^{RW(Curvature)−}) − V_i(x_k) + RW_k^{Curvature} × s_ik.
(3): GIRR, CSR and commodity curvature at the level of the entire curve.

**Art 325g(4) (p. 317):**
K_b = max(K_b⁺, K_b⁻) where K_b⁺ ≠ K_b⁻; K_b⁺ where K_b⁺ = K_b⁻ and Σ_k CVR_k⁺ > Σ_k CVR_k⁻;
K_b⁻ otherwise;
K_b^± = √max(0, Σ_k max(CVR_k^±, 0)² + Σ_{l≠k} Σ_k ρ_kl CVR_k^± CVR_l^± ψ(CVR_k^±, CVR_l^±));
ψ(x, y) = 0 where x < 0 and y < 0; 1 otherwise.

**Art 325g(5) (p. 317):** for bucket 16 of Table 4, bucket 16 of Table 6, bucket 25 of Table 7
and bucket 11 of Table 8: K_b = max(Σ_k max(CVR_k⁺, 0), Σ_k max(CVR_k⁻, 0)).

**Art 325g(6) (p. 317):** RCCR = √max(0, Σ_b K_b² + Σ_{c≠b} Σ_b γ_bc S_b S_c ψ(S_b, S_c)),
S_b = Σ_k CVR_k⁺ where K_b = K_b⁺, Σ_k CVR_k⁻ otherwise. (7): curvature = sum of RCCR over
risk classes.

**Art 325h (p. 318):** "performed three times per risk class ... (a) the medium correlations
scenario, whereby the correlation parameters ρ_kl and γ_bc remain unchanged ...; (b) the high
correlations scenario, whereby the correlation parameters ... shall be uniformly multiplied by
1.25, with ρ_kl and γ_bc subject to a cap at 100%; and (c) the low correlations scenario, whereby
ρ_kl^low = max(2·ρ_kl − 100%, 75%·ρ_kl) and γ_bc^low = max(2·γ_bc − 100%, 75%·γ_bc)".
"3. An institution shall calculate the sum of the delta, vega and curvature risk class-specific own
funds requirements for each scenario to determine three scenario-specific own funds requirements.
4. The own funds requirement under the sensitivities-based method shall be the highest of the three
scenario-specific own funds requirements" -- **one binding scenario on the total across risk
classes** (same as BCBS MAR21.7).

**Art 325ay(4) (p. 361):** "no diversification or hedging benefit ... between vega risk factors
and delta risk factors ... aggregated by simple summation". **(5):** "The curvature risk
correlations shall be the square of corresponding delta risk correlations ρ_kl and γ_bc".

**Art 325i (p. 319-320):** look-through for indices; single sensitivity allowed for a listed index
that has "(b) at least 20 constituents; (c) no single constituent ... more than 25%...; (d) no set
comprising one tenth of the total number of constituents ... rounded up ... more than 60% ...;
(e) total market capitalisation ... no less than GBP 32 billion"; assigned to a single bucket where
"more than 75% of constituents" map there, otherwise to the index bucket.

---

## 3. Risk factors and sensitivities

- **GIRR (Art 325l, p. 322-324):** one bucket per currency; vertices "0.25 years, 0.5 years, one
  year, two years, three years, five years, 10 years, 15 years, 20 years, 30 years" assigned "by
  linear interpolation or ..."; inflation: one risk factor per inflation curve; cross-currency
  basis: "basis over euro and basis over US dollar ... maximum number of net sensitivities per
  bucket shall be two"; vega: option maturity and underlying residual maturity "0.5 years, one
  year, three years, five years, 10 years"; curvature: one vector per currency, "no curvature risk
  own funds requirements for inflation and cross currency basis risks".
- **CSR (Art 325m-325n, p. 324-325):** vertices 0.5, 1, 3, 5, 10 years; "two distinct risk factors
  per issuer and maturity: one ... for debt instruments and one ... for credit default swaps";
  curvature vectors from bonds or CDS of the same issuer are the same risk factor; non-ACTP uses the
  tranche spread.
- **Equity (Art 325o, p. 326):** spot prices and repo rates; "no own funds requirements for vega
  risk for equity repo rates"; "no curvature risk own funds requirements for equity repo rates".
- **Commodity (Art 325p, p. 327):** vertices "0 years, 0.25 years, 0.5 years, one year, two years,
  three years, five years, 10 years, 15 years, 20 years, 30 years"; same factor only if delivery
  location terms identical; curvature does not differentiate by delivery location.
- **FX (Art 325q, p. 327-328):** spot rates against the reporting (or approved base) currency; "one
  bucket per currency pair, containing a single risk factor and a single net sensitivity".
  (5): where an FX underlying refers to neither the reporting nor the base currency, CVR⁺/CVR⁻ may
  be divided by **1.5**; (6) with PRA permission for all FX risk factors.
- **Sensitivity definitions (Art 325r-325s, p. 329-331):** 1 bp shift / 0.0001 for rates and
  spreads, 1% relative / 0.01 for equity, commodity and FX; vega S_k = (V(vol+0.01) − V(vol)) /
  0.01 · vol_k; options without maturity mapped to the longest maturity and subject to the RRAO.

---

## 4. GIRR weights and correlations (Art 325ae-325ag, p. 343-345)

**Table 3 (p. 344):**

| Sub-bucket | Maturity | RW |
|---|---|---|
| 1 | 0.25 years | 1.7% |
| 2 | 0.5 years | 1.7% |
| 3 | One year | 1.6% |
| 4 | Two years | 1.3% |
| 5 | Three years | 1.2% |
| 6 | Five years | 1.1% |
| 7 | 10 years | 1.1% |
| 8 | 15 years | 1.1% |
| 9 | 20 years | 1.1% |
| 10 | 30 years | 1.1% |

- 325ae(2): "1.6% to all sensitivities of inflation and to cross currency basis risk factors".
- 325ae(3): most liquid currencies (IMA Part Art 325bd(8)(a), p. 251: "AUD; CAD; EUR; GBP; JPY;
  SEK; USD") "and ... the domestic currency of the institution ... divided by √2".
- 325af(1): same maturity, different curves: **99.90%**. (2): same curve, different maturities:
  max[e^(−θ·|T_k−T_l|/min{T_k;T_l}); 40%], **θ = 3%**. (3): different curves and maturities:
  paragraph 2 value × 99.90%. (4): GIRR vs inflation **40%**. (5): cross-currency basis vs any GIRR
  factor **0%**. (6): two different inflation factors, same currency **99.90%**.
- 325ag(1): **γ_bc = 50%**.

---

## 5. CSR non-securitisation (Art 325ah-325aj, p. 345-349)

**Table 4 (p. 345-347):**

| Bucket | Credit quality | Sector | RW |
|---|---|---|---|
| 1 | All | The central government of the UK and the Bank of England | 0.5% |
| 1 | Investment grade | Central government, incl. central banks, of a third country, MDBs and Art 117(2)/118 international organisations | 0.5% |
| 2 | IG | Regional or local authority and public sector entities | 1.0% |
| 3 | IG | Financial sector entities incl. credit institutions ... and promotional lenders | 5.0% |
| 4 | IG | Basic materials, energy, industrials, agriculture, manufacturing, mining and quarrying | 3.0% |
| 5 | IG | Consumer goods and services, transportation and storage, administrative and support service activities | 3.0% |
| 6 | IG | Technology, telecommunications | 2.0% |
| 7 | IG | Health care, utilities, professional and technical activities | 1.5% |
| 8 | IG (AA- or higher) | Covered bonds issued by credit institutions | 1.5% |
| 8 | IG (Other) | Covered bonds issued by credit institutions | 2.5% |
| 9 | Non-IG and unrated | Central government ... third country, MDBs, Art 117(2)/118 | 2.0% |
| 10 | Non-IG and unrated | Regional or local authority and PSEs | 4.0% |
| 11 | Non-IG and unrated | Financial sector entities ... | 12.0% |
| 12 | Non-IG and unrated | Basic materials, energy, ... | 7.0% |
| 13 | Non-IG and unrated | Consumer goods and services, ... | 8.5% |
| 14 | Non-IG and unrated | Technology, telecommunications | 5.5% |
| 15 | Non-IG and unrated | Health care, utilities, ... | 5.0% |
| 16 | Other Sector | | 12.0% |
| 17 | Listed credit indices with a majority of its individual constituents being investment grade | | 1.5% |
| 18 | Listed credit indices with a majority ... non-investment grade or unrated | | 5.0% |

- 325ah(2): unassignable issuers to bucket 16. (3): IG per nominated ECAI, internal-rating mapping
  otherwise. (4): non-tranched GSE MBS to bucket 2.
- 325ai(1): ρ_kl = ρ(name)·ρ(tenor)·ρ(basis); ρ(name) = 1 identical names, **35%** buckets 1-15,
  **80%** buckets 17-18; ρ(tenor) = 1 identical vertices, else **65%**; ρ(basis) = 1 same curves,
  else **99.90%**. (2): bucket 16: K_b = Σ_k |WS_k|.
- 325aj: γ_bc = γ(rating)·γ(sector); "γ(rating) = 1 where the two buckets have the same rating
  category (either investment grade, non-investment grade or unrated), otherwise it shall be equal
  to **50%**"; γ(sector) = 1 same sector, else Table 5.

**Table 5 (p. 348-349):**

| Bucket | 1 and 9 | 2 and 10 | 3 and 11 | 4 and 12 | 5 and 13 | 6 and 14 | 7 and 15 | 8 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 and 9 | | 75% | 10% | 20% | 25% | 20% | 15% | 10% | 0% | 45% | 45% |
| 2 and 10 | | | 5% | 15% | 20% | 15% | 10% | 10% | 0% | 45% | 45% |
| 3 and 11 | | | | 5% | 15% | 20% | 5% | 20% | 0% | 45% | 45% |
| 4 and 12 | | | | | 20% | 25% | 5% | 5% | 0% | 45% | 45% |
| 5 and 13 | | | | | | 25% | 5% | 15% | 0% | 45% | 45% |
| 6 and 14 | | | | | | | 5% | 20% | 0% | 45% | 45% |
| 7 and 15 | | | | | | | | 5% | 0% | 45% | 45% |
| 8 | | | | | | | | | 0% | 45% | 45% |
| 16 | | | | | | | | | | 0% | 0% |
| 17 | | | | | | | | | | | 75% |

---

## 6. CSR securitisation

**ACTP -- Table 6 (Art 325ak, p. 349-351):** 1 (UK central government and Bank of England; third
country central government / MDBs / Art 117(2), 118) 4.0%; 2 RGLA and PSEs 4.0%; 3 financials 8.0%;
4 basic materials ... 5.0%; 5 consumer ... 4.0%; 6 technology, telecommunications 3.0%; 7 health
care ... 2.0%; 8 covered bonds 6.0%; 9 third-country central government ... 13.0%; 10 RGLA and PSEs
13.0%; 11 financials 16.0%; 12 basic materials 10.0%; 13 consumer 12.0%; 14 technology 12.0%;
15 health care 12.0%; 16 Other Sector 13.0%. Buckets 1-8 investment grade; 9-15 non-investment
grade and unrated.
**Art 325al (p. 351):** ρ per Art 325ai except "ρ(basis) shall be equal to 1 where the two
sensitivities are related to the same curves, otherwise it shall be equal to **99.00%**"; γ per
Art 325aj.

**Non-ACTP -- Table 7 (Art 325am, p. 351-352):**

| Bucket | Credit quality | Sector | RW |
|---|---|---|---|
| 1-8 | Senior Investment Grade | RMBS-Prime / Mid-prime / Sub-prime / CMBS / ABS-Student Loans / ABS-Credit Cards / ABS-Auto / CLO non-ACTP | 0.9% / 1.5% / 2.0% / 2.0% / 0.8% / 1.2% / 1.2% / 1.4% |
| 9-16 | Non-senior Investment Grade | same order | 1.125% / 1.875% / 2.5% / 2.5% / 1.0% / 1.5% / 1.5% / 1.75% |
| 17-24 | Non-Investment grade and unrated | same order | 1.575% / 2.625% / 3.5% / 3.5% / 1.4% / 2.1% / 2.1% / 2.45% |
| 25 | Other sector | | 3.5% |

**Art 325an (p. 353):** ρ = ρ(tranche)·ρ(tenor)·ρ(basis); ρ(tranche) = 1 same tranche ("more than
80% overlap in notional terms"), otherwise **40%**; ρ(tenor) **80%**; ρ(basis) **99.90%**; bucket
25: K_b = Σ|WS_k|. **Art 325ao (p. 353):** "γ_bc ... at **0%**"; "(2) ... add the own funds
requirement for bucket 25 of Table 7 to the overall risk class level capital, with no
diversification or hedging effects recognised with any other bucket".

---

## 7. Equity (Art 325ap-325ar, p. 353-356)

**Table 8 (p. 354):**

| Bucket | Market cap | Economy | Sector | RW spot | RW repo |
|---|---|---|---|---|---|
| 1 | Large | Emerging market | Consumer goods and services, transportation and storage, administrative and support service activities, healthcare, utilities | 55% | 0.55% |
| 2 | Large | EM | Telecommunications, industrials | 60% | 0.60% |
| 3 | Large | EM | Basic materials, energy, agriculture, manufacturing, mining and quarrying | 45% | 0.45% |
| 4 | Large | EM | Financials incl. government-backed financials, real estate activities, technology | 55% | 0.55% |
| 5 | Large | Advanced economy | (as 1) | 30% | 0.30% |
| 6 | Large | AE | (as 2) | 35% | 0.35% |
| 7 | Large | AE | (as 3) | 40% | 0.40% |
| 8 | Large | AE | (as 4) | 50% | 0.50% |
| 9 | Small | EM | All sectors of buckets 1-4 | 70% | 0.70% |
| 10 | Small | AE | All sectors of buckets 5-8 | 50% | 0.50% |
| 11 | Other sector | | | 70% | 0.70% |
| 12 | Large market cap, advanced economy equity indices | | | 15% | 0.15% |
| 13 | Other equity indices | | | 25% | 0.25% |

- 325ap(2) with IMA Part Art 325bd(9) (p. 251): large capitalisation "greater than **GBP 1.60
  billion**". 325ap(3): advanced economies: Australia; Canada; euro-area member states; Denmark;
  Hong Kong SAR; Japan; Mexico; New Zealand; Norway; Singapore; Sweden; Switzerland; the United
  Kingdom; the United States; all others emerging markets. (4): unassignable issuers to bucket 11.
- 325aq(1): spot vs repo of the same issuer **99.90%**; (2): (a) **15%** buckets 1-4, (b) **25%**
  5-8, (c) **7.5%** 9, (d) **12.5%** 10, (e) **80%** 12-13; (3) repo-repo the same; (4) spot vs
  repo of different issuers = paragraph 2 × 99.90%; (5) bucket 11: K_b = Σ|WS_k|.
- 325ar: (a) **15%** both within 1-10; (b) **0%** either is 11; (c) **75%** buckets 12 and 13;
  (d) **45%** otherwise.

---

## 8. Commodity (Art 325as-325au, p. 356-359)

**Tables 9 and 10 (p. 357-358):**

| Bucket | Name | RW | ρ(commodity) |
|---|---|---|---|
| 1 | Energy – solid combustibles | 30% | 55% |
| 2 | Energy – liquid combustibles | 35% | 95% |
| 3a | Energy – electricity | 60% | 40% |
| 3b | Energy – carbon trading | 60% | 40% |
| 4 | Freight | 80% | 80% |
| 5 | Metals – non-precious | 40% | 60% |
| 6 | Gaseous combustibles | 45% | 65% |
| 7 | Precious metals (including gold) | 20% | 55% |
| 8 | Grains and oilseed | 35% | 45% |
| 9 | Livestock and dairy | 25% | 15% |
| 10 | Softs and other agricultural commodities | 35% | 40% |
| 11 | Other commodities | 50% | 15% |

- 325at(2)/(2A): ρ = ρ(commodity)·ρ(tenor)·ρ(basis); ρ(tenor) **99%**; ρ(basis) **99.90%** for
  different delivery locations. (4): electricity of different regions / delivery periods and freight
  of different routes / weeks are distinct commodities.
- 325au: **20%** both within 1-10; **0%** either is 11.

## 9. FX (Art 325av-325aw, p. 359)

- 325av(1): **15%**; (4): most liquid currency pairs (IMA Part Art 325bd(8)(b), p. 251: "any
  currency pairs formed from any two of the following currencies: AUD; Brazilian lire (BRL); CAD;
  CHF; CNY; EUR; GBP; HKD; INR; JPY; KRW; MXN; NOK; NZD; RUB; Swiss kroner (SEK); SGD; TRY; USD;
  ZAR") "divided by √2".
- 325aw: "uniform correlation parameter γ_bc equal to **60%**".

## 10. Vega and curvature (Art 325ax-325ay, p. 359-361)

**Table 11 (p. 359-360):** GIRR 100%; CSR non-securitisations 100%; CSR securitisations (ACTP)
100%; CSR securitisations (non-ACTP) 100%; Equity (large cap and indices) **77.78%**; Equity (small
cap and other sector) 100%; Commodity 100%; Foreign exchange 100%.

- 325ax(4): FX and equity curvature RW = relative shift equal to the delta RW; (5) GIRR, CSR and
  commodity: "parallel shift of all the vertices for each curve on the basis of the highest
  prescribed delta risk weight ... for the relevant bucket".
- 325ay(1): GIRR vega ρ_kl = min{ρ(option maturity)·ρ(underlying maturity); 1}, ρ = e^(−α·|T_k−T_l|
  /min{T_k;T_l}), **α = 1%**; (2) other classes ρ_kl = min{ρ(DELTA)·ρ(option maturity); 1};
  (3) γ as for delta.

---

## 11. Residual risk add-on (Art 325u, p. 333-335)

- (2)(a) exotic underlying; (b) other residual risks (non-replicable pay-offs; ACTP positions
  excluding hedges).
- (3): "sum of gross notional amounts ... multiplied by ... (a) **1%** ... point (a) ...; (b)
  **0.1%** ... point (b)".
- (4): other-residual-risk charge not applied to an instrument "(a) listed on a recognised exchange;
  or (b) eligible for central clearing". (4a): none for an instrument that "perfectly offsets the
  market risk of another matching position in the trading book, provided that such position is with
  a third party"; remaining net notional charged.
- (5): exotic underlyings include "(a) longevity; (b) weather; (c) natural disasters; and (d) future
  realised volatility". (6)-(7): examples and exclusions.

---

## 12. Default risk charge (Art 325v-325ad, p. 335-343)

- **325w(1)-(2) (p. 336):** JTD_long = max{V_A − V_D; 0}; JTD_short = min{V_A − V_D; 0}; V_D
  assumes default with recovery "(1-LGD)" on face value. **(3) (p. 337):** LGD "(a) non-senior debt
  ... **100%**; (b) senior debt ... **75%**; (c) covered bonds ... **25%**". **(4):** equity V_D:
  "a full loss in value". (6) defaulted obligor already reflected → 0; (7) unwind with no default
  exposure → 0.
- **325x (p. 337-338):** offsetting "only ... between exposures to the same obligor where the short
  exposures have the same seniority as, or lower seniority than, the long exposures"; exposures
  < 1 year "multiplied by the ratio of the exposure's maturity relative to one year, with a floor
  of three months"; derivatives use their own maturity; cash equity 1 year or 3 months.
- **325y Table 2 (p. 338-339):** AAA **0.5%**; AA+ to AA- **2%**; A+ to A- **3%**; BBB+ to BBB-
  **6%**; BB+ to BB- **15%**; B+ to B- **30%**; CCC+ and below **50%**; Unrated **15%**; Defaulted
  **100%**. (2): "Exposures which would receive a 0% risk-weight under the Standardised Approach
  shall receive a 0% default risk weight". (3): buckets "corporates, sovereigns, and local
  governments/municipalities". (4): DRC_b = max{(Σ_{long} RW_i·netJTD_i) − WtS × (Σ_{short}
  RW_i·|netJTD_i|); 0}, WtS = Σ netJTD_long / (Σ netJTD_long + Σ|netJTD_short|). (5): simple sum.
- **325z-325aa (p. 340-341):** securitisation gross JTD = market value; offsetting only same pool and
  same tranche; RW = "8% of the risk weight that applies ... in the non-trading book"; maturity one
  year for RWs under Art 259/263 CRR; cap at fair value for cash securitisations; buckets "(a) one
  common bucket for all corporates, regardless of the region; (b) 44 different buckets ... one
  bucket per region for each of the 11 asset classes": ABCP; auto loans/leases; RMBS; credit cards;
  CMBS; CLO; CDO squared; SMEs; student loans; other retail; other wholesale × Asia; Europe; North
  America; rest of the world.
- **325ac-325ad (p. 341-343):** ACTP gross JTD = market value; nth-to-default attachment (N−1)/Total
  Names, detachment N/Total Names; RW Table 2 (non-tranched) or Art 325aa(1) (tranched); buckets =
  indices; "DRC_b = max{(Σ RW·netJTD) − WtS_ACTP·(Σ RW·|netJTD|); 0}" with WtS_ACTP over the entire
  ACTP; "DRC_ACTP = max{Σ_b max{DRC_b, 0} + 0.5·(min{DRC_b, 0}); 0}".

---

## 13. Internal model approach scalars (Annex H)

- 325bb(1) (p. 243-244): ES_t = ρ·UES_t + (1−ρ)·Σ_i UES_t^i, **ρ = 50%**.
- 325bc(1) (p. 245-246): daily, "97.5th percentile, one tailed"; PES_t = √((PES_t(T))² +
  Σ_{j≥2}(PES_t(T,j)·√((LH_j − LH_{j−1})/10))²), T = 10 days; Table 1 LH_j = 10, 20, 40, 60, 120
  days. 325bc(2)(a): reduced-set ratio ≥ **75%**; stress period from 1 January 2007.
- 325bd Table 2 (p. 249-251): IR most liquid and domestic 10; other currencies 20; volatility 60;
  other 60. CS sovereign IG 20; sovereign HY 40; corporate IG 40; corporate HY 60; volatility 120;
  other 120. Equity large cap 10; small cap 20; volatility large 20; volatility small 60; other 60.
  FX most liquid pairs 10; other pairs 20; volatility 40; other 40. Commodity energy and carbon 20;
  precious and non-ferrous 20; other prices 60; energy/carbon volatility 60; precious/non-ferrous
  volatility 60; other volatilities 120; other 120.
- 325ba(1) (p. 241): max(ES_{t−1} + SS_{t−1}; m_c·ES_avg + SS_avg), 60-day averages; (2) IDRC higher
  of latest and 12-week average; (3) min(IMA_{g&y} + capital surcharge + C_U; SA_all) +
  max(IMA_{g&y} − SA_{g&y}; 0); (5) k = 0.5 × Σ_y SA_i / Σ_{g&y} SA_i.
- 325bf(3) (p. 260): desk back-testing limits 12 (99%) / 30 (97.5%) overshootings in 250 days.
  (6) Table 3 (p. 261-262): m_c = 1.5 + add-on: fewer than 5 → 0.00; 5 → 0.20; 6 → 0.26; 7 → 0.33;
  8 → 0.38; 9 → 0.42; more than 9 → 0.50.
- 325bg(7) (p. 269): green: Spearman > **0.8** and KS < **0.09**; red: Spearman < **0.7** or KS >
  **0.12**; orange / yellow otherwise.
- 325bk (p. 278-283): SS_j = SS_j(T)·√(max(20, LH_j)/10); SS_total = √Σ_{ICSR} SS_k² +
  √Σ_{IEQ} SS_l² + √((ρ·Σ_{OR} SS_j)² + (1−ρ²)·Σ_{OR} SS_j²), **ρ = 0.6**.
- 325bn (p. 284): IDRC VaR at **99.9%** over one year; weekly.
- Transitional: "IMA transitional period means the period beginning with 1 January 2027 and ending
  with 31 December 2027" (Glossary, p. 5); IMA Part rule 4.1 (p. 238): for one year after it every
  IMA desk is treated as a green desk.

---

## 14. Simplified standardised approach (Annex G Art 325(2)/325a; Annex J)

**Multipliers (Art 325(2), p. 226-227):** debt (Art 334-340) × **1.3**; equity (Art 341-344, 346,
347) × **3.5**; CIUs (Art 348) × **3.5**; FX (Art 351-354) × **1.2**; commodities (Art 355-361) ×
**1.9**.

**Eligibility (Art 325a(1), p. 231):** market-risk business ≤ "(a) 10% of the institution's total
assets; and (b) GBP 440 million", monthly; loss of eligibility after 3 consecutive months or more
than 6 of the last 12.

**Art 336 Table 1 (p. 370):** SA RW 0% → 0%; > 0% and ≤ 50% → 0.25% (residual ≤ 6 months), 1.00%
(> 6 and ≤ 24 months), 1.60% (> 24 months); > 50% and ≤ 100% → 8%; > 100% → 12%. 336(3): 10%-RW
covered bonds at half the second category. **Art 337(1):** securitisations 8% of the non-trading
book RW; (4) summed regardless of sign. **Art 335:** cap at maximum default-related loss.

**Art 339 Table 2 (p. 372-373):**

| Zone | Coupon ≥ 3% | Coupon < 3% | Weighting (%) | Assumed rate change (%) |
|---|---|---|---|---|
| One | 0 ≤ 1 month | 0 ≤ 1 month | 0.00 | — |
| | > 1 ≤ 3 months | > 1 ≤ 3 months | 0.20 | 1.00 |
| | > 3 ≤ 6 months | > 3 ≤ 6 months | 0.40 | 1.00 |
| | > 6 ≤ 12 months | > 6 ≤ 12 months | 0.70 | 1.00 |
| Two | > 1 ≤ 2 years | > 1.0 ≤ 1.9 years | 1.25 | 0.90 |
| | > 2 ≤ 3 years | > 1.9 ≤ 2.8 years | 1.75 | 0.80 |
| | > 3 ≤ 4 years | > 2.8 ≤ 3.6 years | 2.25 | 0.75 |
| Three | > 4 ≤ 5 years | > 3.6 ≤ 4.3 years | 2.75 | 0.75 |
| | > 5 ≤ 7 years | > 4.3 ≤ 5.7 years | 3.25 | 0.70 |
| | > 7 ≤ 10 years | > 5.7 ≤ 7.3 years | 3.75 | 0.65 |
| | > 10 ≤ 15 years | > 7.3 ≤ 9.3 years | 4.50 | 0.60 |
| | > 15 ≤ 20 years | > 9.3 ≤ 10.6 years | 5.25 | 0.60 |
| | > 20 years | > 10.6 ≤ 12.0 years | 6.00 | 0.60 |
| | | > 12.0 ≤ 20.0 years | 8.00 | 0.60 |
| | | > 20 years | 12.50 | 0.60 |

339(9): "(a) 10% of the sum of the matched weighted positions in all maturity bands; (b) 40% ...
zone one; (c) 30% ... zone two; (d) 30% ... zone three; (e) 40% ... between zones one and two and
between zones two and three; (f) 150% ... between zones one and three; and (g) 100% of the residual
unmatched weighted positions". (6): zones two-three may be matched first.

**Art 340 (p. 373-374):** modified duration = D/(1+R); D = Σ t·C_t/(1−R)^t ÷ Σ C_t/(1−R)^t as
printed (see TODO). Table 3: zone one > 0 ≤ 1.0 (1.0%); two > 1.0 ≤ 3.6 (0.85%); three > 3.6 (0.7%).
340(7): 2% matched per zone; 40% adjacent zones; 150% zones one-three; 100% residual.

**Equities (Art 341-344, p. 375-376):** specific 8% × overall gross position; general 8% × overall
net position (per national market); no specific risk for exchange-traded futures on appropriately
diversified indices (≥ 20 equities; no equity > 25%; top 10% < 60%; ≥ 4 industries).

**Underwriting Art 345 Table 4 (p. 376):** day 0 100%; day 1 90%; days 2-3 75%; day 4 50%; day 5
25%; after day 5 0%.

**CIUs Art 348(1) (p. 378):** 32% (specific and general); 40% including FX.

**FX Art 351-354 (p. 380-388):** charge only if net FX + net gold "exceeds 2% of its total own
funds"; 8% × (overall net FX position + net gold); overall net = higher of total net short and total
net long (Art 352(4)); closely correlated currencies 4% of matched position (Art 354(1)).

**Options Art 352a (p. 382-387):** simplified approach (bought options only) max(0, gross amount −
risk-weighted delta equivalent); delta-plus gamma impact = ½ × Gamma × VU², sum per distinct
underlying type, requirement = |sum of negative values|; vega: ±25% shift in implied volatility,
sum per underlying type, sum of absolute values; scenario approach (≥ 7 price points, ≥ 3 vol
points, requirement −min(0, PC − DE)).

**Commodities (Art 359-361, p. 390-392):** Table 1 bands 0 ≤ 1 month, > 1 ≤ 3 months, > 3 ≤ 6
months, > 6 ≤ 12 months, > 1 ≤ 2 years, > 2 ≤ 3 years, > 3 years, spread rate **1.50%** each;
359(5): (a) matched long and short × spread × spot; (b) matched between bands × **0.6%** carry for
each band carried; (c) residual × **15%** outright. Art 360: 15% × |net| + 3% × gross. Art 361
Table 2 (spread / carry / outright): precious metals (except gold) 1.0 / 0.3 / 8; base metals
1.2 / 0.5 / 10; agricultural products (softs) 1.5 / 0.6 / 12; other incl. energy 1.5 / 0.6 / 15.

---

## Not settled by the instrument (TODO: VERIFY)

1. **Art 325ad(3) floor (p. 343):** the PRA (and CRR) text floors ACTP DRC_b at zero, which makes the
   0.5·min(DRC_b, 0) term of 325ad(4) inert; BCBS MAR22.44(2) has no bucket floor. Literal text is
   the default (`UKMarketRisk(ctp_bucket_floor=False)` gives the BCBS reading).
2. **Art 325aj γ(rating) (p. 348):** applied literally to any two buckets of different rating
   category, including 17 vs 18 (37.5%) and 8 vs 18; BCBS MAR21.57 limits it to buckets 1-15.
3. **Non-IG covered bonds:** Tables 4 and 6 have no non-IG covered-bond bucket; bucket 16
   (Art 325ah(2) unassignable) used.
4. **ACTP index sensitivities:** Table 6 has no index bucket; bucket 16 used.
5. **Art 340(3) duration formula (p. 374):** printed with (1 − R)^t; CRR Art 340(3) uses (1 + R)^t,
   which is implemented.
6. **Securitisation banking-book RW missing:** 1,250% placeholder (DRC and SSA specific risk).
7. **SSA option non-delta multiplier:** Art 325(2) does not list Art 352a; scaled by the underlying
   category's multiplier.
8. **AAA vs AA DRC weight:** the contract's rating bucket merges AAA with AA; 2% unless
   `flags['rating_aaa']`.
