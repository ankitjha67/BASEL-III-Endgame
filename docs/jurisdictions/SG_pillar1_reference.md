# Singapore — Pillar 1 Reference: Securitisation, SA-CVA, Leverage, Large Exposures, CCPs

**Sources.**
- MAS Notice 637, *Notice on Risk Based Capital Adequacy Requirements for Banks Incorporated in
  Singapore* (version effective 1 January 2026). Authority for securitisation (Part VII
  Division 1 Sub-division 7 and Division 6), CCPs (Part VII Division 7), SA-CVA (Part VIII
  Division 5 Sub-division 3) and the leverage ratio (Part IV Division 2, Annexes 4C and 4D).
- MAS Notice 656, *Exposures to Single Counterparty Groups for Banks Incorporated in Singapore*
  (14 August 2019, last revised 22 May 2026, effective 1 July 2026). Authority for large
  exposures.

**Code.** `src/jurisdictions/sg/pillar1/` (`SGPillar1`, `Jurisdiction.SG`). Every constant in
`src/jurisdictions/sg/pillar1/params.py` cites one of the provisions below.

**Conventions.** Page numbers are the Notices' own footers (MAS 637 "p. 7-133"; MAS 656 "p. 10").
Formulas printed as images in the PDF were checked against rendered pages (MAS 637 pp. 7-142,
7-317 and 8-196). Amounts are in SGD millions. Values are transcribed verbatim; anything the text
does not settle is listed in §6.

**Note on the brief.** SA-CVA is in **Part VIII** Division 5 Sub-division 3 of MAS 637 (Part X
is the Supervisory Review Process).

---

## 1. Securitisation — MAS 637 Part VII Division 1 Sub-division 7 and Division 6

### 1.1 Credit RWA, caps and CRM (paras 7.1.14–7.1.23, pp. 7-7 to 7-10)

- Credit RWE = Exposure × RW (7.1.14(b)). RW is the SEC-IRBA, SEC-ERBA, SEC-IAA or SEC-SA weight
  (as adjusted by Sub-divisions 9–11), or 1250% "if the Reporting Bank is unable to use the
  SEC-IRBA, SEC-ERBA, SEC-IAA or SEC-SA, or where it cannot meet the requirements in paragraph
  7.6.8(a) to (c)". This is subject to the senior maximum risk weights (7.1.15–7.1.17) and the
  NPL minimum risk weight (7.6.88).
- **Senior look-through cap (7.1.15).** "the risk weight applied to a senior securitisation
  exposure is capped at the exposure weighted-average risk weight applicable to the underlying
  exposures". For mixed pools under the SEC-IRBA, SA(CR) weights apply to the SA part and IRBA
  weights to the IRB part. Under the SEC-SA, SEC-ERBA or SEC-IAA, SA(CR) weights apply. "The
  Reporting Bank must calculate the applicable risk weight under the IRBA taking into account
  the expected loss multiplied by 12.5."
- 7.1.16: "Where the risk weight cap results in a lower risk weight than the floor risk weight
  of 15%, a Reporting Bank must apply the risk weight resulting from the cap."
- 7.1.17: the cap does not apply to resecuritisation exposures.
- **Maximum capital requirement (7.1.18–7.1.22).** Investors using the SEC-IRBA, and
  originators under any approach, may cap the aggregated RWE for one securitisation at
  **P × K_P × 12.5** (7.1.20). P is the largest proportion of interest held across tranches.
  K_P is K_IRB (IRB pool), K_SA (SA pool) or the exposure-weighted average (mixed pool). Gain on
  sale and credit-enhancing I/O strips are still deducted (7.1.21). The cap does not apply to
  resecuritisations (7.1.22).
- 7.1.23: effective risk weight = Credit RWE / Exposure, used as the risk weight of the
  unprotected portion for CRM.

### 1.2 Hierarchy (paras 7.6.8, 7.6.13–7.6.19, pp. 7-125 to 7-127)

| Step | Provision | Rule |
|---|---|---|
| 0 | 7.6.8 | Must understand risk characteristics, access pool performance data and understand structural features; otherwise 1250% (7.1.14(b)(iii)(E)) |
| 1 | 7.6.13–7.6.15 | SEC-IRBA for an IRB pool. Not required where the bank cannot compute K_IRB (7.6.14); prohibited where MAS so directs (7.6.15) |
| 2 | 7.6.16 | SEC-ERBA for an SA pool with an external, or inferred, assessment meeting Annex 7AD |
| 3 | 7.6.17 | With MAS approval, SEC-IAA for an unrated exposure of an SA pool within an ABCP programme |
| 4 | 7.6.18 | SEC-SA where SEC-ERBA / SEC-IAA cannot be used |
| 5 | 7.6.19 | "A Reporting Bank must apply a risk weight of 1250% to a securitisation exposure to which the SEC-IRBA, SEC-ERBA, SEC-IAA and SEC-SA cannot be applied." |

Mixed pools (7.6.80–7.6.81, p. 7-143). Where K_IRB is available for at least 95% of the pool,
apply the SEC-IRBA with pool capital **d × K_IRB + (1 − d) × K_SA**. Otherwise use the SA-pool
hierarchy.

### 1.3 SEC-IRBA (paras 7.6.20–7.6.47, pp. 7-127 to 7-133)

- K_IRB (7.6.21): the IRBA capital requirement of the pool (UL + EL, incl. defaulted and dilution)
  ÷ the pool exposure amount.
- A (7.6.33) = max(0, (pool − tranches senior **or pari passu** to the tranche) / pool).
  D (7.6.34) = max(0, (pool − tranches **senior** to the tranche) / pool).
- N (7.6.38) = (Σ EAD_i)² / Σ EAD_i². LGD_avg (7.6.39) = Σ LGD_i·EAD_i / Σ EAD_i.
- Simplified method (7.6.40–7.6.41), where the largest exposure is ≤ 3% of the pool:
  N = (C1·Cm + ((Cm − C1)/(m − 1)) × max{1 − m × C1, 0})^−1 and LGD_avg = 0.5. If only C1 is
  available (≤ 0.03): N = 1/C1, LGD_avg = 0.5.
- **Supervisory parameter (7.6.42):**
  `p = max[0.3, (A + B/N + (C × K_IRB) + (D × LGD_avg) + (E × M_T))]`

**Table 7-28 — Parameters for Calculation of Supervisory Parameter under SEC-IRBA (p. 7-132)**

| | | A | B | C | D | E |
|---|---|---|---|---|---|---|
| Wholesale | Senior, granular (N ≥ 25) | 0 | 3.56 | −1.85 | 0.55 | 0.07 |
| Wholesale | Senior, non-granular (N < 25) | 0.11 | 2.61 | −2.91 | 0.68 | 0.07 |
| Wholesale | Non-senior, granular (N ≥ 25) | 0.16 | 2.87 | −1.03 | 0.21 | 0.07 |
| Wholesale | Non-senior, non-granular (N < 25) | 0.22 | 2.35 | −2.46 | 0.48 | 0.07 |
| Retail | Senior | 0 | 0 | −7.48 | 0.71 | 0.24 |
| Retail | Non-senior | 0 | 0 | −5.78 | 0.55 | 0.27 |

7.6.43: for a mixed retail / wholesale pool, compute p per sub-pool and take the
exposure-weighted average. 7.6.44: for a mixed pool, p is based on the K_IRB part only.

- **K_SSFA (7.6.45):**
  `K_SSFA(K_IRB) = (e^{a·u} − e^{a·l}) / (a(u − l))`, `a = −(1 / (p × K_IRB))`,
  `u = D − K_IRB`, `l = max(A − K_IRB, 0)`.
- **Risk weight (7.6.46), with a 15% floor:** (a) D ≤ K_IRB: 1250%. (b) A ≥ K_IRB: K_SSFA × 12.5.
  (c) A < K_IRB < D:
  `RW = [((K_IRB − A)/(D − A)) × 12.5] + [((D − K_IRB)/(D − A)) × 12.5 × K_SSFA(K_IRB)]`.

### 1.4 SEC-ERBA (paras 7.6.48–7.6.54, pp. 7-133 to 7-136)

**Table 7-29 — SEC-ERBA Risk Weights for Short-Term External Credit Assessment (p. 7-133)**, 15% floor

| Credit quality grade | I | II | III | All other credit assessments |
|---|---|---|---|---|
| Risk weight | 15% | 50% | 100% | 1250% |

**Table 7-30 — SEC-ERBA Risk Weights for Long-Term External Credit Assessment (p. 7-134)**, 15% floor

| Grade | Senior M_T = 1 | Senior M_T = 5 | Non-senior M_T = 1 | Non-senior M_T = 5 |
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
| 18 | 1250% | 1250% | 1250% | 1250% |

- Maturity (7.6.50): `RW_M adj. = RW(M=1) + (RW(M=5) − RW(M=1)) · ((M_T − 1)/(5 − 1))`.
- Senior (7.6.51): `RW = RW_M adj.`. Non-senior thickness (7.6.52):
  `RW = RW_M adj. · [1 − min(T, 0.5)]`, T = D − A.
- 7.6.53: market-risk hedges take the RW of the pari passu (or next subordinated) exposure.
- 7.6.54: a non-senior exposure's RW may not be lower than that of the immediately preceding,
  more senior exposure with the same rating and maturity.

**Table 7M-3 — Credit Quality Grades for SEC-ERBA and SEC-IAA Exposures (Annex 7M, p. 7-272)**

| Grade | Fitch | Moody's | S&P |
|---|---|---|---|
| 1 | AAA | Aaa | AAA |
| 2 | AA+ | Aa1 | AA+ |
| 3 | AA | Aa2 | AA |
| 4 | AA- | Aa3 | AA- |
| 5 | A+ | A1 | A+ |
| 6 | A | A2 | A |
| 7 | A- | A3 | A- |
| 8 | BBB+ | Baa1 | BBB+ |
| 9 | BBB | Baa2 | BBB |
| 10 | BBB- | Baa3 | BBB- |
| 11 | BB+ | Ba1 | BB+ |
| 12 | BB | Ba2 | BB |
| 13 | BB- | Ba3 | BB- |
| 14 | B+ | B1 | B+ |
| 15 | B | B2 | B |
| 16 | B- | B3 | B- |
| 17 | CCC+/CCC/CCC- | Caa1/Caa2/Caa3 | CCC+/CCC/CCC- |
| 18 | Below CCC- | Below Caa3 | Below CCC- |

**Table 7M-4 — Short-term grades (p. 7-272):** I = F-1 / P-1 / A-1; II = F-2 / P-2 / A-2;
III = F-3 / P-3 / A-3; IV = Others. Per Table 7M-2 para 1.1, A-1 includes A-1+ and A-1−.

**Tranche maturity (Annex 7V Section 6, pp. 7-317, 7-318).**
(a) `M_T = Σ_t t·CF_t / Σ_t CF_t` (contractual, unconditional cash flows).
(b) `M_T = 1 + (M_L − 1) · 80%` (final legal maturity), which must be used where unconditional
contractual payment dates are not available (6.2). 6.3: "subject ... to a cap of 5 years and a
floor of one year".

### 1.5 SEC-IAA (paras 7.6.55–7.6.61, pp. 7-136 to 7-139)

- Requires MAS written approval and IRBA approval for at least one asset class (7.6.55). Covers
  unrated exposures to ABCP programmes only. Without approval, use the SEC-SA (7.6.58).
- 7.6.61: map the internal rating to an equivalent short- or long-term assessment and apply
  Table 7-29 / 7-30. 1250% applies where the equivalent short-term assessment is not "III" or
  better, or the long-term assessment is not grade "10" or better.

### 1.6 SEC-SA (paras 7.6.62–7.6.79, pp. 7-139 to 7-143)

- K_SA (7.6.64, p. 7-140):
  `K_SA = (SA(CR) RWA_Underlying + CCR-SA RWA_Underlying) / (SA(CR) Exposure_Underlying + CCR Exposure_Underlying) · 8%`.
- W (7.6.70): the share of underlying exposures that are delinquent (90+ days past due,
  bankruptcy / insolvency, foreclosure, REO, or default under the deal documents).
- `K_A = (1 − W) × K_SA + W × 0.5` (7.6.73).
- Unknown W (7.6.74, rendered p. 7-142), for no more than 5% of the pool by E:
  `K_A = (E_Subpool1 / E_Total × K_A^Subpool1) + E_Subpool2 / E_Total`. Above 5%: 1250%.
- K_SSFA(K_A) as in 1.3 with K_A (7.6.75). **p = 1** (7.6.76).
- RW (7.6.77), with a 15% floor: (a) D ≤ K_A: 1250%. (b) A ≥ K_A: K_SSFA × 12.5. (c) blend
  `RW = [((K_A − A)/(D − A)) × 12.5] + [((D − K_A)/(D − A)) × 12.5 × K_SSFA(K_A)]`.
- 7.6.79: the RW of an unrated non-senior exposure may not be below that of the immediately
  preceding, more senior rated exposure.

### 1.7 Resecuritisation (paras 7.6.82–7.6.83, pp. 7-143, 7-144)

SEC-SA with a 100% floor. "(a) the capital requirement of the resecuritisation's underlying
securitisation exposures (KSA) is calculated using the securitisation framework ... (b)
delinquencies (W) are set to zero for any exposure to a securitisation tranche in the underlying
pool; (c) the supervisory parameter p is set equal to 1.5, rather than 1." In a mixed underlying
pool, K_A is the nominal-weighted average of K_A for the securitisation subset and the
non-securitised subset.

### 1.8 NPL securitisations (paras 7.6.84–7.6.92, pp. 7-144, 7-145)

- Definition (7.6.85). W ≥ 90% at origination and at each replenishment / restructuring. The
  pool holds only loans, loan-equivalent instruments (incl. unlisted bonds) or sub-participation
  instruments. There are no securitisation exposures in the pool.
- Hierarchy as in 1.2 (7.6.86). No SEC-IRBA where K_IRB uses the F-IRBA (7.6.87).
- **Floor 100%** under SEC-IRBA, SEC-SA or the look-through approach (7.6.88).
- **Senior 100%** under SEC-IRBA / SEC-SA for a traditional NPL securitisation where NRPPD
  ≥ 50% of the pool's outstanding amount (7.6.89; NRPPD defined in 7.6.90).
- Cap of 7.1.18–7.1.20 for originators, and for investors using SEC-IRBA (7.6.91).
- 7.6.92: no NPL securitisation "for the purposes of reducing capital requirements on
  non-delinquent exposures".

### 1.9 STC (paras 7.6.93–7.6.104, pp. 7-145 to 7-150)

- Scope (7.6.93): traditional securitisations only. Non-ABCP deals must meet all Annex 7AE
  criteria. ABCP conduits must meet Annex 7AF conduit- and transaction-level criteria; ABCP
  transactions must meet the Annex 7AF transaction-level criteria. All criteria apply on an
  ongoing basis.
- 7.6.98: "the resulting risk weight is subject to a minimum risk weight of 10% for senior
  securitisation tranches, and 15% for non-senior securitisation tranches."
- SEC-IRBA (7.6.99):
  `p = max[0.3, 0.5 × (A + B/N + (C × K_IRB) + (D × LGD_avg) + (E × M_T))]`. Table 7-31 has the
  same cells as Table 7-28.
- SEC-SA (7.6.103): **p = 0.5**. 7.6.104 repeats the 7.6.77 blend with the 10% / 15% floors.

**Table 7-32 — STC, short-term (p. 7-148):** I 10%, II 30%, III 60%, all other 1250%.

**Table 7-33 — STC, long-term (p. 7-149)**

| Grade | Senior 1Y | Senior 5Y | Non-senior 1Y | Non-senior 5Y |
|---|---|---|---|---|
| 1 | 10% | 10% | 15% | 40% |
| 2 | 10% | 15% | 15% | 55% |
| 3 | 15% | 20% | 15% | 70% |
| 4 | 15% | 25% | 25% | 80% |
| 5 | 20% | 30% | 35% | 95% |
| 6 | 30% | 40% | 60% | 135% |
| 7 | 35% | 40% | 95% | 170% |
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
| 18 | 1250% | 1250% | 1250% | 1250% |

### 1.10 Annex 7C — CCF for off-balance sheet securitisation exposures (p. 7-181)

| | Item | CCF |
|---|---|---|
| (a) | Undrawn servicer cash advances / facilities, unconditionally cancellable without prior notice | 10% |
| (b) | Undrawn portion of other servicer cash advances or facilities | 100% |
| (c) | Other facilities which are not credit risk mitigants | 100% |

---

## 2. SA-CVA — MAS 637 Part VIII Division 5 Sub-division 3 (pp. 8-188 to 8-227)

- 8.5.1: CVA RWA = 12.5 × (BA-CVA capital + SA-CVA capital). SA-CVA needs MAS prior written
  approval (8.5.7, 8.5.19). Netting sets may be carved out to the BA-CVA (8.5.8–8.5.9).
- 8.5.29: K = Σ delta capital over 6 risk classes (IR, FX, counterparty credit spread,
  reference credit spread, equity, commodity) + Σ vega capital over 5 classes (all except
  counterparty credit spread; 8.5.30).
- **Aggregation (8.5.32; formula rendered from p. 8-196):**
  - `WS_k^CVA = RW_k s_k^CVA`, `WS_k^Hdg = RW_k s_k^Hdg`, `WS_k = WS_k^CVA − WS_k^Hdg`.
  - `K_b = sqrt( (Σ_k WS_k² + Σ_k Σ_{l≠k} ρ_kl WS_k WS_l) + R · Σ_k (WS_k^Hdg)² )`, R = 0.01.
  - `K = m_CVA · sqrt( Σ_b K_b² + Σ_b Σ_{c≠b} γ_bc S_b S_c )`, `S_b = max{−K_b; min(Σ_k WS_k; K_b)}`.
  - m_CVA = 1; "The Authority may require a Reporting Bank to use a higher value".
- Qualified index (8.5.34): listed on an approved or overseas exchange, look-through possible,
  ≥ 20 constituents, no constituent above 25%, largest 10% of constituents below 60% of the
  index, total market cap ≥ USD 40 billion.

### 2.1 Interest rate (8.5.35–8.5.39)

One bucket per currency. For the reporting currency and USD, EUR, GBP, AUD, CAD, SEK and JPY
(8.5.36) the delta risk factors are the tenors 1, 2, 5, 10 and 30 years plus inflation.

**Table 8-28 (p. 8-200):** 1Y 1.11%, 2Y 0.93%, 5Y 0.74%, 10Y 0.74%, 30Y 0.74%, inflation 1.11%.

**Table 8-29 (p. 8-200)**

| | 2Y | 5Y | 10Y | 30Y | Inflation |
|---|---|---|---|---|---|
| 1Y | 91% | 72% | 55% | 31% | 40% |
| 2Y | | 87% | 72% | 45% | 40% |
| 5Y | | | 91% | 68% | 40% |
| 10Y | | | | 83% | 40% |
| 30Y | | | | | 40% |

- Other currencies (8.5.37): a parallel shift of the whole curve plus inflation. RW 1.58% for
  both; correlation 40%.
- Vega (8.5.38): rate volatility and inflation volatility. RW 100%; correlation 40%.
- γ_bc = 0.5 for all currency pairs (8.5.39).

### 2.2 FX (8.5.40–8.5.45)

One bucket per currency other than the reporting currency. Delta RW **11%** (8.5.41(c)), vega RW
100% (8.5.43(c)), γ_bc = 0.6 (8.5.45).

### 2.3 Counterparty credit spread (8.5.46–8.5.52), delta only

**Table 8-30 / 8-31 — Buckets and risk weights (pp. 8-206, 8-209)**

| Bucket | Sector | Grade "3" or better | Grade "4" or worse / not rated |
|---|---|---|---|
| 1 a) | Sovereigns (central governments, central banks, BIS, IMF, ECB, EU, ESM, EFSF) and MDBs | 0.5% | 2.0% |
| 1 b) | PSEs, education | 1.0% | 4.0% |
| 2 | Financial institutions | 5.0% | 12.0% |
| 3 | Basic materials, energy, industrials, agriculture, manufacturing, mining and quarrying | 3.0% | 7.0% |
| 4 | Consumer goods and services, transportation and storage, administrative and support service activities | 3.0% | 8.5% |
| 5 | Technology, telecommunications | 2.0% | 5.5% |
| 6 | Health care, utilities, professional and technical activities | 1.5% | 5.0% |
| 7 | Other sector | 5.0% | 12.0% |
| 8 | Qualified indices | 1.5% | 5.0% |

- Tenors: 0.5, 1, 3, 5 and 10 years (8.5.50(a)).
- Correlation (8.5.50(d)): ρ_kl = ρ_tenor · ρ_name · ρ_quality.
  - ρ_tenor: 100% for the same tenor, else 90%.
  - ρ_name, buckets 1–7: 100% for the same entity; 90% for parent / subsidiary or two
    subsidiaries of a common parent; 50% otherwise.
  - ρ_name, bucket 8: 100% for the same index and series; 90% for the same index, distinct
    series; 80% otherwise.
  - ρ_quality: 100% for the same quality, else 80%. "Same" (8.5.51) means both grade "3" or
    better, or both grade "4" or worse / unrated.

**Table 8-32 — γ_bc (p. 8-211)**

| | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|
| 1 | 10% | 20% | 25% | 20% | 15% | 0% | 45% |
| 2 | | 5% | 15% | 20% | 5% | 0% | 45% |
| 3 | | | 20% | 25% | 5% | 0% | 45% |
| 4 | | | | 25% | 5% | 0% | 45% |
| 5 | | | | | 5% | 0% | 45% |
| 6 | | | | | | 0% | 45% |
| 7 | | | | | | | 0% |

### 2.4 Reference credit spread (8.5.53–8.5.61)

Table 8-33 (p. 8-214) buckets:
- 1–7: grade "3" or better. Sectors: sovereigns / MDBs; PSEs / education; financial
  institutions; basic materials etc.; consumer etc.; technology / telecommunications;
  health care etc.
- 8–14: the same seven sectors, grade "4" or worse / not rated.
- 15: other sector.
- 16: qualified indices, grade "3" or better.
- 17: qualified indices, grade "4" or worse.

One risk factor per bucket: a simultaneous shift of all tenors (8.5.58).

**Table 8-34 — delta RW (p. 8-216):** 1 0.5%, 2 1.0%, 3 5.0%, 4 3.0%, 5 3.0%, 6 2.0%, 7 1.5%,
8 2.0%, 9 4.0%, 10 12.0%, 11 7.0%, 12 8.5%, 13 5.5%, 14 5.0%, 15 12.0%, 16 1.5%, 17 5.0%.
Vega RW 100% (8.5.59(c)).

**Table 8-35 — γ_bc (p. 8-217)**

| | 1/8 | 2/9 | 3/10 | 4/11 | 5/12 | 6/13 | 7/14 | 15 | 16 | 17 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1/8 | 100% | 75% | 10% | 20% | 25% | 20% | 15% | 0% | 45% | 45% |
| 2/9 | | 100% | 5% | 15% | 20% | 15% | 10% | 0% | 45% | 45% |
| 3/10 | | | 100% | 5% | 15% | 20% | 5% | 0% | 45% | 45% |
| 4/11 | | | | 100% | 20% | 25% | 5% | 0% | 45% | 45% |
| 5/12 | | | | | 100% | 25% | 5% | 0% | 45% | 45% |
| 6/13 | | | | | | 100% | 5% | 0% | 45% | 45% |
| 7/14 | | | | | | | 100% | 0% | 45% | 45% |
| 15 | | | | | | | | | 0% | 0% |
| 16 | | | | | | | | | | 75% |

8.5.60(a): for a pair of buckets 1–14 with different credit qualities, the Table 8-35 value is
divided by 2.

### 2.5 Equity (8.5.62–8.5.69)

Table 8-36 (p. 8-221). Large cap is ≥ USD 2 bn (8.5.66(a)). Advanced economies: Canada, US,
Mexico, euro area, UK, Norway, Sweden, Denmark, Switzerland, Japan, Australia, New Zealand,
Singapore, Hong Kong SAR (8.5.66(b)).

| Bucket | Size | Economy | Sector | Delta RW (Table 8-37, p. 8-223) |
|---|---|---|---|---|
| 1 | Large | Emerging | Consumer goods and services, transportation and storage, administrative and support service activities, healthcare, utilities | 55% |
| 2 | Large | Emerging | Telecommunications, industrials | 60% |
| 3 | Large | Emerging | Basic materials, energy, agriculture, manufacturing, mining and quarrying | 45% |
| 4 | Large | Emerging | Financial institutions, real estate activities, technology | 55% |
| 5 | Large | Advanced | (as 1) | 30% |
| 6 | Large | Advanced | (as 2) | 35% |
| 7 | Large | Advanced | (as 3) | 40% |
| 8 | Large | Advanced | (as 4) | 50% |
| 9 | Small | Emerging | All sectors of buckets 1–4 | 70% |
| 10 | Small | Advanced | All sectors of buckets 5–8 | 50% |
| 11 | n/a | | Other sector | 70% |
| 12 | Large market cap and advanced economy | | Qualified indices | 15% |
| 13 | Other | | Qualified indices | 25% |

- Vega RW (8.5.68(c)): "78% for a bucket that corresponds to large market capitalisation in
  Table 8-36, and 100% in all other cases".
- γ_bc (8.5.69): 15% between buckets 1–10; 75% between 12 and 13; 45% between 12/13 and 1–10;
  0% with bucket 11.

### 2.6 Commodity (8.5.70–8.5.73)

**Table 8-38 / 8-39 (pp. 8-225, 8-226)**

| Bucket | Group | Delta RW |
|---|---|---|
| 1 | Energy – solid combustibles | 30% |
| 2 | Energy – liquid combustibles | 35% |
| 3 | Energy – electricity and carbon trading | 60% |
| 4 | Freight | 80% |
| 5 | Metals – non-precious | 40% |
| 6 | Gaseous combustibles | 45% |
| 7 | Precious metals (including gold) | 20% |
| 8 | Grains and oilseed | 35% |
| 9 | Livestock and dairy | 25% |
| 10 | Softs and other agricultural commodities | 35% |
| 11 | Other commodity | 50% |

Vega RW 100% (8.5.72(c)). γ_bc: 20% between buckets 1–10; 0% with bucket 11 (8.5.73).

---

## 3. Leverage ratio — MAS 637 Part IV Division 2, Annexes 4C and 4D

- 4.2.2 (p. 4-12): "A Reporting Bank must, at all times, maintain at both the Solo and Group
  levels, a minimum leverage ratio of 3%."
- Annex 4C para 1.1: `Leverage ratio = Capital measure (CM) / Total exposure measure (TEM)`.
- 1.3: items deducted from CET1 / AT1 may be deducted from the TEM, but no liability items.
  2.2: no netting of assets against liabilities and no CRM. 2.3:
  TEM = on-balance (2.8–2.12) + derivatives (2.13–2.39) + SFTs (2.40–2.50) + off-balance
  (2.51–2.53), less the deductions of paras 1.3, 2.6, 2.8 and 2.21(b).
- On-balance (2.8): carrying amount net of specific allowances. General allowances that reduced
  CET1 may be deducted. Right-of-use assets are included (2.9). Fiduciary assets may be
  excluded (2.10). Cash pooling has its own conditions (2.12).
- Derivatives (2.13 / 2.14): `exposure measure = alpha × (RC + PFE)`, alpha = 1.4,
  `RC = max(V − CVM_r + CVM_p, 0)`, `PFE = multiplier × AddOn^aggregate` per Annex 7D,
  "except that the value of the multiplier ... must be fixed at one". Maturity-factor margining
  benefit is allowed. 2.15: off-balance-sheet derivatives use the sum of positive fair values.
  2.17: no reduction for collateral received, and a gross-up for collateral provided.
  2.18–2.21: eligible cash VM received may reduce RC (conditions (a)–(f)); PFE is not reduced.
- Client clearing (2.22–2.29): a clearing member may exclude QCCP trade exposures if not
  obliged to reimburse the client on CCP default. The exposure to the client uses SA-CCR
  (2.25).
- Written credit derivatives (2.31–2.39): add the effective notional, less negative fair-value
  changes in CM. It may be offset by purchased protection on an identical reference name
  meeting 2.33(a)–(e).
- SFTs (2.40): gross SFT assets (cash payables / receivables netted only under (a)(ii)(A)–(C)),
  plus `CE_SFT* = max{0, [Σ CE_SFT,i − Σ C_SFT,i]}` under a qualifying netting agreement, or per
  transaction otherwise.
- Off-balance (2.51–2.53): notional × CCF from Annex 4D (non-securitisation) or Annex 7C
  (securitisation). Apply the CCF to the lower of the unused line and any constraint on
  availability. Allowances may reduce the EM, but not below zero.
- **No exclusion of central bank reserves** appears in Annex 4C.

**Table 4D-1 — CCF for off-balance sheet items (Annex 4D, pp. 4-37, 4-38)**

| | Item | CCF |
|---|---|---|
| (a) | Direct credit substitutes | 100% |
| (b) | Sale and repurchase agreements and asset sales with recourse (other than SFTs) | 100% |
| (c) | Commitments with certain drawdown (forward purchases, forward deposits, partly paid shares) | 100% |
| (d) | Credit substitutes not in (a)–(c) | 100% |
| (e) | Commitments to pay for unsettled purchases (settlement-date accounting) | 100% |
| (f) | NIFs and RUFs, regardless of maturity | 50% |
| (g) | Certain transaction-related contingent items | 50% |
| (h) | Other commitments, regardless of maturity | 40% |
| (i) | Self-liquidating trade-related contingent items, original maturity below one year | 20% |
| (j) | Commitments unconditionally cancellable at any time without prior notice | 10% |

- 1.2: a commitment on another off-balance item takes the lower of the two CCFs.
- 1.3: a tranched loan commitment takes 40% on the full undisbursed portion.
- 1.4: MAS may require more than 10% under item (j).

---

## 4. Large exposures — MAS Notice 656

| Provision | Rule |
|---|---|
| Para 4 ("large exposure", p. 6) | Aggregate exposures to a single counterparty group "equal to or above 10% of the Tier 1 capital" (Solo, Group) |
| Para 7 (p. 10) | Solo: aggregate exposures to any single counterparty group must not "exceed 25% of its Tier 1 capital" |
| Para 8 (pp. 10, 11) | Group: same 25% limit, aggregating banking group entities |
| Para 9 (p. 11) | A G-SIB headquartered in Singapore: 15% of Tier 1 to any other G-SIB, or to a connected counterparty group including the G-SIB (Solo and Group) |
| Paras 10–11 (p. 11) | 15% applies within 12 months of becoming a G-SIB, or of a counterparty becoming one, on or after 1 July 2021 |
| Para 12 | Internal limits on exposures to G-SIFIs and D-SIBs |
| Para 16 (p. 12) | Economic-dependence due diligence where exposure to X exceeds 5% of Tier 1 |
| Para 28 (p. 15) | Semi-annual reporting. (a) All large exposures, incl. exempt ones except 1(e) intraday. (b) All non-exempt exposures ≥ 10% of Tier 1, before CRM. (c) The 20 largest exposures. (d)–(e) Non-aggregated persons |
| Annex C para 2.5 (p. 26) | Off-balance sheet: notional × Table 7B-1 CCF, "with a floor of 10%" |
| Annex C paras 4.1–4.3 (pp. 30–32) | Covered bonds: 100% of nominal; qualifying covered bonds at least 25% |
| Annex C paras 4.8–4.11 (pp. 33, 34) | Look-through of structures with a 0.25% of Tier 1 threshold |
| Annex C paras 4.17–4.23, Table C-2 (pp. 36, 37) | CCPs. Trade exposures excl. IM: measured per Annex C. Segregated IM: 0. Non-segregated IM: nominal. Pre-funded DF: nominal. Unfunded DF: 0. Equity stakes: nominal unless deducted. Non-QCCP: C + N |

"Single counterparty group" (para 4) means a counterparty, a director group, a major stake
entity group, a substantial shareholder group, or a connected counterparty group (control or
economic dependence; paras 5A–5C, 17).

**Exempt exposures (Annex A para 1, pp. 17–19)**

| | Exemption |
|---|---|
| (a) | Singapore Government or the Authority |
| (b) | Other central governments / central banks: (i) domestic currency; (ii) other currency where the sovereign is rated at least AA-; (iii) statutory liquidity / reserve requirements |
| (c) | PSEs at 0% under Table 7-3 of MAS 637 (outside Singapore: domestic currency only) |
| (d) | BIS, IMF, ECB, EU, ESM, EFSF |
| (da) | Qualifying MDBs |
| (e) | Intraday exposures to banks, up to 2 business days, absent the listed credit events |
| (f) | QCCP exposures related to clearing activities (Table C-2) |
| (g) | Related corporations: bank holding companies; bank / merchant bank / regulated FI subsidiaries (residual maturity ≤ 1 year); sister banks / FIs |

---

## 5. CCP exposures — MAS 637 Part VII Division 7 (pp. 7-154 to 7-166)

- QCCP (7.7.3) means: (a) licensed CCP; (b) supervised under CPSS-IOSCO PFMI-consistent rules;
  (c) K_CCP etc. made available (7.7.37(a)–(b)).
- 7.7.4: QCCP RWA = trade-exposure RWA + 12.5 × the default fund capital requirement.
  Pre-funded default funds for settlement-risk-only products are risk-weighted at 0%.
- 7.7.5: where the QCCP RWA exceeds the non-qualifying RWA, use the non-qualifying RWA.
- 7.7.6: non-qualifying CCP RWA = (a) bilateral CCR (7.1.9(a)–(e)) on trade exposures + (b)
  "1250% of default fund exposures, including all pre-funded contributions and unfunded
  contributions". 7.7.8: MAS determines the amount for unlimited unfunded commitments.
- 7.7.10: three-month transition after a CCP ceases to qualify.
- Trade exposures:
  - 7.7.15: clearing member, 2% of E/EAD.
  - 7.7.18: MPOR at least 10 days for OTC derivatives; no 20-day floor for more than 5,000
    trades unless disputes or illiquid collateral.
  - 7.7.20: client meeting conditions (a)–(d), 2%.
  - 7.7.23: client meeting all conditions except 7.7.20(b)(i)(C), 4%.
  - 7.7.24: otherwise bilateral exposure to the clearing member.
- Collateral (7.7.25–7.7.33): bankruptcy-remote collateral attracts no CCR charge. Collateral
  held at the CCP and not bankruptcy remote takes 2% (clearing member, 7.7.26) or 2% / 4%
  (client, 7.7.28). Collateral at the clearing member takes the clearing member's RW (7.7.31).
- 7.7.34: clearing member exposures to clients are bilateral. MPOR may be as low as 5 days.
- **K_CCP (7.7.41, p. 7-163):** `K_CCP = Σ_i EAD_i × 20% × 8%`. EAD_i uses SA-CCR with a 10-day
  MPOR (7.7.43). For SFTs, `EAD_i = max(EBRM_i − IM_i − DF_i; 0)`. MAS may set a risk weight
  above 20% (7.7.42(e)).
- **K_CM (7.7.44, p. 7-166):**
  `K_CM(Bank) = max(K_CCP × DF_CM(Bank)^pref / (DF_CCP + DF_CM^pref) ; 8% × 2% × DF_CM(Bank)^pref)`.
  This is "a 2% risk weight floor ... applied to the default fund exposure".

---

## 6. Items the text does not settle (TODO: VERIFY) and modelling choices

| Item | Treatment |
|---|---|
| D-SIB leverage-ratio buffer | Annex 11D row 27 (p. 11-164) mentions a "D-SIB leverage ratio buffer requirement". Part IV Division 2 sets only the 3% minimum; no rate is given. `sg/params.py` keeps 0% + TODO (unchanged) |
| D-SIB / HLA buffer rate | Not set in Part IV Division 2 or Annexes 4C / 4D; unchanged |
| Missing N / LGD in SEC-IRBA | The text requires them (7.6.38–7.6.41). The engine uses N = 1 and LGD = 100% (conservative) and notes it |
| SEC-IAA mapping input | The internal rating is passed as an equivalent rating string (7.6.61(a)) |
| Look-through cap, more-senior floor, mixed-pool d | Taken as optional keyword arguments (not in the protocol) |
| Bankruptcy-remote initial margin amount | Not in the contract. `trade_exposure` must exclude bankruptcy-remote collateral (7.7.25 / 7.7.27) |
| Unfunded default fund commitments (non-QCCP) | Not in the contract. `default_fund_contribution` is taken as funded + unfunded (7.7.6(b)) |
| Reporting currency | SGD assumed for 8.5.36 / 8.5.40 |
