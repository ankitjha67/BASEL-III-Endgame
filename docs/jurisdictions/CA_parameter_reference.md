# OSFI CAR 2026 — parameter reference transcribed from the guideline text

Source: OSFI *Capital Adequacy Requirements (CAR) Guideline (2026)*, chapters 1–9, effective fiscal
2026 ("valid until the end of the reporting period on January 31, 2027"), converted from the OSFI
web page to plain text. Tables in that conversion are flattened into running text; each table below
was rebuilt from the flattened row/column sequence. Where this file and the official OSFI publication
differ, the official publication governs.

Citation format used in code: `CAR Ch.<n> s.<section> [Table <t>] [Basel Framework <ref>]`. OSFI
paragraph numbers are cited only where the CAR text itself cross-references them; the HTML conversion
does not preserve the paragraph numbering.

All dollar amounts are **Canadian dollars** (CAR Ch.1 footnote 6: "All dollar values in this
guideline are in Canadian dollars, unless otherwise noted").

Items marked **⚠ VERIFY** are carried as `# TODO: VERIFY` in `src/jurisdictions/ca/`.

---

## Chapter 1 — Overview of risk-based capital requirements

### s.1.3 Total RWA [RBC 20.4]
RWA = higher of (credit RWA + market RWA + operational RWA) and the adjusted RWA under the capital
floor of s.1.5.

### s.1.4 IRB approval floors
- "For institutions approved to use the IRB approach, upon approval, the floor adjustment factor will
  be set at 90%."
- "Institutions may be eligible for a reduction of the floor adjustment factor by up to 7.5%, after at
  least four quarters at a set level ... until the floor adjustment factor set out in paragraph 33 is
  reached."

### s.1.5 Capital floor [RBC 20.11–20.12]
- Applies to institutions using IRB, IMM or IMA. "Institutions that have only implemented the
  standardized approaches ... are not subject to the capital floor."
- s.1.5.1 (paragraph 33): capital floor = floor adjustment factor × [total RWA for the capital floor
  − 12.5 × general allowances recognised in Tier 2 under the SA].
  **"The floor adjustment factor is set at 67.5% until further notice. OSFI will provide at least two
  years prior notice to resuming an increase in the floor adjustment factor. OSFI may set a higher
  floor adjustment factor for individual institutions."** No year-by-year phase-in table is printed.
- s.1.5.2: adjusted capital requirement = total RWA + 12.5 × provisioning shortfall deduction − 12.5 ×
  excess provisions in Tier 2 − 12.5 × general allowances in Tier 2 for SA exposures.
- If the floor exceeds the adjusted requirement, the difference is added to total RWA.
- Floor base excludes IRB, SEC-IRBA, IMA, VaR models for SFTs and IMM.

### s.1.6.1 Table 2 — Minimum capital requirements (in RWA)
| Ratio | Minimum |
|---|---|
| CET1 | 4.5% |
| Tier 1 | 6.0% |
| Total | 8.0% |

(Table 3: identical minimums for Category III SMSBs measured as SRBCR = Capital / (Adjusted Total
Assets + RWA operational risk) — not implemented.)

### s.1.7.1 Table 4 — Capital conservation buffer [RBC 30.2]
| | |
|---|---|
| Capital conservation buffer | 2.5% |
| CET1 + CCB | 7.0% |
| Tier 1 + CCB | 8.5% |
| Total + CCB | 10.5% |

### s.1.7.1 Table 5 — Minimum capital conservation ratios [RBC 30.4]
| CET1 ratio | Minimum conservation ratio (% of earnings) |
|---|---|
| 4.5% – 5.125% | 100% |
| >5.125% – 5.75% | 80% |
| >5.75% – 6.375% | 60% |
| >6.375% – 7.0% | 40% |
| >7.0% | 0% |

### s.1.7.2 Countercyclical buffer [RBC 30.7–30.19]
"a countercyclical buffer requirement, ranging from 0% to 2.5% of total risk-weighted assets, will be
put in place when circumstances warrant." Consolidated CCyB = weighted average of jurisdictional
buffers, weights = private-sector credit RWA by jurisdiction (ultimate-risk basis). Reciprocity
mandatory up to 2.5% (footnote 19). Table 6: quartile-based conservation ratios 100/80/60/40/0%.

### s.1.8 D-SIB surcharge [BCBS RBC 40.7–40.23]
"D-SIBs will be subject to a CET1 surcharge equal to 1% of RWAs." Implemented as an extension of the
capital conservation buffer. Six D-SIBs: BMO, BNS, CIBC, National Bank, RBC, TD.

### s.1.8 Table 7 — D-SIB minimum capital conservation ratios
| CET1 ratio | Tier 1 leverage ratio | Minimum capital conservation ratio |
|---|---|---|
| 4.5% – 5.375% | 3% – 3.125% | 100% |
| >5.375% – 6.250% | >3.125% – 3.25% | 80% |
| >6.250% – 7.125% | >3.25% – 3.375% | 60% |
| >7.125% – 8.0% | >3.375% – 3.50% | 40% |
| >8.0% | >3.50% | 0% |

### s.1.9 Domestic Stability Buffer
- "The level of the DSB will range between 0 and 4.0% of a D-SIB's total RWA ... must be met with
  CET1 capital."
- Not a Pillar 1 buffer: breaches → remediation plan, not automatic distribution constraints.
- Reviewed semi-annually; changes published in June and December. **The current level is not stated
  in CAR** (Annex 2 mentions 1% "as at May 1, 2020"; footnote 35 uses 2% as an example).
  **⚠ VERIFY** — engine input (`domestic_stability_buffer` / `stress_buffer`).

### s.1.10 Table 8 — Target capital ratios
| | SMSBs | D-SIBs |
|---|---|---|
| Target CET1 | 7.0% | 8.0% plus DSB |
| Target Tier 1 | 8.5% | 9.5% plus DSB |
| Target Total | 10.5% | 11.5% plus DSB |

Footnote 35: "where the DSB is set to 2% of RWA, D-SIBs' target capital ratios would be at least 10%
for CET1, 11.5% for Tier 1 and 13.5% for Total capital."

### Annex 1 — G-SIB relationship
OSFI adopted the BCBS G-SIB methodology; HLA "range from 1% to 3.5% RWA"; "For Canadian D-SIBs that
are also designated as G-SIBs, the higher of the D-SIB and G-SIB surcharges will apply." Bucket rates
(1.0/1.5/2.0/2.5/3.5%) are taken from Basel Framework RBC40.4 Table 1 (not tabulated in CAR).

### Leverage (stated in CAR Ch.4 s.4.1.4, SCRA Grade A for Canadian banks)
"Banks are required to have a minimum Leverage Ratio of 3%. Banks designated by OSFI as D-SIB are
expected to maintain a leverage ratio that meets or exceeds 3.5% at all times." → D-SIB leverage
buffer 0.5% (consistent with Table 7). Confirmed against the OSFI Leverage Requirements Guideline
(2023): 3% minimum; the D-SIB leverage buffer is 50% of the D-SIB's higher-loss-absorbency
requirement (0.5% at the 1% D-SIB surcharge), now computed as 0.5 x the systemic surcharge in
`capital_stack.py`. See `CA_pillar1_reference.md`.

---

## Chapter 3 — Operational risk

### s.3.2 Methodologies
- D-SIBs must use the Standardized Approach (SA). Category I SMSBs with annual Adjusted Gross Income
  > $1.5 billion must use the SA (minimum two years once crossed). Other SMSBs use the Simplified
  Standardized Approach (SSA), or the SA with OSFI approval and ≥ 5 years of loss data — "not
  permitted to set the ILM to less than one until OSFI has determined that they have 10 years of
  high-quality loss data."

### s.3.3 Simplified Standardized Approach
- ORC_SSA = (AGI over previous 12 fiscal quarters / 3) × 15%; RWA = 12.5 × ORC.
- AGI = lesser of (|net interest income|, 2.25% × interest-earning assets) + dividend income +
  |fee and commission income| + |other income| + |net P&L trading book| + |net P&L banking book|;
  gross of provisions and operating expenses, excluding extraordinary items and insurance income.

### s.3.4 Standardized Approach [OPE 25.1–25.10]
- ORC_SA = BIC × ILM; RWA = 12.5 × ORC.
- BI = ILDC + SC + FC (bar = three-year average; absolute value of net items taken year by year,
  footnote 7):
  - ILDC = Min[Abs(Interest Income − Interest Expense)‾ ; 2.25% × Interest Earning Assets‾] +
    Dividend Income‾
  - SC = Max[Fee and Commission Income‾ ; Fee and Commission Expenses‾] + Max[Other Operating
    Income‾ ; Other Operating Expenses‾]
  - FC = Abs(Net P&L Trading Book)‾ + Abs(Net P&L Banking Book)‾
- **BIC = 12% of BI, plus 3% of BI above $1.5 billion (if any), plus 3% of BI above $45 billion
  (if any).** Footnote 8: BI = $50B → BIC = ($50B × 0.12) + [($50B − $1.5B) × 0.03] + [($50B −
  $45B) × 0.03] = $7.605B.
- ILM = ln(exp(1) − 1 + (LC/BIC)^0.8); LC = 15 × average annual net operational losses over the
  previous 10 years.
- "Institutions that do not have ten years of high-quality loss data must calculate the capital
  requirement using an ILM greater than or equal to one." OSFI may require fewer years if the
  resulting ILM > 1.
- s.3.4.2: institutions not meeting the loss-data standards hold at least 100% of BIC (ILM ≥ 1).
- s.3.4.3: loss-event threshold **$30,000** net of recoveries.
- s.3.4.5: exclusions only for events > 5% of average annual losses and held ≥ 3 years in the
  database (divestitures excepted).
- s.3.4.7: M&A — missing loss years estimated at 1% of acquired BI (ILM ≤ 1) or x% (ILM > 1);
  alternatively 125% of acquired AGI as BI proxy.

---

## Chapter 4 — Credit risk, standardized approach

SMSB simplified treatment (Categories I/II, asset-class grouping ≤ $500 million, Appendix I/II):
banks 40% (20% ≤ 3 months); covered bonds 20%; corporates/SMEs/SL 100%; revolving and non-revolving
regulatory retail 75%; RRE 35% (LTV ≤ 80%) / 75% (LTV > 80%); CRE 100%.

### s.4.1.1 Table 1 — Sovereigns and central banks [CRE 20.7]
| AAA to AA− | A+ to A− | BBB+ to BBB− | BB+ to B− | Below B− | Unrated |
|---|---|---|---|---|---|
| 0% | 20% | 50% | 100% | 150% | 100% |

"exposures to the Canadian sovereign and central bank are to be risk-weighted at 0%." BIS, IMF, ECB,
EU, ESM, EFSF: 0% [CRE 20.10].

### s.4.1.1 Table 2 — ECA risk scores [CRE 20.9]
| 0–1 | 2 | 3 | 4 to 6 | 7 |
|---|---|---|---|---|
| 0% | 20% | 50% | 100% | 150% |

### s.4.1.2 Table 3 — PSEs [CRE 20.11]
| Sovereign rating | AAA to AA− | A+ to A− | BBB+ to BBB− | BB+ to B− | Below B− | Unrated |
|---|---|---|---|---|---|---|
| Sovereign RW | 0% | 20% | 50% | 100% | 150% | 100% |
| PSE RW | 20% | 50% | 100% | 100% | 150% | 100% |

Provinces/territories and agents of the federal/provincial/territorial government whose debts are
obligations of the parent government: Government of Canada RW. PSE guarantees outside own services:
corporate exposure on the PSE's rating. Foreign PSEs: host-regulator treatment [CRE 20.12].

### s.4.1.3 Table 4 — MDBs [CRE 20.15]
| AAA to AA− | A+ to A− | BBB+ to BBB− | BB+ to B− | Below B− | Unrated |
|---|---|---|---|---|---|
| 20% | 30% | 50% | 100% | 150% | 50% |

0% for MDBs meeting the CRE 20.14 criteria (footnote 14: World Bank Group, ADB, AfDB, EBRD, IADB,
EIB, EIF, NIB, CDB, IsDB, CEDB, IFFIm, AIIB).

### s.4.1.4 Table 5 — Banks, ECRA [CRE 20.18–20.19]
| | AAA to AA− | A+ to A− | BBB+ to BBB− | BB+ to B− | Below B− |
|---|---|---|---|---|---|
| "Base" RW | 20% | 30% | 50% | 100% | 150% |
| Short-term RW | 20% | 20% | 20% | 50% | 150% |

Short-term = original maturity ≤ 3 months, or goods-movement trade ≤ 6 months. Due diligence: at
least one bucket higher where warranted; never lower [CRE 20.20].

### s.4.1.4 Table 6 — Banks, SCRA [CRE 20.21–20.31]
| | Grade A | Grade B | Grade C |
|---|---|---|---|
| "Base" RW | 40% | 75% | 150% |
| Short-term RW | 20% | 50% | 150% |

- 30% for unrated banks with CET1 ≥ 14% and Tier 1 leverage ≥ 5% that meet Grade A.
- Option: 100% to all unrated bank exposures (prior notification).
- Sovereign floor where the exposure is not in the debtor bank's local currency; not for short-term
  (< 1 year) self-liquidating trade items [CRE 20.32].
- Canadian Grade A: meets CAR minimums and buffers (4.5/6/8%, CCB 2.5%, CCyB, D-SIB 1%) and the
  leverage requirements (3%; D-SIBs 3.5%).

### s.4.1.5 Table 7 — Rated covered bonds [CRE 20.38]  ⚠ VERIFY
| AAA to AA− | A+ to A− | BBB+ to BBB− | BB+ to B− | Below B− |
|---|---|---|---|---|
| 20% | 30% | 50% | 100% | 150% |

### s.4.1.5 Table 8 — Unrated covered bonds [CRE 20.38]  ⚠ VERIFY
| Issuer RW | 20% | 30% | 40% | 50% | 75% | 100% | 150% |
|---|---|---|---|---|---|---|---|
| Covered bond RW | 20% | 30% | 40% | 50% | 75% | 100% | 150% |

As printed, Tables 7–8 give no reduction relative to the issuing bank (Basel CRE20.38 Tables 8–9:
10/20/20/50/100% and 10/15/20/25/35/50/100%).

### s.4.1.7 Table 9 — Rated corporates [CRE 20.42–20.43]
| AAA to AA− | A+ to A− | BBB+ to BBB− | BB+ to BB− | Below BB− |
|---|---|---|---|---|
| 20% | 50% | 75% | 100% | 150% |

- U.S. GSEs 20%. Optional 100% to all corporate exposures (prior notification, paragraph 60).
- Paragraph 62: "Institutions may assign a 65% risk weight to unrated corporate exposures identified
  as 'investment grade' ... Unrated corporate exposures that are not identified as 'investment grade'
  ... will be assigned a risk weight of 150%. If an institution chooses not to identify all of its
  unrated corporate exposures as 'investment grade' and 'non-investment grade' ..., the risk weight
  for all of its unrated corporate exposures will be 100%." **⚠ VERIFY** 150% (Basel CRE20.44: 100%).
- Paragraph 63: IG = internal grading system; corporate (or parent) has listed securities or
  consolidated annual sales > $75 million; SMEs excluded.
- Paragraph 64: corporate SME = consolidated annual sales ≤ $75 million; unrated SMEs 85%; SMEs meeting
  paragraph 83 → regulatory retail SBE 75%.

### Specialized lending [CRE 20.48–20.52]
Issue-specific ratings via Table 9 (issuer ratings not used). Unrated: object and commodities finance
100%; project finance 130% pre-operational, 100% operational, 80% high-quality operational.

### s.4.1.8 Subordinated debt, equity [CRE 20.53–20.62]
- Equity: 400% speculative unlisted; 250% all other equity.
- 100% for legislated programmes (incl. Specialized Financing (Banks) Regulations) up to 10% of Total
  capital.
- Subordinated debt and capital instruments other than equity (incl. non-deducted other TLAC): 150%.
- Significant investments in commercial entities: aggregate above 10% of CET1 deducted; below → 250%.
- **No equity transitional schedule** appears in CAR 2026.

### s.4.1.9 Retail [CRE 20.63–20.68]
- Regulatory retail criteria (paragraph 83): orientation, product, aggregate exposure ≤ $1.50 million,
  granularity ≤ 0.2%.
- Transactors (paragraph 84): QRR (revolving, unsecured, uncommitted; maximum $150,000 to one
  individual); cards with accrued interest < $50 over 12 months; overdrafts/LOCs undrawn for 12 months.
- Risk weights as printed: "Regulatory retail exposures that arise from exposures to transactors ...
  will be risk-weighted at **15%**. Regulatory retail exposures that do not arise from exposures to
  transactors ... will be risk-weighted at 75%. Non-regulatory retail exposures will be risk weighted
  at 100%." [cross-ref CRE 20.68]. **⚠ VERIFY** — the 15% conflicts with the cross-referenced CRE20.68
  (45%); the engine applies 45% by default (flag `ca_apply_printed_transactor_rw` selects 15%).

### s.4.1.10 Real estate — eligibility (paragraph 90) [CRE 20.71]
Finished property; legal enforceability; claims over the property (senior lien or qualifying junior
liens, LTV ≤ 80% collectively); ability to repay; prudent value; documentation. Property value held
at origination (downward adjustments only). Mortgage insurance in Canada treated as a guarantee.

### s.4.1.11 Table 10 — General residential real estate [CRE 20.82] (whole loan)
| LTV ≤ 50% | 50% < LTV ≤ 60% | 60% < LTV ≤ 70% | 70% < LTV ≤ 80% | 80% < LTV ≤ 90% | 90% < LTV ≤ 100% | LTV > 100% |
|---|---|---|---|---|---|---|
| 20% | 25% | 30% | 35% | 40% | 50% | 70% |

HELOC LTV: 75% CCF on the undrawn amount. RRE not meeting Guideline B-20 expectations: Table 11 (or
the IRB 0.22 correlation). Non-qualifying RRE: counterparty RW (individuals/SBEs 75%, SMEs 85%,
otherwise unsecured RW).

### s.4.1.11 Table 11 — Income-producing residential real estate [CRE 20.80, 20.84]
| LTV ≤ 50% | 50% < LTV ≤ 60% | 60% < LTV ≤ 70% | 70% < LTV ≤ 80% | 80% < LTV ≤ 90% | 90% < LTV ≤ 100% | LTV > 100% |
|---|---|---|---|---|---|---|
| 30% | 35% | 45% | 50% | 60% | 75% | 105% |

Paragraph 101 scope: "(i) a variable rate fixed-payment residential mortgage with an LTV above 65% for
which payments are insufficient to cover the interest component of the mortgage for three or more
consecutive months due to increases in interest rates; (ii) when the prospects for servicing the loan
materially depend on the cash flows generated by the property" — Table 11 if paragraph 90 is met,
150% otherwise. Material dependence: > 50% of the income used in the serviceability assessment comes
from the property. Excluded: primary residence; housing co-operatives; public / not-for-profit housing
[CRE 20.81].

Footnote 42 (junior liens behind another institution): base RW × 1.25, not applied in the lowest LTV
bucket, capped at the RW for exposures not meeting paragraph 90.

### s.4.1.12 Table 12 — General commercial real estate [CRE 20.85]
| LTV ≤ 60% | LTV > 60% |
|---|---|
| Min(60%, RW of counterparty) | RW of counterparty |

"Risk weight of the counterparty" = 75% individuals/SBEs, 85% SMEs, otherwise the unsecured RW.

### s.4.1.12 Table 13 — Income-producing commercial real estate [CRE 20.87–20.89]
| LTV ≤ 60% | 60% < LTV ≤ 80% | LTV > 80% |
|---|---|---|
| 70% | 90% | 110% |

Non-qualifying IPCRE 150%. Footnote 51: general treatment allowed if CRE losses up to 60% LTV ≤ 0.3%
and overall CRE losses ≤ 0.5% of outstanding loans in any year.

### s.4.1.13 ADC [CRE 20.90–20.91]
150%; 100% for residential ADC with pre-sales > 50% or equity at risk ≥ 25% of as-completed value
(land LTV ≤ 60%); subordinated / mezzanine tranche 300%; high-rise (≥ 5 storeys) needs the 50%
pre-sale test (purpose-built rentals excepted).

### s.4.1.14 Table 14 — Reverse mortgages (OSFI-specific)
| Current LTV | ≤ 35% | > 35% and ≤ 55% | > 55% and ≤ 65% | > 65% and ≤ 80% | > 80% |
|---|---|---|---|---|---|
| RW | 30% | 35% | 45% | 60% | Partial deduction |

> 80%: amount above 80% LTV deducted from CET1, remainder 100%. Non-qualifying: amount above 80% LTV
deducted, remainder 150%. Undrawn amounts: CCF 40%.

### s.4.1.15 MBS
NHA MBS guaranteed by CMHC 0%; receivables from NHA MBS sales 250%; pass-throughs look through to
Tables 10–13.

### s.4.1.16 Currency mismatch (paragraph 123) [CRE 20.92–20.93]
Unhedged RRE exposures to individuals where > 10% of qualifying income is foreign-currency: RW × 1.5,
maximum 150%. Hedges must cover ≥ 90% of the instalment.

### s.4.1.18 CCFs [CRE 20.94–20.101]
| Item | CCF |
|---|---|
| Direct credit substitutes, repos / asset sales with recourse, securities lent / posted, forward asset purchases, forward forward deposits, partly paid shares, other credit substitutes | 100% |
| NIFs and RUFs | 50% |
| Transaction-related contingent items (performance bonds, bid bonds, warranties, standby LCs for non-financial obligations) | 50% |
| Commitments, regardless of maturity | 40% |
| Undrawn credit card and charge card balances ("even if they meet the criteria in paragraph 135") | 25% |
| Short-term self-liquidating trade letters of credit (issuing and confirming) | 20% |
| Unconditionally cancellable commitments | 10% |

Lower of two CCFs applies to commitments to provide OBS items (footnote 56).

### s.4.1.21 Defaulted [CRE 20.104–20.108]
150% if specific provisions < 20% of outstanding; 100% if ≥ 20%. Defaulted RRE not cash-flow
dependent: 100%.

### s.4.1.23 Other assets [CRE 20.109–20.110]
0%: cash, gold bullion (own vaults / allocated). 20%: cheques and items in transit. 100%: premises,
fixed assets, other investments, prepaid expenses, ROU assets, unidentifiable receivables, all other
assets. 250%: threshold-deduction items below thresholds; PV of future spread income subject to
prepayment. 1250%: credit-enhancing I/O strips, certain unrated securitisation exposures.

### s.4.2.3.5 Table 15 — Issue-specific short-term ratings [CRE 21.16]
| A-1/P-1 | A-2/P-2 | A-3/P-3 | Others |
|---|---|---|---|
| 20% | 50% | 100% | 150% |

### s.4.3 CRM
- Comprehensive approach [CRE 22.46]: E′ = max{0, [E × (1 + He) − C × (1 − Hc − Hfx)]}.
- Maturity mismatch [CRE 22.13]: Pa = P × (t − 0.25)/(T − 0.25), t = min{T, residual protection},
  T = min{5, residual exposure}; recognised only with original maturity ≥ 1 year and residual ≥ 3
  months.
- Haircut scaling [CRE 22.59]: H = H10 × √((N_R + T_M − 1)/10); minimum holding periods: repo-style 5,
  other capital market 10, secured lending 20 business days.
- Hfx = 8% (10-day). Non-eligible instruments lent in SFTs: 30%.
- Simple approach floor 20%; 0%/10% repo exemptions [CRE 22.33–22.39].
- Credit derivatives without restructuring: 60% recognition [CRE 22.75].
- Guarantees: substitution of the guarantor's RW where lower [CRE 22.79]; guarantee FX haircut
  GA = G × (1 − HFX) [CRE 22.82].
- Mortgage insurance (paragraphs 273–275): NHA / provincial insured → Government of Canada 0%.
  Private insurer with GoC backstop: deductible portion = 10% of original loan amount (risk-weighted
  as the insurer, or as the borrower × 2.2, footnote 97); backstop portion = sovereign.

#### Supervisory haircuts, 10-business-day holding period [CRE 22.49]
| Issue rating | Residual maturity | Sovereigns | Other issuers | Securitisation |
|---|---|---|---|---|
| AAA to AA− / A-1 | ≤ 1 year | 0.5 | 1 | 2 |
| | > 1, ≤ 3 years | 2 | 3 | 8 |
| | > 3, ≤ 5 years | 2 | 4 | 8 |
| | > 5, ≤ 10 years | 4 | 6 | 16 |
| | > 10 years | 4 | 12 | 16 |
| A+ to BBB− / A-2 / A-3 / P-3, unrated bank securities | ≤ 1 year | 1 | 2 | 4 |
| | > 1, ≤ 3 years | 3 | 4 | 12 |
| | > 3, ≤ 5 years | 3 | 6 | 12 |
| | > 5, ≤ 10 years | 6 | 12 | 24 |
| | > 10 years | 6 | 20 | 24 |
| BB+ to BB− | All | 15 | Not eligible | Not eligible |
| Main index equities (incl. convertibles) and gold | | 20 | | |
| Other equities / convertibles on a recognised exchange | | 30 | | |
| UCITS / mutual funds | | highest haircut of any eligible holding (or LTA weighted average) | | |
| Cash in the same currency | | 0 | | |

---

## Chapter 7 — SA-CCR

- s.7.1.7 [CRE 52.1]: **EAD = alpha × (RC + PFE), alpha = 1.4.** No alpha exemption for commercial
  end-users, non-financials or pension funds is printed. (s.7.1.5: IMM alpha 1.4; own estimates
  floored at 1.2.)
- RC unmargined = max{V − C, 0}; RC margined = max{V − C; TH + MTA − NICA; 0} [CRE 52.10–52.18].
  Margined EAD capped at unmargined EAD [CRE 52.2].
- s.7.1.7.3 [CRE 52.23]: multiplier = min{1; Floor + (1 − Floor) × exp((V − C) / (2 × (1 − Floor) ×
  AddOn_aggregate))}, Floor = 5%. PFE = multiplier × AddOn_aggregate.
- s.7.1.7.12 [CRE 52.48–52.53]: MF_unmargined = √(min{M, 1 year}/1 year), M floored at 10 business
  days; MF_margined = 3/2 × √(MPOR/1 year); MPOR floors 10 bd (daily margin), 9 + N bd, 20 bd for
  > 5,000 trades or illiquid collateral / hard-to-replace derivatives; doubled after > 2 disputes.

### Table 2 — Supervisory parameters [CRE 52.72]
| Asset class | Subclass | SF | Correlation | Option vol |
|---|---|---|---|---|
| Interest rate | — | 0.50% | N/A | 50% |
| Foreign exchange | — | 4.0% | N/A | 15% |
| Credit, single name | AAA | 0.38% | 50% | 100% |
| | AA | 0.38% | 50% | 100% |
| | A | 0.42% | 50% | 100% |
| | BBB | 0.54% | 50% | 100% |
| | BB | 1.06% | 50% | 100% |
| | B | 1.6% | 50% | 100% |
| | CCC | 6.0% | 50% | 100% |
| Credit, index | IG | 0.38% | 80% | 80% |
| | SG | 1.06% | 80% | 80% |
| Equity, single name | — | 32% | 50% | 120% |
| Equity, index | — | 20% | 80% | 75% |
| Commodity | Electricity | 40% | 40% | 150% |
| | Oil/Gas | 18% | 40% | 70% |
| | Metals | 18% | 40% | 70% |
| | Agricultural | 18% | 40% | 70% |
| | Other | 18% | 40% | 70% |

---

## Chapter 8 — CVA

- s.8.1 [MAR 50.9]: "Any institution whose aggregate notional amount of non-centrally cleared
  derivatives is less than or equal to **$150 billion** is deemed as being below the materiality
  threshold" and may set CVA capital equal to 100% of its CCR capital requirement (no hedge
  recognition; whole portfolio; OSFI may remove the option).
- s.8.2.1 [MAR 50.14]: capital = DS_BA-CVA × K_reduced, DS_BA-CVA = 0.65;
  K_reduced = √[(ρ · Σ_c SCVA_c)² + (1 − ρ²) · Σ_c SCVA_c²], ρ = 50%.
- [MAR 50.15]: SCVA_c = (1/α) · RW_c · Σ_NS M_NS · EAD_NS · DF_NS, α = 1.4;
  DF_NS = (1 − e^(−0.05·M_NS)) / (0.05·M_NS) (non-IMM), 1 (IMM).
- s.8.2.2 [MAR 50.20–50.25]: K_full = β · K_reduced + (1 − β) · K_hedged, β = 0.25;
  K_hedged = √[(ρ · Σ_c (SCVA_c − SNH_c) − IH)² + (1 − ρ²) · Σ_c (SCVA_c − SNH_c)² + Σ_c HMA_c];
  SNH_c = Σ_h r_hc · RW_h · M_h · B_h · DF_h; IH = Σ_i RW_i · M_i · B_i · DF_i (index RW × 0.7);
  HMA_c = Σ_h (1 − r_hc²) · (RW_h · M_h · B_h · DF_h)².
- s.8.3.3: SA-CVA m_CVA = 1 [MAR 50.41]. RWA = 12.5 × capital.

### Table 1 — Supervisory risk weights RW_c [MAR 50.16]
| Sector of counterparty | IG | HY and NR |
|---|---|---|
| Sovereigns including central banks and MDBs | 0.5% | 2.0% |
| Local government, government-backed non-financials, education and public administration | 1.0% | 4.0% |
| Financials including government-backed financials | 5.0% | 12.0% |
| Basic materials, energy, industrials, agriculture, manufacturing, mining and quarrying | 3.0% | 7.0% |
| Consumer goods and services, transportation and storage, administrative and support service activities | 3.0% | 8.5% |
| Technology, telecommunications | 2.0% | 5.5% |
| Health care, utilities, professional and technical activities | 1.5% | 5.0% |
| Other sector | 5.0% | 12.0% |

### Table 2 — r_hc [MAR 50.26]
| Single-name hedge of counterparty c | r_hc |
|---|---|
| References counterparty c directly | 100% |
| Has legal relation with counterparty c | 80% |
| Shares sector and region with counterparty c | 50% |
