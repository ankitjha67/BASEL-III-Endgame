# EU market risk (FRTB) -- parameter reference

Verbatim transcription of every table and formula implemented in `src/jurisdictions/eu/frtb/`.

**Sources**

* **CRR3** -- Regulation (EU) 2024/1623 of 31 May 2024 (OJ L, 19.6.2024), Article 1 points
  (156)-(196), (236), (242), (245) and Article 2. "p." = OJ page of the 189-page act. CRR3 is the
  authority wherever it replaces or amends an article.
* **Consolidated CRR** -- 02013R0575 -- EN -- 09.07.2024 -- 017.001. In Chapter 1a the
  consolidation carries Commission Delegated Regulation (EU) 2021/424 (marker `M12`), which
  recalibrated Tables 3-11. The CRR3 market-risk amendments (applicable from 1 January 2025) are
  **not** consolidated there (only the 9 July 2024 points are, marker `M17`), so CRR3 was read
  directly. "cons. p." = page of the consolidated PDF.
* Formulas printed as images in the text extraction were read from rendered PDF pages: cons.
  pp. 426-430 (325f(8), 325g, 325h(2)(c)), 457 (325ad(4)), 477 (325bc(1)(c)); CRR3 pp. 120
  (325s(1)), 121 (325ad(3), 325ae(3)), 125 (325ba(3)).

---

## 1. Approaches and application -- Article 325 (CRR3 point (156)), 325a (point (157))

Article 325(1): "An institution shall calculate the own funds requirements for market risk for
all its trading book positions and all its non-trading book positions that are subject to foreign
exchange risk or commodity risk in accordance with the following approaches: (a) the alternative
standardised approach set out in Chapter 1a; (b) the alternative internal model approach set out
in Chapter 1b ...; (c) the simplified standardised approach referred to in paragraph 2 of this
Article, provided that the institution meets the conditions set out in Article 325a(1)."

Article 325(2) (simplified standardised approach) -- sum of:

| Component | Multiplier |
|---|---|
| (a)(i) position risk, Chapter 2, general and specific risks of debt instruments, excluding securitisation instruments (Art 337) | 1,3 |
| (a)(ii) position risk, general and specific risks of equity instruments | 3,5 |
| (b) foreign exchange risk, Chapter 3 | 1,2 |
| (c) commodity risk, Chapter 4 | 1,9 |
| (d) securitisation instruments, Article 337 | (none) |

Article 325(4): ASA and AIMA may be combined permanently "provided that the total own funds
requirements for market risk calculated using the alternative internal model approach represent
at least 10 % of the total own funds requirements for market risk"; SSA not combined with either
on an individual basis.

Article 325a(1) thresholds (kept by CRR3, which replaced only the introductory wording):
"(a) 10 % of the institution's total assets; (b) EUR 500 million", assessed monthly. 325a(5):
cease within three months if a condition is not met "for three consecutive months" or "during
more than 6 out of the last 12 months".

Article 92(6)(b) (CRR3 point (28)): "institutions shall multiply the own funds requirements set
out in paragraph 4, points (b) to (f), by 12,5."

### Application dates and transitional provisions

* CRR3 Article 2: "It shall apply from 1 January 2025." Points applicable from 9 July 2024 that
  concern market risk: (156)(b) [325(9) RTS], (159)(c) concerning 325c(8), (160)(c) concerning
  325j(7), (164)(b) [325u(6)-(7)], (178)(e), (180), (182)(d), (183)(c), (184)(b)(iii) (all RTS
  mandates / EBA opinions).
* Article 461a(2) (CRR3 point (236)): the Commission may by delegated act "(a) apply[], until
  the date of application of the legislative act referred to in paragraph 3 ... or for up to three
  years in the absence of such an act, ... targeted operational relief measures or targeted
  multipliers equal to or greater than 0 and lower than 1 ... for specific risk classes and
  specific risk factors" (ASA 325c-325ay, AIMA 325az-325bp, SSA 326-361); "(b) postpon[e] for up
  to two years the date from which institutions shall apply the own funds requirements for market
  risk set out in Part Three, Title IV". 461a(3): EBA report by 10 July 2026. **The postponing
  delegated acts are not among the supplied texts** -- TODO: VERIFY.
* Article 325u(4a) (CRR3 point (164)(a)): RRAO hedge derogation "until 31 December 2032";
  325u(7): EBA report by 31 December 2029.
* Article 495h (CRR3 point (242)): "institutions may use, until 1 January 2026, the alternative
  internal model approach ... for trading desks that do not meet the requirements laid down in
  Article 325bg."
* Article 500c (CRR3 point (245)): COVID-19 back-testing overshootings (1 January 2020 to
  31 December 2021) may be excluded.

---

## 2. Sensitivities-based method -- Articles 325e-325h

**325f(6)**: `WS_k = RW_k · s_k`.

**325f(7)**: `K_b = sqrt( Σ_k WS_k² + Σ_k Σ_{k≠l} ρ_kl WS_k WS_l )`, "where the quantity within the
square root function is floored at zero".

**325f(8)**: `Risk-class requirement = sqrt( Σ_b K_b² + Σ_b Σ_{c≠b} γ_bc S_b S_c )`,
`S_b = Σ_k WS_k`; (C7) "where those values for S_b and S_c produce a negative number for the
overall sum ..., the institution shall calculate ... using an alternative specification whereby
S_b = max[min(Σ_k WS_k, K_b), − K_b] ... and S_c = max[min(Σ_k WS_k, K_c), − K_c]".

**325g(2)** (M12, cons. p.426):
`CVR_k^+ = − Σ_i CVR_ik^+`, `CVR_k^- = − Σ_i CVR_ik^-`,
`CVR_ik^+ = V_i(x_k^{RW(Curvature)+}) − V_i(x_k) − RW_k^Curvature × s_ik`,
`CVR_ik^- = V_i(x_k^{RW(Curvature)-}) − V_i(x_k) + RW_k^Curvature × s_ik`.
325g(3): for GIRR, CSR and commodity curves the calculation is performed at the level of the
entire curve; `s_ik` is the sum of the delta sensitivities across all tenors.

**325g(4)** (cons. p.428):
```
K_b = max(K_b^+, K_b^-),          where K_b^+ ≠ K_b^-
      K_b^+, where K_b^+ = K_b^- and Σ_k CVR_k^+ > Σ_k CVR_k^-
      K_b^-, otherwise
K_b^+ = sqrt( max(0, Σ_k max(CVR_k^+, 0)² + Σ_{l≠k} Σ_k ρ_kl CVR_k^+ CVR_l^+ ψ(CVR_k^+, CVR_l^+)) )
K_b^- = sqrt( max(0, Σ_k max(CVR_k^-, 0)² + Σ_{l≠k} Σ_k ρ_kl CVR_k^- CVR_l^- ψ(CVR_k^-, CVR_l^-)) )
ψ(x, y) = 0, where x < 0 and y < 0;  1, otherwise
```
**325g(5)**: for bucket 18 of Art 325ah, bucket 18 of 325ak, bucket 25 of 325am and bucket 11 of
325ap: `K_b = max( Σ_k max(CVR_k^+, 0), Σ_k max(CVR_k^-, 0) )`.

**325g(6)**: `RCCR = sqrt( max(0, Σ_b K_b² + Σ_{c≠b} Σ_b γ_bc S_b S_c ψ(S_b, S_c)) )`,
`S_b = Σ_k CVR_k^+` where `K_b = K_b^+`, otherwise `Σ_k CVR_k^-` (cons. p.429).
**325g(7)**: curvature requirement = sum of the RCCR across risk classes.

**325h(2)** -- three correlation scenarios:
* (a) medium: ρ_kl and γ_bc unchanged;
* (b) high: "uniformly multiplied by 1,25, with ρ_kl and γ_bc subject to a cap at 100 %";
* (c) low (M12, cons. p.430): `ρ_kl^low = max(2 · ρ_kl − 100 %; 75 % · ρ_kl)` and
  `γ_bc^low = max(2 · γ_bc − 100 %; 75 % · γ_bc)`.

**325h(3)-(4)**: sum delta, vega and curvature risk-class requirements per scenario; the SBM
requirement "shall be the highest of the three scenario-specific own funds requirements".

**325q(5)-(6)** (M12): where the FX underlying refers neither to the reporting nor base currency,
the institution "may divide by 1,5 the corresponding components" CVR^+/CVR^-; with permission,
for all FX curvature risk factors.

**325s(1)** as replaced by CRR3 point (162) (p.120): `s_k = (V_i(1,01 · vol_k, x, y) − V_i(vol_k, x, y)) / 0,01`.

**325k(2) Table 1** (underwriting, ASA): business day 0: 0 %; 1: 10 %; 2 and 3: 25 %; 4: 50 %;
5: 75 %; after business day 5: 100 %.

**325i(3)** listed-index single-sensitivity conditions: (b) at least 20 constituents; (c) no
constituent > 25 % of market capitalisation; (d) top one tenth of constituents ≤ 60 %; (e) total
market capitalisation ≥ EUR 40 billion. 325i(1)(c)(i)/(2)(a): "more than 75 % of constituents"
mapped to one bucket. 325j(2): tracking difference "below 1 % in absolute terms".

---

## 3. GIRR -- Articles 325l, 325ae-325ag

325l(1): vertices "0,25 years, 0,5 years, 1 year, 2 years, 3 years, 5 years, 10 years, 15 years,
20 years, 30 years"; one bucket per currency. 325l(7): vega maturities "0,5 years, 1 year,
3 years, 5 years, 10 years". 325l(9): "There shall be no curvature risk own funds requirements for
inflation and cross currency basis risks."

**325ae(1) Table 3** (M12) -- currencies not in the most liquid sub-category:

| Bucket | Maturity | Risk Weight |
|---|---|---|
| 1 | 0,25 years | 1,7 % |
| 2 | 0,5 years | 1,7 % |
| 3 | 1 year | 1,6 % |
| 4 | 2 years | 1,3 % |
| 5 | 3 years | 1,2 % |
| 6 | 5 years | 1,1 % |
| 7 | 10 years | 1,1 % |
| 8 | 15 years | 1,1 % |
| 9 | 20 years | 1,1 % |
| 10 | 30 years | 1,1 % |

325ae(2) (M12): "a risk weight of 1,6 % to all sensitivities of inflation and to cross currency
basis risk factors."

325ae(3) as replaced by CRR3 point (170) (p.121): "The risk weights of risk factors based on the
currencies included in the most liquid currency sub-category as referred to in Article 325bd(7),
point (b), and the domestic currency of the institution shall be the following: (a) for risk-free
rate risk factors, the risk weights referred to in paragraph 1, Table 3, of this Article divided
by √2; (b) for inflation risk factor and cross currency basis risk factors, the risk weights
referred to in paragraph 2 of this Article divided by √2."
325bd(5a) (CRR3 point (181)): "Currencies of Member States participating in ERM II shall be
included in the most liquid currencies and domestic currency sub-category".
The list of most liquid currencies (325bd(7)(b) RTS) is **not** in the supplied texts -- TODO.

325af: (1) same maturity, different curves: ρ = 99,90 %; (2) same curve, different maturities:
`ρ = max( e^(−θ·|T_k − T_l| / min{T_k; T_l}) ; 40 % )`, θ = 3 %; (3) different curves and
maturities: (2) × 99,90 %; (4) GIRR vs inflation: 40 %; (5) cross-currency basis vs any GIRR
factor "including another cross-currency basis risk factor": 0 %.

325ag: (1) γ_bc = 50 %; (2) γ_bc = 80 % "to aggregate an interest rate risk factor based on a
currency as referred to in Article 325av(3) and an interest rate risk factor based on the euro".

---

## 4. CSR non-securitisation -- Articles 325m, 325ah-325aj

**325ah(1) Table 4** (M12; bucket 13 sector replaced by CRR3 point (171)(a)(i)):

| Bucket | Credit quality | Sector | Risk weight |
|---|---|---|---|
| 1 | All | Central government, including central banks, of Member States | 0,5 % |
| 2 | CQS 1 to 3 | Central government, incl. central banks, of a third country, MDBs and IOs referred to in Art 117(2) or 118 | 0,5 % |
| 3 | CQS 1 to 3 | Regional or local authority and public sector entities | 1,0 % |
| 4 | CQS 1 to 3 | Financial sector entities including credit institutions incorporated or established by a central government, a regional government or a local authority and promotional lenders | 5,0 % |
| 5 | CQS 1 to 3 | Basic materials, energy, industrials, agriculture, manufacturing, mining and quarrying | 3,0 % |
| 6 | CQS 1 to 3 | Consumer goods and services, transportation and storage, administrative and support service activities | 3,0 % |
| 7 | CQS 1 to 3 | Technology, telecommunications | 2,0 % |
| 8 | CQS 1 to 3 | Health care, utilities, professional and technical activities | 1,5 % |
| 9 | CQS 1 to 3 | Covered bonds issued by credit institutions established in Member States | 1,0 % |
| 10 | CQS 1 / CQS 2 to 3 | Covered bonds issued by credit institutions in third countries | 1,5 % / 2,5 % |
| 11 | CQS 4 to 6 and unrated | Central government ... of a third country, MDBs, IOs | 2 % |
| 12 | CQS 4 to 6 and unrated | Regional or local authority and PSEs | 4,0 % |
| 13 | CQS 4 to 6 and unrated | "Financial sector entities, including credit institutions incorporated or established by a central government, a regional government or a local authority, promotional lenders and covered bonds" (CRR3) | 12,0 % |
| 14 | CQS 4 to 6 and unrated | Basic materials, energy, industrials, ... | 7,0 % |
| 15 | CQS 4 to 6 and unrated | Consumer goods and services, ... | 8,5 % |
| 16 | CQS 4 to 6 and unrated | Technology, telecommunications | 5,5 % |
| 17 | CQS 4 to 6 and unrated | Health care, utilities, professional and technical activities | 5,0 % |
| 18 | Other sector | | 12,0 % |
| 19 | Listed credit indices with a majority of its individual constituents being investment grade | | 1,5 % |
| 20 | Listed credit indices with a majority of its individual constituents being non-investment grade or unrated | | 5 % |

325ah(1) second subparagraph (CRR3): "an exposure shall be assigned the credit quality category
corresponding to the credit quality category that it would be assigned under the standardised
approach for credit risk". 325ah(2): unassignable issuers -> bucket 18. 325ah(3) (CRR3 point
(171)(b)): "institutions may assign a risk exposure of an unrated covered bond to bucket 4 where
the institution that issued the covered bond has credit quality step 1 to 3."

**325ai(1)**: `ρ_kl = ρ_kl(name) · ρ_kl(tenor) · ρ_kl(basis)`; ρ(name) as replaced by CRR3 point
(172): "equal to 1 where the two names ... are identical; it shall be equal to 35 % where the two
names ... are in buckets 1 to 18 in Article 325ah(1), Table 4, otherwise it shall be equal to
80 %"; ρ(tenor): 1 / 65 %; ρ(basis): 1 / 99,90 %. **325ai(2)**: bucket 18:
`K_b(bucket 18) = Σ_k |WS_k|`.

**325aj**: `γ_bc = γ_bc(rating) · γ_bc(sector)`. γ(rating) as replaced by CRR3 point (173):
"(a) 1, where buckets b and c are buckets 1 to 17 and both buckets have the same credit quality
category (either credit quality step 1 to 3 or credit quality step 4 to 6); otherwise it shall be
equal to 50 %; ... bucket 1 shall be considered as belonging to the same credit quality category
as buckets that have credit quality step 1 to 3; (b) 1, where either bucket b or c is bucket 18;
(c) 1, where bucket b or c is bucket 19 and the other bucket has credit quality step 1 to 3;
otherwise ... 50 %; (d) 1, where bucket b or c is bucket 20 and the other bucket has credit
quality step 4 to 6; otherwise ... 50 %". γ(sector) = 1 for the same sector, else **Table 5**
(M12):

| Bucket | 1,2,11 | 3,12 | 4,13 | 5,14 | 6,15 | 7,16 | 8,17 | 9,10 | 18 | 19 | 20 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1, 2 and 11 | | 75 % | 10 % | 20 % | 25 % | 20 % | 15 % | 10 % | 0 % | 45 % | 45 % |
| 3 and 12 | | | 5 % | 15 % | 20 % | 15 % | 10 % | 10 % | 0 % | 45 % | 45 % |
| 4 and 13 | | | | 5 % | 15 % | 20 % | 5 % | 20 % | 0 % | 45 % | 45 % |
| 5 and 14 | | | | | 20 % | 25 % | 5 % | 5 % | 0 % | 45 % | 45 % |
| 6 and 15 | | | | | | 25 % | 5 % | 15 % | 0 % | 45 % | 45 % |
| 7 and 16 | | | | | | | 5 % | 20 % | 0 % | 45 % | 45 % |
| 8 and 17 | | | | | | | | 5 % | 0 % | 45 % | 45 % |
| 9 and 10 | | | | | | | | | 0 % | 45 % | 45 % |
| 18 | | | | | | | | | | 0 % | 0 % |
| 19 | | | | | | | | | | | 75 % |
| 20 | | | | | | | | | | | |

---

## 5. CSR securitisation -- Articles 325n, 325ak-325ao

**325ak Table 6** (ACTP; M12; CRR3 point (174) relabels the credit-quality rows "Credit quality
step 1 to 10" and "Credit quality step 11 to 17" and adds covered bonds to bucket 13):

| Bucket | Credit quality | Sector | RW |
|---|---|---|---|
| 1 | All | Central government incl. central banks of Member States | 4,0 % |
| 2 | CQS 1 to 10 | Third-country central government, MDBs, IOs | 4,0 % |
| 3 | | Regional or local authority and PSEs | 4,0 % |
| 4 | | Financial sector entities ... promotional lenders | 8,0 % |
| 5 | | Basic materials, energy, industrials, ... | 5,0 % |
| 6 | | Consumer goods and services, ... | 4,0 % |
| 7 | | Technology, telecommunications | 3,0 % |
| 8 | | Health care, utilities, professional and technical activities | 2,0 % |
| 9 | | Covered bonds issued by credit institutions established in Member States | 3,0 % |
| 10 | | Covered bonds issued by credit institutions in third countries | 6,0 % |
| 11 | CQS 11 to 17 and unrated | Third-country central government, MDBs, IOs | 13,0 % |
| 12 | | Regional or local authority and PSEs | 13,0 % |
| 13 | | Financial sector entities ... promotional lenders and covered bonds | 16,0 % |
| 14 | | Basic materials, ... | 10,0 % |
| 15 | | Consumer goods and services, ... | 12,0 % |
| 16 | | Technology, telecommunications | 12,0 % |
| 17 | | Health care, utilities, ... | 12,0 % |
| 18 | Other sector | | 13,0 % |

325ak (CRR3 point (174)(b)): SA credit-quality category; unrated covered bond to bucket 4 where
the issuer has CQS 1 to 3. **325al**: ρ as 325ai "except that ... ρ_kl(basis) shall be equal to 1
... otherwise ... 99,00 %"; γ as 325aj.

**325am(1) Table 7** (non-ACTP; M12; credit-quality labels replaced by CRR3 point (175)(a)):

| Bucket | Credit quality | Sector | RW |
|---|---|---|---|
| 1 | Senior and CQS 1 to 10 | RMBS -- Prime | 0,9 % |
| 2 | | RMBS -- Mid-Prime | 1,5 % |
| 3 | | RMBS -- Sub-Prime | 2,0 % |
| 4 | | CMBS | 2,0 % |
| 5 | | ABS -- Student loans | 0,8 % |
| 6 | | ABS -- Credit cards | 1,2 % |
| 7 | | ABS -- Auto | 1,2 % |
| 8 | | CLO non-ACTP | 1,4 % |
| 9 | Non-senior and CQS 1 to 10 | RMBS -- Prime | 1,125 % |
| 10 | | RMBS -- Mid-Prime | 1,875 % |
| 11 | | RMBS -- Sub-Prime | 2,5 % |
| 12 | | CMBS | 2,5 % |
| 13 | | ABS -- Student loans | 1 % |
| 14 | | ABS -- Credit cards | 1,5 % |
| 15 | | ABS -- Auto | 1,5 % |
| 16 | | CLO non-ACTP | 1,75 % |
| 17 | CQS 11 to 17 and unrated | RMBS -- Prime | 1,575 % |
| 18 | | RMBS -- Mid-Prime | 2,625 % |
| 19 | | RMBS -- Sub-Prime | 3,5 % |
| 20 | | CMBS | 3,5 % |
| 21 | | ABS -- Student loans | 1,4 % |
| 22 | | ABS -- Credit cards | 2,1 % |
| 23 | | ABS -- Auto | 2,1 % |
| 24 | | CLO non-ACTP | 2,45 % |
| 25 | Other sector | | 3,5 % |

325am(3) (CRR3): credit quality category "under the External Ratings Based Approach".
**325an(1)**: `ρ_kl = ρ_kl(tranche) · ρ_kl(tenor) · ρ_kl(basis)`: tranche 1 "where the two names
... are related to the same securitisation tranche (more than 80 % overlap in notional terms)",
otherwise 40 %; tenor 1 / 80 %; basis 1 / 99,90 %. 325an(2): `K_b(bucket 25) = Σ_k |WS_k|`.
**325ao**: (1) γ_bc = 0 %; (2) "The own funds requirement for bucket 25 shall be added to the
overall risk class level capital, with no diversification or hedging effects recognised with any
other bucket."

---

## 6. Equity -- Articles 325o, 325ap-325ar

**325ap(1) Table 8** (M12):

| Bucket | Market cap | Economy | Sector | RW spot | RW repo |
|---|---|---|---|---|---|
| 1 | Large | Emerging | Consumer goods and services, transportation and storage, administrative and support service activities, healthcare, utilities | 55 % | 0,55 % |
| 2 | Large | Emerging | Telecommunications, industrials | 60 % | 0,60 % |
| 3 | Large | Emerging | Basic materials, energy, agriculture, manufacturing, mining and quarrying | 45 % | 0,45 % |
| 4 | Large | Emerging | Financials including government-backed financials, real estate activities, technology | 55 % | 0,55 % |
| 5 | Large | Advanced | (as bucket 1) | 30 % | 0,30 % |
| 6 | Large | Advanced | (as bucket 2) | 35 % | 0,35 % |
| 7 | Large | Advanced | (as bucket 3) | 40 % | 0,40 % |
| 8 | Large | Advanced | (as bucket 4) | 50 % | 0,50 % |
| 9 | Small | Emerging | All sectors described under bucket numbers 1, 2, 3 and 4 | 70 % | 0,70 % |
| 10 | Small | Advanced | All sectors described under bucket numbers 5, 6, 7 and 8 | 50 % | 0,50 % |
| 11 | Other sector | | | 70 % | 0,70 % |
| 12 | Large market cap, advanced economy indices | | | 15 % | 0,15 % |
| 13 | Other indices | | | 25 % | 0,25 % |

325ap(2)-(3): small/large market cap, emerging/advanced economy -- RTS (not supplied).
325ap(4): unassignable -> bucket 11.

**325aq** (M12): (1) spot vs repo of the same issuer: 99,90 %; (2) spot/spot within a bucket:
(a) 15 % buckets 1-4; (b) 25 % buckets 5-8; (c) 7,5 % bucket 9; (d) 12,5 % bucket 10; (e) 80 %
index buckets 12 or 13; (3) repo/repo "in accordance with points (a) to (d) of paragraph 2"; (4)
spot vs repo, different issuers: paragraph-2 correlation × 99,90 %; (5) bucket 11:
`K_b(bucket 11) = Σ_k |WS_k|`.

**325ar** (M12): (a) 15 % where both buckets are within 1 to 10; (b) 0 % where either is 11;
(c) 75 % between 12 and 13; (d) 45 % otherwise.
325o(3)-(4): no vega and no curvature requirement for equity repo rates.

---

## 7. Commodity -- Articles 325p, 325as-325au

**325as Table 9** (bucket 3 renamed and 3a/3b inserted by CRR3 point (176)):

| Bucket | Name | RW |
|---|---|---|
| 1 | Energy -- solid combustibles | 30 % |
| 2 | Energy -- liquid combustibles | 35 % |
| 3 | Energy -- electricity | 60 % |
| 3a | Energy -- EU ETS carbon trading | 40 % |
| 3b | Energy -- non-EU ETS carbon trading | 60 % |
| 4 | Freight | 80 % |
| 5 | Metals -- non-precious | 40 % |
| 6 | Gaseous combustibles | 45 % |
| 7 | Precious metals (including gold) | 20 % |
| 8 | Grains and oilseed | 35 % |
| 9 | Livestock and dairy | 25 % |
| 10 | Softs and other agricultural commodities | 35 % |
| 11 | Other commodities | 50 % |

**325at(2)**: `ρ_kl = ρ_kl(commodity) · ρ_kl(tenor) · ρ_kl(basis)`; tenor 1 / 99 %; basis
(delivery location) 1 / 99,90 %. **Table 10** ρ(commodity) (not amended by CRR3):

| Bucket | Name | ρ(commodity) |
|---|---|---|
| 1 | Energy - solid combustibles | 55 % |
| 2 | Energy - liquid combustibles | 95 % |
| 3 | Energy - electricity and carbon trading | 40 % |
| 4 | Freight | 80 % |
| 5 | Metals -- non-precious | 60 % |
| 6 | Gaseous combustibles | 65 % |
| 7 | Precious metals (including gold) | 55 % |
| 8 | Grains and oilseed | 45 % |
| 9 | Livestock and dairy | 15 % |
| 10 | Softs and other agricultural commodities | 40 % |
| 11 | Other commodity | 15 % |

**325au**: (a) 20 % where both buckets fall within 1 to 10; (b) 0 % where either is bucket 11.

---

## 8. FX -- Articles 325q, 325av, 325aw

325q(1) (M12): one bucket per currency pair with the reporting (or base, 325q(7)) currency.
**325av**: (1) (M12) 15 %; (2) EUR / ERM II currency pairs: "(a) the risk weight referred to in
paragraph 1, divided by 3; (b) the maximum fluctuation within the fluctuation band formally agreed
... if that fluctuation band is narrower"; (3) narrower-band currencies: the maximum percentage
fluctuation; (4) most liquid currency pairs (325bd(7)(c)): "divided by √2"; (5) constant
EUR / Member-State pair with zero bid/ask, with express permission: "divided by 2".
**325aw**: "A uniform correlation parameter γ_bc equal to 60 %".

---

## 9. Vega and curvature -- Articles 325ax, 325ay

**325ax(2) Table 1** as replaced by CRR3 point (177)(a) (paragraph 3 deleted):

| Risk class | Risk weights |
|---|---|
| GIRR | 100 % |
| CSR non-securitisations | 100 % |
| CSR securitisations (ACTP) | 100 % |
| CSR securitisations (non-ACTP) | 100 % |
| Equity (large cap and indices) | 77,78 % |
| Equity (small cap and other sector) | 100 % |
| Commodity | 100 % |
| Foreign exchange | 100 % |

(Former 325ax(3) M12 for reference: `RW_k = (value of risk factor k) · min(RW_σ · sqrt(LH_risk class)/sqrt(10); 100 %)`,
RW_σ = 55 %, Table 11 LH: GIRR 60; CSR (all) 120; equity large cap/indices 20; equity small
cap/other 60; commodity 120; FX 40.)

325ax(5): FX and equity curvature RW = relative shift equal to the delta RW. 325ax(6) as replaced
by CRR3 point (177)(c): "For general interest rate, credit spread and commodity curvature risk
factors, the curvature risk weight shall be the parallel shift of all vertices for each curve on
the basis of the highest prescribed delta risk weight ... for the relevant risk bucket."

**325ay**: (1) GIRR vega `ρ_kl = min{ρ_kl^(option maturity) · ρ_kl^(underlying maturity); 1}`,
`ρ^(option maturity) = e^(−α·|T_k − T_l| / min{T_k; T_l})`, α = 1 %;
`ρ^(underlying maturity) = e^(−α·|TU_k − TU_l| / min{TU_k; TU_l})`, TU = underlying maturity minus
option maturity; (2) other classes `ρ_kl = min{ρ_kl^(DELTA) · ρ_kl^(option maturity); 1}`;
(3) γ_bc as for delta; (4) delta and vega summed (no diversification); (5) "The curvature risk
correlations shall be the square of corresponding delta risk correlations ρ_kl and γ_bc".

---

## 10. Default risk charge -- Articles 325v-325ad

**325w(1)**: `JTD_long = max{LGD · V_notional + P&L_long + Adjustment_long; 0}`;
**325w(2)**: `JTD_short = min{LGD · V_notional + P&L_short + Adjustment_short; 0}`, V_notional
entering with a negative sign. **325w(3)**: non-senior debt 100 %; senior debt 75 %; covered bonds
(Art 129) 25 %. **325w(5)-(6)**: equity, notional = fair value of cash equity, LGD 100 %.
325v(3) (CRR3 point (165)): look-through for traded non-securitisation credit and equity
derivatives (moved from deleted 325ab(2), CRR3 point (168)).

**325x**: (1) offsetting "only ... between exposures to the same obligor where the short exposures
have the same seniority as, or lower seniority than, the long exposures"; (2) "(a) offsetting
shall be full where all offsetting exposures have maturities of one year or more; (b) ... partial
where at least one of the offsetting exposures has a maturity of less than one year, in which case
the size of the JTD amount of each exposure with a maturity of less than one year shall be
multiplied by the ratio of the exposure's maturity relative to one year"; (3) no offsetting:
"multiplied by the ratio of the exposure's maturity relative to one year, with a floor of three
months"; (4) derivative maturity; "Cash equity exposures shall be assigned a maturity of either
one year or three months, at the institution's discretion"; (5) (CRR3 point (166)) derivative
hedged with its cash underlying, both legs closable at the first-to-mature expiry: net JTD of the
combined position = 0.

**325y(1) Table 2**:

| Credit quality category | Default risk weight |
|---|---|
| Credit quality step 1 | 0,5 % |
| Credit quality step 2 | 3 % |
| Credit quality step 3 | 6 % |
| Credit quality step 4 | 15 % |
| Credit quality step 5 | 30 % |
| Credit quality step 6 | 50 % |
| Unrated | 15 % |
| Defaulted | 100 % |

325y(2): 0 % SA RW -> 0 % default RW. 325y(3): buckets "corporates, sovereigns, and local
governments/municipalities". 325y(6) (CRR3): SA credit-quality category.
**325y(4)**: `DRC_b = max{(Σ_{i∈long} RW_i · netJTD_i) − WtS · (Σ_{i∈short} RW_i · |netJTD_i|); 0}`,
`WtS = Σ netJTD_long / (Σ netJTD_long + Σ |netJTD_short|)`. 325y(5): simple sum of buckets.

**Securitisation non-ACTP** -- 325z(1): gross JTD = market value (or fair value); (2) offsetting
only "with the same underlying asset pool and belonging to the same tranche"; (5) 325x applies,
maturities of the tranches. **325aa**: (1) "multiplied by 8 % of the risk weight that applies to
the relevant securitisation exposure, including STS securitisations, in the non-trading book";
(2) one-year maturity for SEC-IRBA / SEC-ERBA; (3) risk-weighted JTD of cash securitisations
capped at fair value; (4) buckets: one common corporate bucket + 44 = 11 asset classes (ABCP,
auto loans/leases, RMBS, credit cards, CMBS, CLO, CDO-squared, SMEs, student loans, other retail,
other wholesale) × 4 regions (Asia, Europe, North America, rest of the world); (5) unassignable
-> other retail / other wholesale / rest of the world; (6) 325y(4) formula; (7) simple sum.

**ACTP** -- 325ac(2): gross JTD = market value; (3) Nth-to-default attachment `(N − 1)/Total
Names`, detachment `N/Total Names`; (4) offsetting only between exposures "otherwise identical
except for maturity". **325ad(1)** as replaced by CRR3 point (169)(a): "(a) for non-tranched
products, the default risk weights corresponding to their credit quality as specified in
Article 325y(1) and (2); (b) for tranched products, the default risk weights referred to in
Article 325aa(1)." (2) buckets per index. **325ad(3)** as replaced by CRR3 point (169)(b) (p.121):
`DRC_b = Σ_{i∈long} RW_i · netJTD_i − WtS_ACTP · (Σ_{i∈short} RW_i · |netJTD_i|)` (no zero floor),
WtS_ACTP using long and short positions across the entire ACTP. **325ad(4)** (C7, cons. p.457):
`DRC_ACTP = max{ Σ_b (max{DRC_b, 0} + 0,5 · min{DRC_b, 0}); 0 }`.

---

## 11. Residual risk add-on -- Article 325u

(2)(a) exotic underlying; (2)(b) other residual risks: (i) non-replicable pay-offs subject to vega
and curvature; (ii) ACTP positions (ACTP hedges under 325(8) excluded). (3) "the sum of gross
notional amounts ... multiplied by ... (a) 1,0 % ... (b) 0,1 %". (4) not applied to an instrument
(a) listed on a recognised exchange; (b) eligible for central clearing (Regulation (EU)
No 648/2012); (c) perfectly offsetting another trading-book position (both exempt). (4a) (CRR3)
"until 31 December 2032, an institution shall not apply the own funds requirement for residual
risks to instruments that aim solely to hedge the market risk of positions in the trading book
that generate an own funds requirement for residual risks and are subject to the same type of
residual risks as the positions they hedge" (with permission).

---

## 12. Alternative internal model approach -- Articles 325ba-325bp

**325ba(1)**: `max{ES_{t−1} + SS_{t−1}; m_c · ES_avg + SS_avg}` (60-business-day averages);
(2) default-risk requirement: max(most recent, 12-week average). **325ba(3)** (CRR3 point
(179)(c), p.125):
`AIMA_total = min(AIMA + PLA_addon + ASA_non-aima; ASA_all portfolio) + max(AIMA − ASA_aima; 0)`.

**325bb(1)**: `ES_t = ρ · UES_t + (1 − ρ) · Σ_i UES_t^i`, ρ = 50 %;
`UES_t = PES_t^RS · max{PES_t^FC / PES_t^RC; 1}` (and per broad category i).

**325bc(1)**: daily; "(b) at 97,5th percentile, one tailed confidence interval"; (c) (C7, cons.
p.477): `PES_t = sqrt( (PES_t(T))² + Σ_{j≥2} ( PES_t(T, j) · sqrt((LH_j − LH_{j−1})/10) )² )`,
T = 10 days. **Table 1**: liquidity horizons 1-5 = 10, 20, 40, 60, 120 days. 325bc(2)(a):
`(1/60) Σ_{k=0}^{59} PES_{t−k}^RC / PES_{t−k}^FC ≥ 75 %`; (2)(c) stress period from at least
1 January 2007.

**325bd(1) Table 2** (liquidity horizons, days): Interest rate -- most liquid currencies and
domestic currency 10; other currencies 20; volatility 60; other types 60. Credit spread -- central
government of Member States 20; covered bonds of Member-State credit institutions (IG) 20;
sovereign (IG) 20; sovereign (HY) 40; corporate (IG) 40; corporate (HY) 60; volatility 120; other
types 120. Equity -- price large cap 10; price small cap 20; volatility large cap 20; volatility
small cap 60; other types 60. Foreign exchange -- most liquid currency pairs 10; other pairs 20;
volatility 40; other types 40. Commodity -- energy and carbon emissions price 20; precious and
non-ferrous metal price 20; other commodity prices 60; energy and carbon emissions volatility 60;
precious and non-ferrous metal volatility 60; other commodity volatilities 120; other types 120.
325bd(4): `EffectiveLH = SubCatLH if Mat > LH5; min(SubCatLH, min_j{LH_j / LH_j ≥ Mat}) if
LH1 ≤ Mat ≤ LH5; LH1 if Mat < LH1`. 325bd(5): EUR / ERM II pairs in most liquid pairs.

**325bf**: (3) desk back-testing limits over 250 business days: 12 overshootings at 99 % (hypo
and actual), 30 at 97,5 % (hypo and actual); (6) as amended by CRR3 point (183): "m_c shall be
equal to at least the sum of 1,5 and an add-on determined in accordance with Table 3".
**Table 3**: fewer than 5 -> 0,00; 5 -> 0,20; 6 -> 0,26; 7 -> 0,33; 8 -> 0,38; 9 -> 0,42; more
than 9 -> 0,50.

**325bg** (CRR3 point (184)): P&L attribution "close" / "sufficiently close"; criteria and the
PLA add-on by EBA RTS (not supplied). **325bk(3)**: SES scenarios and aggregation by RTS (not
supplied).

**Internal default risk model** -- 325bn(1): VaR "at the 99,9 % confidence interval over a
one-year time horizon"; 10-year correlation data; weekly (325bn(2)); 60-day horizon option for
equities (325bn(3)). 325bp(5)(a) as replaced by CRR3 point (188): PD "floored at 0,01 % for
exposures to which a 0 % risk weight is applied in accordance with Articles 114 to 118 and at
0,01 % for covered bonds to which a 10 % risk weight is applied in accordance with Article 129;
otherwise ... 0,03 %"; 325bp(6)(a): LGD floored at 0 %.

---

## 13. Simplified standardised approach -- Articles 326-361 (as amended by CRR3)

**336(1) Table 1** (specific risk, non-securitisation debt):

| Category | Specific risk OFR |
|---|---|
| Debt securities which would receive a 0 % SA risk weight | 0 % |
| 20 % or 50 % SA risk weight and other qualifying items (336(4)) | 0,25 % (residual term ≤ 6 months); 1,00 % (> 6 months and ≤ 24 months); 1,60 % (> 24 months) |
| 100 % SA risk weight | 8,00 % |
| 150 % SA risk weight | 12,00 % |

336(3): 10 %-RW covered bonds (Art 129(4)-(6)) -- "half of the applicable specific risk own funds
requirement for the second category in Table 1".
**337(1)**: securitisation -- "8 % of the risk weight the institution would apply to the position
in its non-trading book"; 337(2) as replaced by CRR3 point (190)(a): exclusively Title II
Chapter 5 Section 3; 337(4): long and short weighted positions summed. **338(2)** as replaced by
CRR3 point (191): CTP -- larger of the requirement on net long positions and on net short
positions.

**339(4) Table 2** (maturity-based general risk):

| Zone | Coupon ≥ 3 % | Coupon < 3 % | Weighting (%) | Assumed rate change (%) |
|---|---|---|---|---|
| One | 0 ≤ 1 month | 0 ≤ 1 month | 0,00 | -- |
| | > 1 ≤ 3 months | > 1 ≤ 3 months | 0,20 | 1,00 |
| | > 3 ≤ 6 months | > 3 ≤ 6 months | 0,40 | 1,00 |
| | > 6 ≤ 12 months | > 6 ≤ 12 months | 0,70 | 1,00 |
| Two | > 1 ≤ 2 years | > 1,0 ≤ 1,9 years | 1,25 | 0,90 |
| | > 2 ≤ 3 years | > 1,9 ≤ 2,8 years | 1,75 | 0,80 |
| | > 3 ≤ 4 years | > 2,8 ≤ 3,6 years | 2,25 | 0,75 |
| Three | > 4 ≤ 5 years | > 3,6 ≤ 4,3 years | 2,75 | 0,75 |
| | > 5 ≤ 7 years | > 4,3 ≤ 5,7 years | 3,25 | 0,70 |
| | > 7 ≤ 10 years | > 5,7 ≤ 7,3 years | 3,75 | 0,65 |
| | > 10 ≤ 15 years | > 7,3 ≤ 9,3 years | 4,50 | 0,60 |
| | > 15 ≤ 20 years | > 9,3 ≤ 10,6 years | 5,25 | 0,60 |
| | > 20 years | > 10,6 ≤ 12,0 years | 6,00 | 0,60 |
| | | > 12,0 ≤ 20,0 years | 8,00 | 0,60 |
| | | > 20 years | 12,50 | 0,60 |

339(9): "(a) 10 % of the sum of the matched weighted positions in all maturity bands; (b) 40 % of
the matched weighted position in zone one; (c) 30 % ... zone two; (d) 30 % ... zone three; (e)
40 % of the matched weighted position between zones one and two and between zones two and three;
(f) 150 % of the matched weighted position between zones one and three; (g) 100 % of the residual
unmatched weighted positions." 339(5)-(8): zone 1 vs 2, then 2 vs 3, then 1 vs 3.

**340** (duration-based): `modified duration = D / (1 + R)`,
`D = Σ_t t·C_t/(1+R)^t / Σ_t C_t/(1+R)^t`; **Table 3**: zone one (> 0 ≤ 1,0 years) 1,0 %; zone
two (> 1,0 ≤ 3,6) 0,85 %; zone three (> 3,6) 0,7 %; 340(7): "(a) 2 % of the matched
duration-weighted position for each zone; (b) 40 % ... between zones one and two and between zones
two and three; (c) 150 % ... between zones one and three; (d) 100 % of the residual unmatched".

**341-343**: overall gross position × 8 % (specific); overall net position (per market) × 8 %
(general). **345 Table 4** (underwriting): working day 0: 100 %; 1: 90 %; 2 to 3: 75 %; 4: 50 %;
5: 25 %; after working day 5: 0 %. **348(1)** as replaced by CRR3 point (192): CIUs 32 %
(position risk); 40 % (position and FX risk).

**351** as replaced by CRR3 point (193): "If the sum of an institution's overall net foreign
exchange position and its net gold position ... exceeds 2 % of its total own funds, the
institution shall calculate an own funds requirement for foreign exchange risk. The own funds
requirement for foreign exchange risk shall be the sum of its overall net foreign exchange
position and its net gold position in the reporting currency, multiplied by 8 %." **352(4)**: the
higher of total net short and total net long positions. 352(2) deleted by CRR3 point (194).
354(1): closely correlated currencies 4 %; 354(4): ERM II matched positions 1,6 %.

**359(1) Table 1** (commodity maturity ladder): bands 0 ≤ 1 month, > 1 ≤ 3 months, > 3 ≤ 6
months, > 6 ≤ 12 months, > 1 ≤ 2 years, > 2 ≤ 3 years, > 3 years -- spread rate 1,50 % in each;
359(5): "(a) the sum of the matched long and short positions, multiplied by the appropriate spread
rate ... and by the spot price; (b) the matched position between two maturity bands for each
maturity band into which an unmatched position is carried forward, multiplied by 0,6 %, which is
the carry rate ...; (c) the residual unmatched positions, multiplied by 15 % which is the outright
rate". **360(1)**: "(a) 15 % of the net position, long or short ...; (b) 3 % of the gross
position, long plus short". **361 Table 2** (extended maturity ladder; 361(c) deleted by CRR3
point (195)):

| | Precious metals (except gold) | Base metals | Agricultural products (softs) | Other, including energy products |
|---|---|---|---|---|
| Spread rate (%) | 1,0 | 1,2 | 1,5 | 1,5 |
| Carry rate (%) | 0,3 | 0,5 | 0,6 | 0,6 |
| Outright rate (%) | 8 | 10 | 12 | 15 |

Part Three Title IV Chapter 5 (Articles 362-377, internal models of the pre-FRTB regime) is deleted
by CRR3 point (196).
