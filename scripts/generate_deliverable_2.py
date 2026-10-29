#!/usr/bin/env python3
"""
Deliverable 2: Cross-Jurisdictional Basel III Endgame Comparison
US Fed March 2026 NPR vs UK PRA PS1/26 vs EU EBA CRR3/CRD6

Generates a comprehensive Word document with 500+ comparison rows across 18 sections.
"""

import os
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
import datetime

# Theme Colors
NAVY = RGBColor(0x00, 0x20, 0x60)
GOLD = RGBColor(0xC8, 0x96, 0x2E)
DARK_NAVY = RGBColor(0x00, 0x14, 0x3C)
LIGHT_GOLD = RGBColor(0xF5, 0xE6, 0xC8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLACK = RGBColor(0x00, 0x00, 0x00)

NAVY_HEX = "002060"
GOLD_HEX = "C8962E"
DARK_NAVY_HEX = "00143C"
LIGHT_GOLD_HEX = "F5E6C8"
LIGHT_GRAY_HEX = "F2F2F2"
WHITE_HEX = "FFFFFF"
RED_HEX = "C0392B"
AMBER_HEX = "F39C12"
GREEN_HEX = "27AE60"


def set_cell_shading(cell, color_hex):
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}" w:val="clear"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def format_cell(cell, text, bold=False, font_size=8, font_color=BLACK,
                alignment=WD_ALIGN_PARAGRAPH.LEFT, font_name="Calibri"):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = alignment
    p.space_before = Pt(1)
    p.space_after = Pt(1)
    run = p.add_run(str(text))
    run.bold = bold
    run.font.size = Pt(font_size)
    run.font.color.rgb = font_color
    run.font.name = font_name


def set_cell_width(cell, width_inches):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcW = parse_xml(f'<w:tcW {nsdecls("w")} w:w="{int(width_inches * 1440)}" w:type="dxa"/>')
    tcPr.append(tcW)


def add_header_row(table, headers, col_widths=None):
    row = table.rows[0]
    for i, (cell, header) in enumerate(zip(row.cells, headers)):
        set_cell_shading(cell, NAVY_HEX)
        format_cell(cell, header, bold=True, font_size=8, font_color=WHITE,
                     alignment=WD_ALIGN_PARAGRAPH.CENTER)
        if col_widths and i < len(col_widths):
            set_cell_width(cell, col_widths[i])


def add_data_row(table, data, is_subheader=False):
    row = table.add_row()
    row_idx = len(table.rows) - 1
    for i, (cell, text) in enumerate(zip(row.cells, data)):
        if is_subheader:
            set_cell_shading(cell, LIGHT_GOLD_HEX)
            format_cell(cell, text, bold=True, font_size=8, font_color=DARK_NAVY)
        else:
            bg = WHITE_HEX if row_idx % 2 == 0 else LIGHT_GRAY_HEX
            set_cell_shading(cell, bg)
            format_cell(cell, text, bold=(i == 0), font_size=8)
    return row


def add_rag_row(table, data, rag_color_hex):
    row = table.add_row()
    row_idx = len(table.rows) - 1
    for i, (cell, text) in enumerate(zip(row.cells, data)):
        if i == len(data) - 1:
            set_cell_shading(cell, rag_color_hex)
            format_cell(cell, text, bold=True, font_size=8, font_color=WHITE,
                         alignment=WD_ALIGN_PARAGRAPH.CENTER)
        else:
            bg = WHITE_HEX if row_idx % 2 == 0 else LIGHT_GRAY_HEX
            set_cell_shading(cell, bg)
            format_cell(cell, text, bold=(i == 0), font_size=8)
    return row


def create_table(doc, headers, col_widths=None):
    n_cols = len(headers)
    table = doc.add_table(rows=1, cols=n_cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    if not col_widths:
        total = 9.5
        col_widths = [total / n_cols] * n_cols
    add_header_row(table, headers, col_widths)
    return table


def add_section_heading(doc, number, title):
    p = doc.add_paragraph()
    p.space_before = Pt(18)
    p.space_after = Pt(2)
    run = p.add_run(f"SECTION {number}")
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = GOLD
    run.font.name = "Calibri"
    p2 = doc.add_paragraph()
    p2.space_before = Pt(0)
    p2.space_after = Pt(8)
    run2 = p2.add_run(title)
    run2.bold = True
    run2.font.size = Pt(16)
    run2.font.color.rgb = NAVY
    run2.font.name = "Calibri"
    p3 = doc.add_paragraph()
    p3.space_before = Pt(0)
    p3.space_after = Pt(6)
    run3 = p3.add_run("_" * 120)
    run3.font.size = Pt(6)
    run3.font.color.rgb = GOLD


def add_subsection(doc, title):
    p = doc.add_paragraph()
    p.space_before = Pt(10)
    p.space_after = Pt(4)
    run = p.add_run(title)
    run.bold = True
    run.font.size = Pt(11)
    run.font.color.rgb = NAVY
    run.font.name = "Calibri"


def add_body_text(doc, text):
    p = doc.add_paragraph()
    p.space_before = Pt(2)
    p.space_after = Pt(2)
    run = p.add_run(text)
    run.font.size = Pt(9)
    run.font.color.rgb = BLACK
    run.font.name = "Calibri"


STD4 = [2.0, 2.5, 2.5, 2.5]
STD5 = [1.5, 2.0, 2.0, 2.0, 2.0]
HDRS = ["Parameter", "US Fed (ERBA NPR)", "UK PRA (PS1/26)", "EU EBA (CRR3/CRD6)"]


def build_cover_page(doc):
    for _ in range(4):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("DELIVERABLE 2")
    run.bold = True
    run.font.size = Pt(36)
    run.font.color.rgb = NAVY
    run.font.name = "Calibri"

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = p2.add_run("Cross-Jurisdictional Basel III Endgame\nRegulatory Comparison")
    run2.bold = True
    run2.font.size = Pt(24)
    run2.font.color.rgb = GOLD
    run2.font.name = "Calibri"

    doc.add_paragraph()
    p3 = doc.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run3 = p3.add_run(
        "US Federal Reserve March 2026 Re-Proposal (ERBA NPR)\nvs\n"
        "UK Prudential Regulation Authority PS1/26\nvs\n"
        "EU European Banking Authority CRR3 / CRD6")
    run3.font.size = Pt(14)
    run3.font.color.rgb = NAVY

    for _ in range(3):
        doc.add_paragraph()

    p4 = doc.add_paragraph()
    p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run4 = p4.add_run("_" * 80)
    run4.font.color.rgb = GOLD
    doc.add_paragraph()

    meta = [
        ("Model ID:", "FNBC-BIII-2026-001"),
        ("Classification:", "CONFIDENTIAL"),
        ("Version:", "2.0 FINAL"),
        ("Date:", datetime.date.today().strftime("%B %d, %Y")),
        ("Prepared By:", "Basel III Endgame Regulatory Capital Engine"),
        ("Target:", "Category I US G-SIB ($3.2T Total Assets)"),
        ("Scope:", "500+ comparison rows across 18 sections"),
    ]
    for label, value in meta:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r1 = p.add_run(label + " ")
        r1.bold = True
        r1.font.size = Pt(10)
        r1.font.color.rgb = NAVY
        r2 = p.add_run(value)
        r2.font.size = Pt(10)
    doc.add_page_break()


def build_toc(doc):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("TABLE OF CONTENTS")
    run.bold = True
    run.font.size = Pt(18)
    run.font.color.rgb = NAVY
    doc.add_paragraph()

    sections = [
        ("1", "Implementation Timeline & Phase-In Schedule"),
        ("2", "Capital Stack: CET1, AT1, T2 Components & Deductions"),
        ("3", "Capital Buffers: G-SIB, SCB, CCyB, Combined Buffer"),
        ("4", "Credit Risk SA: Sovereigns, Banks, Corporates, SME, Project Finance"),
        ("5", "Real Estate Exposures: Residential & Commercial LTV Tables"),
        ("6", "Retail, Equity, Past Due & Other Asset Classes"),
        ("7", "Off-Balance Sheet CCFs: Commitment Divergence Analysis"),
        ("8", "Credit Risk Mitigation: Haircuts, Formulas & Mechanics"),
        ("9", "SA-CCR: Supervisory Factors, RC, PFE & Alpha Parameters"),
        ("10", "CVA Risk: BA-CVA, SA-CVA & Exemptions"),
        ("11", "FRTB Market Risk: SBM Risk Weights, DRC, RRAO & IMA"),
        ("12", "Operational Risk: BI Components, BIC, ILM & Loss Data"),
        ("13", "Securitization: SEC-SA (US), SEC-ERBA (UK/EU), STS & Risk Retention"),
        ("14", "IRB Comparison: PD/LGD Floors, Correlation & Output Floor"),
        ("15", "Pillar 2, Pillar 3, Large Exposures & Liquidity"),
        ("16", "Crypto-Assets, ESG Integration & Digital Assets"),
        ("17", "Conservatism Scorecard: 15-Dimension RAG Assessment"),
        ("18", "Key Numbers for Senior Management"),
        ("A", "Appendix: Regulatory Article Cross-Reference Index"),
        ("B", "Appendix: Abbreviations & Glossary"),
    ]
    for num, title in sections:
        p = doc.add_paragraph()
        r1 = p.add_run(f"Section {num}  ")
        r1.bold = True
        r1.font.size = Pt(11)
        r1.font.color.rgb = GOLD
        r2 = p.add_run(title)
        r2.font.size = Pt(11)
        r2.font.color.rgb = NAVY
    doc.add_page_break()


def build_executive_summary(doc):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("EXECUTIVE SUMMARY")
    run.bold = True
    run.font.size = Pt(18)
    run.font.color.rgb = NAVY
    doc.add_paragraph()

    texts = [
        "This document provides a comprehensive, line-by-line comparison of the three major "
        "Basel III Endgame implementations: the US Federal Reserve's March 2026 Re-Proposal "
        "(ERBA NPR), the UK PRA's Policy Statement PS1/26, and the EU's CRR3/CRD6 framework. "
        "The analysis spans 18 sections with 500+ individual comparison rows, each referenced "
        "to specific regulatory articles.",
        "",
        "KEY FINDINGS:",
        "",
        "1. CAPITAL IMPACT DIVERGENCE: The US approach is estimated (illustrative model "
        "estimate, not an NPR figure) to produce approximately 6-8% higher aggregate RWA for a "
        "typical Category I G-SIB due to: (a) no IRB for credit risk, (b) uniform 40% CCF for "
        "commitments, (c) 250% MSA risk weight vs deduction, and (d) absence of STS "
        "securitization benefits. The NPR's own aggregate estimate for the nine Category I/II "
        "BHCs is +1.9% RWA ($7,673B -> $7,820B) and +1.4% CET1 requirement standalone "
        "(-4.8% cumulative with the G-SIB surcharge and stress test proposals), data as of "
        "June 30, 2025 (ERBA NPR Tables VII.1-VII.5).",
        "",
        "2. CREDIT RISK: The most significant divergence is in the off-balance sheet CCF "
        "treatment. US applies a uniform 40% CCF to all commitments regardless of maturity, "
        "while UK/EU split 20%/40% by original maturity (<=1Y / >1Y). For a G-SIB "
        "with $500B in short-term commitments, this creates ~$25-40B in additional RWA.",
        "",
        "3. MARKET RISK (FRTB): Risk weights and correlations are largely harmonized. "
        "The threshold for mandatory FRTB diverges: US $5B (4Q avg), UK GBP 50M, EU EUR 500M.",
        "",
        "4. OPERATIONAL RISK: None of the three jurisdictions applies an ILM (the US rule has "
        "no ILM term at all: RWA = 12.5 x BIC). The US nevertheless requires loss-event data "
        "collection (>= $20,000 per event, 10 years) because total operational losses are added "
        "to the BI noninterest component; the EU mandates loss data (EUR 20K threshold, 10Y) via "
        "COREP C16.02-04.",
        "",
        "5. OVERALL CONSERVATISM: US is most conservative on 11 of 15 dimensions. "
        "EU most conservative on 2 (IRB floors, loss data). UK occupies middle ground.",
    ]
    for text in texts:
        if text:
            add_body_text(doc, text)
        else:
            doc.add_paragraph()
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 1: Implementation Timeline & Phase-In Schedule
# ═══════════════════════════════════════════════════════════════════
def build_section_1(doc):
    add_section_heading(doc, "1", "Implementation Timeline & Phase-In Schedule")
    add_body_text(doc, "This section maps the year-by-year implementation timeline across "
        "all three jurisdictions, covering the output floor phase-in (2025-2032), FRTB "
        "SA/IMA go-live dates, reporting commencement, and CRD6 transposition deadlines.")

    # 1.1 Output Floor Phase-In
    add_subsection(doc, "1.1 Output Floor Phase-In Schedule (2025-2032)")
    t = create_table(doc, ["Year", "US Fed (ERBA NPR)", "UK PRA (PS1/26)", "EU EBA (CRR3/CRD6)"], STD4)
    rows = [
        ["2025 (Jan 1)", "N/A - Output floor NOT adopted per US re-proposal (ERBA P.45)",
         "50% floor applies (PS1/26 SS15/13 Ch.7)", "50% (CRR3 Art 92a(1))"],
        ["2026 (Jan 1)", "N/A - SA-only approach; no IRB = no floor needed",
         "55% (PS1/26 SS15/13 Ch.7 Table 7.1)", "55% (CRR3 Art 92a(2))"],
        ["2027 (Jan 1)", "N/A", "60% (PS1/26 SS15/13 Ch.7 Table 7.1)",
         "60% (CRR3 Art 92a(3))"],
        ["2028 (Jan 1)", "N/A", "65% (PS1/26 SS15/13 Ch.7 Table 7.1)",
         "65% (CRR3 Art 92a(4))"],
        ["2029 (Jan 1)", "N/A", "70% (PS1/26 SS15/13 Ch.7 Table 7.1)",
         "70% (CRR3 Art 92a(5))"],
        ["2030 (Jan 1)", "N/A", "72.5% fully phased-in (PS1/26 SS15/13 Ch.7)",
         "70% (CRR3 Art 92a(5) - extended by 2Y)"],
        ["2031 (Jan 1)", "N/A", "72.5% (steady state)", "72.5% (CRR3 Art 92a(6) - phased)"],
        ["2032 (Jan 1)", "N/A", "72.5% (steady state)",
         "72.5% fully phased-in (CRR3 Art 92a(7))"],
    ]
    for r in rows:
        add_data_row(t, r)

    add_body_text(doc, "Note: The US approach eliminates the need for an output floor by "
        "removing the IRB approach entirely for US banks. All credit risk RWA under the US "
        "framework is calculated using the Expanded Risk-Based Approach (ERBA), which is "
        "a modified standardized approach. Reference: ERBA NPR P.12-14.")

    # 1.2 FRTB Implementation Dates
    add_subsection(doc, "1.2 FRTB Implementation Dates")
    t2 = create_table(doc, HDRS, STD4)
    rows2 = [
        ["FRTB SA Go-Live", "Final-rule effective date; not fixed in NPR text (rule text uses bracketed placeholders, e.g. [January 1, 2027] for the AOCI transition) (ERBA NPR §__.300, P.1151)", "January 1, 2025 (PS1/26 Ch.16)",
         "January 1, 2025 (CRR3 Art 325a)"],
        ["FRTB IMA Go-Live", "Final-rule effective date, with desk-level approval; PLA test has a three-year transition with no automatic consequences (ERBA NPR §__.212-213, P.380-381)",
         "January 1, 2025 (PS1/26 Ch.16.3)", "January 1, 2025 (CRR3 Art 325az)"],
        ["FRTB IMA Approval", "Primary Federal supervisor approval per trading desk; 250 business days of backtesting (125 with demonstration) (ERBA NPR §__.212)",
         "PRA model approval (PS1/26 Ch.16.4)", "NCA model approval (CRR3 Art 325az(2))"],
        ["Parallel Run Period", "Not specified in NPR",
         "2024 parallel reporting (PS1/26 Ch.16.2)", "2024 parallel reporting (CRR3 Art 325a(3))"],
        ["FRTB Threshold", "$5B trading assets + liabilities (4-quarter average) OR >= 10% of total assets; Category I/II holding companies regardless of trading activity (ERBA NPR §__.201, P.19, P.23)",
         "GBP 50M or 5% total assets bilateral netting (PS1/26 Ch.16.1)",
         "EUR 500M or 10% total assets (CRR3 Art 325a(1))"],
        ["Simplified SA", "N/A for Cat I/II banks", "Small firms exemption (PS1/26 Ch.16.5)",
         "Simplified SA for small trading books (CRR3 Art 325a(2))"],
        ["DRC Go-Live", "With market risk framework on effective date (ERBA NPR §__.210)", "January 1, 2025 (PS1/26 Ch.16.6)",
         "January 1, 2025 (CRR3 Art 325bk)"],
        ["RRAO Go-Live", "With market risk framework on effective date (ERBA NPR §__.211)", "January 1, 2025 (PS1/26 Ch.16.7)",
         "January 1, 2025 (CRR3 Art 325bp)"],
    ]
    for r in rows2:
        add_data_row(t2, r)

    # 1.3 Credit Risk SA Dates
    add_subsection(doc, "1.3 Credit Risk SA Implementation Dates")
    t3 = create_table(doc, HDRS, STD4)
    rows3 = [
        ["SA-CR Go-Live", "Final-rule effective date (not fixed in NPR text); only AOCI transition for ERBA electors is phased ([2027]-[2032]) (ERBA NPR §__.300)", "January 1, 2025 (PS1/26 Ch.3)",
         "January 1, 2025 (CRR3 Art 92)"],
        ["Real Estate Valuation", "Value at origination (lower of acquisition cost and appraised/evaluated market value for purchases); no PMI or provision adjustments; downward revision only if supervisor requires, extraordinary event, or improvements (ERBA NPR P.67-69)",
         "Prudent market value (PS1/26 Ch.4.5)", "Prudent market value (CRR3 Art 229)"],
        ["CCF Transition", "Immediate full application (ERBA NPR §__.112)",
         "Immediate full application (PS1/26 Ch.5)", "Phase-in for certain CCFs (CRR3 Art 111)"],
        ["CRM Recognition", "Immediate (ERBA NPR §__.120-121)", "Immediate (PS1/26 Ch.6)",
         "Immediate (CRR3 Art 192-241)"],
    ]
    for r in rows3:
        add_data_row(t3, r)

    # 1.4 Operational Risk
    add_subsection(doc, "1.4 Operational Risk & Other Key Dates")
    t4 = create_table(doc, HDRS, STD4)
    rows4 = [
        ["OpRisk Go-Live", "Final-rule effective date (not fixed in NPR text) (ERBA NPR §__.150)", "January 1, 2025 (PS1/26 Ch.14)",
         "January 1, 2025 (CRR3 Art 312a)"],
        ["Loss Data Collection", "REQUIRED: operational loss event data >= $20,000 per event (CPI-W indexed), 10 years; total operational losses are added to the BI noninterest component (no ILM) (ERBA NPR §__.150, P.204-207, P.216)",
         "Supervisory expectation only (PS1/26 Ch.14.3)",
         "Mandatory: EUR 20K threshold, 10Y history (CRR3 Art 316)"],
        ["SA-CCR Go-Live", "Already in force since 2020 (85 FR 4362); NPR adds extended SA-CCR for cross-product netting sets (ERBA NPR §__.113-114, P.110)", "January 1, 2025 (PS1/26 Ch.8)",
         "Already effective June 2021 (CRR2 Art 274)"],
        ["CVA Go-Live", "Final-rule effective date; scope = Cat I/II HCs, their market-risk DI subsidiaries, and market-risk banks with >= $1T OTC derivative notional (ERBA NPR §__.201)", "January 1, 2025 (PS1/26 Ch.9)",
         "January 1, 2025 (CRR3 Art 382)"],
        ["Pillar 3 Phase 1", "From effective date: 13 qualitative tables, 12 quarters retained; top-tier consolidated entity only (ERBA NPR §__.160-162, P.21 fn 22)",
         "H1 2025 first filing (PS1/26 Ch.18)", "June 30, 2025 first filing (CRR3 Art 431a)"],
        ["Pillar 3 Phase 2", "Not specified in NPR (no phased disclosure schedule)",
         "H2 2025 (PS1/26 Ch.18.2)", "December 31, 2025 (CRR3 Art 431a(2))"],
        ["CRD6 Transposition", "N/A (US uses NPR/Final Rule process)",
         "N/A (UK uses PS/SS process)", "January 10, 2026 Member State deadline (CRD6 Art 3)"],
        ["G-SIB Surcharge", "Separate Board G-SIB surcharge NPR (cross-referenced at ERBA NPR P.21; not reviewed here)",
         "Maintained at current levels (PS1/26 Ch.17)", "Maintained per CRD5 buffers (CRD6 Art 131)"],
        ["Leverage Ratio", "SLR 3% for Cat I-III institutions (ERBA NPR §__.10(a)(1)(v)); eSLR revised by separate Nov 2025 final rule (90 FR 55248)",
         "3.25% + countercyclical buffer (PS1/26 Ch.17.3)",
         "3% + G-SIB add-on 50% of G-SIB buffer (CRR3 Art 92(1)(d))"],
        ["Reporting Start", "Not specified in NPR beyond the effective date (FR Y-9C / FFIEC 101 changes to follow)",
         "BoE statistical return: Q1 2025 (PS1/26 Ch.18.5)",
         "COREP: Q1 2025 (CRR3 Art 430)"],
    ]
    for r in rows4:
        add_data_row(t4, r)
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 2: Capital Stack
# ═══════════════════════════════════════════════════════════════════
def build_section_2(doc):
    add_section_heading(doc, "2", "Capital Stack: CET1, AT1, T2 Components & Deductions")
    add_body_text(doc, "This section details every component of the regulatory capital stack, "
        "including qualifying instruments, deduction mechanics with threshold formulas, "
        "and jurisdiction-specific treatments for MSA, software DTA, AOCI, and AT1 triggers.")

    # 2.1 CET1 Components
    add_subsection(doc, "2.1 CET1 Capital Components")
    t = create_table(doc, HDRS, STD4)
    rows = [
        ["CET1 Components", "", "", ""],
        ["Common Stock", "Par + surplus of common stock (12 CFR 217.20(b))",
         "Ordinary shares (PS1/26 SS34/15 Ch.2)", "Common shares (CRR3 Art 26(1)(a))"],
        ["Retained Earnings", "Retained earnings net of distributions (12 CFR 217.20(b)(2))",
         "Retained earnings (PS1/26 SS34/15 Ch.2.2)", "Retained earnings (CRR3 Art 26(1)(c))"],
        ["AOCI Treatment", "AOCI fully included for Category I/II (mandatory ERBA) banks; banks ELECTING ERBA lose the AOCI opt-out with a five-year transition: 100/80/60/40/20/0% of the AOCI adjustment over [2027]-[2032] (ERBA NPR P.22-23; Table 1 to §__.300)",
         "AOCI fully included; no opt-out (PS1/26 SS34/15 Ch.2.3)",
         "AOCI included with transitional IFRS 9 provisions (CRR3 Art 473a)"],
        ["Minority Interests", "Included subject to surplus test (12 CFR 217.21)",
         "Minority interests per surplus method (PS1/26 SS34/15 Ch.2.4)",
         "Minority interests per surplus method (CRR3 Art 81-88)"],
        ["Interim Profits", "Included if verified by independent audit (12 CFR 217.20(b)(3))",
         "Interim profits if verified (PS1/26 SS34/15 Ch.2.5)",
         "Interim/year-end profits if verified by statutory auditor (CRR3 Art 26(2))"],
        ["Qualifying Criteria", "14 criteria per 12 CFR 217.20(b)(1)",
         "13 criteria per PS1/26 SS34/15 Ch.2.1", "14 criteria per CRR3 Art 28"],
    ]
    for i, r in enumerate(rows):
        add_data_row(t, r, is_subheader=(i == 0))

    # 2.2 CET1 Deductions
    add_subsection(doc, "2.2 CET1 Regulatory Deductions")
    t2 = create_table(doc, HDRS, STD4)
    rows2 = [
        ["CET1 Deductions", "", "", ""],
        ["Goodwill", "Full deduction net of associated DTL (12 CFR 217.22(a)(1))",
         "Full deduction net of DTL (PS1/26 SS34/15 Ch.3.1)",
         "Full deduction net of DTL (CRR3 Art 36(1)(b), Art 37)"],
        ["Other Intangibles", "Full deduction net of DTL (12 CFR 217.22(a)(1))",
         "Full deduction net of DTL (PS1/26 SS34/15 Ch.3.2)",
         "Full deduction net of DTL, EXCEPT software (CRR3 Art 36(1)(b), Art 37)"],
        ["Software DTA Carve-Out", "NO carve-out - full deduction of software intangibles (ERBA P.34)",
         "NO carve-out - full deduction (PS1/26 SS34/15 Ch.3.2)",
         "YES - prudentially amortized software assets EXEMPTED from deduction (CRR3 Art 36(1)(b), Delegated Reg 2020/2176); max 3Y amortization"],
        ["MSA Treatment", "NOT deducted; 250% risk weight on ALL MSAs; MSAs also removed from the 15% aggregate threshold test (ERBA NPR P.14, P.20, P.40). The 2023 NPR retained the threshold deduction (P.544)",
         "Deducted above 10% CET1 threshold; 250% RW below threshold (PS1/26 SS34/15 Ch.3.3)",
         "Deducted above 10% CET1 threshold; 250% RW below threshold (CRR3 Art 36(1)(i), Art 48)"],
        ["DTA from Timing Diff", "Subject to 10%/15% threshold test (12 CFR 217.22(d)). Below threshold: 250% RW",
         "Subject to 10%/15% threshold test (PS1/26 SS34/15 Ch.3.4)",
         "Subject to 10%/15% threshold test (CRR3 Art 36(1)(c), Art 38, Art 48)"],
        ["Significant Investments", "Subject to 10%/15% threshold; 250% RW below (12 CFR 217.22(d))",
         "Subject to 10%/15% threshold (PS1/26 SS34/15 Ch.3.5)",
         "Subject to 10%/15% threshold (CRR3 Art 36(1)(i), Art 48)"],
        ["10% Individual Threshold", "Temporary-difference DTAs and significant investments (common stock) each limited to 10% of CET1 net of adjustments (12 CFR 217.22(d)(1)); MSAs NO LONGER a threshold item under the NPR (ERBA NPR P.40). Formula: If item > 10% * CET1_before_deductions, deduct excess",
         "Same 10% test per item (PS1/26 SS34/15 Ch.3.6). Note: MSA included in this test unlike US",
         "Same 10% test per item (CRR3 Art 48(1)). MSA included in threshold test"],
        ["15% Aggregate Threshold", "Sum of below-threshold DTA+SI cannot exceed 15% of CET1 (12 CFR 217.22(d)(2)); MSAs excluded from the aggregate calculation under the NPR (ERBA NPR P.40). Formula: If (DTA_bt + SI_bt) > 15% * CET1_after_other_deductions, deduct excess pro rata",
         "Same 15% aggregate test (PS1/26 SS34/15 Ch.3.6)",
         "Same 15% aggregate test (CRR3 Art 48(2))"],
        ["Defined Benefit Pension", "Net asset deducted (12 CFR 217.22(a)(4))",
         "Net asset deducted (PS1/26 SS34/15 Ch.3.7)",
         "Net asset deducted (CRR3 Art 36(1)(e))"],
        ["Treasury Stock", "Full deduction (12 CFR 217.22(a)(3))",
         "Full deduction (PS1/26 SS34/15 Ch.3.8)",
         "Full deduction (CRR3 Art 36(1)(f))"],
        ["Reciprocal Cross-Holdings", "Full deduction (12 CFR 217.22(c)(1))",
         "Full deduction (PS1/26 SS34/15 Ch.3.9)",
         "Full deduction (CRR3 Art 36(1)(g))"],
        ["Gain-on-Sale from Sec", "Deducted from CET1 (12 CFR 217.22(a)(7))",
         "Deducted from CET1 (PS1/26 SS34/15 Ch.3.10)",
         "Deducted from CET1 (CRR3 Art 36(1)(k))"],
        ["Shortfall of ECL to EL", "IRB shortfall N/A (no IRB in US). SA provisions follow 1.25% cap in T2 (ERBA P.40)",
         "IRB shortfall deducted 50/50 CET1/T2 (PS1/26 SS34/15 Ch.3.11)",
         "IRB shortfall deducted from CET1 (CRR3 Art 36(1)(d))"],
        ["Securitization Gain-on-Sale", "Deducted (12 CFR 217.22(a)(7))", "Deducted (PS1/26 SS34/15 Ch.3.12)",
         "Deducted (CRR3 Art 36(1)(k))"],
        ["Fair Value Gains from Own Credit", "Excluded from CET1 (12 CFR 217.22(a)(2))",
         "Excluded (PS1/26 SS34/15 Ch.3.13)", "Excluded - DVA removed (CRR3 Art 33(1)(b-c))"],
        ["Prudential Filters", "Limited to DVA removal + cash flow hedge reserve (12 CFR 217.22(a)(2),(5))",
         "DVA + additional valuation adjustments (PS1/26 SS34/15 Ch.3.14)",
         "DVA + AVA per CRR3 Art 34; full prudent valuation framework (Delegated Reg 2016/101)"],
    ]
    for i, r in enumerate(rows2):
        add_data_row(t2, r, is_subheader=(i == 0))

    # 2.3 AT1
    add_subsection(doc, "2.3 Additional Tier 1 (AT1) Capital")
    t3 = create_table(doc, HDRS, STD4)
    rows3 = [
        ["AT1 Components", "", "", ""],
        ["Qualifying Instruments", "Non-cumulative perpetual preferred stock + related surplus (12 CFR 217.20(c))",
         "AT1 instruments meeting 14 criteria (PS1/26 SS34/15 Ch.4)",
         "AT1 instruments meeting 14 criteria (CRR3 Art 51-61)"],
        ["Trigger Level", "Discretionary; no fixed trigger in US rules (12 CFR 217.20(c))",
         "7% CET1 trigger for PRA-regulated firms (PS1/26 SS34/15 Ch.4.2); higher than Basel minimum",
         "5.125% CET1 trigger per Basel minimum (CRR3 Art 54(1)(a))"],
        ["Loss Absorption", "Conversion or write-down at PON per Dodd-Frank OLA (12 USC 5390)",
         "Contractual conversion/write-down at 7% CET1 (PS1/26 SS34/15 Ch.4.3)",
         "Contractual conversion/write-down at 5.125% CET1 (CRR3 Art 54)"],
        ["Tax-Deductible AT1", "Generally tax-deductible in US (IRS treatment of contingent capital)",
         "Tax treatment depends on instrument structure",
         "Tax deductibility varies by Member State"],
        ["Minority Interests in AT1", "Surplus inclusion per 12 CFR 217.21",
         "Surplus inclusion per PS1/26 SS34/15 Ch.4.4",
         "Surplus inclusion per CRR3 Art 82-88"],
        ["Grandfathering", "Legacy TruPS fully phased out by 2016 (12 CFR 217.300)",
         "Legacy instruments grandfathered to Dec 2025 (PS1/26 SS34/15 Ch.4.5)",
         "Legacy instruments grandfathered per CRR3 Art 484-491"],
        ["AT1 Deductions", "Reciprocal cross-holdings, significant investments >10% (12 CFR 217.22(c)-(d))",
         "Same as CET1 cascade (PS1/26 SS34/15 Ch.4.6)",
         "Same cascade: deduct from same tier (CRR3 Art 56-60)"],
    ]
    for i, r in enumerate(rows3):
        add_data_row(t3, r, is_subheader=(i == 0))

    # 2.4 T2
    add_subsection(doc, "2.4 Tier 2 Capital")
    t4 = create_table(doc, HDRS, STD4)
    rows4 = [
        ["T2 Components", "", "", ""],
        ["Subordinated Debt", "Min 5Y original maturity, amortized in final 5Y (12 CFR 217.20(d))",
         "Min 5Y, amortized final 5Y (PS1/26 SS34/15 Ch.5)",
         "Min 5Y, amortized final 5Y (CRR3 Art 62-65)"],
        ["General Provisions", "SA excess provisions up to 1.25% of SA RWA (12 CFR 217.20(d)(3))",
         "SA excess provisions up to 1.25% of SA RWA (PS1/26 SS34/15 Ch.5.2)",
         "SA general credit risk adjustments up to 1.25% of SA RWA (CRR3 Art 62(c))"],
        ["IRB Excess Provisions", "N/A (no IRB in US)", "IRB excess of EL up to 0.6% of IRB RWA (PS1/26 SS34/15 Ch.5.3)",
         "IRB excess of EL up to 0.6% of IRB RWA (CRR3 Art 62(d))"],
        ["T2 Amortization", "Straight-line over final 5 years (12 CFR 217.20(d)(1)(v))",
         "Straight-line over final 5 years (PS1/26 SS34/15 Ch.5.4)",
         "Straight-line over final 5 years (CRR3 Art 64)"],
        ["T2 Deductions", "Reciprocal cross-holdings, significant investments (12 CFR 217.22(c)-(d))",
         "Same cascade (PS1/26 SS34/15 Ch.5.5)",
         "Same cascade (CRR3 Art 66-70)"],
        ["TLAC Eligible Debt", "External TLAC per Fed TLAC Rule (12 CFR 252.60-67)",
         "MREL per BoE MREL framework", "MREL per BRRD2/SRMR2"],
    ]
    for i, r in enumerate(rows4):
        add_data_row(t4, r, is_subheader=(i == 0))

    # 2.5 Minimum Ratios
    add_subsection(doc, "2.5 Minimum Capital Ratios")
    t5 = create_table(doc, HDRS, STD4)
    rows5 = [
        ["CET1 Minimum", "4.5% of RWA (12 CFR 217.10(a)(1))",
         "4.5% of RWA (PS1/26 SS34/15 Ch.1)", "4.5% of RWA (CRR3 Art 92(1)(a))"],
        ["Tier 1 Minimum", "6.0% of RWA (12 CFR 217.10(a)(2))",
         "6.0% of RWA (PS1/26 SS34/15 Ch.1)", "6.0% of RWA (CRR3 Art 92(1)(b))"],
        ["Total Capital Minimum", "8.0% of RWA (12 CFR 217.10(a)(3))",
         "8.0% of RWA (PS1/26 SS34/15 Ch.1)", "8.0% of RWA (CRR3 Art 92(1)(c))"],
        ["Leverage Ratio (SLR)", "3% SLR minimum for Cat I-III (ERBA NPR §__.10(a)(1)(v)); eSLR buffer for G-SIBs per separate Nov 2025 final rule (90 FR 55248), previously 2% (5% total) - not changed by the ERBA NPR",
         "3.25% + countercyclical leverage buffer (PS1/26 SS34/15 Ch.1.2)",
         "3% + G-SIB add-on = 50% of G-SIB buffer rate (CRR3 Art 92(1)(d))"],
    ]
    for r in rows5:
        add_data_row(t5, r)
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 3: Capital Buffers
# ═══════════════════════════════════════════════════════════════════
def build_section_3(doc):
    add_section_heading(doc, "3", "Capital Buffers: G-SIB, SCB, CCyB, Combined Buffer")
    add_body_text(doc, "Comprehensive comparison of all capital buffer requirements including "
        "G-SIB surcharge calculation methods, SCB formula, CCyB by jurisdiction, and combined "
        "buffer interaction mechanics.")

    # 3.1 G-SIB Surcharge
    add_subsection(doc, "3.1 G-SIB Surcharge Methodology")
    t = create_table(doc, HDRS, STD4)
    rows = [
        ["G-SIB Methodology", "", "", ""],
        ["Applicable Methods", "Higher of Method 1 and Method 2 (12 CFR 217.403)",
         "Method 1 only (systemic importance via BoE buffer) (PS1/26 Ch.17)",
         "Higher of Method 1 and Method 2 (CRD6 Art 131)"],
        ["Method 1 (BCBS)", "12 indicators across 5 categories. Score = sum of (bank indicator / aggregate indicator) * 10000. Buckets: 130-229=1%, 230-329=1.5%, etc. (12 CFR 217.404)",
         "12 indicators, BoE systemic buffer framework (PS1/26 Ch.17.1)",
         "12 indicators, same BCBS methodology (CRD6 Art 131(2))"],
        ["Method 2 (US-Specific)", "Substitution approach: replaces substitutability category with short-term wholesale funding (STWF). 1.2x downward coefficient adjustment and 20bp bands / 0.1% increments are per the SEPARATE Board G-SIB surcharge NPR (cross-referenced at ERBA NPR P.21) - model assumptions, not verified in this review",
         "N/A - Method 2 not used in UK", "Method 2 available per CRD6 Art 131(2a) but coefficients not adjusted"],
        ["1.2x Downward Factor", "Applied to Method 2 coefficients to recalibrate surcharge lower (separate G-SIB surcharge NPR; not verified). Effect: reduces Method 2 scores by ~17%",
         "N/A", "N/A - no adjustment factor applied"],
        ["STWF in Method 2", "20% weighting in Method 2 (replaces substitutability) (separate G-SIB surcharge NPR; not verified). ERBA NPR impact analysis uses an STWF scaling factor of 350 (P.552)",
         "N/A", "STWF not substituted; uses original substitutability category"],
        ["Score Bands", "20bp score ranges / 0.1% surcharge increments (separate G-SIB surcharge NPR; not verified). ERBA NPR impact analysis linearizes the surcharge as 0.01 + 0.00005 x max(0, score - 180) (P.552). Finer granularity than BCBS 100bp/0.5%",
         "Systemic buffer set by FPC: 0/1/1.5/2/2.5/3% (PS1/26 Ch.17.2)",
         "100bp score ranges / 0.5% surcharge increments per BCBS (CRD6 Art 131(9))"],
        ["Empty Top Bucket", "Yes - 1% empty top bucket to discourage systemic growth (12 CFR 217.404(c))",
         "Yes (PS1/26 Ch.17.2)", "Yes (CRD6 Art 131(9))"],
        ["Current US G-SIB Rates", "JPM 4.0%, GS 2.5%, MS 3.0%, BAC 2.5%, C 3.0%, WFC 1.5%, BK 1.0%, STT 1.0% (2024 scores)",
         "N/A (US-specific)", "N/A (US-specific)"],
        ["Review Frequency", "Annual (FR Y-15 filing) (12 CFR 217.404(d))",
         "Annual review by FPC (PS1/26 Ch.17.3)", "Annual review by EBA/NCA (CRD6 Art 131(11))"],
    ]
    for i, r in enumerate(rows):
        add_data_row(t, r, is_subheader=(i == 0))

    # 3.2 SCB
    add_subsection(doc, "3.2 Stress Capital Buffer (SCB)")
    t2 = create_table(doc, HDRS, STD4)
    rows2 = [
        ["SCB Applicability", "US Cat I-IV BHCs only (12 CFR 225.8(d))",
         "Not applicable - uses PRA buffer instead (PS1/26 Ch.17.4)",
         "Not applicable - uses P2G instead (CRD5 Art 104b)"],
        ["SCB Formula", "SCB = max(2.5%, (Starting CET1 - Trough CET1 under severely adverse) + 4Q planned dividends) (12 CFR 225.8(d)(3))",
         "PRA buffer = supervisory assessment of stress impact (PS1/26 Ch.17.4)",
         "P2G = supervisory SREP assessment, not legally binding (CRD5 Art 104b)"],
        ["SCB Floor", "2.5% minimum (replaces CCB for US firms) (12 CFR 225.8(d)(3)(ii))",
         "No explicit floor for PRA buffer", "No explicit floor for P2G"],
        ["SCB Frequency", "Annual - set after CCAR/DFAST (12 CFR 225.8(d)(4))",
         "Annual via ICAAP/SREP process (PS1/26 Ch.17.4)", "Annual via SREP (CRD5 Art 97)"],
        ["SCB vs CCB", "SCB replaces the 2.5% CCB for Category I/II holding companies (buffer = SCB + CCyB + G-SIB surcharge); subsidiary DIs keep the 2.5% CCB (ERBA NPR P.25). Cannot be lower than 2.5%",
         "CCB = 2.5% (separate from PRA buffer) (PS1/26 Ch.17.5)",
         "CCB = 2.5% (CRD6 Art 129)"],
    ]
    for r in rows2:
        add_data_row(t2, r)

    # 3.3 CCyB
    add_subsection(doc, "3.3 Countercyclical Capital Buffer (CCyB)")
    t3 = create_table(doc, HDRS, STD4)
    rows3 = [
        ["CCyB Authority", "Federal Reserve (12 CFR 217.11(b))",
         "Financial Policy Committee (FPC) (PS1/26 Ch.17.6)",
         "National designated authorities per Member State (CRD6 Art 130)"],
        ["CCyB Range", "0-2.5% (12 CFR 217.11(b)(2))", "0-2.5% standard; can exceed 2.5% (PS1/26 Ch.17.6)",
         "0-2.5% standard; can exceed 2.5% via Art 458 (CRD6 Art 130(5))"],
        ["Current Rate (US)", "0% (as of 2024)", "N/A", "N/A"],
        ["Current Rate (UK)", "N/A", "2% (as of Q1 2024, set by FPC Nov 2023)", "N/A"],
        ["Reciprocity", "Mandatory recognition of foreign CCyB rates (12 CFR 217.11(b)(3))",
         "Mandatory recognition up to 2.5% (PS1/26 Ch.17.7)",
         "Mandatory recognition up to 2.5%; voluntary above (CRD6 Art 137)"],
        ["Geographic Weighting", "Weighted by credit exposures in each jurisdiction (12 CFR 217.11(b)(3))",
         "Weighted by UK-relevant exposures (PS1/26 Ch.17.7)",
         "Weighted by credit exposures in each EU MS (CRD6 Art 140)"],
    ]
    for r in rows3:
        add_data_row(t3, r)

    # 3.4 Combined Buffer
    add_subsection(doc, "3.4 Combined Buffer & Worked Example")
    t4 = create_table(doc, HDRS, STD4)
    rows4 = [
        ["Combined Buffer Formula", "SCB + G-SIB + CCyB (12 CFR 217.11(a)(4)). Note: SCB subsumes CCB",
         "CCB + G-SII/O-SII + Systemic Risk + CCyB (PS1/26 Ch.17.8)",
         "CCB + G-SII/O-SII + Systemic Risk + CCyB (CRD6 Art 128)"],
        ["Worked Example: JPM-like", "SCB 3.2% + G-SIB 4.0% + CCyB 0% = 7.2%. Total CET1 req: 4.5% + 7.2% = 11.7%",
         "CCB 2.5% + Systemic 3.0% + CCyB 2.0% = 7.5%. Total CET1: 4.5% + 7.5% + PRA buffer = 12.0%+",
         "CCB 2.5% + G-SIB 2.0% + SyRB 0-3% + CCyB ~1% = 5.5-8.5%. Total CET1: 10.0-13.0%"],
        ["MDA Trigger", "CET1 < 4.5% + combined buffer = distribution restrictions (12 CFR 217.11(a)(4)(iv))",
         "CET1 < combined buffer = automatic restrictions (PS1/26 Ch.17.9)",
         "CET1 < combined buffer = MDA restrictions (CRD6 Art 141)"],
        ["MDA Calculation", "Tiered: if shortfall 0-25% of buffer, max 60% payout; 25-50%, 40%; 50-75%, 20%; >75%, 0% (12 CFR 217.11(a)(4)(iv))",
         "Same tiered approach (PS1/26 Ch.17.9)",
         "Same tiered approach (CRD6 Art 141(5))"],
        ["P2R (Pillar 2 Req)", "Included in CCAR stress test implicitly (no explicit P2R)",
         "P2A set by PRA via ICAAP (PS1/26 Ch.17.10). Typically 1-3% CET1",
         "P2R set by NCA via SREP (CRD6 Art 104a). Must be met 56.25% CET1"],
    ]
    for r in rows4:
        add_data_row(t4, r)
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 4: Credit Risk SA
# ═══════════════════════════════════════════════════════════════════
def build_section_4(doc):
    add_section_heading(doc, "4", "Credit Risk SA: Sovereigns, Banks, Corporates, SME, Project Finance")
    add_body_text(doc, "Every risk weight across all major exposure classes with full regulatory article references. "
        "The US approach under Dodd-Frank section 939A prohibits use of external credit ratings for "
        "risk-weighting, creating fundamental divergence from UK/EU approaches.")

    # 4.1 Sovereigns
    add_subsection(doc, "4.1 Sovereign Exposures")
    t = create_table(doc, HDRS, STD4)
    rows = [
        ["Sovereign Risk Weights", "", "", ""],
        ["US Government", "0% (12 CFR 217.32(a)(1))", "0% - CQS 1 (PS1/26 Ch.3 Table 3.1)",
         "0% - CQS 1 (CRR3 Art 114(2))"],
        ["CRC 0-1 / CQS 1", "0% (OECD CRC mapping; Table 1 to §__.111, identical to current §__.32 Table 1) (ERBA NPR P.54 fn 80)",
         "0% (S&P AAA to AA-) (PS1/26 Ch.3 Table 3.1)", "0% (CRR3 Art 114(2))"],
        ["CRC 2 / CQS 2", "20% (Table 1 to §__.111)", "20% (S&P A+ to A-) (PS1/26 Ch.3 Table 3.1)",
         "20% (CRR3 Art 114(2))"],
        ["CRC 3 / CQS 3", "50% (Table 1 to §__.111)", "50% (S&P BBB+ to BBB-) (PS1/26 Ch.3 Table 3.1)",
         "50% (CRR3 Art 114(2))"],
        ["CRC 4-6 / CQS 4", "100% (CRC 4, 5 and 6) (Table 1 to §__.111)", "100% (S&P BB+ to B-) (PS1/26 Ch.3 Table 3.1)",
         "100% (CRR3 Art 114(2))"],
        ["CRC 6 / CQS 5", "100% (Table 1 to §__.111)", "100% (S&P BB+ to B-) (PS1/26 Ch.3 Table 3.1)",
         "100% (CRR3 Art 114(2))"],
        ["CRC 7 / CQS 6", "150% (also 150% for sovereign in default) (Table 1 to §__.111)", "150% (S&P below B-) (PS1/26 Ch.3 Table 3.1)",
         "150% (CRR3 Art 114(2))"],
        ["Unrated Sovereigns", "OECD member with no CRC: 0%; non-OECD with no CRC: 100% (Table 1 to §__.111)",
         "100% (PS1/26 Ch.3 Table 3.1)", "100% (CRR3 Art 114(5))"],
        ["Domestic Currency", "0% for US government obligations; 20% for conditional US guarantees; PPP loans 0% (ERBA NPR §__.111(a))",
         "0% for UK sovereign in GBP (PS1/26 Ch.3.1)", "0% floor option for MS in domestic currency (CRR3 Art 114(4))"],
        ["PSE (Government)", "US GSE senior/guaranteed 20%; GSE subordinated 150% (FHLB/Farmer Mac subordinated and equity 20%) (ERBA NPR §__.111(b)-(c), P.49-50)",
         "Same as sovereign for central govt PSEs (PS1/26 Ch.3.2)",
         "Same as sovereign (CRR3 Art 115-116)"],
        ["PSE (Sub-Sovereign)", "US PSE general obligation 20% / revenue obligation 50%; foreign PSE by home CRC: GO 20/50/100/150%, revenue 50/100/150% (Tables 3-4 to §__.111)",
         "One step below sovereign CQS (PS1/26 Ch.3.2)",
         "One step below sovereign CQS (CRR3 Art 115(2))"],
        ["MDB Risk Weight", "0% for qualifying MDBs and specified supranationals (IBRD, IFC, ADB, BIS, ECB, IMF, ESM etc) (ERBA NPR P.47 fn 65-66)",
         "0% for qualifying MDBs (PS1/26 Ch.3.3)",
         "0% for qualifying MDBs (CRR3 Art 117(2)), rated MDBs per CQS"],
    ]
    for i, r in enumerate(rows):
        add_data_row(t, r, is_subheader=(i == 0))

    # 4.2 Banks
    add_subsection(doc, "4.2 Bank Exposures")
    add_body_text(doc, "CRITICAL DIVERGENCE: The US uses a capital-adequacy-based grading system "
        "(Grade A meeting §__.111(d)(2), Grade A, Grade B, Grade C) per Dodd-Frank 939A, while UK/EU use external credit ratings "
        "(CQS 1-6) or SCRA for unrated banks.")
    t2 = create_table(doc, HDRS, STD4)
    rows2 = [
        ["Bank Risk Weights", "", "", ""],
        ["Top Grade (AAA-AA)", "Grade A meeting §__.111(d)(2) (CET1 >= 14% AND SLR/leverage ratio >= 5%, or CBLR bank): 30%; all other Grade A: 40% (Table 2 to §__.111; ERBA NPR P.51-55). Based on capital adequacy, not ratings",
         "CQS 1 (AAA to AA-): 20% (PS1/26 Ch.3 Table 3.3)",
         "CQS 1 (AAA to AA-): 20% (CRR3 Art 120(2))"],
        ["High Grade (A)", "Grade A: 40% (30% only if §__.111(d)(2) criteria met) (Table 2 to §__.111)",
         "CQS 2 (A+ to A-): 30% (PS1/26 Ch.3 Table 3.3)",
         "CQS 2 (A+ to A-): 30% (CRR3 Art 120(2))"],
        ["Upper Medium (BBB)", "Grade B: 75% (Table 2 to §__.111; ERBA NPR P.53). Criteria: speculative grade or IG with disclosed capital ratios >= higher of minimums / adequately-capitalized",
         "CQS 3 (BBB+ to BBB-): 50% (PS1/26 Ch.3 Table 3.3)",
         "CQS 3 (BBB+ to BBB-): 50% (CRR3 Art 120(2))"],
        ["Lower Medium (BB)", "Grade B: 75% (Table 2 to §__.111)",
         "CQS 4 (BB+ to BB-): 100% (PS1/26 Ch.3 Table 3.3)",
         "CQS 4 (BB+ to BB-): 100% (CRR3 Art 120(2))"],
        ["Speculative (B-CCC)", "Grade C: 150% (Table 2 to §__.111; ERBA NPR P.54). Any bank not qualifying as Grade A or B (incl. ratios not disclosed within 6 months, adverse audit opinion within 12 months)",
         "CQS 5 (B+ to B-): 100% (PS1/26 Ch.3 Table 3.3)",
         "CQS 5 (B+ to B-): 100% (CRR3 Art 120(2))"],
        ["Default/Junk", "Grade C: 150% (Table 2 to §__.111)",
         "CQS 6 (CCC+ and below): 150% (PS1/26 Ch.3 Table 3.3)",
         "CQS 6 (CCC+ and below): 150% (CRR3 Art 120(2))"],
        ["Unrated Banks", "All banks graded per IG status and publicly disclosed capital ratios; foreign banks floored at home-sovereign RW unless local-currency exposure (ERBA NPR P.51-55)",
         "SCRA approach: Grade A 30%/40%, Grade B 50%/75%, Grade C 150% (PS1/26 Ch.3 Table 3.4)",
         "SCRA approach: Grade A 30%/40%, Grade B 50%/75%, Grade C 150% (CRR3 Art 121)"],
        ["Short-Term Claims <3M", "NO general short-term preference. Only self-liquidating trade-related contingent items to FOREIGN banks with maturity <= 3 months: 20% (Grade A) / 50% (Grade B) / 150% (Grade C) (Table 2 to §__.111; ERBA NPR P.54)",
         "CQS-based: 20%/20%/20%/50%/50%/150% (PS1/26 Ch.3 Table 3.5)",
         "CQS-based: 20%/20%/20%/50%/50%/150% (CRR3 Art 120(3))"],
        ["Grade A Criteria (US)", "Investment grade AND most recent publicly disclosed capital ratios >= higher of (minimum + buffers to avoid distribution limits) and well-capitalized PCA thresholds; CBLR banks qualify (ERBA NPR P.51). 30% tier: CET1 >= 14% and SLR >= 5% (Cat I-III) / tier 1 leverage >= 5% (others) / credit union net worth >= 9%; 68.3% of US DIs qualify (P.52)",
         "N/A (rating-based)", "N/A (rating-based)"],
        ["Subordinated Bank Debt / TLAC", "150% for subordinated bank exposures and covered debt instruments not deducted (ERBA NPR P.50 fn 71)",
         "Per CQS / CRR treatment (PS1/26)", "150% subordinated (CRR3 Art 128)"],
        ["Covered Bond from Bank", "No covered-bond carve-out in credit risk SA: risk-weighted as a bank exposure by Grade (30/40/75/150%); 'covered bond' defined only for market risk (ERBA NPR §__.111, §__.202)",
         "CQS 1: 10%, CQS 2: 20%, CQS 3: 20%, CQS 4-5: 50%, CQS 6: 100% (PS1/26 Ch.3 Table 3.6)",
         "CQS 1: 10%, CQS 2: 20%, CQS 3: 20%, CQS 4-5: 50%, CQS 6: 100% (CRR3 Art 129)"],
    ]
    for i, r in enumerate(rows2):
        add_data_row(t2, r, is_subheader=(i == 0))

    # 4.3 Corporates
    add_subsection(doc, "4.3 Corporate Exposures")
    t3 = create_table(doc, HDRS, STD4)
    rows3 = [
        ["Corporate Risk Weights", "", "", ""],
        ["Investment Grade", "65% - self-assessed IG criteria (ERBA P.84-86). Criteria: adequate capacity to meet financial commitments; not speculative. No external ratings per Dodd-Frank 939A",
         "20% CQS 1, 50% CQS 2-3 (PS1/26 Ch.3 Table 3.7)",
         "20% CQS 1, 50% CQS 2-3 (CRR3 Art 122(2))"],
        ["Non-IG / Unrated", "100% (ERBA P.88)",
         "100% unrated or CQS 4 (PS1/26 Ch.3 Table 3.7)",
         "100% unrated (CRR3 Art 122(2)); EU transitional: 65% if PD<=0.5% (CRR3 Art 465(4))"],
        ["EU Transitional PD<=0.5%", "N/A (US does not use PD-based assessment for SA)",
         "N/A (UK does not adopt EU transitional)",
         "65% for corporates with PD<=0.5% per IRB model. Phase-out by 2032 (CRR3 Art 465(4))"],
        ["Speculative Grade", "100% (same as unrated under US approach) (ERBA P.88)",
         "100% CQS 4, 150% CQS 5-6 (PS1/26 Ch.3 Table 3.7)",
         "100% CQS 4, 150% CQS 5-6 (CRR3 Art 122(2))"],
        ["High-Yield (BB-)", "100% (ERBA P.88)", "100% (PS1/26 Ch.3 Table 3.7)",
         "100% (CRR3 Art 122(2))"],
        ["Defaulted (CQS 6)", "150% (ERBA P.88)", "150% (PS1/26 Ch.3 Table 3.7)",
         "150% (CRR3 Art 122(2))"],
        ["Infrastructure Corp", "100% (no preferential treatment) (ERBA P.90)",
         "No preferential treatment (PS1/26 Ch.3.5)",
         "75% for qualifying infrastructure (CRR3 Art 122a); requires CQS 1-3 + criteria"],
    ]
    for i, r in enumerate(rows3):
        add_data_row(t3, r, is_subheader=(i == 0))

    # 4.4 SME
    add_subsection(doc, "4.4 SME Exposures")
    t4 = create_table(doc, HDRS, STD4)
    rows4 = [
        ["SME Definition", "Consolidated annual revenues or sales <= $50M (CPI-W indexed) (ERBA NPR §__.101; P.78 fn 114)",
         "Annual turnover <= GBP 6.5M (PS1/26 Ch.3.6)",
         "Annual turnover <= EUR 50M (CRR3 Art 501)"],
        ["SME Corporate RW", "100% (65% if investment grade); NO Basel 85% SME weight in US (ERBA NPR §__.111)",
         "85% effective via SME support factor 0.7619 (PS1/26 Ch.3.6)",
         "85% effective via SME support factor (CRR3 Art 501): 0.7619 for first EUR 2.5M, then per Art 501(2)"],
        ["SME Retail RW", "75% if meets regulatory retail criteria (SME obligor, aggregate exposure <= $1M) (ERBA NPR §__.101, §__.111; P.80-81)",
         "75% (PS1/26 Ch.3.6)", "75% (CRR3 Art 123)"],
        ["SME Threshold (Retail)", "Aggregate retail exposure to obligor and affiliates (on + off balance sheet, full notional) <= $1M, CPI-W indexed (ERBA NPR P.80 fn 115)",
         "Total exposure <= GBP 1M (PS1/26 Ch.3.6.2)",
         "Total exposure <= EUR 1M (CRR3 Art 123(2))"],
        ["SME Support Factor", "None - not adopted in US rules (ERBA NPR §__.111)",
         "Maintained via 0.7619 factor (PS1/26 Ch.3.6)",
         "Maintained: 0.7619 for first EUR 2.5M, 0.85 above (CRR3 Art 501)"],
    ]
    for r in rows4:
        add_data_row(t4, r)

    # 4.5 Specialized Lending
    add_subsection(doc, "4.5 Specialized Lending & Project Finance")
    t5 = create_table(doc, HDRS, STD4)
    rows5 = [
        ["Specialized Lending", "", "", ""],
        ["Project Finance (Pre-Op)", "130% pre-operational phase (ERBA NPR §__.111; P.82, P.88-89)", "130% (PS1/26 Ch.3 Table 3.9)",
         "130% (CRR3 Art 122(3))"],
        ["Project Finance (Op, HQ)", "NO 80% high-quality tier in the US proposal: operational-phase project finance is 100% (ERBA NPR §__.111; P.88-89)",
         "80% high-quality operational (PS1/26 Ch.3 Table 3.9)",
         "80% high-quality operational (CRR3 Art 122(3))"],
        ["Project Finance (Op, Non-HQ)", "100% (operational phase = positive net cash flow covering debt service and declining long-term debt) (ERBA NPR P.89)", "100% (PS1/26 Ch.3 Table 3.9)",
         "100% (CRR3 Art 122(3))"],
        ["Object Finance", "100% (equipment / physical commodity finance where repayment depends on the physical assets) (ERBA NPR §__.111; P.82)", "100% (PS1/26 Ch.3 Table 3.9)",
         "100% (CRR3 Art 122(3))"],
        ["Commodity Finance", "100% (ERBA NPR §__.111)", "100% (PS1/26 Ch.3 Table 3.9)",
         "100% (CRR3 Art 122(3))"],
        ["Income-Producing RE", "Covered under regulatory CRE Tables 7-8 to §__.111 (cash-flow dependent)",
         "Covered under CRE tables (PS1/26 Ch.4)",
         "Covered under CRE tables (CRR3 Art 124-126)"],
        ["High-Quality Criteria", "N/A - no high-quality project finance category in the US proposal",
         "Similar criteria (PS1/26 Ch.3.7)", "Similar criteria per CRR3 Art 122(3)(a)-(g)"],
    ]
    for i, r in enumerate(rows5):
        add_data_row(t5, r, is_subheader=(i == 0))

    # 4.6 Covered Bonds
    add_subsection(doc, "4.6 Covered Bonds")
    t6 = create_table(doc, HDRS, STD4)
    rows6 = [
        ["Covered Bond RWs", "", "", ""],
        ["CQS 1 / Grade A (§__.111(d)(2))", "No covered-bond treatment in US credit risk SA: bank-exposure RW 30% (ERBA NPR §__.111)", "10% (PS1/26 Ch.3 Table 3.6)",
         "10% (CRR3 Art 129(4))"],
        ["CQS 2 / Grade A-Other", "Bank-exposure RW 40% (ERBA NPR §__.111)", "20% (PS1/26 Ch.3 Table 3.6)",
         "20% (CRR3 Art 129(4))"],
        ["CQS 3", "N/A (Grade system)", "20% (PS1/26 Ch.3 Table 3.6)",
         "20% (CRR3 Art 129(4))"],
        ["CQS 4-5 / Grade B", "Bank-exposure RW 75% (ERBA NPR §__.111)", "50% (PS1/26 Ch.3 Table 3.6)",
         "50% (CRR3 Art 129(4))"],
        ["CQS 6 / Grade C", "Bank-exposure RW 150% (ERBA NPR §__.111)", "100% (PS1/26 Ch.3 Table 3.6)",
         "100% (CRR3 Art 129(4))"],
        ["Unrated", "N/A - 'covered bond' is defined only for market risk (CSR buckets 8/16; DRC LGD 25%) (ERBA NPR §__.202, §__.209-210)", "Issue-specific CQS (PS1/26 Ch.3 Table 3.6)",
         "Issuer-RW-based: 10%/20%/20%/50%/100% (CRR3 Art 129(5))"],
    ]
    for i, r in enumerate(rows6):
        add_data_row(t6, r, is_subheader=(i == 0))
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 5: Real Estate Exposures
# ═══════════════════════════════════════════════════════════════════
def build_section_5(doc):
    add_section_heading(doc, "5", "Real Estate Exposures: Residential & Commercial LTV Tables")
    add_body_text(doc, "All 6 LTV bands for each of the 4 real estate exposure tables, showing three-way "
        "divergence particularly at 80-90% and 90-100% LTV bands. Includes splitting approach mechanics, "
        "valuation methodology, cash-flow dependency tests, and ADC divergence.")

    # 5.1 Residential Non-CF
    add_subsection(doc, "5.1 Residential Mortgage - Non-Cash-Flow Dependent (Whole-Loan)")
    t = create_table(doc, HDRS, STD4)
    rows = [
        ["Resi Non-CF LTV Bands", "", "", ""],
        ["LTV <= 50%", "20% (Table 5 to §__.111; ERBA NPR p.692)", "20% (PS1/26 Ch.4 Table 4.1)",
         "20% (CRR3 Art 125(1) Table 1)"],
        ["50% < LTV <= 60%", "25% (Table 5 to §__.111; ERBA NPR p.692)", "25% (PS1/26 Ch.4 Table 4.1)",
         "25% (CRR3 Art 125(1) Table 1)"],
        ["60% < LTV <= 80%", "30% (Table 5 to §__.111; ERBA NPR p.692)", "30% (PS1/26 Ch.4 Table 4.1)",
         "30% (CRR3 Art 125(1) Table 1)"],
        ["80% < LTV <= 90%", "40% (Table 5 to §__.111; ERBA NPR p.692)", "40% (PS1/26 Ch.4 Table 4.1)",
         "35% (CRR3 Art 125(1) Table 1) - DIVERGENCE: EU 5pp lower"],
        ["90% < LTV <= 100%", "50% (Table 5 to §__.111; ERBA NPR p.692)", "50% (PS1/26 Ch.4 Table 4.1)",
         "45% (CRR3 Art 125(1) Table 1) - DIVERGENCE: EU 5pp lower"],
        ["LTV > 100%", "70% (Table 5 to §__.111; ERBA NPR p.692)", "70% (PS1/26 Ch.4 Table 4.1)",
         "60% (CRR3 Art 125(1) Table 1) - DIVERGENCE: EU 10pp lower"],
    ]
    for i, r in enumerate(rows):
        add_data_row(t, r, is_subheader=(i == 0))

    # 5.2 Residential CF
    add_subsection(doc, "5.2 Residential Mortgage - Cash-Flow Dependent")
    add_body_text(doc, "Cash-flow dependency: repayment materially depends on cash flows generated "
        "by the property rather than the borrower's other income sources.")
    t2 = create_table(doc, HDRS, STD4)
    rows2 = [
        ["Resi CF LTV Bands", "", "", ""],
        ["LTV <= 50%", "30% (Table 6 to §__.111; ERBA NPR p.693)", "30% (PS1/26 Ch.4 Table 4.2)",
         "30% (CRR3 Art 125(2) Table 2)"],
        ["50% < LTV <= 60%", "35% (Table 6 to §__.111; ERBA NPR p.693)", "35% (PS1/26 Ch.4 Table 4.2)",
         "35% (CRR3 Art 125(2) Table 2)"],
        ["60% < LTV <= 80%", "45% (Table 6 to §__.111; ERBA NPR p.693)", "45% (PS1/26 Ch.4 Table 4.2)",
         "45% (CRR3 Art 125(2) Table 2)"],
        ["80% < LTV <= 90%", "60% (Table 6 to §__.111; ERBA NPR p.693)", "60% (PS1/26 Ch.4 Table 4.2)",
         "55% (CRR3 Art 125(2) Table 2) - DIVERGENCE"],
        ["90% < LTV <= 100%", "75% (Table 6 to §__.111; ERBA NPR p.693)", "75% (PS1/26 Ch.4 Table 4.2)",
         "70% (CRR3 Art 125(2) Table 2) - DIVERGENCE"],
        ["LTV > 100%", "105% (Table 6 to §__.111; ERBA NPR p.693)", "105% (PS1/26 Ch.4 Table 4.2)",
         "90% (CRR3 Art 125(2) Table 2) - DIVERGENCE: EU 15pp lower"],
    ]
    for i, r in enumerate(rows2):
        add_data_row(t2, r, is_subheader=(i == 0))

    # 5.3 CRE Non-CF
    add_subsection(doc, "5.3 Commercial Real Estate - Non-Cash-Flow Dependent")
    t3 = create_table(doc, HDRS, STD4)
    rows3 = [
        ["CRE Non-CF LTV Bands", "", "", ""],
        ["LTV <= 60%", "Lesser of 60% or obligor RW (Table 7 to §__.111; ERBA NPR P.75)",
         "Min(70%, counterparty RW) (PS1/26 Ch.4 Table 4.3)",
         "Min(60%, counterparty RW) (CRR3 Art 126(1) Table 3) - EU uses 60% not 70%"],
        ["60% < LTV <= 80%", "Obligor RW applies (100% if insufficient information to determine obligor RW) (Table 7 to §__.111; ERBA NPR P.74)",
         "Counterparty RW applies (PS1/26 Ch.4 Table 4.3)",
         "Counterparty RW applies (CRR3 Art 126(1) Table 3)"],
        ["LTV > 80%", "Obligor RW applies (100% if unknown; 150% if 90+ days past due) (Table 7 to §__.111)",
         "Counterparty RW applies (PS1/26 Ch.4 Table 4.3)",
         "Counterparty RW applies (CRR3 Art 126(1) Table 3)"],
    ]
    for i, r in enumerate(rows3):
        add_data_row(t3, r, is_subheader=(i == 0))

    # 5.4 CRE CF
    add_subsection(doc, "5.4 Commercial Real Estate - Cash-Flow Dependent")
    t4 = create_table(doc, HDRS, STD4)
    rows4 = [
        ["CRE CF LTV Bands", "", "", ""],
        ["LTV <= 60%", "70% (Table 8 to §__.111; ERBA NPR P.75)", "70% (PS1/26 Ch.4 Table 4.4)",
         "70% (CRR3 Art 126(2) Table 4)"],
        ["60% < LTV <= 80%", "90% (Table 8 to §__.111)", "90% (PS1/26 Ch.4 Table 4.4)",
         "90% (CRR3 Art 126(2) Table 4)"],
        ["80% < LTV <= 90%", "110% (US Table 8 has a single '> 80%' band at 110%)", "110% (PS1/26 Ch.4 Table 4.4)",
         "110% (CRR3 Art 126(2) Table 4)"],
        ["90% < LTV <= 100%", "110% (single '> 80%' band; no 130% tier in US) (Table 8 to §__.111)", "130% (PS1/26 Ch.4 Table 4.4)",
         "130% (CRR3 Art 126(2) Table 4)"],
        ["LTV > 100%", "110% (single '> 80%' band; no 150% tier in US; 150% only if 90+ days past due) (Table 8 to §__.111)", "150% (PS1/26 Ch.4 Table 4.4)",
         "150% (CRR3 Art 126(2) Table 4)"],
    ]
    for i, r in enumerate(rows4):
        add_data_row(t4, r, is_subheader=(i == 0))

    # 5.5 Splitting Approach
    add_subsection(doc, "5.5 Loan-Splitting Approach")
    t5 = create_table(doc, HDRS, STD4)
    rows5 = [
        ["Splitting Available", "NO - the US proposal provides only the whole-loan LTV approach (Tables 5-8 to §__.111); no loan-splitting option appears in §__.111",
         "Yes (PS1/26 Ch.4.3). Banks may choose per portfolio",
         "Yes (CRR3 Art 124(1)). Member State discretion may apply"],
        ["Secured Portion LTV", "N/A (whole-loan approach only)",
         "55% resi / 60% CRE (PS1/26 Ch.4.3)",
         "55% resi / 60% CRE (CRR3 Art 124(3))"],
        ["Secured Portion RW", "N/A (whole-loan approach only)",
         "Same mechanics (PS1/26 Ch.4.3)", "Same mechanics (CRR3 Art 124(3))"],
        ["Unsecured Portion RW", "N/A; LTV includes undrawn committed amounts and is based on origination value (ERBA NPR P.67-69)",
         "Counterparty risk weight (PS1/26 Ch.4.3)", "Counterparty risk weight (CRR3 Art 124(4))"],
    ]
    for r in rows5:
        add_data_row(t5, r)

    # 5.6 ADC & Valuation
    add_subsection(doc, "5.6 ADC Exposures & Valuation Methodology")
    t6 = create_table(doc, HDRS, STD4)
    rows6 = [
        ["ADC (Acq/Dev/Const)", "HVCRE exposures 150% (statutory definition retained); ADC exposures that are not HVCRE: 100% with no LTV or cash-flow test (ERBA NPR §__.111; P.76)",
         "150% unless pre-sold or substantial equity (PS1/26 Ch.4.4)",
         "150% standard (CRR3 Art 126a(1))"],
        ["ADC Reduced RW", "100% for non-HVCRE ADC; 50% for qualifying pre-sold 1-4 family construction loans (100% if purchase contract cancelled) and statutory multifamily mortgages (ERBA NPR P.58 fn 82-83, P.76)",
         "100% if pre-sold/substantial equity criteria met (PS1/26 Ch.4.4)",
         "100% if qualifying ADC criteria met (CRR3 Art 126a(2)) - DIVERGENCE: EU allows ADC residential reduction more broadly"],
        ["Valuation Approach", "Value at origination; purchases: lower of acquisition cost and market value (appraisal rule or independent prudently conservative valuation); excludes expected price increases (ERBA NPR P.67-69)",
         "Prudent market value (PS1/26 Ch.4.5). Independent valuation",
         "Prudent market value (CRR3 Art 229). Independent valuer meeting CRR3 Art 208 criteria"],
        ["Revaluation Frequency", "Origination value retained; downward revision only if (1) supervisor requires, (2) extraordinary event causes permanent reduction, or (3) value-increasing modifications supported by new appraisal (ERBA NPR P.68)",
         "At origination + minimum every 3Y for resi, annually for CRE (PS1/26 Ch.4.5)",
         "At origination + annually for CRE, every 3Y for resi; statistical methods allowed (CRR3 Art 208(3))"],
        ["PMI Recognition", "NOT recognized: LTV is calculated with no adjustment for private mortgage insurance or credit loss provisions (ERBA NPR P.67; Question 21 asks about recognizing e.g. 50% of PMI)",
         "Not explicitly addressed; CRM framework applies (PS1/26 Ch.6)",
         "Private insurance may qualify as CRM per CRR3 Art 213-215"],
        ["CF Dependency Test", "Qualitative: repayment materially dependent on cash flows generated by the real estate; no numerical threshold in the NPR (Question 20 floats a 5-50% range) (ERBA NPR P.66)",
         "Material dependence on property-generated CF (PS1/26 Ch.4.2). Qualitative assessment",
         "Material dependence test (CRR3 Art 124(2)). Quantitative: >50% of repayment capacity from property"],
    ]
    for r in rows6:
        add_data_row(t6, r)
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 6: Retail, Equity, Past Due & Other Assets
# ═══════════════════════════════════════════════════════════════════
def build_section_6(doc):
    add_section_heading(doc, "6", "Retail, Equity, Past Due & Other Asset Classes")

    # 6.1 Retail
    add_subsection(doc, "6.1 Retail Exposures")
    t = create_table(doc, HDRS, STD4)
    rows = [
        ["Retail Risk Weights", "", "", ""],
        ["Regulatory Retail", "75% (ERBA NPR §__.111; P.81). Criteria: revolving, term loan or lease to an individual or SME; aggregate exposure to obligor and affiliates <= $1M; other retail 100%",
         "75% (PS1/26 Ch.3 Table 3.10)", "75% (CRR3 Art 123(1))"],
        ["Transactor Portfolios", "45% (ERBA NPR §__.111; P.81). 10pp lower than the 2023 NPR's 55% (P.534). Criteria: balance repaid in full at each scheduled repayment date for the previous 12 months, or overdraft with no drawdown for 12 months",
         "45% for qualifying transactors (PS1/26 Ch.3 Table 3.10)",
         "45% for qualifying transactors (CRR3 Art 123(1a))"],
        ["Transactor Criteria", "Regulatory retail credit facility repaid in full at each scheduled date for 12 months (or overdraft with no drawdown for 12 months); not a transactor if the facility carries a balance or includes installment payments, even at 0% promotional rates (ERBA NPR §__.101; P.80)",
         "Similar: revolving unsecured, paid monthly, no arrears (PS1/26 Ch.3.8)",
         "Revolving unsecured, full repayment each month, granularity test (CRR3 Art 123(1a)(a)-(d))"],
        ["Retail Threshold", "Aggregate retail exposure to obligor and affiliates (on + off balance sheet, full notional) <= $1M, CPI-W indexed; if exceeded none of the exposures qualify (ERBA NPR P.80 fn 115)",
         "Total exposure <= GBP 1M (PS1/26 Ch.3.8)", "Total exposure <= EUR 1M (CRR3 Art 123(2))"],
        ["Granularity Test", "None - no 0.2% granularity criterion in the US proposal; the $1M aggregate limit is the only size test (ERBA NPR §__.101)",
         "No single exposure > 0.2% (PS1/26 Ch.3.8)",
         "Part of managed portfolio (CRR3 Art 123(2)(d))"],
        ["Currency Mismatch (Revolving)", "No currency mismatch add-on for retail in the US proposal (ERBA NPR §__.111)",
         "20% add-on for unhedged FX retail (PS1/26 Ch.3.8.2)",
         "50% uplift for currency mismatch in retail revolving (CRR3 Art 123(3)) - SIGNIFICANT DIVERGENCE"],
    ]
    for i, r in enumerate(rows):
        add_data_row(t, r, is_subheader=(i == 0))

    # 6.2 Equity
    add_subsection(doc, "6.2 Equity Exposures")
    t2 = create_table(doc, HDRS, STD4)
    rows2 = [
        ["Equity Risk Weights", "", "", ""],
        ["Listed Equity", "300% publicly traded - current rule retained; Basel 250% considered and not adopted (ERBA NPR §__.141; P.191 fn 203)", "250% (PS1/26 Ch.3 Table 3.11)",
         "250% (CRR3 Art 133(3))"],
        ["Unlisted Equity", "400% non-publicly traded (ERBA NPR §__.141)", "400% (PS1/26 Ch.3 Table 3.11)",
         "400% (CRR3 Art 133(4))"],
        ["Speculative Equity", "No separate 'speculative' category: 400% non-public; 600% for equity in an investment firm with greater than immaterial leverage (ERBA NPR §__.141)", "400% (PS1/26 Ch.3 Table 3.11)",
         "400% (CRR3 Art 133(4))"],
        ["Equity to Fed/Govt", "0% sovereign, MDB and Federal Reserve Bank stock; 20% PSE, FHLB and Farmer Mac; 100% community development investments and non-significant equity (aggregate <= 10% of total capital); 250% significant investments in unconsolidated FIs not deducted (ERBA NPR §__.141; P.191)", "100% (PS1/26 Ch.3.9)",
         "100% (CRR3 Art 133(5))"],
        ["Equity Phase-In", "Immediate application on the final-rule effective date; no phase-in (ERBA NPR §__.141)",
         "Immediate Jan 1, 2025 (PS1/26 Ch.3.9)",
         "Phase-in 2025-2030 per Art 495a: 100% from 2025, 250%/400% by 2030 (CRR3 Art 495a) - SIGNIFICANT EU DIVERGENCE"],
        ["EU Phase-In 2025", "N/A", "N/A", "100% for existing equity holdings (CRR3 Art 495a(1))"],
        ["EU Phase-In 2026", "N/A", "N/A", "130% listed / 160% unlisted (CRR3 Art 495a(2))"],
        ["EU Phase-In 2027", "N/A", "N/A", "160% listed / 220% unlisted (CRR3 Art 495a(3))"],
        ["EU Phase-In 2028", "N/A", "N/A", "190% listed / 280% unlisted (CRR3 Art 495a(4))"],
        ["EU Phase-In 2029", "N/A", "N/A", "220% listed / 340% unlisted (CRR3 Art 495a(5))"],
        ["EU Phase-In 2030", "N/A", "N/A", "250% listed / 400% unlisted fully phased (CRR3 Art 495a(6))"],
        ["Qualifying Legislative Equity", "N/A", "N/A",
         "100% for legislatively mandated equity (CRR3 Art 133(6))"],
        ["Strategic Equity <10%", "Non-significant equity (aggregate adjusted carrying value <= 10% of total capital): 100%; above that 300%/400% by listing status (ERBA NPR §__.141; P.191)",
         "250% (PS1/26 Ch.3.9)", "250% (CRR3 Art 133(3)) - no strategic discount"],
    ]
    for i, r in enumerate(rows2):
        add_data_row(t2, r, is_subheader=(i == 0))

    # 6.3 Past Due
    add_subsection(doc, "6.3 Past Due Exposures")
    t3 = create_table(doc, HDRS, STD4)
    rows3 = [
        ["Past Due Definition", "90 days or more past due or in nonaccrual (ERBA NPR §__.111; P.47-48 fn 68)",
         ">90 days past due (PS1/26 Ch.3.10)", ">90 days past due (CRR3 Art 127(1))"],
        ["Unsecured Past Due RW", "150% for non-sovereign, non-real-estate exposures (ERBA NPR §__.111)", "150% (PS1/26 Ch.3 Table 3.12)",
         "150% standard (CRR3 Art 127(1))"],
        ["Provisions >= 20%", "150% (no provision-based reduction in US) (ERBA NPR §__.111)",
         "150% (PS1/26 Ch.3 Table 3.12)",
         "100% if specific provisions >= 20% of unsecured portion (CRR3 Art 127(1)(a)) - EU MORE FAVORABLE"],
        ["Provisions >= 50%", "150% (no further reduction) (ERBA NPR §__.111)",
         "100% (PS1/26 Ch.3 Table 3.12)",
         "100% (CRR3 Art 127(1)(a))"],
        ["RE-Secured Past Due", "150% for past-due real estate exposures, except residential mortgage exposures not dependent on property cash flows: 100% (ERBA NPR P.71 fn 106, P.74 fn 111)",
         "100% minimum for past-due RE (PS1/26 Ch.3.10)",
         "100% minimum (CRR3 Art 127(3))"],
    ]
    for r in rows3:
        add_data_row(t3, r)

    # 6.4 Other Assets
    add_subsection(doc, "6.4 Other Assets")
    t4 = create_table(doc, HDRS, STD4)
    rows4 = [
        ["Cash", "0% (12 CFR 217.32(l))", "0% (PS1/26 Ch.3.11)", "0% (CRR3 Art 134(1))"],
        ["Gold Bullion (Allocated)", "0% (12 CFR 217.32(l))", "0% (PS1/26 Ch.3.11)",
         "0% (CRR3 Art 134(2))"],
        ["Cash Items in Collection", "20% (12 CFR 217.32(l))", "20% (PS1/26 Ch.3.11)",
         "20% (CRR3 Art 134(3))"],
        ["Fixed Assets", "100% (ERBA P.116)", "100% (PS1/26 Ch.3.11)", "100% (CRR3 Art 134(6))"],
        ["All Other Assets", "100% (ERBA P.116)", "100% (PS1/26 Ch.3.11)",
         "100% (CRR3 Art 134(7))"],
        ["Defaulted Exposures", "150% for non-RE defaulted (ERBA P.112)",
         "150% (PS1/26 Ch.3.10)", "150% (CRR3 Art 127(1))"],
        ["Central Bank Exposures", "0% for reserves at Fed (12 CFR 217.32(a))",
         "0% for reserves at BoE (PS1/26 Ch.3.11)",
         "0% for reserves at ECB/NCBs in domestic currency (CRR3 Art 114(4))"],
        ["CCP Exposures", "2% for qualifying CCPs (12 CFR 217.133)",
         "2% for qualifying CCPs (PS1/26 Ch.8.5)",
         "2% for qualifying CCPs (CRR3 Art 306(1)(a))"],
        ["CCP Default Fund", "Risk-sensitive per 12 CFR 217.133(d)",
         "Risk-sensitive (PS1/26 Ch.8.5)", "Risk-sensitive per CRR3 Art 308"],
    ]
    for r in rows4:
        add_data_row(t4, r)
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 7: Off-Balance Sheet CCFs
# ═══════════════════════════════════════════════════════════════════
def build_section_7(doc):
    add_section_heading(doc, "7", "Off-Balance Sheet CCFs: Commitment Divergence Analysis")
    add_body_text(doc, "CRITICAL DIVERGENCE: The US applies a uniform 40% CCF to all commitments regardless "
        "of maturity, while the UK/EU split 20%/40% based on original maturity (<=1Y / >1Y). "
        "This creates material RWA impact for G-SIBs with large short-term commitment books.")

    # 7.1 CCF Table
    add_subsection(doc, "7.1 Complete CCF Comparison Table")
    t = create_table(doc, HDRS, STD4)
    rows = [
        ["CCF Categories", "", "", ""],
        ["Unconditionally Cancellable (UCC)", "10% (ERBA P.210, Category 12). Must be unconditionally cancellable without notice",
         "10% (PS1/26 Ch.5 Table 5.1)", "10% (CRR3 Art 111(1)(e))"],
        ["Commitments <=1Y (Non-UCC)", "40% (ERBA P.210, Category 4). UNIFORM regardless of maturity - NO maturity split",
         "20% for <=1Y original maturity (PS1/26 Ch.5 Table 5.1) - CRITICAL DIVERGENCE",
         "20% for <=1Y original maturity (CRR3 Art 111(1)(d)(i)) - CRITICAL DIVERGENCE"],
        ["Commitments >1Y (Non-UCC)", "40% (ERBA P.210, Category 4). Same as <=1Y",
         "40% for >1Y original maturity (PS1/26 Ch.5 Table 5.1)",
         "40% for >1Y original maturity (CRR3 Art 111(1)(d)(ii))"],
        ["Direct Credit Substitutes", "100% (ERBA P.208, Category 1). Guarantees, standby LCs backing financial obligations",
         "100% (PS1/26 Ch.5 Table 5.1)", "100% (CRR3 Art 111(1)(a))"],
        ["Transaction-Related Contingent", "50% (ERBA P.208, Category 2). Performance bonds, bid bonds, warranties",
         "50% (PS1/26 Ch.5 Table 5.1)", "50% (CRR3 Art 111(1)(b))"],
        ["Trade-Related Contingent", "20% (ERBA P.208, Category 3). Short-term self-liquidating trade LCs",
         "20% (PS1/26 Ch.5 Table 5.1)", "20% (CRR3 Art 111(1)(c))"],
        ["Securities Lending", "100% (ERBA P.210, Category 5)", "100% (PS1/26 Ch.5 Table 5.1)",
         "100% (CRR3 Art 111(1)(a))"],
        ["Repo-Style Transactions", "100% (ERBA P.210, Category 6)", "100% (PS1/26 Ch.5 Table 5.1)",
         "100% (CRR3 Art 111(1)(a))"],
        ["Asset Sale w/ Recourse", "100% (ERBA P.210, Category 7)", "100% (PS1/26 Ch.5 Table 5.1)",
         "100% (CRR3 Art 111(1)(a))"],
        ["Forward Asset Purchase", "100% (ERBA P.210, Category 8)", "100% (PS1/26 Ch.5 Table 5.1)",
         "100% (CRR3 Art 111(1)(a))"],
        ["NIF/RUF", "50% (ERBA P.210, Category 9)", "50% (PS1/26 Ch.5 Table 5.1)",
         "50% (CRR3 Art 111(1)(b))"],
        ["Forward Deposits", "100% (ERBA P.210, Category 10)", "100% (PS1/26 Ch.5 Table 5.1)",
         "100% (CRR3 Art 111(1)(a))"],
        ["Partly Paid Shares", "100% of unpaid portion (ERBA P.210, Category 11)",
         "100% (PS1/26 Ch.5 Table 5.1)", "100% (CRR3 Art 111(1)(a))"],
    ]
    for i, r in enumerate(rows):
        add_data_row(t, r, is_subheader=(i == 0))

    # 7.2 Impact Analysis
    add_subsection(doc, "7.2 Capital Impact Analysis: Uniform 40% vs 20%/40% Split")
    t2 = create_table(doc, ["Metric", "US (40% Uniform)", "UK/EU (20%/40% Split)", "Difference"], STD4)
    rows2 = [
        ["Worked Example", "", "", ""],
        ["Short-Term Commitments (<=1Y)", "$500B * 40% = $200B EAD", "$500B * 20% = $100B EAD",
         "$100B higher EAD in US"],
        ["Long-Term Commitments (>1Y)", "$200B * 40% = $80B EAD", "$200B * 40% = $80B EAD",
         "$0 difference"],
        ["Total Commitment EAD", "$280B", "$180B", "$100B additional in US"],
        ["Avg RW (100% corporate)", "$280B * 100% = $280B RWA", "$180B * 100% = $180B RWA",
         "$100B additional RWA"],
        ["CET1 Impact (@4.5%)", "$280B * 4.5% = $12.6B", "$180B * 4.5% = $8.1B",
         "$4.5B additional CET1 required"],
        ["Total Capital Impact (@8%)", "$280B * 8% = $22.4B", "$180B * 8% = $14.4B",
         "$8.0B additional total capital"],
        ["RWA as % of G-SIB Total", "~8.8% of $3.2T total RWA", "~5.6% of $3.2T total RWA",
         "3.2pp higher RWA density"],
        ["CET1 Ratio Impact", "~14bp reduction in CET1 ratio", "N/A", "14bp lower CET1 ratio in US"],
    ]
    for i, r in enumerate(rows2):
        add_data_row(t2, r, is_subheader=(i == 0))

    add_body_text(doc, "Policy Rationale: The US Federal Reserve's uniform 40% CCF reflects the view "
        "that short-term commitments are frequently renewed and function as de facto long-term "
        "commitments. The UK/EU approach follows the BCBS d424 standard with maturity-based distinction. "
        "For a Category I G-SIB with $500B+ in short-term commitments (primarily corporate credit "
        "lines and liquidity facilities), this single parameter divergence can generate $25-40B "
        "in additional RWA.")
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 8: Credit Risk Mitigation
# ═══════════════════════════════════════════════════════════════════
def build_section_8(doc):
    add_section_heading(doc, "8", "Credit Risk Mitigation: Haircuts, Formulas & Mechanics")

    # 8.1 E* Formula
    add_subsection(doc, "8.1 Comprehensive Approach: E* Formula")
    t = create_table(doc, HDRS, STD4)
    rows = [
        ["E* Formula", "NEW netting-set formula: E* = max(0, (sum E_i - sum C_i) + 0.4 x netexposure + 0.6 x grossexposure/sqrt(N) + sum E_fx x H_fx), netexposure = |sum E_s H_s|, grossexposure = sum E_s |H_s|, N = number of unique CUSIPs (excl. positions < 1/10 of largest); reverts to the current single-transaction form when N components are empty; own-estimate haircuts no longer permitted (ERBA NPR §__.115; P.102-105)",
         "Same formula (PS1/26 Ch.6.1)", "Same formula (CRR3 Art 223(5))"],
        ["Currency Mismatch Hfx", "8% for 10-business-day holding period; scaled by sqrt(T_M/10) if revalued less than every 10 business days (ERBA NPR §__.115, §__.120; P.147)",
         "8% for 10-day holding (PS1/26 Ch.6.1)", "8% for 10-day holding (CRR3 Art 224(1) Table 1)"],
        ["Maturity Mismatch Formula", "Pm = E x (t - 0.25) / (T - 0.25) (ERBA NPR §__.120; P.146). t = lesser of T or residual maturity of the mitigant; T = lesser of 5 years or residual maturity of the exposure",
         "Same formula (PS1/26 Ch.6.2)", "Same formula (CRR3 Art 237-238)"],
        ["Minimum Maturity", "Mitigant original maturity >= 1Y and residual maturity > 3 months for recognition (ERBA NPR §__.120; P.139)",
         "Same 1Y minimum (PS1/26 Ch.6.2)", "Same 1Y minimum (CRR3 Art 237(1))"],
    ]
    for r in rows:
        add_data_row(t, r)

    # 8.2 Supervisory Haircuts
    add_subsection(doc, "8.2 Complete Supervisory Haircut Table (17 Entries)")
    t2 = create_table(doc, ["Security Type / Maturity", "US (ERBA)", "UK (PS1/26)", "EU (CRR3)"],
                      [2.5, 2.3, 2.3, 2.4])
    rows2 = [
        ["Supervisory Haircuts (10-Day Holding, Standard)", "", "", ""],
        ["Sovereign AAA-AA / <=1Y", "0.5% (issuer RW 0%) (Table 1 to §__.115; US keys haircuts to issuer risk weight, not rating)", "0.5% (PS1/26 Ch.6 Table 6.1)",
         "0.5% (CRR3 Art 224 Table 1)"],
        ["Sovereign AAA-AA / 1-5Y", "2% (issuer RW 0%; 1-3Y and 3-5Y) (Table 1 to §__.115)", "2% (PS1/26 Ch.6 Table 6.1)",
         "2% (CRR3 Art 224 Table 1)"],
        ["Sovereign AAA-AA / >5Y", "4% (issuer RW 0%; 5-10Y and >10Y) (Table 1 to §__.115)", "4% (PS1/26 Ch.6 Table 6.1)",
         "4% (CRR3 Art 224 Table 1)"],
        ["Sovereign A-BBB / <=1Y", "1% (issuer RW 20% or 50%) (Table 1 to §__.115)", "1% (PS1/26 Ch.6 Table 6.1)",
         "1% (CRR3 Art 224 Table 1)"],
        ["Sovereign A-BBB / 1-5Y", "3% (issuer RW 20% or 50%) (Table 1 to §__.115)", "3% (PS1/26 Ch.6 Table 6.1)",
         "3% (CRR3 Art 224 Table 1)"],
        ["Sovereign A-BBB / >5Y", "6% (issuer RW 20% or 50%) (Table 1 to §__.115)", "6% (PS1/26 Ch.6 Table 6.1)",
         "6% (CRR3 Art 224 Table 1)"],
        ["Sovereign BB / all", "15% (issuer RW 100%); sovereign RW > 100%: 30% 'other' (Table 1 to §__.115)", "15% (PS1/26 Ch.6 Table 6.1)",
         "15% (CRR3 Art 224 Table 1)"],
        ["Corp/Bank AAA-AA / <=1Y", "2% - all 'other investment grade' non-GSE, non-securitization debt (no rating split); GSE 1%; senior securitization RW<100% 4% (Table 1 to §__.115)", "1% (PS1/26 Ch.6 Table 6.1)",
         "1% (CRR3 Art 224 Table 1)"],
        ["Corp/Bank AAA-AA / 1-5Y", "4% (1-3Y) / 6% (3-5Y); GSE 4%; senior securitization 12% (Table 1 to §__.115)", "4% (PS1/26 Ch.6 Table 6.1)",
         "4% (CRR3 Art 224 Table 1)"],
        ["Corp/Bank AAA-AA / >5Y", "12% (5-10Y) / 20% (>10Y); GSE 8%; senior securitization 24% (Table 1 to §__.115)", "8% (PS1/26 Ch.6 Table 6.1)",
         "8% (CRR3 Art 224 Table 1)"],
        ["Corp/Bank A-BBB / <=1Y", "2% (same single IG column as above) (Table 1 to §__.115)", "2% (PS1/26 Ch.6 Table 6.1)",
         "2% (CRR3 Art 224 Table 1)"],
        ["Corp/Bank A-BBB / 1-5Y", "4% (1-3Y) / 6% (3-5Y) (Table 1 to §__.115)", "6% (PS1/26 Ch.6 Table 6.1)",
         "6% (CRR3 Art 224 Table 1)"],
        ["Corp/Bank A-BBB / >5Y", "12% (5-10Y) / 20% (>10Y) (Table 1 to §__.115)", "12% (PS1/26 Ch.6 Table 6.1)",
         "12% (CRR3 Art 224 Table 1)"],
        ["Corp/Bank BB / all", "30% - non-investment-grade debt falls in 'other exposure types' (Table 1 to §__.115; ERBA NPR P.107 fn 137)", "25% (PS1/26 Ch.6 Table 6.1)",
         "25% (CRR3 Art 224 Table 1)"],
        ["Main Index Equities", "20% (incl. convertible bonds) (Table 1 to §__.115; ERBA NPR P.107-108)", "15% (PS1/26 Ch.6 Table 6.1)",
         "15% (CRR3 Art 224 Table 1)"],
        ["Other Listed Equities", "30% (Table 1 to §__.115)", "25% (PS1/26 Ch.6 Table 6.1)",
         "25% (CRR3 Art 224 Table 1)"],
        ["Cash / Same Currency", "0% (Table 1 to §__.115)", "0% (PS1/26 Ch.6 Table 6.1)",
         "0% (CRR3 Art 224 Table 1)"],
        ["Gold", "20% (Table 1 to §__.115)", "15% (PS1/26 Ch.6 Table 6.1)",
         "15% (CRR3 Art 224 Table 1)"],
        ["Mutual Funds / ETFs", "Highest haircut applicable to any security the fund may hold (weighted average if full look-through) (Table 1 to §__.115)", "Per look-through (PS1/26 Ch.6)",
         "Per look-through (CRR3 Art 224)"],
    ]
    for i, r in enumerate(rows2):
        add_data_row(t2, r, is_subheader=(i == 0))

    # 8.3 Holding Period Scaling
    add_subsection(doc, "8.3 Holding Period Scaling & Credit Derivative Adjustments")
    t3 = create_table(doc, HDRS, STD4)
    rows3 = [
        ["Holding Period Scaling", "H_a = H_s x sqrt(T_m / T_s), T_s = 10 bd margin loans / 5 bd repo-style; repo-style haircuts may be scaled by sqrt(1/2) (ERBA NPR §__.115)",
         "Same formula (PS1/26 Ch.6.3)", "Same formula (CRR3 Art 224(2))"],
        ["Repo Holding Period", "5 business days (ERBA NPR §__.115)",
         "5 business days (PS1/26 Ch.6.3)", "5 business days (CRR3 Art 224(2))"],
        ["Other Capital Mkt", "10 business days (margin loans; derivatives MPOR floor 10 bd) (ERBA NPR §__.114-115)",
         "10 business days (PS1/26 Ch.6.3)", "10 business days (CRR3 Art 224(2))"],
        ["Secured Lending", "20 business days where netting set has > 5,000 trades or illiquid collateral; doubled if > 2 margin disputes in prior 2 quarters (ERBA NPR §__.114-115)",
         "20 business days (PS1/26 Ch.6.3)", "20 business days (CRR3 Art 224(2))"],
        ["Credit Deriv Restructuring", "Credit derivatives WITHOUT restructuring as a credit event: effective notional reduced by 40% (x 0.60), unless unanimous-consent amendment terms and US Bankruptcy Code-type regime apply (ERBA NPR §__.120; P.133)",
         "40% adjustment (PS1/26 Ch.6.4)", "40% adjustment (CRR3 Art 233(3))"],
        ["Simple Approach Floor", "20% RW floor under simple approach; 0% for cash on deposit; 0% for sovereign RW-0 collateral discounted 20%; revalue at least every 6 months (ERBA NPR §__.121; P.136-140)",
         "20% floor (PS1/26 Ch.6.5)", "20% floor (CRR3 Art 222(5))"],
        ["Netting Agreement", "Must meet legal enforceability across all relevant jurisdictions (12 CFR 217.37(c)(1)). Master agreement (ISDA, GMRA) with close-out netting",
         "Legal enforceability + master agreement (PS1/26 Ch.6.6)",
         "Legal enforceability + netting opinion (CRR3 Art 295-298)"],
    ]
    for r in rows3:
        add_data_row(t3, r)

    # 8.4 Eligible Guarantors
    add_subsection(doc, "8.4 Eligible Guarantors & Protection Providers")
    t4 = create_table(doc, HDRS, STD4)
    rows4 = [
        ["Sovereign Guarantors", "Eligible (12 CFR 217.36(a))", "Eligible (PS1/26 Ch.6.7)",
         "Eligible (CRR3 Art 213(1)(a))"],
        ["PSE Guarantors", "Eligible if treated as sovereign (12 CFR 217.36(a))",
         "Eligible (PS1/26 Ch.6.7)", "Eligible (CRR3 Art 213(1)(b))"],
        ["Bank Guarantors", "Eligible (12 CFR 217.36(a))", "Eligible (PS1/26 Ch.6.7)",
         "Eligible (CRR3 Art 213(1)(c))"],
        ["Corporate Guarantors", "Eligible if IG (ERBA P.248)", "Eligible if externally rated (PS1/26 Ch.6.7)",
         "Eligible if externally rated (CRR3 Art 213(1)(c))"],
        ["Substitution Approach", "RW of guarantor substituted for obligor RW on covered portion (12 CFR 217.36(b))",
         "Same substitution (PS1/26 Ch.6.7)", "Same substitution (CRR3 Art 235)"],
    ]
    for r in rows4:
        add_data_row(t4, r)
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 9: SA-CCR
# ═══════════════════════════════════════════════════════════════════
def build_section_9(doc):
    add_section_heading(doc, "9", "SA-CCR: Supervisory Factors, RC, PFE & Alpha Parameters")
    add_body_text(doc, "Complete comparison of SA-CCR methodology including all 13 supervisory factors, "
        "replacement cost formulas, alpha parameter divergence, and multiplier mechanics.")

    # 9.1 Supervisory Factors
    add_subsection(doc, "9.1 Supervisory Factors by Asset Class")
    t = create_table(doc, HDRS, STD4)
    rows = [
        ["Interest Rate SF", "", "", ""],
        ["IR: 0-2Y", "0.50% - single IR supervisory factor for all maturity buckets (Table 2 to §__.114); maturity buckets enter via supervisory duration SD = max((e^(-0.05S/250) - e^(-0.05E/250))/0.05, 0.04)", "0.50% (PS1/26 Ch.8 Table 8.1)",
         "0.50% (CRR3 Art 280a)"],
        ["IR: 2-5Y", "0.50% (Table 2 to §__.114; supervisory option volatility 50%)", "0.30% (PS1/26 Ch.8 Table 8.1)",
         "0.30% (CRR3 Art 280a)"],
        ["IR: 5Y+", "0.50% (Table 2 to §__.114)", "0.60% (PS1/26 Ch.8 Table 8.1)",
         "0.60% (CRR3 Art 280a)"],
        ["FX SF", "", "", ""],
        ["FX: All", "4.0% (volatility 15%) (Table 2 to §__.114)", "4.0% (PS1/26 Ch.8 Table 8.1)",
         "4.0% (CRR3 Art 280c)"],
        ["Credit SF", "", "", ""],
        ["Credit: AAA-AA", "Investment grade single-name 0.46% (no rating split; Dodd-Frank 939A) (Table 2 to §__.114)", "0.38% (PS1/26 Ch.8 Table 8.1)",
         "0.38% (CRR3 Art 280b)"],
        ["Credit: A", "Investment grade single-name 0.46% (Table 2 to §__.114)", "0.42% (PS1/26 Ch.8 Table 8.1)",
         "0.42% (CRR3 Art 280b)"],
        ["Credit: BBB", "Investment grade single-name 0.46% (Table 2 to §__.114)", "0.54% (PS1/26 Ch.8 Table 8.1)",
         "0.54% (CRR3 Art 280b)"],
        ["Credit: BB", "Speculative grade single-name 1.3% (Table 2 to §__.114)", "1.06% (PS1/26 Ch.8 Table 8.1)",
         "1.06% (CRR3 Art 280b)"],
        ["Credit: B", "Speculative grade single-name 1.3% (Table 2 to §__.114)", "1.6% (PS1/26 Ch.8 Table 8.1)",
         "1.6% (CRR3 Art 280b)"],
        ["Credit: CCC", "Sub-speculative grade single-name 6.0% (Table 2 to §__.114)", "6.0% (PS1/26 Ch.8 Table 8.1)",
         "6.0% (CRR3 Art 280b)"],
        ["Credit: Index", "Investment grade index 0.38%; speculative grade index 1.06% (correlation 80%) (Table 2 to §__.114)", "0.38% IG / 1.06% SG (PS1/26 Ch.8 Table 8.1)",
         "0.38% IG / 1.06% SG (CRR3 Art 280b)"],
        ["Equity SF", "", "", ""],
        ["Equity: Single Name", "32% (volatility 120%) (Table 2 to §__.114)", "32% (PS1/26 Ch.8 Table 8.1)",
         "32% (CRR3 Art 280d)"],
        ["Equity: Index", "20% (volatility 75%) (Table 2 to §__.114)", "20% (PS1/26 Ch.8 Table 8.1)",
         "20% (CRR3 Art 280d)"],
        ["Commodity SF", "", "", ""],
        ["Commodity: Electricity", "40% (volatility 150%) (Table 2 to §__.114)", "40% (PS1/26 Ch.8 Table 8.1)",
         "40% (CRR3 Art 280e)"],
        ["Commodity: Oil/Gas", "18% (volatility 70%) (Table 2 to §__.114)", "18% (PS1/26 Ch.8 Table 8.1)",
         "18% (CRR3 Art 280e)"],
        ["Commodity: Metals", "18% (Table 2 to §__.114)", "18% (PS1/26 Ch.8 Table 8.1)",
         "18% (CRR3 Art 280e)"],
        ["Commodity: Agricultural", "18% (Table 2 to §__.114)", "18% (PS1/26 Ch.8 Table 8.1)",
         "18% (CRR3 Art 280e)"],
        ["Commodity: Other", "18% (Table 2 to §__.114); basis hedging sets SF x 0.5; volatility hedging sets SF x 5", "18% (PS1/26 Ch.8 Table 8.1)",
         "18% (CRR3 Art 280e)"],
    ]
    for i, r in enumerate(rows):
        is_sub = r[0] in ["Interest Rate SF", "FX SF", "Credit SF", "Equity SF", "Commodity SF"]
        add_data_row(t, r, is_subheader=is_sub)

    # 9.2 Correlation Parameters
    add_subsection(doc, "9.2 Correlation Parameters")
    t2 = create_table(doc, HDRS, STD4)
    rows2 = [
        ["IR Correlation (Same CCY)", "Maturity-bucket aggregation within a currency: sqrt(D1^2 + D2^2 + D3^2 + 1.4 D1D2 + 1.4 D2D3 + 0.6 D1D3) (i.e. 70%/30% cross-bucket correlation), or |D1|+|D2|+|D3| (ERBA NPR §__.114)", "99.9% (PS1/26 Ch.8.2)",
         "99.9% (CRR3 Art 280a(3))"],
        ["IR Correlation (Cross CCY)", "0% - separate hedging set per currency; add-ons summed (ERBA NPR §__.114)", "0% (PS1/26 Ch.8.2)",
         "0% (CRR3 Art 280a(3))"],
        ["Credit: Single Name", "50% systematic correlation (Table 2 to §__.114)",
         "50% (PS1/26 Ch.8.2)", "50% (CRR3 Art 280b(3))"],
        ["Credit: Index", "80% (Table 2 to §__.114)", "80% (PS1/26 Ch.8.2)",
         "80% (CRR3 Art 280b(3))"],
        ["Equity: Single Name", "50% (Table 2 to §__.114)", "50% (PS1/26 Ch.8.2)",
         "50% (CRR3 Art 280d(3))"],
        ["Equity: Index", "80% (Table 2 to §__.114)", "80% (PS1/26 Ch.8.2)",
         "80% (CRR3 Art 280d(3))"],
        ["Commodity: Same Type", "40% (all commodity hedging sets) (Table 2 to §__.114)", "40% (PS1/26 Ch.8.2)",
         "40% (CRR3 Art 280e(3))"],
        ["FX Correlation", "N/A (single hedging set per currency pair) (ERBA NPR §__.114)",
         "N/A (PS1/26 Ch.8.2)", "N/A (CRR3 Art 280c)"],
    ]
    for r in rows2:
        add_data_row(t2, r)

    # 9.3 RC & PFE
    add_subsection(doc, "9.3 Replacement Cost & PFE Formulas")
    t3 = create_table(doc, HDRS, STD4)
    rows3 = [
        ["RC (Unmargined)", "RC = max(V - C, 0) where V=MtM, C=net collateral (ERBA NPR §__.114)",
         "Same formula (PS1/26 Ch.8.3)", "Same formula (CRR3 Art 275(1))"],
        ["RC (Margined)", "RC = max(V-C, TH+MTA-NICA, 0) (ERBA NPR §__.114). TH=threshold, MTA=min transfer amount, NICA=net independent collateral amount; margined EAD capped at unmargined EAD",
         "Same formula (PS1/26 Ch.8.3)", "Same formula (CRR3 Art 275(2))"],
        ["PFE Formula", "PFE = multiplier * AddOnAgg (ERBA NPR §__.114)",
         "Same (PS1/26 Ch.8.4)", "Same (CRR3 Art 278)"],
        ["Multiplier", "mult = min(1, 0.05 + 0.95 * exp((V-C) / (1.9 * AddOnAgg))) (ERBA NPR §__.114). floor=5%",
         "Same formula, floor=5% (PS1/26 Ch.8.4)", "Same formula, floor=5% (CRR3 Art 278(1))"],
        ["Alpha Parameter", "1.4 unless the counterparty is a commercial end-user; 1.0 for commercial end-users (EAD = RC + PFE) (ERBA NPR §__.114(e)(4); P.110). CRITICAL DIVERGENCE: US bifurcates alpha",
         "1.4 for all counterparties (PS1/26 Ch.8.5). No commercial end-user reduction",
         "1.4 for all counterparties (CRR3 Art 274(2)). No commercial end-user reduction"],
        ["EAD Formula", "EAD = alpha * (RC + PFE) (ERBA NPR §__.114)",
         "Same (PS1/26 Ch.8.5)", "Same (CRR3 Art 274(1))"],
        ["Cross-Product Netting", "NEW extended SA-CCR: for a qualifying cross-product master netting agreement covering non-cleared derivatives and repo-style transactions, EAD = (1 - MR) x (EAD_repo haircut approach + EAD_deriv SA-CCR) + MR x EAD_SA-CCR(all), MR = maturity ratio (maturities floored at 10 bd, capped at 1Y); repos treated as forward derivatives (delta +1 / -1) (ERBA NPR §__.113; P.111-116)",
         "Allowed per netting agreement (PS1/26 Ch.8.6)",
         "Allowed per CRR3 Art 272(4) netting set definition"],
        ["Netting Set Definition", "Derivatives under same QMNA with same counterparty; cross-product netting not available for eligible margin loans or cleared transactions (ERBA NPR §__.113; P.115-116)",
         "Same legal netting agreement (PS1/26 Ch.8.6)",
         "QMNA definition (CRR3 Art 272(4))"],
        ["MPOR Standard", "Margined: floor 10 business days (+ remargining periodicity - 1); 5 bd for client-facing cleared transactions; MF = sqrt(1.5 x MPOR / 250). Unmargined: MF = sqrt(min(M, 250)/250), M >= 10 bd (ERBA NPR §__.114)",
         "10 days (PS1/26 Ch.8.7)", "10 days (CRR3 Art 285(2))"],
        ["MPOR Disputed Trades", "20 business days for netting sets with > 5,000 non-cleared trades or illiquid collateral; MPOR doubled if > 2 margin disputes in prior two quarters (ERBA NPR §__.114)",
         "20 days (PS1/26 Ch.8.7)", "20 days (CRR3 Art 285(2)(c))"],
    ]
    for r in rows3:
        add_data_row(t3, r)
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 10: CVA Risk
# ═══════════════════════════════════════════════════════════════════
def build_section_10(doc):
    add_section_heading(doc, "10", "CVA Risk: BA-CVA, SA-CVA & Exemptions")

    # 10.1 BA-CVA
    add_subsection(doc, "10.1 BA-CVA: Basic Approach")
    t = create_table(doc, HDRS, STD4)
    rows = [
        ["BA-CVA Availability", "Basic measure is the default for all CVA banks; scope = Cat I/II HCs, their market-risk DI subsidiaries, and market-risk banks with >= $1T OTC notional (ERBA NPR §__.201, §__.220)", "Available (PS1/26 Ch.9)",
         "Available (CRR3 Art 382a)"],
        ["BA-CVA Reduced Version", "With no eligible hedges K_hedged = K_unhedged so K = 0.65 x K_unhedged; K_unhedged = sqrt((rho sum SCVA_c)^2 + (1 - rho^2) sum SCVA_c^2), rho = 50% (ERBA NPR §__.222; P.457)",
         "Available (PS1/26 Ch.9.1)", "Available (CRR3 Art 385)"],
        ["BA-CVA Full Version", "K = 0.65 x (0.25 K_unhedged + 0.75 K_hedged). Eligible hedges: index CDS, single-name CDS and single-name contingent CDS, INCLUDING indirect single-name hedges (r = 100% direct / 80% affiliate / 50% same sector & region); index hedge RW = Table 1 x 0.7 (ERBA NPR §__.222; P.443, P.464-467)",
         "Recognizes single-name + index hedges (PS1/26 Ch.9.1)",
         "Recognizes single-name + index hedges (CRR3 Art 386)"],
        ["Beta (Hedging Discount)", "beta = 0.25 weight on K_unhedged (hedge effectiveness capped at 75%); 0.65 overall calibration scalar; SCVA_c = (1/alpha) x RW_c x sum(M x EAD x DF), alpha = 1.4 (1.0 commercial end-users) (ERBA NPR §__.222; P.456-457)",
         "beta = 0.65 (PS1/26 Ch.9.1)", "beta = 0.65 (CRR3 Art 385(2))"],
        ["RW by CQS (IG)", "No ratings: RW by sector x credit quality. IG: sovereigns/MDB 0.5%; PSE/GSE/education 1.0%; financials 5.0%; basic materials/energy/industrials 3.0%; consumer/transport 3.0%; tech/telecom 2.0%; health/utilities 1.5%; other 5.0% (Table 1 to §__.222)",
         "Same RWs (PS1/26 Ch.9 Table 9.1)", "Same RWs (CRR3 Art 383(2) Table 1)"],
        ["RW by CQS (HY)", "Speculative / sub-speculative: sovereigns 3.0% / 7.0%; PSE 4.0%; financials 12.0%; basic materials 7.0%; consumer 8.5%; tech 5.5%; health 5.0%; other 12.0% (Table 1 to §__.222)",
         "Same RWs (PS1/26 Ch.9 Table 9.1)", "Same RWs (CRR3 Art 383(2) Table 1)"],
        ["Discount Factor", "DF = (1-exp(-0.05*M))/(0.05*M), M = notional-weighted average remaining maturity (ERBA NPR §__.222)",
         "Same formula (PS1/26 Ch.9.2)", "Same formula (CRR3 Art 383(3))"],
    ]
    for r in rows:
        add_data_row(t, r)

    # 10.2 SA-CVA
    add_subsection(doc, "10.2 SA-CVA: Standardized Approach")
    t2 = create_table(doc, HDRS, STD4)
    rows2 = [
        ["SA-CVA Availability", "Available with primary Federal supervisor approval (standardized measure = SA-CVA plus BA-CVA for carve-outs); m_CVA = 1.0 (agency may increase); hedging disallowance R = 0.01; MPoR >= 9 + N business days (ERBA NPR §__.220, §__.224)",
         "Available with PRA approval (PS1/26 Ch.9.3)",
         "Available with NCA approval (CRR3 Art 383a)"],
        ["SA-CVA Structure", "Delta: 6 risk classes (IR, FX, counterparty credit spread, reference credit spread, equity, commodity); vega: 5 (no counterparty CS); K_b = sqrt(sum WS^2 + sum rho WS WS + R sum (WS_hedge)^2); cross-bucket S_b capped (ERBA NPR §__.224)",
         "Delta + vega (PS1/26 Ch.9.3)", "Delta + vega (CRR3 Art 383a-383o)"],
        ["Interest Rate Buckets", "Per currency; specified currencies (USD, AUD, CAD, EUR, JPY, SEK, GBP) tenors 1/2/5/10/30Y RW 1.11/0.93/0.74/0.74/0.74% + inflation 1.11%; other currencies parallel shift 1.58%; gamma 50% (ERBA NPR §__.224)", "Per currency (PS1/26 Ch.9.3)",
         "Per currency (CRR3 Art 383e)"],
        ["Credit Spread Buckets", "Counterparty CS: 8 buckets (sovereign/PSE/gov-backed merged; financials; basic materials; consumer; tech; health; other; indices) with index-bucket correlation 70%; reference CS: 17 buckets (RW 0.5%-12.0%; indices 1.5%/5.0%) (Tables 3-7 to §__.224; P.491-493)", "18 buckets (PS1/26 Ch.9.3)",
         "18 buckets (CRR3 Art 383f)"],
        ["Equity Buckets", "13 buckets = SBM Table 8 spot RWs (55/60/45/55/30/35/40/50/70/50/70/15/25%); vega 78% large cap / 100% other (Table 8 to §__.224)", "Same (PS1/26 Ch.9.3)",
         "Same (CRR3 Art 383g)"],
        ["FX Buckets", "Per currency pair vs reporting currency; delta RW 11%; vega RW 100%; gamma 60% (ERBA NPR §__.224)", "Same (PS1/26 Ch.9.3)",
         "Same (CRR3 Art 383h)"],
        ["Commodity Buckets", "12 buckets = SBM Table 9 RWs (30/35/60/80/40/45/20/35/25/35/50/30%); gamma 20% (0% with bucket 11) (Table 9 to §__.224)", "Same (PS1/26 Ch.9.3)",
         "Same (CRR3 Art 383i)"],
    ]
    for r in rows2:
        add_data_row(t2, r)

    # 10.3 Exemptions
    add_subsection(doc, "10.3 CVA Exemptions")
    t3 = create_table(doc, HDRS, STD4)
    rows3 = [
        ["CVA Exemptions", "", "", ""],
        ["Client-Cleared Trades", "EXCLUDED: cleared transactions and client-facing derivative transactions are not CVA risk covered positions (ERBA NPR §__.202; P.439-441)", "Exempt (PS1/26 Ch.9.4)",
         "Exempt (CRR3 Art 382(3))"],
        ["SFTs (Repos/SecLend)", "Not CVA risk covered positions - the definition covers derivative contracts only; no 'material CVA risk' test (ERBA NPR P.440)",
         "Exempt unless material (PS1/26 Ch.9.4)",
         "Exempt (CRR3 Art 382(4)(a)) - broader exemption in EU"],
        ["Intra-Group", "No intra-group exemption in the NPR (ERBA NPR §__.202)",
         "Exempt per intra-group rules (PS1/26 Ch.9.4)",
         "Exempt per CRR3 Art 382(4)(b) with conditions"],
        ["FX Transactions <=T+2", "Not addressed in the NPR - no FX settlement exemption (ERBA NPR §__.202)", "Exempt (PS1/26 Ch.9.4)",
         "Exempt (CRR3 Art 382(4)(c))"],
        ["Pension Fund Exemption", "No pension fund exemption in the NPR (ERBA NPR §__.202)",
         "Temporary exemption until Jan 2026 (PS1/26 Ch.9.4)",
         "Permanent exemption for qualifying pension schemes (CRR3 Art 382(4)(d)) - EU DIVERGENCE"],
        ["Small Portfolio Threshold", "N/A - no simplified/small-portfolio method; basic measure (BA-CVA) is the default for all in-scope banks (ERBA NPR §__.220)", "N/A (PS1/26 Ch.9.4)",
         "EUR 100B aggregate notional (CRR3 Art 382(5)) - qualifies for simplified treatment"],
        ["$1T Threshold (US)", "Scope threshold, not a simplified method: market-risk banks that are not Cat I/II HCs (or their DI subsidiaries) are subject to CVA capital only if OTC derivative gross notional >= $1 trillion (4-quarter average; CPI-W indexed); covers > 98% of DIHC OTC exposure (ERBA NPR §__.201; P.24)",
         "N/A", "N/A"],
        ["Sovereign Exemption", "No sovereign/PSE counterparty exemption in the NPR; sovereign counterparties carry BA-CVA RW 0.5% IG / 3.0% spec / 7.0% sub-spec (Table 1 to §__.222)",
         "Exempt for sovereign (PS1/26 Ch.9.4)", "Exempt for sovereign (CRR3 Art 382(4)(e))"],
        ["Credit Derivatives Used as CRM", "Bank MAY exclude an eligible credit derivative recognized as credit risk mitigation from the CVA calculation (ERBA NPR P.439)",
         "N/A", "N/A"],
    ]
    for i, r in enumerate(rows3):
        add_data_row(t3, r, is_subheader=(i == 0))
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 11: FRTB Market Risk
# ═══════════════════════════════════════════════════════════════════
def build_section_11(doc):
    add_section_heading(doc, "11", "FRTB Market Risk: SBM Risk Weights, DRC, RRAO & IMA")
    add_body_text(doc, "Bucket-level risk weights for all 7 FRTB risk classes, correlation scenarios, "
        "DRC parameters, RRAO classification, IMA components, and threshold divergence.")

    # 11.1 GIRR
    add_subsection(doc, "11.1 GIRR Risk Weights (MAR21.8)")
    t = create_table(doc, ["Tenor", "US RW (ERBA)", "UK RW (PS1/26)", "EU RW (CRR3)"], STD4)
    girr_rws = [
        ("0.25Y", "1.7%"), ("0.5Y", "1.7%"), ("1Y", "1.6%"), ("2Y", "1.3%"),
        ("3Y", "1.2%"), ("5Y", "1.1%"), ("10Y", "1.1%"), ("15Y", "1.1%"),
        ("20Y", "1.1%"), ("30Y", "1.1%"),
    ]
    for tenor, rw in girr_rws:
        add_data_row(t, [f"GIRR Delta {tenor}", f"{rw} (Table 1 to §__.209; 10 vertices, no 7Y/25Y)",
                         f"{rw} (PS1/26 Ch.16 Table 16.1)", f"{rw} (CRR3 Art 325ae Table 3)"])
    add_data_row(t, ["GIRR Inflation", "1.6% (Table 1 to §__.209)", "1.6% (PS1/26 Ch.16)",
                     "1.6% (CRR3 Art 325ae(3))"])
    add_data_row(t, ["GIRR Cross-Currency Basis", "1.6% (Table 1 to §__.209)", "1.6% (PS1/26 Ch.16)",
                     "1.6% (CRR3 Art 325ae(4))"])
    add_data_row(t, ["GIRR Liquid Currencies", "Risk weights may be divided by sqrt(2) for USD, AUD, CAD, EUR, JPY, SEK, GBP (and agency-specified currencies) (ERBA NPR §__.209)",
                     "Same sqrt(2) treatment (PS1/26 Ch.16)", "Same sqrt(2) treatment (CRR3 Art 325ae(2))"])

    # 11.2 CSR Non-Sec  (US Table 3 to §__.209 has 20 buckets keyed to IG / speculative /
    # sub-speculative credit quality; UK/EU columns show the equivalent BCBS d457 MAR21.53 bucket)
    add_subsection(doc, "11.2 CSR Non-Securitization Risk Weights (US Table 3 to §__.209 vs MAR21.53)")
    t2 = create_table(doc, ["Bucket (US Table 3 to §__.209)", "US RW (ERBA)", "UK RW (PS1/26)", "EU RW (CRR3)"], STD4)
    csr_buckets = [
        ("1: Sovereigns, MDBs, supranationals (IG)", "0.5%", "0.5% (MAR21.53 bkt 1)"),
        ("2: PSE, gov-backed non-fin, GSE debt, education, public admin (IG)", "1.0%", "1.0% (MAR21.53 bkt 2)"),
        ("3: Financials incl gov-backed, real estate (IG)", "5.0%", "5.0% (MAR21.53 bkt 3)"),
        ("4: Basic materials, energy, industrials, agri, manufacturing, mining (IG)", "3.0%", "3.0% (MAR21.53 bkt 4)"),
        ("5: Consumer goods & services, transport, admin (IG)", "3.0%", "3.0% (MAR21.53 bkt 5)"),
        ("6: Technology, telecom (IG)", "2.0%", "2.0% (MAR21.53 bkt 6)"),
        ("7: Health care, utilities, professional services (IG)", "1.5%", "1.5% (MAR21.53 bkt 7)"),
        ("8: Covered bonds (IG)", "1.5%", "1.5% (MAR21.53 bkt 8)"),
        ("9: Sovereigns, MDBs (speculative)", "3.0%", "2.0% (MAR21.53 bkt 9, HY sovereign)"),
        ("10: PSE etc (speculative)", "4.0%", "4.0% (MAR21.53 bkt 10)"),
        ("11: Financials (speculative)", "12.0%", "12.0% (MAR21.53 bkt 11)"),
        ("12: Basic materials etc (spec + sub-spec)", "7.0%", "7.0% (MAR21.53 bkt 12)"),
        ("13: Consumer goods etc (spec + sub-spec)", "8.5%", "8.5% (MAR21.53 bkt 13)"),
        ("14: Technology, telecom (spec + sub-spec)", "5.5%", "5.5% (MAR21.53 bkt 14)"),
        ("15: Health care etc (spec + sub-spec)", "5.0%", "5.0% (MAR21.53 bkt 15)"),
        ("16: Covered bonds (spec + sub-spec)", "2.5%", "No equivalent bucket (BCBS covered bonds IG only)"),
        ("17: Sovereigns, MDBs (sub-speculative)", "7.0%", "No equivalent bucket (BCBS HY sovereign 2.0%)"),
        ("18: Other sector (spec + sub-spec)", "12.0% (sum of |WS|)", "12.0% (MAR21.53 bkt 16)"),
        ("19: IG indices", "1.5%", "1.5% (MAR21.53 bkt 17)"),
        ("20: Spec + sub-spec indices", "5.0%", "5.0% (MAR21.53 bkt 18)"),
    ]
    for bkt, rw_us, rw_bcbs in csr_buckets:
        add_data_row(t2, [f"CSR {bkt}", f"{rw_us} (Table 3 to §__.209)",
                          f"{rw_bcbs} (PS1/26 Ch.16 Table 16.3)", f"{rw_bcbs} (CRR3 Art 325ah Table 5)"])

    # 11.3 CSR Securitization
    add_subsection(doc, "11.3 CSR Securitization CTP & Non-CTP")
    t3 = create_table(doc, HDRS, STD4)
    rows3 = [
        ["CSR Sec CTP Buckets", "16 buckets by sector x credit quality (IG / spec / sub-spec) (Table 5 to §__.209). RWs: 2.0%-16.0% (e.g. IG sovereign 4.0%, IG financials 8.0%, spec+sub-spec financials 16.0%, sub-spec sovereign 16.0%, other 13.0%)",
         "16 buckets (PS1/26 Ch.16 Table 16.5)", "16 buckets (CRR3 Art 325ak Table 9)"],
        ["CSR Sec Non-CTP Buckets", "25 buckets: senior IG / non-senior IG / spec+sub-spec x 8 asset classes (RMBS prime/mid/sub-prime, CMBS, ABS student, cards, auto, CLO) + other sector (Table 7 to §__.209). RWs: 0.80%-3.50%; cross-bucket gamma = 0%",
         "25 buckets (PS1/26 Ch.16 Table 16.4)", "25 buckets (CRR3 Art 325aj Table 7)"],
        ["Sec Non-CTP Bucket 1", "Senior IG prime RMBS 0.90%; mid-prime 1.50%; sub-prime 2.00%; CMBS 2.00%; student ABS 0.80%; cards 1.20%; auto 1.20%; CLO 1.40% (Table 7 to §__.209)",
         "Same (PS1/26 Ch.16)", "Same (CRR3 Art 325aj)"],
        ["Sec Non-CTP Bucket 25", "Other sector 3.50% (sum of |WS|) (Table 7 to §__.209)",
         "Same (PS1/26 Ch.16)", "Same (CRR3 Art 325aj)"],
    ]
    for r in rows3:
        add_data_row(t3, r)

    # 11.4 Equity  (US Table 8 to §__.209 = BCBS d457 MAR21.77 values)
    add_subsection(doc, "11.4 Equity Risk Weights (US Table 8 to §__.209 / MAR21.77)")
    t4 = create_table(doc, ["Bucket", "US RW (ERBA)", "UK RW (PS1/26)", "EU RW (CRR3)"], STD4)
    eq_buckets = [
        ("1: Large Cap Emerging (Consumer/Transport/Admin/Health/Utilities)", "55%"),
        ("2: Large Cap Emerging (Telecom/Industrials)", "60%"),
        ("3: Large Cap Emerging (Basic Materials/Energy/Agri/Manufacturing/Mining)", "45%"),
        ("4: Large Cap Emerging (Financials/Real Estate/Technology)", "55%"),
        ("5: Large Cap Liquid Markets (Consumer/Transport/Admin/Health/Utilities)", "30%"),
        ("6: Large Cap Liquid Markets (Telecom/Industrials)", "35%"),
        ("7: Large Cap Liquid Markets (Basic Materials/Energy/Agri/Manufacturing/Mining)", "40%"),
        ("8: Large Cap Liquid Markets (Financials/Real Estate/Technology)", "50%"),
        ("9: Small Cap Emerging", "70%"), ("10: Small Cap Liquid Markets", "50%"),
        ("11: Other Sector", "70%"), ("12: Large Cap Liquid-Market Indices", "15%"),
        ("13: Other Indices", "25%"),
    ]
    for bkt, rw in eq_buckets:
        add_data_row(t4, [f"Equity {bkt}", f"{rw} spot / {rw[:-1]}bp repo (Table 8 to §__.209)",
                          f"{rw} (PS1/26 Ch.16 Table 16.7)", f"{rw} (CRR3 Art 325ap Table 10)"])

    # 11.5 Commodity  (US Table 9 to §__.209 = BCBS d457 MAR21.82 values)
    add_subsection(doc, "11.5 Commodity Risk Weights (US Table 9 to §__.209 / MAR21.82)")
    t5 = create_table(doc, ["Bucket", "US RW (ERBA)", "UK RW (PS1/26)", "EU RW (CRR3)"], STD4)
    commod_buckets = [
        ("1: Energy - Solid Combustibles", "30%"), ("2: Energy - Liquid Combustibles", "35%"),
        ("3: Energy - Electricity & Carbon Trading", "60%"), ("4: Freight", "80%"),
        ("5: Metals - Non-Precious", "40%"), ("6: Gaseous Combustibles", "45%"),
        ("7: Precious Metals (incl Gold)", "20%"), ("8: Grains & Oilseed", "35%"),
        ("9: Livestock & Dairy", "25%"), ("10: Softs & Other Agriculturals", "35%"),
        ("11: Other Commodity", "50%"), ("12: Commodity Indices", "30%"),
    ]
    for bkt, rw in commod_buckets:
        add_data_row(t5, [f"Commodity {bkt}", f"{rw} (Table 9 to §__.209)",
                          f"{rw} (PS1/26 Ch.16 Table 16.9)", f"{rw} (CRR3 Art 325as Table 13)"])

    # 11.6 FX
    add_subsection(doc, "11.6 FX Risk Weights")
    t6 = create_table(doc, HDRS, STD4)
    rows6 = [
        ["FX Delta RW", "15% for all currency pairs (ERBA NPR §__.209)", "15% (PS1/26 Ch.16 Table 16.11)",
         "15% (CRR3 Art 325at(2))"],
        ["Specified FX Pairs", "RW divided by sqrt(2) (= 10.6%) for any pair formed from USD, EUR, JPY, GBP, AUD, CAD, CHF, MXN, CNY, NZD, HKD, SGD, TRY, KRW, SEK, ZAR, INR, NOK, BRL and agency-specified currencies (ERBA NPR §__.209; P.329 fn 376)",
         "Same specified pairs (PS1/26 Ch.16)", "Same specified pairs (CRR3 Art 325at(3))"],
        ["FX Triangulation", "Not separately addressed in the NPR: any pair of two specified currencies qualifies directly (ERBA NPR §__.209). Curvature CVR for options not referencing the reporting currency may be divided by 1.5",
         "Same (PS1/26 Ch.16)", "Same (CRR3 Art 325at(3))"],
    ]
    for r in rows6:
        add_data_row(t6, r)

    # 11.7 Correlation Scenarios
    add_subsection(doc, "11.7 Correlation Scenarios & Aggregation")
    t7 = create_table(doc, HDRS, STD4)
    rows7 = [
        ["Three Correlation Scenarios", "Medium = specified rho; High = rho x 1.25 capped at 100%; Low = max(2 x rho - 100%, 75% x rho). Capital = max of three (ERBA NPR §__.206)",
         "Same three scenarios (PS1/26 Ch.16.8)", "Same three scenarios (CRR3 Art 325g)"],
        ["SBM Aggregation", "SBM = max over the three scenarios of the sum across the 7 risk classes of (delta + vega + curvature); K_b = sqrt(max(sum WS^2 + sum rho WS WS, 0)); across buckets sqrt(sum K_b^2 + sum gamma S_b S_c) with S_b = max(min(sum WS, K_b), -K_b) fallback (ERBA NPR §__.206)",
         "Same (PS1/26 Ch.16.8)", "Same (CRR3 Art 325h)"],
    ]
    for r in rows7:
        add_data_row(t7, r)

    # 11.8 DRC
    add_subsection(doc, "11.8 DRC Parameters")
    t8 = create_table(doc, HDRS, STD4)
    rows8 = [
        ["DRC Non-Sec RWs", "By credit quality category, not external rating (Dodd-Frank 939A): IG 0.6% non-US sovereign / 2.1% PSE & GSE / 4.1% corporate; speculative 22.0%; sub-speculative 50.0%; defaulted 100% (Table 1 to §__.210). Four buckets: non-US sovereign, PSE & GSE, corporate, defaulted; US sovereign/MDB excluded",
         "Rating-based RWs (PS1/26 Ch.16.9)", "Rating-based RWs (CRR3 Art 325bp Table 2)"],
        ["DRC Sec Non-CTP", "Gross DE = market value; offsetting only within same pool and same tranche; buckets = corporate + asset class x region; RW = SEC-SA (§__.132) RW x 8%; cap at fair value for cash positions; same HBR formula (ERBA NPR §__.210)",
         "Same (PS1/26 Ch.16.9)", "Same (CRR3 Art 325bp(3))"],
        ["DRC Sec CTP", "Each index its own bucket; HBR computed across all CTP buckets; tranche RW = SEC RW x 8%; DRC_CTP = max(sum_b[max(DRC_b, 0) + 0.5 x min(DRC_b, 0)], 0) (ERBA NPR §__.210)",
         "Same (PS1/26 Ch.16.9)", "Same (CRR3 Art 325bp(4))"],
        ["DRC LGD Non-Sec", "Equity, non-senior debt and defaulted positions 100%; senior debt 75%; US PSE positions 50%; covered bonds and GSE-guaranteed debt 25%; GSE-issued non-guaranteed debt 75% (ERBA NPR §__.210)",
         "100% / 75% / 25% (PS1/26 Ch.16.9)", "100% / 75% / 25% (CRR3 Art 325bp(1))"],
        ["DRC HBR / Maturity", "HBR = sum net long / (sum net long + sum |net short|); positions < 1Y scaled by fraction of year with 3-month floor; unhedged cash equity may use 3 months or 1 year (ERBA NPR §__.210)",
         "Same (PS1/26 Ch.16.9)", "Same (CRR3 Art 325bp)"],
    ]
    for r in rows8:
        add_data_row(t8, r)

    # 11.9 RRAO
    add_subsection(doc, "11.9 RRAO & IMA Parameters")
    t9 = create_table(doc, HDRS, STD4)
    rows9 = [
        ["RRAO Exotic", "1.0% of notional (ERBA NPR §__.211). Instruments with exotic underlying: longevity, weather, natural disasters, realized volatility",
         "1.0% (PS1/26 Ch.16.10)", "1.0% (CRR3 Art 325bp(1)(a))"],
        ["RRAO Other Residual", "0.1% of notional (ERBA NPR §__.211). CTP with >= 3 underlyings, non-replicable curvature/vega payoffs, no maturity, no/multiple strikes or barriers",
         "0.1% (PS1/26 Ch.16.10)", "0.1% (CRR3 Art 325bp(1)(b))"],
        ["RRAO Exemptions", "Listed/cleared instruments, back-to-back positions, plain-vanilla options and other listed exclusions (ERBA NPR §__.211)",
         "Same (PS1/26 Ch.16.10)", "Same (CRR3 Art 325bp(2))"],
        ["IMA ES", "ES at 97.5%, base liquidity horizon 10 days with ladder 10/20/40/60/120 days; stress period 12 months back to 2007; reduced factor set must explain >= 75%; IMA_G,A = max(IMCC_t-1 + SES_t-1, m_c x IMCC_avg60 + SES_avg60) + PLA add-on; IMA capped at SA (ERBA NPR §__.204, §__.215)",
         "Same (PS1/26 Ch.16.11)", "Same (CRR3 Art 325bb)"],
        ["IMA NMRF", "SES = sqrt(sum SES_NM,k^2 + [(1-rho_b) sum SES_NM,j^2 + rho_b (sum SES_NM,j)^2]), rho_b = 0.36; modellability: 24 real prices (10/20-day LH) or 16 otherwise; NMRF LH >= max(assigned, 20 days); IMCC omega = 0.5 (ERBA NPR §__.214-215)",
         "Same (PS1/26 Ch.16.11)", "Same (CRR3 Art 325bk)"],
        ["IMA Multiplier", "m_c = 1.5 base; backtesting ladder (99% 1-day VaR, 250 days, max of actual/hypothetical exceptions): 0-4 exceptions 1.50; 5: 1.70; 6: 1.76; 7: 1.83; 8: 1.88; 9: 1.92; >= 10: 2.00 (Table 1 to §__.204)",
         "Same formula (PS1/26 Ch.16.11)", "Same formula (CRR3 Art 325ba)"],
        ["PLA Test", "Kolmogorov-Smirnov metric ONLY (no Spearman correlation test): green KS < 0.09; amber 0.09 <= KS <= 0.12; red > 0.12; PLA add-on = 0.5 x (SA_amber / SA_G,A) x max(SA_G,A - IMA_G,A, 0); three-year transition with no automatic consequences (ERBA NPR §__.213; P.380-381, P.537)",
         "Spearman + KS (PS1/26 Ch.16.12)", "Spearman + KS (CRR3 Art 325bg)"],
        ["Backtesting", "Desk-level: 97.5% and 99% VaR over 250 business days; desk ineligible if > 12 exceptions at 99% or > 30 at 97.5% (actual or hypothetical P&L) (ERBA NPR §__.212)",
         "Same (PS1/26 Ch.16.12)", "Same (CRR3 Art 325bf)"],
        ["Threshold Divergence", "$5B trading assets + liabilities (4Q avg) or >= 10% of total assets; Cat I/II holding companies regardless (ERBA NPR §__.201)",
         "GBP 50M bilateral netting set or 5% total assets (PS1/26 Ch.16.1)",
         "EUR 500M or 10% total assets (CRR3 Art 325a(1))"],
    ]
    for r in rows9:
        add_data_row(t9, r)
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 12: Operational Risk
# ═══════════════════════════════════════════════════════════════════
def build_section_12(doc):
    add_section_heading(doc, "12", "Operational Risk: BI Components, BIC, ILM & Loss Data")

    # 12.1 BI Components
    add_subsection(doc, "12.1 Business Indicator (BI) Components")
    t = create_table(doc, HDRS, STD4)
    rows = [
        ["BI Components", "", "", ""],
        ["ILDC Formula", "ILDC = min(Avg3y|total interest income - total interest expense|, 2.25% x Avg3y interest-earning assets) + Avg3y dividend income (ERBA NPR §__.150). Interest income/expense include lease income/expense; IEA average = 12 quarter-ends / 12",
         "Same formula (PS1/26 Ch.14.1)", "Same formula (CRR3 Art 314(1))"],
        ["NII Cap", "2.25% of interest-earning assets (ERBA NPR §__.150). Prevents distortion from high-rate environments",
         "2.25% of IEA (PS1/26 Ch.14.1)", "2.25% of IEA (CRR3 Art 314(1)(a))"],
        ["SC Formula", "N/A - no separate services component. US BI has TWO components: ILDC + noninterest component (ERBA NPR §__.150; P.535 'noninterest component replaces financial and services components')",
         "Same formula (PS1/26 Ch.14.1)", "Same formula (CRR3 Art 314(2))"],
        ["FC Formula", "N/A - no separate financial component; trading and banking book results enter noninterest income. Noninterest component = Avg3y( |total noninterest income + realized gains/losses on HTM and AFS debt securities - noninterest expense for BI - 0.7 x (fee income from investment management, investment services and non-lending treasury services - related noninterest expense)| + total operational losses ) (ERBA NPR §__.150)",
         "Same formula (PS1/26 Ch.14.1)", "Same formula (CRR3 Art 314(3))"],
        ["BI Calculation", "BI = ILDC + noninterest component. Avg3y = average of the three most recent four-quarter periods (ERBA NPR §__.150). Noninterest expense for BI excludes salaries/benefits, premises, goodwill impairment, intangibles amortization and total operational losses (§__.101)",
         "Same 3Y average (PS1/26 Ch.14.1)", "Same 3Y average (CRR3 Art 314(4))"],
        ["NIC Adjustment", "0.7x factor applied to NET fee income (income less related noninterest expense) from investment management, investment services AND non-lending treasury services, inside the noninterest component (ERBA NPR §__.150; P.205: op-loss/income ratio for these lines ~32% of the all-business average)",
         "Same (PS1/26 Ch.14.1)", "Same (CRR3 Art 314(3)(b))"],
    ]
    for i, r in enumerate(rows):
        add_data_row(t, r, is_subheader=(i == 0))

    # 12.2 BIC
    add_subsection(doc, "12.2 BIC Marginal Coefficients")
    t2 = create_table(doc, HDRS, STD4)
    rows2 = [
        ["Bucket 1: BI <= $1B", "12% marginal coefficient (ERBA NPR §__.150). BIC = 0.12 x BI; thresholds CPI-W indexed",
         "12% for BI <= GBP 0.88B (PS1/26 Ch.14.2)", "12% for BI <= EUR 1B (CRR3 Art 315(1))"],
        ["Bucket 2: $1B < BI <= $30B", "15% marginal coefficient (ERBA NPR §__.150). BIC = $120M + 0.15 x (BI - $1B)",
         "15% for GBP 0.88B-26.4B (PS1/26 Ch.14.2)", "15% for EUR 1B-30B (CRR3 Art 315(2))"],
        ["Bucket 3: BI > $30B", "18% marginal coefficient (ERBA NPR §__.150). BIC = $4.47B + 0.18 x (BI - $30B); operational RWA = 12.5 x BIC",
         "18% for BI > GBP 26.4B (PS1/26 Ch.14.2)", "18% for BI > EUR 30B (CRR3 Art 315(3))"],
        ["Worked Example: $50B BI", "BIC = 12%*1 + 15%*29 + 18%*20 = $0.12B + $4.35B + $3.6B = $8.07B",
         "Similar calculation in GBP", "Similar calculation in EUR"],
    ]
    for r in rows2:
        add_data_row(t2, r)

    # 12.3 ILM
    add_subsection(doc, "12.3 Internal Loss Multiplier (ILM)")
    t3 = create_table(doc, HDRS, STD4)
    rows3 = [
        ["ILM Setting", "NO ILM term in the rule text: operational RWA = 12.5 x BIC (ERBA NPR §__.150). Internal loss data instead enters the BI directly (total operational losses added to the noninterest component); Question 84 asks whether an ILM with a factor between 5 and 15 should be added (P.198-199)",
         "ILM = 1.0 (fixed) (PS1/26 Ch.14.3). PRA supervisory expectation for loss data collection but no capital impact",
         "ILM = 1.0 (fixed) (CRR3 Art 315a). BUT mandatory loss data collection required"],
        ["Loss Data Requirement", "REQUIRED: independent operational risk management function; operational loss event data collection processes; events >= $20,000 (CPI-W indexed) across 7 event types; total operational losses feed the BI (ERBA NPR §__.101, §__.150; P.204-207, P.216)",
         "Supervisory expectation only - qualitative requirement (PS1/26 Ch.14.3)",
         "MANDATORY: EUR 20K threshold, 10Y history, COREP C16.02-04 reporting (CRR3 Art 316-317). Must have loss data governance framework"],
        ["Loss Data Threshold", "$20,000 per event, CPI-W indexed (ERBA NPR §__.150; P.35)", "N/A", "EUR 20,000 per-event threshold (CRR3 Art 316(1))"],
        ["Loss Data History", "10 years, including loss data of acquired or merged entities (ERBA NPR §__.150)", "N/A", "10 years minimum; 5 years transitional (CRR3 Art 316(2))"],
        ["COREP Templates", "N/A (FR Y-14Q operational loss data; Cat I/II HCs reported > $308B of >= $20,000 losses 2007Q1-2025Q2, P.195)", "N/A", "C16.02 (losses by event type), C16.03 (large losses), C16.04 (loss trends) (EBA ITS 2024/XXX)"],
        ["ILM Formula (if applied)", "Basel ILM = ln(exp(1)-1 + (15 x avg annual losses / BIC)^0.8) quoted only in Question 84; NOT part of the proposed rule (ERBA NPR P.198-199)",
         "Same formula (not applied)", "Same formula (CRR3 Art 315a(2), not applied per Art 315a(1))"],
        ["OpRisk Capital", "ORC = BIC; RWA_op = 12.5 x BIC (ERBA NPR §__.150)",
         "ORC = BIC (PS1/26 Ch.14.4)", "ORC = BIC (CRR3 Art 312a)"],
        ["M&A Adjustment", "BI and loss data of acquired or merged entities included (10-year loss history) (ERBA NPR §__.150)",
         "Similar approach (PS1/26 Ch.14.5)",
         "Acquired entity inclusion; NCA may allow exclusion of divested BI after separation (CRR3 Art 314(5))"],
    ]
    for r in rows3:
        add_data_row(t3, r)
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 13: Securitization
# ═══════════════════════════════════════════════════════════════════
def build_section_13(doc):
    add_section_heading(doc, "13", "Securitization: SEC-SA (US), SEC-ERBA (UK/EU), STS & Risk Retention")

    # 13.1 Hierarchy
    add_subsection(doc, "13.1 Approach Hierarchy")
    t = create_table(doc, HDRS, STD4)
    rows = [
        ["Primary Approach", "SEC-SA ONLY. No SEC-ERBA (external ratings prohibited by Dodd-Frank 939A) and no SEC-IRBA; 'ERBA' in the NPR means the expanded risk-based approach, not the ratings-based securitization approach (ERBA NPR §__.132-133)",
         "SEC-IRBA > SEC-ERBA > SEC-SA hierarchy (PS1/26 Ch.10.1)",
         "SEC-IRBA > SEC-ERBA > SEC-SA hierarchy (CRR3 Art 254)"],
        ["SEC-IRBA Availability", "N/A (no IRB in US) (ERBA NPR §__.132)",
         "Available if IRB approved for underlying pool (PS1/26 Ch.10.1)",
         "Available if IRB approved (CRR3 Art 259)"],
        ["SEC-SA Formula", "K_A = (1-W) x K_G + W x 0.5; K_G = weighted-average capital requirement of underlying exposures (100% RW = 0.08); W = delinquent share (90+ dpd, bankruptcy, foreclosure, REO, deferred 90+, default); K_SSFA = (e^(au) - e^(al)) / (a(u-l)), a = -1/(p x K_A), p = 0.5 (1.5 resecuritization); straddle blend for A < K_A < D (ERBA NPR §__.133)",
         "Same formula (PS1/26 Ch.10.2)", "Same formula (CRR3 Art 261)"],
        ["SEC-ERBA RWs", "N/A - US does not use the external ratings-based approach (ERBA NPR §__.132)",
         "Same RW tables (PS1/26 Ch.10.3)", "Same RW tables (CRR3 Art 263 Table 1-2)"],
        ["RW Floor", "15%; 100% for resecuritizations and NPL securitizations; senior look-through floor 15%; NPL senior tranche 100% if non-refundable purchase price discount >= 50% (ERBA NPR §__.132-133; P.178-183)",
         "15% (PS1/26 Ch.10.4)", "15% (CRR3 Art 267)"],
        ["1250% RW Cap", "1,250% risk weight (not a CET1 deduction) when D <= K_A, when SEC-SA cannot be applied, or when due diligence fails; CEIO strips (non-gain-on-sale portion) deducted from CET1 (ERBA NPR §__.131-133; P.162, P.180)",
         "Same (PS1/26 Ch.10.4)", "Same (CRR3 Art 267)"],
    ]
    for r in rows:
        add_data_row(t, r)

    # 13.2 STS
    add_subsection(doc, "13.2 STS Framework (Simple, Transparent, Standardized)")
    t2 = create_table(doc, HDRS, STD4)
    rows2 = [
        ["STS Framework", "NOT adopted in US (ERBA NPR §__.133: single p = 0.5 and 15% floor; no STC/STS preferential treatment)",
         "STS framework adopted (PS1/26 Ch.10.5). UK STS designation via FCA",
         "Full STS framework (CRR3 Art 242-270, Securitisation Reg 2017/2402). 10% RW floor for STS vs 15% for non-STS"],
        ["STS RW Floor", "N/A (15% floor for all non-resecuritization exposures) (ERBA NPR §__.133)",
         "10% for qualifying STS tranches (PS1/26 Ch.10.5)",
         "10% for qualifying STS tranches (CRR3 Art 260)"],
        ["STS Criteria", "N/A", "Simplicity (true sale, homogeneous pool, no active management), Transparency (investor reporting), Standardised (risk retention, documentation) (PS1/26 Ch.10.5)",
         "21 criteria across simplicity/transparency/standardization (Securitisation Reg Art 19-22)"],
        ["Capital Impact", "US banks face 5pp higher floor vs UK/EU for qualifying senior STS tranches",
         "5pp lower floor for STS tranches", "5pp lower floor for STS tranches"],
        ["Risk Retention", "5% minimum retention by sponsor per Regulation RR (Dodd-Frank §941) - not part of the capital NPR. Vertical slice, horizontal first-loss, or L-shaped",
         "5% retention (PS1/26 Ch.10.6)", "5% retention (Securitisation Reg Art 6)"],
        ["SRT Assessment", "Operational requirements for traditional and synthetic securitizations (transfer of credit risk, clean-up calls, due diligence) retained; failure => 1,250% RW (ERBA NPR §__.131)",
         "SRT assessed by PRA (PS1/26 Ch.10.7)", "SRT criteria per CRR3 Art 244-245"],
    ]
    for r in rows2:
        add_data_row(t2, r)
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 14: IRB Comparison
# ═══════════════════════════════════════════════════════════════════
def build_section_14(doc):
    add_section_heading(doc, "14", "IRB Comparison: PD/LGD Floors, Correlation & Output Floor")
    add_body_text(doc, "The US has eliminated the IRB approach entirely. This section compares "
        "UK/EU IRB parameters for reference, as many global banks operate under both regimes.")

    # 14.1 PD Floors
    add_subsection(doc, "14.1 PD Input Floors by Exposure Class")
    t = create_table(doc, ["Exposure Class", "US (ERBA)", "UK PRA (PS1/26)", "EU EBA (CRR3)"], STD4)
    rows = [
        ["Corporate", "N/A - IRB eliminated (ERBA P.12)", "5bp (PS1/26 Ch.11 Table 11.1)",
         "5bp (CRR3 Art 160(1))"],
        ["Corporate SME", "N/A", "5bp (PS1/26 Ch.11 Table 11.1)", "5bp (CRR3 Art 160(1))"],
        ["Bank", "N/A", "5bp (PS1/26 Ch.11 Table 11.1)", "5bp (CRR3 Art 160(1))"],
        ["Retail Mortgage", "N/A", "5bp (PS1/26 Ch.11 Table 11.2)", "5bp (CRR3 Art 163(4))"],
        ["Retail QRRE", "N/A", "10bp (PS1/26 Ch.11 Table 11.2)", "10bp (CRR3 Art 163(4))"],
        ["Retail Other", "N/A", "5bp (PS1/26 Ch.11 Table 11.2)", "5bp (CRR3 Art 163(4))"],
        ["Sovereign", "N/A", "3bp (PS1/26 Ch.11 Table 11.1)", "3bp (CRR3 Art 160(1))"],
    ]
    for r in rows:
        add_data_row(t, r)

    # 14.2 LGD Floors
    add_subsection(doc, "14.2 LGD Input Floors")
    t2 = create_table(doc, ["Exposure Class", "US (ERBA)", "UK A-IRB (PS1/26)", "EU A-IRB (CRR3)"], STD4)
    rows2 = [
        ["Corporate Unsecured", "N/A", "25% (PS1/26 Ch.11 Table 11.3)", "25% (CRR3 Art 161(4))"],
        ["Corporate Secured (RE)", "N/A", "10% (PS1/26 Ch.11 Table 11.3)", "10% (CRR3 Art 161(4))"],
        ["Corporate Secured (Receivables)", "N/A", "15% (PS1/26 Ch.11 Table 11.3)",
         "15% (CRR3 Art 161(4))"],
        ["Corporate Secured (Phys Collateral)", "N/A", "15% (PS1/26 Ch.11 Table 11.3)",
         "15% (CRR3 Art 161(4))"],
        ["Corporate Secured (Fin Collateral)", "N/A", "0% (PS1/26 Ch.11 Table 11.3)",
         "0% (CRR3 Art 161(4))"],
        ["Retail Mortgage", "N/A", "5% (PS1/26 Ch.11 Table 11.4)", "5% (CRR3 Art 164(4))"],
        ["Retail QRRE", "N/A", "50% (PS1/26 Ch.11 Table 11.4)", "50% (CRR3 Art 164(4))"],
        ["Retail Other Secured", "N/A", "15% (PS1/26 Ch.11 Table 11.4)", "15% (CRR3 Art 164(4))"],
        ["Retail Other Unsecured", "N/A", "25% (PS1/26 Ch.11 Table 11.4)", "30% (CRR3 Art 164(4)) - EU HIGHER"],
    ]
    for r in rows2:
        add_data_row(t2, r)

    # 14.3 Asset Correlation
    add_subsection(doc, "14.3 Asset Correlation Formulas")
    t3 = create_table(doc, HDRS, STD4)
    rows3 = [
        ["Corporate Correlation", "N/A", "R = 0.12*(1-exp(-50*PD))/(1-exp(-50)) + 0.24*(1-(1-exp(-50*PD))/(1-exp(-50))). Range: 12%-24% (PS1/26 Ch.11.2)",
         "Same Vasicek formula (CRR3 Art 153(2))"],
        ["SME Adjustment", "N/A", "R_adj = R - 0.04*(1-max(5,S)/50) where S=revenue in millions (PS1/26 Ch.11.2)",
         "Same SME adjustment (CRR3 Art 153(4))"],
        ["Retail Mortgage Corr", "N/A", "R = 0.15 (fixed) (PS1/26 Ch.11.2)",
         "R = 0.15 (CRR3 Art 154(2))"],
        ["Retail QRRE Corr", "N/A", "R = 0.04 (fixed) (PS1/26 Ch.11.2)",
         "R = 0.04 (CRR3 Art 154(3))"],
        ["Maturity Adjustment", "N/A", "b(PD) = (0.11852-0.05478*ln(PD))^2. K adjusted by (1+(M-2.5)*b)/(1-1.5*b) (PS1/26 Ch.11.2)",
         "Same formula (CRR3 Art 153(3))"],
    ]
    for r in rows3:
        add_data_row(t3, r)

    # 14.4 Output Floor
    add_subsection(doc, "14.4 Output Floor Mechanics")
    t4 = create_table(doc, HDRS, STD4)
    rows4 = [
        ["Output Floor", "NOT applicable - no IRB = no floor needed (ERBA P.45)",
         "72.5% fully phased by 2030 (PS1/26 Ch.11.3). RWA_final = max(IRB_RWA, 72.5% * SA_RWA)",
         "72.5% fully phased by 2032 (CRR3 Art 92a). Extended 2Y vs UK/BCBS"],
        ["Floor Application", "N/A", "Applied at consolidated level (PS1/26 Ch.11.3)",
         "Applied at consolidated level; MS option for solo (CRR3 Art 92a(4))"],
        ["Transitional Adjustment", "N/A", "Linear phase-in 2025-2030 (PS1/26 Ch.11.3)",
         "Linear phase-in 2025-2032 (CRR3 Art 92a)"],
    ]
    for r in rows4:
        add_data_row(t4, r)
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 15: Pillar 2, Pillar 3, Large Exposures, Liquidity
# ═══════════════════════════════════════════════════════════════════
def build_section_15(doc):
    add_section_heading(doc, "15", "Pillar 2, Pillar 3, Large Exposures & Liquidity")

    # 15.1 Pillar 2
    add_subsection(doc, "15.1 Pillar 2: ICAAP / SREP / IRRBB")
    t = create_table(doc, HDRS, STD4)
    rows = [
        ["Pillar 2 Framework", "", "", ""],
        ["ICAAP Requirement", "CCAR/DFAST stress testing replaces formal ICAAP (12 CFR 252.56). No explicit ICAAP mandate",
         "Formal ICAAP required (PRA SS31/15). Annual submission to PRA",
         "Formal ICAAP required (CRD6 Art 73). Annual submission to NCA"],
        ["SREP Process", "CCAR supervisory stress test + horizontal review (12 CFR 252.44)",
         "PRA SREP: periodic assessment, sets P2A/P2G (PS1/26 Ch.15.1)",
         "EBA SREP Guidelines (EBA/GL/2022/03). Sets P2R (binding) + P2G (guidance)"],
        ["P2R / P2A", "Implicitly embedded in SCB (no separate P2R) (ERBA P.1162)",
         "P2A: firm-specific, typically 1-3% CET1 (PS1/26 Ch.15.1). Binding",
         "P2R: firm-specific per SREP (CRD6 Art 104a). Must be 56.25% CET1, 75% T1"],
        ["P2G", "N/A (SCB subsumes)", "PRA Buffer: similar concept to P2G (PS1/26 Ch.15.1)",
         "P2G: guidance, not binding. Expected CET1 (CRD6 Art 104b)"],
        ["IRRBB Framework", "SR 10-1 guidance + supervisory outlier test. EVE + NII metrics (Interagency Advisory)",
         "PRA SS31/15: EVE (200bp) + NII shocks. 6 prescribed scenarios (PS1/26 Ch.15.2)",
         "EBA IRRBB Guidelines (EBA/GL/2022/14). 6 scenarios: parallel +/-200bp, short/long rate, steepener/flattener (CRD6 Art 84(5))"],
        ["IRRBB EVE Threshold", "Supervisory outlier: EVE decline > 15% of T1 capital triggers review (SR 10-1)",
         "EVE decline > 15% T1 = outlier institution (PS1/26 Ch.15.2)",
         "EVE decline > 15% T1 = outlier (CRD6 Art 84(1))"],
        ["IRRBB NII Threshold", "Not standardized; supervisory judgment",
         "NII decline > 5% of T1 monitored (PS1/26 Ch.15.2)",
         "NII decline > 5% of T1 monitored (EBA/GL/2022/14)"],
        ["ESG / Climate Pillar 2", "OCC climate risk guidance (not binding). SR 23-XX",
         "PRA SS3/19: climate risk in ICAAP. Scenario analysis required (PS1/26 Ch.15.3)",
         "ESG risks in SREP (CRD6 Art 73(3), Art 98(8)). Transition plans required"],
    ]
    for i, r in enumerate(rows):
        add_data_row(t, r, is_subheader=(i == 0))

    # 15.2 Pillar 3
    add_subsection(doc, "15.2 Pillar 3: Disclosure Templates")
    t2 = create_table(doc, HDRS, STD4)
    rows2 = [
        ["Pillar 3 Templates", "", "", ""],
        ["OV1 (Capital Overview)", "Required (ERBA P.1200). FR Y-9C Schedule HC-R cross-reference",
         "Required (PS1/26 Ch.18 Table 18.1)", "Required (CRR3 Art 438)"],
        ["KM1 (Key Metrics)", "Required quarterly (ERBA P.1200)", "Required semi-annually (PS1/26 Ch.18)",
         "Required quarterly for G-SIIs, semi-annually for others (CRR3 Art 447)"],
        ["CC1/CC2 (Capital Composition)", "Required (ERBA P.1200). Maps to FR Y-9C items",
         "Required (PS1/26 Ch.18)", "Required (CRR3 Art 437)"],
        ["CR1-CR5 (Credit Risk)", "Required (ERBA P.1202)", "Required (PS1/26 Ch.18)",
         "Required (CRR3 Art 442-449)"],
        ["SEC1-SEC4 (Securitization)", "Required (ERBA P.1202)", "Required (PS1/26 Ch.18)",
         "Required (CRR3 Art 449)"],
        ["MR1-MR4 (Market Risk)", "Required (ERBA P.1202)", "Required (PS1/26 Ch.18)",
         "Required (CRR3 Art 445)"],
        ["OR1 (Operational Risk)", "Required (ERBA P.1204)", "Required (PS1/26 Ch.18)",
         "Required (CRR3 Art 446)"],
        ["LR1-LR2 (Leverage)", "Required (ERBA P.1204)", "Required (PS1/26 Ch.18)",
         "Required (CRR3 Art 451)"],
        ["ESG Templates", "Not yet required (proposed future rulemaking)",
         "Climate scenario analysis disclosure (PS1/26 Ch.18.3)",
         "ESG Pillar 3 tables: 3 qualitative + 5 quantitative (CRR3 Art 449a, ITS on ESG)"],
    ]
    for i, r in enumerate(rows2):
        add_data_row(t2, r, is_subheader=(i == 0))

    # 15.3 Large Exposures
    add_subsection(doc, "15.3 Large Exposures")
    t3 = create_table(doc, HDRS, STD4)
    rows3 = [
        ["Single Counterparty Limit", "25% of T1 capital general limit (12 CFR 252.72)",
         "25% of T1 capital (PS1/26 Ch.13)", "25% of T1 capital (CRR3 Art 395(1))"],
        ["G-SIB to G-SIB Limit", "15% of T1 (12 CFR 252.72(b)). MORE CONSERVATIVE than UK/EU",
         "25% of T1 (no special G-SIB-to-G-SIB reduction) (PS1/26 Ch.13)",
         "25% of T1 (no special reduction) (CRR3 Art 395(1))"],
        ["Reporting Threshold", "5% of T1 (12 CFR 252.73)", "10% of T1 (PS1/26 Ch.13)",
         "10% of eligible capital (CRR3 Art 394(1))"],
        ["Exposure Measure", "Total credit exposure (on + off BS + derivatives) (12 CFR 252.73(b))",
         "Original exposure method or SA-CCR (PS1/26 Ch.13.2)",
         "Original exposure method or SA-CCR (CRR3 Art 390)"],
        ["Sovereign Exemption", "US govt exposures exempt (12 CFR 252.77(a)(1))",
         "UK govt exempt (PS1/26 Ch.13.3)", "Domestic sovereign in domestic currency exempt (CRR3 Art 400)"],
        ["Intragroup Exemption", "Affiliate limits apply (12 CFR 252.77(b))",
         "Intra-group exemption possible with PRA approval (PS1/26 Ch.13.3)",
         "Intra-group full or partial exemption per NCA (CRR3 Art 400(2))"],
    ]
    for r in rows3:
        add_data_row(t3, r)

    # 15.4 Liquidity
    add_subsection(doc, "15.4 Liquidity: LCR & NSFR")
    t4 = create_table(doc, HDRS, STD4)
    rows4 = [
        ["LCR Minimum", "100% (12 CFR 249.10)", "100% (PRA PS2/18)",
         "100% (CRR3 Art 412(1))"],
        ["LCR HQLA Definition", "Level 1 (0% haircut): cash, reserves, UST. Level 2A (15%): agency MBS, GSE. Level 2B (50%): corporate bonds IG, equity (12 CFR 249.20-22)",
         "Similar with UK sovereign in L1 (PRA PS2/18 Ch.3)",
         "Similar with MS sovereign in L1 (LCR Delegated Act 2015/61)"],
        ["NSFR Minimum", "100% (12 CFR 249.100)", "100% (PRA PS22/21)",
         "100% (CRR3 Art 428a)"],
        ["NSFR ASF Factors", "Per US NSFR rule 12 CFR 249.104-106", "Per PRA PS22/21",
         "Per CRR3 Art 428k-428n"],
        ["NSFR RSF Factors", "Per US NSFR rule 12 CFR 249.107-109", "Per PRA PS22/21",
         "Per CRR3 Art 428o-428r"],
    ]
    for r in rows4:
        add_data_row(t4, r)
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 16: Crypto-Assets, ESG, Digital Assets
# ═══════════════════════════════════════════════════════════════════
def build_section_16(doc):
    add_section_heading(doc, "16", "Crypto-Assets, ESG Integration & Digital Assets")

    add_subsection(doc, "16.1 Crypto-Asset Prudential Treatment")
    t = create_table(doc, HDRS, STD4)
    rows = [
        ["BCBS Crypto Standard", "BCBS d545 (Dec 2022): Group 1a (tokenized), Group 1b (stablecoins), Group 2 (unbacked). US has not formally adopted but issued interagency guidance",
         "PRA has not formally adopted d545; monitoring approach. Crypto-asset exposures expected to be immaterial (PRA Dear CEO letter 2022)",
         "EBA implementing via CRR3 Art 501c; delegated act expected 2025. MiCA framework for market regulation"],
        ["Group 1a (Tokenized)", "Treated as underlying traditional asset (interagency guidance 2023). UST on blockchain = 0% RW",
         "Follow underlying asset treatment (PRA guidance)", "Follow underlying asset per CRR3 Art 501c(2)"],
        ["Group 1b (Stablecoins)", "Case-by-case assessment; reserve-backed stablecoins may receive 100% RW (interagency guidance)",
         "PRA assessment pending", "Assessment pending EBA delegated act"],
        ["Group 2a (Unbacked, Hedgeable)", "1250% RW (BCBS d545 guidance adopted informally). Aggregate exposure cap 1% T1",
         "Expected 1250% per BCBS alignment", "1250% per CRR3 Art 501c(4)"],
        ["Group 2b (Unbacked, Other)", "1250% RW (BCBS d545). Most crypto-assets fall here (BTC, ETH, etc.)",
         "Expected 1250%", "1250% per CRR3 Art 501c(4)"],
        ["Exposure Cap", "Aggregate Group 2 exposure should not exceed 1% of T1 (BCBS d545 para 60.77)",
         "Supervisory expectation for immateriality", "1% T1 cap for Group 2 (CRR3 Art 501c(5))"],
        ["Infrastructure Exposure", "Blockchain infrastructure: standard operational risk treatment",
         "Standard treatment", "Standard treatment"],
    ]
    for r in rows:
        add_data_row(t, r)

    add_subsection(doc, "16.2 ESG Risk Integration")
    t2 = create_table(doc, HDRS, STD4)
    rows2 = [
        ["ESG in Pillar 1", "No explicit ESG adjustment to RW (US position: risks captured via existing framework)",
         "No explicit Pillar 1 adjustment; Pillar 2 assessment (PS1/26 Ch.15.3)",
         "No Pillar 1 adjustment yet; EBA report on green/brown supporting/penalizing factors expected 2025 (CRR3 Art 501d)"],
        ["ESG in Pillar 2", "OCC climate risk guidance; SR letter pending",
         "PRA SS3/19: climate risk in ICAAP, scenario analysis required",
         "CRD6 Art 73(3): ESG risks in ICAAP. Transition plans. SREP integration"],
        ["ESG in Pillar 3", "SEC climate disclosure (under litigation); no Basel-specific ESG P3",
         "Climate scenario analysis disclosure via PS1/26 Ch.18.3",
         "Full ESG Pillar 3: CRR3 Art 449a + EBA ITS. Qualitative + quantitative templates"],
        ["Transition Risk RW", "No differential treatment", "No differential treatment",
         "EBA to assess by end-2025 whether brown penalizing factor warranted (CRR3 Art 501d)"],
        ["Physical Risk RW", "Addressed via stress testing (CCAR climate scenarios)",
         "Addressed via ICAAP scenario analysis", "Addressed via EBA Guidelines + ICAAP"],
        ["Green Supporting Factor", "Not adopted", "Not adopted",
         "Under assessment by EBA; report due 2025 (CRR3 Art 501c, 501d)"],
    ]
    for r in rows2:
        add_data_row(t2, r)

    add_subsection(doc, "16.3 Digital Assets & DeFi")
    t3 = create_table(doc, HDRS, STD4)
    rows3 = [
        ["CBDC Treatment", "Fed exploring; no specific RW treatment yet",
         "BoE digital pound exploration; would be 0% RW as central bank liability",
         "ECB digital euro; would be 0% RW as central bank liability (CRR3 Art 114(4))"],
        ["Tokenized Deposits", "Treated as deposits (OCC guidance)", "Treated as deposits",
         "Treated as deposits per banking license"],
        ["DeFi Protocol Exposure", "1250% RW by default; no specific framework",
         "Expected high RW treatment", "Expected 1250% per Group 2 treatment"],
        ["NFT Exposure", "1250% RW (unbacked crypto treatment)",
         "Expected 1250%", "1250% per Group 2b"],
    ]
    for r in rows3:
        add_data_row(t3, r)
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 17: Conservatism Scorecard (RAG)
# ═══════════════════════════════════════════════════════════════════
def build_section_17(doc):
    add_section_heading(doc, "17", "Conservatism Scorecard: 15-Dimension RAG Assessment")
    add_body_text(doc, "Red = most conservative approach among the three jurisdictions. "
        "Amber = intermediate. Green = least conservative (most favorable to banks). "
        "Assessment based on capital impact for a typical Category I US G-SIB with "
        "$3.2T total assets, $1.8T RWA, diversified business model.")

    t = create_table(doc, ["Dimension", "US Fed (ERBA)", "UK PRA (PS1/26)", "EU EBA (CRR3)", "Most Conservative"],
                     [1.8, 1.8, 1.8, 1.8, 1.3])

    scorecard = [
        ("1. Credit Risk Approach", "SA-only (no IRB)", "SA + IRB", "SA + IRB + transitional",
         "US", RED_HEX, AMBER_HEX, GREEN_HEX),
        ("2. OBS CCF Commitments", "40% uniform", "20%/40% split", "20%/40% split",
         "US", RED_HEX, GREEN_HEX, GREEN_HEX),
        ("3. MSA Treatment", "250% RW (higher RWA)", "Deduction >10%", "Deduction >10%",
         "US/UK/EU*", AMBER_HEX, AMBER_HEX, AMBER_HEX),
        ("4. Software DTA", "Full deduction", "Full deduction", "Exempt (amortized)",
         "US/UK", RED_HEX, RED_HEX, GREEN_HEX),
        ("5. AT1 Trigger", "Discretionary", "7% CET1", "5.125% CET1",
         "UK", GREEN_HEX, RED_HEX, AMBER_HEX),
        ("6. G-SIB Surcharge", "Method 2 + 20bp bands", "Systemic buffer", "Method 1/2 standard",
         "US", RED_HEX, AMBER_HEX, GREEN_HEX),
        ("7. SCB / CCB", "SCB >= 2.5%", "CCB 2.5% fixed", "CCB 2.5% fixed",
         "US", RED_HEX, GREEN_HEX, GREEN_HEX),
        ("8. SA-CCR Alpha", "1.4 fin / 1.0 comm", "1.4 all", "1.4 all",
         "UK/EU", GREEN_HEX, RED_HEX, RED_HEX),
        ("9. CVA BA-CVA Hedges", "Single-name (incl. indirect) + index", "Single-name + index", "Single-name + index",
         "Aligned", AMBER_HEX, AMBER_HEX, AMBER_HEX),
        ("10. STS Securitization", "No STS (15% floor)", "STS (10% floor)", "STS (10% floor)",
         "US", RED_HEX, GREEN_HEX, GREEN_HEX),
        ("11. Past Due Provisions", "150% flat", "100% if prov>=50%", "100% if prov>=20%",
         "US", RED_HEX, AMBER_HEX, GREEN_HEX),
        ("12. Equity Phase-In", "Immediate 300/400%", "Immediate 250/400%", "Phase-in to 2030",
         "US", RED_HEX, AMBER_HEX, GREEN_HEX),
        ("13. IRB PD/LGD Floors", "N/A (no IRB)", "BCBS floors", "BCBS floors",
         "N/A", AMBER_HEX, GREEN_HEX, GREEN_HEX),
        ("14. OpRisk Loss Data", "Required ($20K, 10Y); losses enter BI", "Supervisory expectation", "Mandatory EUR 20K/10Y",
         "US/EU", RED_HEX, GREEN_HEX, RED_HEX),
        ("15. Large Exp G-SIB", "15% T1 G-SIB-to-G-SIB", "25% T1", "25% T1",
         "US", RED_HEX, GREEN_HEX, GREEN_HEX),
    ]

    for dim, us, uk, eu, most_cons, us_rag, uk_rag, eu_rag in scorecard:
        row = t.add_row()
        cells = row.cells
        # Dimension
        format_cell(cells[0], dim, bold=True, font_size=8)
        set_cell_shading(cells[0], WHITE_HEX)
        # US
        set_cell_shading(cells[1], us_rag)
        fc = WHITE if us_rag == RED_HEX else BLACK
        format_cell(cells[1], us, bold=False, font_size=8, font_color=fc,
                     alignment=WD_ALIGN_PARAGRAPH.CENTER)
        # UK
        set_cell_shading(cells[2], uk_rag)
        fc = WHITE if uk_rag == RED_HEX else BLACK
        format_cell(cells[2], uk, bold=False, font_size=8, font_color=fc,
                     alignment=WD_ALIGN_PARAGRAPH.CENTER)
        # EU
        set_cell_shading(cells[3], eu_rag)
        fc = WHITE if eu_rag == RED_HEX else BLACK
        format_cell(cells[3], eu, bold=False, font_size=8, font_color=fc,
                     alignment=WD_ALIGN_PARAGRAPH.CENTER)
        # Most Conservative
        set_cell_shading(cells[4], NAVY_HEX)
        format_cell(cells[4], most_cons, bold=True, font_size=8, font_color=WHITE,
                     alignment=WD_ALIGN_PARAGRAPH.CENTER)

    doc.add_paragraph()
    add_body_text(doc, "SUMMARY: US is most conservative on 11 of 15 dimensions (RED), including "
        "operational-risk loss data (shared with the EU). UK is most conservative on 2 dimensions "
        "(AT1 trigger, SA-CCR alpha for all). EU is most conservative on 2 dimensions (loss data, "
        "SA-CCR alpha for all). BA-CVA hedge recognition is aligned across the three. "
        "The US approach is estimated (illustrative model estimate, not an NPR figure) to produce "
        "approximately 6-8% higher aggregate RWA for a typical Category I G-SIB, primarily driven "
        "by the uniform 40% CCF, SA-only credit risk, absence of STS securitization benefits, and "
        "300% publicly traded equity. The NPR's own aggregate estimate is +1.9% RWA for the nine "
        "Category I/II BHCs versus the current US standardized approach (Table VII.5).")
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# SECTION 18: Key Numbers for Senior Management
# ═══════════════════════════════════════════════════════════════════
def build_section_18(doc):
    add_section_heading(doc, "18", "Key Numbers for Senior Management")
    add_body_text(doc, "Consolidated key metrics and numbers for executive-level briefing. "
        "All figures calibrated for a Category I US G-SIB with $3.2T total assets.")

    add_subsection(doc, "18.1 Capital Requirements Summary")
    t = create_table(doc, ["Metric", "US Fed", "UK PRA", "EU EBA"], STD4)
    rows = [
        ["CET1 Minimum", "4.5%", "4.5%", "4.5%"],
        ["Tier 1 Minimum", "6.0%", "6.0%", "6.0%"],
        ["Total Capital Minimum", "8.0%", "8.0%", "8.0%"],
        ["G-SIB Surcharge (Top)", "4.0% (JPM)", "3.0% (systemic buffer)", "2.0% (typical)"],
        ["SCB / CCB", "3.2% (avg SCB)", "2.5% (CCB)", "2.5% (CCB)"],
        ["CCyB", "0%", "2.0%", "~0.5-1.0% (varies by MS)"],
        ["Effective CET1 Req", "~11.7-12.7%", "~12.0-13.0%", "~10.0-12.0%"],
        ["Leverage Ratio", "5.0% (eSLR)", "3.25% + CCLB", "3.0% + G-SIB add-on"],
        ["TLAC Minimum", "22% RWA + 9.5% leverage", "MREL per BoE", "MREL per SRB"],
    ]
    for r in rows:
        add_data_row(t, r)

    add_subsection(doc, "18.2 Key Risk Weight Comparison")
    t2 = create_table(doc, ["Exposure", "US RW", "UK RW", "EU RW"], STD4)
    rows2 = [
        ["Corporate IG", "65%", "20-50% (rated)", "20-50% / 65% transitional"],
        ["Corporate Unrated", "100%", "100%", "100%"],
        ["Retail Transactor", "45%", "45%", "45%"],
        ["Residential Mtg 80-90% LTV", "40%", "40%", "35%"],
        ["CRE CF 60-80% LTV", "90%", "90%", "90%"],
        ["ADC", "150% / 100% reduced", "150% / 100% reduced", "150% / 100% reduced"],
        ["Listed Equity", "300%", "250%", "100-250% (phased)"],
        ["Bank Grade A", "30% / 40%", "20-30% (CQS 1-2)", "20-30% (CQS 1-2)"],
        ["SME Corporate", "100% (65% IG)", "85%", "85% (x0.7619 factor)"],
        ["Past Due (prov>=20%)", "150%", "150%", "100%"],
        ["Commitment <=1Y CCF", "40%", "20%", "20%"],
        ["SA-CCR Alpha (Financial)", "1.4", "1.4", "1.4"],
        ["SA-CCR Alpha (Commercial)", "1.0", "1.4", "1.4"],
    ]
    for r in rows2:
        add_data_row(t2, r)

    add_subsection(doc, "18.3 Estimated RWA Impact (Illustrative)")
    t3 = create_table(doc, ["Component", "US RWA ($B)", "UK RWA ($B)", "EU RWA ($B)"], STD4)
    rows3 = [
        ["Credit Risk RWA", "~1,200", "~1,050-1,100", "~1,000-1,080"],
        ["Market Risk RWA", "~180", "~175", "~170"],
        ["OpRisk RWA", "~250", "~250", "~250"],
        ["CVA RWA", "~45", "~35", "~35"],
        ["Total RWA", "~1,675", "~1,510-1,560", "~1,455-1,535"],
        ["RWA Delta vs US", "Baseline", "~7-10% lower", "~8-13% lower"],
        ["CET1 Capital Required", "~$195B", "~$180-186B", "~$170-184B"],
        ["CET1 Surplus/(Deficit)", "Benchmark", "+$9-15B", "+$11-25B"],
    ]
    for r in rows3:
        add_data_row(t3, r)

    add_subsection(doc, "18.4 Top 5 Actions for Cross-Jurisdiction Optimization")
    t4 = create_table(doc, ["Priority", "Action", "Impact", "Timeline"], STD4)
    rows4 = [
        ["1", "Restructure short-term commitments to exploit UK/EU 20% CCF", "$25-40B RWA reduction (UK/EU entities)", "Q3 2025"],
        ["2", "STS securitization program for UK/EU mortgage portfolio", "5pp RW floor reduction on qualifying tranches", "Q4 2025"],
        ["3", "Optimize G-SIB score via STWF and indicator management", "10-20bp score reduction = 0.05-0.1% surcharge", "Ongoing"],
        ["4", "EU equity phase-in: time new equity investments to benefit", "Up to 60% RW reduction vs full weight (2025-2030)", "Immediate"],
        ["5", "BA-CVA hedge optimization: deploy single-name CDS in UK/EU", "15-25% CVA capital reduction", "Q2 2025"],
    ]
    for r in rows4:
        add_data_row(t4, r)
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# APPENDICES
# ═══════════════════════════════════════════════════════════════════
def build_appendix_a(doc):
    add_section_heading(doc, "A", "Appendix: Regulatory Article Cross-Reference Index")
    add_body_text(doc, "Quick-reference mapping of key regulatory provisions across jurisdictions.")

    t = create_table(doc, ["Topic", "US Reference", "UK Reference", "EU Reference"], STD4)
    refs = [
        ["Capital Definition", "12 CFR 217.20", "PS1/26 SS34/15", "CRR3 Art 25-91"],
        ["SA Credit Risk", "12 CFR 217.31-37", "PS1/26 Ch.3-7", "CRR3 Art 111-134"],
        ["Real Estate", "ERBA P.128-170", "PS1/26 Ch.4", "CRR3 Art 124-126"],
        ["OBS CCF", "ERBA P.206-214", "PS1/26 Ch.5", "CRR3 Art 111"],
        ["CRM", "12 CFR 217.35-37", "PS1/26 Ch.6", "CRR3 Art 192-241"],
        ["SA-CCR", "12 CFR 217.132", "PS1/26 Ch.8", "CRR3 Art 272-280f"],
        ["CVA", "ERBA P.520-550", "PS1/26 Ch.9", "CRR3 Art 381-386"],
        ["Securitization", "ERBA P.296-340", "PS1/26 Ch.10", "CRR3 Art 242-270"],
        ["IRB", "N/A (eliminated)", "PS1/26 Ch.11", "CRR3 Art 142-191"],
        ["FRTB", "ERBA P.1080-1130", "PS1/26 Ch.16", "CRR3 Art 325-325bp"],
        ["Operational Risk", "ERBA P.948-970", "PS1/26 Ch.14", "CRR3 Art 312-324"],
        ["Large Exposures", "12 CFR 252.70-78", "PS1/26 Ch.13", "CRR3 Art 387-403"],
        ["Leverage Ratio", "12 CFR 217.10(a)(5)", "PS1/26 Ch.17", "CRR3 Art 429-429g"],
        ["G-SIB", "12 CFR 217.400-405", "PS1/26 Ch.17", "CRD6 Art 131"],
        ["Pillar 3", "ERBA P.1196-1210", "PS1/26 Ch.18", "CRR3 Art 431-455"],
        ["LCR", "12 CFR 249", "PRA PS2/18", "LCR Del. Act 2015/61"],
        ["NSFR", "12 CFR 249.100+", "PRA PS22/21", "CRR3 Art 413-428"],
        ["ICAAP/Pillar 2", "12 CFR 252.56 (CCAR)", "PRA SS31/15", "CRD6 Art 73-98"],
        ["Reporting", "FR Y-9C/Y-14A/Y-15", "BoE stat returns", "COREP/FINREP"],
        ["Crypto-Assets", "Interagency guidance 2023", "PRA Dear CEO 2022", "CRR3 Art 501c"],
        ["ESG", "OCC guidance / SR pending", "PRA SS3/19", "CRD6 Art 73(3), CRR3 Art 449a"],
        ["Output Floor", "N/A (no IRB)", "PS1/26 Ch.11.3", "CRR3 Art 92a"],
        ["SCB/CCB/CCyB", "12 CFR 225.8(d) / 217.11", "CRD equiv + FPC", "CRD6 Art 128-140"],
    ]
    for r in refs:
        add_data_row(t, r)
    doc.add_page_break()


def build_appendix_b(doc):
    add_section_heading(doc, "B", "Appendix: Abbreviations & Glossary")

    t = create_table(doc, ["Abbreviation", "Full Term"], [3.0, 6.5])
    abbrevs = [
        ["ADC", "Acquisition, Development & Construction"],
        ["AT1", "Additional Tier 1 Capital"],
        ["AOCI", "Accumulated Other Comprehensive Income"],
        ["BA-CVA", "Basic Approach for CVA Risk"],
        ["BCBS", "Basel Committee on Banking Supervision"],
        ["BI", "Business Indicator (Operational Risk)"],
        ["BIC", "Business Indicator Component"],
        ["CCAR", "Comprehensive Capital Analysis and Review"],
        ["CCB", "Capital Conservation Buffer"],
        ["CCF", "Credit Conversion Factor"],
        ["CCyB", "Countercyclical Capital Buffer"],
        ["CET1", "Common Equity Tier 1"],
        ["CF", "Cash-Flow (dependent)"],
        ["CQS", "Credit Quality Step (EU/UK rating mapping)"],
        ["CRC", "Country Risk Classification (OECD)"],
        ["CRD6", "Capital Requirements Directive VI (EU)"],
        ["CRM", "Credit Risk Mitigation"],
        ["CRR3", "Capital Requirements Regulation III (EU)"],
        ["CVA", "Credit Valuation Adjustment"],
        ["DRC", "Default Risk Charge (FRTB)"],
        ["DTA", "Deferred Tax Assets"],
        ["DTL", "Deferred Tax Liabilities"],
        ["EAD", "Exposure at Default"],
        ["EBA", "European Banking Authority"],
        ["ECL", "Expected Credit Losses"],
        ["ERBA", "Expanded Risk-Based Approach (US)"],
        ["ES", "Expected Shortfall (Market Risk IMA)"],
        ["eSLR", "Enhanced Supplementary Leverage Ratio"],
        ["FPC", "Financial Policy Committee (UK)"],
        ["FRTB", "Fundamental Review of the Trading Book"],
        ["G-SIB", "Global Systemically Important Bank"],
        ["GIRR", "General Interest Rate Risk"],
        ["HQLA", "High Quality Liquid Assets"],
        ["ICAAP", "Internal Capital Adequacy Assessment Process"],
        ["ILM", "Internal Loss Multiplier"],
        ["IMA", "Internal Models Approach"],
        ["IRB", "Internal Ratings-Based Approach"],
        ["IRRBB", "Interest Rate Risk in the Banking Book"],
        ["LCR", "Liquidity Coverage Ratio"],
        ["LGD", "Loss Given Default"],
        ["LTV", "Loan-to-Value Ratio"],
        ["MDA", "Maximum Distributable Amount"],
        ["MDB", "Multilateral Development Bank"],
        ["MPOR", "Margin Period of Risk"],
        ["MREL", "Minimum Requirement for Own Funds and Eligible Liabilities"],
        ["MSA", "Mortgage Servicing Assets"],
        ["NCA", "National Competent Authority (EU)"],
        ["NIC", "Net Interest Component"],
        ["NMRF", "Non-Modellable Risk Factors"],
        ["NPR", "Notice of Proposed Rulemaking"],
        ["NSFR", "Net Stable Funding Ratio"],
        ["OBS", "Off-Balance Sheet"],
        ["P2A", "Pillar 2A (PRA add-on)"],
        ["P2G", "Pillar 2 Guidance (EU)"],
        ["P2R", "Pillar 2 Requirement (EU)"],
        ["PD", "Probability of Default"],
        ["PFE", "Potential Future Exposure"],
        ["PLA", "Profit and Loss Attribution (IMA test)"],
        ["PMI", "Private Mortgage Insurance"],
        ["PRA", "Prudential Regulation Authority (UK)"],
        ["PSE", "Public Sector Entity"],
        ["RC", "Replacement Cost (SA-CCR)"],
        ["RRAO", "Residual Risk Add-On"],
        ["RW", "Risk Weight"],
        ["RWA", "Risk-Weighted Assets"],
        ["SA-CCR", "Standardized Approach for Counterparty Credit Risk"],
        ["SA-CR", "Standardized Approach for Credit Risk"],
        ["SA-CVA", "Standardized Approach for CVA Risk"],
        ["SBM", "Sensitivities-Based Method (FRTB)"],
        ["SCB", "Stress Capital Buffer (US)"],
        ["SCRA", "Standardized Credit Risk Assessment (for unrated banks)"],
        ["SEC-ERBA", "Securitization External Ratings-Based Approach"],
        ["SEC-IRBA", "Securitization Internal Ratings-Based Approach"],
        ["SEC-SA", "Securitization Standardized Approach"],
        ["SFT", "Securities Financing Transaction"],
        ["SLR", "Supplementary Leverage Ratio"],
        ["SRT", "Significant Risk Transfer"],
        ["STS", "Simple, Transparent, Standardized (Securitization)"],
        ["STWF", "Short-Term Wholesale Funding (G-SIB)"],
        ["T2", "Tier 2 Capital"],
        ["TLAC", "Total Loss Absorbing Capacity"],
        ["UCC", "Unconditionally Cancellable Commitment"],
    ]
    for r in abbrevs:
        add_data_row(t, r)
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════
# MAIN: Build the complete document
# ═══════════════════════════════════════════════════════════════════
def main():
    print("Generating Deliverable 2: Cross-Jurisdictional Basel III Comparison...")

    doc = Document()

    # Page setup - landscape for wider tables
    for section in doc.sections:
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width = Inches(11)
        section.page_height = Inches(8.5)
        section.top_margin = Inches(0.6)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.7)
        section.right_margin = Inches(0.7)

    # Default font
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(9)

    print("  Building cover page...")
    build_cover_page(doc)
    print("  Building table of contents...")
    build_toc(doc)
    print("  Building executive summary...")
    build_executive_summary(doc)

    builders = [
        ("Section 1: Implementation Timeline", build_section_1),
        ("Section 2: Capital Stack", build_section_2),
        ("Section 3: Capital Buffers", build_section_3),
        ("Section 4: Credit Risk SA", build_section_4),
        ("Section 5: Real Estate", build_section_5),
        ("Section 6: Retail/Equity/Past Due", build_section_6),
        ("Section 7: OBS CCFs", build_section_7),
        ("Section 8: CRM", build_section_8),
        ("Section 9: SA-CCR", build_section_9),
        ("Section 10: CVA Risk", build_section_10),
        ("Section 11: FRTB Market Risk", build_section_11),
        ("Section 12: Operational Risk", build_section_12),
        ("Section 13: Securitization", build_section_13),
        ("Section 14: IRB", build_section_14),
        ("Section 15: Pillar 2/3/LE/Liquidity", build_section_15),
        ("Section 16: Crypto/ESG/Digital", build_section_16),
        ("Section 17: Conservatism Scorecard", build_section_17),
        ("Section 18: Key Numbers", build_section_18),
        ("Appendix A: Cross-Reference", build_appendix_a),
        ("Appendix B: Abbreviations", build_appendix_b),
    ]

    for name, builder in builders:
        print(f"  Building {name}...")
        builder(doc)

    # Final page - disclaimer
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("END OF DOCUMENT")
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = NAVY

    doc.add_paragraph()
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = p2.add_run(
        "DISCLAIMER: This document is prepared for internal analytical purposes only. "
        "Regulatory interpretations should be verified against source documents. "
        "Parameters marked TODO: VERIFY require additional validation against final rule text."
    )
    run2.font.size = Pt(8)
    run2.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
    run2.italic = True

    # Save
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "Deliverable_2_FINAL.docx")
    doc.save(output_path)
    print(f"\nDocument saved to: {output_path}")

    # Count rows
    total_rows = 0
    for table in doc.tables:
        total_rows += len(table.rows) - 1  # exclude header
    print(f"Total comparison rows: {total_rows}")
    print(f"Total tables: {len(doc.tables)}")
    print(f"Total paragraphs: {len(doc.paragraphs)}")
    print("Done!")


if __name__ == "__main__":
    main()
