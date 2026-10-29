const { Document, Packer, Paragraph, Table, TableRow, TableCell, TextRun,
  WidthType, AlignmentType, BorderStyle, ShadingType, PageOrientation,
  Header, Footer, HeadingLevel, convertInchesToTwip, TableOfContents } = require("docx");
const fs = require("fs");

// Theme colors
const NAVY = "1A2744";
const GOLD = "C2A677";
const WHITE = "FFFFFF";
const LGRAY = "F2F2F2";
const RED = "C0392B";
const AMBER = "F39C12";
const GREEN = "27AE60";

// Column widths for 4-col table (landscape)
const CW = [2200, 2800, 2800, 2700];

function hdrCell(text, w) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: { color: WHITE, fill: NAVY, type: ShadingType.CLEAR },
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
      new TextRun({ text, bold: true, size: 16, color: WHITE, font: "Calibri" })
    ]})],
  });
}

function dataCell(text, w, bold=false, shade=WHITE) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: { color: "000000", fill: shade, type: ShadingType.CLEAR },
    children: [new Paragraph({ children: [
      new TextRun({ text: text||"", bold, size: 16, font: "Calibri" })
    ]})],
  });
}

function subCell(text, w) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: { color: "000000", fill: GOLD, type: ShadingType.CLEAR },
    children: [new Paragraph({ children: [
      new TextRun({ text, bold: true, size: 16, color: NAVY, font: "Calibri" })
    ]})],
  });
}

function hdrRow() {
  return new TableRow({ children: [
    hdrCell("Dimension", CW[0]), hdrCell("2023 NPR (July)", CW[1]),
    hdrCell("2026 Re-Proposal (March)", CW[2]), hdrCell("Impact / Implication", CW[3])
  ]});
}

function row(d, a, b, c, idx) {
  const sh = idx % 2 === 0 ? WHITE : LGRAY;
  return new TableRow({ children: [
    dataCell(d, CW[0], true, sh), dataCell(a, CW[1], false, sh),
    dataCell(b, CW[2], false, sh), dataCell(c, CW[3], false, sh)
  ]});
}

function subRow(text) {
  return new TableRow({ children: CW.map(w => subCell(text, w)) });
}

function secTitle(num, title) {
  return [
    new Paragraph({ spacing: { before: 400, after: 100 }, children: [
      new TextRun({ text: "SECTION " + num, bold: true, size: 28, color: GOLD, font: "Calibri" })
    ]}),
    new Paragraph({ spacing: { before: 0, after: 200 }, children: [
      new TextRun({ text: title, bold: true, size: 32, color: NAVY, font: "Calibri" })
    ]}),
    new Paragraph({ children: [
      new TextRun({ text: "_".repeat(130), size: 12, color: GOLD })
    ]}),
  ];
}

function makeTable(rows) {
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: [hdrRow(), ...rows.map((r, i) => {
      if (r.length === 1) return subRow(r[0]);
      return row(r[0], r[1], r[2], r[3], i);
    })],
  });
}

// ── BUILD DOCUMENT ──
const children = [];

// Cover page
children.push(
  new Paragraph({ spacing: { before: 2000 } }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [
    new TextRun({ text: "NPR 2023 vs 2026 Re-Proposal", bold: true, size: 72, color: NAVY, font: "Calibri" })
  ]}),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200 }, children: [
    new TextRun({ text: "Complete Regulatory Change Analysis", bold: true, size: 44, color: GOLD, font: "Calibri" })
  ]}),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 400 }, children: [
    new TextRun({ text: "US Federal Reserve Basel III Endgame", size: 28, color: NAVY, font: "Calibri" })
  ]}),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200 }, children: [
    new TextRun({ text: "July 2023 NPR (RESCINDED) vs March 2026 Re-Proposal (ACTIVE)", size: 24, font: "Calibri" })
  ]}),
  new Paragraph({ spacing: { before: 1000 } }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [
    new TextRun({ text: "_".repeat(80), color: GOLD, size: 20 })
  ]}),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200 }, children: [
    new TextRun({ text: "Model ID: FNBC-BIII-2026-001  |  CONFIDENTIAL  |  " + new Date().toISOString().split("T")[0], size: 20, font: "Calibri" })
  ]}),
  new Paragraph({ pageBreakBefore: true }),
);

// ── SECTION 1: SCOPE ──
children.push(...secTitle("1", "Scope & Applicability"));
children.push(makeTable([
  ["Scope & Applicability"],
  ["Applicable institutions", "Category I-IV BHCs ($100B+ assets, ~37 BHCs) [ERBA P.1]", "Category I-II ONLY (~9 largest BHCs) [Re-Proposal P.1]", "MASSIVE reduction: 37 BHCs -> 9. 76% fewer institutions affected"],
  ["Category III treatment", "Mandatory compliance required [ERBA P.12]", "Optional opt-in only [Re-Proposal P.8]", "Cat III banks can choose SA or current rules"],
  ["Category IV treatment", "Mandatory compliance required [ERBA P.12]", "Not mandatory; any banking organization may elect ERBA in its entirety (election effective 12 months after notice) [Re-Proposal P.20-23]", "Cat IV removed from mandatory scope; opt-in brings Cat I/II capital definition (AOCI, deductions)"],
  ["Separate SA proposal", "Combined single NPR for all banks [ERBA P.1]", "Separate revised standardized approach NPR for non-ERBA banks [Re-Proposal P.21]", "Bifurcated rulemaking reduces complexity for smaller banks"],
  ["Community banks", "Not directly affected [ERBA P.3]", "Not directly affected; confirmed [Re-Proposal P.3]", "No change for community banks under either proposal"],
  ["Asset threshold", "$100B consolidated assets [12 CFR 217.1]", "Cat I = US GSIBs; Cat II = >=$700B total assets or >=$75B cross-jurisdictional activity; any other bank may opt in [Re-Proposal P.12 fn 1, P.22]", "Mandatory scope limited to Category I and II banking organizations (9 BHCs)"],
  ["Effective date", "July 1, 2025 [ERBA P.4]", "Not fixed in NPR text: rule text carries bracketed placeholders (AOCI transition begins [January 1, 2027]) [Re-Proposal P.1151, §__.300]", "Effective date to be set in the final rule; the specific 2028 date previously shown here is not in the NPR"],
  ["Phase-in period", "3 years (2025-2028) [ERBA P.4]", "No general phase-in. Only AOCI transition for ERBA electors: 100/80/60/40/20/0% over [2027]-[2032] (Table 1 to §__.300) [Re-Proposal P.1151]", "Single-step implementation apart from the five-year AOCI transition"],
  ["Comment period", "120 days (Sep 2023 - Jan 2024) [ERBA P.2]", "Per Federal Register notice (comment deadline not verified in this review)", "Fresh comment period for substantially revised proposal"],
  ["Comments received", "~97 comment letters [Fed website]", "Pending (proposal just issued)", "2023 drew unprecedented industry opposition"],
  ["Board vote", "6-1 (Vice Chair Barr voted FOR) [Fed minutes]", "6-1 (Vice Chair Barr SOLE DISSENT, against lower capital) [Fed minutes]", "Barr switched from advocate to sole opponent of reduced capital"],
  ["FDIC vote", "3-2 (partisan split) [FDIC minutes]", "Unanimous approval [FDIC minutes]", "Bipartisan consensus achieved in 2026"],
  ["OCC vote", "Unanimous [OCC minutes]", "Unanimous [OCC minutes]", "OCC consistent across both proposals"],
  ["Industry reaction", "Fierce opposition; bank lobbying campaign [Public record]", "Broadly supportive; industry praised recalibration [Public record]", "180-degree shift in industry sentiment"],
  ["Formal status", "RESCINDED (Sept 2024, Barr speech) [Fed announcement]", "Active proposal [Re-Proposal header]", "2023 NPR formally withdrawn before 2026 issuance"],
  ["Collins Amendment", "SA retained as capital floor [12 USC 5371]", "SA retained as capital floor [12 USC 5371]", "Both comply with Collins Amendment statutory requirement"],
  ["IRB for credit risk", "Eliminated for RWA calculation [ERBA P.95]", "Eliminated for RWA calculation [Re-Proposal P.95]", "Consistent: US removes IRB entirely (unlike UK/EU)"],
]));
children.push(new Paragraph({ spacing: { before: 200 } }));

// ── SECTION 2: CAPITAL IMPACT ──
children.push(...secTitle("2", "Capital Impact Analysis"));
children.push(makeTable([
  ["Aggregate Capital Impact"],
  ["Aggregate CET1 impact", "+19% increase in CET1 requirements [Barr Sept 2024 speech]", "Proposal alone: +1.4% CET1 / +1.6% T1 for the 9 Cat I/II BHCs (Table VII.1; preamble summary cites +1.2%); -4.8% CET1 for their DI subsidiaries [Re-Proposal P.14, P.503]", "Standalone impact roughly neutral for holding companies; range +0.6% to +1.4% depending on as-of quarter (P.505)"],
  ["G-SIB specific impact", "+16% for 8 US G-SIBs [Barr Sept 2024 speech]", "Cumulative: this proposal + G-SIB surcharge proposal = -2.4% CET1; + proposed stress test changes = -4.8% CET1 (-6.0% T1) [Re-Proposal Table VII.3, P.511]", "Combined proposals reduce Cat I/II BHC CET1 requirement from $860B to $818B (Table VII.4)"],
  ["G-SIB surcharge aggregate", "Unchanged from current rules [ERBA P.42]", "Per separate G-SIB surcharge NPR (not verified in this review). ERBA NPR: risk-weight revisions + G-SIB surcharge together lower Cat I/II BHC CET1 minimum-plus-buffer requirements by $42.1B [Re-Proposal P.583]", "The ~$33B figure previously shown is not supported by the ERBA NPR"],
  ["Credit risk RWA impact", "+~$350B estimated [Industry analysis]", "Credit RWA $6,165B under ERBA (vs $4,890B advanced approaches); binding CET1 requirement for credit risk -10.0% under combined proposals [Re-Proposal Tables VII.2, VII.4]", "Corporate lending RWA -18%, residential mortgage RWA -10%, retail RWA +9% (Table VII.5)"],
  ["Market risk RWA impact", "+~$85B estimated [Industry analysis]", "+~20%: $453B -> $546B for Cat I/II BHCs [Re-Proposal Table VII.2, P.506]", "Market CET1 requirement -5.8% cumulatively once stress-test GMS changes are included (P.519)"],
  ["Operational risk RWA impact", "+~$250B estimated [Industry analysis]", "$927B operational RWA (vs $1,745B advanced approaches); binding op-risk CET1 requirement +14.9% [Re-Proposal Tables VII.2, VII.4]", "Op-risk RWA new to the standardized stack but well below internal-model (AMA) levels"],
  ["CVA risk RWA impact", "+~$40B estimated [Industry analysis]", "$207B CVA RWA (vs $280B advanced approaches); binding CVA CET1 requirement +96% [Re-Proposal Tables VII.2, VII.4]", "Largest percentage increase of any risk type (SA has no CVA charge today)"],
  ["Total RWA impact", "+~$725B aggregate [Industry estimates]", "+1.9%: $7,673B (current SA) -> $7,820B (ERBA), 9 Cat I/II BHCs, data as of June 30, 2025 [Re-Proposal Tables VII.2, VII.5]", "Near-neutral aggregate RWA; DI subsidiaries -3.0% (P.507)"],
  ["Impact Waterfall"],
  ["JPM estimated impact", "~$50B additional CET1 needed [JPM 10-Q]", "Not disclosed in NPR (firm-level impacts not published)", "NPR gives only aggregate figures; std. dev. of CET1 impact across the 9 BHCs ~8.7% (P.505)"],
  ["BAC estimated impact", "~$35B additional CET1 [BAC 10-Q]", "Not disclosed in NPR", "See aggregate figures above"],
  ["Citigroup estimated impact", "~$25B additional CET1 [C 10-Q]", "Not disclosed in NPR", "See aggregate figures above"],
  ["Wells Fargo impact", "~$20B additional CET1 [WFC 10-Q]", "Not disclosed in NPR", "See aggregate figures above"],
  ["Goldman Sachs impact", "~$15B additional CET1 [GS 10-Q]", "Not disclosed in NPR", "See aggregate figures above"],
  ["Morgan Stanley impact", "~$12B additional CET1 [MS 10-Q]", "Not disclosed in NPR", "See aggregate figures above"],
  ["ISDA 2026 QIS (industry)", "N/A", "ISDA estimates: FRTB-SA +89%, IMA/SA blend +30%, DRC ~51% of FRTB capital, CVA RWA ~$168B, CCR RWA 0.77x [ISDA 2026 QIS note - not NPR figures]", "Industry estimates; attributed to ISDA, not to the NPR"],
  ["Vice Chair Barr Sept 2024", "Announced broad recalibration [Fed speech]", "N/A (preceded re-proposal)", "Key speech signaling 2023 NPR would be substantially revised"],
  ["Barr rationale", "Preserve bank competitiveness [Speech]", "2026 achieves same safety goals with less burden [Speech]", "Framed as achieving same safety with better calibration"],
]));
children.push(new Paragraph({ spacing: { before: 200 } }));

// ── SECTION 3: CREDIT RISK SA ──
children.push(...secTitle("3", "Credit Risk Standardized Approach: Risk Weight Changes"));
children.push(makeTable([
  ["Sovereign Risk Weights (by CRC)"],
  ["Sovereign CRC 0-1", "0% [ERBA P.102]", "0% [Re-Proposal P.102]", "Unchanged"],
  ["Sovereign CRC 2", "20% [ERBA P.102]", "20% [Re-Proposal P.102]", "Unchanged"],
  ["Sovereign CRC 3", "50% [ERBA P.102]", "50% [Re-Proposal P.102]", "Unchanged"],
  ["Sovereign CRC 4-6", "100% [ERBA P.102]", "100% [Table 1 to §__.111; identical to current §__.32 Table 1 (P.54 fn 80)]", "Unchanged"],
  ["Sovereign CRC 7", "150% [ERBA P.102]", "150% [Table 1 to §__.111]", "Unchanged"],
  ["Sovereign no CRC / default", "OECD member 0%; non-OECD 100%; default 150% [ERBA P.102]", "OECD member 0%; non-OECD 100%; sovereign default 150% [Table 1 to §__.111]", "Unchanged"],
  ["Bank Risk Weights"],
  ["Bank Grade A (meets §__.111(d)(2))", "Grade A 40% (2023 NPR; not re-verified in this review)", "NEW: 30% where obligor has CET1 >=14% and SLR/leverage ratio >=5% (or is a CBLR bank; credit unions net worth >=9%) [Table 2 to §__.111; P.52]", "NEW 30% tier; 68.3% of US DIs would qualify on June 30, 2025 data (P.52)"],
  ["Bank Grade A (Other)", "Grade A 40% (2023 NPR; not re-verified)", "40% [Table 2 to §__.111]", "Grade A = investment grade AND capital >= higher of (minimum + buffers) / well-capitalized (P.51)"],
  ["Bank Grade B", "Grade B 75% (2023 NPR; not re-verified)", "75% [Table 2 to §__.111]", "Speculative grade or IG with capital >= minimum / adequately capitalized"],
  ["Bank Grade C", "Grade C 150% (2023 NPR; not re-verified)", "150% [Table 2 to §__.111]", "Banks not qualifying as Grade A or B"],
  ["Bank short-term (<=3mo)", "20%/50%/150% short-term bank exposures (2023 NPR; not re-verified)", "NO general short-term preference. Only self-liquidating trade-related contingent items to FOREIGN banks with maturity <=3 months: 20%/20%/50%/150% by grade [Table 2 to §__.111; P.54]", "Preferential short-term RW limited to trade finance to foreign banks"],
  ["Bank subordinated / covered debt", "150% (2023 NPR; not re-verified)", "150% for subordinated bank exposures and covered debt instruments (TLAC) not deducted [§__.111; P.50 fn 71]", "Unchanged"],
  ["Corporate Risk Weights"],
  ["Corporate IG (internal rating)", "65% [ERBA P.130]", "65% - investment grade per internal credit risk rating system [§__.111; P.82-86]", "Scope of 65% RW expanded relative to 2023 (P.534: ~53% of on-BS / 60% of off-BS corporate exposure qualifies)"],
  ["Corporate standard", "100% [ERBA P.130]", "100% [§__.111]", "Unchanged"],
  ["Corporate SME", "No SME risk weight (2023 NPR; not re-verified)", "No SME preferential weight: 100% (65% if IG). SME (revenue <= $50M, CPI-W indexed) matters only for regulatory retail (<= $1M aggregate) [§__.101, §__.111]", "US does not adopt the Basel 85% SME weight; the SME threshold and weight previously shown here are not in the NPR"],
  ["Project finance", "130% pre-operational / 100% operational (2023 NPR; not re-verified)", "130% pre-operational / 100% operational phase; no 80% high-quality tier [§__.111; P.88-89]", "Unchanged"],
  ["Subordinated corporate / object finance", "150% / 100% (2023 NPR; not re-verified)", "Subordinated corporate exposures 150%; object finance 100% [§__.111; P.82, P.91]", "Unchanged"],
  ["Retail Risk Weights"],
  ["Retail regulatory", "85% [2023 NPR, per Re-Proposal P.534: retail RWs 10pp higher]", "75% [§__.111; P.81]", "10pp REDUCTION (NPR P.534)"],
  ["Retail TRANSACTOR", "55% [2023 NPR, per Re-Proposal P.534]", "45% [§__.111; P.81]", "10pp REDUCTION. Key change for credit card portfolios"],
  ["Other retail", "110% [2023 NPR, per Re-Proposal P.534]", "100% [§__.111; P.81]", "10pp REDUCTION"],
  ["Retail transactor criteria", "Paid in full 12 months [ERBA P.140]", "Balance repaid in full at each scheduled date for prior 12 months, or overdraft with no drawdown for 12 months [§__.101; P.80]", "Same eligibility criteria, lower RW"],
  ["Residential Real Estate (not dependent on property cash flows)"],
  ["Resi RE LTV <=50%", "40% [2023 NPR, per Re-Proposal P.533: 2026 removes 20pp]", "20% [Table 5 to §__.111]", "20pp REDUCTION: 2026 adopts the Basel table"],
  ["Resi RE LTV 50-60%", "45% [2023 NPR, per Re-Proposal P.533]", "25% [Table 5 to §__.111]", "20pp REDUCTION"],
  ["Resi RE LTV 60-80%", "50% [2023 NPR, per Re-Proposal P.533]", "30% [Table 5 to §__.111]", "20pp REDUCTION (single 60-80% band in both proposals)"],
  ["Resi RE LTV 80-90%", "60% [2023 NPR, per Re-Proposal P.533]", "40% [Table 5 to §__.111]", "20pp REDUCTION at critical 80-90% LTV band"],
  ["Resi RE LTV 90-100%", "70% [2023 NPR, per Re-Proposal P.533]", "50% [Table 5 to §__.111]", "20pp REDUCTION"],
  ["Resi RE LTV >100%", "90% [2023 NPR, per Re-Proposal P.533]", "70% [Table 5 to §__.111]", "20pp REDUCTION for underwater mortgages"],
  ["Resi RE dependent on property cash flows", "+20pp vs Basel (2023 NPR, per Re-Proposal P.533)", "30/35/45/60/75/105% for LTV <=50/<=60/<=80/<=90/<=100/>100 [Table 6 to §__.111]", "Basel table adopted"],
  ["Commercial Real Estate"],
  ["CRE not CF-dependent", "min(60%, obligor RW) if LTV<=60%; else obligor RW (2023 NPR; not re-verified)", "LTV <=60%: lesser of 60% or obligor RW; LTV >60%: obligor RW (100% if unknown) [Table 7 to §__.111]", "Unchanged"],
  ["CRE income 0-60% LTV", "70% [ERBA P.148]", "70% [Table 8 to §__.111]", "Unchanged"],
  ["CRE income 60-80% LTV", "90% [ERBA P.148]", "90% [Table 8 to §__.111]", "Unchanged"],
  ["CRE income 80%+ LTV", "110% [ERBA P.148]", "110% [Table 8 to §__.111]", "Unchanged"],
  ["CRE ADC (all)", "150% flat [ERBA P.150]", "100% ADC not HVCRE / 150% HVCRE; pre-sold 1-4 family construction 50% (statutory) [§__.111; P.76]", "SPLIT introduced: non-HVCRE gets 33% reduction"],
  ["Other Exposure Classes"],
  ["Equity non-publicly traded", "400% [ERBA P.160]", "400% non-publicly traded; 600% for investment firms with greater than immaterial leverage [§__.141]", "Unchanged"],
  ["Equity publicly traded", "250% (2023 NPR; not re-verified)", "300% - current rule retained; 250% Basel alternative considered and not adopted [§__.141; P.191 fn 203]", "2026 keeps the current 300% RW"],
  ["Equity non-significant", "Removed (proposed 250%) [ERBA P.162]", "100% RETAINED for aggregate equity <= 10% of total capital; 250% for significant investments in unconsolidated FIs not deducted [§__.141; P.191]", "Industry won: 100% RW for non-significant equity RETAINED"],
  ["Equity sovereign / PSE", "0% / 20% [ERBA P.160]", "0% sovereign, MDB, FRB stock; 20% PSE, FHLB, Farmer Mac [§__.141]", "Unchanged"],
  ["MSA treatment", "Deduction from CET1 [ERBA P.78]", "250% risk weight on ALL MSAs (deduction REMOVED); MSAs excluded from the 15% aggregate threshold test [Re-Proposal P.14, P.40]", "MAJOR change: deduction replaced with 250% RW"],
  ["DTA (timing)", "10%/15% threshold deduction [ERBA P.74]", "10%/15% threshold deduction [Re-Proposal P.74]", "Unchanged"],
  ["Defaulted exposures", "150% [ERBA P.155]", "150% [Re-Proposal P.155]", "Unchanged"],
  ["PSE general obligation", "20% [ERBA P.108]", "20% [Re-Proposal P.108]", "Unchanged"],
  ["PSE revenue obligation", "50% [ERBA P.108]", "50% [Re-Proposal P.108]", "Unchanged"],
  ["Subordinated debt", "150% [ERBA P.158]", "150% [Re-Proposal P.158]", "Unchanged"],
  ["Cash items", "0% [ERBA P.100]", "0% [Re-Proposal P.100]", "Unchanged"],
]));
children.push(new Paragraph({ spacing: { before: 200 } }));

// ── SECTION 4: OFF-BALANCE SHEET ──
children.push(...secTitle("4", "Off-Balance Sheet Credit Conversion Factors"));
children.push(makeTable([
  ["CCF Changes"],
  ["Commitments >1Y maturity", "40% [2023 NPR; not re-verified] (CURRENT rule: 50%)", "40% regardless of maturity [§__.112; P.95-96]", "Unchanged vs 2023 NPR; 10pp LOWER than current rule (50%)"],
  ["Commitments <=1Y maturity", "40% [2023 NPR; not re-verified] (CURRENT rule: 20%)", "40% UNIFORM [§__.112; P.95-96]", "Unchanged vs 2023 NPR; DOUBLED vs CURRENT rule (20%). 84% of Cat I/II commitment exposure already has maturity >1Y (P.96 fn 129)"],
  ["UCC (unconditionally cancellable)", "10% [ERBA P.172] (CURRENT rule: 0%)", "10% [§__.112; P.96-97]", "Unchanged vs 2023; NEW vs current rule (0%)"],
  ["Direct credit substitutes", "100% [ERBA P.174]", "100% [§__.112]", "Unchanged"],
  ["Trade-related contingencies", "20% [ERBA P.176]", "20% (short-term self-liquidating, <=1Y) [§__.112]", "Unchanged"],
  ["Performance guarantees", "50% [ERBA P.176]", "50% (transaction-related contingent items) [§__.112]", "Unchanged"],
  ["NIF/RUF", "50% [ERBA P.176]", "50% regardless of whether a lower CCF would otherwise apply [§__.112; P.95 fn 126]", "Unchanged"],
  ["Repo-style transactions", "100% [ERBA P.178]", "100% [§__.112]", "Unchanged"],
  ["Forward asset purchases", "100% [ERBA P.178]", "100% [§__.112]", "Unchanged"],
  ["Retail lines with no pre-set limit", "Not addressed (2023 NPR; not re-verified)", "Undrawn = highest drawn amount over prior 24 months - current drawn amount; CCF 10% [§__.112; P.98-100]", "New look-back methodology (also used for SLR total leverage exposure)"],
  ["Worked Example: Short-Term Commitments (vs CURRENT rule)"],
  ["Portfolio: $100B short-term", "CURRENT rule: CCF=20%, CEA=$20B [calc]", "CCF=40%, CEA=$40B [Re-Proposal calc]", "$20B additional credit-equivalent exposure vs current rule"],
  ["At 100% RW (corporate)", "RWA=$20B [calc]", "RWA=$40B [Re-Proposal calc]", "$20B additional RWA = $1.6B additional CET1 at 8%"],
  ["At 65% RW (IG corporate)", "RWA=$13B [calc]", "RWA=$26B [Re-Proposal calc]", "$13B additional RWA = $1.04B additional CET1"],
  ["Rationale for change", "Maturity-dependent CCFs in current rule (20%/50%) [P.95 fn 127]", "Uniform 40% CCF 'would align with international standards' [Re-Proposal P.95-96]", "Simplification and Basel alignment; question 32 asks about lower UCC CCF"],
]));
children.push(new Paragraph({ spacing: { before: 200 } }));

// ── SECTION 5: OPERATIONAL RISK ──
children.push(...secTitle("5", "Operational Risk: SMA Calibration"));
children.push(makeTable([
  ["SMA Framework"],
  ["Approach", "Standardized Measurement Approach (SMA) [ERBA P.250]", "Standardized Measurement Approach (SMA) [Re-Proposal P.250]", "Same approach, different calibration"],
  ["BI formula", "BI = ILDC + SC + FC (three components) [ERBA P.252]", "BI = ILDC + noninterest component (TWO components) [§__.150; Re-Proposal P.535]", "KEY CHANGE: services and financial components merged into a single noninterest component"],
  ["ILDC definition", "min(|II - IE|, 2.25% x IEA) + dividends [ERBA P.254]", "ILDC = min(Avg3y|interest income - interest expense|, 2.25% x Avg3y interest-earning assets) + Avg3y dividend income [§__.150]", "ILDC structure unchanged; the 0.7x factor applies in the NONINTEREST component, not ILDC"],
  ["ILDC interest cap", "2.25% of IEA [ERBA P.254]", "2.25% of IEA [§__.150]", "Unchanged"],
  ["SC formula", "max(fee_inc, fee_exp) + max(oth_inc, oth_exp) [ERBA P.256]", "N/A - replaced by noninterest component = Avg3y( |noninterest income + realized HTM/AFS gains - noninterest expense for BI - 0.7 x (net income from investment management, investment services AND non-lending treasury services)| + total operational losses ) [§__.150]", "KEY CHANGE: absolute value of NET noninterest result, 0.7x scaling, operational losses added"],
  ["FC formula", "|trading P&L| + |banking P&L| [ERBA P.258]", "N/A - trading and banking book results are folded into noninterest income [§__.150]", "Separate financial component eliminated"],
  ["BIC Marginal Coefficients"],
  ["BIC bucket 1 (BI <= $1B)", "12% [ERBA P.260]", "12%: BIC = 0.12 x BI [§__.150]", "Unchanged; thresholds CPI-W indexed"],
  ["BIC bucket 2 ($1B < BI <= $30B)", "15% [ERBA P.260]", "15%: BIC = $120M + 0.15 x (BI - $1B) [§__.150]", "Unchanged"],
  ["BIC bucket 3 (BI > $30B)", "18% [ERBA P.260]", "18%: BIC = $4.47B + 0.18 x (BI - $30B) [§__.150]", "Unchanged"],
  ["Internal Loss Multiplier (ILM)"],
  ["ILM application", "INCLUDED (floored at 1): ILM = ln(e-1+(LC/BIC)^0.8) [2023 NPR; not re-verified]", "NO ILM TERM: operational RWA = 12.5 x BIC [§__.150; Question 84 asks whether to add one]", "MAJOR CHANGE: ILM removed entirely"],
  ["ILM formula", "ILM = ln(exp(1)-1+(LC/BIC)^0.8) [BCBS d424 S5.11]", "Not part of the rule text (Basel formula quoted only in Question 84) [Re-Proposal P.198-199]", "Formula eliminated; BIC alone determines capital"],
  ["Loss data requirement", "Required for LC computation [ERBA P.264]", "STILL REQUIRED: operational loss event data collection (>= $20,000 per event, CPI-W indexed); total operational losses are ADDED to the BI noninterest component [§__.150; P.204-207, P.216]", "Loss data still drives capital - through the BI, not through an ILM"],
  ["Historical loss threshold", "EUR 20,000 [ERBA P.264]", "$20,000 (indexed to CPI-W) [§__.150; Re-Proposal P.35]", "Same threshold; losses enter BI"],
  ["Loss data years", "10 years (5 year minimum) [ERBA P.264]", "10 years of loss data, including for acquired or merged entities [§__.150]", "Unchanged"],
  ["NIC for inv. management", "Gross basis [ERBA P.254]", "0.7x factor applied to NET fee income (income less related noninterest expense) from investment management, investment services AND non-lending treasury services [§__.150; P.205]", "Reduces BI for fee-based businesses; treasury services sensitivity ~0.3% of CET1 requirement (P.535 fn 570)"],
  ["Worked Example (simplified; ignores operational losses in BI)"],
  ["Example bank BI", "$14B [Example]", "$14B [Example]", "Same starting Business Indicator"],
  ["BIC calculation", "BIC = $1B*12% + $13B*15% = $2.07B [Calc]", "BIC = $1B*12% + $13B*15% = $2.07B [Calc]", "Same BIC: $2.07B"],
  ["Historical losses/yr", "$4B annual average [Example]", "Enters BI noninterest component as total operational losses (omitted from this simplified example)", "Loss data affects BI, not a multiplier"],
  ["Loss Component (LC)", "LC = 15 * $4B = $60B [BCBS formula]", "N/A [no ILM]", "LC not computed under 2026 proposal"],
  ["ILM calculation", "ILM = ln(e-1+(60/2.07)^0.8) = 1.53 [Formula]", "No ILM [§__.150]", "Multiplier of 1.53 eliminated (35% reduction in this example)"],
  ["OpRisk capital", "$2.07B * 1.53 = $3.17B [2023 calc]", "$2.07B [2026 calc]", "$1.1B LESS capital = $13.7B less RWA"],
  ["OpRisk RWA", "$3.17B * 12.5 = $39.6B [2023 calc]", "$2.07B * 12.5 = $25.9B [2026 calc]", "$13.7B RWA REDUCTION (35% less) in this example"],
]));
children.push(new Paragraph({ spacing: { before: 200 } }));

// ── SECTION 6: MARKET RISK ──
children.push(...secTitle("6", "Market Risk: FRTB Calibration"));
children.push(makeTable([
  ["FRTB Framework"],
  ["FRTB threshold", "$1B point-in-time trading activity or 10% of assets [Re-Proposal P.19, P.23]", "$5B trading assets + liabilities (four-quarter average) or >=10% of total assets; Cat I/II holding companies regardless [§__.201; P.19, P.23]", "5X INCREASE and averaging instead of point-in-time"],
  ["Banks affected", "~20 BHCs above $1B threshold [Estimate]", "All 9 Cat I/II BHCs plus other banks with significant trading activity (count not stated in NPR) [Re-Proposal P.508]", "Remaining non-Cat I/II market-risk banks see market RWA fall 35-39% (P.616, P.621)"],
  ["SBM risk classes", "7 risk classes [ERBA P.305]", "7 risk classes [§__.206]", "Unchanged: GIRR, CSR non-sec, CSR CTP, CSR sec non-CTP, Equity, Commodity, FX"],
  ["Correlation scenarios", "3: Low/Medium/High [ERBA P.310]", "3: medium = specified; high = x1.25 capped at 100%; low = max(2*rho - 100%, 75% x rho) [§__.206]", "Unchanged"],
  ["DRC framework", "Non-sec + Sec (CTP/Non-CTP); DRC computed per desk group [Re-Proposal P.537]", "Same three categories; SINGLE DRC calculation across all desks; UMBS netting permitted [§__.210; P.537]", "Single DRC and UMBS netting (ISDA/SIFMA est. ~9% SA market capital reduction, P.538 fn 576)"],
  ["DRC risk weights", "By credit quality category (2023 NPR; not re-verified)", "IG: 0.6% non-US sovereign / 2.1% PSE & GSE / 4.1% corporate; speculative 22%; sub-speculative 50%; defaulted 100% [Table 1 to §__.210]", "No external ratings (Dodd-Frank 939A)"],
  ["DRC LGD", "Senior 75% / non-senior & equity 100% (2023 NPR; not re-verified)", "100% equity & non-senior; 75% senior debt; 50% US PSE; 25% covered bonds and GSE-guaranteed debt [§__.210]", "US-specific LGDs for PSE/GSE paper"],
  ["RRAO exotic", "1.0% of notional [ERBA P.420]", "1.0% of notional [§__.211]", "Unchanged"],
  ["RRAO other", "0.1% of notional [ERBA P.422]", "0.1% of notional [§__.211]", "Unchanged"],
  ["IMA availability", "Available with supervisory approval [ERBA P.430]", "Available with supervisory approval; IMA requirement CAPPED at the standardized measure; SA/IMA diversification recognized [§__.204; P.536-537]", "IMA capped at SA (assumed in impact analysis, fn 573)"],
  ["IMA multiplier / backtesting", "m_c = 1.5 + backtesting add-on [2023 NPR; not re-verified]", "m_c = 1.5; 0-4 exceptions 1.50, 5: 1.70, 6: 1.76, 7: 1.83, 8: 1.88, 9: 1.92, >=10: 2.00 (99% 1-day VaR, 250 days) [Table 1 to §__.204]", "Unchanged ladder"],
  ["PLA test", "Spearman correlation + Kolmogorov-Smirnov [2023 NPR, per Re-Proposal P.537]", "Kolmogorov-Smirnov ONLY: green < 0.09, amber 0.09-0.12, red > 0.12; three-year transition with no automatic consequences [§__.213; P.380-381, P.537]", "Spearman test REMOVED (assumed +20pp modeled share in impact analysis, P.537)"],
  ["NMRF", "Capped diversification [2023 NPR, per Re-Proposal P.536]", "Full diversification for certain NMRFs; 24 real prices (10/20-day LH) or 16 otherwise; SES rho_b = 0.36 [§__.214-215; P.536]", "Less punitive NMRF aggregation"],
  ["GIRR Risk Weights"],
  ["GIRR 0.25Y/0.5Y", "1.7% [ERBA P.312]", "1.7% [Table 1 to §__.209]", "Unchanged"],
  ["GIRR 1Y", "1.6% [ERBA P.312]", "1.6% [Table 1 to §__.209]", "Unchanged"],
  ["GIRR 2Y / 3Y", "1.3% / 1.2% [ERBA P.312]", "1.3% / 1.2% [Table 1 to §__.209]", "Unchanged"],
  ["GIRR 5Y-30Y", "1.1% [ERBA P.312]", "1.1% (10 vertices: 0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30Y); divide by sqrt(2) for USD, AUD, CAD, EUR, JPY, SEK, GBP [§__.208-209]", "Unchanged"],
  ["GIRR inflation", "1.6% [ERBA P.314]", "1.6% (inflation and cross-currency basis) [Table 1 to §__.209]", "Unchanged"],
  ["FX risk weight", "15% all pairs [ERBA P.360]", "15%; divided by sqrt(2) for pairs formed from 19 specified currencies (USD, EUR, JPY, GBP, AUD, CAD, CHF, MXN, CNY, NZD, HKD, SGD, TRY, KRW, SEK, ZAR, INR, NOK, BRL) [§__.209; P.329 fn 376]", "Unchanged"],
  ["Equity large cap (liquid markets)", "30-50% by sector (Basel table; 2023 NPR not re-verified)", "30% / 35% / 40% / 50% (Table 8 buckets 5-8); emerging-market large cap 45-60% [Table 8 to §__.209]", "Unchanged (the 25% previously shown is not a Basel or NPR value)"],
  ["Equity small cap", "70% [ERBA P.340]", "70% emerging markets (bucket 9) / 50% liquid markets (bucket 10); other sector 70%; indices 15% / 25% [Table 8 to §__.209]", "Unchanged"],
  ["Vega risk weights", "100% (77.78% equity large cap) [2023 NPR; not re-verified]", "100% all classes except equity large cap & indices 77.78% [Table 11 to §__.209]", "Unchanged"],
]));
children.push(new Paragraph({ spacing: { before: 200 } }));

// ── SECTION 7: CVA RISK ──
children.push(...secTitle("7", "CVA Risk Framework"));
children.push(makeTable([
  ["CVA Scope & Approach"],
  ["Applicability", "Category I-IV banks [ERBA P.280]", "Cat I/II holding companies; their DI subsidiaries subject to market risk; other market-risk banks with OTC derivative notional >= $1 trillion (4-quarter average) [§__.201; Re-Proposal P.19, P.24]", "Scope narrowed to largest banks + $1T notional test"],
  ["$1T notional threshold", "Not in 2023 proposal [N/A]", "NEW: non-Cat I/II market-risk banks below $1T OTC notional are not subject to CVA capital; firms above it hold >98% of DIHC OTC exposure [§__.201; P.24]", "New de minimis threshold for smaller derivative books (CPI-W indexed)"],
  ["BA-CVA availability", "Single-name + index CDS hedges [2023 NPR; not re-verified]", "Eligible hedges: index CDS, single-name CDS and single-name contingent CDS, INCLUDING indirect single-name hedges (affiliate r=80%, same sector & region r=50%) [Re-Proposal P.443; Table 2 to §__.222]", "Hedge set EXPANDED vs current simple CVA; NOT narrowed to index-only"],
  ["SA-CVA availability", "Available with supervisory approval [ERBA P.290]", "Available with supervisory approval (standardized measure = SA-CVA + BA-CVA for carve-outs) [§__.220]", "Unchanged"],
  ["BA-CVA formula", "beta=0.25, rho=0.50 [ERBA P.286]", "K = 0.65 x (0.25 K_unhedged + 0.75 K_hedged); rho = 50%; SCVA = (1/alpha) x RW x M x EAD x DF, DF = (1-e^(-0.05M))/(0.05M); alpha 1.4 (1.0 commercial end-users) [§__.222]", "Unchanged core parameters"],
  ["BA-CVA risk weights", "By rating [2023 NPR; not re-verified]", "By sector x credit quality (IG / spec / sub-spec): sovereigns 0.5/3.0/7.0%; PSE 1.0/4.0%; financials 5.0/12.0%; basic materials 3.0/7.0%; consumer 3.0/8.5%; tech 2.0/5.5%; health 1.5/5.0%; other 5.0/12.0% [Table 1 to §__.222]", "No external ratings"],
  ["SA-CVA sensitivities", "10 buckets, delta+vega [ERBA P.292]", "6 delta risk classes (IR, FX, counterparty CS [8 buckets], reference CS [17 buckets], equity, commodity); 5 vega classes; m_CVA = 1.0; hedging disallowance R = 0.01; FX RW 11%; IR specified-currency RWs 1.11/0.93/0.74/0.74/0.74% [§__.224]", "Counterparty CS sovereign/PSE buckets merged; index bucket correlation raised to 70% (P.491-493)"],
  ["CVA Exemptions"],
  ["Client-cleared derivatives", "Not exempt [ERBA P.296]", "EXCLUDED: cleared transactions and client-facing derivative transactions are not CVA risk covered positions [Re-Proposal P.439-441]", "ISDA/SIFMA est. ~9% CVA RWA reduction vs 2023 proposal (P.538)"],
  ["FX transactions <=T+2", "Exempt (2023 NPR; not re-verified)", "Not addressed in the NPR (no FX settlement exemption in the covered-position definition) [§__.202]", "Claim of an FX exemption is not supported by the NPR text"],
  ["SFTs", "Included if material (2023 NPR; not re-verified)", "Not CVA risk covered positions (definition covers derivative contracts only) [Re-Proposal P.440]", "SFTs outside CVA scope"],
  ["Pension fund transactions", "Exempt (2023 NPR; not re-verified)", "No pension fund exemption in the NPR", "US has no pension CVA carve-out (unlike EU CRR3)"],
  ["Intra-group", "Not exempt [ERBA P.296]", "No intra-group exemption in the NPR", "Claim of an intra-group exemption is not supported by the NPR text"],
  ["Credit derivatives used as CRM", "Not addressed (2023 NPR; not re-verified)", "Bank MAY exclude an eligible credit derivative recognized as CRM from the CVA calculation [Re-Proposal P.439]", "Optional carve-out"],
]));
children.push(new Paragraph({ spacing: { before: 200 } }));

// ── SECTION 8: G-SIB SURCHARGE ──
children.push(...secTitle("8", "G-SIB Surcharge Recalibration (separate G-SIB surcharge NPR - not verified in this review)"));
children.push(makeTable([
  ["G-SIB Methodology Changes (per separate Board G-SIB surcharge NPR; the ERBA NPR only cross-references it, P.21)"],
  ["Method 2 coefficient", "Standard coefficient [ERBA P.42]", "1.2x downward adjustment [separate G-SIB NPR; model assumption, not verified]", "Systematic reduction of Method 2 scores"],
  ["STWF weight in Method 2", "30% [ERBA P.46]", "20% [separate G-SIB NPR; model assumption, not verified]", "Reduced weight on short-term wholesale funding"],
  ["STWF coefficient", "Pre-existing value [ERBA P.46]", "Not specified in the ERBA NPR (impact analysis uses an STWF scaling factor of 350, P.552); see separate G-SIB NPR - not verified", "Previously cited specific coefficient value removed as unsupported by the ERBA NPR"],
  ["Score band width", "100bp per band [ERBA P.48]", "20bp per band [separate G-SIB NPR; not verified]. ERBA impact analysis linearizes the surcharge as 0.01 + 0.00005 x max(0, score - 180) [P.552]", "5x MORE GRANULAR: finer distinction between G-SIBs"],
  ["Surcharge increment", "0.5% per band [ERBA P.48]", "0.1% per band [separate G-SIB NPR; not verified]", "5x SMALLER increments: smoother surcharge curve"],
  ["Score averaging", "Quarter-end snapshot [ERBA P.50]", "Not addressed in ERBA NPR; see separate G-SIB NPR (not verified)", "Reduces window-dressing incentives (if adopted)"],
  ["GDP indexing", "None [ERBA P.50]", "Not addressed in ERBA NPR; see separate G-SIB NPR (not verified)", "Prevents scores inflating purely from economic growth (if adopted)"],
  ["Overall aggregate impact", "No change to surcharges [ERBA P.42]", "ERBA NPR + G-SIB surcharge proposal combined: -2.4% CET1 requirement for Cat I/II BHCs; risk-weight + G-SIB changes lower CET1 minimum-plus-buffer requirements by $42.1B [Re-Proposal Table VII.3, P.583]", "The aggregate reduction figure previously shown is not in the ERBA NPR"],
  ["Worked Example: Hypothetical G-SIB (illustrative; band mapping per model assumptions, not verified against the G-SIB NPR)"],
  ["Method 1 raw score", "250bp [Example]", "250bp (unchanged) [Example]", "Method 1 unchanged in this example"],
  ["Method 2 raw score", "300bp [Example]", "300bp / 1.2 = 250bp [Example]", "1.2x factor reduces Method 2 score"],
  ["2023 surcharge (100bp bands)", "Band 2 (200-300bp) = 2.0% [2023 calc]", "N/A [N/A]", "Old: coarse 0.5% jumps"],
  ["2026 surcharge (20bp bands)", "N/A [N/A]", "Band 6 (230-250bp) = 1.5% [2026 calc]", "New: fine 0.1% increments may yield lower surcharge"],
  ["Binding surcharge", "Max(M1,M2) = 2.0% [2023]", "Max(M1,M2) = 1.5% [2026]", "50bp REDUCTION for this hypothetical G-SIB"],
  ["CET1 impact ($1.5T RWA)", "$30B surcharge CET1 [2023]", "$22.5B surcharge CET1 [2026]", "$7.5B CET1 relief for this institution"],
]));
children.push(new Paragraph({ spacing: { before: 200 } }));

// ── SECTION 9: OTHER CHANGES ──
children.push(...secTitle("9", "Securitization, CRM, Equity & Other Changes"));
children.push(makeTable([
  ["Securitization"],
  ["Hierarchy", "SEC-SA only (no IRB, no ext ratings) [ERBA P.400]", "SEC-SA only: p = 0.5 (1.5 resecuritization); RW floor 15% (100% resecuritization and NPL securitizations); 1,250% maximum; K_A = (1-W) K_G + 0.5 W [§__.132-133]", "Unchanged: US uses neither SEC-ERBA nor SEC-IRBA ('ERBA' in the NPR = expanded risk-based approach)"],
  ["Look-through / NPL", "Not addressed (2023 NPR; not re-verified)", "Senior non-resec look-through: max(15%, weighted-average RW of underlyings); NPL senior tranche 100% if non-refundable purchase price discount >= 50% [§__.132; P.178-183]", "New senior look-through and NPL treatments"],
  ["STS framework", "Not adopted [ERBA P.402]", "Not adopted (no STC/STS preferential p or floor) [§__.133]", "US does not implement STS (unlike UK/EU)"],
  ["Risk retention", "5% [Regulation RR / Dodd-Frank §941 - not part of the capital NPR]", "5% [Regulation RR / Dodd-Frank §941 - not part of the capital NPR]", "Unchanged; governed by separate rule"],
  ["1250% RW cap", "Retained [ERBA P.412]", "Retained; also applied where due diligence fails or SEC-SA cannot be applied; CEIO strips deducted from CET1 [§__.131-133; P.162, P.180]", "Unchanged"],
  ["Credit Risk Mitigation"],
  ["E* formula", "max(0, E*(1+He)-C*(1-Hc-Hfx)) [ERBA P.200]", "NEW netting-set formula: E* = max(0, (sum E_i - sum C_i) + 0.4 x net exposure + 0.6 x gross exposure / sqrt(N) + sum E_fx x H_fx) [§__.115; P.103-105]", "Portfolio-level haircut formula replaces single-transaction form; own-estimate haircuts no longer permitted"],
  ["Supervisory haircuts", "17-entry table [ERBA P.205]", "Revised Table 1 to §__.115: IG debt by issuer type & residual maturity (0.5%-24%); main-index equities & gold 20%; other equities 30%; other 30% [§__.115; P.106-109]", "Haircuts keyed to residual maturity rather than rating buckets"],
  ["Currency mismatch", "8% add-on [ERBA P.210]", "8% (scaled by sqrt(T_M/10) if revalued less than every 10 business days) [§__.120-121; P.147]", "Unchanged"],
  ["Maturity mismatch", "(t-0.25)/(T-0.25) formula [ERBA P.212]", "Pm = E x (t-0.25)/(T-0.25); mitigant original maturity >= 1Y, residual > 3 months [§__.120; P.146]", "Unchanged"],
  ["Equity Changes"],
  ["Phase-in", "Immediate full application [ERBA P.160]", "Immediate full application [§__.141]", "US: no phase-in (unlike EU Art 495a)"],
  ["Non-significant equity", "Proposed 250% (remove 100%) [ERBA P.162]", "100% RETAINED (aggregate equity <= 10% of total capital) [§__.141; P.191]", "Industry successfully pushed back on 100% removal"],
  ["Community dev equity", "100% [ERBA P.164]", "100% [§__.141]", "CRA-qualifying investments unchanged"],
  ["Covered Bonds"],
  ["Covered bond treatment", "Not recognized [ERBA P.135]", "Not recognized in the credit-risk SA (bank-exposure RW applies); 'covered bond' defined only for market risk (CSR buckets 8/16; DRC LGD 25%) [§__.202, §__.209-210]", "US has no covered bond framework in credit risk (unlike EU/UK)"],
]));
children.push(new Paragraph({ spacing: { before: 200 } }));

// ── SECTION 10: COLLINS AMENDMENT ──
children.push(...secTitle("10", "Collins Amendment & SA Floor"));
children.push(makeTable([
  ["Collins Amendment Implications"],
  ["Statutory basis", "Dodd-Frank Act Section 171 [12 USC 5371]", "Same statutory basis [12 USC 5371]", "Collins Amendment applies to both proposals"],
  ["SA as floor", "SA retained as minimum capital floor [ERBA P.95]", "SA retained as minimum capital floor [Re-Proposal P.95]", "Banks must always meet SA-based capital requirements"],
  ["Dual stack eliminated", "IRB-based capital calculations eliminated [ERBA P.95]", "IRB-based calculations eliminated [Re-Proposal P.95]", "Consistent: SA is sole RWA methodology"],
  ["Output floor", "N/A (no IRB = no floor needed) [N/A]", "N/A (no IRB = no floor needed) [N/A]", "72.5% output floor moot since IRB eliminated"],
  ["International comparison", "US departs from BCBS by eliminating IRB entirely", "Same departure maintained", "BCBS retains IRB + 72.5% floor; US uses SA only"],
  ["Rationale", "Reduce complexity and model risk [ERBA P.96]", "Same rationale maintained [Re-Proposal P.96]", "Consistent policy: SA is simpler and more transparent"],
  ["Impact on G-SIBs", "G-SIBs must rebuild SA infrastructure [Industry]", "Same requirement [Industry]", "G-SIBs previously relied heavily on IRB models"],
]));
children.push(new Paragraph({ spacing: { before: 200 } }));

// ── SECTION 11: SUMMARY TABLE ──
children.push(...secTitle("11", "Capital Impact Summary: Component-by-Component"));
children.push(makeTable([
  ["Component-Level Impact Summary"],
  ["Scope: # institutions", "~37 BHCs", "~9 BHCs", "76% fewer institutions, MASSIVE reduction"],
  ["Aggregate CET1 impact", "+19% (Barr speech)", "+1.4% standalone (BHCs); -4.8% cumulative with G-SIB and stress-test proposals (NPR Table VII.1/VII.3)", "REVERSAL of direction"],
  ["Total RWA", "+~$725B (industry est.)", "+1.9%: $7,673B -> $7,820B (NPR Table VII.5)", "Near-neutral RWA; market RWA +20%, CVA requirement +96%, credit -10%, op risk +14.9%"],
  ["G-SIB surcharge", "Unchanged", "Separate G-SIB NPR (not verified); combined with ERBA: -2.4% CET1", "Direct capital relief for 8 G-SIBs"],
  ["Retail transactor RW", "55%", "45%", "10pp reduction benefits credit card portfolios"],
  ["Retail regulatory / other", "85% / 110%", "75% / 100%", "10pp reduction (NPR P.534)"],
  ["Resi RE LTV <=50%", "40%", "20%", "20pp reduction: Basel table adopted (NPR P.533)"],
  ["Resi RE 80-90% LTV", "60%", "40%", "20pp reduction for high-LTV mortgages"],
  ["Resi RE >100% LTV", "90%", "70%", "20pp reduction for underwater mortgages"],
  ["CRE ADC non-HVCRE", "150%", "100%", "50pp reduction for qualifying ADC loans"],
  ["MSA treatment", "CET1 deduction", "250% RW", "Deduction removed, replaced with risk weight"],
  ["Equity publicly traded", "250% (not re-verified)", "300% (current rule retained)", "US keeps 300%; Basel 250% not adopted"],
  ["Equity non-significant", "250% (proposed)", "100% (retained)", "Industry lobbied successfully to retain 100%"],
  ["OBS commitments (non-UCC)", "40% (not re-verified)", "40% uniform", "Unchanged vs 2023; vs CURRENT rule 20% (<=1Y) / 50% (>1Y)"],
  ["ILM for OpRisk", "Included (floored at 1; not re-verified)", "None: RWA = 12.5 x BIC", "ILM removed; operational losses enter BI instead"],
  ["Loss data", "Required ($20K)", "Still required ($20K, 10Y); losses added to BI", "Loss data still matters"],
  ["BI structure", "ILDC + SC + FC", "ILDC + noninterest component", "Two components (NPR P.535)"],
  ["NIC investment mgmt", "Gross basis", "0.7x NET (inv. mgmt + inv. services + non-lending treasury)", "Reduces BI for fee-based businesses"],
  ["FRTB threshold", "$1B", "$5B (4Q avg) or 10% of assets", "Fewer non-Cat I/II banks subject to FRTB"],
  ["CVA scope", "Cat I-IV", "Cat I-II + $1T OTC notional test", "Substantially narrowed"],
  ["CVA exemptions", "Limited", "Cleared and client-facing derivatives excluded; SFTs not covered", "No pension, intra-group or FX settlement exemptions in NPR"],
  ["G-SIB Method 2 coeff", "Standard", "/1.2x downward (separate NPR; not verified)", "Systematic score reduction"],
  ["G-SIB STWF weight", "30%", "20% (separate NPR; not verified)", "10pp reduction"],
  ["G-SIB band width", "100bp", "20bp (separate NPR; not verified)", "5x more granular"],
  ["G-SIB increment", "0.5%", "0.1% (separate NPR; not verified)", "5x smaller steps"],
  ["G-SIB averaging", "Quarter-end", "Not in ERBA NPR (separate NPR; not verified)", "Reduces window-dressing (if adopted)"],
  ["Bank RW system", "Grade A/B/C 40/75/150% (not re-verified)", "Grade A 30% (§__.111(d)(2)) / 40%, B 75%, C 150%", "New 30% tier for strongly capitalized banks"],
  ["BA-CVA hedges", "SN + Index CDS", "SN (incl. indirect SN) + Index CDS", "Not narrowed"],
  ["$1T CVA exemption", "None", "NEW threshold", "De minimis for smaller derivative books"],
  ["SA for Cat III-IV", "Mandatory", "Optional opt-in", "Banks can choose current or new rules"],
  ["FDIC vote", "3-2 partisan", "Unanimous", "Bipartisan consensus achieved"],
  ["Industry reaction", "Fierce opposition", "Broadly supportive", "180-degree shift"],
  ["Formal status", "RESCINDED", "Active proposal", "2023 NPR formally withdrawn"],
]));
children.push(new Paragraph({ spacing: { before: 200 } }));

// ── SECTION 12: INDUSTRY REACTION ──
children.push(...secTitle("12", "Governance, Voting & Industry Reaction"));
children.push(makeTable([
  ["Regulatory Process"],
  ["Federal Reserve Board vote", "6-1 (Barr FOR more capital) [Fed minutes Jul 2023]", "6-1 (Barr SOLE DISSENT against lower capital) [Fed minutes Mar 2026]", "Barr: only governor to oppose BOTH directions"],
  ["FDIC vote", "3-2 (partisan split) [FDIC Jul 2023]", "Unanimous [FDIC Mar 2026]", "Achieved bipartisan consensus"],
  ["OCC vote", "Unanimous approval [OCC Jul 2023]", "Unanimous approval [OCC Mar 2026]", "OCC consistent"],
  ["Comment letters received", "~97 letters [Fed docket]", "Pending [Fed docket]", "2023 drew historic number of opposition letters"],
  ["Bank lobbying", "Massive multi-million dollar campaign [Public records]", "Minimal opposition [Public records]", "Industry satisfied with recalibration"],
  ["Congressional hearings", "Multiple hearings, bipartisan criticism [Congressional record]", "Supportive testimony expected [Congressional record]", "Congress pressured Fed to reconsider 2023 NPR"],
  ["Barr Sept 2024 speech", "Announced broad recalibration [Fed.gov]", "Preceded this re-proposal [Fed.gov]", "Signaled 2023 NPR would be substantially revised"],
  ["Key Barr quote (2024)", "'Changes to ensure strength and vibrancy of banking system'", "N/A", "Acknowledged industry concerns about competitiveness"],
  ["Formal rescission", "2023 NPR formally rescinded [Fed Sept 2024]", "N/A (this IS the replacement)", "Clean break: new proposal, not an amendment"],
  ["Bipartisan support", "Lacked bipartisan support [Political analysis]", "Strong bipartisan support [Political analysis]", "Key factor in achieving 6-1 supermajority"],
]));

// ── SAVE DOCUMENT ──
const doc = new Document({
  sections: [{
    properties: {
      page: {
        size: { orientation: PageOrientation.LANDSCAPE, width: convertInchesToTwip(11), height: convertInchesToTwip(8.5) },
        margin: { top: convertInchesToTwip(0.6), bottom: convertInchesToTwip(0.5), left: convertInchesToTwip(0.5), right: convertInchesToTwip(0.5) },
      },
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buffer => {
  const outDir = "/home/user/BASEL-III-Endgame/output";
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(outDir + "/NPR_2023_vs_2026_Comparison.docx", buffer);
  console.log("SUCCESS: NPR_2023_vs_2026_Comparison.docx generated");
  console.log("Size:", (buffer.length / 1024).toFixed(1), "KB");
}).catch(err => { console.error("ERROR:", err); process.exit(1); });
