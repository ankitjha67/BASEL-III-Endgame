# EU CRR3 -- Pillar 1 reference: securitisation, SA-CVA, leverage, large exposures, CCPs

Verbatim transcription of every table and formula implemented in `src/jurisdictions/eu/pillar1/`.

**Sources**

| Short name | Text | Used for |
|---|---|---|
| CRR3 | Regulation (EU) 2024/1623, OJ L 19.6.2024 (189 pp.) -- "p." = OJ page | SA-CVA (Arts 382a-383z, points (199)-(201)); LE amendments (points (203)-(206)); leverage amendments (points (209)-(213)); Art. 465(13) |
| CRR cons. | Regulation (EU) No 575/2013, consolidated 09.07.2024 -- "cons. p." = page of the PDF | Securitisation Arts 242-270a; CCP Arts 300-311; LE Arts 387-403; leverage Arts 429-429g |
| BCBS | Basel Framework (consolidated) | comparisons only |

Formulas printed as images were read from rendered PDF pages: cons. pp.318-319 (Art. 259),
331-332 (Art. 269a(5)-(6)); CRR3 OJ pp.137-138 (Art. 383b(5)-(8)), p.147 (Art. 383q).

CRR3 did **not** amend the securitisation chapter (only the RW* definition in Art. 252(b), point
(145)) or the CCP section (Arts 300-311). Its point (155) replaces Part Three Title III (operational
risk), not the CCP rules.

---

## 1. Securitisation (CRR cons. Arts 242-270a)

### Art. 254 -- hierarchy of methods (cons. pp.312-314)

> 1. Institutions shall use one of the methods set out in Subsection 3 ... in accordance with the following
> hierarchy: (a) where the conditions set out in Article 258 are met, an institution shall use the SEC-IRBA
> in accordance with Articles 259 and 260; (b) where the SEC-IRBA may not be used, an institution shall use
> the SEC-SA in accordance with Articles 261 and 262; (c) where the SEC-SA may not be used, an institution
> shall use the SEC-ERBA in accordance with Articles 263 and 264 for rated positions or positions in respect
> of which an inferred rating may be used.
>
> 2. For rated positions or positions in respect of which an inferred rating may be used, an institution
> shall use the SEC-ERBA instead of the SEC-SA in each of the following cases: (a) where the application of
> the SEC-SA would result in a risk weight higher than **25 %** for positions qualifying as positions in an
> STS securitisation; (b) where the application of the SEC-SA would result in a risk weight higher than
> **25 %** or the application of the SEC-ERBA would result in a risk weight higher than **75 %** for positions
> not qualifying as positions in an STS securitisation; (c) for securitisation transactions backed by pools
> of auto loans, auto leases and equipment leases.
>
> 3. ... an institution may decide to apply the SEC-ERBA instead of the SEC-SA to all of its rated
> securitisation positions ...
>
> 4. ... competent authorities may prohibit institutions, on a case by case basis, from applying the SEC-SA ...
>
> 5. ... an institution may apply the Internal Assessment Approach ... in relation to an unrated position in
> an ABCP programme or ABCP transaction in accordance with Article 266, provided that the conditions set out
> in Article 265 are met. ...
>
> 6. For a position in a re-securitisation, institutions shall apply the SEC-SA in accordance with Article
> 261, with the modifications set out in Article 269.
>
> 7. In all other cases, a risk weight of **1 250 %** shall be assigned to securitisation positions.

### Art. 255 -- K_IRB and K_SA (cons. pp.314-315)

> 2. ... K_IRB by multiplying the risk-weighted exposure amounts that would be calculated under Chapter 3
> ... as if they had not been securitised by **8 %** divided by the exposure value of the underlying
> exposures. ... 3. ... shall include: (a) the amount of expected losses ... (b) the amount of unexpected
> losses ...
>
> 6. ... K_SA by multiplying the risk-weighted exposure amounts that would be calculated under Chapter 2 ...
> by **8 %** divided by the value of the underlying exposures. ... without netting any specific credit risk
> adjustments and additional value adjustments ...

Engine consequence: the pool's exposure-weighted average RW (Art. 267(1)-(3), including EL x 12,5 for IRB
pools) equals 12,5 x K.

### Art. 256 -- A and D (cons. p.316); Art. 257 -- M_T (cons. p.317)

> 257(1)(a) M_T = Σ_t t·CF_t / Σ_t CF_t ; (b) **M_T = 1 + (M_L − 1) · 80 %**
>
> 2. ... subject in all cases to a floor of **1 year** and a cap of **5 years**.

### Art. 258 -- SEC-IRBA conditions (cons. pp.317-318)

> 1(a) the position is backed by an IRB pool or a mixed pool, provided that, in the latter case, the
> institution is able to calculate K_IRB ... on a minimum of **95 %** of the underlying exposure amount; ...

### Art. 259 -- SEC-IRBA (cons. pp.318-320; formulas rendered from the PDF)

> 1. ... in all cases subject to a floor of **15 %**:
>
> RW = 1 250 % when D ≤ K_IRB
> RW = 12,5 · K_SSFA(K_IRB) when A ≥ K_IRB
> RW = [((K_IRB − A)/(D − A)) · 12,5] + [((D − K_IRB)/(D − A)) · 12,5 · K_SSFA(K_IRB)] when A < K_IRB < D
>
> K_SSFA(K_IRB) = (e^{a·u} − e^{a·l}) / (a(u − l)); a = −(1/(p · K_IRB)); u = D − K_IRB; l = max(A − K_IRB; 0)
>
> p = max[0,3; (A + B·(1/N) + C·K_IRB + D·LGD + E·M_T)]

Look-up table (cons. p.319):

| | | A | B | C | D | E |
|---|---|---|---|---|---|---|
| Non-retail | Senior, granular (N ≥ 25) | 0 | 3,56 | −1,85 | 0,55 | 0,07 |
| Non-retail | Senior, non-granular (N < 25) | 0,11 | 2,61 | −2,91 | 0,68 | 0,07 |
| Non-retail | Non-senior, granular (N ≥ 25) | 0,16 | 2,87 | −1,03 | 0,21 | 0,07 |
| Non-retail | Non-senior, non-granular (N < 25) | 0,22 | 2,35 | −2,46 | 0,48 | 0,07 |
| Retail | Senior | 0 | 0 | −7,48 | 0,71 | 0,24 |
| Retail | Non-senior | 0 | 0 | −5,78 | 0,55 | 0,27 |

> 4. N = (Σ_i EAD_i)² / Σ_i EAD_i² ; 5. LGD = Σ_i LGD_i·EAD_i / Σ_i EAD_i
>
> 6. Where ... C1 is no more than **3 %** ... N = (C1·Cm + ((Cm − C1)/(m − 1))·max{1 − m·C1; 0})^−1,
> LGD = **0,50** ... If only C1 is available ... LGD as 0,50 and N as 1/C1.
>
> 7. [mixed pool] d · K_IRB + (1 − d) · K_SA

### Art. 260 -- STS under SEC-IRBA (cons. p.321)

> risk-weight floor for senior securitisation positions = **10 %**
> p = max[0,3; **0,5** · (A + B·(1/N) + C·K_IRB + D·LGD + E·M_T)]

### Art. 261 -- SEC-SA (cons. pp.321-322)

> 1. ... in all cases subject to a floor of **15 %**: [same three-branch formula with K_A] ...
> p = **1** for a securitisation exposure that is not a re-securitisation exposure
>
> 2. **K_A = (1 − W) · K_SA + W · 0,5** ... W = ratio of (a) the sum of the nominal amount of underlying
> exposures in default, to (b) the sum of the nominal amount of all underlying exposures. ... Where an
> institution does not know the delinquency status for **5 %** or less of underlying exposures ...
> K_A = (EAD_Subpool1 where W known / EAD_Total) × K_A^Subpool1 where W known + EAD_Subpool2 where W unknown / EAD_Total.
> Where the institution does not know the delinquency status for more than 5 % ... risk-weighted at **1 250 %**.

### Art. 262 -- STS under SEC-SA (cons. p.322)

> risk-weight floor for senior securitisation positions = **10 %**; p = **0,5**

### Art. 263 -- SEC-ERBA (cons. pp.322-324)

Table 1 (short-term):

| CQS | 1 | 2 | 3 | All other ratings |
|---|---|---|---|---|
| RW | 15 % | 50 % | 100 % | 1 250 % |

Table 2 (long-term):

| CQS | Senior 1y | Senior 5y | Non-senior 1y | Non-senior 5y |
|---|---|---|---|---|
| 1 | 15 % | 20 % | 15 % | 70 % |
| 2 | 15 % | 30 % | 15 % | 90 % |
| 3 | 25 % | 40 % | 30 % | 120 % |
| 4 | 30 % | 45 % | 40 % | 140 % |
| 5 | 40 % | 50 % | 60 % | 160 % |
| 6 | 50 % | 65 % | 80 % | 180 % |
| 7 | 60 % | 70 % | 120 % | 210 % |
| 8 | 75 % | 90 % | 170 % | 260 % |
| 9 | 90 % | 105 % | 220 % | 310 % |
| 10 | 120 % | 140 % | 330 % | 420 % |
| 11 | 140 % | 160 % | 470 % | 580 % |
| 12 | 160 % | 180 % | 620 % | 760 % |
| 13 | 200 % | 225 % | 750 % | 860 % |
| 14 | 250 % | 280 % | 900 % | 950 % |
| 15 | 310 % | 340 % | 1 050 % | 1 050 % |
| 16 | 380 % | 420 % | 1 130 % | 1 130 % |
| 17 | 460 % | 505 % | 1 250 % | 1 250 % |
| All other | 1 250 % | 1 250 % | 1 250 % | 1 250 % |

> 4. ... linear interpolation between the risk weights applicable for 1 and 5 years maturity ...
>
> 5. **RW = [RW after adjusting for maturity according to paragraph 4] · [1 − min(T; 50 %)]**, T = D − A
>
> 6. The risk weights for non-senior tranches ... shall be subject to a floor of **15 %**. In addition, the
> resulting risk weights shall be no lower than the risk weight corresponding to a hypothetical senior tranche
> of the same securitisation with the same credit assessment and maturity.
>
> 7. [inferred ratings: pari passu or immediately subordinate reference position, no additional credit
> enhancement, maturity ≥, updated on an ongoing basis]

### Art. 264 -- STS under SEC-ERBA (cons. pp.324-325)

Table 3 (short-term): CQS 1 **10 %**, 2 **30 %**, 3 **60 %**, all other 1 250 %.

Table 4 (long-term):

| CQS | Senior 1y | Senior 5y | Non-senior 1y | Non-senior 5y |
|---|---|---|---|---|
| 1 | 10 % | 10 % | 15 % | 40 % |
| 2 | 10 % | 15 % | 15 % | 55 % |
| 3 | 15 % | 20 % | 15 % | 70 % |
| 4 | 15 % | 25 % | 25 % | 80 % |
| 5 | 20 % | 30 % | 35 % | 95 % |
| 6 | 30 % | 40 % | 60 % | 135 % |
| 7 | 35 % | 40 % | 95 % | 170 % |
| 8 | 45 % | 55 % | 150 % | 225 % |
| 9 | 55 % | 65 % | 180 % | 255 % |
| 10 | 70 % | 85 % | 270 % | 345 % |
| 11 | 120 % | 135 % | 405 % | 500 % |
| 12 | 135 % | 155 % | 535 % | 655 % |
| 13 | 170 % | 195 % | 645 % | 740 % |
| 14 | 225 % | 250 % | 810 % | 855 % |
| 15 | 280 % | 305 % | 945 % | 945 % |
| 16 | 340 % | 380 % | 1 015 % | 1 015 % |
| 17 | 415 % | 455 % | 1 250 % | 1 250 % |
| All other | 1 250 % | 1 250 % | 1 250 % | 1 250 % |

**Notch -> CQS mapping.** Not in the sources (Commission Implementing Regulation (EU) 2016/1801).
**TODO: VERIFY.** The engine maps AAA→1, AA+→2, AA→3, AA-→4, A+→5, A→6, A-→7, BBB+→8, BBB→9, BBB-→10,
BB+→11, BB→12, BB-→13, B+→14, B→15, B-→16, CCC+/CCC/CCC-→17 (the row order of the BCBS SEC-ERBA table,
which Tables 2 and 4 reproduce row for row), and A-1/P-1→1, A-2/P-2→2, A-3/P-3→3 for short-term.
`CQS<n>` inputs bypass the mapping.

### Arts 265-266 -- IAA (cons. pp.325-328)

> 266(1) ... the institution shall assign the unrated position ... to one of the rating grades ... The
> position shall be attributed a derived rating ... 2. The rating derived ... shall be at least at the level
> of investment grade or better at the time it was first assigned and shall be regarded as an eligible credit
> assessment ... for the purposes of calculating risk-weighted exposure amounts in accordance with Article 263
> or Article 264, as applicable.

### Art. 243 -- STS criteria for differentiated capital treatment (cons. pp.298-299)

> 1(a) [ABCP] ... a risk weight equal to or smaller than **75 %** on an individual exposure basis where the
> exposure is a retail exposure or **100 %** for any other exposures; (b) ... single obligor ... does not
> exceed **2 %** ...
>
> 2(a) [non-ABCP] ... single obligor ... does not exceed **2 %** ...; (b) ... (i) **40 %** on an exposure
> value-weighted average basis ... residential mortgages ...; (ii) **50 %** ... commercial mortgage; (iii)
> **75 %** ... retail exposure; (iv) ... **100 %** ...; (d) ... no loan ... with a loan-to-value ratio higher
> than **100 %** ...

### Art. 267 -- senior look-through (cons. pp.328-329)

> 1. An institution which has knowledge at all times of the composition of the underlying exposures may
> assign the senior securitisation position a maximum risk weight equal to the exposure-weighted-average risk
> weight that would be applicable to the underlying exposures as if the underlying exposures had not been
> securitised. ... 2(b) where the institution applies the SEC-SA or the SEC-ERBA, the maximum risk weight
> ... shall be equal to the Standardised Approach weighted-average risk weight ... 3. ... shall include the
> ratio of (a) expected losses multiplied by **12,5** to (b) the exposure value ... 4. Where the maximum risk
> weight ... results in a lower risk weight than the risk-weight floors set out in Articles 259 to 264, ...
> the former shall be used instead.

### Art. 268 -- maximum capital requirements (cons. pp.329-330)

> 1. An originator institution, a sponsor institution or other institution using the SEC-IRBA or an
> originator institution or sponsor institution using the SEC-SA or the SEC-ERBA may apply a maximum capital
> requirement ... equal to the capital requirements that would be calculated under Chapter 2 or 3 in respect
> of the underlying exposures had they not been securitised. ... 3. ... multiplying ... by the largest
> proportion of interest that the institution holds in the relevant tranches (V) ... (a) ... V shall be equal
> to the ratio of the nominal amount of the securitisation positions that the institution holds in that given
> tranche to the nominal amount of the tranche; ...

Engine: for a holding in a single tranche, cap on RWEA = 12,5 · K · pool · V = 12,5 · K · exposure / (D − A),
i.e. a risk-weight cap of **12,5 · K / (D − A)**.

### Art. 269 -- re-securitisations (cons. p.330)

> 1. ... (a) W = **0** for any exposure to a securitisation tranche within the pool ...; (b) p = **1,5**;
> (c) the resulting risk weight shall be subject to a risk-weight floor of **100 %**. ...
> 3. The maximum capital requirements set out in Subsection 4 shall not be applied to re-securitisation
> positions. 4. ... the K_A parameter shall be determined as the nominal exposure weighted-average of the K_A
> calculated individually for each subset of exposures.

### Art. 269a -- NPE securitisations (cons. pp.330-333; formulas rendered from pp.331-332)

> 1(b) 'qualifying traditional NPE securitisation' means a traditional NPE securitisation where the
> non-refundable purchase price discount is at least **50 %** ...
>
> 2. ... The risk weight shall be subject to a floor of **100 %**, except when Article 263 is applied.
>
> 3. ... a risk weight of **100 %** to the senior securitisation position in a qualifying traditional NPE
> securitisation, except when Article 263 is applied.
>
> 4. Institutions ... not permitted to use own estimates of LGD and conversion factors ... shall not use the
> SEC-IRBA ... for a position in an NPE securitisation ...
>
> 5. **CR_max = RWEA_IRB · 8 % + max[EL_IRB − NRPPD · EV_IRB/EV_Pool − SCRA_IRB; 0] + RWEA_SA · 8 %**
>
> 6. ... where the exposure-weighted average risk weight calculated in accordance with the look-through
> approach ... is lower than 100 %, institutions may apply the lower risk weight, subject to a **50 %**
> risk-weight floor. ...
> **RW_max = (RWEA_IRB + max[12,5 · (EL_IRB − NRPPD · EV_IRB/EV_Pool − SCRA_IRB); 0] + RWEA_SA) /
> (max[EV_IRB − NRPPD · EV_IRB/EV_Pool − SCRA_IRB; 0] + EV_SA)**
>
> 7. ... NRPPD ... subtracting (b) [initial sale price of tranches sold to third parties + outstanding amount of
> tranches held by the originator] from (a) [outstanding amount of the underlying exposures at transfer] ...
> adjusted downwards taking into account the realised losses ... subject to a floor of zero.

### Art. 270 -- senior positions in STS on-balance-sheet securitisations (cons. p.333)

> 1. An originator institution may calculate the risk-weighted exposure amounts of a securitisation position
> in an STS on-balance sheet securitisation ... in accordance with Article 260, 262 or 264 ... where (a) the
> securitisation meets the requirements set out in Article 243(2); (b) the position qualifies as the senior
> securitisation position.

### Art. 270a -- additional risk weight (cons. p.334)

> 1. ... a proportionate additional risk weight of no less than **250 %** of the risk weight, capped at
> **1 250 %** ...

Engine: RW · (1 + 2,5), capped at 1 250 % (the supervisory minimum).

### Art. 252 -- maturity mismatch in synthetic securitisations (cons. pp.311-312)

> (a) ... longest maturity ... subject to a maximum of **5 years** ...
> (b) RW* = RW_SP · [(t − t*)/(T − t*)] + RW_Ass · [(T − t)/(T − t*)], t* = **0,25**

### Art. 465(13) -- output floor p (CRR3 p.172)

> ... for exposures that are risk weighted using the SEC-IRBA or the Internal Assessment Approach ... where
> the part of [S-TREA] ... is calculated using the SEC-SA ..., institutions shall, until 31 December 2032,
> apply the following factor p: (a) p = **0,25** for a position ... to which Article 262 applies; (b) p =
> **0,5** for a position ... to which Article 261 applies.

---

## 2. SA-CVA (CRR3 Arts 382a-383z, OJ pp.131-154)

### Art. 383(3), 383b -- aggregation (formulas rendered from OJ pp.137-138)

> 383(3) ... own funds requirements for CVA risk using the standardised approach as the sum of ... (a) ...
> delta risk ...; (b) ... vega risk ...
>
> 383b(5) **WS_k^CVA = RW_k · S_k^CVA ; WS_k^hedges = RW_k · S_k^hedges**
>
> 383b(6) **WS_k = WS_k^CVA − WS_k^hedges**
>
> 383b(7) **K_b = sqrt( Σ_{k∈b} WS_k² + Σ_{k∈b} Σ_{l∈b, k≠l} ρ_kl WS_k WS_l + R · Σ_{k∈b} (WS_k^hedges)² )**,
> R = the hedging disallowance parameter equal to **0,01**.
>
> 383b(8) **risk-class specific own funds requirement for delta or vega risk = m_CVA · sqrt( Σ_b K_b² +
> Σ_b Σ_{c≠b} γ_bc S_b S_c )**; m_CVA = a multiplier factor which is equal to **1**; the competent authority
> may increase the value of m_CVA ...; **S_b = max{−K_b; min(Σ_{k∈b} WS_k; K_b)}**.

### Interest rate (Arts 383c, 383k-383m)

> 383c(1) ... one bucket per currency ... risk-free rates ... maturities: 1 year, 2 years, 5 years, 10 years
> and 30 years. ... inflation rates per currency ... 1 year, 2 years, 5 years, 10 years and 30 years.
> 383c(2) ... euro, Swedish krona, Australian dollar, Canadian dollar, British pound sterling, Japanese yen and
> US dollar, the institution's reporting currency and the currency of a Member State participating in ERM II.
> 383c(3) For currencies not specified ... the absolute change of the inflation rate and the parallel shift
> of the entire risk-free curve ...
> 383c(6) ... one net interest rate sensitivity and one net inflation rate sensitivity computed for each
> currency [vega].

383k Table 1: bucket 1 (1y) **1,11 %**; 2 (2y) **0,93 %**; 3 (5y) **0,74 %**; 4 (10y) **0,74 %**; 5 (30y) **0,74 %**.
383k(2) other currencies **1,58 %**; (3) inflation, specified currencies **1,11 %**; (4) other **1,58 %**;
(5) interest-rate and inflation vega **100 %**.

383l Table 1:

| | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| 1 | 100 % | 91 % | 72 % | 55 % | 31 % |
| 2 | | 100 % | 87 % | 72 % | 45 % |
| 3 | | | 100 % | 91 % | 68 % |
| 4 | | | | 100 % | 83 % |
| 5 | | | | | 100 % |

> 383l(2) ... **40 %** for the aggregation of inflation rate delta risk sensitivity and risk-free rate delta
> sensitivity denominated in the same currency. (3) ... **40 %** ... vega ...
> 383m The cross-bucket correlation parameter for interest rate delta and vega risks shall be set at **0,5**.

Inflation-to-inflation correlation across tenors: **not stated** in 383l. **TODO: VERIFY** -- the engine
applies the Table 1 tenor correlations.

### FX (Arts 383d, 383n, 383o)

> 383n(1) ... **11 %**. (2) ... euro and the currency of a Member State participating in ERM II ... (a) the
> risk weight referred to in paragraph 1, divided by **3**; (b) the maximum fluctuation within the [narrower]
> band ... (4) vega **100 %**. 383o: **60 %** delta and vega across buckets.

### Counterparty credit spread (Arts 383e, 383p-383r)

383p Table 1 (all tenors 0,5/1/3/5/10y):

| Bucket | Credit quality | Sector | RW |
|---|---|---|---|
| 1 | All | Central government incl. central banks of Member States | 0,5 % |
| 2 | CQS 1-3 | Third-country central government/central banks, MDBs and IOs (117(2), 118) | 0,5 % |
| 3 | CQS 1-3 | RGLA and PSEs | 1,0 % |
| 4 | CQS 1-3 | Financial sector entities (incl. government-established credit institutions, promotional lenders) | 5,0 % |
| 5 | CQS 1-3 | Basic materials, energy, industrials, agriculture, manufacturing, mining and quarrying | 3,0 % |
| 6 | CQS 1-3 | Consumer goods and services, transportation and storage, administrative and support | 3,0 % |
| 7 | CQS 1-3 | Technology, telecommunications | 2,0 % |
| 8 | CQS 1-3 | Health care, utilities, professional and technical | 1,5 % |
| 9 | CQS 1-3 | Covered bonds issued by credit institutions established in Member States | 1,0 % |
| 10 | CQS 1 / CQS 2-3 | Covered bonds issued by credit institutions in third countries | 1,5 % / 2,5 % |
| 11 | CQS 1-3 | Other sector | 5,0 % |
| 12 | CQS 1-3 | Qualified indices | 1,5 % |
| 13 | CQS 4-6, unrated | Third-country sovereigns, MDBs, IOs | 2,0 % |
| 14 | CQS 4-6, unrated | RGLA and PSEs | 4,0 % |
| 15 | CQS 4-6, unrated | Financial sector entities | 12,0 % |
| 16 | CQS 4-6, unrated | Basic materials ... | 7,0 % |
| 17 | CQS 4-6, unrated | Consumer goods ... | 8,5 % |
| 18 | CQS 4-6, unrated | Technology, telecommunications | 5,5 % |
| 19 | CQS 4-6, unrated | Health care ... | 5,0 % |
| 20 | CQS 4-6, unrated | Other sector | 12,0 % |
| 21 | CQS 4-6, unrated | Qualified indices | 5,0 % |

> 383q(1) [buckets 1-11, 13-20] **ρ_kl = ρ_kl^(tenor) · ρ_kl^(name) · ρ_kl^(quality)**; tenor: 1 if identical,
> otherwise **90 %**; name: 1 if identical, **90 %** if distinct but legally related, otherwise **50 %**;
> quality: 1 where both in buckets 1 to 11 or both in 13 to 20, otherwise **80 %**.
> 383q(2) [buckets 12, 21] tenor as above; name: 1 if identical and same series, **90 %** same index distinct
> series, otherwise **80 %**; quality: 1 where both in 12 or both in 21, otherwise **80 %**.

383r Table 1:

| | 1,2,3,13,14 | 4,15 | 5,16 | 6,17 | 7,18 | 8,19 | 9,10 | 11,20 | 12,21 |
|---|---|---|---|---|---|---|---|---|---|
| 1,2,3,13,14 | 100 % | 10 % | 20 % | 25 % | 20 % | 15 % | 10 % | 0 % | 45 % |
| 4,15 | | 100 % | 5 % | 15 % | 20 % | 5 % | 20 % | 0 % | 45 % |
| 5,16 | | | 100 % | 20 % | 25 % | 5 % | 5 % | 0 % | 45 % |
| 6,17 | | | | 100 % | 25 % | 5 % | 15 % | 0 % | 45 % |
| 7,18 | | | | | 100 % | 5 % | 20 % | 0 % | 45 % |
| 8,19 | | | | | | 100 % | 5 % | 0 % | 45 % |
| 9,10 | | | | | | | 100 % | 0 % | 45 % |
| 11,20 | | | | | | | | 100 % | 0 % |
| 12,21 | | | | | | | | | 100 % |

383e(2): no vega for counterparty credit spread.

### Reference credit spread (Arts 383f, 383s-383u)

383s Table 1: 1 MS sovereigns **0,5 %** (all); CQS 1-3: 2 third-country sovereigns/MDB/IO **0,5 %**, 3 RGLA/PSE
**1,0 %**, 4 financials **5,0 %**, 5 basic materials **3,0 %**, 6 consumer **3,0 %**, 7 technology **2,0 %**,
8 health care **1,5 %**, 9 MS covered bonds **1,0 %**, 10 third-country covered bonds CQS 1 **1,5 %** / CQS 2-3
**2,5 %**, 11 qualified indices **1,5 %**; CQS 4-6 and unrated: 12 sovereigns/MDB/IO **2,0 %**, 13 RGLA/PSE
**4,0 %**, 14 financials **12,0 %**, 15 basic materials **7,0 %**, 16 consumer **8,5 %**, 17 technology **5,5 %**,
18 health care **5,0 %**, 19 qualified indices **5,0 %**; 20 other sector **12,0 %**. 383s(2) vega **100 %**.
383f: one net sensitivity per bucket (delta and vega).

383u Table 1 as printed (OJ p.151):

| | 1, 2 and 12 | 3 and 14 | 4 and 15 | 5 and 16 | 6 and 17 | 7 and 18 | 8 and 19 | 9 and 10 | 20 | 11 | 19 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1, 2, and 12 | 100 % | 75 % | 10 % | 20 % | 25 % | 20 % | 15 % | 10 % | 0 % | 45 % | 45 % |
| 3 and 14 | | 100 % | 5 % | 15 % | 20 % | 15 % | 10 % | 10 % | 0 % | 45 % | 45 % |
| 4 and 15 | | | 100 % | 5 % | 15 % | 20 % | 5 % | 20 % | 0 % | 45 % | 45 % |
| 5 and 16 | | | | 100 % | 20 % | 25 % | 5 % | 5 % | 0 % | 45 % | 45 % |
| 6 and 17 | | | | | 100 % | 25 % | 5 % | 15 % | 0 % | 45 % | 45 % |
| 7 and 18 | | | | | | 100 % | 5 % | 20 % | 0 % | 45 % | 45 % |
| 8 and 19 | | | | | | | 100 % | 5 % | 0 % | 45 % | 45 % |
| 9 and 10 | | | | | | | | 100 % | 0 % | 45 % | 45 % |
| 20 | | | | | | | | | 100 % | 0 % | 0 % |
| 11 | | | | | | | | | | 100 % | 75 % |
| 19 | | | | | | | | | | | 100 % |

> 383u(2) ... divided by **2** for correlations between a bucket from the group of buckets 1 to 10 and a
> bucket from the group of buckets 12 to 18.

**TODO: VERIFY** -- the printed labels list bucket 19 twice ("8 and 19", "19") and omit bucket 13; under
Table 1 of Art. 383s the RGLA, financial, basic-materials, consumer, technology and health-care pairs are
3/13, 4/14, 5/15, 6/16, 7/17 and 8/18. The engine uses these sector-consistent pairs with the printed values.

### Equity (Arts 383g, 383v, 383w)

383v Table 1: Large/EME: 1 consumer, transport, admin, healthcare, utilities **55 %**; 2 telecoms, industrials
**60 %**; 3 basic materials, energy, agriculture, manufacturing, mining **45 %**; 4 financials (incl.
government-backed), immovable property activities, technology **55 %**. Large/advanced: 5 **30 %**; 6 **35 %**;
7 **40 %**; 8 **50 %**. Small: 9 EME **70 %**; 10 advanced **50 %**. 11 other sector **70 %**. 12 large-cap
advanced qualified indices **15 %**; 13 other qualified indices **25 %**.
383v(5) vega **78 %** for buckets 1 to 8 and bucket 12, **100 %** for all other buckets.
383w: (a) **15 %** within buckets 1-10; (b) **75 %** buckets 12 and 13; (c) **45 %** 12/13 with 1-10;
(d) **0 %** where one bucket is 11.

### Commodity (Arts 383h, 383x, 383z)

383x Table 1: 1 energy -- solid combustibles **30 %**; 2 energy -- liquid combustibles **35 %**; 3 energy --
electricity **60 %**; 4 energy -- EU ETS carbon trading **40 %**; 5 energy -- non-EU ETS carbon trading **60 %**;
6 freight **80 %**; 7 metals -- non-precious **40 %**; 8 gaseous combustibles **45 %**; 9 precious metals
including gold **20 %**; 10 grains and oilseed **35 %**; 11 livestock and dairy **25 %**; 12 softs and other
agricultural **35 %**; 13 other commodity **50 %**. 383x(2) vega **100 %**.
383z(1)-(2): **20 %** within buckets 1-12; **0 %** where one bucket is 13 (delta and vega).

---

## 3. Leverage ratio (CRR cons. Arts 429-429g; CRR3 points (209)-(213))

> 429(4) ... the total exposure measure shall be the sum of the exposure values of: (a) assets, excluding
> derivative contracts ..., credit derivatives and the positions referred to in Article 429e, calculated in
> accordance with Article 429b(1); (b) derivative contracts ... calculated in accordance with Articles 429c
> and 429d; (c) add-ons for counterparty credit risk of securities financing transactions ... Article 429e;
> (d) off-balance-sheet items ... Article 429f; (e) regular-way purchases or sales awaiting settlement ...
> Article 429g.
>
> 429(7) (a) physical or financial collateral, guarantees or credit risk mitigation purchased shall not be
> used to reduce the total exposure measure; (b) assets shall not be netted with liabilities.
>
> 429a(1) ... may exclude: (a) amounts deducted from CET1 under 36(1)(d); (b) the assets deducted in the
> calculation of the capital measure; (c) 0 % exposures under 113(6)/(7); (ca) [CRR3] network minimum
> deposits; (d) public development credit institution exposures; (da) [CRR3] shareholder pass-through
> covered-bond exposures; (e) passing-through promotional loans; (f) guaranteed parts of export credits;
> (g) clearing member QCCP trade exposures meeting 306(1)(c); (h) higher-level client trade exposures;
> (i) fiduciary assets; (j) PSE pass-through deposits; (k) excess collateral at tri-party agents; (l) cash VM
> receivables; (m) securitised exposures meeting SRT under 244(2); (n) central bank coins/banknotes and
> reserves [subject to 429a(5)-(6)]; (o)-(p) CSD banking-type ancillary services; (q) 72e(5).
>
> 429a(5) ... (a) the institution's competent authority has determined ... and publicly declared that
> exceptional circumstances exist ...; (b) ... limited period of time not exceeding one year ...
>
> 429a(7) **aLR = 3 % · EM_LR / (EM_LR − CB)**
>
> 429c(1) ... in accordance with the method set out in Section 3 of Chapter 6 of Title II of Part Three
> [SA-CCR] ... Institutions shall include in the total exposure measure sold options even where their
> exposure value can be set to zero ... 429c(3) ... may recognise only collateral received in cash ... as the
> variation margin ... where (a) [CRR3] for trades not cleared through a QCCP, the cash received ... is not
> segregated ...; (b) ... exchanged at least daily ...; (c) ... currency ...; (d) ... full amount ...; (e) ...
> single netting agreement ... 429c(4) [CRR3] ... shall not include collateral received in the calculation
> of NICA ... 429c(5) ... set the value of the multiplier ... to **one**, except in the case of derivative
> contracts with clients where those contracts are cleared by a QCCP.
>
> 429d(2) ... the effective notional amounts referenced in the written credit derivatives reduced by any
> negative fair value changes that have been incorporated in Tier 1 ... (3) ... may ... reduce ... by the
> effective notional amount of purchased credit derivatives [conditions (a)-(e)].
>
> 429e(2) **E*_i = max{0; E_i − C_i}** (3) **E*_i = max{0; Σ_i E_i − Σ_i C_i}** [per netting agreement].
>
> 429f(1) [CRR3] Institutions shall calculate, in accordance with Article 111(2), the exposure value of
> off-balance-sheet items ... (3) [CRR3] By way of derogation from Article 495d, institutions shall apply a
> conversion factor of **10 %** to off-balance-sheet items in the form of unconditionally cancellable
> commitments.

Article 111(2) CCFs (see `EU_parameter_reference.md`): bucket 1 **100 %**, 2 **50 %**, 3 **40 %**, 4 **20 %**,
5 **10 %**. Article 274(2) alpha **1,4**. Article 92(1)(d) minimum **3 %**; 92(1a) G-SII leverage buffer =
**50 %** of the G-SII buffer rate.

---

## 4. Large exposures (CRR cons. Arts 387-403; CRR3 points (203)-(206))

> 392 An institution's exposure to a client or a group of connected clients shall be considered a large
> exposure where the value of the exposure is equal to or exceeds **10 %** of its Tier 1 capital.
>
> 394(1) ... for each large exposure ..., including large exposures exempted from the application of
> Article 395(1) ... Institutions shall also report exposures of a value greater than or equal to
> **EUR 300 million** but less than 10 % of the institution's Tier 1 capital ...
>
> 395(1) An institution shall not incur an exposure to a client or group of connected clients the value of
> which exceeds **25 %** of its Tier 1 capital, after taking into account the effect of the credit risk
> mitigation in accordance with Articles 399 to 403. Where that client is an institution or an investment
> firm, or where a group of connected clients includes one or more institutions or investment firms, that
> value shall not exceed 25 % of the institution's Tier 1 capital or **EUR 150 million**, whichever is higher,
> provided that the sum of exposure values ... to all connected clients that are not institutions or
> investment firms, does not exceed 25 % ...
> Where the amount of EUR 150 million is higher than 25 % of the institution's Tier 1 capital, the value of
> the exposure ... shall not exceed a reasonable limit in terms of that institution's Tier 1 capital. ...
> That limit shall not exceed **100 %** of the institution's Tier 1 capital.
> Competent authorities may set a lower limit than EUR 150 million ...
> ... a G-SII shall not incur an exposure to another G-SII or a non-EU G-SII, the value of which ... exceeds
> **15 %** of its Tier 1 capital. ...
>
> 395(5) ... (c) where 10 days or less have elapsed since the excess ... the trading-book exposure ... does
> not exceed **500 %** of the institution's Tier 1 capital; (d) any excesses that have persisted for more than
> 10 days do not, in aggregate, exceed **600 %** ...
>
> 397(2) ... **200 %** of the requirements ... 397(3) Table 1: excess up to 40 % → **200 %**; 40-60 % →
> **300 %**; 60-80 % → **400 %**; 80-100 % → **500 %**; 100-250 % → **600 %**; over 250 % → **900 %**.
>
> 400(1) The following exposures shall be exempted from the application of Article 395(1): (a)-(n) [0 % RW
> sovereigns/CBs/PSEs; 0 % IOs/MDBs; explicit 0 % guarantees; other 0 % attributable; 0 % MS RGLAs;
> 113(6)/(7) counterparties; cash deposits; own CDs; (i) [CRR3] bucket 5 undrawn facilities with a draw-stop;
> (j) clearing members' QCCP trade exposures and DF contributions; DGS funding; (l) clients' trade exposures
> under 305(2)/(3); intra-resolution-group MREL; (n) minimum value commitments].
> 400(2) Competent authorities may fully or partially exempt: (a) [CRR3] covered bonds as referred to in
> Article 129; (b) 20 % MS RGLAs; (c) intragroup; (d) network central institutions; (e) promotional;
> (f) overnight non-major-currency interbank; (g) minimum reserves; (h) statutory liquidity holdings;
> (i) [CRR3] **50 %** of bucket 4 documentary credits and of bucket 3 undrawn facilities up to one year and
> ... **80 %** of guarantees ... by mutual guarantee schemes; (j) mortgage-bond bridging guarantees;
> (k) CQS 2 RRE guarantees; (l) CQS 2 export credit agencies.
> 400(4) The simultaneous application of more than one exemption ... shall not be permitted.
>
> 402(1) [CRR3] ... reduce the value of an exposure ... secured by residential property ... by the pledged
> amount of the property value, but by not more than **55 %** of the property value, ... (a) the competent
> authorities have not set a risk weight higher than **20 %** ... 402(2) [CRR3] ... commercial immovable
> property ... not more than **55 %** ... (a) ... not set a risk weight higher than **60 %** ...

---

## 5. Central counterparties (CRR cons. Arts 300-311)

> 301(1) ... This Section does not apply to exposures arising from the settlement of cash transactions. ...
> a **0 %** risk weight to default fund contributions covering only those transactions.
>
> 303(2) ... the sum of an institution's own funds requirements for its exposures to a QCCP due to trade
> exposures and default fund contributions shall be subject to a cap equal to the sum of own funds
> requirements that would be applied to those same exposures if the CCP were a non-qualifying CCP.
>
> 304(3) (a) ... a margin period of risk of at least **five** business days for its exposures to a client;
> (b) ... at least **10** business days for its exposures to a CCP ... 304(4)-(5) ... maturity factor of
> **0,21** ...
>
> 305(2) [client] ... may calculate the own funds requirements for its trade exposures ... in accordance with
> Article 306 provided that ... (a) [segregation, bankruptcy remote] (b) [portability] (c) [legal review]
> (d) the CCP is a QCCP. 305(3) ... not protected from losses in case the clearing member and another client
> ... jointly default ... replacing the 2 % risk weight ... with a **4 %** risk weight.
>
> 306(1) (a) ... a risk weight of **2 %** to the exposure values of all its trade exposures with QCCPs;
> (b) ... the risk weight used for the Standardised Approach to credit risk as set out in Article 107(2)(b)
> to all its trade exposures with non-qualifying CCPs; (c) ... not required to reimburse the client ... may
> set the exposure value ... to **zero**; (d) ... required to reimburse ... point (a) or (b) ...
> 306(2) ... assets posted as collateral ... bankruptcy remote ... exposure value of **zero** ...
>
> 107(2) (CRR3 point (39)) ... (b) as exposures to a **corporate** for other types of exposures to a
> non-qualifying CCP. [306(1)(b) refers to this point.]
>
> 308(2) (formula image, cons. p.400) **K_i = max{ K_CCP · DF_i / (DF_CCP + DF_CM) ; 8 % · 2 % · DF_i }**
> (3) ... multiplied by **12,5**.
>
> 309(1) **K = DF + UC** ... (2) ... multiplied by **12,5**.
>
> 310 An institution shall apply a **0 %** risk weight to its unfunded contributions to the default fund of a
> QCCP.
>
> 311(2) ... within **three months** ... (a) apply ... point (b) of Article 306(1) to their trade exposures
> ...; (b) apply ... Article 309 to their pre-funded ... and ... unfunded contributions ...; (c) treat their
> [other] exposures ... as exposures to a corporate ...

K_CCP is "communicated to the institution by the QCCP in accordance with Article 50c of Regulation (EU)
No 648/2012"; its formula (EMIR Article 50a) is not in the CRR.

---

## 6. Register of `TODO: VERIFY` items (this package)

| # | Item | Where | Reason | Placeholder |
|---|---|---|---|---|
| 1 | Long-term notch → securitisation CQS 1-17 | `params.SEC_LONG_TERM_NOTCH_TO_CQS` | Implementing Reg. (EU) 2016/1801 not supplied | BCBS row order (AAA→1 ... CCC→17); `CQS<n>` input bypasses |
| 2 | Short-term notch → CQS 1-3 | `params.SEC_SHORT_TERM_NOTCH_TO_CQS` | same | A-1→1, A-2→2, A-3→3, others 1 250 % |
| 3 | SA-CVA inflation-to-inflation tenor correlation | `sa_cva.intra_bucket_corr` | Art. 383l silent | Table 1 tenor correlations |
| 4 | Art. 383u Table 1 row/column labels | `params.SACVA_RCS_CROSS_GROUPS` | printed labels list bucket 19 twice, omit 13 | sector-consistent pairs 3/13 ... 8/18 |
| 5 | Client positions failing Art. 305(2) | `ccp.CLIENT_NON_SEGREGATED_PLACEHOLDER_RW` | Art. 305(1) needs the clearing member's bilateral RW, not in the contract | 150 % (SCRA grade C) |

Modelling conventions (not parameter gaps): Art. 270a applies the supervisory minimum (×3,5, cap 1 250 %);
Art. 268 is applied as a single-tranche cap (V of one tranche); a QCCP default-fund contribution without
K_CCP / DF_CCP+DF_CM falls back to Art. 309 (1 250 %); Art. 267 look-through and the 269a(6) test use
12,5 × K of the pool.

## 7. Material differences from the Basel Framework

1. **Hierarchy order**: SEC-IRBA → **SEC-SA** → SEC-ERBA (Art. 254(1)) vs BCBS SEC-IRBA → **SEC-ERBA** →
   SEC-SA (CRE40.42-40.44).
2. **Forced switch to SEC-ERBA** for rated positions where SEC-SA > 25 %, or (non-STS) SEC-ERBA > 75 %, and for
   auto loans/leases (Art. 254(2)); election for all rated positions (254(3)). No BCBS equivalent.
3. **STS includes synthetic on-balance-sheet securitisations** (originator's senior position, Art. 270) vs BCBS
   STC limited to traditional securitisations (CRE40.66). STS also requires the Art. 243 pool criteria
   (2 % obligor concentration, 40/50/75/100 % RW caps).
4. **NPE securitisations**: qualifying traditional NPE defined by a ≥ 50 % non-refundable purchase-price
   discount, senior 100 % with a 50 % look-through floor and NRPPD-adjusted CR_max/RW_max (Art. 269a) vs BCBS
   NPL defined by W ≥ 90 % with a 100 % senior option (CRE45.1-45.5); the EU floor does not apply when the
   SEC-ERBA is used (269a(2)).
5. **Article 270a additional risk weight** (≥ 250 % of the RW, cap 1 250 %) for due-diligence breaches -- no
   BCBS equivalent.
6. **SEC-ERBA tables are expressed in 17 credit quality steps** (Arts 263-264) rather than rating notches
   (CRE42 tables); cell values are the BCBS values.
7. **Output-floor p factor** of 0,25/0,5 for SEC-SA in S-TREA for positions using SEC-IRBA/IAA in U-TREA until
   2032 (Art. 465(13)) -- no BCBS equivalent.
8. **SA-CVA counterparty credit spread has 21 buckets** with CQS split, Member State sovereigns at 0,5 %
   regardless of rating and Member State covered bonds at 1 % (Art. 383p) vs BCBS 8 sector buckets with IG/HY
   weights (MAR50.63-50.65).
9. **SA-CVA commodity has 13 buckets** (EU ETS vs non-EU ETS carbon, gaseous combustibles split out; 383x) vs
   BCBS 11 buckets (MAR50.74).
10. **SA-CVA ERM II treatment**: ERM II currencies use the specified-currency IR tenors (383c(2)) and euro/ERM II
    FX pairs take 11 %/3 or the narrower band (383n(2)-(3)) -- no BCBS equivalent; inflation is bucketed by
    tenor (383c(1)) vs one inflation factor (MAR50.56).
11. **Leverage-ratio exclusions** specific to the EU (Art. 429a(1)(c)-(q): public development banks,
    promotional loans, export credits, fiduciary assets, CSD services, SRT-securitised exposures) beyond
    LEV30; the central-bank-reserve exclusion requires a competent-authority declaration and the 429a(7)
    adjusted ratio (vs national discretion with recalibration, LEV30.7).
12. **Large exposures to institutions: EUR 150 million alternative limit** (bounded by an institution limit
    ≤ 100 % of Tier 1) (Art. 395(1)) vs a flat 25 % (LEX20.1); **EUR 300 million reporting threshold**
    (Art. 394(1)); **trading-book excesses** permitted with 200 %-900 % add-ons (Arts 395(5), 397) -- not in
    LEX.
13. **Broader large-exposure exemptions** (Art. 400(1)-(2): intragroup, covered bonds, 20 % MS RGLAs,
    minimum reserves, mortgage-bond bridging guarantees, ECA guarantees) and a 55 %-of-value mortgage
    reduction (Art. 402) vs LEX30/LEX40.
14. **Non-qualifying CCP trade exposures are risk-weighted as corporates** (Art. 306(1)(b) → 107(2)(b)) vs
    "according to the category of the counterparty" (CRE54.41); K_CCP is communicated under EMIR Art. 50c.
