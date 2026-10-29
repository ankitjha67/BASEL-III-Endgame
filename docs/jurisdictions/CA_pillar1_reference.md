# OSFI Pillar 1 reference — securitization, SA-CVA, CCPs, leverage, large exposures

Verbatim transcription of every table and formula implemented in `src/jurisdictions/ca/pillar1/`.

| Area | Authority (supplied text) | Status |
|---|---|---|
| Securitization | OSFI *Capital Adequacy Requirements (CAR) Guideline (2026)*, Chapter 6 | In force, fiscal 2026 |
| SA-CVA | CAR 2026 Chapter 8 s.8.3 | In force |
| CCP exposures | CAR 2026 Chapter 7 s.7.1.8 | In force |
| Leverage exposure measure | OSFI *Leverage Requirements Guideline (2023)* ("LR"), effective Feb / Apr 2023 | In force |
| Large exposures | OSFI *Guideline B-2 Large Exposure Limits (2028)* ("B-2"), dated May 21, 2026, effective Nov 1, 2027 / Jan 1, 2028 | **Consultation draft** ("Consultation closed August 19, 2026. We'll keep this draft on the site until the final guideline is released.") |

The CAR web text was converted to plain text with tables flattened into running text; every table
below was rebuilt from the flattened row/column sequence (each ERBA row was re-parsed by script and
compared cell by cell with the code and with the Basel Framework text). Where this file and the
official OSFI publication differ, the official publication governs.

Citation format in code: `CAR Ch.<n> s.<section> [Basel ref]`, `LR s.<part> (paragraph n) [LEV ref]`,
`B-2 s.<part> [LEX ref]`. OSFI prints the Basel paragraph at the end of each paragraph in square
brackets; those references are reproduced. OSFI paragraph numbers are cited only where the guideline's
own cross-references fix them.

Currency: CAR Ch.1 footnote 6 / Ch.8 footnote 4 — "All dollar values in this guideline are in
Canadian dollars, unless otherwise noted."

Items marked **⚠ VERIFY** carry `# TODO: VERIFY` in source.

---

## 1. Securitization — CAR Chapter 6

### 1.1 Scope note
"all exposures to mortgage-backed securities that do not involve tranching with associated
subordination of credit risk (e.g. NHA MBS) will not be considered securitization exposures" (Ch.6
introduction) — NHA MBS stay in Chapter 4 (0%).

### 1.2 Definitions used
- **NPL securitization** (s.6.2.1.11): "a securitization where the underlying pool's variable W ... is
  equal to or higher than 90% at the origination cut-off date and at any subsequent date on which
  assets are added to or removed from the underlying pool" [CRE 40.48, 45.1].
- **Senior tranche** (s.6.2.1.13): "effectively backed or secured by a first claim on the entire
  amount of the assets in the underlying securitized pool" [CRE 40.18].
- **Tranche maturity** (s.6.2.1.16) [CRE 40.22]:
  - cash-flow method: `M_T = Σ_t t·CF_t / Σ_t CF_t`; OSFI adds prepayment assumptions — the lowest of
    the deal base case, the lowest historical annualised rate and the deal's average rate, "subject to
    a cap of 20%" (zero prepayments with less than five years of data) — and a revolving-period
    maturity adjustment;
  - legal-maturity method: `M_T = 1 + (M_L − 1) × 80%`;
  - "In all cases, MT will have a floor of one year and a cap of five years."

### 1.3 Exposure amount, CCFs and I/O strips (s.6.5.1, 6.5.1.1)
| Item | Treatment |
|---|---|
| Credit-enhancing interest-only strips | 1250% |
| Other unrated I/O strips subject to prepayment risk | 250% |
| Other unrated I/O strips not subject to prepayment risk | 100% (all "consistent with section 4.1.23 of Chapter 4") [CAP 30.14] |
| Undrawn securitization commitment to fund client vehicle acquisitions | CCF 40% |
| Servicer cash advances, unconditionally cancellable without prior notice | CCF 10% |
| Other securitization commitments that are not CRM | CCF 100% [CRE 40.20] |

### 1.4 Hierarchy of approaches (s.6.5.2) [CRE 40.41–40.47]
1. "An institution must use the ... SEC-IRBA ... for a securitization exposure of an IRB pool ...
   unless otherwise determined by OSFI." Investor/sponsor exposures to IRB pools that materially
   benefit from excess spread may be treated as SA pools if externally rated (flag
   `ca_irb_pool_excess_spread_as_sa`).
2. "If an institution cannot use the SEC-IRBA, it must use the ... SEC-ERBA" (external or inferred
   rating). SEC-IAA for unrated ABCP exposures: "In order to use the SEC-IAA, an institution must have
   OSFI approval to use the IRB approach" (flag `ca_iaa_approved`).
3. "An institution that cannot use the SEC-ERBA or a SEC-IAA ... may use the ... SEC-SA".
4. "Securitization exposures to which none of the approaches ... can be applied must be assigned a
   1250% risk weight."
5. Mixed pools: SEC-IRBA with `d × K_IRB + (1 − d) × K_SA` where K_IRB is available for at least 95%
   of the pool; otherwise the SA-pool hierarchy.

**Capital floor (s.6.11, OSFI-specific):** institutions subject to the capital floor must use SEC-ERBA,
SEC-SA or 1250%; "The internal ratings based approach (SEC-IRBA) and internal assessment approach
(SEC-IAA) ... are ineligible for use under the capital floor"; STC treatments apply; the caps may be
used "so long as the pool underlying the exposure is treated as an SA pool" (flag
`ca_capital_floor_calculation`).

### 1.5 SEC-IRBA (s.6.6.1) [CRE 44]
Supervisory parameter (s.6.6.1.6) [CRE 44.17]:

`p = max[0.3; A + B/N + C × K_IRB + D × LGD + E × M_T]`

"Parameters to determine supervisory parameter p":

| Asset class | Seniority / granularity | A | B | C | D | E |
|---|---|---|---|---|---|---|
| Wholesale | Senior, granular (N ≥ 25) | 0 | 3.56 | −1.85 | 0.55 | 0.07 |
| Wholesale | Senior, non-granular (N < 25) | 0.11 | 2.61 | −2.91 | 0.68 | 0.07 |
| Wholesale | Non-senior, granular (N ≥ 25) | 0.16 | 2.87 | −1.03 | 0.21 | 0.07 |
| Wholesale | Non-senior, non-granular (N < 25) | 0.22 | 2.35 | −2.46 | 0.48 | 0.07 |
| Retail | Senior | 0 | 0 | −7.48 | 0.71 | 0.24 |
| Retail | Non-senior | 0 | 0 | −5.78 | 0.55 | 0.27 |

- `N = (Σ EAD_i)² / Σ EAD_i²` (s.6.6.1.7) [CRE 44.20]; `LGD = Σ LGD_i·EAD_i / Σ EAD_i` (s.6.6.1.8)
  [CRE 44.21].
- Simplified method (s.6.6.1.9) [CRE 44.22]: if `C1 ≤ 0.03`, LGD = 0.50 and
  `N = (C1·Cm + (Cm − C1)·max(1 − m·C1, 0)/(m − 1))⁻¹`, or `N = 1/C1`.
- Formula (s.6.6.1.10) [CRE 44.23]: `K_SEC-IRBA = (e^{a·u} − e^{a·l}) / (a·(u − l))`,
  `a = −1/(p·K_IRB)`, `u = D − K_IRB`, `l = max(A − K_IRB, 0)`.
- Risk weight [CRE 44.25]: D ≤ K_IRB → 1,250%; A ≥ K_IRB → 12.5 × K_SEC-IRBA; otherwise
  `RW = 12.5 × (K_IRB − A)/(D − A) + 12.5 × K_SEC-IRBA × (D − K_IRB)/(D − A)`.
- "The resulting risk weight is subject to a floor risk weight of 15%." [CRE 44.26]

**Worked examples reproduced in tests (Appendix 6-3, corporate receivables, N = 100, M_T = 2.5):**

| Example | K_IRB | LGD | A | D | Printed SEC-IRBA RW |
|---|---|---|---|---|---|
| 6-3.A Tranche A | 20.16% | 81.87% | 30% | 100% | 21.22% |
| 6-3.A Tranche B | 20.16% | 81.87% | 5% | 30% | 1013.85% |
| 6-3.A Tranche C | 20.16% | — | 0% | 5% | 1250% |
| 6-3.B Tranche B | 13.47% | 100% | 0% | 26.32% | 886.94% |
| 6-3.B Tranche A (i) | 6.69% | 45% | 5% | 100% | 51.67% |
| 6-3.B Tranche A′ | 13.47% | 100% | 30% | 100% | 11.16% |
| 6-3.B implicit Tranche A | | | | | MAX(15%, $1,193,985 / $950,000) = 125.68% |

### 1.6 SEC-ERBA (s.6.6.2) [CRE 42]
**Table 1: SEC-ERBA risk weights for short-term ratings** [CRE 42.2]

| A–1/P–1 | A–2/P–2 | A–3/P–3 | All other ratings |
|---|---|---|---|
| 15% | 50% | 100% | 1250% |

**Table 2: SEC-ERBA risk weights for long-term ratings** [CRE 42.4]

| Rating | Senior 1y | Senior 5y | Non-senior (thin) 1y | Non-senior (thin) 5y |
|---|---|---|---|---|
| AAA | 15% | 20% | 15% | 70% |
| AA+ | 15% | 30% | 15% | 90% |
| AA | 25% | 40% | 30% | 120% |
| AA− | 30% | 45% | 40% | 140% |
| A+ | 40% | 50% | 60% | 160% |
| A | 50% | 65% | 80% | 180% |
| A− | 60% | 70% | 120% | 210% |
| BBB+ | 75% | 90% | 170% | 260% |
| BBB | 90% | 105% | 220% | 310% |
| BBB− | 120% | 140% | 330% | 420% |
| BB+ | 140% | 160% | 470% | 580% |
| BB | 160% | 180% | 620% | 760% |
| BB− | 200% | 225% | 750% | 860% |
| B+ | 250% | 280% | 900% | 950% |
| B | 310% | 340% | 1050% | 1050% |
| B− | 380% | 420% | 1130% | 1130% |
| CCC+/CCC/CCC− | 460% | 505% | 1250% | 1250% |
| Below CCC− | 1250% | 1250% | 1250% | 1250% |

- "institutions shall use linear interpolation between the risk weights for one and five years."
- "Risk weight = [risk weight from table after adjusting for maturity] × [1 − min(T, 50%)] where T
  equals tranche thickness, and is measured as D minus A" [CRE 42.5].
- "The resulting risk weight is subject to a floor risk weight of 15%. In addition, the resulting risk
  weight should never be lower than the risk weight corresponding to a senior tranche of the same
  securitization with the same rating and maturity." [CRE 42.7]

### 1.7 SEC-IAA (s.6.6.3) [CRE 43]
"Internal assessments of exposures provided to ABCP programmes must be mapped to equivalent external
ratings of an ECAI. Those rating equivalents are used to determine the appropriate risk weights under
the SEC-ERBA" (Tables 1 and 2 above).

### 1.8 SEC-SA (s.6.6.4) [CRE 41]
- K_SA: weighted-average SA capital charge of the performing pool (Chapter 4 RWA ÷ exposure, excluding
  s.4.1.21 defaulted weights) × 8% [CRE 41.2]; W = delinquent / total, delinquent = 90+ days past due,
  bankruptcy, foreclosure, REO or default [CRE 41.6–41.7].
- `K_A = (1 − W) × K_SA + 0.5 × W`; with W unknown for ≤ 5%:
  `K_A = (EAD_known/EAD_total) × K_A,known + EAD_unknown/EAD_total`; unknown for > 5% → 1,250%
  [CRE 41.8–41.10].
- `K_SEC-SA = (e^{a·u} − e^{a·l}) / (a·(u − l))`, `a = −1/(p·K_A)`, `u = D − K_A`,
  `l = max(A − K_A, 0)` [CRE 41.11]; "p ... is set equal to 1 for a securitization exposure that is not
  a resecuritization exposure" [CRE 41.12].
- RW: D ≤ K_A → 1,250%; A ≥ K_A → 12.5 × K_SEC-SA; otherwise
  `RW = [(K_A − A)/(D − A) × 12.5] + [(D − K_A)/(D − A) × 12.5 × K_SEC-SA]` [CRE 41.14]; floor 15%
  [CRE 41.15]. An unrated junior exposure below rated senior tranches is not below the next more senior
  rated RW [CRE 41.15] (not modelled: needs the senior tranche's RW).

### 1.9 Caps (s.6.6.5) [CRE 40.50–40.55]
- **Senior look-through:** "the senior securitization exposure could receive a maximum risk weight
  equal to the exposure weighted-average risk weight applicable to the underlying exposures"; IRB
  weights include "the expected loss portion multiplied by 12.5"; SEC-SA/ERBA caps use SA weights.
  "Where the risk weight cap results in a lower risk weight than the floor risk weight of 15%, the risk
  weight resulting from the cap should be used." **⚠ VERIFY** — implemented as 12.5 × K (the contract
  carries no underlying average RW; exact for IRB pools, K_SA excludes defaulted exposures).
- **Maximum capital requirement:** SEC-IRBA users (any role) and originators using SEC-ERBA/SEC-SA:
  "The maximum aggregated capital requirement for an institution's securitization exposures in the
  same transaction will be equal to KP × P". For a single-tranche holding this is
  `RW_max = 12.5 × K / (D − A)`.
- "The caps ... cannot be applied to resecuritization exposures." [CRE 41.19]

### 1.10 Resecuritization (s.6.7) [CRE 41.16–41.19]
SEC-SA with "delinquencies (W) are set to zero for any exposure to a securitization tranche in the
underlying pool; and the supervisory parameter p is set equal to 1.5"; "subject to a floor risk weight
of 100%".

### 1.11 STC (s.6.10) [CRE 40.66–40.95, 41.20–41.22, 42.12–42.15, 44.27–44.29]
- "Only traditional securitizations (including exposures to ABCP conduits ...) fall within the scope".
- "Under all three approaches, the resulting risk weight is subject to a floor risk weight of 10% for
  senior tranches, and 15% for non-senior tranches."
- SEC-IRBA: `p = max[0.3; 0.5 × (A + B/N + C×K_IRB + D×LGD + E×M_T)]` (same A–E table).
- SEC-SA: "p ... is set equal to 0.5 for an exposure to an STC securitization."
- **Table 1′** (STC short-term): A–1/P–1 10%, A–2/P–2 30%, A–3/P–3 60%, all other 1,250%.
- **Table 2′** (STC long-term):

| Rating | Senior 1y | Senior 5y | Non-senior 1y | Non-senior 5y |
|---|---|---|---|---|
| AAA | 10% | 10% | 15% | 40% |
| AA+ | 10% | 15% | 15% | 55% |
| AA | 15% | 20% | 15% | 70% |
| AA− | 15% | 25% | 25% | 80% |
| A+ | 20% | 30% | 35% | 95% |
| A | 30% | 40% | 60% | 135% |
| A− | 35% | 40% | 95% | 170% |
| BBB+ | 45% | 55% | 150% | 225% |
| BBB | 55% | 65% | 180% | 255% |
| BBB− | 70% | 85% | 270% | 345% |
| BB+ | 120% | 135% | 405% | 500% |
| BB | 135% | 155% | 535% | 655% |
| BB− | 170% | 195% | 645% | 740% |
| B+ | 225% | 250% | 810% | 855% |
| B | 280% | 305% | 945% | 945% |
| B− | 340% | 380% | 1015% | 1015% |
| CCC+/CCC/CCC− | 415% | 455% | 1250% | 1250% |
| Below CCC− | 1250% | 1250% | 1250% | 1250% |

- Appendix 6-1 D1 (capital criteria): underlying SA RW ≤ 40% (RRE portfolio average), ≤ 50% (each CRE
  loan), ≤ 75% (each retail exposure), ≤ 100% (other, portfolio average); D2: single obligor ≤ 1%.
  STC eligibility is a caller input (`is_stc`).

### 1.12 NPL securitizations (s.6.12) [CRE 45.3–45.7]
- "An institution is precluded from applying the SEC-IRBA to an exposure to an NPL securitization where
  the institution uses the foundation approach" (flag `ca_kirb_foundation_irb`).
- "The risk weight applicable to exposures to NPL securitizations according to SEC-IRBA ..., SEC-SA ...
  or the look-through approach ... is floored at 100%."
- "an institution may apply a risk weight of 100% to the senior tranche of an NPL securitization
  provided that the NPL securitization is a traditional securitization and the sum of the
  non-refundable purchase price discounts (NRPPD) ... is equal to or higher than 50% of the outstanding
  balance of the pool" (flag `ca_npl_nrppd_at_least_50pct`).

---

## 2. SA-CVA — CAR Chapter 8 s.8.3 [MAR 50.27–50.77]

- Eligibility: "Institutions must use the BA-CVA unless they receive approval from OSFI to use the
  SA-CVA" (s.8.1). Materiality alternative: aggregate non-centrally-cleared notional "less than or equal
  to $150 billion" (CAD; Basel MAR 50.9: EUR 100 billion).
- s.8.3.3: "The multiplier mcva is set at 1. OSFI may require an institution to use a higher value".
- s.8.3.4: delta = simple sum over IR, FX, counterparty credit spread, reference credit spread, equity,
  commodity; vega = simple sum over the same less counterparty credit spread.
- `WS_k^CVA = RW_k·s_k^CVA`, `WS_k^Hdg = RW_k·s_k^Hdg`, `WS_k = WS_k^CVA − WS_k^Hdg`.
- "R is the hedging disallowance parameter, set at 0.01":
  `K_b = √[(Σ_k WS_k² + Σ_k Σ_{l≠k} ρ_kl WS_k WS_l) + R·Σ_k (WS_k^Hdg)²]`;
  `K = m_CVA·√[Σ_b K_b² + Σ_b Σ_{c≠b} γ_bc S_b S_c]`; `S_b = max{−K_b; min(Σ_k WS_k; K_b)}`.
  (The square roots are lost in the flattened CAR text; the formula is identical to the Basel MAR 50.53
  image, rendered from the Basel Framework PDF p.738.)

### 2.1 Interest rate (s.8.3.5)
Buckets per currency; γ_bc = 0.5. Specified currencies (reporting currency, USD, EUR, GBP, AUD, CAD,
SEK, JPY): tenors 1, 2, 5, 10, 30 years and inflation.

**Table 3** — 1y 1.11% · 2y 0.93% · 5y 0.74% · 10y 0.74% · 30y 0.74% · inflation 1.11%.

**Table 4** (correlations):

| | 1y | 2y | 5y | 10y | 30y | Inflation |
|---|---|---|---|---|---|---|
| 1y | 100% | 91% | 72% | 55% | 31% | 40% |
| 2y | | 100% | 87% | 72% | 45% | 40% |
| 5y | | | 100% | 91% | 68% | 40% |
| 10y | | | | 100% | 83% | 40% |
| 30y | | | | | 100% | 40% |
| Inflation | | | | | | 100% |

Other currencies: parallel curve shift and inflation, RW 1.58% each, correlation 40%. Vega: IR and
inflation volatilities RW 100%, correlation 40%.

### 2.2 FX (s.8.3.6)
Buckets per currency except the reporting currency; γ = 0.6; delta RW 11%; vega RW 100%.

### 2.3 Counterparty credit spread (s.8.3.7) — delta only
**Table 5**: 1 a) sovereigns incl. central banks, MDBs; b) local government, government-backed
non-financials, education and public administration · 2 financials incl. government-backed financials
· 3 basic materials, energy, industrials, agriculture, manufacturing, mining and quarrying · 4 consumer
goods and services, transportation and storage, administrative and support service activities · 5
technology, telecommunications · 6 health care, utilities, professional and technical activities · 7
other sector · 8 qualified indices. Tenors 0.5, 1, 3, 5, 10 years.

**Table 6** (γ_bc):

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

**Table 7** (RW):

| Bucket | 1 a) | 1 b) | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| IG names | 0.5% | 1.0% | 5.0% | 3.0% | 3.0% | 2.0% | 1.5% | 5.0% | 1.5% |
| HY and NR names | 2.0% | 4.0% | 12.0% | 7.0% | 8.5% | 5.5% | 5.0% | 12.0% | 5.0% |

ρ_kl = ρ_tenor·ρ_name·ρ_quality. Buckets 1–7: ρ_tenor 100%/90%; ρ_name 100% same, 90% "distinct, but
legally related", 50% otherwise; ρ_quality 100%/80%. Bucket 8: ρ_name 100% same index and series, 90%
same index distinct series, 80% otherwise.

### 2.4 Reference credit spread (s.8.3.8) — delta and vega
**Table 8**: 1–7 IG (sectors as Table 5 rows 1a, 1b, 2–6), 8–14 HY and NR (same sectors), 15 other
sector, 16 IG qualified indices, 17 HY qualified indices.

**Table 9** (γ_bc, same credit quality; for buckets 1–14 of different quality divide by 2):

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

**Table 10** (delta RW): 1 0.5% · 2 1.0% · 3 5.0% · 4 3.0% · 5 3.0% · 6 2.0% · 7 1.5% · 8 2.0% · 9 4.0%
· 10 12.0% · 11 7.0% · 12 8.5% · 13 5.5% · 14 5.0% · 15 12.0% · 16 1.5% · 17 5.0%. (The flattened table
labels rows 8–9 "IG" and 16–17 "HY/NR", inconsistent with Table 8; the bucket numbers and values match
Table 8 and MAR 50.68 and are used as printed.) Vega RW 100%. One risk factor per bucket.

### 2.5 Equity (s.8.3.9)
"'Large market cap' is defined as a market capitalization equal to or greater than **$2.5 billion**"
(CAD; Basel MAR 50.70: USD 2 billion). Advanced economies: Canada, US, Mexico, euro area, UK, Norway,
Sweden, Denmark, Switzerland, Japan, Australia, New Zealand, Singapore, Hong Kong SAR.

**Table 11**: 1–4 large, emerging markets (1 consumer/transport/admin/healthcare/utilities; 2 telecom,
industrials; 3 basic materials/energy/agriculture/manufacturing/mining; 4 financials/real estate/
technology); 5–8 large, advanced economies (same sectors); 9 small EM; 10 small advanced; 11 other
sector; 12 large cap advanced economies qualified indices; 13 other qualified indices.

**Table 12** (delta RW): 1 55% · 2 60% · 3 45% · 4 55% · 5 30% · 6 35% · 7 40% · 8 50% · 9 70% · 10 50% ·
11 70% · 12 15% · 13 25%. Vega: "78% for large market capitalization buckets and to 100% for the other
buckets" (buckets 1–8 and 12, whose Table 11 size is "Large"/"Large cap").

γ: 15% within 1–10; 75% between 12 and 13; 45% between 12/13 and 1–10; 0% with bucket 11.

### 2.6 Commodity (s.8.3.10)
**Table 13**: 1 energy – solid combustibles · 2 energy – liquid combustibles · 3 energy – electricity
and carbon trading · 4 freight · 5 metals – non-precious · 6 gaseous combustibles · 7 precious metals
(including gold) · 8 grains & oilseed · 9 livestock & dairy · 10 softs and other agricultural · 11 other.

**Table 14** (delta RW): 1 30% · 2 35% · 3 60% · 4 80% · 5 40% · 6 45% · 7 20% · 8 35% · 9 25% · 10 35% ·
11 50%. Vega RW 100%. γ: 20% within 1–10; 0% with bucket 11.

---

## 3. CCP exposures — CAR Chapter 7 s.7.1.8 [CRE 54]

- Non-qualifying status: "Within three months of a central counterparty ceasing to qualify as a QCCP,
  ... the trades with a former QCCP may continue to be capitalized as though they are with a QCCP."
- **Clearing member trade exposures** (A(i)): "a risk weight of 2% must be applied to the institution's
  trade exposure to the CCP in respect of OTC derivatives, exchange-traded derivative transactions,
  SFTs and long-settlement transactions"; MPOR ≥ 10 days for OTC derivatives; no 20-day large-netting-
  set floor.
- **Clearing member exposures to clients** (A(ii)): bilateral, with "a margin period of risk of at least
  five days"; no CVA capital when cleared through a QCCP.
- **Client exposures** (A(iii)): clearing-member treatment (2%) when the two protection conditions are
  met; "Where a client is not protected from losses in the case that the clearing member and another
  client of the clearing member jointly default ..., a risk weight of 4% will apply" (OSFI prints
  "[Basel Framework, CRE 53.16]"; the Basel paragraph is CRE 54.16); otherwise bilateral.
- **Posted collateral** (A(iv)): own risk weight; CCR 2% / 2% / 4% when not bankruptcy remote; zero if
  "held by a custodian; and bankruptcy remote from the CCP".
- **Default fund** (B):
  - `K_CCP = Σ_CM_i EAD_i × RW × capital ratio`, "RW is a risk weight of 20%" (footnote 47: "The 20%
    risk weight is a minimum requirement ... OSFI may increase the risk weight"), "Capital ratio means
    8%".
  - Derivatives EAD_i: SA-CCR with a 10-day MPOR; SFTs: `EAD_i = max(EBRM_i − IM_i − DF_i; 0)`.
  - `K_CM_i = max(K_CCP × DF_i^pref / (DF_CCP + DF_CM^pref); 8% × 2% × DF_i^pref)`.
- **Cap** (C): "Where the sum of an institution's capital charges for exposures to a qualifying CCP due
  to its trade exposure and default fund contribution is higher than the total capital charge that would
  be applied to those same exposures if the CCP were for a non-qualifying CCP ..., the latter total
  capital charge shall be applied."
- **Non-qualifying CCPs** (s.7.1.8.2): "the standardized approach for credit risk in Chapter 4,
  according to the category of the counterparty" for trade exposures; "Institutions must deduct from
  CET1 capital their amount of default fund contributions to a non-qualifying CCP" (funded and
  unfunded). Engine: 12.5 × DF RWA-equivalent; unrated CCP without SCRA grade → Grade C 150%
  **⚠ VERIFY** (conservative default).
- RWA = 12.5 × capital: CAR Ch.1 s.1.3 ("multiplying the capital requirements ... by 12.5").

---

## 4. Leverage exposure measure — OSFI Leverage Requirements Guideline (2023)

### 4.1 Requirement (s.IV)
- "Institutions are expected to maintain a leverage ratio that meets or exceeds 3% at all times."
  [LEV 20.7]
- Authorized leverage ratios: prescribed bilaterally, "considered supervisory information" (not
  modelled; `leverage_requirement(authorized_ratio=...)` takes the higher).
- D-SIBs: "The leverage ratio buffer will be set at 50% of a D-SIB's higher-loss absorbency risk-
  weighted requirements. For example, a D-SIB subject to a 1% higher-loss absorbency requirement would
  be subject to a 0.5% leverage ratio buffer requirement. This means that DSIBs are expected to maintain
  a leverage ratio that meets or exceeds 3.5% at all times." [LEV 40.2] Met with Tier 1.
- **Table 1** (D-SIB, first HLA bucket):

| CET1 risk-based ratio | Tier 1 leverage ratio | Minimum capital conservation ratio |
|---|---|---|
| 4.5%–5.375% | 3%–3.125% | 100% |
| > 5.375%–6.25% | > 3.125%–3.25% | 80% |
| > 6.25%–7.125% | > 3.25%–3.375% | 60% |
| > 7.125%–8.0% | > 3.375%–3.50% | 40% |
| > 8.0% | > 3.50% | 0% |

These confirm the CAR values used in `src/jurisdictions/ca/params.py` (3% minimum; D-SIB 3.5%); the
previous `TODO: VERIFY` there is resolved, and the D-SIB leverage buffer is now 50% of the applicable
HLA (the higher of the 1% D-SIB and any G-SIB surcharge) in `capital_stack.py`.

### 4.2 Exposure measure (s.VI) [LEV 20.5, 30]
Total = on-balance sheet + derivatives + SFTs + off-balance sheet.

- On-balance sheet: gross values net of specific provisions; "balance sheet assets deducted from
  Common Equity Tier 1 (CET1) capital or Additional Tier 1 capital ... may be deducted"; general
  provisions that reduced Tier 1 may be deducted; liability items not deducted; derecognised CMHC/
  private-insured mortgage whole-loan sales and NHA MBS (with CMHC non-objection) may be excluded
  (OSFI-specific; handled by the caller's balance sheet input).
- Derivatives (paragraph 37): "Institutions must calculate their derivative exposures, including where
  an institution sells protection using a credit derivative, as a scalar multiplier alpha set at 1.4,
  multiplied by the sum of the replacement cost (RC) ... and an add-on for potential future exposure
  (PFE), as described in section 7.1.7 of the CAR Guideline." SWWR treatment not applied. The Basel
  LEV30.15–30.24 leverage modifications (PFE multiplier fixed at one; RC reducible only by eligible cash
  VM; collateral received not netted) **do not appear in the OSFI text** (checked in both the text and
  raw HTML). Cash margin posted recognised as an asset may be deducted (paragraph 38) — no contract
  input. **⚠ VERIFY** — PFE multiplier taken as 1 (V − C not in the contract; conservative).
- Clearing (paragraphs 39–41): the CM need not include QCCP trade exposures where it is not obliged to
  reimburse the client for QCCP default losses; multi-level client conditions.
- Written credit derivatives (paragraphs 42–49): effective notional, reduced by negative fair-value
  changes in Tier 1 and by eligible purchased protection on the same reference name; also by "any cash
  independent amount pledged by a counterparty" (OSFI addition).
- SFTs (paragraph 53): gross SFT assets with no accounting netting, less securities received recognised
  as assets, with cash payables/receivables netted only under the three criteria; plus
  `E' = max(0, Σ E_i − Σ C_i)` under a qualifying MNA, else `E_i' = max(0, E_i − C_i)`.
- Central bank reserves: "OSFI may temporarily exempt central bank reserves from the leverage ratio
  exposure measure in exceptional macroeconomic circumstances ... OSFI will also increase the
  calibration of the minimum leverage ratio requirement commensurately" [LEV 30.7].
- Off-balance sheet CCFs (paragraphs 61–75):

| Item | CCF |
|---|---|
| Unconditionally cancellable commitments (excl. paragraph 72) | 10% [LEV 30.54] |
| Undrawn credit card and charge card balances | **25%** (OSFI-specific) |
| Commitments, regardless of maturity | 40% [LEV 30.52] |
| Short-term self-liquidating trade letters of credit | 20% [LEV 30.53] |
| Transaction-related contingent items | 50% [LEV 30.51] |
| NIFs and RUFs | 50% [LEV 30.50] |
| Direct credit substitutes, acceptances | 100% [LEV 30.49] |
| Forward asset purchases, forward deposits, partly paid shares | 100% [LEV 30.49] |
| Unsettled purchases (settlement-date accounting) | 100% [LEV 30.49] |
| Other credit substitutes | 100% [LEV 30.49] |

"Where there is an undertaking to provide a commitment on an OBS item, institutions are to apply the
lower of the two applicable CCFs." Off-balance sheet securitisation exposures follow CAR s.6.5.1.1.

---

## 5. Large exposures — OSFI Guideline B-2 (2028), consultation draft

**Scope (s.II):** "all institutions designated by OSFI as domestic systemically important banks
(D-SIBs); and small and medium-sized deposit-taking institutions (SMSBs) that fall into Category I and
II", consolidated (excluding insurance subsidiaries); Category III SMSBs and foreign bank branches
excluded. Capital base: Tier 1. **⚠ VERIFY** — all values are from the draft.

- Definition (s.III): "An exposure is considered a large exposure when the sum of all the exposures to a
  single counterparty or group of connected counterparties equals or exceeds 10% of the institution's
  Tier 1 capital." Reporting includes exempt exposures meeting the definition (intra-day interbank
  excepted, footnote 10) and the 20 largest exposures.
- Limits (s.IV):

| Reporting institution | Counterparty / group includes | Limit (% Tier 1) |
|---|---|---|
| Canadian G-SIB | a G-SIB | 15% |
| Canadian G-SIB | a Canadian D-SIB that is not a G-SIB | 20% |
| Canadian G-SIB | other | 25% |
| Canadian D-SIB (not G-SIB) | a Canadian D-SIB or a G-SIB | 20% |
| Canadian D-SIB (not G-SIB) | other | 25% |
| Category I/II SMSB | any | 25% |

  Newly designated G-SIBs: 15% within 12 months of the FSB list (footnote 12).
- Exemptions (s.V): (a) amounts deducted from capital (except BFI investments; footnote 16: 1,250%
  exposures are not exempt); (b) Government of Canada and Bank of Canada; (c) Level 1 HQLA; (d) 0% RW
  sovereigns/central banks, domestic currency; (e) other 0% entities under s.4.1.1; (f) Canadian PSEs
  treated as sovereign, US PSEs in conservatorship (OSFI approval), foreign 0% PSEs in domestic currency;
  (g) 0% MDBs; (h) capital/TLAC underwriting ≤ 5 working days; (i) Other TLAC of G-SIBs/D-SIBs under
  market making; (j) intra-day interbank; (k) QCCP clearing exposures.
- Exposure measure (s.VI): on-balance net of specific allowances; off-balance with CAR s.4.1.18 CCFs
  "subject to a minimum value of 10%"; SA-CCR for CCR; comprehensive approach with supervisory haircuts
  for SFTs; trading book gross JTD with 100% LGD.
- Covered bonds (paragraphs 27–28): qualifying ≥ 25% of nominal (cover pool RRE RW ≤ 35% and LTV ≤ 80%,
  CRE RW ≤ 100% and LTV ≤ 60%, over-collateralization ≥ 5%); non-qualifying 100%.
- CCP clearing exposures (paragraph 30): trade exposures per s.VI; segregated IM 0; non-segregated IM
  nominal; pre-funded DF nominal; unfunded DF 0; equity stakes nominal.
- Structured vehicles (paragraph 48): look-through threshold 0.25% of Tier 1 (Category I/II SMSBs:
  max(0.25% of Tier 1, $1.5 million)).
- Connected counterparties (s.VII): thorough economic-interdependence investigation where an exposure
  exceeds 5% of Tier 1.

---

## 6. Material differences from the Basel Framework

1. **SA-CVA equity large-cap threshold** CAD 2.5 billion (CAR s.8.3.9) vs USD 2 billion (MAR 50.70).
2. **CVA materiality threshold** CAD 150 billion (CAR s.8.1) vs EUR 100 billion (MAR 50.9).
3. **Leverage derivatives** use the unmodified CAR s.7.1.7 SA-CCR (LR paragraph 37): no fixed PFE
   multiplier of one, no cash-VM-only RC rule (Basel LEV30.15–30.24 absent).
4. **Leverage credit cards**: 25% CCF on undrawn credit and charge card balances (LR) vs 10% UCC under
   LEV30.54.
5. **Leverage exclusions**: derecognised insured mortgage whole-loan sales and NHA MBS (OSFI-specific);
   cash independent amounts reduce written credit derivative notionals.
6. **D-SIB leverage buffer**: 50% of the D-SIB HLA (3.5% with the 1% D-SIB surcharge); Basel LEV40
   applies the buffer to G-SIBs only.
7. **Large exposures, D-SIB tier**: 20% limit between Canadian D-SIBs (and D-SIB ↔ G-SIB, G-SIB → D-SIB),
   absent from LEX (25% / 15%).
8. **Large exposures scope**: Category I/II SMSBs subject to a 25% limit with a structured-vehicle
   threshold floor of $1.5 million; Government of Canada, Bank of Canada and Level 1 HQLA exemptions.
9. **Securitization under the capital floor** (s.6.11): SEC-IRBA and SEC-IAA ineligible; caps only with
   the pool treated as SA (OSFI-specific; Basel RBC20.11 is general).
10. **Tranche maturity** (s.6.2.1.16): OSFI cash-flow method prescribes prepayment assumptions with a 20%
    annual cap and a revolving-period maturity adjustment (not in CRE40.22).
11. **NHA MBS** without tranching are outside the securitization framework (Chapter 4, 0%).
12. **I/O strips**: credit-enhancing I/O strips 1,250%, other unrated I/O strips 250% (prepayment risk)
    or 100% (OSFI-specific additions to the gain-on-sale deduction OSFI cites as CAP 30.14, which in the
    Basel text covers only the deduction of securitisation gains on sale).
13. **K_CCP risk weight** 20% "is a minimum" that OSFI may raise (footnote 47).
14. **Large exposures source status**: B-2 (2028) is a consultation draft effective from
    November 2027 / January 2028; the limits may change in the final guideline.

Unchanged from Basel (cell-by-cell): SEC-IRBA p table, SEC-ERBA Tables 1/2/1′/2′, SEC-SA/resec p and
floors, STC floors, NPL treatment, SA-CVA risk weights and correlations (other than the market-cap
threshold), K_CCP / K_CM, QCCP 2% / 4%.

---

## 7. Contract inputs read from `flags`

| Flag | Section |
|---|---|
| `ca_capital_floor_calculation`, `ca_irb_pool_excess_spread_as_sa`, `ca_iaa_approved`, `ca_kirb_foundation_irb`, `ca_delinquency_unknown_over_5pct`, `ca_npl_nrppd_at_least_50pct`, `ca_senior_look_through`, `ca_apply_max_capital_cap`, `ca_is_originator` | Securitization |
| `ca_central_bank_reserves_exemption` | Leverage |
| `ca_counterparty_is_canadian_dsib`, `ca_rw_1250`, `ca_exempt_*` (13 keys, s.V) | Large exposures |
| `ca_former_qccp_within_3_months`, `ca_client_conditions_not_met`, `ca_client_not_protected_joint_default`, `ca_ccp_treated_as_corporate`, `ca_ccp_scra_grade_a/b` | CCP |

SA-CVA naming convention: counterparty credit spread names sharing the prefix before `::` are
"distinct, but legally related" (buckets 1–7) or the same index with a different series (bucket 8).
