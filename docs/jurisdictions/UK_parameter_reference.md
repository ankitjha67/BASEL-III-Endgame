# UK PRA Basel 3.1 -- Parameter Reference (PS1/26)

**Source (authority):** PRA PS1/26 Appendix 1, *PRA Rulebook: CRR Firms: (CRR) Instrument 2026*
(PRA2026/1), made 13 January 2026 by the Prudential Regulation Committee; all Annexes in force
**1 January 2027** (instrument para F). 492 pages. Page references are "p. N of 492" of that
instrument. Context only: PS1/26 Appendix 2 and the PS1/26 web page (implementation dates,
para 1.16 on the removal of Pillar 1 support factors, para 1.24 on FRTB-IMA from 1 January 2028).

This file transcribes, table by table, every parameter implemented in `src/jurisdictions/uk/`.
Text in quotation marks is copied from the instrument. Sections 8-9 also transcribe the PRA Rulebook
web text (in force 1 January 2027) of the Counterparty Credit Risk (CRR) Part and Capital Buffers
Part, which the instrument only cross-references. Items still unsettled are listed at the end under
**Not in the supplied texts (TODO: VERIFY)**; the Pillar 1 securitisation, SA-CVA, leverage, large
exposure and CCP rules are in `UK_pillar1_reference.md`.

Amounts stated in GBP in the rules are carried in GBP millions in code (e.g. GBP 880,000 = 0.88).

---

## 1. Glossary Part (Annex A)

### SME (p. 9)
> "in the Credit Risk: Standardised Approach (CRR) Part and the Credit Risk: Internal Ratings Based
> Approach (CRR) Part means a micro, small or medium enterprise with an annual turnover of not more
> than GBP 44 million where: (1) the annual turnover shall be calculated on the basis of the highest
> consolidated accounts of the group to which the enterprise belongs ..."

### transactor exposure (p. 9)
> "means an exposure to an obligor for the following revolving facilities: (1) revolving facilities
> where: (a) the balance to be repaid at each scheduled repayment date is determined as the amount
> drawn at a pre-defined reference date (including credit cards and charge cards); and (b) the obligor
> has repaid the balance in full at each scheduled repayment date for the previous 12-month period;
> and (2) an overdraft facility which the obligor has not drawn down over the previous 12-month period."

### higher risk equity exposure (p. 5)
> "means an equity exposure that is: (1) not listed on a recognised exchange; and (2) to an
> undertaking ('A') whose business has existed for a period of less than five years ..."

### Other definitions used
- **ADC exposure** (p. 3): "an exposure to a corporate or special purpose entity financing any land
  acquisition for development and construction purposes, or financing development and construction of
  any residential real estate or commercial real estate."
- **commitment** (p. 3-4): includes arrangements that "may be (1) unconditionally cancelled by the
  institution at any time without prior notice to the obligor; or (2) cancelled ... if the obligor
  fails to meet conditions".
- **real estate exposure** (p. 7): "an ADC exposure or an exposure secured by a charge on immovable property."
- **object finance / commodities finance / project finance exposure** (p. 3, 7).

---

## 2. Required Level of Own Funds (CRR) Part (Annex B) -- Article 92

### Art 92(1) -- minimum ratios (p. 12)
| Ratio | Requirement |
|---|---|
| (a) Common Equity Tier 1 capital ratio | 4.5% |
| (b) Tier 1 capital ratio | 6% |
| (c) total capital ratio | 8% |

### Art 92(2A)(a) -- output floor (p. 13)
> TREA = max {U-TREA; x · S-TREA + OF-ADJ}
>
> x = 72.5%;
> OF-ADJ = 12.5 * (IRB T2 – IRB CET1 – GCRA + SA T2);
> IRB T2 = amounts calculated in accordance with point (d) of Own Funds (CRR) Part Article 62;
> IRB CET1 = amounts calculated in accordance with point (d) of paragraph 1 of Article 36 and Article 40 of Own Funds (CRR) Part;
> GCRA = general credit risk adjustments, gross of tax effects, of up to 1.25% of risk-weighted exposure amounts calculated in accordance with paragraph 3A;
> SA T2 = amounts calculated in accordance with point (c) of Own Funds (CRR) Part Article 62.

**Scope (Art 92(2A)(a)-(d), p. 13-14):** the floor formula applies (i) on an individual basis to a
stand-alone institution in the UK and a ring-fenced body that is not a member of a sub-consolidation
group, (ii) on a sub-consolidated basis to a ring-fenced body that is a member of a sub-consolidation
group, (iii) on a consolidated basis to a CRR consolidation entity that is not an international
subsidiary. Otherwise TREA = U-TREA (points (b)-(d)).

**S-TREA (Art 92(3A), p. 15):** calculated without the SFT VaR Method, IRB Approach, SEC-IRBA / IAA,
IMM, and the market-risk internal model approaches; IRB firms may assign unrated corporates the
Art 122(8) weights.

**Art 92(4)(b) (p. 15):** "an institution shall multiply the own funds requirements set out in points (b) to (e) of paragraph 3 by 12.5."

### Art 92(5) -- transitional factor x (p. 15)
> "When calculating TREA for the purposes of paragraph 2A(a), an institution or CRR consolidation entity may apply the following factor x during the periods specified below:"

| Period | x |
|---|---|
| 1 January 2027 to 31 December 2027 | 60% |
| 1 January 2028 to 31 December 2028 | 65% |
| 1 January 2029 to 31 December 2029 | 70% |
| From 1 January 2030 | 72.5% (Art 92(2A)(a)) |

No transitional cap on the floor increase appears in Article 92.

---

## 3. Credit Risk: General Provisions (CRR) Part (Annex C) -- equity transitional

Rules 4.2-4.3 apply only to an institution "that did not have permission to use the Internal Ratings
Based Approach under Article 143 of CRR on 31 December 2026" (rule 4.1, p. 20). IRB firms: rules
4.4-4.10 (higher of legacy IRB RW and the 4.2/4.3 weight; opt-out to Art 133 under 4.9 with notice to the PRA).

| Period | Rule 4.2: equity (not higher risk) | Rule 4.3: higher risk equity |
|---|---|---|
| 1 Jan 2027 - 31 Dec 2027 | 160% | 220% |
| 1 Jan 2028 - 31 Dec 2028 | 190% | 280% |
| 1 Jan 2029 - 31 Dec 2029 | 220% | 340% |
| From 1 Jan 2030 (Art 133(3)/(4)) | 250% | 400% |

(p. 20-21)

---

## 4. Credit Risk: Standardised Approach (CRR) Part (Annex D)

### Art 111(1)(b)-(c) and Table A1 -- conversion factors (p. 29-32)

Art 111(1)(c): "a commitment to issue an off-balance sheet item listed in Table A1 shall be
calculated ... using the lower of: (i) the percentage ... applicable to the off-balance sheet item on
which the commitment is made; and (ii) the percentage ... applicable to the type of commitment".

| Row | Column A: issued off-balance sheet items and commitments | Column B |
|---|---|---|
| (1) | (a) financial guarantees having the character of credit substitutes; (b) credit derivatives; (c) acceptances; (d) endorsements on bills not bearing the name of another institution or investment firm; (e) irrevocable standby letters of credit having the character of credit substitutes; (f) any other issued off-balance sheet items that have the character of credit substitutes | 100% |
| (2) | commitments: (a) transactions with recourse (incl. factoring and invoice discount facilities); (b) assets purchased under outright forward purchase agreements; (c) asset sale and repurchase agreements; (d) forward deposits; (e) the unpaid portion of partly-paid shares and securities; (f) other commitments with similar economic substance, "in particular with regard to having certain drawdowns" | 100%* |
| (3) | Other issued off-balance sheet items that do not have the character of credit substitutes | 50% |
| (4) | (a) note issuance facilities and revolving underwriting facilities; (b) UK residential mortgage commitments that are not subject to a conversion factor of 10% or 100% | 50% |
| (5) | Any other commitment that is not subject to a conversion factor of 10%, 50% or 100% | 40% |
| (6) | (a) documentary credits issued or confirmed and other self-liquidating transactions; (b) warranties, tender bonds, performance bonds, advance payment guarantees, retention guarantees, and guarantees not having the character of credit substitutes; (c) irrevocable standby letters of credit not having the character of credit substitutes; (d) shipping guarantees, customs and tax bonds | 20% |
| (7) | Undrawn commitments which may be cancelled unconditionally at any time without notice, or that effectively provide for automatic cancellation due to a deterioration in an obligor's creditworthiness. "Retail credit lines may be considered as unconditionally cancellable if the terms permit the institution to cancel them to the full extent allowable under the applicable consumer protection and related legislation." | 10% |

\* Rows (1) and (2) share the 100% cell in the PDF layout; row (5)'s wording ("not subject to a
conversion factor of 10%, 50% or 100%") confirms 100% for row (2) commitments.

Engine mapping of `OBSCategory`: UNCONDITIONALLY_CANCELLABLE → row (7) 10%; COMMITMENT_OTHER → row (5)
40% (row (4)(b) 50% with flag `uk_residential_mortgage_commitment`); NIF_RUF → row (4)(a) 50%;
TRANSACTION_RELATED_CONTINGENT → row (6)(b)-(c) 20%; SHORT_TERM_TRADE_LC → row (6)(a) 20%;
DIRECT_CREDIT_SUBSTITUTE → row (1) 100%; SECURITIES_LENDING_COLLATERAL → row (2)(c) / Art 111(1A)
100%; FORWARD_ASSET_PURCHASE → row (2)(b) 100%; OTHER_100 → 100%.

### Art 112(2) Table A2 -- exposure-class hierarchy (p. 32-34)
Highest position wins: (1) securitisation positions; (2) CIUs; (3) subordinated debt, equity and other
own funds instruments; (4) particularly high risk; (5) default; (6) eligible covered bonds; (7) real
estate; (8) international organisations; (9) MDBs; (10) institutions; (11) central governments or
central banks; (12) regional governments or local authorities; (13) PSEs; (14) retail; (15) corporates;
(16) other items.

### Art 113(5) (p. 35)
"Exposures for which no calculation is provided ... shall be assigned a risk weight of 100%."

### Art 114 -- central governments or central banks (p. 35-36)
- Art 114(1): 100% unless paragraphs 2-4 / Art 137(2) apply.
- **Table 1** (Art 114(2)):

| CQS | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| Risk weight | 0% | 20% | 50% | 100% | 100% | 150% |

- Art 114(2A): unrated central bank uses its central government's assessment.
- Art 114(3): "Exposures to the European Central Bank shall be assigned a 0% risk weight."
- Art 114(4): "Exposures to the central government of the UK and the Bank of England denominated and funded in sterling shall be assigned a risk weight of 0%."

### Art 137(2) Table 9 -- ECA MEIP (p. 70)
| MEIP | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| Risk weight | 0% | 0% | 20% | 50% | 100% | 100% | 100% | 150% |

(The extracted header reads "0 1 2 3 4 5 6" over eight risk weights; eight MEIPs 0-7 assumed -- TODO: VERIFY.)

### Art 115 -- regional governments or local authorities (p. 36-37)
- Art 115(1)(a)(i) **Table 1A** (unrated RGLA, by CQS of its central government):

| CQS | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| Risk weight | 20% | 50% | 100% | 100% | 100% | 150% |

- Art 115(1)(a)(ii): 100% where the central government is unrated.
- Art 115(1)(b) **Table 1B** (rated RGLA):

| CQS | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| Risk weight | 20% | 50% | 50% | 100% | 100% | 150% |

- Art 115(2): Scottish Government, Welsh Government, Northern Ireland Executive "shall be treated as exposures to the central government of the UK".
- Art 115(5): other UK RGLAs "denominated and funded in sterling shall be assigned a risk weight of 20%".

### Art 116 -- public sector entities (p. 37-38)
- Art 116(1)(a) **Table 2** (unrated, by CQS of the central government): 20% / 50% / 100% / 100% / 100% / 150%.
- Art 116(1)(b): 100% where the central government is unrated.
- Art 116(2) **Table 2A** (rated): 20% / 50% / 50% / 100% / 100% / 150%.
- Art 116(3): "For exposures to UK public sector entities with an original maturity of three months or less, the risk weight shall be 20%."
- Art 116(3A): the same rules apply to third-country PSEs with their own central government.

### Art 117-118 -- MDBs and international organisations (p. 38-40)
- Art 117(1)(a) **Table 2B** (rated MDB): 20% / 30% / 50% / 100% / 100% / 150%.
- Art 117(1)(b): unrated MDB 50%.
- Art 117(2): 0% for IBRD, IFC, IADB, ADB, AfDB, CEB, NIB, CDB, EBRD, EIB, EIF, MIGA, IFFIm, IsDB, IDA, AIIB.
- Art 118(1): 0% for the EU, IMF, BIS, EFSF, ESM.

### Art 120 -- rated institutions (p. 40-41)
- **Table 3** (original maturity > 3 months): 20% / 30% / 50% / 100% / 100% / 150%.
- **Table 4** (Art 120(2): original maturity ≤ 3 months; Art 120(2A): ≤ 6 months and arising from the movement of goods): 20% / 20% / 20% / 50% / 50% / 150%.
- **Table 4A** (short-term credit assessment): CQS 1 20%; 2 50%; 3 100%; Others 150%.
- Art 120(3): interaction of the short-term assessment with the general short-term preference.
- Art 120(4): due diligence -- "at least one step higher" where higher risk characteristics.

### Art 121 -- unrated institutions (SCRA) (p. 40-43)
- **Table 5** (original maturity > 3 months): Grade A 40%; Grade B 75%; Grade C 150%.
- **Table 5A** (≤ 3 months, or ≤ 6 months from the movement of goods): Grade A 20%; Grade B 50%; Grade C 150%.
- Art 121(5): 30% if > 3 months, Grade A and the institution has "(a) a Common Equity Tier 1 ratio which meets or exceeds 14%; and (b) a leverage ratio which meets or exceeds 5%."
- Art 121(6): RW "may not be less than the risk weight applicable to exposures to the central government of the jurisdiction where the institution is incorporated" where the exposure is not in local currency and is not "a self-liquidating, trade-related contingent item arising from the movement of goods with an original maturity of less than one year".
- Art 121(1A): for CRR firms the Grade A/B tests reference Art 92 requirements, regulation 34(1) CRR Regulations additional own funds, the minimum leverage ratio requirement (Leverage Ratio - Capital Requirements and Buffers Part 3.1), the combined buffer (Capital Buffers Part 1.1) and the leverage buffers (Parts 4.1, 4A.1).

### Art 122 -- corporates (p. 43-45)
- **Table 6** (rated): 20% / 50% / 75% / 100% / 150% / 150%.
- **Table 6A** (short-term): CQS 1 20%; 2 50%; 3 100%; Others 150%.
- Art 122(5): unrated, no permission: 100%.
- Art 122(6) (PRA permission): "(a) Exposures to corporates which the institution has assessed as being investment grade shall be assigned a risk weight of 65%. (b) Exposures to corporates which the institution has assessed as not being investment grade shall be assigned a risk weight of 135%."
- Art 122(8): IRB firms, for the output floor, apply either 100% to all unrated corporates or the paragraph 6 weights (with notice to the PRA).
- Art 122(9)-(10): investment-grade definition, using the firm's internal credit assessment system.
- Art 122(11): "An exposure to an SME that is not a retail exposure and for which a credit assessment by a nominated ECAI is not available, shall be assigned a risk weight of 85%."

### Art 122A-122B -- specialised lending (p. 45-47)
- Art 122B(1): issue-specific rating → Art 122(2) Table 6.
- Art 122B(2): object finance 100%; commodities finance 100%; project finance 130% pre-operational, 100% operational.
- Art 122B(3): operational phase = positive net cash-flow covering remaining completion obligations and declining long-term debt.
- Art 122B(4)-(6): high-quality operational project finance 80%.

### Art 123, 123A -- retail (p. 47-48)
- Art 123(1)(b)(ii) / 123A(1)(b)(ii): total owed by obligor/group (excluding RRE) "does not exceed GBP 880,000".
- Art 123(2): "Retail exposures shall exclude real estate exposures."
- Art 123(3): (a) regulatory retail transactor exposures 45%; (b) regulatory retail non-transactor 75%; (c) other retail 100%.
- Art 123(4): loans to pensioners/permanent employees against pension/salary transfer 35% (instalments ≤ 20% of net monthly pension/salary; original maturity ≤ 10 years; insurance cover).
- Art 123A(1): regulatory retail = (a) a retail exposure to an SME, or (b) a natural-person revolving facility or term loan/lease (incl. student loans) ≤ GBP 880,000, one of a significant number of similar exposures.

### Art 123B -- currency mismatch (p. 49-50)
> "an institution shall apply a 1.5 times multiplier to the applicable risk weight, calculated according to Articles 123 and 124F to 124L, as applicable, subject to a maximum risk weight of 150%, to any unhedged retail exposures or unhedged residential real estate exposures ..."

Hedged if natural or financial hedges "together cover at least 90% of any instalment" (Art 123B(2)(a)(ii)).
Art 123B(3): pre-2027 exposures where mismatches cannot be identified -- 1.5x unless the lending
currency is the domestic currency of residence/employment.

### Art 124 -- real estate (p. 50-51)
- 124(1): regulatory RE → Arts 124F-124I; 124(2): other RE → 124J; 124(3): ADC → 124K.
- 124(4): mixed RE split by the ratio of residential and commercial property values.

### Art 124C -- LTV (p. 52)
"The loan-to-value (LTV) ... is the amount of the loan divided by the value of the property."
Loan amount includes the outstanding amount and any undrawn committed amount, gross of provisions
and CRM (except qualifying pledged deposits), and all loans ranking ahead of or pari passu.

### Art 124D -- valuation (p. 52-53)
Re-valuation within a reasonable time if: (a) likely permanent reduction in value; (b) market-driven
decrease of more than 10%; (c) loan > GBP 2.6 million or 5% of own funds and three years since the last
qualifying valuation; (d) five years since the last qualifying valuation. Valuations must exclude price
increase expectations, not exceed market value, and not exceed the purchase price for purchase loans.
Self-build: the higher of underlying land value and the most recent valuation x 0.8.

### Art 124E -- material dependence on cash flows (p. 54-55)
RRE is materially dependent **unless** to natural persons secured on the primary residence; natural
persons meeting the three-property limit; property SPVs guaranteed by natural persons meeting the
limit; UK-regulated social housing; housing associations/co-operatives of natural persons. CRE is
materially dependent **except** where each property is predominantly used by the borrower for its own
business purpose (not rental income).

### Art 124F -- regulatory RRE not materially dependent (loan splitting) (p. 55)
> "(a) the part of the exposure up to 55% of the value of the property shall be assigned a risk weight of 20%; and (b) the risk weight of the counterparty shall be applied to the residual part of the exposure, if any, in accordance with Article 124L."

Art 124F(2): with third-party charges ranking ahead, 55% of value is reduced by those charges;
with pari passu third-party charges, further reduced pro rata.

### Art 124G -- regulatory RRE materially dependent (whole loan) -- Table 6B (p. 56)
| LTV | ≤ 50% | 50% < LTV ≤ 60% | 60% < LTV ≤ 70% | 70% < LTV ≤ 80% | 80% < LTV ≤ 90% | 90% < LTV ≤ 100% | > 100% |
|---|---|---|---|---|---|---|---|
| Risk weight | 30% | 35% | 40% | 50% | 60% | 75% | 105% |

Art 124G(2): "multiply the risk weight ... by 1.25 if the LTV is more than 50%" where charges not held
by the institution rank ahead.

### Art 124H -- regulatory CRE not materially dependent (p. 56-57)
- 124H(1) natural person or SME: "(a) the part of the exposure up to 55% of the value of the property shall be assigned a risk weight of 60%; and (b) the risk weight of the counterparty shall be assigned to the residual part".
- 124H(3) other obligors: "the higher of: (a) 60%; and (b) the lower of: (i) the risk weight of the counterparty ...; and (ii) the risk weight that would be assigned to the exposure under Article 124I if the exposure was materially dependent on the cash-flows generated by the property."

### Art 124I -- regulatory CRE materially dependent (p. 57)
| | LTV ≤ 60% | 60% < LTV ≤ 80% | LTV > 80% |
|---|---|---|---|
| 124I(1)-(2) (no senior third-party charge) | 100% | 100% | 110% |
| 124I(3) (charges not held rank ahead) | 100% | 125% | 137.5% |

### Art 124J -- other real estate (p. 57)
(1) materially dependent: 150%; (2) RRE not dependent: counterparty RW (Art 124L); (3) CRE not
dependent: "the higher of: (a) 60%; and (b) the risk weight of the counterparty".

### Art 124K -- ADC (p. 58)
150%; 100% for residential ADC with prudent underwriting and either significant pre-sale/pre-lease
contracts with substantial forfeitable deposits or substantial borrower equity at risk.

### Art 124L -- counterparty risk weights for real estate (p. 58)
| Counterparty | RW |
|---|---|
| (a) natural person(s), not an SME | 75% |
| (b) SME meeting the retail qualifying conditions if Art 123(2) disapplied | 75% |
| (c) other SME | 85% |
| (d) social housing / housing association or co-operative | higher of 75% and the unsecured RW |
| (e) other counterparties | unsecured RW |

Arts 125-126: "[Note: Provision left blank]" (CRR mortgage articles removed).

### Art 127 -- default (p. 59)
Unsecured part: (a) 150% where specific credit risk adjustments are "less than 20% of the outstanding
amount"; (b) 100% where "equal to or greater than 20%". Art 127(3): defaulted RRE not materially
dependent on cash flows: 100%.

### Art 128 -- particularly high risk (p. 59): 150%.

### Art 129 -- eligible covered bonds (p. 59-62)
- **Table 7** (rated): 10% / 20% / 20% / 50% / 50% / 100%.
- Art 129(5) (unrated, by issuer senior unsecured RW):

| Issuer RW | 20% | 30% | 40% | 50% | 75% | 100% | 150% |
|---|---|---|---|---|---|---|---|
| Covered bond RW | 10% | 15% | 20% | 25% | 35% | 50% | 100% |

### Art 132-132C -- CIUs (p. 62-67)
Fall-back 1,250%; look-through / mandate-based; third-party calculation x 1.2; off-balance sheet
RW*_i = (RWEA_i / E*_i) · (A_i / EQ_i). (Not an `AssetClass` in the base contract; parameters kept.)

### Art 133 -- subordinated debt, equity, other own funds instruments (p. 67-68)
- 133(3): equity 250%; 133(4): higher risk equity 400%; 133(5): subordinated debt / own funds
  instruments not equity exposures 150%; 133(6): deducted items, Art 89(3) 1,250% and Art 48(4) 250%
  are outside 3-5.

### Art 134 -- other items (p. 68-69)
Tangible assets 100%; unallocable prepayments/accrued income 100%; cash items in the process of
collection 20%; cash in hand and equivalent 0%; gold bullion (own vaults/allocated, backed by bullion
liabilities) 0%; nth-to-default baskets aggregated to max 1,250%; residual value of leases 1/t · 100% · RV.

---

## 5. Credit Risk Mitigation (CRR) Part (Annex F)

### Art 223 -- Financial Collateral Comprehensive Method (p. 200-202)
> C_VA = C · (1 − H_C − H_fx)  (para 2)
> E_VA = E · (1 + H_E)          (para 3; E with off-balance sheet items at 100%, para 4)
> E* = max {0, E_VA − C_VAM}    (para 5)
> H = Σ a_i H_i                 (para 7, mixed collateral)

Art 228(1): E* is the exposure value; for off-balance sheet items the Art 111 percentages are applied to E*.

### Art 224 -- supervisory volatility adjustments, daily revaluation (p. 203-205)

**Table 1 -- rated debt securities** (percent; 20-day / 10-day / 5-day liquidation periods)

| CQS | Residual maturity | Art 197(1)(b) issuers | Art 197(1)(c)-(d) issuers | Securitisation (197(1)(h)) |
|---|---|---|---|---|
| 1 | ≤ 1 year | 0.707 / 0.5 / 0.354 | 1.414 / 1 / 0.707 | 2.828 / 2 / 1.414 |
| 1 | > 1 ≤ 3 years | 2.828 / 2 / 1.414 | 4.243 / 3 / 2.121 | 11.314 / 8 / 5.657 |
| 1 | > 3 ≤ 5 years | 2.828 / 2 / 1.414 | 5.657 / 4 / 2.828 | 11.314 / 8 / 5.657 |
| 1 | > 5 ≤ 10 years | 5.657 / 4 / 2.828 | 8.485 / 6 / 4.243 | 22.627 / 16 / 11.314 |
| 1 | > 10 years | 5.657 / 4 / 2.828 | 16.971 / 12 / 8.485 | 22.627 / 16 / 11.314 |
| 2-3 | ≤ 1 year | 1.414 / 1 / 0.707 | 2.828 / 2 / 1.414 | 5.657 / 4 / 2.828 |
| 2-3 | > 1 ≤ 3 years | 4.243 / 3 / 2.121 | 5.657 / 4 / 2.828 | 16.971 / 12 / 8.485 |
| 2-3 | > 3 ≤ 5 years | 4.243 / 3 / 2.121 | 8.485 / 6 / 4.243 | 16.971 / 12 / 8.485 |
| 2-3 | > 5 ≤ 10 years | 8.485 / 6 / 4.243 | 16.971 / 12 / 8.485 | 33.941 / 24 / 16.971 |
| 2-3 | > 10 years | 8.485 / 6 / 4.243 | 28.284 / 20 / 14.142 | 33.941 / 24 / 16.971 |
| 4 | all | 21.213 / 15 / 10.607 | N/A | N/A |

**Table 2 -- short-term credit assessments**

| CQS | Art 197(1)(b) | Art 197(1)(c)-(d) | Securitisation |
|---|---|---|---|
| 1 | 0.707 / 0.5 / 0.354 | 1.414 / 1 / 0.707 | 2.828 / 2 / 1.414 |
| 2-3 | 1.414 / 1 / 0.707 | 2.828 / 2 / 1.414 | 5.657 / 4 / 2.828 |

**Table 3 -- other collateral or exposure types**

| Type | 20-day | 10-day | 5-day |
|---|---|---|---|
| Main Index Equities, Main Index Convertible Bonds | 28.284 | 20 | 14.142 |
| Other Equities or Convertible Bonds listed on a recognised exchange | 42.426 | 30 | 21.213 |
| Cash and cash assimilated instruments issued by the institution | 0 | 0 | 0 |
| Gold | 28.284 | 20 | 14.142 |

**Table 4 -- currency mismatch:** 11.314 / 8 / 5.657.

Art 224(2): liquidation periods -- secured lending 20 business days; repo and securities lending or
borrowing 5 business days; other capital-market-driven transactions 10 business days.
Art 224(4): non-eligible securities lent/sold under SFTs: haircut of non-main-index listed equities.
Art 224(6): unrated eligible institution debt: as CQS 2-3 institutions/corporates.

### Art 226 -- scaling (p. 205-206)
> (1) H = H_m · √[(N_R + (T_m − 1)) / T_m]
> (2) H_m = H_n · √(T_m / T_n)

### Art 227 -- 0% haircut conditions for SFTs with core market participants (p. 206-207).

### Art 233 -- valuation of unfunded protection (p. 212-213)
- Credit derivatives without restructuring: protection "reduce[d] ... by 40%" where not higher than the
  exposure value; otherwise "no higher than 60% of the exposure value".
- G* = G · (1 − H_fx), H_fx on a 10 business day liquidation period, daily revaluation.

### Art 235 -- Risk-Weight Substitution Method (p. 213-214)
> E_g = min{G_A, E} (E with off-balance sheet items at 100%);
> r_g = "the risk weight of a comparable direct exposure to the protection provider";
> E_n = E − E_g; r_n = "the risk weight of the exposure calculated as if there were no unfunded credit protection";
> RW = (E_n · r_n + E_g · r_g) / E.

Art 235(3): the Art 114(4) 0% for UK central government guarantees only where the guarantee is in the
domestic currency and the exposure is funded in that currency.

### Arts 237-239 -- maturity mismatch (p. 217-219)
- Art 237(1): protection with residual maturity < three months not eligible where mismatched;
  237(2)(a): not eligible if original maturity of the protection < one year.
- Art 238(1): exposure effective maturity capped at five years.
- Art 239(2): C_VAM = C_VA · (t − t*) / (T − t*); Art 239(3): G_A = G* · (t − t*) / (T − t*);
  t = min(protection maturity, T), T = min(exposure maturity, 5), t* = 0.25.

---

## 6. Credit Valuation Adjustment Risk Part (Annex K)

### Rule 3.1-3.6 -- scope and approaches (p. 397-399)
SA-CVA with permission; otherwise BA-CVA (Chapter 4) or the alternative approach (Chapter 6).
Intragroup exclusion under rule 3.2 (with notification under 3.3). Rule 3.6: IRB firms map internal
ratings to IG/HY for unrated counterparties.

### Rule 4.2 -- reduced BA-CVA (p. 399)
> own funds = DS_BA−CVA × K_reduced; DS_BA−CVA = 0.65
> K_reduced = √[(ρ · Σ_c SCVA_c)² + (1 − ρ²) · Σ_c SCVA_c²]; ρ = 50%

### Rule 4.3 (p. 400)
> SCVA_c = (1/α) · RW_c · Σ_NS M_NS · EAD_NS · DF_NS
> DF_NS = 1 for IMM firms; otherwise (1 − e^(−0.05·M_NS)) / (0.05 · M_NS)
> α = the value of α as specified in the Counterparty Credit Risk (CRR) Part

M_NS per IRB Art 162 but "not capped at five years but instead at the longest contractual remaining
maturity in the netting set".

### Rule 4.4 -- RW_c (p. 401)
| Sector of counterparty | Investment grade | High yield and non-rated |
|---|---|---|
| Sovereigns including central banks and multilateral development banks | 0.5% | 2.0% |
| Local government, government-backed non-financials, education and public administration | 1.0% | 4.0% |
| Financials including government-backed financials, excluding pension funds | 5.0% | 12.0% |
| Pension funds | 3.5% | 8.5% |
| Basic materials, energy, industrials, agriculture, manufacturing, mining and quarrying | 3.0% | 7.0% |
| Consumer goods and services, transportation and storage, administrative and support service activities | 3.0% | 8.5% |
| Technology, telecommunications | 2.0% | 5.5% |
| Health care, utilities, professional and technical activities | 1.5% | 5.0% |
| Other sector | 5.0% | 12.0% |

### Rules 4.5-4.10 -- full BA-CVA (p. 401-403)
> K_full = β · K_reduced + (1 − β) · K_hedged; β = 0.25
> K_hedged = √[(ρ · Σ_c(SCVA_c − SNH_c) − IH)² + (1 − ρ²) · Σ_c(SCVA_c − SNH_c)² + Σ_c HMA_c]
> SNH_c = Σ_{h∈c} r_hc · RW_h · M_h^SN · B_h^SN · DF_h^SN
> IH = Σ_i RW_i^ind · M_i^ind · B_i^ind · DF_i^ind (RW^ind = rule 4.4 RW × 0.7, name-weighted for mixed indices)
> HMA_c = Σ_{h∈c} (1 − r_hc²) · (RW_h · M_h^SN · B_h^SN · DF_h^SN)²  (exponent placement: TODO: VERIFY)

**Rule 4.10 -- r_hc:** references counterparty c directly 100%; legally related 80%; shares sector and region 50%.

### Rules 6.1-6.4 -- alternative approach (p. 422-423)
> "(1) has non-centrally cleared derivatives of a notional aggregate amount less than GBP 88 billion; and (2) does not have permission from the PRA to use SA-CVA" → "an own funds requirement for CVA risk equal to 100% of the firm's own funds requirement for counterparty credit risk", without CVA hedges, for the entire portfolio, with prior notification.

### Rules 7.1-7.5 -- transitional (p. 423-425)
Until 1 January 2030 a firm may either (1) exclude pre-2027 transactions with (a) EMIR non-financial
counterparties below the clearing threshold, (b) pension scheme arrangements (EMIR Art 2(10), 89(1)),
(c) EMIR Art 1(4)-(5) entities and counterparties previously at 0% under CRR Arts 114(4)/115(2); or
(2) apply a final discount scalar ω̂_T (reconstructed; TODO: VERIFY):

> ω̂_T = max(ω̄_t, [K_1^b3.1 · ω̄_t + (K_T^b3.1 − K_1^b3.1)] / K_T^b3.1 · 100%)
> ω̄_t = max(ω_t, 100% − (K_1^b3.1 − K_1^CRR)/K_1^b3.1 · (5 − t)/5 · (1 − ω_t)/(1 − ω)), ω = 0.5

t = 2 on 1 January 2027, 3 on 1 January 2028, 4 on 1 January 2029.

| Period | Transitional weighting cap ω_t |
|---|---|
| 1 Jan 2027 - 31 Dec 2027 | 70% |
| 1 Jan 2028 - 31 Dec 2028 | 80% |
| 1 Jan 2029 - 31 Dec 2029 | 90% |

---

## 7. Operational Risk Part (Annex L)

### Rule 4.1 (p. 428)
"A firm must calculate its own funds requirement for operational risk in accordance with the
standardised approach by multiplying the Business Indicator Component and the Internal Loss Multiplier."

### Rules 5.2-5.4 -- Business Indicator (p. 428-429)
BI = interest, leases and dividend component + services component + financial component:

> ILDC = Min[Abs(Interest Income − Interest Expense)‾ ; 2.25% × Interest Earning Assets‾] + Dividend Income‾
> SC = Max[Other Operating Income‾ ; Other Operating Expense‾] + Max[Fee Income‾ ; Fee Expense‾]
> FC = Abs(Net Profit and Loss Trading Book)‾ + Abs(Net Profit and Loss Banking Book)‾

Rule 5.4: a bar denotes a three-year average; "the absolute value of net items must firstly be
calculated year by year and after that calculation the average over the last three years must be
calculated"; audited figures where available. Annex 1 Tables A-D define the items (Table D excludes
insurance income/expenses, administrative and staff expenses, provisions other than for operational
loss events, impairments, goodwill changes and corporate income tax).

### Rule 5.8 -- BIC (p. 430)
| Bucket | BI range (GBP bn) | Marginal coefficient |
|---|---|---|
| 1 | ≤ 0.88 | 12% |
| 2 | 0.88 < BI ≤ 26 | 15% |
| 3 | > 26 | 18% |

### Rule 5.9 (p. 430)
"The Internal Loss Multiplier is equal to one."

### Rule 7.1 -- loss data (p. 430-431)
10-year observation period (exceptionally ≥ 5 years); minimum loss-event threshold GBP 20,000;
mapping to Level 1 event types (Annex 2).

RWA = 12.5 × own funds requirement (Required Level of Own Funds (CRR) Part Art 92(3)(e), 92(4)(b)).

---

## 8. Counterparty Credit Risk (CRR) Part amendments (Annex R)

### Art 274(2) (p. 456)
> "Exposure value = α · (RC + PFE) ... α = 1.4, unless the counterparty is a non-financial counterparty or a pension scheme arrangement or an entity established to provide compensation to members of a pension scheme arrangement in case of default, in which case, α = 1."

Definitions (rule 1.2, p. 455): *non-financial counterparty* = EMIR Art 2(9) NFC or an undertaking
that would be one if established in the UK; *pension scheme arrangement* = EMIR Art 2(10) or equivalent.

### Art 274(2A)-(2B) -- alpha add-on transitional (p. 456)
For pre-2027 transactions with counterparties in CVA Part 7.1(1)(a) or (b), add a percentage of the
alpha add-on (EV at α = 1.4 less EV at α = 1, both as at 1 January 2027): 60% (2027), 40% (2028),
20% (2029); not required once the firm ceases to apply CVA Part 7.1(1)/(2); not applied in the
leverage ratio.

### SA-CCR provisions not amended by the instrument (PRA Rulebook CCR (CRR) Part web text, 1 January 2027)
- Art 275(1): "RC = max{ CMV – NICA , 0}"; 275(2): "RC = max{ CMV – VM – NICA , TH + MTA – NICA , 0}";
  275(3) multiple netting sets under one margin agreement (image; form from CRR Art 275(3)):
  max{Σ max{CMV_i, 0} − max{VM_MA + NICA_MA, 0}, 0} + max{Σ min{CMV_i, 0} − min{VM_MA + NICA_MA, 0}, 0}.
- Art 278(1): "PFE = multiplier · AggAddOn"; 278(3): "Floor m = 5%; y = 2 . (1 – Floor m ) . AggAddOn".
  The multiplier and z are images on the Rulebook page; form from CRR Art 278(3):
  multiplier = 1 if z ≥ 0, else min{1; Floor_m + (1 − Floor_m) · exp(z / y)};
  z = CMV − NICA (275(1) sets), CMV − VM − NICA (275(2)), Σ(CMV_i − NICA_i) (275(3)).
- Art 279a(1)(a) Table 1 supervisory volatility: interest rate 50%; FX 15%; credit single-name 100%,
  multiple names 80%; equity single-name 120%, multiple names 75%; commodity electricity 150%, other
  70%; others 150%.
- Art 279b(1)(a): "R = the supervisory discount rate; R = 5%" (duration formula is an image).
- Art 279c(1): MF = √(min{max{M, 10/OneBusinessYear}, 1}) (unmargined); MF = 3/2 · √(MPOR /
  OneBusinessYear) (margined); images, form from CRR Art 279c. Client/clearing member MPOR minimum
  replaced by five business days.
- Art 280: ε = 1 (Art 277a(1) hedging sets), 5 (277a(2)(a) volatility/correlation), 0.5 (277a(2)(b)
  basis).
- Art 280a(2): "SF IR ... 0.5%"; Table 2 maturity buckets (0,1], (1,5], > 5 years.
- Art 280b(2): "SF FX ... 4%".
- Art 280c: correlation 50% single-name / 80% multi-name entities; Table 3 single-name SF by CQS:
  1 0.38%, 2 0.42%, 3 0.54%, 4 1.06%, 5 1.6%, 6 6.0%; SA firm, unrated issuer 0.54% (1.6% where
  Art 128 applies); Table 4 quoted indices: investment grade 0.38%, non-investment grade 1.06%.
- Art 280d: correlation 50% / 80%; SF 32% single-name, 20% multi-name.
- Art 280e: correlation 40%; SF 18% (excluding electricity), 40% electricity.
- Art 280f(2): "SF Other ... 8%".

---

## 9. Capital Buffers Part (PRA Rulebook web text, 1 January 2027; Annex AA amends rule 3.1)
- Rule 1.2 'combined buffer': "the sum of (a) the capital conservation buffer; (b) the
  countercyclical capital buffer; (c) the G-SII buffer (if any); and (d) the O-SII buffer (if any)"
  -- G-SII and O-SII buffers stack; no systemic risk buffer component.
- Rule 2.1: "a capital conservation buffer of common equity tier 1 capital equal to 2.5% of its total
  risk exposure amount".
- Rule 3.1(1)-(3) (as amended by Annex AA, p. 491-492): CCyB = TREA × institution-specific rate, the
  weighted average of FPC / third-country rates, weights = own funds requirements for credit risk,
  default risk, specific risk and IDMR on relevant credit exposures. No rate or maximum is set.
- Rule 4.3(6): MDA factor 0 / 0.2 / 0.4 / 0.6 for the first (lowest) to fourth quartile of the
  combined buffer; 4.3(7): quartile bounds = combined buffer / 4 × (Q_n − 1) and × Q_n.
- The PRA buffer (Pillar 2B) is not part of the combined buffer.

---

## Not in the supplied texts (TODO: VERIFY)

| Item | Where it would be | Placeholder used |
|---|---|---|
| CCyB rate / maximum | FPC decisions (Capital Buffers Part rule 3.1(4)-(8)) | caller-supplied; 2.5% sanity cap |
| G-SII / O-SII rates | firm-specific (outside the Capital Buffers Part) | caller-supplied; 3.5% sanity cap each |
| Leverage ratio minimum | Leverage Ratio - Capital Requirements and Buffers Part 3.1 | 3% (BCBS LEV20) |
| Additional leverage ratio buffer | same Part 4A.1 | 50% of systemic rate (BCBS LEV40.2) |
| Countercyclical leverage ratio buffer | same Part 4.1 | not applied |
| SA-CCR OneBusinessYear convention | CCR Part Art 279c (business-day convention) | 250 business days |
| SME / infrastructure lending adjustments | Pillar 2A (PS7/25) | none in Pillar 1 (support factor = 1) |
| ECA Table 9 header (MEIP 0-7) | Art 137(2), p. 70 | eight categories 0-7 |
| BA-CVA HMA exponent placement | CVA Part rule 4.9, p. 403 | (1 − r_hc²) |
| CVA transitional discount scalar layout | CVA Part rules 7.1(2), 7.2, p. 423-424 | reconstruction above |

Closed in the October 2026 update (sources: Capital Buffers Part, CCR (CRR) Part web text): the
capital conservation buffer rate (2.5%, rule 2.1); G-SII / O-SII stacking (rule 1.2, summed);
systemic risk buffer (no component in rule 1.2); SA-CCR multiplier floor (5%, Art 278(3)) and
multiplier form; replacement cost (Art 275); supervisory factors, volatilities, correlations and
ε (Arts 279a, 280-280f).
