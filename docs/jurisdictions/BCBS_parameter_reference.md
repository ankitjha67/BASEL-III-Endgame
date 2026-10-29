# BCBS Basel Framework — Parameter Reference (International Baseline)

Verbatim transcription of every table and formula implemented in `src/jurisdictions/bcbs/`.
This is the audit trail for `Jurisdiction.BCBS`, the regime the other jurisdiction packages
are compared against.

**Sources**

| Short name | Document | Use |
|---|---|---|
| Framework | *The Basel Framework*, BIS consolidated standards, generated 29/10/2026 (1,429 pp.) | **Authority** |
| d424 | BCBS d424, *Basel III: Finalising post-crisis reforms*, December 2017 | Cross-check; equations that appear only as images in the Framework |

Page numbers are the Framework's "n / 1429" page footers. Where the Framework renders an
equation as an image (it does not survive text extraction), the equation is taken from d424
and both paragraph numbers are given. Where the two texts differ, the Framework is followed and
the difference is recorded in § 12.

Paragraph numbering is the Framework's (e.g. CRE20.104 is the defaulted-exposure definition).
Some comments in `src/jurisdictions/base.py` use older numbering (e.g. OBS "CRE20.92-20.101",
defaulted "CRE20.102-20.105", other assets "CRE20.106-20.107"); the Framework numbers are:
currency mismatch CRE20.92-20.93, CCFs CRE20.94-20.101, CCR CRE20.102, nth-to-default
CRE20.103, defaulted CRE20.104-20.108, other assets CRE20.109-20.110.

Amounts are in $M in the engine. Thresholds the Framework states in EUR (SME EUR 50m, retail
EUR 1m, OpRisk EUR 1bn / 30bn, loss threshold EUR 20,000, CVA EUR 100bn) are kept in EUR as stated.

---

## 1. National discretions (`BCBSOptions`)

| Option | Provision | BCBS default |
|---|---|---|
| `external_ratings_allowed` | CRE20.17, 20.42, 20.44 | True (ECRA / Table 10) |
| `pse_option` | CRE20.11 "at national discretion, according to either of the following two options" | 1 (engine choice — the Framework names no default) |
| `pse_treated_as_sovereign` | CRE20.12 | False |
| `domestic_sovereign_rw` | CRE20.8, CRE22.84 | None (not exercised) |
| `use_eca_scores` | CRE20.9 | False |
| `investment_grade_corporate_65` | CRE20.46 "may assign a 65% risk weight" | True (only used without ratings) |
| `residential_re_treatment` | CRE20.82 whole loan / CRE20.83 loan splitting ("jurisdictions may apply") | WHOLE_LOAN |
| `commercial_re_treatment` | CRE20.85 / CRE20.86 | WHOLE_LOAN |
| `cre_cash_flow_exemption` | CRE20.87 footnote 122 | False |
| `legislative_programme_equity_100` | CRE20.59 "National supervisors may allow" | False |
| `defaulted_50pct_discretion` | CRE20.106 footnote 129 | False |
| `equity_transition_year` | CRE90.1 | None (fully phased-in) |
| `ilm_equal_one` | OPE25.11 | False |
| `include_loss_data_bucket1` | OPE25.11 | False |
| `output_floor_transitional_cap` | RBC90.2 | False |
| `ccr_cva_materiality_option` | MAR50.9 | False (helper `cva.materiality_alternative`) |

---

## 2. CRE20 — Standardised approach: individual exposures (pp. 179-217)

### CRE20.7 Table 1 — Sovereigns and central banks (p. 181-182)

| External rating | AAA to AA– | A+ to A– | BBB+ to BBB– | BB+ to B– | Below B– | Unrated |
|---|---|---|---|---|---|---|
| Risk weight | 0% | 20% | 50% | 100% | 150% | 100% |

CRE20.8: "At national discretion, a lower risk weight may be applied to banks' exposures to their
sovereign (or central bank) of incorporation denominated in domestic currency and funded in that
currency."

### CRE20.9 Table 2 — ECA risk scores (p. 182)

| ECA risk scores | 0 to 1 | 2 | 3 | 4 to 6 | 7 |
|---|---|---|---|---|---|
| Risk weight | 0% | 20% | 50% | 100% | 150% |

CRE20.10: "Exposures to the Bank for International Settlements, the International Monetary Fund,
the European Central Bank, the European Union, the European Stability Mechanism and the European
Financial Stability Facility may receive a 0% risk weight."

### CRE20.11 Table 3 — PSEs, Option 1 (external rating of the sovereign) (p. 183)

| Rating of sovereign | AAA to AA– | A+ to A– | BBB+ to BBB– | BB+ to B– | Below B– | Unrated |
|---|---|---|---|---|---|---|
| RW | 20% | 50% | 100% | 100% | 150% | 100% |

### CRE20.11 Table 4 — PSEs, Option 2 (external rating of the PSE) (p. 183)

| Rating of PSE | AAA to AA– | A+ to A– | BBB+ to BBB– | BB+ to B– | Below B– | Unrated |
|---|---|---|---|---|---|---|
| RW | 20% | 50% | 50% | 100% | 150% | 50% |

CRE20.12: certain domestic PSEs "may also be treated as exposures to the sovereigns in whose
jurisdictions the PSEs are established."

### CRE20.14-20.15 — MDBs (pp. 184-185)

CRE20.14: "A 0% risk weight will be applied to exposures to MDBs that fulfil to the Committee's
satisfaction the eligibility criteria" (footnote 91 list: World Bank Group, ADB, AfDB, EBRD, IADB,
EIB, EIF, NIB, CDB, IsDB, CEB, IFFIm, AIIB).

CRE20.15 Table 5 ("base" risk weight); "Banks incorporated in jurisdictions that do not allow
external ratings for regulatory purposes will risk-weight such exposures at 50%."

| Rating | AAA to AA– | A+ to A– | BBB+ to BBB– | BB+ to B– | Below B– | Unrated |
|---|---|---|---|---|---|---|
| RW | 20% | 30% | 50% | 100% | 150% | 50% |

### CRE20.18 Table 6 — Banks, ECRA (p. 186)

| Rating | AAA to AA– | A+ to A– | BBB+ to BBB– | BB+ to B– | Below B– |
|---|---|---|---|---|---|
| "Base" RW | 20% | 30% | 50% | 100% | 150% |
| RW for short-term exposures | 20% | 20% | 20% | 50% | 150% |

No unrated column: "Banks incorporated in jurisdictions that allow the use of external ratings ...
must only apply SCRA for their unrated bank exposures."

CRE20.19 / CRE20.31: "Exposures to banks with an original maturity of three months or less, as
well as exposures to banks that arise from the movement of goods across national borders with an
original maturity of six months or less can be assigned a risk weight that correspond to the risk
weights for short term exposures".

CRE20.20 (and CRE20.39, CRE20.42): if due diligence reflects higher risk "the bank must assign a
risk weight at least one bucket higher than the 'base' risk weight".

### CRE20.21 Table 7 — Banks, SCRA (p. 188)

| Grade | A | B | C |
|---|---|---|---|
| "Base" RW | 40% | 75% | 150% |
| RW for short-term exposures | 20% | 50% | 150% |

Footnote 98: "exposures to banks without an external credit rating may receive a risk weight of
30%, provided that the counterparty bank has a Common Equity Tier 1 ratio which meets or exceeds
14% and a Tier 1 leverage ratio which meets or exceeds 5%. The counterparty bank must also satisfy
all the requirements for Grade A classification."

CRE20.27: exposures not meeting Grade A are Grade B "unless the exposure falls within Grade C".

CRE20.32 (sovereign floor): "a risk-weight floor based on the risk weight applicable to exposures
to the sovereign of the country where the bank counterparty is incorporated will be applied ...
when: (i) the exposure is not in the local currency of the jurisdiction of incorporation of the
debtor bank; and (ii) for a borrowing booked in a branch ... not in the local currency of the
jurisdiction in which the branch operates. The sovereign floor will not apply to short-term (ie
with a maturity below one year) self-liquidating, trade-related contingent items that arise from
the movement of goods."

### CRE20.38 Table 8 — Rated covered bonds (issue-specific rating) (p. 191)

| Rating | AAA to AA– | A+ to A– | BBB+ to BBB– | BB+ to B– | Below B– |
|---|---|---|---|---|---|
| "Base" RW | 10% | 20% | 20% | 50% | 100% |

### CRE20.38 Table 9 — Unrated covered bonds (p. 192)

| RW of the issuing bank | 20% | 30% | 40% | 50% | 75% | 100% | 150% |
|---|---|---|---|---|---|---|---|
| "Base" RW | 10% | 15% | 20% | 25% | 35% | 50% | 100% |

Eligibility (CRE20.34-20.37): RRE cover assets LTV ≤ 80%; CRE ≤ 60%; bank claims (≤ 30% RW)
≤ 15% of issuance; over-collateralisation ≥ 10%; semi-annual portfolio information.

### CRE20.43 Table 10 — Corporates, jurisdictions using external ratings (p. 194)

| Rating | AAA to AA– | A+ to A– | BBB+ to BBB– | BB+ to BB– | Below BB– | Unrated |
|---|---|---|---|---|---|---|
| "Base" RW | 20% | 50% | 75% | 100% | 150% | 100% |

Note the Table 10 bucket boundary is BB– (not B– as in Tables 1-6): `RatingBucket.B_PLUS_TO_B_MINUS`
maps to 150%.

- CRE20.44: non-ratings jurisdictions "assign a 100% risk weight to all corporate exposures",
  except investment grade (CRE20.46) and SMEs (CRE20.47).
- CRE20.46: "may assign a 65% risk weight to exposures to 'investment grade' corporates".
- CRE20.47: SME = "reported annual sales for the consolidated group ... less than or equal to
  €50 million"; "For unrated exposures to corporate SMEs in jurisdictions that allow the use of
  external ratings ... and for all exposures to corporate SMEs in jurisdictions that do not ...,
  an 85% risk weight will be applied."

### CRE20.50-20.52 — Specialised lending (pp. 195-196)

- CRE20.50: issue-specific ratings via Table 10; "Issuer ratings must not be used".
- CRE20.51(1): "Object and commodities finance exposures will be risk-weighted at 100%";
- CRE20.51(2): "Project finance exposures will be risk-weighted at 130% during the
  pre-operational phase and 100% during the operational phase. Project finance exposures in the
  operational phase which are deemed to be high quality, as described in CRE20.52, will be risk
  weighted at 80%."

### CRE20.53-20.62 — Subordinated debt, equity (pp. 197-200)

- CRE20.57: "a risk weight of 400% to speculative unlisted equity exposures ... and a risk weight
  of 250% to all other equity holdings, with the exception of those equity holdings referred to in
  CRE20.59."
- CRE20.59: "National supervisors may allow banks to assign a risk weight of 100% to equity
  holdings made pursuant to national legislated programmes ... up to an aggregate of 10% of the
  bank's Total capital."
- CRE20.60: "a risk weight of 150% to subordinated debt and capital instruments other than
  equities" (incl. non-deducted other TLAC liabilities).
- CRE20.61-20.62: significant investments in commercial entities: materiality thresholds 15%
  (individual) and 60% (aggregate) of the bank's capital; "Investments in excess of the
  materiality thresholds must be risk-weighted at 1250%."
- CRE20.109: "A 250% risk weight applies to the amount of the three 'threshold deduction' items
  listed in CAP30.32 that are not deducted".

US-only `EquityType.PUBLICLY_TRADED` / `NON_PUBLIC` have no Basel bucket and fall to 250%.

### CRE90.1 — Equity phase-in (p. 514)

"The risk weight treatment described in CRE20.57, excluding equity holdings referred to in
CRE20.59, will be subject to a five-year linear phase-in arrangement from 1 January 2023. For
speculative unlisted equity exposures, the applicable risk weight will start at 100% and increase
by 60 percentage points at the end of each year until the end of Year 5. For all other equity
holdings, the applicable risk weight will start at 100% and increase by 30 percentage points at
the end of each year until the end of Year 5."

| Year | 2023 | 2024 | 2025 | 2026 | 2027 | 2028+ |
|---|---|---|---|---|---|---|
| Other equity | 100% | 130% | 160% | 190% | 220% | 250% |
| Speculative unlisted | 100% | 160% | 220% | 280% | 340% | 400% |

(Derived schedule: Year 1 = 2023; increments at the end of each year.)

### CRE20.65-20.68 — Retail (pp. 200-201)

- Regulatory retail criteria (CRE20.65): product criterion; "maximum aggregated exposure to one
  counterparty cannot exceed an absolute threshold of €1 million"; granularity "0.2% of the
  overall regulatory retail portfolio".
- CRE20.66 transactors: balance repaid in full at each scheduled date for the previous 12 months;
  overdrafts with no drawdown over 12 months.
- CRE20.68: "(1) Regulatory retail exposures that do not arise from exposures to transactors ...
  75%. (2) ... transactors ... 45%. (3) Other retail exposures will be risk weighted at 100%."

### CRE20.82 Table 11 — RRE whole loan, not materially dependent on cash flows (p. 208)

| LTV | ≤ 50% | 50% < LTV ≤ 60% | 60% < LTV ≤ 80% | 80% < LTV ≤ 90% | 90% < LTV ≤ 100% | > 100% |
|---|---|---|---|---|---|---|
| RW | 20% | 25% | 30% | 40% | 50% | 70% |

### CRE20.83 — RRE loan splitting

"the risk weight of 20% is applied to the part of the exposure up to 55% of the property value and
the risk weight of the counterparty (as prescribed in CRE20.89(1)) is applied to the residual
exposure." Footnote 120 worked example: "for a loan of €70,000 to an individual secured on a
property valued at €100,000, the bank will apply a risk weight of 20% to €55,000 of the exposure
and, according to CRE20.89(1), a risk weight of 75% to the residual exposure of €15,000. This
gives total risk weighted assets for the exposure of €22,250". (Tested.)

Footnote 115 (junior liens, whole loan): "determine the 'base' risk weight based on Tables 11, 12,
13 or 14 as applicable and adjust the 'base' risk weight by a multiplier of 1.25 ... If the 'base'
risk weight corresponds to the lowest LTV bucket, the multiplier will not be applied. The
resulting risk weight ... will be capped at the risk weight applied to the exposure when the
requirements in CRE20.71 are not met."

### CRE20.84 Table 12 — RRE materially dependent on cash flows (p. 209)

| LTV | ≤ 50% | 50% < LTV ≤ 60% | 60% < LTV ≤ 80% | 80% < LTV ≤ 90% | 90% < LTV ≤ 100% | > 100% |
|---|---|---|---|---|---|---|
| RW | 30% | 35% | 45% | 60% | 75% | 105% |

### CRE20.85 Table 13 — CRE whole loan, not materially dependent on cash flows (p. 210)

| | LTV ≤ 60% | LTV > 60% |
|---|---|---|
| RW | Min (60%, RW of counterparty) | RW of counterparty |

CRE20.86 (loan splitting): "the risk weight of 60% or the risk weight of the counterparty,
whichever is lower, is applied to the part of the exposure up to 55% of the property value, and
the risk weight of the counterparty is applied to the residual exposure."

### CRE20.87 Table 14 — CRE materially dependent on cash flows (p. 210)

| LTV | ≤ 60% | 60% < LTV ≤ 80% | > 80% |
|---|---|---|---|
| RW | 70% | 90% | 110% |

Footnote 122: national supervisors may allow CRE20.85-20.86 where "(i) the losses stemming from
commercial real estate lending up to 60% of LTV must not exceed 0.3% of the outstanding loans in
any given year and (ii) overall losses ... must not exceed 0.5%".

### CRE20.89 — Other real estate (p. 211)

"(1) The risk weight of the counterparty is used for other real estate exposures that are not
materially dependent on the cash flows generated by the property. For exposures to individuals
the risk weight applied will be 75%. For exposures to SMEs, the risk weight applied will be 85%.
For exposures to other counterparties, the risk weight applied is the risk weight that would be
assigned to an unsecured exposure to that counterparty. (2) The risk weight of 150% is used for
other real estate exposures that are materially dependent on the cash flows generated by the
property."

### CRE20.90-20.91 — Land ADC (pp. 211-212)

"ADC exposures will be risk-weighted at 150%"; "ADC exposures to residential real estate may be
risk weighted at 100%" where underwriting meets CRE20.71 and pre-sale/pre-lease contracts or
equity at risk are substantial.

### CRE20.92-20.93 — Currency mismatch (p. 212)

"For unhedged retail and residential real estate exposures to individuals where the lending
currency differs from the currency of the borrower's source of income, banks will apply a 1.5
times multiplier to the applicable risk weight according to CRE20.63 to CRE20.68 and CRE20.82 to
CRE20.84, subject to a maximum risk weight of 150%." Hedges count where they "cover at least 90%
of the loan instalment".

### CRE20.94-20.101 — Credit conversion factors (pp. 213-215)

| Item | CCF | Paragraph |
|---|---|---|
| Direct credit substitutes, repos / asset sales with recourse, securities lending / posted collateral, forward asset purchases / forward forward deposits / partly paid shares, other credit substitutes | 100% | CRE20.95(1)-(5) |
| Note issuance facilities and revolving underwriting facilities, regardless of maturity | 50% | CRE20.96 |
| Transaction-related contingent items | 50% | CRE20.97 |
| Commitments, regardless of maturity, unless they qualify for a lower CCF | 40% | CRE20.98 |
| Short-term self-liquidating trade letters of credit (maturity below one year), issuing and confirming banks | 20% | CRE20.99 |
| Commitments unconditionally cancellable at any time without prior notice / automatic cancellation | 10% | CRE20.100 |
| Undertaking to provide a commitment on an OBS item: lower of the two CCFs | — | CRE20.101 |

### CRE20.104-20.108 — Defaulted exposures (pp. 216-217)

- Default = past due > 90 days or defaulted borrower (CRE20.104).
- CRE20.106: "(1) 150% risk weight when specific provisions are less than 20% of the outstanding
  amount of the loan; and (2) 100% risk weight when specific provisions are equal or greater than
  20%". Footnote 129: "National supervisors have discretion to reduce the risk weight to 50% when
  specific provisions are no less than 50% of the outstanding amount of the loan."
- CRE20.107: "Defaulted residential real estate exposures where repayments do not materially
  depend on cash flows generated by the property ... at 100%."

### CRE20.109-20.110 — Other assets (p. 217)

"The standard risk weight for all other assets will be 100%", except 0% for "cash owned and held
at the bank or in transit" and "gold bullion held at the bank or held in another bank on an
allocated basis, to the extent the gold bullion assets are backed by gold bullion liabilities";
20% for "cash items in the process of collection". CRE20.109: 250% for non-deducted threshold
items. CRE20.103: nth-to-default sold protection — basket RWs aggregated "up to a maximum of 1250%".

---

## 3. CRE21 — Use of external ratings (pp. 218-224)

### CRE21.16 Table 15 — Specific short-term ratings (p. 223)

| Rating | A-1/P-1 | A-2/P-2 | A-3/P-3 | Others |
|---|---|---|---|---|
| RW | 20% | 50% | 100% | 150% |

"Short-term ratings may only be used for short-term exposures against banks and corporates."
CRE21.10-21.11 (multiple ratings: higher of two; of three or more, the higher of the two lowest)
are the caller's responsibility when mapping to `RatingBucket`.

---

## 4. CRE22 — Credit risk mitigation (pp. 225-249)

### Maturity mismatch (CRE22.12-22.13; equation from d424 para 129)

    Pa = P × (t − 0.25) / (T − 0.25)
    t = min{T, residual maturity of the credit protection arrangement, years}
    T = min{five years, residual maturity of the exposure, years}

Recognised only if original maturity ≥ 1 year and residual maturity ≥ 3 months (CRE22.12).

### Simple approach (CRE22.33-22.39)

- CRE22.33: collateralised portion "receive[s] the risk weight applicable to the collateral
  instrument ... subject to a floor of 20%"; revaluation at least every six months; no maturity
  mismatch.
- CRE22.38: qualifying repos "receive a 10% risk weight"; 0% with a core market participant.
- CRE22.39: 0% where same currency and "(1) the collateral is cash on deposit ...; or (2) ...
  sovereign/PSE securities eligible for a 0% risk weight, and its market value has been
  discounted by 20%."

### Comprehensive approach (CRE22.46; equation from d424 para 160)

    E* = max{0, E × (1 + He) − C × (1 − Hc − Hfx)}

### CRE22.49 — Supervisory haircuts, jurisdictions allowing external ratings (pp. 236-237; d424 Table 14)

10-business-day holding period, daily mark-to-market and remargining; percentages.

| Issue rating | Residual maturity | Sovereigns | Other issuers | Securitisation |
|---|---|---|---|---|
| AAA to AA–/A-1 | ≤ 1 year | 0.5 | 1 | 2 |
| | > 1 year, ≤ 3 years | 2 | 3 | 8 |
| | > 3 years, ≤ 5 years | 2 | 4 | 8 |
| | > 5 years, ≤ 10 years | 4 | 6 | 16 |
| | > 10 years | 4 | 12 | 16 |
| A+ to BBB–/A-2/A-3/P-3 and unrated bank securities (CRE22.34(3)(b)) | ≤ 1 year | 1 | 2 | 4 |
| | > 1 year, ≤ 3 years | 3 | 4 | 12 |
| | > 3 years, ≤ 5 years | 3 | 6 | 12 |
| | > 5 years, ≤ 10 years | 6 | 12 | 24 |
| | > 10 years | 6 | 20 | 24 |
| BB+ to BB– | All | 15 | Not eligible | Not eligible |
| Main index equities (incl. convertible bonds) and gold | | 20 | | |
| Other equities and convertible bonds listed on a recognised exchange | | 30 | | |
| UCITS/mutual funds | | Highest haircut applicable to any security in which the fund can invest (or LTA weighted average) | | |
| Cash in the same currency | | 0 | | |

The sovereign and securitisation columns merge the 1-3y/3-5y cells and the 5-10y/>10y cells (the
value is printed once across the merged rows in both the Framework and d424 Table 14).

CRE22.51: "Sovereigns" includes PSEs treated as sovereigns and 0%-RW MDBs; "Other issuers"
includes PSEs not treated as sovereigns.

### CRE22.50 — Supervisory haircuts, jurisdictions not allowing external ratings (pp. 237-238; d424 Table 15)

| Residual maturity | Sovereign issuer RW 0% | 20% or 50% | 100% | Other IG non-securitisation (CRE22.34(4)(c)) | Senior securitisation SA RW < 100% |
|---|---|---|---|---|---|
| ≤ 1 year | 0.5 | 1 | 15 | 2 | 4 |
| > 1 year, ≤ 3 years | 2 | 3 | 15 | 4 | 12 |
| > 3 years, ≤ 5 years | 2 | 3 | 15 | 6 | 12 |
| > 5 years, ≤ 10 years | 4 | 6 | 15 | 12 | 24 |
| > 10 years | 4 | 6 | 15 | 20 | 24 |
| Main index equities (incl. convertible bonds) and gold | 20 | | | | |
| Other equities / convertibles listed on a recognised exchange | 30 | | | | |
| UCITS/mutual funds | Highest haircut of any eligible security (or LTA weighted average) | | | | |
| Cash in the same currency | 0 | | | | |
| Other exposure types | 30 | | | | |

### Other CRM parameters

- CRE22.52: "The haircut for currency risk (Hfx) ... is 8% (also based on a 10-business day
  holding period and daily mark-to-market)."
- CRE22.54: non-eligible instruments lent/posted in SFTs: "the haircut to be applied on the
  exposure must be 30%".
- CRE22.55 (d424 para 168): basket haircut `H = Σ_i a_i H_i`.
- CRE22.57 minimum holding periods: repo-style 5 business days (daily remargining); other capital
  market transactions 10 (daily remargining); secured lending 20 (daily revaluation). CRE22.58:
  20 days for > 5,000 trades or illiquid collateral; doubled after > 2 lengthy margin disputes.
- CRE22.59 (equation from d424 para 172): `H = H10 × sqrt[(NR + (TM − 1)) / 10]`.
- CRE22.75: credit derivatives without restructuring: "60% of the amount of the hedge can be
  recognised", capped at 60% of the underlying.
- CRE22.79: protected portion at the protection provider's RW; portion below a materiality
  threshold at 1250%.
- CRE22.82-22.83 (equation from d424 para 204): `GA = G × (1 − HFX)`, HFX = 8% (10-day, scaled
  by the square-root-of-time formula).
- CRE22.76: eligible protection providers — sovereigns, PSEs, MDBs, banks, securities firms and
  other prudentially regulated FIs with a lower RW than the counterparty; with ratings, other
  externally rated entities; without ratings, "investment grade" entities with listed securities.

---

## 5. CRE52 — SA-CCR (pp. 434-462)

- CRE52.1: "EAD ... is determined using the following formula, where: alpha = 1.4" —
  `EAD = alpha × (RC + PFE)` (equation image; confirmed by CRE99.125: "USD 161 (= 1.4 *(100+15))").
  The Framework has **no** alpha exemption for non-financial or pension counterparties.
- CRE52.20: `PFE = multiplier × AddOn_aggregate`.
- CRE52.22-52.23: "the multiplier is floored at 5% of the PFE add-on"; "Floor is 5%; V is the value
  of the derivative transactions in the netting set; C is the haircut value of net collateral held".
  Equation (image in the Framework; transcription cross-checked against CRR Art. 278(3)):

      multiplier = min{1; Floor + (1 − Floor) × exp[(V − C) / (2 × (1 − Floor) × AddOn_aggregate)]}

- CRE52.48-52.49: unmargined MF uses "the lesser of one year and the remaining maturity ... floored
  at ten business days"; 250 business days per year. `MF = sqrt(min(M, 1 year) / 1 year)`.
- CRE52.52 / CRE52.2 FAQ1 ("the 3/2 multiplier in CRE52.52"): `MF = 3/2 × sqrt(MPOR / 1 year)`.
- CRE52.50-52.51 MPOR floors: 10 business days (daily margin); 9 + remargining period otherwise;
  20 days for > 5000 transactions or illiquid collateral / hard-to-replace OTC derivatives;
  doubled after > 2 lengthy disputes.
- CRE52.73: basis hedging sets SF × ½; volatility hedging sets SF × 5.

### CRE52.72 Table 2 — Supervisory parameters (p. 459)

| Asset class | Subclass | Supervisory factor | Correlation | Supervisory option volatility |
|---|---|---|---|---|
| Interest rate | | 0.50% | N/A | 50% |
| Foreign exchange | | 4.0% | N/A | 15% |
| Credit, single name | AAA | 0.38% | 50% | 100% |
| | AA | 0.38% | 50% | 100% |
| | A | 0.42% | 50% | 100% |
| | BBB | 0.54% | 50% | 100% |
| | BB | 1.06% | 50% | 100% |
| | B | 1.6% | 50% | 100% |
| | CCC | 6.0% | 50% | 100% |
| Credit, index | IG | 0.38% | 80% | 80% |
| | SG | 1.06% | 80% | 80% |
| Equity, single name | | 32% | 50% | 120% |
| Equity, index | | 20% | 80% | 75% |
| Commodity | Electricity | 40% | 40% | 150% |
| | Oil/Gas | 18% | 40% | 70% |
| | Metals | 18% | 40% | 70% |
| | Agricultural | 18% | 40% | 70% |
| | Other | 18% | 40% | 70% |

---

## 6. MAR50 — Basic approach for CVA risk (pp. 722-729)

Equations are images in the Framework; transcribed from d424 CVA paras 12-23.

- MAR50.1: RWA = 12.5 × capital.
- MAR50.9: "Any bank whose aggregate notional amount of non-centrally cleared derivatives is less
  than or equal to 100 billion euro is deemed as being below the materiality threshold"; such a
  bank "may choose to set its CVA capital requirement equal to 100% of the bank's capital
  requirement for counterparty credit risk"; CVA hedges not recognised; whole portfolio.
- MAR50.14 (reduced): capital = DS_BA-CVA × K_reduced, "where the discount scalar DS_BA-CVA = 0.65";
  "ρ = 50%"

      K_reduced = sqrt[ (ρ · Σ_c SCVA_c)² + (1 − ρ²) · Σ_c SCVA_c² ]

- MAR50.15: `SCVA_c = (1/α) · RW_c · Σ_NS M_NS · EAD_NS · DF_NS`, α = 1.4;
  `DF_NS = (1 − e^(−0.05·M_NS)) / (0.05·M_NS)` for non-IMM banks, 1 for IMM (footnote 357:
  "The interest rate used for discounting is set at 5%"). M_NS without the five-year cap.
- MAR50.20 (full): capital = DS_BA-CVA × K_full, DS = 0.65, "β=0.25":

      K_full = β · K_reduced + (1 − β) · K_hedged

- MAR50.21:

      K_hedged = sqrt[ (ρ · Σ_c (SCVA_c − SNH_c) − IH)² + (1 − ρ²) · Σ_c (SCVA_c − SNH_c)² + Σ_c HMA_c ]

- MAR50.23: `SNH_c = Σ_h r_hc · RW_h · M_h · B_h · DF_h`
- MAR50.24: `IH = Σ_i RW_i · M_i · B_i · DF_i`; RW_i = Table 1 × 0.7 (single sector/quality) or the
  name-weighted average × 0.7.
- MAR50.25: `HMA_c = Σ_h (1 − r_hc²) · (RW_h · M_h · B_h · DF_h)²`
- MAR50.18: eligible hedges are single-name CDS, single-name contingent CDS and index CDS only.

### MAR50.16 Table 1 — Supervisory risk weights RW_c (p. 727)

| Sector of counterparty | IG | HY and NR |
|---|---|---|
| Sovereigns including central banks and multilateral development banks | 0.5% | 2.0% |
| Local government, government-backed non-financials, education and public administration | 1.0% | 4.0% |
| Financials including government-backed financials | 5.0% | 12.0% |
| Basic materials, energy, industrials, agriculture, manufacturing, mining and quarrying | 3.0% | 7.0% |
| Consumer goods and services, transportation and storage, administrative and support service activities | 3.0% | 8.5% |
| Technology, telecommunications | 2.0% | 5.5% |
| Health care, utilities, professional and technical activities | 1.5% | 5.0% |
| Other sector | 5.0% | 12.0% |

Engine sector keys: SOVEREIGN, LOCAL_GOVERNMENT, FINANCIAL, BASIC_MATERIALS, CONSUMER,
TECHNOLOGY, HEALTH_CARE, OTHER.

### MAR50.26 Table 2 — Counterparty / single-name hedge correlations

| Single-name hedge h of counterparty c | r_hc |
|---|---|
| references counterparty c directly | 100% |
| has legal relation with counterparty c | 80% |
| shares sector and region with counterparty c | 50% |

---

## 7. OPE25 — Operational risk standardised approach (pp. 769-776)

Equations are images in the Framework; transcribed from d424 OpRisk paras 6 and 9.

- OPE25.2: `ORC = BIC × ILM`; "RWA for operational risk are equal to 12.5 times ORC."
- OPE25.4: `BI = ILDC + SC + FC`
- OPE25.5 (bar = three-year average; footnote 362: absolute values of net items year by year
  first, then averaged):

      ILDC = min[ avg|Interest Income − Interest Expense| ; 2.25% · avg(Interest Earning Assets) ] + avg(Dividend Income)
      SC   = max[ avg(Other Operating Income) ; avg(Other Operating Expense) ] + max[ avg(Fee Income) ; avg(Fee Expense) ]
      FC   = avg|Net P&L Trading Book| + avg|Net P&L Banking Book|

### OPE25.7 Table 1 — BI ranges and marginal coefficients

| Bucket | BI range (€bn) | Marginal coefficient α_i |
|---|---|---|
| 1 | ≤ 1 | 12% |
| 2 | 1 < BI ≤ 30 | 15% |
| 3 | > 30 | 18% |

Footnote 363: "given a BI = €35bn, the BIC = (1 x 12%) + (30-1) x 15% + (35-30) x 18% = €5.37bn."
(Tested.)

- OPE25.8: `ILM = ln( exp(1) − 1 + (LC / BIC)^0.8 )`; "LC is equal to 15 times average annual
  operational risk losses incurred over the previous 10 years".
- OPE25.10: 10 years of loss data; minimum five years in transition; "Banks that do not have five
  years of high-quality loss data must calculate the capital requirement based solely on the BIC."
- OPE25.11: bucket 1 — "ILM is equal to 1"; "At national discretion, supervisors may allow the
  inclusion of internal loss data into the framework for banks in bucket 1"; "at national
  discretion, supervisors may set the value of ILM equal to 1 for all banks in their jurisdiction."
- OPE25.13: banks not meeting loss data standards hold at least 100% of the BIC.
- OPE25.18: loss threshold €20,000; national discretion €100,000 for buckets 2 and 3.

---

## 8. RBC20 / RBC90 — Minimums and output floor (pp. 138-177)

- RBC20.1: CET1 ≥ 4.5%, Tier 1 ≥ 6%, Total capital ≥ 8.0% of RWA.
- RBC20.4: RWA is the higher of nominated-approach RWA and "72.5% of the sum of the elements ...
  calculated using only the standardised approaches listed in RBC20.11."
- RBC20.11: floor base = SA credit risk; nominated approach for equity investments in funds;
  SEC-ERBA/SEC-SA/1250% for securitisation (if SEC-IRBA/IAA used); SA-CCR or comprehensive
  approach (if IMM/VaR used); FRTB SA (if IMA used); nominated CVA approach; SA operational risk.
- RBC20.13 Table 1 example: pre-floor 76, standardised 140, 72.5% → 101.5. (Tested.)

### RBC90.1 Table 1 — Output floor phase-in (p. 177)

| Date | 1 Jan 2023 | 1 Jan 2024 | 1 Jan 2025 | 1 Jan 2026 | 1 Jan 2027 | 1 Jan 2028 |
|---|---|---|---|---|---|---|
| Calibration | 50% | 55% | 60% | 65% | 70% | 72.5% |

RBC90.2: "supervisors may exercise national discretion to cap the incremental increase in a bank's
total risk-weighted assets (RWA) that results from the application of the floor. This transitional
cap will be set at 25% of a bank's RWA before the application of the floor. In the example shown
in RBC20.13, ... would cap the bank's RWA to 95". (Tested; the cap is applied only in 2023-2027.)

---

## 9. RBC30 / RBC40 / SCO40 — Buffers (pp. 15-24, 156-175)

- RBC30.2: "A capital conservation buffer of 2.5%, comprised of Common Equity Tier 1".
- RBC30.4 conservation standards (no CCyB):

| CET1 ratio | 4.5%-5.125% | >5.125%-5.75% | >5.75%-6.375% | >6.375%-7.0% | >7.0% |
|---|---|---|---|---|---|
| Minimum conservation ratio | 100% | 80% | 60% | 40% | 0% |

- RBC30.9 / RBC30.12: CCyB "will vary between zero and 2.5% of risk weighted assets"; footnote 78:
  national buffers above 2.5% are not reciprocated. RBC30.13: jurisdictional weighted average.
- RBC30.17: quartiles of the (extended) buffer: 100% / 80% / 60% / 40% / 0%.
- RBC30.18 (2.5% CCyB): 4.5%-5.75% 100%; >5.75%-7.0% 80%; >7.0%-8.25% 60%; >8.25%-9.5% 40%;
  >9.5% 0%.

### RBC40.4 Table 1 — G-SIB bucketing approach (p. 170)

| Bucket | Score range | HLA (CET1 % of RWA) |
|---|---|---|
| 5 | 530-629 | 3.5% |
| 4 | 430-529 | 2.5% |
| 3 | 330-429 | 2.0% |
| 2 | 230-329 | 1.5% |
| 1 | 130-229 | 1.0% |

- SCO40.21 / RBC40.4: "The cutoff score for G-SIB designation is 130 basis points and the buckets
  ... each have a range of 100 basis points."
- RBC40.5: new buckets "will increase in increments of 1% of risk-weighted assets (eg if bucket 5
  should become populated, bucket 6 would be created with a minimum higher loss absorbency
  requirement of 4.5%)."
- RBC40.8(3), RBC40.18-40.19: home authorities "impose the higher of either the D-SIB or G-SIB
  higher loss absorbency requirements"; the two "should not be additive". D-SIB HLA levels are
  national (no Basel calibration).

---

## 10. LEV20 / LEV40 — Leverage ratio (pp. 787-813)

- LEV20.7: "Banks must meet a 3% leverage ratio minimum requirement at all times."
- LEV40.2: "The leverage ratio buffer will be set at 50% of a G-SIB's higher loss-absorbency
  risk-based requirements. For example, a G-SIB subject to a 2% higher loss-absorbency
  requirement would be subject to a 1% leverage ratio buffer requirement." Met with Tier 1 (LEV40.1).
- LEV40.5 example (bucket 1): CET1 4.5%-5.375% / leverage 3%-3.125% → 100%; ... > 8.0% / > 3.50% → 0%.

---

## 11. Items not settled by the source texts (`TODO: VERIFY`)

| Item | Where | Treatment |
|---|---|---|
| SA-CCR multiplier equation (CRE52.23) is an image in the Framework text | `params.SACCR_MULTIPLIER_FLOOR`, `saccr.pfe_multiplier` | Standard form, Floor 5% (from text); structure cross-checked to CRR Art. 278(3) |
| CCF for a self-liquidating trade LC with maturity ≥ one year (outside CRE20.99) | `params.SHORT_TERM_TRADE_LC_LONG_DATED_CCF` | 100% (CRE20.95(5) residual, conservative) |
| PSE Option 1 vs Option 2 — no Framework default | `BCBSOptions.pse_option` | Option 1 (engine choice) |

Engine conventions (documented, not regulatory parameters): SCRA grade missing → Grade B
(CRE20.27 residual); PF phase missing → pre-operational 130%; RE LTV missing → highest LTV band;
liens not held by the bank are not modelled in loan splitting (not in `SAExposure`); He = 0 for a
loan in the comprehensive approach with the CRE22.57 secured-lending 20-day holding period and
daily revaluation (repo-style / capital-market flags select 5 / 10 days); simple-approach
collateral RW uses the highest CRE20 RW within the haircut band.

---

## 12. Differences between d424 (Dec 2017) and the Basel Framework (followed)

| Item | d424 | Basel Framework | Source |
|---|---|---|---|
| Output floor phase-in | 50% from 1 Jan 2022 … 72.5% from 1 Jan 2027 | 50% from 1 Jan 2023 … 72.5% from 1 Jan 2028 | RBC90.1 (27 March 2020 deferral) |
| Equity phase-in start | "from the date of implementation of this standard" (2022) | from 1 January 2023 | CRE90.1 |
| BA-CVA discount scalar | none | DS_BA-CVA = 0.65 on K_reduced and K_full | MAR50.14, MAR50.20 |
| BA-CVA RW, sovereigns HY/NR | 3.0% | 2.0% | MAR50.16 Table 1 |
| CRM / OpRisk / CVA equations | printed | images (not extractable) | d424 used as transcription source |

---

## 13. Exposure flags read by the BCBS package

See the table in the `src/jurisdictions/bcbs/credit_risk.py` module docstring (e.g.
`is_supranational_zero_rw`, `is_zero_rw_mdb`, `due_diligence_uplift`, `foreign_currency_exposure`,
`covered_bond_ineligible`, `issue_specific_rating`, `exceeds_commercial_materiality_threshold`,
`counterparty_is_individual`, `counterparty_is_corporate`, `junior_lien`, `defaulted_rre_non_cf`,
`is_cash`, `is_gold_bullion`, `is_cash_in_collection`, `is_threshold_deduction_item`,
`commitment_to_issue_obs_item`, `commitment_unconditionally_cancellable`,
`collateral_currency_mismatch`, `guarantee_currency_mismatch`, `repo_style`, `capital_market_txn`,
`crm_simple_approach`, `guarantor_investment_grade`, `guarantee_domestic_currency_funded`).
