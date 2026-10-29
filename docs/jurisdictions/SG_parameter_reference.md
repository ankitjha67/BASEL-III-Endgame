# Singapore — MAS Notice 637 Parameter Reference

**Source:** MAS Notice 637, *Notice on Risk Based Capital Adequacy Requirements for Banks
Incorporated in Singapore* (Banking Act 1970), 20 September 2023, last revised 9 October 2025
(version effective 1 January 2026), 1,110 pp.

**Code:** `src/jurisdictions/sg/` (`SGRegime`, `Jurisdiction.SG`). Every constant in
`src/jurisdictions/sg/params.py` cites one of the provisions below.

**Conventions.**
- Page numbers are the Notice's own footers (e.g. "p. 7-42").
- "Credit quality grade" (CQG) 1–6 is defined by Table 7M-1. Short-term grades I–IV are
  defined by Table 7M-2.
- Absolute thresholds are stated in Singapore dollars (S$). The engine takes inputs already
  converted to SGD millions.
- Values are transcribed verbatim. Items the text does not settle are marked
  **TODO: VERIFY** and listed in §15.

---

## 1. Capital adequacy ratios — Part IV Division 1

### 1.1 CAR definitions (paras 4.1.1–4.1.4, p. 4-1)

```
CET1 CAR  = CET1 Capital            / (Credit RWA + Market RWA + Operational RWA)
Tier 1 CAR = Tier 1 Capital         / (Credit RWA + Market RWA + Operational RWA)
Total CAR  = Eligible Total Capital / (Credit RWA + Market RWA + Operational RWA)
```
Para 4.1.4 says the denominators are "the higher of – (a) the sum of credit RWA, market RWA, and
operational RWA, calculated using the Reporting Bank's nominated approaches; and (b) its output
floor calculated in accordance with Part V."

### 1.2 Table 4-1 — Minimum ratios for a D-SIB (para 4.1.5, p. 4-1)

| | Minimum CAR |
|---|---|
| Minimum CET1 CAR | 6.5% |
| Minimum Tier 1 CAR | 8% |
| Minimum Total CAR | 10% |

These minimums apply "at all times ... at both the Solo and Group levels". The list of D-SIBs
is published on the MAS website (footnote 38).

### 1.3 Table 4-2 — Minimum ratios for a non-D-SIB (para 4.1.6, p. 4-2)

| | Minimum CAR |
|---|---|
| Minimum CET1 CAR | 4.5% |
| Minimum Tier 1 CAR | 6% |
| Minimum Total CAR | 8% |

### 1.4 Capital conservation buffer (para 4.1.7, p. 4-2)

"a capital conservation buffer comprising CET1 Capital of 2.5% of the relevant denominators as
determined in paragraph 4.1.4."

### 1.5 Table 4-3 — Minimum capital conservation ratios, D-SIB (p. 4-4)

| CET1 CAR | Minimum capital conservation ratio (% of earnings) |
|---|---|
| first quartile of buffer: 6.5% - 7.125% | 100% |
| second quartile of buffer: >7.125% - 7.75% | 80% |
| third quartile of buffer: >7.75% - 8.375% | 60% |
| fourth quartile of buffer: >8.375% - 9% | 40% |
| Above top of buffer: >9% | 0% |

### 1.6 Table 4-4 — Minimum capital conservation ratios, non-D-SIB (p. 4-4)

| CET1 CAR | Ratio |
|---|---|
| first quartile of buffer: 4.5% - 5.125% | 100% |
| second quartile of buffer: >5.125% - 5.75% | 80% |
| third quartile of buffer: >5.75% - 6.375% | 60% |
| fourth quartile of buffer: >6.375% - 7% | 40% |
| Above top of buffer: >7% | 0% |

### 1.7 Countercyclical buffer (paras 4.1.17–4.1.32, pp. 4-5 to 4-11)

- Para 4.1.17 sets "a countercyclical buffer comprising CET1 Capital ranging from zero up to 2.5%
  of the relevant denominators ... can be 0% at a particular point in time."
- Para 4.1.18(a)(ii) covers rates set in foreign jurisdictions: they are applied "subject to a cap
  of 2.5% unless the Authority specifies that the cap does not apply or that a higher
  country-specific countercyclical buffer requirement applies".
- Para 4.1.19 defines the buffer as the "weighted average of the country-specific countercyclical
  buffer requirements". Each weight is the RWA for private sector credit exposures in that
  jurisdiction divided by the RWA for all private sector credit exposures.
- Para 4.1.21 gives a weight of zero to (a) a relevant jurisdiction with zero exposure and
  (b) a jurisdiction that is not a relevant jurisdiction (a relevant jurisdiction is a BCBS
  member or one specified by MAS, para 4.1.20).
- Para 4.1.29 sets the Singapore-specific rate at between zero and 2.5%. Para 4.1.30 says MAS
  may set it higher than 2.5%.

### 1.8 Table 4-5 — Ratios with a countercyclical buffer (para 4.1.25, p. 4-9)

| CET1 CAR | Ratio |
|---|---|
| ≤ applicable minimum CET1 CAR + ¼ of buffer | 100% |
| > min + ¼ buffer, ≤ min + ½ buffer | 80% |
| > min + ½ buffer, ≤ min + ¾ buffer | 60% |
| > min + ¾ buffer, ≤ min + buffer | 40% |
| Above top of buffer | 0% |

### 1.9 Table 4-6 — D-SIB with a 2.5% countercyclical buffer (p. 4-9)

| CET1 CAR | Ratio |
|---|---|
| 6.5% - 7.75% | 100% |
| >7.75% - 9% | 80% |
| >9% - 10.25% | 60% |
| >10.25% - 11.5% | 40% |
| >11.5% | 0% |

### 1.10 Table 4-7 — Non-D-SIB with a 2.5% countercyclical buffer (p. 4-9)

| CET1 CAR | Ratio |
|---|---|
| 4.5% - 5.75% | 100% |
| >5.75% - 7% | 80% |
| >7% - 8.25% | 60% |
| >8.25% - 9.5% | 40% |
| >9.5% | 0% |

### 1.11 D-SIB / G-SIB buffer

Part IV contains no separate D-SIB higher loss absorbency buffer rate. The D-SIB loading is the
2-percentage-point uplift in the Table 4-1 minimums over Table 4-2. Annex 11A row 64 (p. 11-148)
describes the bank-specific buffer requirement as "(iv) the buffer requirement for G-SIBs and/or
D-SIBs (if applicable)". The code therefore accepts an input rate, which defaults to 0%.

## 2. Leverage ratio — Part IV Division 2 (p. 4-12)

Para 4.2.2: "A Reporting Bank must, at all times, maintain at both the Solo and Group levels, a
minimum leverage ratio of 3%."

Annex 11D row 27 (p. 11-164) says: "the Reporting Bank must include the D-SIB leverage ratio buffer
requirement and any other applicable buffers". The Notice sets no rate for this buffer
(**TODO: VERIFY**).

## 3. Output floor — Part V (pp. 5-1 to 5-4)

Para 5.1.1: "output floor as the sum of its credit RWA, market RWA, and operational RWA,
calculated using only standardised approaches, multiplied by the output floor calibration."

Table 5-1 maps each nominated approach to its standardised approach. For example, IRBA maps to
SA(CR); IMM maps to SA-CCR (derivatives) or FC(CA) (SFTs); IMA maps to SA(MR); SEC-IRBA/SEC-IAA
map to the SEC-ERBA/SEC-SA/1250% hierarchy.

### Table 5-3 — Output floor calibration (para 5.1.6, p. 5-4)

| Period | Output floor calibration |
|---|---|
| From 1 July 2024 to 31 December 2024 | 50% |
| From 1 January 2025 to 31 December 2025 | 55% |
| From 1 January 2026 to 31 December 2026 | 60% |
| From 1 January 2027 to 31 December 2027 | 65% |
| From 1 January 2028 to 31 December 2028 | 70% |
| From 1 January 2029 onwards | 72.5% |

Para 5.1.6 allows "such other higher percentage (in any case, not more than 100%) as the
Authority may determine". The Notice has no transitional cap on the increase in RWA (compare
BCBS RBC90.2).

**Annex 4A, Table 4A-1 (p. 4-13), worked example:** nominated-approach RWA is 76 and
standardised RWA is 140. The floor is 72.5% × 140 = 101.5, which binds.

## 4. SA(CR) categorisation — para 7.3.1 (pp. 7-23 to 7-27)

| Para 7.3.1 | Asset class / sub-class |
|---|---|
| (a) | cash items (cash and cash equivalents; gold bullion backed by gold bullion liabilities) |
| (b) | central government and central bank (incl. BIS, IMF, ECB, EU, ESM, EFSF) |
| (c) | PSE |
| (d) | MDB |
| (e) | bank (banks, merchant banks, finance companies, predominantly banking DFHCs, foreign securities firms / FIs risk-weighted as banks) |
| (f) | covered bond (eligible covered bonds, para 7.3.2) |
| (g)(i) | general corporate |
| (g)(ii) | corporate SME — exposure to a small business (reported annual revenue ≤ S$100 million, para 7.3.4) |
| (g)(iii) | specialised lending (project, object, commodities finance, para 7.3.7) |
| (h) | equity and subordinated debt (subordinated debt 7.3.8, equity 7.3.9–7.3.10, regulatory capital instruments 7.3.14) |
| (i) | regulatory retail: (A) transactor, (B) non-transactor. Conditions (iii) "not more than S$2 million" and (iv) "less than or equal to 0.2%" of the pool |
| (j) | other retail (individuals only) |
| (k)(i) | ADC |
| (k)(ii) | regulatory real estate (para 7.3.17 conditions) |
| (k)(iii) | other real estate |
| (l) | other exposures (250% under 6.1.5(p)(iii); 400% under 6.1.6; lessor residual value; right-of-use assets) |

## 5. Credit quality grades — Annex 7M (p. 7-271)

### Table 7M-1 — Credit Quality Grades for SA(CR) Exposures

| CQG | Fitch / S&P | Moody's |
|---|---|---|
| 1 | AAA, AA+, AA, AA- | Aaa, Aa1, Aa2, Aa3 |
| 2 | A+, A, A- | A1, A2, A3 |
| 3 | BBB+, BBB, BBB- | Baa1, Baa2, Baa3 |
| 4 | BB+, BB, BB- | Ba1, Ba2, Ba3 |
| 5 | B+, B, B- | B1, B2, B3 |
| 6 | CCC+, CCC, CCC-, CC, C, D | Caa1, Caa2, Caa3, Ca, C |

### Table 7M-2 — Credit Quality Grades for Short-term SA(CR) Exposures

| Short-term CQG | I | II | III | IV |
|---|---|---|---|---|
| Fitch | F-1 | F-2 | F-3 | Others |
| Moody's | P-1 | P-2 | P-3 | Others |
| S&P | A-1 | A-2 | A-3 | Others |

Para 1.1 adds that S&P A-1 includes A-1+ and A-1–, and that "Others" includes all non-prime and
B or C ratings. The recognised ECAIs are Fitch Ratings, Moody's Investor Services and Standard &
Poor's Ratings Services (Annex 7N).

## 6. SA(CR) risk weights — Part VII Division 3 Sub-division 3

### 6.1 Cash items (paras 7.3.40–7.3.41, p. 7-42)

- Cash items: 0%.
- Cash equivalents (cheques, drafts and other items drawn on other banks ... payable on
  presentation or in the process of collection): 20%.

### 6.2 Table 7-1 — Central Government and Central Bank (para 7.3.42, p. 7-42)

| CQG | 1 | 2 | 3 | 4 | 5 | 6 | Unrated |
|---|---|---|---|---|---|---|---|
| RW | 0% | 20% | 50% | 100% | 100% | 150% | 100% |

- Para 7.3.43: 0% for the Singapore Government or MAS "denominated in Singapore dollars and funded
  by liabilities denominated in Singapore dollars".
- Para 7.3.44: for other sovereigns in local currency, local-currency funded, the bank "may apply
  such risk weights as may be specified by the bank regulatory agency".
- Para 7.3.46: 0% for the BIS, IMF, ECB, EU, ESM and EFSF.

### 6.3 Table 7-2 — PSE (para 7.3.47, p. 7-42)

| CQG | 1 | 2 | 3 | 4 | 5 | 6 | Unrated |
|---|---|---|---|---|---|---|---|
| RW | 20% | 50% | 50% | 100% | 100% | 150% | 50% |

### 6.4 Table 7-3 — PSEs where the central government has CQG "1" or "2" (para 7.3.48, p. 7-43)

| PSE CQG | 1 | 2 | 3 | 4 | 5 | 6 | Unrated |
|---|---|---|---|---|---|---|---|
| Central government CQG "1" | 0% | 0% | 0% | 100% | 100% | 150% | 0% |
| Central government CQG "2" | 20% | 20% | 20% | 100% | 100% | 150% | 20% |

Para 7.3.49: a Singapore PSE is treated as the Singapore Government only if it is a statutory
board (other than MAS).

### 6.5 Table 7-4 — MDB (para 7.3.50, p. 7-43)

| CQG | 1 | 2 | 3 | 4 | 5 | 6 | Unrated |
|---|---|---|---|---|---|---|---|
| RW | 20% | 30% | 50% | 100% | 100% | 150% | 50% |

Para 7.3.51: 0% for qualifying MDBs. Annex 7O lists AfDB, ADB, AIIB, CDB, CEB, EBRD, EIB, EIF,
IDB, IsDB, NIB, IFFIm and the World Bank Group.

### 6.6 Table 7-5 — Bank, rated (para 7.3.52, p. 7-44)

| CQG | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| Risk Weight | 20% | 30% | 50% | 100% | 100% | 150% |
| Risk Weight for Short-Term Exposures | 20% | 20% | 20% | 50% | 50% | 150% |

Short-term means "(a) exposures with an original maturity of 3 months or less; (b) exposures that
arise from the movement of goods across national borders with an original maturity of 6 months
or less."

Para 7.3.53: ratings that assume implicit government support may be used "up to 31 December
2028". From 1 January 2029 they may not be used, unless the rating is of a public bank owned by
its government.

### 6.7 Table 7-6 — Short-term bank exposures with issue-specific assessments (para 7.3.54, p. 7-44)

| Short-term CQG | I | II | III | IV |
|---|---|---|---|---|
| RW | 20% | 50% | 100% | 150% |

Para 7.3.55 sets two floors for unrated exposures to the same entity:
- If a rated short-term issue attracts 50% or 100%, an unrated short-term exposure takes no less
  than 100%.
- If a rated short-term issue attracts 150%, any unrated exposure takes 150%.

### 6.8 Table 7-7 — Bank, unrated (para 7.3.58, p. 7-46)

| Credit risk assessment grade | Grade A | Grade B | Grade C |
|---|---|---|---|
| Risk Weight | 40% | 75% | 150% |
| Risk Weight for Short-Term Exposures | 20% | 50% | 150% |

- Para 7.3.59: 30% instead of 40% for Grade A where "(a) ... Common Equity Tier 1 ratio which meets
  or exceeds 14%; and (b) ... Tier 1 leverage ratio which meets or exceeds 5%."
- Para 7.3.60 sets the grade criteria:
  - **A:** meets published minimums and buffers.
  - **B:** meets published minimums, excluding buffers.
  - **C:** fails the minimums, or has an adverse or going-concern audit opinion. A bank whose
    requirements are not publicly available is Grade B or C.
- Para 7.3.62: the weight is the higher of Table 7-7 and the weight of the sovereign of
  incorporation where the exposure is not in the counterparty's local currency (or the branch's
  local currency).
- Para 7.3.63: self-liquidating trade items arising from the movement of goods with an original
  maturity below one year are exempt.

### 6.9 Table 7-8 — Covered bonds with issue-specific assessments (para 7.3.64, p. 7-48)

| CQG | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| RW | 10% | 20% | 20% | 50% | 50% | 100% |

### 6.10 Table 7-9 — Covered bonds without issue-specific assessments (para 7.3.65, p. 7-48)

| RW of issuing bank | 20% | 30% | 40% | 50% | 75% | 100% | 150% |
|---|---|---|---|---|---|---|---|
| Covered bond RW | 10% | 15% | 20% | 25% | 35% | 50% | 100% |

The eligibility criteria for covered bonds are in para 7.3.2:
- The cover pool may hold RRE with LTV ≤ 80% and CRE with LTV ≤ 60%.
- Bank exposures in the pool must qualify for ≤ 30% and be ≤ 15% of the issuance.
- The pool must be over-collateralised by at least 10%.

### 6.11 Table 7-10 — General corporate (para 7.3.67, p. 7-49)

| CQG | 1 | 2 | 3 | 4 | 5 | 6 | Unrated |
|---|---|---|---|---|---|---|---|
| RW | 20% | 50% | 75% | 100% | 150% | 150% | 100% |

- Table 7-11 (para 7.3.68, p. 7-49) covers short-term issue-specific assessments: I 20%,
  II 50%, III 100%, IV 150%.
- Para 7.3.69 sets the same unrated floors as para 7.3.55.
- Para 7.3.70 requires a one-grade uplift where due diligence shows higher risk.

### 6.12 Table 7-12 — Corporate SME (para 7.3.71, p. 7-50)

| CQG | 1 | 2 | 3 | 4 | 5 | 6 | Unrated |
|---|---|---|---|---|---|---|---|
| RW | 20% | 50% | 75% | 100% | 150% | 150% | 85% |

- Table 7-13 (para 7.3.72, p. 7-50) covers short-term issue-specific assessments: I 20%,
  II 50%, III 100%, IV 150%.
- Para 7.3.4 defines a small business by "reported annual revenue of less than or equal to S$100
  million". For a group of companies, the consolidated group revenue is used.

### 6.13 Table 7-14 — Specialised lending, rated (para 7.3.75, p. 7-50)

| CQG | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| RW | 20% | 50% | 75% | 100% | 150% | 150% |

Issuer assessments must not be used; only issue-specific assessments apply.

### 6.14 Table 7-15 — Specialised lending, unrated (para 7.3.76, p. 7-51)

| Condition | RW |
|---|---|
| Project finance in the operational phase (7.3.77(a)) **and** high quality (7.3.77(b)) | 80% |
| Project finance in the operational phase, not high quality | 100% |
| Any other project finance exposure | 130% |
| Object finance and commodities finance exposures | 100% |

### 6.15 Equity and subordinated debt (paras 7.3.80–7.3.85, pp. 7-53 to 7-55)

Para 7.3.80 sets the base weights:
- (a) 400% for speculative unlisted equity (7.3.81: short-term resale, venture capital or similar).
- (b) 250% for all other equity exposures.
- (c) 150% for subordinated debt and for regulatory capital instruments that are not equities.

Para 7.3.82 applies 1250% to the major-stake portions in non-financial-institution companies:
- (a) the portion of each individual equity or subordinated-debt exposure above 15% of Eligible
  Total Capital;
- (b) the portion of the aggregate above 60% of Eligible Total Capital.

Para 7.3.83 allocates the aggregate excess pro rata over the within-15% portions:
- (a) for each exposure, take the portion not exceeding 15% of Eligible Total Capital;
- (b) aggregate those portions;
- (c) compute the excess of the full sum of exposures over 60% of Eligible Total Capital;
- (d) compute the ratio of (c) to (b);
- (e) apply 1250% to each (a) amount multiplied by the (d) ratio.

**Table 7-16 — Phase-in of equity risk weights from 1 July 2024 (para 7.3.85, p. 7-55)**

| From | Speculative unlisted equity | All other equity |
|---|---|---|
| 1 July 2024 | 160% | 130% |
| 31 December 2025 | 220% | 160% |
| 31 December 2026 | 280% | 190% |
| 31 December 2027 | 340% | 220% |
| 31 December 2028 | 400% | 250% |

Undeducted major-stake FI ordinary shares take 250% (paras 6.1.5(p)(iii) and 7.3.104). With MAS
approval they may take 400% at Solo level (paras 6.1.6 and 7.3.105).

### 6.16 Retail (paras 7.3.86–7.3.87, p. 7-55)

**Table 7-17**

| Asset sub-class | RW |
|---|---|
| Regulatory retail transactor | 45% |
| Regulatory retail non-transactor | 75% |

Other retail takes 100% (7.3.87).

A transactor is a borrower on credit or charge cards who repaid the billed balance in full at
each scheduled date for the previous 12 months. An overdraft not drawn down over the previous
12 months also qualifies (7.3.1(i)(A)).

### 6.17 Real estate (paras 7.3.88–7.3.103, pp. 7-55 to 7-59)

**ADC** takes 150% (7.3.88). An ADC exposure secured by RRE takes 100% if it meets the 7.3.17(f)
underwriting standards and has "LTV ... less than or equal to 80%" on gross development value
(7.3.89).

**Table 7-18 — Regulatory RRE, not materially dependent on cash flows (para 7.3.91, p. 7-56)**

| LTV | ≤50% | 50%<LTV≤60% | 60%<LTV≤80% | 80%<LTV≤90% | 90%<LTV≤100% | >100% |
|---|---|---|---|---|---|---|
| RW | 20% | 25% | 30% | 40% | 50% | 70% |

**Table 7-19 — Regulatory RRE, materially dependent on cash flows (para 7.3.92, p. 7-57)**

| LTV | ≤50% | 50%<LTV≤60% | 60%<LTV≤80% | 80%<LTV≤90% | 90%<LTV≤100% | >100% |
|---|---|---|---|---|---|---|
| RW | 30% | 35% | 45% | 60% | 75% | 105% |

**Table 7-20 — Regulatory CRE, not materially dependent on cash flows (para 7.3.93, p. 7-57)**

| LTV | ≤60% | >60% |
|---|---|---|
| RW | Min. (60%, Risk Weight of counterparty) | Risk Weight of counterparty |

Para 7.3.94 defines the counterparty weight:
- (a) individual or group of individuals: 75%;
- (b) small business: 85%;
- (c) otherwise: the weight of an unsecured exposure to the obligor.

**Table 7-21 — Regulatory CRE, materially dependent on cash flows (para 7.3.95, p. 7-57)**

| LTV | ≤60% | 60%<LTV≤80% | >80% |
|---|---|---|---|
| RW | 70% | 90% | 110% |

- **Junior charges (7.3.96):** "a multiplier of 1.25 to the applicable risk weight of any
  regulatory real estate exposure against a junior charge, unless ... the lowest LTV bucket". The
  result is capped at the other-real-estate weight.
- **Other real estate (7.3.98–7.3.99):** if not materially dependent on cash flows, 75%
  (individual), 85% (small business) or the unsecured obligor weight. If materially dependent,
  150%.
- **Material dependence (7.3.100–7.3.101):** the following are never treated as materially
  dependent:
  - the owner-occupied primary residence;
  - an individual with 2 or fewer mortgaged non-owner-occupied RRE units;
  - housing associations or cooperatives;
  - public housing companies and not-for-profit associations.
- **Whole loan only:** the Notice contains no loan-splitting option.
- **Footnote 238:** MAS "may from time to time specify a higher risk weight for a particular
  exposure or group of exposures".

### 6.18 Other exposures (paras 7.3.104–7.3.106, p. 7-59)

- Exposures under 6.1.5(p)(iii): 250%.
- Exposures under 6.1.6 (Solo, with approval): 400%.
- Any other exposure in the other exposures class: 100%.

### 6.19 Currency mismatch (paras 7.3.107–7.3.108, pp. 7-60, 7-61)

"Subject to a maximum risk weight of 150%, ... a multiplier of 1.5 times". The conditions are:
- (a) the exposure is to an individual;
- (b) it is regulatory retail, other retail, regulatory RRE (incl. 7.3.96 / 7.3.97), or other
  real estate secured by RRE;
- (c) it is denominated in a currency other than that of the individual's income;
- (d) it is unhedged.

"Unhedged" means natural or financial hedges cover less than 90% of the loan instalment.

### 6.20 Table 7-22 — Defaulted exposures (para 7.3.109, p. 7-61)

| Condition | RW |
|---|---|
| Specific allowances are less than 20% of the outstanding amount | 150% |
| Specific allowances are no less than 20% of the outstanding amount | 100% |

- Para 7.3.110: 100% for defaulted regulatory RRE, or other real estate secured by RRE, that is
  not materially dependent on cash flows.
- Para 7.3.111 defines the uncollateralised portion as E – P – Cf under FC(SA) and E* – P under
  FC(CA).

## 7. CCFs — Annex 7B, Table 7B-1 (pp. 7-179, 7-180)

| Item | Description | Standardised CCF |
|---|---|---|
| (a) | Direct credit substitutes | 100% |
| (b) | Sale and repurchase agreements and asset sales with recourse, where the credit risk remains with the Reporting Bank | 100% |
| (c) | Commitments with certain drawdown, including forward purchases, forward deposits, and partly paid shares and securities | 100% |
| (d) | Credit substitutes which are not explicitly included in (a) to (c) | 100% |
| (e) | Note issuance facilities and revolving underwriting facilities, regardless of the maturity of the underlying facility | 50% |
| (f) | Certain transaction-related contingent items | 50% |
| (g) | Other commitments, regardless of the maturity of the underlying facility, unless ... (h) or (i) | 40% |
| (h) | Self-liquidating trade-related contingent items arising from the movement of goods with an original maturity of below one year (issuing or confirming bank) | 20% |
| (i) | Commitments which are unconditionally cancellable at any time ... without prior notice, or that effectively provide for automatic cancellation due to deterioration in an obligor's creditworthiness | 10% |

- Para 1.2: a commitment to provide another off-balance sheet item takes the lower of the two
  CCFs.
- Para 1.5: a tranched loan commitment takes 40% on the full undisbursed portion.
- Para 1.6: MAS may direct a CCF above 10% for item (i).
- Para 7.2.12: posted collateral takes a 100% CCF.

## 8. Credit risk mitigation

### 8.1 FC(CA) — Annex 7J para 1.1 (p. 7-259)

```
E* (or EAD*) = max {0, [E (or EAD)(1 + HE) - C(1 – HC – HFX)]}
```
Where there is a maturity mismatch, PA (Annex 7H para 7.4) replaces C(1 – HC – HFX) (para 1.2).

### 8.2 Table 7J-1 — Standard Supervisory Haircuts (Annex 7J para 2.1, pp. 7-261, 7-262)

All haircuts assume a 10-business-day holding period with daily remargining and revaluation.

| Issue rating for debt securities | Residual maturity | Sovereign issuers | Other issuers | Securitisation exposures |
|---|---|---|---|---|
| CQG "1" or short-term "I" | ≤ 1 year | 0.005 | 0.01 | 0.02 |
| | > 1 year, ≤ 3 years | 0.02 | 0.03 | 0.08 |
| | > 3 years, ≤ 5 years | 0.02 | 0.04 | 0.08 |
| | > 5 years, ≤ 10 years | 0.04 | 0.06 | 0.16 |
| | > 10 years | 0.04 | 0.12 | 0.16 |
| CQG "2" and "3" or short-term "II" and "III" | ≤ 1 year | 0.01 | 0.02 | 0.04 |
| | > 1 year, ≤ 3 years | 0.03 | 0.04 | 0.12 |
| | > 3 years, ≤ 5 years | 0.03 | 0.06 | 0.12 |
| | > 5 years, ≤ 10 years | 0.06 | 0.12 | 0.24 |
| | > 10 years | 0.06 | 0.20 | 0.24 |
| CQG "4" | All | 0.15 | Not eligible | Not eligible |

| Other collateral | Haircut |
|---|---|
| Gold | 0.20 |
| Any equity (including a convertible bond) in a main index | 0.20 |
| Any other equity (including a convertible bond) listed on an approved exchange or an overseas exchange | 0.30 |
| Units in a CIS | highest haircut of any security the fund can invest in (or LTA weighted average) |
| Cash in the same currency as the underlying exposure | 0 |
| Instruments in the trading book other than those listed above (repo-style transactions in the trading book) | 0.30 |

- Para 2.2(b): "sovereign issuer" covers central governments, central banks, qualifying MDBs, and
  PSEs at 0% or 20% under Table 7-3.
- Para 2.3: HE = 0.30 for non-eligible instruments lent or posted.
- Para 2.4: **HFX = 0.08**.

### 8.3 Table 7J-2 — Minimum holding periods (para 3.1, p. 7-263)

| Transaction type | Minimum holding period | Condition |
|---|---|---|
| Repo-style transactions | 5 business days | daily remargining |
| Other capital market transactions (OTC derivatives, margin lending, commodities lending/borrowing) | 10 business days | daily remargining |
| Secured lending | 20 business days | daily revaluation |
| Netting set of repo-style and other capital market transactions | 10 business days | daily remargining |

Table 7J-3 raises the holding period to 20 business days for netting sets with more than 5,000
transactions, or with illiquid collateral. Para 3.3 doubles the holding period after more than 2
margin disputes.

**Para 3.4 (p. 7-264):**
```
H = H10 × sqrt( (NR + (TM − 1)) / 10 )
```

### 8.4 Guarantees and credit derivatives (paras 7.3.112–7.3.113; Annex 7H)

- **Substitution (7.3.112):** the protected portion takes the weight of the eligible protection
  provider and the unprotected portion takes the obligor's weight. This applies only "where the
  risk weight of the eligible protection provider is lower than that of the obligor".
- **Materiality threshold (7.3.113):** an exposure below a materiality threshold takes 1250%.
- **Currency mismatch (Annex 7H para 6.2, p. 7-253):** `GA = G x (1-HFX)` with HFX = 8% on a
  10-business-day basis.
- **Maturity mismatch (Annex 7H paras 7.1 and 7.4, p. 7-254):** the mitigant is recognised only
  with an original maturity ≥ 1 year and a residual maturity ≥ 3 months. Then:
  ```
  PA = [P x (t-0.25)]/(T-0.25),  t = min(T, residual maturity of the CRM),  T = min(5, residual maturity of the exposure)
  ```
- **FC(SA) floor (7.3.124):** 20% on the collateralised portion. The exceptions are 0% (core
  market participant repo), 10% (other qualifying repo), and 0% (same-currency cash, or 0%-weight
  sovereign/PSE collateral discounted by 20%).

## 9. Operational risk — Part IX SA(OR) (pp. 9-1 to 9-7)

Para 9.1.1: operational RWA = 12.5 × the operational risk requirement, at Group and Solo levels.

Para 9.1.2: `K_ORC = BIC × ILM`.
- **BIC (9.1.2(a))**, summed over three terms:
  - (i) 12% of BI;
  - (ii) 3% of the BI above S$1.5 billion;
  - (iii) 3% of the BI above S$45 billion.
- **Footnote 901 example:** BI = S$50bn gives BIC = 50 × 12% + 48.5 × 3% + 5 × 3% = S$7.605bn.
- **ILM (9.1.2(b)):** `ILM = ln(exp(1) − 1 + (LC/BIC)^0.8)`. LC = 15 × the average annual net
  losses over the past 10 consecutive financial years, or over the observation period of
  9.1.14 / 9.1.15.

Para 9.1.3 defines BI = ILDC + SC + FC, where a bar denotes the average over the past 3 years:
```
ILDC = min(abs(interest income − interest expenses)‾, 2.25% × interest earning assets‾) + dividend income‾
SC   = max(fee and commission income‾, fee and commission expenses‾) + max(other operating income‾, other operating expenses‾)
FC   = abs(Net P&L on the trading book)‾ + abs(Net P&L on the banking book)‾
```
"the absolute value of net items must be calculated first for each financial year" (9.1.3(iii)).
Items are defined in Annex 9A, and excluded items in 9.1.6.

**When the ILM applies:**
- **9.1.8(a):** BI ≤ S$1.5 billion: "must set the ILM equal to one ... unless the Reporting Bank
  has obtained the Authority's written approval to calculate the ILM".
- **9.1.8(b):** BI > S$1.5 billion: "must calculate the ILM".
- **9.1.10:** if the loss-data criteria fail, ILM = 1, or more than 1 if MAS requires.
- **9.1.13–9.1.15:** 10 years of loss data is standard. 5 years is the minimum, with approval.
  With fewer than 5 years, ILM = 1, unless ILM > 1 and MAS requires the shorter data to be used.

**Loss thresholds:**
- 9.1.20: S$30,000 for the internal loss data set.
- 9.1.21(b): S$150,000 for the LC of a bank with BI > S$1.5 billion.
- 9.1.21(a): S$30,000 for a bank with BI ≤ S$1.5 billion.

## 10. SA-CCR — Annex 7D (pp. 7-182 to 7-200)

- **1.1:** `E or EAD = alpha × (RC + PFE)`, **alpha = 1.4**. The Notice has no variation for
  non-financial or pension counterparties.
- **1.4:** the EAD of a margined netting set is capped at its unmargined EAD.
- **2.1:** unmargined `RC = max{V − C; 0}`.
- **2.4:** margined `RC = max{V − C; TH + MTA − NICA; 0}`.
- **3.1:** `PFE = multiplier × AddOn_aggregate`, with
  `multiplier = min{1; Floor + (1 − Floor) exp((V − C) / (2(1 − Floor) AddOn_aggregate))}` and
  **Floor = 5%**.
- **3.13:** IR maturity buckets are < 1 year, 1–5 years and > 5 years.
- **3.28(a):** `SD_i = (exp(−0.05 × S_i) − exp(−0.05 × E_i)) / 0.05`. S_i = 0 once the start
  date has occurred.
- **3.36(a):** unmargined `MF = sqrt(min{M_i; 1 year} / 1 year)`, with M_i ≥ 10 business days.
- **3.36(b):** margined `MF = (3/2) sqrt(MPOR_i / 1 year)`. Footnote 361 allows 250 business days
  per year.
- **3.41:** SF × 0.5 for basis hedging sets and SF × 5 for volatility hedging sets.
- **3.42:** an unrated reference entity without an IRBA mapping takes SF 1.06%.

### Table 7D-1 — Supervisory Parameters (pp. 7-199, 7-200)

| Asset class | Subclass | SF | Correlation | Option vol |
|---|---|---|---|---|
| Interest rate | | 0.5% | N/A | 50% |
| Foreign exchange | | 4% | N/A | 15% |
| Credit, single name | CQG 1 | 0.38% | 50% | 100% |
| | CQG 2 | 0.42% | 50% | 100% |
| | CQG 3 | 0.54% | 50% | 100% |
| | CQG 4 | 1.06% | 50% | 100% |
| | CQG 5 | 1.6% | 50% | 100% |
| | CQG 6 | 6% | 50% | 100% |
| Credit, index | CQG 1 to 3 | 0.38% | 80% | 80% |
| | CQG 4 to 6 | 1.06% | 80% | 80% |
| Equity | Single name | 32% | 50% | 120% |
| | Index | 20% | 80% | 75% |
| Commodity | Electricity | 40% | 40% | 150% |
| | Oil/Gas | 18% | 40% | 70% |
| | Metals | 18% | 40% | 70% |
| | Agricultural commodities | 18% | 40% | 70% |
| | Other | 18% | 40% | 70% |

## 11. CVA — Part VIII Division 5 (pp. 8-178 to 8-187)

- **8.5.1:** CVA RWA = 12.5 × (BA-CVA capital + SA-CVA capital).
- **8.5.7:** banks use BA-CVA unless MAS approves SA-CVA.
- **8.5.10:** "If a Reporting Bank's aggregate notional amount of non-centrally cleared
  derivatives is less than or equal to S$150 billion, the Reporting Bank may choose to set its CVA
  RWA equal to the sum of its CCR-SA RWA and CCR-IRBA RWA", with no hedge recognition. MAS may
  override this choice (8.5.11).

**Reduced BA-CVA (8.5.13–8.5.14):**
```
capital = DS_BA-CVA × K_reduced,  DS_BA-CVA = 0.65
K_reduced = sqrt( (ρ · Σ_c SCVA_c)² + (1 − ρ²) · Σ_c SCVA_c² ),  ρ = 50%
SCVA_c = (1/α) · RW_c · Σ_NS (M_NS · EAD_NS · DF_NS),  α = 1.4
DF_NS = 1 (IMM banks);  DF_NS = (1 − e^(−0.05·M_NS)) / (0.05·M_NS) otherwise
```
M_NS follows Annex 7E or Annex 7V without the 5-year cap. An unrated counterparty may be mapped
from IRBA internal ratings with MAS approval; otherwise it is "not rated".

**Full BA-CVA (8.5.15–8.5.17):**
```
capital = 0.65 × K_full,  K_full = β · K_reduced + (1 − β) · K_hedged,  β = 0.25
K_hedged = sqrt( (ρ · Σ_c (SCVA_c − SNH_c) − IH)² + (1 − ρ²) · Σ_c (SCVA_c − SNH_c)² + Σ_c HMA_c )
SNH_c = Σ_h∈c r_hc · RW_h · M_h^SN · B_h^SN · DF_h^SN
IH    = Σ_i RW_i · M_i^ind · B_i^ind · DF_i^ind
HMA_c = Σ_h∈c (1 − r_hc²) · (RW_h · M_h^SN · B_h^SN · DF_h^SN)²
```
For index hedges:
- an index whose constituents share one sector and credit quality takes RW × 0.7;
- otherwise the hedge takes the weighted-average RW × 0.7.

Para 8.5.18 defines "same credit quality" as: both CQG ≤ 3; both ≥ 4; one ≥ 4 and one unrated;
or both unrated.

### Table 8-26 — BA-CVA risk weights (p. 8-183)

| Sector of counterparty | CQG "3" or better | CQG "4" or worse or not rated |
|---|---|---|
| Sovereigns (central governments, central banks, BIS, IMF, ECB, EU, ESM, EFSF) and MDBs | 0.5% | 2.0% |
| PSEs, education | 1.0% | 4.0% |
| Financial institutions | 5.0% | 12.0% |
| Basic materials, energy, industrials, agriculture, manufacturing, mining and quarrying | 3.0% | 7.0% |
| Consumer goods and services, transportation and storage, administration and support service activities | 3.0% | 8.5% |
| Technology, telecommunications | 2.0% | 5.5% |
| Health care, utilities, professional and technical activities | 1.5% | 5.0% |
| Other sector | 5.0% | 12.0% |

### Table 8-27 — r_hc (p. 8-187)

| Single-name hedge references | r_hc |
|---|---|
| counterparty c | 100% |
| parent, subsidiary, or entity with the same parent as counterparty c | 80% |
| entity in the same sector (Table 8-26) and country or jurisdiction as counterparty c | 50% |

## 12. Implementation mapping (engine fields → MAS provisions)

| Engine input | MAS treatment |
|---|---|
| `SAExposure.rating` / `short_term_rating` | Table 7M-1 / 7M-2 grade |
| `scra_grade`, `scra_grade_a_enhanced` | Table 7-7, para 7.3.59 |
| `original_maturity_months` | Bank short-term (≤ 3 months; trade ≤ 6 months); Table 7B-1 item (h) (< 1 year) |
| `annual_turnover` (SGD m) | SME test ≤ S$100m (para 7.3.4) |
| `aggregate_retail_exposure_to_obligor` (SGD m) | ≤ S$2m (para 7.3.1(i)(iii)) |
| `ltv`, `is_cash_flow_dependent`, `is_regulatory_real_estate` | Tables 7-18 to 7-21; paras 7.3.98–7.3.99 |
| `currency_matches_borrower_income` | para 7.3.107 |
| `specific_provision_pct` | Table 7-22 |
| `collateral_haircut_class` | Table 7J-1 key (see `params.SUPERVISORY_HAIRCUTS`) |
| `flags[...]` | listed in the `credit_risk.py` module docstring |

## 13. Equity date convention

Table 7-16 rows are labelled "From 31 December 2025" and so on. The engine applies a row on and
after that date. `SGRegime(as_of=...)` defaults to 1 January 2026, which gives 220% / 160%.

## 14. Comparison anchors in the Basel Framework

Each MAS provision is listed against its Basel Framework counterpart:
- Minimums: RBC20.1–20.2 (4.5% / 6% / 8%) vs Tables 4-1 / 4-2.
- Output floor: RBC20.4 and RBC90 Table 1, which runs 50% from 1 January 2023 to 72.5% from
  1 January 2028, with the RBC90.2 25% cap. Compare Table 5-3.
- Operational risk: OPE25.7 (€1bn / €30bn buckets) and OPE25.11 (ILM = 1 discretion) vs
  9.1.2 / 9.1.8.

## 15. Open items (TODO: VERIFY)

1. **Table 7B-1 item (h)** covers only "original maturity of below one year". The CCF for
   self-liquidating trade items of one year or more is not stated. A placeholder of 100% (item
   (d)) is used.
2. **D-SIB leverage ratio buffer** is referenced in Annex 11D row 27, but the Notice sets no rate.
   The placeholder is 0%.
3. **D-SIB / G-SIB CET1 buffer** is referenced in Annex 11A row 64(iv), but Part IV sets no rate.
   It is an input, defaulting to 0%; the D-SIB loading sits in the Table 4-1 minimums.
4. **Corporate "short-term"** is used in paras 7.3.69(a) and 7.3.73(a) but not defined for
   corporates. One year of original maturity is used; it affects only the 100% floor.
