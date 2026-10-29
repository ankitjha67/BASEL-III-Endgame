# UK PRA -- Pillar 1 Reference: Securitisation, SA-CVA, Leverage Exposure, Large Exposures, CCPs

**Sources (authority):** PRA Rulebook, CRR Firms, web text "as at 01/01/2027":

| Part | Provisions used | Code |
|---|---|---|
| Securitisation (CRR) | Arts 243-270F | `src/jurisdictions/uk/pillar1/securitisation.py` |
| Credit Valuation Adjustment Risk | Chapter 5, rules 5.14-5.30 (PS1/26 Appendix 1, PRA2026/1, p. 408-422) | `sa_cva.py` |
| Leverage Ratio (CRR) | Arts 429-429g | `leverage.py` |
| Large Exposures (CRR) | rule 1.2, Arts 390-403, Chapter 5 | `large_exposures.py` |
| Counterparty Credit Risk (CRR) | Arts 300-311 (CCPs); Arts 274-280f (SA-CCR, see UK_parameter_reference.md) | `ccp.py` |
| Credit Risk: General Provisions (CRR) | Art 107(2) (PS1/26 Appendix 1) | `ccp.py` |

Text in quotation marks is copied from the source. Where a formula is printed as an image on the
Rulebook page (no text or alt text in the HTML), the identical formula is taken from the CRR
article the Rulebook note says the rule "corresponds to" (Regulation (EU) No 575/2013,
consolidated 09.07.2024) and both are cited. GBP amounts are carried in GBP millions.

**Not sourced** (implemented with BCBS structure and `TODO: VERIFY`): the Non-Performing Exposures
Securitisation (CRR) Part (Art 269A cross-reference; not supplied) and the Leverage Ratio -
Capital Requirements and Buffers Part (leverage minimum and buffers; not supplied).

---

## 1. Securitisation (CRR) Part

### Art 254 -- hierarchy of methods
> "(a) where the conditions set out in Article 258 are met, an institution shall use the SEC-IRBA
> in accordance with Articles 259 and 260; (b) where the SEC-IRBA may not be used, an institution
> shall use the SEC-SA in accordance with Articles 261 and 262; (c) where the SEC-SA may not be
> used, an institution shall use the SEC-ERBA in accordance with Articles 263 and 264 for rated
> positions or positions in respect of which an inferred rating may be used."

254(2): "an institution shall use the SEC-ERBA instead of the SEC-SA in each of the following cases:
(a) where the application of the SEC-SA would result in a risk weight higher than 25% for positions
qualifying as positions in an STS securitisation; (b) where the application of the SEC-SA would
result in a risk weight higher than 25% or the application of the SEC-ERBA would result in a risk
weight higher than 75% for positions not qualifying as positions in an STS securitisation; (c) for
securitisation transactions backed by pools of auto loans, auto leases and equipment leases."
(254(3) adds a notification regime for "a decision ... to apply the SEC-ERBA instead of the SEC-SA
to all its rated securitisation positions"; the code applies 254(2) literally.)

254(4): SEC-SA not applied where the PRA has prohibited it. 254(5): IAA for unrated ABCP positions
with 138BA permission. 254(6): "For a position in a resecuritisation, institutions shall apply the
SEC-SA in accordance with Article 261, with the modifications set out in Article 269." 254(7): "In
all other cases, a risk weight of 1250% shall be assigned to securitisation positions."

### Art 255 -- K_IRB and K_SA
K_IRB = IRB RWEA of the underlying (including EL and UL, 255(3)) × 8% / exposure value (255(2)).
K_SA = SA RWEA × 8% / value of the underlying (255(6)). 255(10): a non-originator may replace
underlying SA risk weights by 100% (non-defaulted, non-real-estate retail / unrated corporate /
unrated SME), 100% (RRE not materially dependent), 150% (anything other than securitisation,
subordinated debt, own funds / equity, CIU) or 1250%.

### Art 256 -- A and D
A = max(0, (pool − tranches senior or pari passu incl. the position) / pool); D = max(0, (pool −
tranches senior to the position) / pool). Overcollateralisation and funded reserve accounts are
tranches (256(3)).

### Art 257 -- tranche maturity M_T
(a) (Σ_t t·CF_t) / Σ_t CF_t; or (b) M_T = 1 + (M_L − 1) × 80%. 257(2): "a floor of one year and a
cap of five years".

### Art 258 -- SEC-IRBA conditions
IRB pool, or mixed pool with K_IRB on "a minimum of 95% of the underlying exposure amount";
sufficient information; not precluded by the PRA.

### Art 259 -- SEC-IRBA ("in all cases subject to a floor of 15%")
| Condition | RW |
|---|---|
| D ≤ K_POOL | 1250% |
| D > A ≥ K_POOL | 12.5 × K_SSFA(K_POOL) |
| A < K_POOL < D | [12.5 × (K_POOL − A)/(D − A)] + [12.5 × K_SSFA(K_POOL) × (D − K_POOL)/(D − A)] |
| K_POOL < A = D | 12.5 × e^(a·u) |

K_SSFA(K_POOL) = (e^(a·u) − e^(a·l)) / (a(u − l)); a = −1/(p × K_POOL); u = D − K_POOL;
l = max(A − K_POOL, 0).

p = max[0.3, (A + B × (1/N) + C × K_IRB + D × LGD + E × M_T)]

| | | A | B | C | D | E |
|---|---|---|---|---|---|---|
| Non-retail | Senior, granular (N ≥ 25) | 0 | 3.56 | -1.85 | 0.55 | 0.07 |
| | Senior, non-granular (N < 25) | 0.11 | 2.61 | -2.91 | 0.68 | 0.07 |
| | Non-senior, granular (N ≥ 25) | 0.16 | 2.87 | -1.03 | 0.21 | 0.07 |
| | Non-senior, non-granular (N < 25) | 0.22 | 2.35 | -2.46 | 0.48 | 0.07 |
| Retail | Senior | 0 | 0 | -7.48 | 0.71 | 0.24 |
| | Non-senior | 0 | 0 | -5.78 | 0.55 | 0.27 |

N = (Σ EAD_i)² / Σ EAD_i² (259(4)); LGD = Σ LGD_i·EAD_i / Σ EAD_i (259(5)); simplified where
C_1 ≤ 3%: N = (C_1·C_m + (C_m − C_1)/(m − 1) · max{1 − m·C_1, 0})⁻¹, LGD = 0.50, or N = 1/C_1
(259(6)). 259(7): mixed pool K_POOL = d × K_IRB + (1 − d) × K_A; IRB pool K_POOL = K_IRB.

### Art 260 -- STS under SEC-IRBA
"risk-weight floor for senior securitisation positions = 10%";
p = max[0.3, 0.5 × (A + B × (1/N) + C × K_IRB + D × LGD + E × M_T)].

### Art 260A -- qualifying securitisation (single RRE, synthetic) under SEC-IRBA
RW = IRB Art 154 RW of the underlying + 12.5 × Art 158 EL (as if not securitised). Not modelled
(requires IRB inputs outside the contract).

### Art 261 -- SEC-SA ("in all cases subject to a floor of 15%")
Same piecewise function and K_SSFA as Art 259 with K_A in place of K_POOL.
> "For the value of p, an institution may for each securitisation either apply a value of 1 or
> calculate p in accordance with the following formula:
> p = min[1, max[0.5, (A + B × (1/N) + C × K_A + D × LGD + E × M_T)]]"

with the same (A, B, C, D, E) table and the LGD table of 261(1)(a):

| Exposure type | LGD |
|---|---|
| Regulatory residential real estate exposures with LTV at most 100% | 20% |
| Other exposures secured on immovable property with LTV at most 100% | 30% |
| Senior purchased corporate receivables | 50% |
| Other senior exposures to non-financial corporates | 40% |
| Other senior non-retail exposures | 45% |
| Subordinated purchased corporate receivables | 100% |
| Other subordinated non-retail exposures | 75% |
| Other exposures | 100% |

261(1A): mixed retail / non-retail pools -- separate p per subpool, nominal-weighted average.
261(2): "K A = (1 − W) * K SAE + W * 0.5" or "K A = (1 − W) * K SA + W * 0.5"; W = defaulted
nominal / total nominal (90 days past due, bankruptcy, foreclosure, or default per documentation).
Delinquency unknown for ≤ 5%: K_A = (EAD_known × K_known + EAD_unknown) / EAD_total; "more than
5% ... must be risk-weighted at 1250%".

### Art 262 -- STS under SEC-SA
"risk-weight floor for senior securitisation positions = 10%"; p = 0.5 or
p = min[0.5, max[0.3, 0.5 × (A + B × (1/N) + C × K_A + D × LGD + E × M_T)]].

### Art 262A -- qualifying securitisation under SEC-SA
20% when A ≥ X; 75% when D ≤ X; 20% × (D − X)/(D − A) + 75% × (X − A)/(D − A) when D > X > A;
X = 1 − (0.55 × property value / exposure value).

### Art 263 -- SEC-ERBA
Table 1 (short-term): CQS 1 15%, 2 50%, 3 100%, all other 1250%.

Table 2 (long-term; senior / non-senior (thin); M_T 1 year / 5 years):

| CQS | Sen 1y | Sen 5y | Non-sen 1y | Non-sen 5y |
|---|---|---|---|---|
| 1 | 15% | 20% | 15% | 70% |
| 2 | 15% | 30% | 15% | 90% |
| 3 | 25% | 40% | 30% | 120% |
| 4 | 30% | 45% | 40% | 140% |
| 5 | 40% | 50% | 60% | 160% |
| 6 | 50% | 65% | 80% | 180% |
| 7 | 60% | 70% | 120% | 210% |
| 8 | 75% | 90% | 170% | 260% |
| 9 | 90% | 105% | 220% | 310% |
| 10 | 120% | 140% | 330% | 420% |
| 11 | 140% | 160% | 470% | 580% |
| 12 | 160% | 180% | 620% | 760% |
| 13 | 200% | 225% | 750% | 860% |
| 14 | 250% | 280% | 900% | 950% |
| 15 | 310% | 340% | 1050% | 1050% |
| 16 | 380% | 420% | 1130% | 1130% |
| 17 | 460% | 505% | 1250% | 1250% |
| All other | 1250% | 1250% | 1250% | 1250% |

263(4): linear interpolation between 1 and 5 years. 263(5): non-senior
RW = [RW after maturity adjustment] × [1 − min(T, 50%)], T = D − A. 263(6): non-senior "floor of
15%" and "no lower than the risk weight corresponding to a hypothetical senior tranche of the same
securitisation with the same credit assessment and maturity". 263(7): inferred ratings.

### Art 264 -- STS under SEC-ERBA
Table 3 (short-term): CQS 1 10%, 2 30%, 3 60%, all other 1250%.

Table 4 (long-term):

| CQS | Sen 1y | Sen 5y | Non-sen 1y | Non-sen 5y |
|---|---|---|---|---|
| 1 | 10% | 10% | 15% | 40% |
| 2 | 10% | 15% | 15% | 55% |
| 3 | 15% | 20% | 15% | 70% |
| 4 | 15% | 25% | 25% | 80% |
| 5 | 20% | 30% | 35% | 95% |
| 6 | 30% | 40% | 60% | 135% |
| 7 | 35% | 45% | 95% | 170% |
| 8 | 45% | 55% | 150% | 225% |
| 9 | 55% | 65% | 180% | 255% |
| 10 | 70% | 85% | 270% | 345% |
| 11 | 120% | 135% | 405% | 500% |
| 12 | 135% | 155% | 535% | 655% |
| 13 | 170% | 195% | 645% | 740% |
| 14 | 225% | 250% | 810% | 855% |
| 15 | 280% | 305% | 945% | 945% |
| 16 | 340% | 380% | 1015% | 1015% |
| 17 | 415% | 455% | 1250% | 1250% |
| All other | 1250% | 1250% | 1250% | 1250% |

### Arts 265-266 -- Internal Assessment Approach
Only with 138BA permission (265(1)); the internal grade gives "a derived rating which shall be the
same as the credit assessments corresponding to that rating grade" (266(1)), which must be
"investment grade or better at the time it was first assigned" and is used under Art 263 / 264
(266(2)).

### Art 267 -- senior look-through cap
Senior position: maximum RW = exposure-weighted average RW of the underlying as if not securitised
(SA, or IRB RW + 12.5 × EL / EV, 267(3)); for mixed pools under SEC-SA/ERBA the SA average
(267(2)(b)). 267(4): "Where the maximum risk weight ... results in a lower risk weight than the
risk-weight floors set out in Articles 259 to 264, as applicable, the former shall be used instead."
Code: cap = 12.5 × K_IRB (SEC-IRBA) or 12.5 × K_SA (other approaches), from the pool capital.

### Art 268 -- maximum capital requirement
"Max capital requirement = U * Y + Σ_i max(0, V_i − U) * Z_i"; U ∈ [0, 1] set by the
institution; Y = capital of the underlying as if not securitised (IRB incl. EL); Z_i = capital of
tranche i; V_i = share held of tranche i. Available to originators / sponsors (any approach) and
SEC-IRBA users (268(1)). Stand-alone helper (the contract is per tranche).

### Art 269 -- resecuritisations
"(a) W = 0 for any exposure to a securitisation tranche within the pool of underlying exposures;
(b) p = 1.5; (c) the resulting risk weight shall be subject to a risk-weight floor of 100%."
269(3): Articles 267-268 caps not applied.

### Art 269A -- NPE securitisations (NOT SOURCED)
"The risk weight for a position in an NPE securitisation calculated in accordance with this Part is
subject to the requirements laid down in the Non-Performing Exposures Securitisation (CRR) Part."
That Part was not supplied. Placeholder (TODO: VERIFY) = BCBS CRE45.4 ("floored at 100%") and
CRE45.5 (100% for the senior tranche of a traditional NPL securitisation with NRPPD ≥ 50%).

### Art 270 -- senior positions in SME securitisations
Originator may apply Arts 260 / 262 / 264 to the senior position where (among others) the
originator, sponsor and SSPE are UK-established, ≥ 70% of the pool are SMEs, and risk is
transferred to the UK government, Bank of England, an MDB / IO / promotional entity at 0%, or a
fully cash-collateralised institutional investor.

### Art 252 -- synthetic maturity mismatch
RW* = RW_SP × [(t − t*)/(T − t*)] + RW_Ass × [(T − t)/(T − t*)], t* = 0.25; T capped at five
years (252(1)(a)).

### Art 248 -- exposure value
Off-balance sheet conversion factor 100%, "except in the case of cash advance facilities" -- 10%
for an unconditionally cancellable liquidity facility whose draws rank senior (248(1)(b)).

### Art 270F -- ECAI mapping (S&P Global Ratings UK row; Fitch / Moody's equivalent)
CQS 1 AAA, 2 AA+, 3 AA, 4 AA-, 5 A+, 6 A, 7 A-, 8 BBB+, 9 BBB, 10 BBB-, 11 BB+, 12 BB, 13 BB-,
14 B+, 15 B, 16 B-, 17 CCC+/CCC/CCC-, All other below. Moody's: Aaa, Aa1-Aa3, A1-A3, Baa1-Baa3,
Ba1-Ba3, B1-B3, Caa1-Caa3 (17). Short-term: A-1+/A-1 → 1, A-2 → 2, A-3 → 3 (P-1/P-2/P-3;
F1+/F1, F2, F3), below → all other.

### SRT thresholds (Arts 244-245, recorded only)
Mezzanine RWEA held ≤ 50%; first-loss held ≤ 20%; clean-up call when ≤ 10% remains.

---

## 2. Credit Valuation Adjustment Risk Part -- SA-CVA (Chapter 5)

Rule 5.22: WS_k^CVA = RW_k s_k^CVA; WS_k^Hdg = RW_k s_k^Hdg. Rule 5.23: WS_k = WS_k^CVA − WS_k^Hdg.

Rule 5.24(1) (rendered from the PDF, p. 410 -- the R term is inside the square root):

K_b = √( (Σ_{k∈b} WS_k² + Σ_{k∈b} Σ_{l∈b,l≠k} ρ_kl WS_k WS_l) + R · Σ_{k∈b} (WS_k^Hdg)² ),
"R= the hedging disallowance parameter set at 0.01".

Rule 5.24(2): K = m_CVA √(Σ_b K_b² + Σ_b Σ_{c≠b} γ_bc S_b S_c), "mCVA= multiplier factor equal to
1"; S_b = max{−K_b; min(Σ_{k∈b} WS_k; K_b)}.

Rules 5.15 / 5.17: delta for six risk classes (IR, FX, counterparty credit spread, reference credit
spread, equity, commodity); vega for five (no counterparty credit spread).

### Rule 5.25 -- interest rate
Buckets = currencies; γ_bc = 0.5. USD, EUR, GBP, AUD, CAD, SEK, JPY: tenors 1, 2, 5, 10, 30 years
plus inflation.

| Risk factor | 1 year | 2 years | 5 years | 10 years | 30 years | Inflation |
|---|---|---|---|---|---|---|
| Risk weight | 1.11% | 0.93% | 0.74% | 0.74% | 0.74% | 1.11% |

| | 1 year | 2 years | 5 years | 10 years | 30 years | Inflation |
|---|---|---|---|---|---|---|
| 1 year | 100% | 91% | 72% | 55% | 31% | 40% |
| 2 years | | 100% | 87% | 72% | 45% | 40% |
| 5 years | | | 100% | 91% | 68% | 40% |
| 10 years | | | | 100% | 83% | 40% |
| 30 years | | | | | 100% | 40% |
| Inflation | | | | | | 100% |

Other currencies: parallel shift + inflation, RW 1.58% both, correlation 40%. Vega: IR and
inflation volatilities, RW 100%, correlation 40%.

### Rule 5.26 -- foreign exchange
Buckets = currencies other than the reporting currency; γ_bc = 0.6; delta RW 11%; vega RW 100%.

### Rule 5.27 -- counterparty credit spread (delta only)
| Bucket | Sector |
|---|---|
| 1 | (a) Sovereigns including central banks, multilateral development banks; (b) Local government, government-backed non-financials, education and public administration |
| 2 | (a) Financials including government-backed financials, excluding pension funds; (b) Pension funds |
| 3 | Basic materials, energy, industrials agriculture, manufacturing, mining and quarrying |
| 4 | Consumer goods and services, transportation and storage, administrative and support services activities |
| 5 | Technology, telecommunications |
| 6 | Health care, utilities, professional and technical activities |
| 7 | Other sector |
| 8 | Qualified Indices |

γ_bc:

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

Tenors 0.5, 1, 3, 5, 10 years. Risk weights:

| Bucket | 1 a) | 1 b) | 2 a) | 2 b) | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|---|
| Investment grade names | 0.5% | 1.0% | 5.0% | 3.5% | 3.0% | 3.0% | 2.0% | 1.5% | 5.0% | 1.5% |
| High yield and not rated names | 2.0% | 4.0% | 12.0% | 8.5% | 7.0% | 8.5% | 5.5% | 5.0% | 12.0% | 5.0% |

ρ_kl = ρ_tenor · ρ_name · ρ_quality: ρ_tenor 100% same tenor / 90%; ρ_name 100% same / 90%
"distinct, but legally related" / 50%; ρ_quality 100% same / 80%. Bucket 8: ρ_name 100% same index
and series / 90% same index, distinct series / 80% otherwise.

### Rule 5.28 -- reference credit spread
Buckets 1-7 investment grade (sovereigns; local government; financials; basic materials ...;
consumer goods ...; technology ...; health care ...), 8-14 the same sectors high yield and not
rated, 15 other sector, 16 IG qualified index, 17 HY qualified index.

γ_bc between buckets of the same credit quality (p. 417):

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

(b) "between buckets 1 to 14 of different credit quality, by dividing the correlations in the table
at point (a) of 5.28(2) by 2".

Delta risk weights by bucket: 1 0.5%, 2 1.0%, 3 5.0%, 4 3.0%, 5 3.0%, 6 2.0%, 7 1.5%, 8 2.0%,
9 4.0%, 10 12.0%, 11 7.0%, 12 8.5%, 13 5.5%, 14 5.0%, 15 12.0%, 16 1.5%, 17 5.0%. (The PDF prints
buckets 1-9 under an "Investment grade bucket" heading and 10-17 under "High yield/Not rated";
values are transcribed by bucket number.) Vega RW 100%.

### Rule 5.29 -- equity
| Bucket | Size | Region | Sector |
|---|---|---|---|
| 1 | Large | Emerging | Consumer goods and services, transportation and storage, administrative and support service activities, healthcare, utilities |
| 2 | Large | Emerging | Telecommunications, industrials |
| 3 | Large | Emerging | Basic materials, energy, agriculture, manufacturing, mining and quarrying |
| 4 | Large | Emerging | Financials including government-backed financials, real estate activities, technology |
| 5-8 | Large | Advanced | as 1-4 |
| 9 | Small | Emerging | All sectors of buckets 1-4 |
| 10 | Small | Advanced | All sectors of buckets 5-8 |
| 11 | -- | -- | Other sector |
| 12 | Large capitalisation, advanced economies | | Qualified index |
| 13 | Other | | Qualified index |

"large market capitalisation= a market capitalisation equal to or greater than GBP 1.6 billion";
advanced economies: "the UK, Canada, the United States, Mexico, the euro area, Norway, Sweden,
Denmark, Switzerland, Japan, Australia, New Zealand, Singapore and Hong Kong SAR".
γ_bc: 15% within 1-10; 75% between 12 and 13; 45% between 12/13 and 1-10; 0% with 11.

| Bucket | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RW | 55% | 60% | 45% | 55% | 30% | 35% | 40% | 50% | 70% | 50% | 70% | 15% | 25% |

Vega: "78% for large market capitalisation buckets and at 100% for the other buckets" (buckets 1-8
and 12 treated as large cap).

### Rule 5.30 -- commodity
Buckets: 1 energy - solid combustibles; 2 energy - liquid combustibles; 3 energy - electricity and
carbon trading; 4 freight; 5 metals - non-precious; 6 gaseous combustibles; 7 precious metals
(including gold); 8 grains & oilseed; 9 livestock & dairy; 10 softs and other agriculturals;
11 other commodity. γ_bc: 20% within 1-10; 0% with 11.

| Bucket | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| RW | 30% | 35% | 60% | 80% | 40% | 45% | 20% | 35% | 25% | 35% | 50% |

Vega RW 100%.

---

## 3. Leverage Ratio (CRR) Part

Art 429(2)-(3): leverage ratio = tier 1 capital (leverage) / total exposure measure. 429(4): sum of
(a) assets (Art 429b(1)); (b) derivatives (Arts 429c-429d); (c) SFT add-ons (Art 429e);
(d) off-balance-sheet items (Art 429f); (e) regular-way purchases / sales (Art 429g). 429(7): no
CRM to reduce the measure; no netting of assets and liabilities.

Art 429a(A1): "a central bank claim of a firm shall be netted off against a liability, provided
that" same currency, maturity no later than the liability, omnibus-account conditions (A2).
429a(1): exclusions incl. (a)-(b) Tier 1 deductions; (c) Art 113(6) 0% intragroup with permission;
(g) clearing member QCCP trade exposures meeting Art 306(1)(c); (h) higher-level client trade
exposures; (i) fiduciary assets; (j) PSE pass-through deposits (permission); (k) tri-party excess
collateral not lent; (l) cash VM receivable; (m) SRT securitised exposures; (q) Bounce Back Loans.

Art 429c(1): derivatives under "the standardised approach for counterparty credit risk".
429c(3): only cash VM meeting (a)-(e) reduces RC. 429c(4): "institutions shall not include
collateral received in the calculation of the net independent collateral amount" (except
client QCCP-cleared). 429c(5): "set the value of the multiplier used in the calculation of the
potential future exposure ... to one". 429c(6)(b): SDDTs "Exposure value = α ∙max{CMV,0}",
α = 1.4. CCR Part Art 274(2B): the alpha add-on transitional does not apply to the leverage ratio
(Art 274(2) alpha, including α = 1 for NFCs and pension schemes, does).

Art 429d: written credit derivatives -- effective notional less negative fair value changes in
Tier 1; offset by purchased protection meeting 429d(3)(a)-(e).

Art 429e(2): per transaction add-on E*_i = max{0, E_i − C_i}; 429e(3): per master netting agreement
E*_i = max{0, Σ E_i − Σ C_i} (images on the Rulebook page; formula from CRR Art 429e(2)-(3)).
429e(5): Art 222 alternative "subject to a 20% floor for the applicable risk weight".

Art 429f(1): off-balance-sheet items per Art 111(1) CCFs; 429f(3): "a conversion factor of 10% to
low-risk off-balance-sheet items referred to in point (d) of Article 111(1)".

**Leverage minimum and buffers: NOT SOURCED** (Leverage Ratio - Capital Requirements and Buffers
Part not supplied). The exposure-measure calculation does not need them.

---

## 4. Large Exposures (CRR) Part

Rule 1.2 'large exposure': "a firm's exposure to a client or group of connected clients where the
value of the exposure is equal to or exceeds 10% of its Tier 1 capital".

Art 394(1): report each large exposure (including exempted); the 20 largest (IRB firms); and
"exposures of a value greater than or equal to GBP 260 million but less than 10% of the firm's Tier
1 capital on a consolidated basis".

Art 395(1): "the value of which exceeds 25% of its Tier 1 capital" (after CRM, Arts 399-403).
Relevant exposures to Article 119 institutions: "25% of the firm's Tier 1 capital or GBP 130
million, whichever is higher", provided the non-institution connected clients are within 25%;
where GBP 130 million is higher than 25%, a firm-set reasonable limit that "must not exceed 100% of
the firm's Tier 1 capital". "a G-SII must not incur an exposure to another G-SII or to a non-UK
G-SII, the value of which ... exceeds 15% of its Tier 1 capital", within 12 months of
identification.

Art 395(5): trading-book excess permitted where the non-trading book is within the limit, the
additional requirement of Art 397 is met, within 10 days the trading-book exposure ≤ 500% of Tier 1,
and persistent excesses in aggregate ≤ 600%.

Art 397(2): 200% where the excess has not persisted more than 10 days. Art 397(3) Table 1:

| Excess over the limits (% of Tier 1) | Factor |
|---|---|
| Up to 40% | 200% |
| From 40% to 60% | 300% |
| From 60% to 80% | 400% |
| From 80% to 100% | 500% |
| From 100% to 250% | 600% |
| Over 250% | 900% |

Art 400(1) exemptions (a)-(j), (l): 0% RW sovereigns / central banks / PSEs, IOs / MDBs, explicit
0% guarantees, other exposures attributable to 0% entities, 0% UK RGLAs, Art 113(6)/(7) 0%
counterparties, cash-deposit and own-CD collateral, low-risk undrawn facilities, clearing members'
QCCP trade exposures and default fund contributions, clients' Art 305(2)/(3) trade exposures.
Art 400(2) with permission: (c) intragroup, (g) required minimum reserves, (h) statutory liquidity
holdings of IG sovereign securities. 400(4): no more than one exemption per exposure.

Art 390(6): FX settlement (two business days), securities settlement (five business days),
money-transmission and intraday institution exposures excluded. Chapter 5 Art 6: transactions with
underlying assets -- separate client below 0.25% of Tier 1, else the unknown client.

---

## 5. Counterparty Credit Risk (CRR) Part -- exposures to CCPs

Credit Risk: General Provisions (CRR) Part Art 107(2): trade exposures and default fund
contributions per CCR Part Section 9; other exposures "(a) as exposures to an institution ... to a
qualifying CCP; (b) as exposures to a corporate ... to a non-qualifying CCP".

Art 303(2): "the sum of an institution's own funds requirements for its exposures to a QCCP due to
trade exposures and default fund contributions shall be subject to a cap equal to the sum of own
funds requirements that would be applied to those same exposures if the CCP were a non-qualifying
CCP".

Art 304(3)-(5): clearing member MPOR ≥ 5 business days to clients, ≥ 10 to the CCP; maturity
factor 0.21 for client exposures under the simplified SA-CCR / OEM.

Art 305(2): client may apply Art 306 where positions are segregated and bankruptcy remote,
portability is facilitated, legal review is done and "the CCP is a QCCP". 305(3): "replacing the 2%
risk weight set out in point (a) of Article 306(1) with a 4% risk weight" where only joint-default
protection is missing.

Art 306(1): "(a) it shall apply a risk weight of 2% to the exposure values of all its trade
exposures with QCCPs; (b) it shall apply the risk weight used for the Standardised Approach to
credit risk as set out in Article 107(2)(b) to all its trade exposures with non-qualifying CCPs";
(c) intermediary not required to reimburse the client on CCP default -> exposure value zero.
306(2): bankruptcy-remote posted collateral -> exposure value zero.

Art 308(2) (image on the Rulebook page; transcribed from CRR Art 308(2)):
K_i = max{K_CCP · DF_i / (DF_CCP + DF_CM); 8% · 2% · DF_i}; 308(3): RWEA = K_i × 12.5.

Art 309(1): "K = DF + UC"; 309(2): RWEA = K × 12.5. Art 310: "a 0% risk weight to its unfunded
contributions to the default fund of a QCCP". Art 301(1): 0% for default fund contributions covering
only cash transactions. Art 311(2): within three months of becoming aware that a CCP will cease to
comply, apply Art 306(1)(b), Art 309, and corporate treatment for other exposures.
