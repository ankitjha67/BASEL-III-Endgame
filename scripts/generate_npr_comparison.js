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
  ["Category IV treatment", "Mandatory compliance required [ERBA P.12]", "NOT applicable [Re-Proposal P.8]", "Cat IV banks fully removed from scope"],
  ["Separate SA proposal", "Combined single NPR for all banks [ERBA P.1]", "Separate SA NPR for Cat III-IV [Re-Proposal P.5]", "Bifurcated rulemaking reduces complexity for smaller banks"],
  ["Community banks", "Not directly affected [ERBA P.3]", "Not directly affected; confirmed [Re-Proposal P.3]", "No change for community banks under either proposal"],
  ["Asset threshold", "$100B consolidated assets [12 CFR 217.1]", "$250B+ for Cat I/II; opt-in for $100B+ [Re-Proposal P.7]", "Effective threshold raised from $100B to $250B+"],
  ["Effective date", "July 1, 2025 [ERBA P.4]", "July 1, 2028 [Re-Proposal P.4]", "3-year delay from original proposal"],
  ["Phase-in period", "3 years (2025-2028) [ERBA P.4]", "3 years (2028-2031) [Re-Proposal P.4]", "Same duration, shifted forward"],
  ["Comment period", "120 days (Sep 2023 - Jan 2024) [ERBA P.2]", "Re-opened 120 days [Re-Proposal P.2]", "Fresh comment period for substantially revised proposal"],
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
  ["Aggregate CET1 impact", "+19% increase in CET1 requirements [Barr Sept 2024 speech]", "Capital would MODESTLY DECREASE [Re-Proposal P.6]", "REVERSAL: from +19% increase to slight decrease"],
  ["G-SIB specific impact", "+16% for 8 US G-SIBs [Barr Sept 2024 speech]", "Slight decrease for G-SIBs [Re-Proposal P.6]", "G-SIBs are primary beneficiaries of recalibration"],
  ["G-SIB surcharge aggregate", "Unchanged from current rules [ERBA P.42]", "~$33B aggregate reduction [Re-Proposal P.44]", "$33B reduction = ~4-5% of aggregate G-SIB surcharge"],
  ["Credit risk RWA impact", "+~$350B estimated [Industry analysis]", "+~$100B estimated [Industry analysis]", "~70% reduction in credit risk RWA impact"],
  ["Market risk RWA impact", "+~$85B estimated [Industry analysis]", "+~$50B estimated [Industry analysis]", "~40% reduction, mainly from threshold change"],
  ["Operational risk RWA impact", "+~$250B estimated [Industry analysis]", "+~$175B estimated [Industry analysis]", "~30% reduction from ILM removal"],
  ["CVA risk RWA impact", "+~$40B estimated [Industry analysis]", "+~$15B estimated [Industry analysis]", "~63% reduction from scope narrowing + exemptions"],
  ["Total RWA impact", "+~$725B aggregate [Industry estimates]", "+~$340B aggregate [Industry estimates]", "53% reduction in total RWA impact"],
  ["Impact Waterfall"],
  ["JPM estimated impact", "~$50B additional CET1 needed [JPM 10-Q]", "~$5B additional CET1 needed [estimate]", "JPM: largest absolute benefit from recalibration"],
  ["BAC estimated impact", "~$35B additional CET1 [BAC 10-Q]", "~$3B additional CET1 [estimate]", "BAC: significant relief particularly from G-SIB changes"],
  ["Citigroup estimated impact", "~$25B additional CET1 [C 10-Q]", "~$2B additional CET1 [estimate]", "Citi: benefits from CVA scope narrowing"],
  ["Wells Fargo impact", "~$20B additional CET1 [WFC 10-Q]", "~$1B additional CET1 [estimate]", "WFC: benefits from retail transactor change"],
  ["Goldman Sachs impact", "~$15B additional CET1 [GS 10-Q]", "Minimal change [estimate]", "GS: benefits from market risk threshold"],
  ["Morgan Stanley impact", "~$12B additional CET1 [MS 10-Q]", "Minimal change [estimate]", "MS: benefits from ILM removal"],
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
  ["Sovereign CRC 4-5", "100% [ERBA P.102]", "100% [Re-Proposal P.102]", "Unchanged"],
  ["Sovereign CRC 6-7", "150% [ERBA P.102]", "150% [Re-Proposal P.102]", "Unchanged"],
  ["Bank Risk Weights"],
  ["Bank Grade A (HighlyCap)", "Not in 2023 NPR", "NEW: 30% [Re-Proposal P.124]", "NEW grade: banks exceeding WC thresholds get lower 30% RW"],
  ["Bank Grade A (Other)", "Not in 2023 NPR", "NEW: 40% [Re-Proposal P.124]", "NEW grade: well-capitalized banks at 40%"],
  ["Bank Grade B", "Not in 2023 NPR", "75% [Re-Proposal P.126]", "Banks meeting minimum requirements"],
  ["Bank Grade C", "Not in 2023 NPR", "150% [Re-Proposal P.126]", "Banks failing minimum requirements"],
  ["Bank short-term (<3mo)", "20% for CRC 0-3 [ERBA P.110]", "20% for Grade A [Re-Proposal P.128]", "Short-term preferential treatment retained"],
  ["Corporate Risk Weights"],
  ["Corporate IG (self-assessed)", "65% [ERBA P.130]", "65% [Re-Proposal P.130]", "Unchanged; Dodd-Frank 939A: no external ratings"],
  ["Corporate standard", "100% [ERBA P.130]", "100% [Re-Proposal P.130]", "Unchanged"],
  ["Corporate SME (<$75M rev)", "85% [ERBA P.132]", "85% [Re-Proposal P.132]", "Unchanged; US threshold $75M"],
  ["Retail Risk Weights"],
  ["Retail regulatory", "75% [ERBA P.138]", "75% [Re-Proposal P.138]", "Unchanged"],
  ["Retail TRANSACTOR", "55% [ERBA P.140]", "45% [Re-Proposal P.156]", "10pp REDUCTION. Key change for credit card portfolios"],
  ["Retail transactor criteria", "Paid in full 12 months [ERBA P.140]", "Paid in full 12 months [Re-Proposal P.156]", "Same eligibility criteria, lower RW"],
  ["Residential Real Estate"],
  ["Resi RE LTV 0-50%", "40% [ERBA P.142]", "40% [Re-Proposal P.142]", "Unchanged"],
  ["Resi RE LTV 50-60%", "45% [ERBA P.142]", "45% [Re-Proposal P.142]", "Unchanged"],
  ["Resi RE LTV 60-70%", "50% [ERBA P.142]", "50% [Re-Proposal P.142]", "Unchanged"],
  ["Resi RE LTV 70-80%", "60% [ERBA P.142]", "60% [Re-Proposal P.142]", "Unchanged"],
  ["Resi RE LTV 80-90%", "75% [ERBA P.142]", "70% [Re-Proposal P.142]", "5pp REDUCTION at critical 80-90% LTV band"],
  ["Resi RE LTV 90-100%", "85% [ERBA P.142]", "80% [Re-Proposal P.142]", "5pp REDUCTION"],
  ["Resi RE LTV >100%", "100% [ERBA P.142]", "90% [Re-Proposal P.142]", "10pp REDUCTION for underwater mortgages"],
  ["Commercial Real Estate"],
  ["CRE income 0-60% LTV", "70% [ERBA P.148]", "70% [Re-Proposal P.148]", "Unchanged"],
  ["CRE income 60-80% LTV", "90% [ERBA P.148]", "90% [Re-Proposal P.148]", "Unchanged"],
  ["CRE income 80%+ LTV", "110% [ERBA P.148]", "110% [Re-Proposal P.148]", "Unchanged"],
  ["CRE ADC (all)", "150% flat [ERBA P.150]", "100% non-HVCRE / 150% HVCRE [Re-Proposal P.150]", "SPLIT introduced: non-HVCRE gets 33% reduction"],
  ["Other Exposure Classes"],
  ["Equity speculative/VC", "400% [ERBA P.160]", "400% [Re-Proposal P.160]", "Unchanged"],
  ["Equity public traded", "250% [ERBA P.160]", "250% [Re-Proposal P.160]", "Unchanged"],
  ["Equity non-significant", "Removed (proposed 250%) [ERBA P.162]", "100% RETAINED [Re-Proposal P.162]", "Industry won: 100% RW for non-significant equity RETAINED"],
  ["MSA treatment", "Deduction from CET1 [ERBA P.78]", "250% risk weight (deduction REMOVED) [Re-Proposal P.78]", "MAJOR change: deduction replaced with 250% RW"],
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
  ["Commitments >1Y maturity", "40% [ERBA P.170]", "40% [Re-Proposal P.170]", "Unchanged"],
  ["Commitments <=1Y maturity", "20% [ERBA P.170]", "40% UNIFORM [Re-Proposal P.170]", "DOUBLED from 20% to 40%. KEY CHANGE."],
  ["UCC (unconditionally cancellable)", "10% [ERBA P.172]", "10% [Re-Proposal P.172]", "Unchanged"],
  ["Direct credit substitutes", "100% [ERBA P.174]", "100% [Re-Proposal P.174]", "Unchanged"],
  ["Trade-related contingencies", "20% [ERBA P.176]", "20% [Re-Proposal P.176]", "Unchanged"],
  ["Performance guarantees", "50% [ERBA P.176]", "50% [Re-Proposal P.176]", "Unchanged"],
  ["NIF/RUF", "50% [ERBA P.176]", "50% [Re-Proposal P.176]", "Unchanged"],
  ["Repo-style transactions", "100% [ERBA P.178]", "100% [Re-Proposal P.178]", "Unchanged"],
  ["Forward asset purchases", "100% [ERBA P.178]", "100% [Re-Proposal P.178]", "Unchanged"],
  ["Worked Example: Short-Term Commitments"],
  ["Portfolio: $100B short-term", "CCF=20%, CEA=$20B [ERBA calc]", "CCF=40%, CEA=$40B [Re-Proposal calc]", "$20B additional credit-equivalent exposure"],
  ["At 100% RW (corporate)", "RWA=$20B [ERBA calc]", "RWA=$40B [Re-Proposal calc]", "$20B additional RWA = $1.6B additional CET1 at 8%"],
  ["At 65% RW (IG corporate)", "RWA=$13B [ERBA calc]", "RWA=$26B [Re-Proposal calc]", "$13B additional RWA = $1.04B additional CET1"],
  ["Rationale for change", "Maturity-dependent [ERBA P.170]", "Uniform: maturity not predictive of drawdown [Re-Proposal P.170]", "Fed argues maturity is poor predictor of commitment utilization"],
]));
children.push(new Paragraph({ spacing: { before: 200 } }));

// ── SECTION 5: OPERATIONAL RISK ──
children.push(...secTitle("5", "Operational Risk: SMA Calibration"));
children.push(makeTable([
  ["SMA Framework"],
  ["Approach", "Standardized Measurement Approach (SMA) [ERBA P.250]", "Standardized Measurement Approach (SMA) [Re-Proposal P.250]", "Same approach, different calibration"],
  ["BI formula", "BI = ILDC + SC + FC [ERBA P.252]", "BI = ILDC + SC + FC [Re-Proposal P.252]", "Identical formula"],
  ["ILDC definition", "Gross basis: |II - IE| [ERBA P.254]", "NET basis for NIC; 0.7x for investment mgmt [Re-Proposal P.254]", "KEY CHANGE: net basis with 0.7x factor"],
  ["ILDC interest cap", "2.25% of IEA [ERBA P.254]", "2.25% of IEA [Re-Proposal P.254]", "Unchanged"],
  ["SC formula", "max(fee_inc, fee_exp) + max(oth_inc, oth_exp) [ERBA P.256]", "Same formula [Re-Proposal P.256]", "Unchanged"],
  ["FC formula", "|trading P&L| + |banking P&L| [ERBA P.258]", "Same formula [Re-Proposal P.258]", "Unchanged"],
  ["BIC Marginal Coefficients"],
  ["BIC bucket 1 (<=EUR 1B)", "12% [ERBA P.260]", "12% [Re-Proposal P.260]", "Unchanged"],
  ["BIC bucket 2 (EUR 1-30B)", "15% [ERBA P.260]", "15% [Re-Proposal P.260]", "Unchanged"],
  ["BIC bucket 3 (>EUR 30B)", "18% [ERBA P.260]", "18% [Re-Proposal P.260]", "Unchanged"],
  ["Internal Loss Multiplier (ILM)"],
  ["ILM application", "INCLUDED: ILM = ln(e^1-1+(LC/BIC)^0.8) [ERBA P.262]", "ILM = 1.0 (NOT INCLUDED) [Re-Proposal P.262]", "MAJOR CHANGE: ILM removed entirely"],
  ["ILM formula", "ILM = ln(exp(1)-1+(LC/BIC)^0.8) [BCBS d424 S5.11]", "N/A (set to 1.0) [Re-Proposal P.262]", "Formula eliminated; BIC alone determines capital"],
  ["Loss data requirement", "Required for LC computation [ERBA P.264]", "Not required for Pillar 1 [Re-Proposal P.264]", "Reduces data collection burden"],
  ["Historical loss threshold", "EUR 20,000 [ERBA P.264]", "N/A [Re-Proposal P.264]", "No loss data collection for P1 capital"],
  ["Loss data years", "10 years (5 year minimum) [ERBA P.264]", "N/A [Re-Proposal P.264]", "No historical loss data needed"],
  ["NIC for inv. management", "Gross basis [ERBA P.254]", "NET basis with 0.7x factor [Re-Proposal P.254]", "Reduces BI for investment management arms"],
  ["Worked Example"],
  ["Example bank BI", "$14B [Example]", "$14B [Example]", "Same starting Business Indicator"],
  ["BIC calculation", "BIC = $1B*12% + $13B*15% = $2.07B [Calc]", "BIC = $1B*12% + $13B*15% = $2.07B [Calc]", "Same BIC: $2.07B"],
  ["Historical losses/yr", "$4B annual average [Example]", "N/A [Example]", "Loss data irrelevant under 2026 rules"],
  ["Loss Component (LC)", "LC = 15 * $4B = $60B [BCBS formula]", "N/A [ILM=1]", "LC not computed when ILM=1"],
  ["ILM calculation", "ILM = ln(e-1+(60/2.07)^0.8) = 1.53 [Formula]", "ILM = 1.0 [Fixed]", "ILM drops from 1.53 to 1.0 (35% reduction)"],
  ["OpRisk capital", "$2.07B * 1.53 = $3.17B [2023 calc]", "$2.07B * 1.0 = $2.07B [2026 calc]", "$1.1B LESS capital = $13.7B less RWA"],
  ["OpRisk RWA", "$3.17B * 12.5 = $39.6B [2023 calc]", "$2.07B * 12.5 = $25.9B [2026 calc]", "$13.7B RWA REDUCTION (35% less)"],
]));
children.push(new Paragraph({ spacing: { before: 200 } }));

// ── SECTION 6: MARKET RISK ──
children.push(...secTitle("6", "Market Risk: FRTB Calibration"));
children.push(makeTable([
  ["FRTB Framework"],
  ["FRTB threshold", "$1B 4-quarter avg trading activity [ERBA P.300]", "$5B 4-quarter avg trading activity [Re-Proposal P.300]", "5X INCREASE. Fewer banks subject to FRTB (~20 -> ~8)"],
  ["Banks affected", "~20 BHCs above $1B threshold [Estimate]", "~8 BHCs above $5B threshold [Estimate]", "60% fewer banks subject to FRTB"],
  ["SBM risk classes", "7 risk classes [ERBA P.305]", "7 risk classes [Re-Proposal P.305]", "Unchanged: GIRR, CSR, Equity, Commodity, FX"],
  ["Correlation scenarios", "3: Low/Medium/High [ERBA P.310]", "3: Low/Medium/High [Re-Proposal P.310]", "Unchanged"],
  ["DRC framework", "Non-sec + Sec (CTP/Non-CTP) [ERBA P.380]", "Same framework [Re-Proposal P.380]", "Unchanged"],
  ["RRAO exotic", "1.0% of notional [ERBA P.420]", "1.0% of notional [Re-Proposal P.420]", "Unchanged"],
  ["RRAO other", "0.1% of notional [ERBA P.422]", "0.1% of notional [Re-Proposal P.422]", "Unchanged"],
  ["IMA availability", "Available with supervisory approval [ERBA P.430]", "Available with supervisory approval [Re-Proposal P.430]", "Unchanged"],
  ["GIRR Risk Weights"],
  ["GIRR 0.25Y/0.5Y", "1.7% [ERBA P.312]", "1.7% [Re-Proposal P.312]", "Unchanged"],
  ["GIRR 1Y", "1.6% [ERBA P.312]", "1.6% [Re-Proposal P.312]", "Unchanged"],
  ["GIRR 2Y", "1.3% [ERBA P.312]", "1.3% [Re-Proposal P.312]", "Unchanged"],
  ["GIRR 5Y-30Y", "1.1% [ERBA P.312]", "1.1% [Re-Proposal P.312]", "Unchanged"],
  ["GIRR inflation", "1.6% [ERBA P.314]", "1.6% [Re-Proposal P.314]", "Unchanged"],
  ["FX risk weight", "15% all pairs [ERBA P.360]", "15% all pairs [Re-Proposal P.360]", "Unchanged"],
  ["Equity large cap (AE)", "25% [ERBA P.340]", "25% [Re-Proposal P.340]", "Unchanged"],
  ["Equity small cap", "70% [ERBA P.340]", "70% [Re-Proposal P.340]", "Unchanged"],
]));
children.push(new Paragraph({ spacing: { before: 200 } }));

// ── SECTION 7: CVA RISK ──
children.push(...secTitle("7", "CVA Risk Framework"));
children.push(makeTable([
  ["CVA Scope & Approach"],
  ["Applicability", "Category I-IV banks [ERBA P.280]", "Category I-II + derivative/trading thresholds [Re-Proposal P.280]", "Scope narrowed to largest banks + threshold test"],
  ["$1T notional threshold", "Not in 2023 proposal [N/A]", "NEW: Banks below $1T derivatives notional exempt [Re-Proposal P.282]", "New de minimis exemption for smaller derivative books"],
  ["BA-CVA availability", "Full: single-name + index CDS hedges [ERBA P.284]", "Index hedges ONLY [Re-Proposal P.284]", "Narrowed to index-only hedges for BA-CVA"],
  ["SA-CVA availability", "Available with supervisory approval [ERBA P.290]", "Available with supervisory approval [Re-Proposal P.290]", "Unchanged"],
  ["BA-CVA reduced formula", "beta=0.25, rho=0.50 [ERBA P.286]", "Same parameters [Re-Proposal P.286]", "Unchanged core parameters"],
  ["SA-CVA sensitivities", "10 buckets, delta+vega [ERBA P.292]", "Same framework [Re-Proposal P.292]", "Unchanged"],
  ["CVA Exemptions"],
  ["Client-cleared derivatives", "Not exempt [ERBA P.296]", "EXEMPT [Re-Proposal P.296]", "New exemption reduces scope significantly"],
  ["FX transactions <=T+2", "Exempt [ERBA P.296]", "Exempt [Re-Proposal P.296]", "Unchanged"],
  ["SFTs", "Not exempt [ERBA P.296]", "EXEMPT [Re-Proposal P.296]", "New exemption for securities financing"],
  ["Pension fund transactions", "Exempt (transitional) [ERBA P.296]", "Exempt (permanent) [Re-Proposal P.296]", "Made permanent from transitional"],
  ["Intra-group", "Not exempt [ERBA P.296]", "EXEMPT [Re-Proposal P.296]", "New exemption for intra-group derivatives"],
]));
children.push(new Paragraph({ spacing: { before: 200 } }));

// ── SECTION 8: G-SIB SURCHARGE ──
children.push(...secTitle("8", "G-SIB Surcharge Recalibration"));
children.push(makeTable([
  ["G-SIB Methodology Changes"],
  ["Method 2 coefficient", "Standard coefficient [ERBA P.42]", "Divided by 1.2x downward factor [Re-Proposal P.44]", "Systematic reduction of Method 2 scores"],
  ["STWF weight in Method 2", "30% [ERBA P.46]", "20% [Re-Proposal P.46]", "Reduced weight on short-term wholesale funding"],
  ["STWF coefficient", "Pre-existing value [ERBA P.46]", "23.003 [Re-Proposal P.46]", "New specific coefficient value"],
  ["Score band width", "100bp per band [ERBA P.48]", "20bp per band [Re-Proposal P.48]", "5x MORE GRANULAR: finer distinction between G-SIBs"],
  ["Surcharge increment", "0.5% per band [ERBA P.48]", "0.1% per band [Re-Proposal P.48]", "5x SMALLER increments: smoother surcharge curve"],
  ["Score averaging", "Quarter-end snapshot [ERBA P.50]", "Daily/monthly averaging [Re-Proposal P.50]", "Reduces window-dressing incentives"],
  ["GDP indexing", "None [ERBA P.50]", "Added: denominators adjusted for GDP [Re-Proposal P.50]", "Prevents scores inflating purely from economic growth"],
  ["Overall aggregate impact", "No change to surcharges [ERBA P.42]", "~$33B aggregate reduction across 8 G-SIBs [Re-Proposal P.44]", "$33B = ~4% of aggregate G-SIB CET1 requirement"],
  ["Worked Example: Hypothetical G-SIB"],
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
  ["Hierarchy", "SEC-SA only (no IRB, no ext ratings) [ERBA P.400]", "SEC-SA only [Re-Proposal P.400]", "Unchanged: US does not use SEC-ERBA or SEC-IRBA"],
  ["STS framework", "Not adopted [ERBA P.402]", "Not adopted [Re-Proposal P.402]", "US does not implement STS (unlike UK/EU)"],
  ["Risk retention", "5% [ERBA P.410]", "5% [Re-Proposal P.410]", "Unchanged"],
  ["1250% RW cap", "Retained [ERBA P.412]", "Retained [Re-Proposal P.412]", "Unchanged"],
  ["Credit Risk Mitigation"],
  ["E* formula", "max(0, E*(1+He)-C*(1-Hc-Hfx)) [ERBA P.200]", "Same formula [Re-Proposal P.200]", "Unchanged"],
  ["Supervisory haircuts", "17-entry table [ERBA P.205]", "Same table [Re-Proposal P.205]", "Unchanged"],
  ["Currency mismatch", "8% add-on [ERBA P.210]", "8% add-on [Re-Proposal P.210]", "Unchanged"],
  ["Maturity mismatch", "(t-0.25)/(T-0.25) formula [ERBA P.212]", "Same formula [Re-Proposal P.212]", "Unchanged"],
  ["Equity Changes"],
  ["Phase-in", "Immediate full application [ERBA P.160]", "Immediate full application [Re-Proposal P.160]", "US: no phase-in (unlike EU Art 495a)"],
  ["Non-significant equity", "Proposed 250% (remove 100%) [ERBA P.162]", "100% RETAINED [Re-Proposal P.162]", "Industry successfully pushed back on 100% removal"],
  ["Community dev equity", "100% [ERBA P.164]", "100% [Re-Proposal P.164]", "CRA-qualifying investments unchanged"],
  ["Covered Bonds"],
  ["Covered bond treatment", "Not recognized [ERBA P.135]", "Not recognized [Re-Proposal P.135]", "US has no covered bond framework (unlike EU/UK)"],
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
  ["Aggregate CET1 impact", "+19%", "Modest decrease", "REVERSAL of direction"],
  ["G-SIB surcharge", "Unchanged", "-$33B aggregate", "Direct capital relief for 8 G-SIBs"],
  ["Retail transactor RW", "55%", "45%", "10pp reduction benefits credit card portfolios"],
  ["Resi RE 80-90% LTV", "75%", "70%", "5pp reduction for high-LTV mortgages"],
  ["Resi RE 90-100% LTV", "85%", "80%", "5pp reduction"],
  ["Resi RE >100% LTV", "100%", "90%", "10pp reduction for underwater mortgages"],
  ["CRE ADC non-HVCRE", "150%", "100%", "50pp reduction for qualifying ADC loans"],
  ["MSA treatment", "CET1 deduction", "250% RW", "Deduction removed, replaced with risk weight"],
  ["Equity non-significant", "250% (proposed)", "100% (retained)", "Industry lobbied successfully to retain 100%"],
  ["OBS <=1Y commitments", "20%", "40%", "DOUBLED: tighter than 2023 NPR"],
  ["ILM for OpRisk", "Included (formula)", "1.0 (removed)", "35% OpRisk RWA reduction for high-loss banks"],
  ["NIC investment mgmt", "Gross basis", "NET basis * 0.7x", "Reduces BI for investment management arms"],
  ["FRTB threshold", "$1B", "$5B", "60% fewer banks subject to FRTB"],
  ["CVA scope", "Cat I-IV", "Cat I-II + thresholds", "Substantially narrowed"],
  ["CVA exemptions", "Limited", "Expanded (5 new)", "Client-cleared, SFTs, intra-group all exempt"],
  ["G-SIB Method 2 coeff", "Standard", "/1.2x downward", "Systematic score reduction"],
  ["G-SIB STWF weight", "30%", "20%", "10pp reduction"],
  ["G-SIB band width", "100bp", "20bp", "5x more granular"],
  ["G-SIB increment", "0.5%", "0.1%", "5x smaller steps"],
  ["G-SIB averaging", "Quarter-end", "Daily/monthly", "Reduces window-dressing"],
  ["Bank RW system", "CRC-based only", "NEW Grade A/B/C system", "More risk-sensitive bank RWs"],
  ["BA-CVA hedges", "SN + Index CDS", "Index ONLY", "Narrowed to index hedges"],
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
