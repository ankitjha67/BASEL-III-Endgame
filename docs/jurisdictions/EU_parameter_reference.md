# EU CRR3 -- parameter reference transcribed from the legal text

Sources (the text governs wherever this file and the text differ):

- **CRR3**: Regulation (EU) 2024/1623 of 31 May 2024 amending Regulation (EU) No 575/2013,
  OJ L, 19.6.2024 (189 pp.). Applies from 1 January 2025 (Article 2). "p." below is the OJ page
  of this act. Several formulas (Articles 313, 314(2), 384, 465(2)) are printed as images in the
  OJ and are transcribed here from the rendered PDF pages.
- **CRR (consolidated)**: Regulation (EU) No 575/2013, consolidated text 02013R0575 as of
  09.07.2024 ("cons. p." = page footer of the consolidation). Used **only** for articles CRR3 did
  not replace. The consolidation predates the 1.1.2025 application date and still shows the
  pre-CRR3 text of several replaced articles (e.g. Article 122 Table 6, Article 133(2)); those
  old texts are cited only where CRR3 itself refers to "the risk weight applicable on 8 July
  2024" (Article 495a).
- EBA Policy Advice on the Basel III reforms: Credit Risk (EBA-Op-2019-09, Aug 2019): context
  only, never a source of EU values.

Implementation: `src/jurisdictions/eu/` (constants in `params.py`). Decimals in code; percentages
below are as printed (the OJ uses a decimal comma).

---

## 1. Own funds requirements and output floor

### Article 92(1)-(1a) (cons. p.123, not amended by CRR3)
> 1. ... institutions shall at all times satisfy the following own funds requirements:
> (a) a Common Equity Tier 1 capital ratio of 4,5 %; (b) a Tier 1 capital ratio of 6 %;
> (c) a total capital ratio of 8 %; (d) a leverage ratio of 3 %.
>
> 1a. In addition to the requirement laid down in point (d) of paragraph 1 ..., a G-SII shall
> maintain a leverage ratio buffer equal to the G-SII's total exposure measure ... multiplied by
> 50 % of the G-SII buffer rate applicable to the G-SII in accordance with Article 131 of
> Directive 2013/36/EU. ... A G-SII shall meet the leverage ratio buffer requirement with Tier 1
> capital only.

### Article 92(3)-(6) (CRR3 point (28), pp.30-31)
> 3. Institutions shall calculate the total risk exposure amount as follows:
> **TREA = max{U-TREA; x · S-TREA}** ... x = 72,5 %.
> By way of derogation ..., a Member State may decide that the total risk exposure amount shall
> be the un-floored total risk exposure amount ... for institutions which are part of a group with
> a parent institution in the same Member State, provided that that parent institution ...
> calculates its total risk exposure amount in accordance with the first subparagraph ... on a
> consolidated basis.
>
> 5. The standardised total risk exposure amount shall be calculated ... without using any of the
> following approaches: (i) the internal model approach for master netting agreements (Art. 221);
> (ii) the IRB Approach; (iii) SEC-IRBA and the Internal Assessment Approach; (iv) the Internal
> Model Method ...; (b) ... market risk ... without using the alternative internal model approach.
>
> 6. ... (b) institutions shall multiply the own funds requirements set out in paragraph 4,
> points (b) to (f), by 12,5.

### Article 465 -- Transitional arrangements for the output floor (CRR3 point (237), pp.172-174)
> 1. ... institutions may apply the following factor x where calculating TREA:

| Period | x |
|---|---|
| 1.1.2025-31.12.2025 | 50 % |
| 1.1.2026-31.12.2026 | 55 % |
| 1.1.2027-31.12.2027 | 60 % |
| 1.1.2028-31.12.2028 | 65 % |
| 1.1.2029-31.12.2029 | 70 % |
| from 1.1.2030 | 72,5 % (Art. 92(3)) |

> 2. ... institutions may, until 31 December 2029, apply the following formula where calculating
> TREA: **TREA = min{max{U-TREA; x · S-TREA}; 125 % · U-TREA}** (image, p.172). For the purposes
> of that calculation, institutions shall take into account the applicable factor x referred to in
> paragraph 1.
>
> 3. ... institutions may, until 31 December 2032, assign a risk weight of **65 %** to exposures to
> corporates for which no credit assessment by a nominated ECAI is available and provided that
> those institutions' estimates of the PD of those obligors, calculated in accordance with Part
> Three, Title II, Chapter 3, are no greater than **0,5 %**.
>
> 4. ... institutions shall, until 31 December 2029, replace alpha by **1** in the calculation of the
> exposure value for the contracts listed in Annex II in accordance with ... Section 3 where the same
> exposure values are calculated in accordance with ... Section 6 [IMM] for the purposes of the total
> un-floored risk exposure amount.
>
> 5. ... provided that all conditions set out in paragraph 8 ... are met, Member States may allow
> institutions to assign: (a) until 31 December 2032, a risk weight of **10 %** to the part of the
> exposures secured by mortgages on residential property up to **55 %** of the property value ...;
> and (b) until 31 December 2029, a risk weight of **45 %** to any remaining part of the exposures
> secured by mortgages on residential property up to **80 %** of the property value ..., provided that
> the adjustment to own funds requirements for credit risk referred to in Article 501 is not applied.
>
> 8. ... (a) the exposures qualify for the treatment pursuant to Article 125(1); (b) ... risk weighted
> in accordance with Part Three, Title II, Chapter 3; (c) the residential property ... is located in
> the Member State that has exercised the discretion; (d) over the last eight years the institution's
> losses ... do not exceed on average **0,25 %** ...; (e) enforceable rights on the property and on
> other assets and income of the obligor; (f) the competent authority has verified (a) to (e).
>
> 9. ... institutions may assign the following risk weights to any remaining part of the exposures ...
> referred to in paragraph 5, point (b), until 31 December 2032:

| Period | RW on the 55 %-80 % part |
|---|---|
| until 31.12.2029 | 45 % (465(5)(b)) |
| 2030 | 52,5 % (465(9)(a)) |
| 2031 | 60 % (465(9)(b)) |
| 2032 | 67,5 % (465(9)(c)) |

> 12. Any extension of any of the transitional arrangements referred to in paragraphs 3, 5 and 9 ...
> and in Articles 495b(1), 495c(1) and 495d(1), shall be limited to four years ...
>
> 13. ... until 31 December 2032, apply the following factor p: (a) p = **0,25** for a position in a
> securitisation to which Article 262 applies; (b) p = **0,5** for a position ... to which Article 261
> applies.

Not in the source texts: the CRD VI (Directive (EU) 2024/1619) transitional on the interaction of the
floor with Pillar 2 / the combined buffer ("OF-ADJ" and CET1-based caps). **TODO: VERIFY.**

## 2. Credit risk -- standardised approach

### Article 114 central governments / central banks (cons. p.148)
> 1. ... shall be assigned a 100 % risk weight, unless the treatments set out in paragraphs 2 to 7 apply.
> 2. Table 1:

| CQS | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| RW | 0 % | 20 % | 50 % | 100 % | 100 % | 150 % |

> 3. Exposures to the ECB shall be assigned a 0 % risk weight.
> 4. Exposures to Member States' central governments, and central banks denominated and funded in the
> domestic currency of that central government and central bank shall be assigned a risk weight of 0 %.

### Article 115 RGLA (CRR3 point (45), p.42)
> -1. ... for which a credit assessment by a nominated ECAI is available ... Table 1:

| CQS | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| RW | 20 % | 50 % | 50 % | 100 % | 100 % | 150 % |

> 1. ... not available ... in accordance with the credit quality step to which exposures to the central
> government ... are assigned in accordance with Table 2:

| Sovereign CQS | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| RW | 20 % | 50 % | 100 % | 100 % | 100 % | 150 % |

> ... a risk weight of 100 % shall be assigned where the central government ... is unrated.
> 2. ... treated as exposures to the central government ... where there is no difference in risk ...
> 5. ... regional governments or local authorities of the Member States ... denominated and funded in
> the domestic currency ... shall be assigned a risk weight of 20 %.

### Article 116 PSEs (cons. p.151; para 2 replaced by CRR3 point (46))
> 1. ... no credit assessment ... Table 2: CQS of sovereign 1-6 -> 20 % / 50 % / 100 % / 100 % / 100 % / 150 %.
> For exposures to public sector entities incorporated in countries where the central government is
> unrated, the risk weight shall be 100 %.
> 2. (CRR3) Exposures to public sector entities for which a credit assessment by a nominated ECAI is
> available shall be treated in accordance with Article 115(-1).
> 3. For exposures to public sector entities with an original maturity of three months or less, the
> risk weight shall be 20 %.
> 4. In exceptional circumstances, exposures to public-sector entities may be treated as exposures to
> the central government, regional government or local authority ...

### Article 117 MDBs (CRR3 point (47), p.43; para 2 cons. p.152)
> 1. ... not referred to in paragraph 2 and for which a credit assessment ... is available ... Table 1.
> ... for which a credit assessment ... is not available shall be assigned a risk weight of **50 %**.

| CQS | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| RW | 20 % | 30 % | 50 % | 100 % | 100 % | 150 % |

> 2. Exposures to the following multilateral development banks shall be assigned a 0 % risk weight:
> IBRD, IFC, IADB, ADB, AfDB, CEB, NIB, CDB, EBRD, EIB, EIF, MIGA, IFFIm, IsDB, IDA, AIIB.

### Article 118 international organisations (cons. p.152)
> 0 % risk weight: EU and Euratom; IMF; BIS; EFSF; ESM; an international financial institution
> established by two or more Member States ...

### Article 120 rated institutions (CRR3 point (49), p.43; para 3 cons. p.154)
> 1. Table 1:

| CQS | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| RW | 20 % | 30 % | 50 % | 100 % | 100 % | 150 % |

> 2. Exposures to institutions with an original maturity of three months or less ... and exposures
> which arise from the movement of goods across national borders with an original maturity of six
> months or less ... Table 2:

| CQS | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| RW | 20 % | 20 % | 20 % | 50 % | 50 % | 150 % |

> 3. (cons.) (a) If there is no short-term exposure assessment, the general preferential treatment ...
> shall apply ...; (b)/(c) if there is a short-term assessment ... the short-term assessment shall be
> used [whether more or less favourable].

### Article 121 unrated institutions (CRR3 point (50), pp.44-45)
Grade A (adequate capacity; meets Art. 92(1) + Art. 104 CRD + combined buffer, publicly disclosed);
Grade B (substantial credit risk; meets minima excl. buffers); Grade C otherwise (121(1)(c)).
> 3. (a) Grade A, B or C ... original maturity of three months or less, or six months or less arising
> from the movement of goods across national borders -> short-term row of Table 1;
> (b) Grade A ... not short term ... **30 %** where ... CET1 capital ratio ... ≥ **14 %** ... leverage
> ratio ... ≥ **5 %**; (c) otherwise Table 1.
> Where an exposure to an institution is not denominated in the domestic currency of the
> jurisdiction of incorporation ... the risk weight ... to exposures other than those with a maturity
> of one year or less stemming from self-liquidating, trade-related contingent items ... shall not be
> lower than the risk weight of an exposure to the central government of the country where the
> institution is incorporated.

| Table 1 | Grade A | Grade B | Grade C |
|---|---|---|---|
| Risk weight for short-term exposures | 20 % | 50 % | 150 % |
| Risk weight | 40 % | 75 % | 150 % |

### Article 131 short-term credit assessments (cons., Table 7)

| CQS | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| RW | 20 % | 50 % | 100 % | 150 % | 150 % | 150 % |

Short-term rating -> CQS mapping (Implementing Regulation (EU) 2016/1799) is not in the sources:
A-1 -> 1, A-2 -> 2, A-3 -> 3, others -> 4 assumed. **TODO: VERIFY.**

### Article 122 corporates (CRR3 point (51), pp.45-46)
> 1. ... Table 1:

| CQS | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| RW | 20 % | 50 % | 75 % | 100 % | 150 % | 150 % |

> 2. Exposures for which such a credit assessment is not available shall be assigned a risk weight of
> **100 %**.

(The pre-CRR3 "or the risk weight of ... the central government ..., whichever is the higher" is
deleted.) SME = turnover not exceeding **EUR 50 000 000** (Article 5, point (9), CRR3 point (2), p.22).
No 85 % SME risk weight exists in the CRR.

### Article 122a specialised lending (CRR3 point (52), pp.46-48)
> 2. ... directly applicable credit assessment ... Table 1: CQS 1-6 -> 20 % / 50 % / 75 % / 100 % /
> 150 % / 150 %.
> 3. (a) object finance ... 100 %; (b) commodity finance ... 100 %; (c) project finance:
> (i) **130 %** ... pre-operational phase; (ii) provided that the adjustment ... referred to in Article
> 501a is not applied, **80 %** ... operational phase and the exposure meets all of the following
> criteria [(1)-(8)]; (iii) **100 %** ... operational phase and ... not ... point (ii).
> (e) ... operational phase ... (i) positive net cash flow sufficient to cover any remaining
> contractual obligation; (ii) declining long term debt.

### Article 495b(3) (CRR3 point (242), p.177)
> ... specialised lending exposures [object finance, 122a(3)(a)] for which a directly applicable credit
> assessment ... is not available may, until 31 December 2032, be assigned a risk weight of **80 %**,
> where the adjustment ... referred to in Article 501a is not applied and the exposure is deemed to be
> of high quality ... [criteria (a)-(c)].

### Article 123 retail (CRR3 point (53), pp.48-49)
> 1. (b) the total amount owed ... excluding exposures secured by residential property, up to the
> property value shall not ... exceed **EUR 1 million**;
> 3. Retail exposures ... shall be assigned a risk weight of **75 %**, with the exception of transactor
> exposures, which shall be assigned a risk weight of **45 %**.
> 4. Where any of the criteria referred to in paragraph 1 are not met for an exposure to one or more
> natural persons, the exposure shall be considered a retail exposure and shall be assigned a risk
> weight of **100 %**.
> 5. ... loans granted ... to pensioners or employees with a permanent contract against the
> unconditional transfer of part of the borrower's pension or salary ... **35 %** ... (c) monthly
> payments ... do not in aggregate exceed 20 % of the borrower's net monthly pension or salary;
> (d) maximum original maturity ... 10 years.

### Article 123a currency mismatch (CRR3 point (54), p.49)
> 1. For exposures to natural persons [retail class, or RRE-secured] ... the risk weight ... shall be
> multiplied by a factor of **1,5**, whereby the resulting risk weight shall not be higher than **150 %**
> ... (b) ... the total of such hedges ... covers less than **90 %** of each instalment ...
> 3. ... euro and the currency of a Member State participating in ... ERM II ... the risk weight
> multiplier of 1,5 shall not apply.

### Article 124 immovable property (CRR3 point (55), pp.50-54)
> 1. A non-ADC exposure that does not meet all of the conditions set out in paragraph 3, or any part
> ... that exceeds the nominal amount of the lien ...: (a) a non-IPRE exposure shall be risk weighted as
> an exposure to the counterparty ...; (b) an IPRE exposure shall be assigned a risk weight of **150 %**.
> 2. (a)(i) non-IPRE RRE -> Article 125(1); (ii) IPRE RRE -> Article 125(1) where (1) primary
> residence, (2) natural person ... not ... more than four immovable properties ..., (3) housing
> associations/cooperatives, (4) public housing companies / not-for-profit ...; (iii) other IPRE RRE ->
> Article 125(2). (b) CRE: non-IPRE -> 126(1); IPRE -> 126(2).
> 6. ... ETV ... dividing the gross exposure amount by the property value ... [junior liens with
> unknown ranking]: ... adjust this risk weight by a multiplier of **1,25** ... Where the base risk weight
> corresponds to the lowest exposure-to-value bucket, the multiplier shall not be applied. The risk
> weight resulting ... shall be capped at the risk weight that would be applied ... if the requirements
> in paragraph 3 were not met.
> 9. ... That authority shall not increase those risk weights to more than **150 %**.

### Article 125 residential property (CRR3, pp.54-55)
> 1. ... the part of the exposure up to **55 %** of the property value shall be assigned a risk weight of
> **20 %**. [junior/pari passu lien reductions] ... The remaining part ... shall be risk weighted as an
> exposure to the counterparty that is not secured by residential property.
> 2. An exposure as referred to in Article 124(2), point (a)(iii) ... Table 1:

| ETV | ≤ 50 % | 50 % < ETV ≤ 60 % | 60 % < ETV ≤ 80 % | 80 % < ETV ≤ 90 % | 90 % < ETV ≤ 100 % | > 100 % |
|---|---|---|---|---|---|---|
| RW | 30 % | 35 % | 45 % | 60 % | 75 % | 105 % |

> By way of derogation ... institutions may apply the treatment referred to in paragraph 1 ... where
> the competent authority ... has published ... loss rates ... (a) ... does not exceed **0,3 %**; (b) ...
> does not exceed **0,5 %**.

### Article 126 commercial immovable property (CRR3, pp.55-56)
> 1. ... the part of the exposure up to **55 %** of the property value shall be assigned a risk weight of
> **60 %**. ... The remaining part ... shall be risk weighted as an exposure to the counterparty ...
> 2. ... Table 1:

| ETV | ≤ 60 % | 60 % < ETV ≤ 80 % | > 80 % |
|---|---|---|---|
| RW | 70 % | 90 % | 110 % |

(Same 0,3 % / 0,5 % loss-rate derogation.)

### Article 126a ADC (CRR3 point (56), p.56)
> 1. An ADC exposure shall be assigned a risk weight of **150 %**.
> 2. ADC exposures to residential property may be assigned a risk weight of **100 %** ... where ...
> (a) legally binding pre-sale or pre-lease contracts ... amount to a significant portion of total
> contracts; (b) the obligor has substantial equity at risk ...

### Article 127 default (para 1 cons.; paras 2-3 CRR3 point (57), p.56)
> 1. The unsecured part of any item where the obligor has defaulted ... (a) **150 %**, where the sum of
> specific credit risk adjustments and of the amounts deducted ... is less than **20 %** of the unsecured
> part ...; (b) **100 %**, where [that sum] is no less than 20 % ...
> 3. The exposure value remaining after specific credit risk adjustments of non-IPRE exposures secured
> by residential property or commercial immovable property ... shall be assigned a risk weight of
> **100 %** if a default has occurred ...

### Article 128 subordinated debt (CRR3 point (58), p.57)
> 2. Subordinated debt exposures shall be assigned a risk weight of **150 %** ...

### Article 129(4)-(5) covered bonds (CRR3 point (59), pp.57-58)
> 4. Table 1:

| CQS | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| RW | 10 % | 20 % | 20 % | 50 % | 50 % | 100 % |

> 5. ... not available ... on the basis of the risk weight assigned to senior unsecured exposures to the
> institution which issues them:

| Issuer RW | 20 % | 30 % | 40 % | 50 % | 75 % | 100 % | 150 % |
|---|---|---|---|---|---|---|---|
| Covered bond RW | 10 % | 15 % | 20 % | 25 % | 35 % | 50 % | 100 % |

### Article 133 equity (CRR3 point (63), pp.58-60)
> 3. Equity exposures, other than those referred to in paragraphs 4 to 7, shall be assigned a risk
> weight of **250 %** ...
> 4. ... equity exposures to unlisted companies shall be assigned a risk weight of **400 %** ...:
> (a) investments for short-term resale purposes; (b) investments in venture capital firms or similar
> ... By way of derogation ..., long-term equity investments ... shall be assigned a risk weight in
> accordance with paragraph 3 or 5 ... a long-term equity investment is ... held for **three years** or
> longer ...
> 5. ... **100 %** to equity exposures incurred under legislative programmes ... up to the part ... that in
> aggregate does not exceed **10 %** of the institutions' own funds ...
> 6. Equity exposures to central banks shall be assigned a risk weight of **0 %**.
> 7. An equity holding ... recorded as a loan ... from a debt-equity swap ... shall not be assigned a risk
> weight lower than ... if ... treated as a debt exposure.

Article 48(4) (cons.): "The amounts of the items that are not deducted pursuant to paragraph 1 shall be
risk weighted at **250 %**."

### Article 495a equity transitional (CRR3 point (242), p.176)
> 1. By way of derogation from ... Article 133(3), equity exposures shall be assigned the higher of the
> risk weight applicable on 8 July 2024, capped at 250 %, and the following risk-weights:
> 2. By way of derogation from ... Article 133(4), ... the higher of the risk weight applicable on
> 8 July 2024 and the following risk weights:
> 3. ... institutions may continue to assign the same risk weight that was applicable on 8 July 2024 to
> equity exposures ... to entities in which they have been a shareholder on 27 October 2021 for six
> consecutive years and over which they ... exercise significant influence or control ...

| Year | 495a(1) (Art. 133(3)) | 495a(2) (Art. 133(4)) |
|---|---|---|
| 2025 | 100 % | 100 % |
| 2026 | 130 % | 160 % |
| 2027 | 160 % | 220 % |
| 2028 | 190 % | 280 % |
| 2029 | 220 % | 340 % |

"Risk weight applicable on 8 July 2024" (SA): pre-CRR3 Article 133(2) (cons. p.175) "Equity exposures
shall be assigned a risk weight of **100 %**"; pre-CRR3 Article 128(1)-(2)(a)-(b) (cons.) **150 %** for
venture capital and private equity ("items associated with particular high risk").

### Article 134 other items (para 3 CRR3 point (64), p.60; others cons. p.175)
> 1. Tangible assets ... **100 %**. 2. Prepayments and accrued income [counterparty unknown] ... **100 %**.
> 3. (CRR3) Cash items in the process of collection shall be assigned a **20 %** risk weight. Cash owned
> and held by the institution, or in transit, and equivalent cash items shall be assigned a **0 %** risk
> weight. 4. Gold bullion held in own vaults or on an allocated basis to the extent backed by bullion
> liabilities ... **0 %**.

Article 113(5) (CRR3 point (44)): "The exposure value of any item for which no risk weight is provided
for under this Chapter shall be assigned a risk weight of **100 %**."

## 3. Off-balance-sheet items

### Article 111(2)-(4) (CRR3 point (42), p.40)
> 2. ... (a) 100 % for items in bucket 1; (b) 50 % ... bucket 2; (c) 40 % ... bucket 3; (d) 20 % ...
> bucket 4; (e) 10 % ... bucket 5.
> 3. The exposure value of a commitment on an off-balance-sheet item ... shall be the lower of [the
> percentage of the underlying item and of the type of commitment].
> 4. ... For contractual arrangements that meet the conditions set out in Article 5, points (10)(a) to
> (e), the applicable percentage shall be **0 %**.

### Annex I (CRR3 Annex, pp.188-189)
| Bucket | Items |
|---|---|
| 1 | (a) credit derivatives, general guarantees of indebtedness, SBLCs as financial guarantees, acceptances, other direct credit substitutes; (b) repos and asset sales with recourse; (c) securities lent or posted as collateral; (d) forward asset purchases, forward deposits, partly paid shares; (e) credit substitutes not explicitly included elsewhere; (f) similar risk as communicated to EBA |
| 2 | (a) NIFs and RUFs regardless of maturity; (b) performance bonds, bid bonds, warranties and SBLCs related to particular transactions and similar transaction-related contingent items, excluding trade finance items in bucket 4; (c) similar |
| 3 | (a) the undrawn amount of commitments, regardless of the maturity of the underlying facility, unless they fall under another category; (b) similar |
| 4 | (a) trade finance off-balance-sheet items: (i) warranties, incl. tender and performance bonds and associated advance payment and retention guarantees, and guarantees not having the character of credit substitutes; (ii) irrevocable SBLCs not having the character of credit substitutes; (iii) short-term, self-liquidating trade letters of credit ...; (b) similar |
| 5 | (a) the undrawn amount of unconditionally cancellable commitments; (b) the undrawn amount of retail credit lines [cancellable to the extent allowed by consumer protection law]; (c) undrawn credit facilities for tender and performance guarantees which may be cancelled unconditionally ...; (d) similar |

### Article 495d (CRR3 point (242), p.179)
> 1. ... the exposure value of an off-balance-sheet item in the form of unconditionally cancellable
> commitment by multiplying the percentage provided for in that Article by the following factors:
> (a) **0 %** 1.1.2025-31.12.2029; (b) **25 %** 2030; (c) **50 %** 2031; (d) **75 %** 2032.

Effective bucket-5 CCF: 0 % (2025-2029), 2,5 % (2030), 5 % (2031), 7,5 % (2032), 10 % (2033+).

## 4. Credit risk mitigation

### Article 223 (cons. p.279-280; para 4 replaced by CRR3 point (129))
> 2. C_VA = C · (1 − H_C − H_fx). 3. E_VA = E · (1 + H_E).
> 4. (a) [SA] the exposure value of an off-balance-sheet item listed in Annex I shall be 100 % of that
> item's value rather than the exposure value indicated in Article 111(2).
> 5. E* = max{0; E_VA − C_VAM}.

### Article 228 (CRR3 point (134), p.96)
> Under the Standardised Approach, institutions shall use E* ... as the exposure value ... In the case
> of off-balance-sheet items listed in Annex I, institutions shall use E* as the value to which the
> percentages indicated in Article 111(2) shall be applied ...

### Article 224(2) (cons. p.283)
> (a) for secured lending transactions the liquidation period shall be **20** business days; (b) for
> repurchase transactions ... and securities lending or borrowing transactions ... **5** business days;
> (c) for other capital market driven transactions ... **10** business days.

### Article 224(1) Tables 1-4 (CRR3 point (130), pp.94-95) -- volatility adjustments, % (20-day / 10-day / 5-day)

Table 1 (long-term credit assessments):

| CQS | Residual maturity | 197(1)(b) sovereign | 197(1)(c)-(d) other issuers | 197(1)(h) securitisation |
|---|---|---|---|---|
| 1 | m ≤ 1 | 0,707 / 0,5 / 0,354 | 1,414 / 1 / 0,707 | 2,828 / 2 / 1,414 |
| 1 | 1 < m ≤ 3 | 2,828 / 2 / 1,414 | 4,243 / 3 / 2,121 | 11,314 / 8 / 5,657 |
| 1 | 3 < m ≤ 5 | 2,828 / 2 / 1,414 | 5,657 / 4 / 2,828 | 11,314 / 8 / 5,657 |
| 1 | 5 < m ≤ 10 | 5,657 / 4 / 2,828 | 8,485 / 6 / 4,243 | 22,627 / 16 / 11,314 |
| 1 | m > 10 | 5,657 / 4 / 2,828 | 16,971 / 12 / 8,485 | 22,627 / 16 / 11,314 |
| 2-3 | m ≤ 1 | 1,414 / 1 / 0,707 | 2,828 / 2 / 1,414 | 5,657 / 4 / 2,828 |
| 2-3 | 1 < m ≤ 3 | 4,243 / 3 / 2,121 | 5,657 / 4 / 2,828 | 16,971 / 12 / 8,485 |
| 2-3 | 3 < m ≤ 5 | 4,243 / 3 / 2,121 | 8,485 / 6 / 4,243 | 16,971 / 12 / 8,485 |
| 2-3 | 5 < m ≤ 10 | 8,485 / 6 / 4,243 | 16,971 / 12 / 8,485 | 33,941 / 24 / 16,971 |
| 2-3 | m > 10 | 8,485 / 6 / 4,243 | 28,284 / 20 / 14,142 | 33,941 / 24 / 16,971 |
| 4 | all | 21,213 / 15 / 10,607 | N/A | N/A |

Table 2 (short-term assessments): CQS 1: 0,707/0,5/0,354 (sov), 1,414/1/0,707 (other),
2,828/2/1,414 (sec); CQS 2-3: 1,414/1/0,707, 2,828/2/1,414, 5,657/4/2,828.

Table 3: main index equities, main index convertible bonds 28,284 / 20 / 14,142; other equities or
convertible bonds listed on a recognised exchange 42,426 / 30 / 21,213; cash 0 / 0 / 0; gold bullion
28,284 / 20 / 14,142.

Table 4 (H_fx): 11,314 / 8 / 5,657.

Article 197(1)(b) (CRR3 point (112)): sovereign debt eligible at CQS 1-4; (c)-(e): CQS 1-3.

Unfunded protection: substitution of the protection provider's risk weight for the covered part
(Article 235 as amended by CRR3 point (140)); the full text of Article 235 is not transcribed here and the
engine applies plain substitution only where it lowers RWEA. Currency-mismatch (Art. 233(3)) and
maturity-mismatch (Art. 239) adjustments are not modelled.

## 5. Supporting factors (retained by CRR3)

### Article 501 SME supporting factor (para 1 cons. p.733; para 2(a)-(b) CRR3 point (246), p.180)
> 1. ... RWEA* = RWEA · [min{E*; EUR 2 500 000} · **0,7619** + max{E* − EUR 2 500 000; 0} · **0,85**] / E*
> where ... E* = the total amount owed to the institution, its subsidiaries, its parent undertakings ...
> by the SME or the group of connected clients ..., excluding claims ... secured on residential property
> collateral ...
> 2. (a) (CRR3) the exposure to an SME shall be included either in the retail or in the corporates or
> secured by mortgages on immovable property exposure classes but excluding ADC exposures;
> (b) (CRR3) an SME shall have the meaning laid down in Article 5, point (9).

### Article 501a infrastructure supporting factor (cons. p.734; points (a), (f), (o) CRR3 point (247))
> 1. Own funds requirements for credit risk ... shall be multiplied by a factor of **0,75**, provided that
> the exposure complies with all the following criteria: (a) (CRR3) the exposure is assigned to the
> exposure class referred to in Article 112, point (g) [corporates, incl. specialised lending], or ...
> Article 147(2), point (c)(i), (ii) or (iii), with the exclusion of exposures in default; (b) ... entity
> ... created specifically to finance or operate physical structures ... that provide or support
> essential public services; (c) ... not less than two thirds ... income generated by the assets ...;
> ... (o) (CRR3) for exposures originated after 1 January 2025 ... contribute positively to ... the
> environmental objectives ... of Regulation (EU) 2020/852 ...

## 6. Operational risk (CRR3 point (155), pp.105-112)

> Article 312: The own funds requirement for operational risk shall be the business indicator component
> calculated in accordance with Article 313.

Article 313 (image, p.105), BI in billions of euro:

```
        ⎧ 0,12 · BI,                  where BI ≤ 1
BIC  =  ⎨ 0,12 + 0,15 · (BI − 1),     where 1 < BI ≤ 30
        ⎩ 4,47 + 0,18 · (BI − 30),    where BI > 30
```

Article 314: BI = ILDC + SC + FC (314(1)); **ILDC = min(IC, 0,0225 · AC) + DC** (314(2), image p.106);
IC = interest income minus interest expenses (incl. leases) "calculated as the annual average of the
absolute values of the differences over the last three financial years"; AC = gross loans, advances,
interest-bearing securities and lease assets, three-year average of year-end amounts; DC = dividend
income from non-consolidated investments, three-year average.
SC = max(OI, OE) + max(FI, FE) (314(5)); FC = TC + BC, each "the annual average of the absolute values
over the last three financial years of the net profit or loss" (314(6)). Exclusions in 314(7).

Article 316(1): institutions with a BI equal to or exceeding **EUR 750 million** calculate the annual
operational risk loss; waiver possible where BI does not exceed **EUR 1 billion**.
Article 318(1): net loss = gross loss − recovery, maintained over a **10**-year window.
Article 319: loss data thresholds **EUR 20 000** (316(1)) and **EUR 100 000** (Article 446 disclosure).
There is no loss component and no internal loss multiplier in the EU calculation.

## 7. Counterparty credit risk and CVA

### Article 274(2) (cons. p.345, not amended)
> Exposure value = α · (RC + PFE) ... α = **1,4**.
> 3. The exposure value of a netting set that is subject to a contractual margin agreement shall be capped
> at the exposure value of the same netting set not subject to any form of margin agreement.
> 5. ... may set to zero the exposure value of a netting set that satisfies all the following conditions:
> (a) solely composed of sold options; (b) current market value ... at all times negative; (c) premium ...
> received upfront ...; (d) not subject to any margin agreement.

### Article 278 (cons. p.351)
> 1. PFE = multiplier · Σ_a AddOn(a).
> 3. multiplier = 1 if z ≥ 0; min{1; Floor_m + (1 − Floor_m) · exp(z / y)} if z < 0, where
> Floor_m = **5 %**; y = 2 · (1 − Floor_m) · Σ_a AddOn(a); z = CMV − NICA (Art. 275(1) netting sets),
> CMV − VM − NICA (Art. 275(2)), CMV_i − NICA_i (Art. 275(3)).

### Article 382(3)-(4) (cons. p.543) -- exclusions from CVA risk
> 3. Transactions with a qualifying central counterparty and a client's transactions with a clearing
> member ... are excluded ...
> 4. (a) transactions with non-financial counterparties ... where those transactions do not exceed the
> clearing threshold ...; (b) intragroup transactions ...; (c) transactions with counterparties referred
> to in point (10) of Article 2 of Regulation (EU) No 648/2012 [pension scheme arrangements] and subject
> to the transitional provisions ...; (d) transactions with counterparties referred to in Article 1(4) and
> (5) of Regulation (EU) No 648/2012 and ... for which Article 114(4) and Article 115(2) ... specifies a
> risk weight of 0 % ...

CRR3 point (198) adds 382(4a) (optional inclusion of hedged exempt transactions) and 382(4b) (reporting
of the requirement that would apply to the exempt transactions).

### Article 384 basic approach (CRR3 point (202), pp.155-158; formulas are images)
```
BACVA_total          = β · BACVA_csr-unhedged + DS_CVA · (1 − β) · BACVA_csr-hedged,   DS_CVA = 0,65, β = 0,25
BACVA_csr-hedged     = sqrt( (ρ·Σ_c(SCVA_c − SNH_c) − IH)² + (1 − ρ²)·Σ_c(SCVA_c − SNH_c)² + Σ_c HMA_c )
SCVA_c               = (1/α) · RW_c · Σ_NS M_NS^c · EAD_NS^c · DF_NS^c
SNH_c                = Σ_h r_hc · RW_h^SN · M_h^SN · B_h^SN · DF_h^SN
IH                   = Σ_i RW_i^ind · M_i^ind · B_i^ind · DF_i^ind
HMA_c                = Σ_h (1 − r_hc²) · (RW_h · M_h^SN · B_h^SN · DF_h^SN)²
α = 1,4;  ρ = 0,5
DF                   = (1 − e^(−0,05·M)) / (0,05·M);   DF = 1 for IMM users
BACVA_csr-unhedged   = DS_CVA · sqrt( (ρ·Σ_c SCVA_c)² + (1 − ρ²)·Σ_c SCVA_c² )         (384(3))
```
M_NS per Article 162 but "shall not be capped at five years, but at the longest contractual remaining
maturity in the netting set". RW_i^ind = Table 1 RW (single sector/quality) or the weighted average of the
constituents' Table 1 RWs, "multiplied by **0,7**". Unrated counterparties: internal rating mapped to CQS
1-3 or 4-6 subject to approval, "otherwise, the risk weights for unrated exposures shall be applied".

Table 1:

| Sector of counterparty | CQS 1 to 3 | CQS 4 to 6 and not rated |
|---|---|---|
| Central government, incl. central banks, MDBs and international organisations in Art. 117(2) or 118 | 0,5 % | 2,0 % |
| Regional government or local authority and public sector entities | 1,0 % | 4,0 % |
| Financial sector entities, incl. credit institutions incorporated or established by a central government, a regional government or a local authority, and promotional lenders | 5,0 % | 12,0 % |
| Basic materials, energy, industrials, agriculture, manufacturing, mining and quarrying | 3,0 % | 7,0 % |
| Consumer goods and services, transportation and storage, administrative and support service activities | 3,0 % | 8,5 % |
| Technology, telecommunications | 2,0 % | 5,5 % |
| Health care, utilities, professional and technical activities | 1,5 % | 5,0 % |
| Other sector | 5,0 % | 12,0 % |

Table 2: r_hc = **100 %** (reference entity is the counterparty, 386(3)(a)(i)); **80 %** (legally
related: parent/subsidiary or common parent, (a)(ii)); **50 %** (same sector and region, (a)(iii)).

### Article 385 simplified approach (p.158)
> 1. An institution that meets all of the conditions set out in Article 273a(2) [or] ... Article 273a(4)
> ... may calculate the own funds requirements for CVA risk as the risk-weighted exposure amounts for
> counterparty risk ... divided by **12,5**.

## 8. Buffers (Directive 2013/36/EU -- not in the source texts)

| Item | Placeholder in engine | Status |
|---|---|---|
| Capital conservation buffer (CRD Art. 129) | 2,5 % | **TODO: VERIFY** |
| Countercyclical buffer (CRD Art. 130, 136, 140) | input rate | **TODO: VERIFY** range |
| G-SII buffer by sub-category 1-5 (CRD Art. 131(4), (9)) | 1,0 / 1,5 / 2,0 / 2,5 / 3,5 % | **TODO: VERIFY** |
| O-SII buffer ceiling (CRD Art. 131(5)) | 3 % cap on the input | **TODO: VERIFY** |
| Systemic risk buffer (CRD Art. 133) | input rate, additive | **TODO: VERIFY** stacking |
| Combination of G-SII / O-SII / SyRB (CRD Art. 131(14)-(15)) | max(G-SII, O-SII) + SyRB | **TODO: VERIFY** |

The only buffer-related value in the sources is the G-SII leverage ratio buffer (Article 92(1a)).

## 9. Register of `TODO: VERIFY` items

1. CRD buffer rates and stacking (section 8) -- Directive text not supplied.
2. Short-term rating -> CQS mapping for Article 131 / 120(3) (Implementing Regulation (EU) 2016/1799).
3. Interaction of the Article 501 and 501a factors on one exposure (text silent; engine applies only 501a).
4. CRD VI output-floor transitional (OF-ADJ, CET1 caps; Directive (EU) 2024/1619) -- not supplied.

## 10. Material differences from the Basel Framework (BCBS)

1. **Output floor phase-in starts 2025 and reaches 72,5 % in 2030** (Art. 465(1)) vs BCBS 50 % in 2023 to
   72,5 % in 2028 (RBC90.1 Table 1).
2. **Transitional cap at 125 % of U-TREA until 2029 is an institution option** (Art. 465(2)) vs a
   supervisory discretion "to cap the incremental increase ... at 25 %" (RBC90.2).
3. **Floor-only transitionals** absent from BCBS: unrated corporates with PD ≤ 0,5 % at 65 % to 2032
   (465(3)); RRE 10 % / 45 %-67,5 % to 2032 (465(5), (9)); SA-CCR alpha 1 in S-TREA to 2029 (465(4));
   SEC-SA p of 0,25 / 0,5 to 2032 (465(13)). Member State waiver at individual level (92(3)).
4. **SME supporting factor retained** (Art. 501: 0,7619 up to EUR 2,5m, 0,85 above) and **no 85 % SME
   corporate weight** (Art. 122(2) 100 %) vs BCBS 85 % unrated SME corporates (CRE20.47). The EBA advised
   removing the factor (EBA Policy Advice, Recommendation CR 2).
5. **Infrastructure supporting factor retained** (Art. 501a, x0,75) -- no BCBS equivalent; EBA
   Recommendation CR 3 advised removal.
6. **Unconditionally cancellable commitments: 0 % CCF until 2029**, then 2,5 / 5 / 7,5 % and 10 % from
   2033 (Art. 495d) vs 10 % immediately (CRE20.100).
7. **Equity phase-in** 2025-2029 (Art. 495a: 100 %->220 % / 100 %->340 %) and grandfathering of strategic
   participations held since 2015 (495a(3)); BCBS phase-in runs from 1 January 2023 over five years
   (CRE90.1).
8. **Real estate: loan-splitting is mandatory for non-IPRE** (Art. 125(1)/126(1): 20 % / 60 % up to 55 %
   of value) vs the BCBS whole-loan default with loan-splitting as a national option (CRE20.82-20.83,
   CRE20.86); the CRE secured-part weight is a flat 60 % rather than "60 % or the counterparty RW,
   whichever is lower" (CRE20.86).
9. **IPRE residential owned by natural persons with ≤ 4 properties, co-operatives and social housing are
   treated as non-IPRE** (Art. 124(2)(a)(ii)); hard-test derogation for IPRE at 0,3 % / 0,5 % loss rates
   (125(2), 126(2) third subpara.).
10. **Specialised lending: 80 % transitional for high-quality object finance to 2032** (495b(3)) -- no BCBS
    equivalent; high-quality PF 80 % only if the infrastructure factor is not used (122a(3)(c)(ii)).
11. **Retail payroll/pension loans at 35 %** (Art. 123(5)) -- no BCBS equivalent.
12. **Rated MDBs not on the 0 % list follow a 20/30/50/100/100/150 % table and unrated MDBs 50 %**
    (Art. 117(1)); PSEs and RGLAs keep the CRR sovereign-based option with a 20 % short-term PSE weight
    (116(3)) and 20 % for Member State RGLAs in domestic currency (115(5)).
13. **Covered bonds: unrated mapping adds 30 %->15 %, 40 %->20 %, 75 %->35 %** (Art. 129(5)); rated CQS 1
    at 10 % (129(4)).
14. **Operational risk: BIC only, no ILM/loss component** (Art. 312) vs BCBS ILM with a national option to
    set ILM = 1 (OPE25.11 in the supplied Basel Framework text). EU also allows a separate ILDC for
    high-PD subsidiaries until 2027 (314(3)).
15. **SA-CCR alpha fixed at 1,4 for all counterparties** (Art. 274(2)); no non-financial / pension alpha
    relief (contrast the US NPR 1,0 for commercial end-users).
16. **CVA exemptions** for NFCs below the EMIR clearing threshold, intragroup, pension schemes and
    0 %-RW sovereigns (Art. 382(4)) -- not in the Basel framework (MAR50).
17. **Defaulted non-IPRE real estate always 100 %** (Art. 127(3)); short-term preference for unrated
    PSEs; ECAI assessments embedding implicit government support banned for institutions (Art. 138(g))
    with a 2029 transitional (495e).

## 11. Where the final law departs from the EBA advice (context only)

- EBA recommended removing both supporting factors (Recommendations CR 2, CR 3); CRR3 keeps them
  (Art. 501, 501a, amended only in scope).
- EBA analysed the 85 % unrated SME weight together with the factor (advice paras. 24-28); CRR3 adopts
  neither the 85 % weight nor removal of the factor.
- EBA recommended continuing loan-splitting for residential mortgages (advice section on LS vs WL);
  CRR3 follows this (Art. 125(1)).
- EBA assessed a 10 % CCF for unconditionally cancellable commitments; CRR3 introduces a 0 % factor until
  2029 with a phase-in to 2032 (Art. 495d).
