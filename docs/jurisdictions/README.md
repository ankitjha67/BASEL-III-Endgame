# Multi-jurisdiction Basel III engines

`src/jurisdictions/` holds one package per regulator. Each implements the `RegimeCalculator`
contract in `src/jurisdictions/base.py`:

- SA credit risk for every exposure class, including CCFs and CRM;
- operational risk;
- the output floor;
- the capital, buffer and leverage stack;
- SA-CCR EAD;
- BA-CVA.

Every parameter is transcribed from the regulator's own legal text. The verbatim tables are in the
per-regime references in this folder (`<CC>_parameter_reference.md`).

## Source documents

| Code | Regime | Legal text used | Reference |
|---|---|---|---|
| `bcbs` | Basel Committee | Basel Framework, consolidated (BIS, 1,429 pp.); *Basel III: Finalising post-crisis reforms* (d424, Dec 2017) for cross-checks | [BCBS](BCBS_parameter_reference.md) |
| `us` | United States | ERBA NPR, March 2026 (OCC NR 2026-16a), via the engine's `src/` calculators | [ERBA](../ERBA_NPR_2026_parameter_reference.md) |
| `uk` | United Kingdom (PRA) | PS1/26 Appendix 1, *PRA Rulebook: CRR Firms: (CRR) Instrument 2026* (492 pp.) | [UK](UK_parameter_reference.md) |
| `eu` | European Union | Regulation (EU) 2024/1623 (CRR3); consolidated CRR 575/2013 for unchanged articles; EBA Policy Advice (Aug 2019) for context only | [EU](EU_parameter_reference.md) |
| `sg` | Singapore (MAS) | MAS Notice 637, version effective 1 January 2026 (1,110 pp.) | [SG](SG_parameter_reference.md) |
| `ca` | Canada (OSFI) | Capital Adequacy Requirements (CAR) Guideline 2026, chapters 1–9 | [CA](CA_parameter_reference.md) |

## Key differences

| Topic | BCBS | US | UK | EU | SG | CA |
|---|---|---|---|---|---|---|
| Output floor | 72.5%; phase-in 50% (2023) → 72.5% (2028) (RBC90.1); optional 25% cap (RBC90.2) | None: single expanded risk-based approach | 60/65/70/72.5% for 2027–30 (Art 92(5)); provisions adjustment; no transitional cap | 50→72.5% over 2025–30 (Art 465(1)); optional 125% cap to 2029 (465(2)); floor-only transitionals for unrated corporates (65%) and mortgages (465(3),(5)) | 50% (1 Jul 2024) → 72.5% (2029) (Table 5-3); MAS may set higher | 67.5% "until further notice" (CAR Ch.1 s.1.5.1) |
| Op-risk BIC thresholds | €1bn / €30bn (OPE25.7) | $1bn / $30bn, CPI-W indexed (§ __.150) | £0.88bn / £26bn | €1bn / €30bn (Art 313) | S$1.5bn / S$45bn (9.1.2) | C$1.5bn / C$45bn (Ch.3 s.3.4) |
| ILM | Loss-component formula; national option to set 1 (OPE25.11) | None (RWA = 12.5 × BIC) | 1 (Op Risk Part rule 5.9) | None (Art 312) | Computed above S$1.5bn (9.1.8) | Computed; floored at 1 without 10 years of data |
| SA-CCR alpha | 1.4 for all counterparties (CRE52.1) | 1.0 for commercial end users (§ __.114(e)(4)) | 1.0 for non-financials and pension schemes (Art 274(2)); 2027–29 add-on | 1.4 (Art 274(2)) | 1.4 | 1.4 |
| Ratings | ECRA / SCRA | Not used (Dodd-Frank s.939A) | ECRA / SCRA | CQS / SCRA | ECRA / SCRA | ECRA / SCRA |
| Unrated corporate | 100%; IG 65% (national option) | IG 65%, otherwise 100% | 100%; with permission 65% IG / 135% non-IG (Art 122(5)–(6)) | 100% (floor transitional 65%) | 100% | 100%; IG option; non-IG 150% as printed |
| SME corporate | 85% | No preference (100%) | 85%; support factors removed (Pillar 2A) | No 85%; SME supporting factor 0.7619 / 0.85 (Art 501) | 85% (revenue ≤ S$100m) | 85% |
| Residential real estate | Whole loan (CRE20.82); loan-splitting is a national option | Six LTV bands, 20–70% (Table 5 to § __.111) | Mandatory loan-splitting: 20% up to 55% of property value (Arts 124F, 124L) | Mandatory loan-splitting: 20% up to 55% of value (Art 125) | Whole loan only | Whole loan; seven LTV bands (Table 10) |
| Transactors | 45% | 45% | 45% | 45% | 45% | **CAR prints 15%** while citing CRE20.68 (45%); engine defaults to 45%, flag switches to 15% |
| Unconditionally cancellable commitments | 10% | 10% | 10% (Table A1) | 0% until 2029, then rising to 10% in 2033 (Art 495d) | 10% | 10% (undrawn cards 25%) |
| Equity | 250% / 400%; phase-in from 2023 (CRE90.1) | 300% listed / 400% non-public / 600% leveraged (§ __.141) | 2027–29 transitional to 250% / 400% | 2025–29 phase-in (Art 495a) | 2024–28 phase-in (Table 7-16) | 250% / 400% |
| CET1 / T1 / Total minimums | 4.5 / 6 / 8% | 4.5 / 6 / 8% | 4.5 / 6 / 8% | 4.5 / 6 / 8% (Art 92) | **6.5 / 8 / 10% for D-SIBs** (Table 4-1) | 4.5 / 6 / 8% |
| Buffers | CCB 2.5%; CCyB; G-SIB 1.0–3.5% | SCB (≥ 2.5%) replaces CCB; G-SIB per 12 CFR 217.403 | CCB / CCyB / O-SII: TODO VERIFY (outside the instrument) | CRD buffers as inputs (TODO VERIFY) | CCB 2.5%; CCyB | CCB 2.5%; D-SIB 1%; DSB 0–4% (input) |
| Leverage | 3% + 50% of the G-SIB HLA | eSLR 3% + 2% | TODO VERIFY (Leverage Ratio Part) | 3% + 50% of the G-SII rate (Art 92(1a)) | 3% | 3%; 3.5% for D-SIBs |

## Cross-jurisdiction run

`src/jurisdictions/comparison.py` takes the same synthetic bank through all six rulebooks. Stage 18
of `scripts/run_end_to_end.py` runs it for 2027 and for the 2030 end state, and the result is written
to `output/reports/e2e/` (Markdown, JSON, and Excel sheets `Jurisdictions_2027`, `Jurisdictions_2030`,
`Jurisdiction_Credit` and `Output_Floor_WhatIf`).

- **Currency.** Monetary thresholds are applied in each regime's own currency. USD inputs are converted
  at the ECB reference rates of 31 Dec 2024: EUR/USD 1.0389, GBP 0.82918, CAD 1.4948 and SGD 1.4164
  per EUR. The EUR/USD rate is the one the Fed used in FR Doc. 2025-22964.
- **Held common across regimes:** market-risk RWA (US FRTB-SA engine), securitisation RWA (US SEC-SA
  engine), capital resources and the leverage exposure measure.
- **Output floor.** The bank uses standardised approaches only, so the floor cannot bind. The floor
  what-if instead applies each regime's schedule to hypothetical modelled-to-SA ratios of 50%, 60% and
  70%.

## Open items (`TODO: VERIFY`)

Each package's reference file lists its own items. The main ones:

- **UK:** buffer rates, leverage ratio and most of SA-CCR sit in other PRA Rulebook Parts that the
  PS1/26 instrument doesn't contain. These use BCBS placeholders and are flagged.
- **EU:** CRD buffer rates and the CRD VI output-floor transitional (Directive (EU) 2024/1619) were
  not supplied. They are inputs.
- **CA:** the 15% transactor weight versus 45% (see the table above); the Domestic Stability Buffer
  level (set by OSFI announcement); unrated non-IG corporates at 150% as printed.
- **SG:** no rates set for the D-SIB leverage buffer or the HLA buffer (inputs, default 0).
- **BCBS:** three formulas are images in the Framework PDF (SA-CCR multiplier, CRM, BA-CVA). They were
  taken from d424 or the CRR, where the same formula is printed, and cited.
- **Not yet modelled per jurisdiction:** FRTB-SA risk weights and correlations, and securitisation.
