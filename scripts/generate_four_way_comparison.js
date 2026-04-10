const { Document, Packer, Paragraph, Table, TableRow, TableCell, TextRun,
  WidthType, AlignmentType, BorderStyle, ShadingType, PageOrientation,
  Header, Footer, convertInchesToTwip } = require("docx");
const fs = require("fs");

const NAVY = "1A2744";
const GOLD = "C2A677";
const WHITE = "FFFFFF";
const LGRAY = "F2F2F2";
const RED = "C0392B";
const AMBER = "F39C12";
const GREEN = "27AE60";

const CW = [1800, 2100, 2100, 2100, 2100];

function hc(text, w) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: { color: WHITE, fill: NAVY, type: ShadingType.CLEAR },
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
      new TextRun({ text, bold: true, size: 15, color: WHITE, font: "Calibri" })
    ]})],
  });
}

function dc(text, w, bold=false, shade=WHITE) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: { color: "000000", fill: shade, type: ShadingType.CLEAR },
    children: [new Paragraph({ children: [
      new TextRun({ text: text||"", bold, size: 15, font: "Calibri" })
    ]})],
  });
}

function sc(text, w) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: { color: "000000", fill: GOLD, type: ShadingType.CLEAR },
    children: [new Paragraph({ children: [
      new TextRun({ text, bold: true, size: 15, color: NAVY, font: "Calibri" })
    ]})],
  });
}

function ragCell(text, w, color) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: { color: WHITE, fill: color, type: ShadingType.CLEAR },
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
      new TextRun({ text, bold: true, size: 15, color: WHITE, font: "Calibri" })
    ]})],
  });
}

function hr5() {
  return new TableRow({ children: [
    hc("Dimension", CW[0]), hc("US Fed (2026 NPR)", CW[1]),
    hc("BCBS (d424/d457)", CW[2]), hc("UK PRA (PS1/26)", CW[3]),
    hc("EU EBA (CRR3/CRD6)", CW[4])
  ]});
}

function r5(d, a, b, c, e, idx) {
  const sh = idx % 2 === 0 ? WHITE : LGRAY;
  return new TableRow({ children: [
    dc(d, CW[0], true, sh), dc(a, CW[1], false, sh),
    dc(b, CW[2], false, sh), dc(c, CW[3], false, sh),
    dc(e, CW[4], false, sh)
  ]});
}

function sub5(text) {
  return new TableRow({ children: CW.map(w => sc(text, w)) });
}

function st(num, title) {
  return [
    new Paragraph({ spacing: { before: 400, after: 100 }, children: [
      new TextRun({ text: "SECTION " + num, bold: true, size: 28, color: GOLD, font: "Calibri" })
    ]}),
    new Paragraph({ spacing: { before: 0, after: 200 }, children: [
      new TextRun({ text: title, bold: true, size: 32, color: NAVY, font: "Calibri" })
    ]}),
    new Paragraph({ children: [new TextRun({ text: "_".repeat(130), size: 12, color: GOLD })] }),
  ];
}

function mt(rows) {
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: [hr5(), ...rows.map((r, i) => {
      if (r.length === 1) return sub5(r[0]);
      return r5(r[0], r[1], r[2], r[3], r[4], i);
    })],
  });
}

const ch = [];

// Cover
ch.push(
  new Paragraph({ spacing: { before: 2000 } }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [
    new TextRun({ text: "Four-Way Regulatory Comparison", bold: true, size: 72, color: NAVY, font: "Calibri" })
  ]}),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200 }, children: [
    new TextRun({ text: "US Fed vs BCBS vs UK PRA vs EU EBA", bold: true, size: 44, color: GOLD, font: "Calibri" })
  ]}),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 400 }, children: [
    new TextRun({ text: "Basel III Endgame — Cross-Jurisdictional Analysis", size: 28, color: NAVY })
  ]}),
  new Paragraph({ spacing: { before: 1500 } }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [
    new TextRun({ text: "_".repeat(80), color: GOLD, size: 20 })
  ]}),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200 }, children: [
    new TextRun({ text: "FNBC-BIII-2026-001  |  CONFIDENTIAL  |  " + new Date().toISOString().split("T")[0], size: 20 })
  ]}),
  new Paragraph({ pageBreakBefore: true }),
);

// ── S1: Implementation ──
ch.push(...st("1", "Implementation Timeline & Phase-In Schedule"));
ch.push(mt([
  ["Effective Dates & Phase-In"],
  ["Effective date", "Jul 1, 2028 [Re-Proposal P.4]", "Jan 1, 2023 (orig); Jan 1, 2028 (rec) [d424 P.1]", "Jul 1, 2025 [PS1/26 S1.1]", "Jan 1, 2025 [CRR3 Art 461]"],
  ["BCBS original target", "N/A", "Jan 1, 2022 (delayed COVID) [d424]", "N/A", "N/A"],
  ["Output floor (IRB)", "N/A (no IRB) [Re-Proposal P.95]", "50% starting 2023 [d424 P.4]", "50% starting Jul 2025 [PS1/26 S3.1]", "50% starting Jan 2025 [CRR3 Art 465]"],
  ["Floor 2025", "N/A", "50% [d424]", "50% [PS1/26]", "50% [CRR3 Art 465(3)]"],
  ["Floor 2026", "N/A", "55% [d424]", "55% [PS1/26]", "55% [CRR3 Art 465(3)]"],
  ["Floor 2027", "N/A", "60% [d424]", "60% [PS1/26]", "60% [CRR3 Art 465(3)]"],
  ["Floor 2028", "N/A", "65% [d424]", "65% [PS1/26]", "65% [CRR3 Art 465(3)]"],
  ["Floor 2029", "N/A", "70% [d424]", "70% [PS1/26]", "70% [CRR3 Art 465(3)]"],
  ["Floor 2030+", "N/A", "72.5% [d424 P.4]", "72.5% [PS1/26]", "72.5% [CRR3 Art 465(3)]"],
  ["FRTB SA go-live", "Jul 2028 [Re-Proposal]", "Jan 2023 (rec) [d457]", "Jul 2025 [PS1/26]", "Jan 2025 [CRR3 Art 325a]"],
  ["FRTB IMA go-live", "Jul 2028 (with approval) [Re-Proposal]", "Jan 2023 [d457]", "Jul 2025 (with approval) [PS1/26]", "Jan 2026 [CRR3 Art 325az]"],
  ["OpRisk SMA go-live", "Jul 2028 [Re-Proposal]", "Jan 2023 [d424]", "Jul 2025 [PS1/26]", "Jan 2025 [CRR3 Art 312]"],
  ["Pillar 3 Phase 1", "Jul 2028 [Re-Proposal]", "Jan 2023 [d455]", "Jul 2025 [PS1/26]", "Jun 2025 (first disclosure) [CRR3 Art 433]"],
  ["CRD6 transposition", "N/A", "N/A", "N/A (UK not EU)", "Feb 2026 deadline [CRD6 Art 2]"],
]));
ch.push(new Paragraph({ spacing: { before: 200 } }));

// ── S2: Capital Framework ──
ch.push(...st("2", "Capital Framework: Ratios, Buffers & Deductions"));
ch.push(mt([
  ["Minimum Capital Ratios"],
  ["CET1 minimum", "4.5% [12 CFR 217.10]", "4.5% [d424 P.49]", "4.5% [PS1/26 S2.1]", "4.5% [CRR3 Art 92(1)(a)]"],
  ["Tier 1 minimum", "6.0% [12 CFR 217.10]", "6.0% [d424 P.49]", "6.0% [PS1/26 S2.1]", "6.0% [CRR3 Art 92(1)(b)]"],
  ["Total capital minimum", "8.0% [12 CFR 217.10]", "8.0% [d424 P.49]", "8.0% [PS1/26 S2.1]", "8.0% [CRR3 Art 92(1)(c)]"],
  ["Capital Buffers"],
  ["CCB", "2.5% CET1 [12 CFR 217.11]", "2.5% [d424 P.50]", "2.5% [PS1/26 S2.3]", "2.5% [CRD6 Art 129]"],
  ["G-SIB surcharge", "20bp bands/0.1% inc [Re-Proposal P.44]", "100bp bands/0.5% inc [d424 P.51]", "Per BCBS [PS1/26 S2.5]", "Per BCBS [CRD6 Art 131]"],
  ["SCB", ">=2.5% (replaces CCB) [12 CFR 217.11]", "Not in framework [N/A]", "Not adopted (use P2G) [PS1/26]", "Not adopted (use P2G) [CRD6]"],
  ["CCyB", "0-2.5% [12 CFR 217.11(b)]", "0-2.5% [d424 P.50]", "0-2.5% (2% standard) [PRA]", "0-2.5% [CRD6 Art 130]"],
  ["Leverage Ratio"],
  ["Minimum leverage ratio", "3% (SLR) [12 CFR 217.10(a)(5)]", "3% [d424 P.53]", "3.25% (UK-specific) [PS1/26 S2.7]", "3% [CRR3 Art 92(1)(d)]"],
  ["Enhanced leverage", "5% eSLR for Cat I G-SIBs [12 CFR 217.11(d)]", "Not in BCBS [N/A]", "Not adopted [PS1/26]", "G-SII leverage buffer [CRR3 Art 92a]"],
  ["CET1 Deductions"],
  ["Goodwill", "Full deduction [12 CFR 217.22]", "Full deduction [d424 P.52]", "Full deduction [PS1/26]", "Full deduction [CRR3 Art 36(1)(b)]"],
  ["DTA (timing)", "10%/15% threshold [12 CFR 217.22(d)]", "10%/15% threshold [d424 P.52]", "10%/15% threshold [PS1/26]", "10%/15% threshold [CRR3 Art 48]"],
  ["MSA", "250% RW (NOT deducted) [Re-Proposal P.78]", "Deduction [d424 P.52]", "Deduction [PS1/26]", "Deduction [CRR3 Art 36]"],
  ["Significant investments", "10%/15% threshold [12 CFR 217.22(d)]", "Same [d424]", "Same [PS1/26]", "Same [CRR3 Art 48]"],
  ["Software DTA", "No carve-out [12 CFR 217.22]", "No carve-out [d424]", "No carve-out [PS1/26]", "EU CARVE-OUT: not deducted [CRR3 Art 36(1)(b)]"],
  ["AOCI recognition", "Full recognition [12 CFR 217.22]", "Full [d424]", "Full [PS1/26]", "Filter option REMOVED under CRR3 [CRR3 Art 35]"],
  ["AT1 trigger", "N/A (no CoCo market) [US practice]", "5.125% CET1 [d424]", "7% CET1 [PRA rules]", "National discretion (mostly 5.125%) [CRR3 Art 54]"],
]));
ch.push(new Paragraph({ spacing: { before: 200 } }));

// ── S3: Credit Risk SA ──
ch.push(...st("3", "Credit Risk SA: Full Risk Weight Comparison"));
ch.push(mt([
  ["Sovereign Risk Weights"],
  ["Sov CRC/CQS 0-1 / AAA-AA", "0% [Re-Proposal P.102]", "0% [d424 CRE20.7]", "0% [PS1/26 S4.1]", "0% [CRR3 Art 114]"],
  ["Sov CRC 2 / A", "20% [Re-Proposal P.102]", "20% [d424 CRE20.7]", "20% [PS1/26]", "20% [CRR3 Art 114]"],
  ["Sov CRC 3 / BBB", "50% [Re-Proposal P.102]", "50% [d424]", "50% [PS1/26]", "50% [CRR3 Art 114]"],
  ["Sov CRC 4-5 / BB-B", "100% [Re-Proposal P.102]", "100% [d424]", "100% [PS1/26]", "100% [CRR3 Art 114]"],
  ["Sov CRC 6-7 / CCC or below", "150% [Re-Proposal P.102]", "150% [d424]", "150% [PS1/26]", "150% [CRR3 Art 114]"],
  ["Rating basis", "CRC (OECD, no ext ratings) [Dodd-Frank 939A]", "ECAI ratings [d424 CRE20.7]", "ECAI ratings [PS1/26]", "ECAI ratings [CRR3 Art 114]"],
  ["Bank Risk Weights"],
  ["Bank approach", "Self-assessment Grade A/B/C [Re-Proposal P.124]", "ECAI or SCRA [d424 CRE20.16]", "ECAI (aligned BCBS) [PS1/26 S4.3]", "ECAI CQS-based [CRR3 Art 120]"],
  ["Bank Grade A / CQS 1-2", "30-40% [Re-Proposal P.124]", "20-30% ECAI; 30-40% SCRA [d424]", "20-30% [PS1/26]", "20-30% [CRR3 Art 120]"],
  ["Bank Grade B / CQS 3", "75% [Re-Proposal P.126]", "50-75% [d424]", "50% [PS1/26]", "50% [CRR3 Art 120]"],
  ["Bank Grade C / CQS 4-6", "150% [Re-Proposal P.126]", "100-150% [d424]", "100-150% [PS1/26]", "100-150% [CRR3 Art 120]"],
  ["Corporate Risk Weights"],
  ["Corp standard (unrated)", "100% [Re-Proposal P.130]", "100% [d424 CRE20.25]", "100% [PS1/26]", "100% [CRR3 Art 122]"],
  ["Corp IG", "65% (self-assessed) [Re-Proposal P.130]", "65% (PD<=0.5% transitional) [d424]", "65% (PD<=0.5%) [PS1/26]", "65% (CRR3 Art 122a transitional) [CRR3]"],
  ["Corp rated AAA-AA", "N/A (Dodd-Frank) [939A]", "20% [d424 CRE20.25]", "20% [PS1/26]", "20% [CRR3 Art 122]"],
  ["Corp rated A", "N/A [939A]", "50% [d424]", "50% [PS1/26]", "50% [CRR3 Art 122]"],
  ["Corp rated BBB", "N/A [939A]", "75% [d424]", "75% [PS1/26]", "75% [CRR3 Art 122]"],
  ["Corp rated BB", "N/A [939A]", "100% [d424]", "100% [PS1/26]", "100% [CRR3 Art 122]"],
  ["Corp rated <BB", "N/A [939A]", "150% [d424]", "150% [PS1/26]", "150% [CRR3 Art 122]"],
  ["SME"],
  ["SME RW", "85% [Re-Proposal P.132]", "85% [d424 CRE20.28]", "85% [PS1/26]", "85% [CRR3 Art 122(2)]"],
  ["SME threshold", "USD 75M revenue [Re-Proposal]", "EUR 50M [d424]", "GBP 44M [PS1/26]", "EUR 50M [CRR3 Art 122(2)]"],
  ["SME supporting factor", "None [N/A]", "None [d424]", "None [PS1/26]", "0.7619x RETAINED [CRR3 Art 501]"],
  ["Specialised Lending"],
  ["Project finance", "100% (no PF RW) [Re-Proposal]", "130%/100%/80% high-quality [d424 CRE20.32]", "130%/100%/80% [PS1/26]", "130%/100%/80% [CRR3 Art 122a(3)]"],
  ["Object finance", "100% [Re-Proposal]", "100%/80% [d424]", "100%/80% [PS1/26]", "100%/80% [CRR3]"],
  ["Retail"],
  ["Regulatory retail", "75% [Re-Proposal P.138]", "75% [d424 CRE20.37]", "75% [PS1/26]", "75% [CRR3 Art 123]"],
  ["Transactor", "45% [Re-Proposal P.156]", "45% [d424 CRE20.38]", "45% [PS1/26]", "45% [CRR3 Art 123(1a)]"],
  ["Retail threshold", "USD 1M [Re-Proposal]", "EUR 1M [d424]", "GBP 1M [PS1/26]", "EUR 1M [CRR3 Art 123]"],
  ["Residential Real Estate (Non-CF Dependent)"],
  ["Resi LTV 0-50%", "40% [Re-Proposal P.142]", "20% [d424 CRE20.43]", "20% [PS1/26]", "20% [CRR3 Art 125]"],
  ["Resi LTV 50-60%", "45% [Re-Proposal]", "25% [d424]", "25% [PS1/26]", "25% [CRR3 Art 125]"],
  ["Resi LTV 60-70%", "50% [Re-Proposal]", "30% [d424]", "30% [PS1/26]", "30% [CRR3 Art 125]"],
  ["Resi LTV 70-80%", "60% [Re-Proposal]", "30% [d424]", "30% [PS1/26]", "30% [CRR3 Art 125]"],
  ["Resi LTV 80-90%", "70% [Re-Proposal]", "40% [d424]", "40% [PS1/26]", "40% [CRR3 Art 125]"],
  ["Resi LTV 90-100%", "80% [Re-Proposal]", "50% [d424]", "50% [PS1/26]", "50% [CRR3 Art 125]"],
  ["Resi LTV >100%", "90% [Re-Proposal]", "70% [d424]", "70% [PS1/26]", "70% [CRR3 Art 125]"],
  ["ADC/HVCRE", "100/150% (HVCRE split) [Re-Proposal P.150]", "150% flat [d424]", "150% flat [PS1/26]", "150% flat [CRR3 Art 126a]"],
  ["Other Exposures"],
  ["Equity public traded", "250% [Re-Proposal P.160]", "250% [d424 CRE20.55]", "250% [PS1/26]", "250% (phased Art 495a) [CRR3]"],
  ["Equity speculative", "400% [Re-Proposal]", "400% [d424]", "400% [PS1/26]", "400% (phased) [CRR3]"],
  ["Equity EU phase-in", "Immediate [Re-Proposal]", "Immediate [d424]", "Immediate [PS1/26]", "2025-2030 phase-in [CRR3 Art 495a]"],
  ["Past due >90 days", "150% flat [Re-Proposal P.155]", "150% (100% if prov>=20%) [d424 CRE20.51]", "Per BCBS [PS1/26]", "100% if provisions>=20% [CRR3 Art 127]"],
  ["Defaulted", "150% [Re-Proposal P.155]", "150%/100% [d424]", "Per BCBS [PS1/26]", "Per BCBS [CRR3 Art 127]"],
  ["Covered bonds", "N/A [Re-Proposal]", "CQS-based 10-100% [d424]", "CQS-based [PS1/26]", "CQS-based [CRR3 Art 129]"],
]));
ch.push(new Paragraph({ spacing: { before: 200 } }));

// ── S4-S9 ──
ch.push(...st("4", "Off-Balance Sheet Credit Conversion Factors"));
ch.push(mt([
  ["OBS CCF Comparison — KEY US-BCBS DIVERGENCE"],
  ["Commitments >1Y", "40% [Re-Proposal P.170]", "40% [d424 CRE20.69]", "40% [PS1/26]", "40% [CRR3 Art 111]"],
  ["Commitments <=1Y", "40% UNIFORM [Re-Proposal P.170]", "20% [d424 CRE20.69]", "20% [PS1/26]", "20% [CRR3 Art 111]"],
  ["UCC", "10% [Re-Proposal P.172]", "10% [d424 CRE20.70]", "10% [PS1/26]", "10% [CRR3 Art 111]"],
  ["Direct credit substitutes", "100% [Re-Proposal]", "100% [d424]", "100% [PS1/26]", "100% [CRR3 Art 111]"],
  ["Trade-related", "20% [Re-Proposal]", "20% [d424]", "20% [PS1/26]", "20% [CRR3 Art 111]"],
  ["NIF/RUF", "50% [Re-Proposal]", "50% [d424]", "50% [PS1/26]", "50% [CRR3 Art 111]"],
  ["Performance guarantees", "50% [Re-Proposal]", "50% [d424]", "50% [PS1/26]", "50% [CRR3 Art 111]"],
  ["Repo-style", "100% [Re-Proposal]", "100% [d424]", "100% [PS1/26]", "100% [CRR3 Art 111]"],
  ["Impact: $500B ST commit", "+$100B RWA vs BCBS/UK/EU", "Baseline", "Same as BCBS", "Same as BCBS"],
]));
ch.push(new Paragraph({ spacing: { before: 200 } }));

ch.push(...st("5", "Credit Risk Mitigation"));
ch.push(mt([
  ["CRM Mechanics"],
  ["E* formula", "max(0,E*(1+He)-C*(1-Hc-Hfx)) [Re-Proposal P.200]", "Same [d424 CRE22.51]", "Same [PS1/26]", "Same [CRR3 Art 223]"],
  ["Currency mismatch", "8% add-on [Re-Proposal P.210]", "8% [d424 CRE22.60]", "8% [PS1/26]", "8% [CRR3 Art 224]"],
  ["Maturity mismatch", "(t-0.25)/(T-0.25) [Re-Proposal P.212]", "Same [d424 CRE22.65]", "Same [PS1/26]", "Same [CRR3 Art 237]"],
  ["Credit deriv restructuring", "40% adjustment [Re-Proposal]", "40% [d424]", "40% [PS1/26]", "40% [CRR3 Art 233]"],
  ["Simple approach floor", "20% [Re-Proposal]", "20% [d424 CRE22.72]", "20% [PS1/26]", "20% [CRR3 Art 222(5)]"],
  ["Haircuts: Cash", "0% [Re-Proposal]", "0% [d424]", "0% [PS1/26]", "0% [CRR3 Art 224]"],
  ["Haircuts: Sov <=1Y", "0.5% [Re-Proposal]", "0.5% [d424]", "0.5% [PS1/26]", "0.5% [CRR3 Art 224]"],
  ["Haircuts: Sov 1-5Y", "2% [Re-Proposal]", "2% [d424]", "2% [PS1/26]", "2% [CRR3 Art 224]"],
  ["Haircuts: Sov >5Y", "4% [Re-Proposal]", "4% [d424]", "4% [PS1/26]", "4% [CRR3 Art 224]"],
  ["Haircuts: Corp IG <=1Y", "1% [Re-Proposal]", "1% [d424]", "1% [PS1/26]", "1% [CRR3 Art 224]"],
  ["Haircuts: Corp IG 1-5Y", "4% [Re-Proposal]", "4% [d424]", "4% [PS1/26]", "4% [CRR3 Art 224]"],
  ["Haircuts: Corp IG >5Y", "6% [Re-Proposal]", "6% [d424]", "6% [PS1/26]", "6% [CRR3 Art 224]"],
  ["Haircuts: Equity main idx", "15% [Re-Proposal]", "15% [d424]", "15% [PS1/26]", "15% [CRR3 Art 224]"],
  ["Haircuts: Equity other", "25% [Re-Proposal]", "25% [d424]", "25% [PS1/26]", "25% [CRR3 Art 224]"],
  ["Haircuts: Gold", "15% [Re-Proposal]", "15% [d424]", "15% [PS1/26]", "15% [CRR3 Art 224]"],
]));
ch.push(new Paragraph({ spacing: { before: 200 } }));

ch.push(...st("6", "SA-CCR: Counterparty Credit Risk"));
ch.push(mt([
  ["SA-CCR Parameters"],
  ["Alpha (financial)", "1.4 [Re-Proposal P.220]", "1.4 [d424 CRE52.30]", "1.4 [PS1/26]", "1.4 [CRR3 Art 274]"],
  ["Alpha (non-financial)", "1.0 (end-user) [Re-Proposal P.220]", "1.4 (nat disc for 1.0) [d424]", "1.0 (pensions+NFC) [PS1/26]", "1.0 (pensions+NFC<thresh) [CRR3 Art 274]"],
  ["SF: Interest Rate", "0.50% [Re-Proposal]", "0.50% [d424 CRE52.40]", "0.50% [PS1/26]", "0.50% [CRR3 Art 280a]"],
  ["SF: FX", "4.0% [Re-Proposal]", "4.0% [d424]", "4.0% [PS1/26]", "4.0% [CRR3 Art 280c]"],
  ["SF: Credit IG", "0.38% [Re-Proposal]", "0.38% [d424]", "0.38% [PS1/26]", "0.38% [CRR3 Art 280d]"],
  ["SF: Credit Spec", "0.54% [Re-Proposal]", "0.54% [d424]", "0.54% [PS1/26]", "0.54% [CRR3 Art 280d]"],
  ["SF: Equity single", "32% [Re-Proposal]", "32% [d424]", "32% [PS1/26]", "32% [CRR3 Art 280e]"],
  ["SF: Equity index", "20% [Re-Proposal]", "20% [d424]", "20% [PS1/26]", "20% [CRR3 Art 280e]"],
  ["SF: Comm electricity", "40% [Re-Proposal]", "40% [d424]", "40% [PS1/26]", "40% [CRR3 Art 280f]"],
  ["SF: Comm other", "18% [Re-Proposal]", "18% [d424]", "18% [PS1/26]", "18% [CRR3 Art 280f]"],
  ["Multiplier floor", "5% (0.05) [Re-Proposal]", "5% [d424 CRE52.41]", "5% [PS1/26]", "5% [CRR3 Art 278]"],
  ["RC unmargined", "max(V-C, 0) [Re-Proposal]", "Same [d424 CRE52.31]", "Same [PS1/26]", "Same [CRR3 Art 275]"],
  ["RC margined", "max(V-C, TH+MTA-NICA, 0) [Re-Proposal]", "Same [d424 CRE52.34]", "Same [PS1/26]", "Same [CRR3 Art 275]"],
]));
ch.push(new Paragraph({ spacing: { before: 200 } }));

ch.push(...st("7", "CVA Risk Framework"));
ch.push(mt([
  ["CVA Approach & Exemptions"],
  ["BA-CVA", "Available (index hedges only) [Re-Proposal P.284]", "Available (SN+index) [d424 MAR50]", "Available (SN+index) [PS1/26]", "Available (SN+index) [CRR3 Art 382]"],
  ["SA-CVA", "With approval [Re-Proposal P.290]", "With approval [d424 MAR51]", "With approval [PS1/26]", "With approval [CRR3 Art 383]"],
  ["Client-cleared", "Exempt [Re-Proposal P.296]", "Exempt [d424 MAR50.4]", "Exempt [PS1/26]", "Exempt [CRR3 Art 382(4)]"],
  ["FX <=T+2", "Exempt [Re-Proposal]", "Exempt [d424]", "Exempt [PS1/26]", "Exempt [CRR3 Art 382(4)]"],
  ["SFTs", "Exempt [Re-Proposal P.296]", "Not exempt [d424]", "Exempt [PS1/26]", "Exempt [CRR3 Art 382(4)]"],
  ["Pensions", "Exempt [Re-Proposal]", "Exempt [d424]", "Exempt [PS1/26]", "Exempt [CRR3 Art 382(4)]"],
  ["Intra-group", "Exempt [Re-Proposal]", "National discretion [d424]", "Exempt [PS1/26]", "Exempt [CRR3 Art 382(4)]"],
  ["$1T threshold", "YES (US only) [Re-Proposal P.282]", "No [d424]", "No [PS1/26]", "No [CRR3]"],
]));
ch.push(new Paragraph({ spacing: { before: 200 } }));

ch.push(...st("8", "FRTB Market Risk: Key Risk Weights"));
ch.push(mt([
  ["FRTB Thresholds"],
  ["FRTB threshold", "$5B 4Q avg [Re-Proposal P.300]", "Proportionality [d457 MAR10]", "GBP 50M bilateral [PS1/26]", "EUR 500M or % assets [CRR3 Art 325a]"],
  ["GIRR Risk Weights"],
  ["GIRR 0.25Y", "1.7% [Re-Proposal P.312]", "1.7% [d457 MAR21.8]", "1.7% [PS1/26]", "1.7% [CRR3 Art 325q]"],
  ["GIRR 1Y", "1.6% [Re-Proposal]", "1.6% [d457]", "1.6% [PS1/26]", "1.6% [CRR3 Art 325q]"],
  ["GIRR 5Y", "1.1% [Re-Proposal]", "1.1% [d457]", "1.1% [PS1/26]", "1.1% [CRR3 Art 325q]"],
  ["GIRR 10Y-30Y", "1.1% [Re-Proposal]", "1.1% [d457]", "1.1% [PS1/26]", "1.1% [CRR3 Art 325q]"],
  ["GIRR inflation", "1.6% [Re-Proposal]", "1.6% [d457]", "1.6% [PS1/26]", "1.6% [CRR3]"],
  ["CSR Non-Sec Sov IG", "0.5% [Re-Proposal]", "0.5% [d457 MAR21.12]", "0.5% [PS1/26]", "0.5% [CRR3 Art 325s]"],
  ["CSR Non-Sec Corp IG", "1.0% [Re-Proposal]", "1.0% [d457]", "1.0% [PS1/26]", "1.0% [CRR3]"],
  ["CSR Non-Sec HY", "2.0-3.5% [Re-Proposal]", "2.0-3.5% [d457]", "2.0-3.5% [PS1/26]", "2.0-3.5% [CRR3]"],
  ["Equity large AE", "25% [Re-Proposal P.340]", "25% [d457 MAR21.17]", "25% [PS1/26]", "25% [CRR3 Art 325w]"],
  ["Equity small cap", "70% [Re-Proposal]", "70% [d457]", "70% [PS1/26]", "70% [CRR3]"],
  ["Equity index", "15% [Re-Proposal]", "15% [d457]", "15% [PS1/26]", "15% [CRR3]"],
  ["FX all pairs", "15% [Re-Proposal P.360]", "15% [d457 MAR21.21]", "15% [PS1/26]", "15% [CRR3 Art 325y]"],
  ["Commodity crude/coal", "30% [Re-Proposal]", "30% [d457 MAR21.19]", "30% [PS1/26]", "30% [CRR3 Art 325aa]"],
  ["DRC AAA", "0.5% [Re-Proposal]", "0.5% [d457 MAR22.14]", "0.5% [PS1/26]", "0.5% [CRR3]"],
  ["DRC BBB", "6% [Re-Proposal]", "6% [d457]", "6% [PS1/26]", "6% [CRR3]"],
  ["RRAO exotic", "1% [Re-Proposal P.420]", "1% [d457 MAR23.4]", "1% [PS1/26]", "1% [CRR3 Art 325u]"],
  ["RRAO other", "0.1% [Re-Proposal]", "0.1% [d457]", "0.1% [PS1/26]", "0.1% [CRR3]"],
]));
ch.push(new Paragraph({ spacing: { before: 200 } }));

ch.push(...st("9", "Operational Risk: SMA Components"));
ch.push(mt([
  ["OpRisk SMA Comparison"],
  ["BI = ILDC+SC+FC", "Yes [Re-Proposal P.252]", "Yes [d424 S5.2]", "Yes [PS1/26]", "Yes [CRR3 Art 314]"],
  ["ILDC interest cap", "2.25% IEA [Re-Proposal]", "2.25% [d424 S5.3]", "2.25% [PS1/26]", "2.25% [CRR3 Art 314]"],
  ["NIC 0.7x inv mgmt", "YES (US specific) [Re-Proposal P.254]", "Not in BCBS [d424]", "Not adopted [PS1/26]", "Not adopted [CRR3]"],
  ["BIC 12% (<=EUR 1B)", "12% [Re-Proposal P.260]", "12% [d424 S5.7]", "12% [PS1/26]", "12% [CRR3 Art 315]"],
  ["BIC 15% (EUR 1-30B)", "15% [Re-Proposal]", "15% [d424]", "15% [PS1/26]", "15% [CRR3 Art 315]"],
  ["BIC 18% (>EUR 30B)", "18% [Re-Proposal]", "18% [d424]", "18% [PS1/26]", "18% [CRR3 Art 315]"],
  ["ILM", "1.0 (NOT applied) [Re-Proposal P.262]", "National discretion [d424 S5.11]", "1.0 [PS1/26]", "1.0 [CRR3 Art 315(2)]"],
  ["Loss data P1", "Not required [Re-Proposal P.264]", "Required [d424 S5.10]", "Not required P1 [PS1/26]", "MANDATORY (EUR 20K, 10Y) [CRR3 Art 316]"],
  ["COREP templates", "N/A [US reporting]", "N/A [BCBS]", "N/A [PRA reporting]", "C16.02-04 mandatory [CRR3/ITS]"],
  ["M&A loss inclusion", "Supervisory discretion [Re-Proposal]", "Include if material [d424]", "Case-by-case [PS1/26]", "Include if material [CRR3 Art 316(5)]"],
]));
ch.push(new Paragraph({ spacing: { before: 200 } }));

// ── S10-S15 + Save ──
ch.push(...st("10", "Securitization: Hierarchy & STS"));
ch.push(mt([
  ["Securitization Framework"],
  ["Hierarchy", "SEC-SA only [Re-Proposal P.400]", "SEC-IRBA>ERBA>SA [d424 CRE40]", "Full hierarchy [PS1/26]", "Full hierarchy [CRR3 Art 254]"],
  ["STS framework", "NOT adopted [Re-Proposal]", "Optional [d424 CRE40.73]", "Yes (UK STS) [PS1/26]", "Yes, 10% RW floor [CRR3 Art 243]"],
  ["STS RW benefit", "N/A [N/A]", "Lower p=0.3 [d424]", "Lower RW [PS1/26]", "10% floor (vs 15%) [CRR3 Art 260]"],
  ["Risk retention", "5% [Re-Proposal P.410]", "5% [d424 CRE40.5]", "5% [PS1/26]", "5% [CRR3 Art 405]"],
  ["1250% cap", "Yes [Re-Proposal]", "Yes [d424]", "Yes [PS1/26]", "Yes [CRR3 Art 267]"],
  ["SRT assessment", "US rules [Re-Proposal]", "Principle-based [d424]", "PRA review [PS1/26]", "EBA RTS [CRR3 Art 244]"],
]));
ch.push(new Paragraph({ spacing: { before: 200 } }));

ch.push(...st("11", "IRB: Availability, Floors & Output Floor"));
ch.push(mt([
  ["IRB Framework Comparison"],
  ["IRB availability", "ELIMINATED [Re-Proposal P.95]", "Retained (restricted) [d424 CRE30]", "Retained (A-IRB limited) [PS1/26]", "Retained (A-IRB limited) [CRR3 Art 142]"],
  ["Output floor", "N/A (no IRB) [N/A]", "72.5% of SA RWA [d424 P.4]", "72.5% (phased 2025-2030) [PS1/26]", "72.5% (phased 2025-2030) [CRR3 Art 465]"],
  ["F-IRB for corporates", "N/A [N/A]", "Available [d424 CRE31]", "Available [PS1/26]", "Available [CRR3 Art 143]"],
  ["A-IRB for corporates", "N/A [N/A]", "Restricted (large corp) [d424]", "Restricted [PS1/26]", "Restricted [CRR3 Art 143]"],
  ["A-IRB for banks/FIs", "N/A [N/A]", "NOT available [d424]", "NOT available [PS1/26]", "NOT available [CRR3 Art 150]"],
  ["A-IRB for equity", "N/A [N/A]", "NOT available [d424]", "NOT available [PS1/26]", "NOT available [CRR3 Art 155]"],
  ["IRB Input Floors"],
  ["PD floor corporate", "N/A", "5bp (0.05%) [d424 CRE31.4]", "5bp [PS1/26]", "5bp [CRR3 Art 160(1)]"],
  ["PD floor retail MTG", "N/A", "5bp [d424 CRE32.5]", "5bp [PS1/26]", "5bp [CRR3 Art 163]"],
  ["PD floor retail QRE", "N/A", "10bp [d424 CRE32.7]", "10bp [PS1/26]", "10bp [CRR3 Art 163]"],
  ["PD floor retail other", "N/A", "5bp [d424 CRE32.9]", "5bp [PS1/26]", "5bp [CRR3 Art 163]"],
  ["LGD floor unsecured", "N/A", "25% [d424 CRE31.4]", "25% [PS1/26]", "25% [CRR3 Art 161(4)]"],
  ["LGD floor secured (fin)", "N/A", "0% [d424]", "0% [PS1/26]", "0% [CRR3 Art 161(4)]"],
  ["LGD floor secured (RE)", "N/A", "10% [d424]", "10% [PS1/26]", "10% [CRR3 Art 161(4)]"],
  ["LGD floor secured (other)", "N/A", "15% [d424]", "15% [PS1/26]", "15% [CRR3 Art 161(4)]"],
  ["Correlation formula", "N/A", "R=0.12*(1-e^-50PD)/(1-e^-50)+0.24*(1-f) [d424]", "Same [PS1/26]", "Same [CRR3 Art 153]"],
]));
ch.push(new Paragraph({ spacing: { before: 200 } }));

ch.push(...st("12", "Large Exposures"));
ch.push(mt([
  ["Single-Counterparty Credit Limits"],
  ["Standard limit", "25% of Tier 1 [12 CFR 252.72]", "25% of Tier 1 [d283 S2]", "25% of Tier 1 [PS1/26]", "25% of Tier 1 [CRR3 Art 395]"],
  ["G-SIB to G-SIB", "15% of Tier 1 [12 CFR 252.72(a)]", "15% [d283 S2]", "15% [PS1/26]", "15% [CRR3 Art 395(1a)]"],
  ["Reporting threshold", "5% of Tier 1 [12 CFR 252.78]", "10% [d283]", "10% [PS1/26]", "10% [CRR3 Art 394]"],
  ["Sovereign exemption", "Yes (US govt) [12 CFR 252.77]", "National discretion [d283]", "Yes (UK govt) [PS1/26]", "Yes (EU member state) [CRR3 Art 400]"],
  ["Connected parties", "Economic interdependence [12 CFR 252.76]", "Same concept [d283 S5]", "Same concept [PS1/26]", "Same concept [CRR3 Art 4(39)]"],
]));
ch.push(new Paragraph({ spacing: { before: 200 } }));

ch.push(...st("13", "Pillar 2, Pillar 3, ESG & Liquidity"));
ch.push(mt([
  ["Pillar 2"],
  ["ICAAP/SREP", "CCAR + supervisory [Fed SR 12-7]", "Pillar 2 framework [d424]", "ICAAP+PRA buffer [PS1/26]", "SREP + P2R + P2G [CRD6 Art 104a]"],
  ["IRRBB", "Part of CCAR [Fed SR 15-18]", "6 prescribed scenarios [d368]", "Aligned BCBS d368 [PS1/26]", "Aligned BCBS d368 [CRD6 Art 84]"],
  ["ESG risk", "Not in framework [N/A]", "Principles published [BCBS 2024]", "Climate scenario testing [PRA SS3/19]", "MANDATORY ESG in SREP [CRD6 Art 87a]"],
  ["Pillar 3"],
  ["OV1 (Overview RWA)", "Yes [Re-Proposal]", "Yes [d455]", "Yes [PS1/26]", "Yes [CRR3 Art 438]"],
  ["KM1 (Key Metrics)", "Yes [Re-Proposal]", "Yes [d455]", "Yes [PS1/26]", "Yes [CRR3 Art 447]"],
  ["CC1/CC2 (Capital)", "Yes [Re-Proposal]", "Yes [d455]", "Yes [PS1/26]", "Yes [CRR3 Art 437]"],
  ["CR1-CR5 (Credit)", "Yes [Re-Proposal]", "Yes [d455]", "Yes [PS1/26]", "Yes [CRR3 Art 442]"],
  ["MR1-MR4 (Market)", "Yes [Re-Proposal]", "Yes [d455]", "Yes [PS1/26]", "Yes [CRR3 Art 445]"],
  ["OR1 (OpRisk)", "Yes [Re-Proposal]", "Yes [d455]", "Yes [PS1/26]", "Yes [CRR3 Art 446]"],
  ["LR1-LR2 (Leverage)", "Yes [Re-Proposal]", "Yes [d455]", "Yes [PS1/26]", "Yes [CRR3 Art 451]"],
  ["Liquidity"],
  ["LCR", "Implemented [12 CFR 249]", "Standard [d295]", "Implemented [PRA]", "Implemented [CRR3 Art 412]"],
  ["NSFR", "Implemented [12 CFR 249]", "Standard [d295]", "Implemented [PRA]", "Implemented [CRR3 Art 428a]"],
]));
ch.push(new Paragraph({ spacing: { before: 200 } }));

ch.push(...st("14", "Conservatism Scorecard: 20-Dimension RAG Assessment"));
const ragHdrs = ["Dimension", "US Fed", "BCBS", "UK PRA", "EU EBA"];
const ragTable = new Table({
  width: { size: 100, type: WidthType.PERCENTAGE },
  rows: [
    new TableRow({ children: CW.map((w, i) => hc(ragHdrs[i], w)) }),
    ...[
      ["Credit risk SA RWs", RED, AMBER, GREEN, GREEN, "US highest (resi RE +20pp)"],
      ["Off-balance sheet CCFs", RED, GREEN, GREEN, GREEN, "US: 40% uniform (KEY divergence)"],
      ["IRB availability", RED, GREEN, AMBER, AMBER, "US: ELIMINATED entirely"],
      ["Output floor", GREEN, AMBER, AMBER, AMBER, "US: N/A (no IRB to floor)"],
      ["MSA treatment", GREEN, RED, RED, RED, "US: 250% RW (others: deduction)"],
      ["FRTB threshold", GREEN, AMBER, AMBER, AMBER, "US: $5B (highest threshold)"],
      ["CVA scope", GREEN, AMBER, AMBER, AMBER, "US: narrowest scope + exemptions"],
      ["OpRisk ILM", GREEN, AMBER, GREEN, GREEN, "All set ILM=1.0"],
      ["Loss data requirement", GREEN, RED, GREEN, RED, "EU: mandatory COREP C16"],
      ["G-SIB methodology", AMBER, GREEN, GREEN, GREEN, "US: 20bp/0.1% (finer bands)"],
      ["Leverage ratio", RED, GREEN, AMBER, GREEN, "US: 5% eSLR (highest)"],
      ["AT1 trigger", GREEN, AMBER, RED, AMBER, "UK: 7% (highest trigger)"],
      ["STS securitization", RED, AMBER, GREEN, GREEN, "US: no STS framework"],
      ["ESG integration", GREEN, AMBER, AMBER, RED, "EU: mandatory ESG in SREP"],
      ["Real estate RWs", RED, GREEN, GREEN, GREEN, "US: highest RE RWs across LTV"],
      ["Equity phase-in", RED, AMBER, AMBER, GREEN, "EU: Art 495a phase-in 2025-30"],
      ["Past due treatment", RED, GREEN, GREEN, AMBER, "US: flat 150% (others: 100% option)"],
      ["SME supporting factor", RED, RED, RED, GREEN, "EU only: 0.7619x factor"],
      ["Large exposures", AMBER, AMBER, AMBER, AMBER, "Broadly aligned (25%/15%)"],
      ["Pillar 3 disclosure", AMBER, AMBER, AMBER, AMBER, "Broadly aligned templates"],
    ].map((d, idx) => {
      const sh = idx % 2 === 0 ? WHITE : LGRAY;
      return new TableRow({ children: [
        dc(d[0], CW[0], true, sh),
        ragCell(d[0].includes("US") ? "Most" : (d[1]===RED?"Most":"Less"), CW[1], d[1]),
        ragCell(d[2]===RED?"Most":"Baseline", CW[2], d[2]),
        ragCell(d[3]===RED?"Most":"Less", CW[3], d[3]),
        ragCell(d[4]===RED?"Most":"Less", CW[4], d[4]),
      ]});
    }),
  ],
});
ch.push(ragTable);
ch.push(new Paragraph({ spacing: { before: 200 } }));

ch.push(...st("15", "Key Numbers for Senior Management"));
ch.push(mt([
  ["Quick Reference"],
  ["CET1 minimum", "4.5%", "4.5%", "4.5%", "4.5%"],
  ["CCB", "2.5% (or SCB>=2.5%)", "2.5%", "2.5%", "2.5%"],
  ["G-SIB surcharge range", "1.0-4.5%", "1.0-3.5%", "1.0-3.5%", "1.0-3.5%"],
  ["Leverage ratio", "5% eSLR (Cat I)", "3%", "3.25%", "3% + buffer"],
  ["Corp IG risk weight", "65%", "65% (transitional)", "65%", "65% (transitional)"],
  ["Retail transactor RW", "45%", "45%", "45%", "45%"],
  ["Resi RE 80-90% LTV", "70%", "40%", "40%", "40%"],
  ["OBS <=1Y commitment CCF", "40%", "20%", "20%", "20%"],
  ["FRTB threshold", "$5B", "Proportionality", "GBP 50M", "EUR 500M"],
  ["ILM", "1.0", "National discretion", "1.0", "1.0"],
  ["IRB", "ELIMINATED", "Retained + floor", "Retained + floor", "Retained + floor"],
  ["Output floor", "N/A", "72.5%", "72.5%", "72.5%"],
  ["G-SIB bands", "20bp / 0.1%", "100bp / 0.5%", "Per BCBS", "Per BCBS"],
  ["STS securitization", "No", "Optional", "Yes", "Yes (10% floor)"],
  ["Loss data required", "No (P1)", "Yes", "No (P1)", "Yes (EUR 20K, 10Y)"],
]));

// ── SAVE ──
const doc = new Document({
  sections: [{
    properties: {
      page: {
        size: { orientation: PageOrientation.LANDSCAPE, width: convertInchesToTwip(11), height: convertInchesToTwip(8.5) },
        margin: { top: convertInchesToTwip(0.5), bottom: convertInchesToTwip(0.4), left: convertInchesToTwip(0.4), right: convertInchesToTwip(0.4) },
      },
    },
    children: ch,
  }],
});

Packer.toBuffer(doc).then(buffer => {
  const outDir = "/home/user/BASEL-III-Endgame/output";
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(outDir + "/Four_Way_Regulatory_Comparison.docx", buffer);
  console.log("SUCCESS: Four_Way_Regulatory_Comparison.docx generated");
  console.log("Size:", (buffer.length / 1024).toFixed(1), "KB");
}).catch(err => { console.error("ERROR:", err); process.exit(1); });
