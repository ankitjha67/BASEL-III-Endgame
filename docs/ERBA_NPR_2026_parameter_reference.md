# ERBA NPR (March 2026) — parameter reference transcribed from the regulatory text

Source: OCC news release NR 2026-16a attachment, "Regulatory Capital Rules: Category I and II
Banking Organizations; Banking Organizations with Significant Trading Activity" (OCC / Board / FDIC,
1,241 pages). Page numbers below are the PDF page numbers of the common rule text (pp. 674-988).
This file is the working transcription used to reconcile the engine; where it and the PDF differ,
the PDF governs.


## §__.101 Definitions (p.675-684)
- Grade A bank: IG + capital ≥ higher of (min + buffers) / well-capitalized. Not Grade A if ratios not disclosed in 6 months, adverse audit opinion 12 months, or foreign non-Basel-consistent.
- Grade B: spec or IG + capital ≥ min / adequately capitalized. Grade C: otherwise.
- Interest-earning assets definition (loans, leases, interest securities, interest-bearing balances, fed funds sold, reverse repos).
- Investment management / investment services / non-lending treasury services definitions (op risk services component).
- Noninterest expense for BI excludes salaries/benefits, premises, goodwill impairment, intangibles amortization.
- 7 op loss event types.
- Project finance; operational phase definition.
- Regulatory retail: revolving/term loan/lease; aggregate ≤ $1 million (indexed §__.4). SME ≤ $50 million revenues.
- Transactor: repaid in full at each scheduled date for prior 12 months, or overdraft with no drawdown 12 months.
- Subordinated exposure incl. preferred stock not equity.

## §__.111 General risk weights (p.686-700)
- US gov 0%; conditional guarantee 20%; PPP 0%.
- Table 1 sovereign by CRC: 0-1→0, 2→20, 3→50, 4-6→100, 7→150; OECD no CRC 0; non-OECD no CRC 100; default 150.
- Supranational/MDB 0%. GSE 20%; subordinated GSE 150% (FHLB/Farmer Mac sub 20%).
- Table 2 Bank: Grade A meeting (d)(2) 30%, Grade A otherwise 40%, Grade B 75%, Grade C 150%. Trade-related ≤3m foreign bank: 20/20/50/150.
  (d)(2): CBLR bank, or CET1 ≥14% & SLR 5% (Cat I-III) / T1 leverage 5% (others) / CU net worth 9% / foreign CET1 14% & leverage 5%.
  Foreign bank floor = home sovereign RW unless local currency etc. Subordinated bank/covered debt instrument 150%.
- US PSE GO 20%, revenue 50%. Table 3 foreign PSE GO: CRC 0-1→20, 2→50, 3→100, 4-7→150; OECD no CRC 20; non-OECD 100; default 150. Table 4 revenue: 0-1→50, 2-3→100, 4-7→150; OECD no CRC 50.
- Real estate: statutory multifamily 50%; pre-sold construction 50% (100% if cancelled); HVCRE 150%; ADC non-HVCRE 100%.
- **Table 5 resi NOT dependent on CF by LTV: ≤50 20%, ≤60 25%, ≤80 30%, ≤90 40%, ≤100 50%, >100 70%.**
- **Table 6 resi dependent: 30/35/45/60/75/105.**
- **Table 7 CRE not dependent: LTV≤60 → min(60%, borrower RW); >60 → borrower RW (100% if unknown).**
- **Table 8 CRE dependent: ≤60 70%, 60-80 90%, >80 110%.**
- Other real estate 150% (resi not dependent: 100%). Past-due real estate 150% (resi not dependent 100%).
- Retail: regulatory retail 75%; transactor 45%; other retail 100%.
- Corporate 100%; IG (internal rating system criteria) 65%; equipment/physical commodity object finance 100%; project finance operational 100% / pre-operational 130%; QCCP cash collateral 2%/4%; subordinated / covered debt instrument 150%.
- Past due non-sovereign non-RE 150%.
- Other assets: cash 0%, CIPC 20%, DTA carryback 100%, MSAs 250%, DTA temp diff 250%, other 100%. Policy loans 20%.

## §__.112 OBS CCFs (p.700-)
- 10% unconditionally cancelable; 20% trade-related ≤1y; 40% commitments; 50% transaction-related contingent + NIF/RUF; 100% guarantees, repos, CERW, sec lending/borrowing...
- Retail commitment without contractual max: undrawn = highest drawn over 24 months − current drawn.

## §__.113 CCR / extended SA-CCR (p.703-705)
- SA-CCR mandatory for derivatives; MAY use SA-CCR for netting set under qualifying cross-product master netting agreement (derivatives + repo-style, non-cleared).
- Extended SA-CCR: EAD_NC = (1 − MR_NC)·(EAD_repo(haircut approach) + EAD_deriv(SA-CCR)) + MR_NC·EAD_SACCR(all). MR_NC = NWM_repo / max(NWM_repo, NWM_deriv); maturities floored 10 bd, capped 1 year.
- Repo as derivative: delta +1 repo/sec lending, −1 reverse repo/sec borrowing; MPOR ≥ 5 bd + periodicity − 1.

## §__.114 SA-CCR (p.705-726)
- EAD = 1.4 × (RC + PFE). Margined: min(margined, unmargined). Sold options fully paid, no VM: 0. **Commercial end-user: EAD = RC + PFE (alpha 1.0)**.
- Client-facing: haircut scaling sqrt(1/2)=0.707107; scaling = sqrt(H/10).
- RC margined = max(V − C; TH + MTA − NICA; 0). Unmargined = max(V − C; 0).
- PFE multiplier = min(1; 0.05 + 0.95·exp((V−C)/(1.9·A))).
- IR hedging set: Formula 1 sqrt(D1²+D2²+D3² + 1.4 D1D2 + 1.4 D2D3 + 0.6 D1D3); or Formula 2 |D1|+|D2|+|D3|.
- Credit/equity: sqrt((Σρ_k AddOn_k)² + Σ(1−ρ_k²)AddOn_k²). Commodity same with single ρ.
- SD = max((e^{-0.05 S/250} − e^{-0.05 E/250})/0.05, 0.04).
- Supervisory delta options Table 1 (Black formula with λ shift; λ IR = max(−L+0.1%,0), else max(−1.1L,0)). CDO delta 15/((1+14A)(1+14D)).
- MF margined sqrt(1.5·MPOR/250); MPOR floors 10 bd (+ remargin periodicity − 1), 5 bd client-facing, 20 bd for >5,000 non-cleared trades/illiquid; doubled if >2 disputes. Unmargined sqrt(min(M,250)/250), M ≥ 10 bd.
- Binary option: 0.95K/1.05K decomposition.
- **Table 2 to §__.114** (vol % / corr % / SF %):
  - IR: 50 / – / 0.50
  - FX: 15 / – / 4.0
  - Credit single-name: IG 100/50/0.46; Spec 100/50/1.3; Sub-spec 100/50/6.0
  - Credit index: IG 80/80/0.38; Spec 80/80/1.06
  - Equity single 120/50/32; Equity index 75/80/20
  - Commodity: electricity 150/40/40; energy other 70/40/18; metals 70/40/18; agri 70/40/18; other 70/40/18
  - Basis hedging sets SF × 0.5; volatility hedging sets SF × 5.

## §__.115 Collateral haircut approach (p.726-)
- E* = max(0; (ΣE_i − ΣC_i) + 0.4·net_exposure + 0.6·gross_exposure/√N + Σ E_fx·H_fx). net = |Σ E_s H_s|; gross = Σ E_s|H_s|. N = # unique CUSIPs (excluding those < 1/10 of largest).
- Table 1 haircuts (%): sovereign RW0: ≤1y 0.5, 1-3y 2.0, 3-5y 2.0, 5-10y 4.0, >10y 4.0; sovereign RW20/50: 1.0/3.0/3.0/6.0/6.0; sovereign RW100: 15 all; GSE: 1.0/4.0/4.0/8.0/8.0; other IG non-GSE/non-sec: 2.0/4.0/6.0/12.0/20.0; senior sec RW<100%: 4.0/12.0/12.0/24.0/24.0; main index equities & gold 20; other equities/convertibles 30; funds: highest; cash 0; other 30 (incl. senior sec ≥100% RW, sovereign >100%).
- FX mismatch haircut 8%.
- Repo-style: may scale haircuts by sqrt(1/2). Holding-period scaling H_a = H_s·sqrt(T_m/T_s), T_s = 10 bd margin loans / 5 bd repo; >5,000 trades or illiquid → 20 bd; disputes → 2×. Non-financial collateral 30%.

## §__.116 Cleared (p.731-740)
- Client: QCCP 2% (bankruptcy-remote arrangement) / 4%; non-QCCP: CCP RW under §__.111. Clearing member: 2% QCCP; 0% if intermediary with no reimbursement obligation.
- Default fund non-QCCP: 1250%. QCCP: RWA = 12.5·K_CM; K_CM = max(K_CCP·DF_pref/(DF_CCP + DF_CM^pref); 0.16%·DF_pref); K_CCP = Σ EA_i × 1.6%; MPOR 10 bd.

## §__.117 Unsettled (p.740-743)
- DvP/PvP: 5-15 bd 100%, 16-30 625%, 31-45 937.5%, 46+ 1250%. Non-DvP: counterparty RW until 5 bd, then 1250%.

## §__.120 Guarantees/credit derivatives (p.743-749)
- Substitution approach. Maturity mismatch Pm = E·(t−0.25)/(T−0.25); mitigant original maturity ≥ 1y, residual > 3m. No-restructuring 0.60. FX mismatch H_FX 8% × sqrt(T_M/10).

## §__.121 Collateral simple approach / prepaid credit protection (p.749-757)
- Simple approach: collateral RW floor 20% (0% for cash on deposit; 0% sovereign RW0 collateral discounted 20%). Revalue every 6 months.
- Prepaid credit protection: 0% RW on protected portion.

## §__.130-134 Securitization (p.757-775)
- Due diligence failure → 1250%. Cannot apply SEC-SA → 1250%. IO MBS ≥ 100%. Look-through senior non-resec: max(weighted avg RW of underlying, 15%). NPL senior with NRPPD ≥ 50% → 100%.
- **SEC-SA §__.133**: RW = max(RW_floor, 1250%·K_SSFA) if K_A ≤ A; straddle = max(floor, (K_A−A)/(D−A)·1250% + (D−K_A)/(D−A)·1250%·K_SSFA) if A<K_A<D; 1250% if D ≤ K_A.
  - RW_floor = 100% for resecuritization and NPL securitizations; 15% otherwise.
  - K_SSFA = (e^{au} − e^{al})/(a(u−l)); a = −1/(p·K_A); **p = 0.5 non-resec, 1.5 resec**; u = D−K_A; l = max(A−K_A,0).
  - K_A = (1−W)·K_G + W·0.5. W = delinquent (90+ dpd, bankruptcy, foreclosure, REO, deferred 90+, default). K_G = weighted avg total capital requirement (100% RW → 0.08). No separate concentration add-on.
- Nth-to-default protection provider: sum RWs capped 1250%.

## §__.140-142 Equity (p.775-783)
- Equity commitments CF: conditional 40%, unconditional 100%.
- SRWA: 0% sovereign/MDB; 20% PSE/FHLB/Farmer Mac; 100% CD investments, effective hedge portion, non-significant equity up to 10% of total capital; 250% significant investments in unconsolidated FIs not deducted; **300% publicly traded; 400% non-publicly traded**; 600% investment firm with leverage.
- Funds: full look-through / simple modified (highest RW) / alternative modified; min RW 20%. Hedge pair E ≥ 0.8.

## §__.150 Operational risk (p.783-788)
- RWA_op = BIC × 12.5 (NO ILM term at all).
- BIC: BI ≤ $1B: 0.12·BI; $1B–$30B: $120M + 0.15·(BI−$1B); > $30B: $4.47B + 0.18·(BI−$30B). Thresholds indexed §__.4.
- BI = interest/lease/dividend component + noninterest component (two components, not three).
  - ILDC = min(Avg3y(|TII − TIE|), 0.0225·Avg3y(IEA)) + Avg3y(dividend income).
  - Noninterest component = Avg3y(|total noninterest income + realized G/L HTM + realized G/L AFS debt − noninterest expense for BI − 0.7·(fee income from investment management, investment services, and non-lending treasury services − related noninterest expense for BI)| + total operational losses).
  - 0.7 factor applies to investment management + investment services + non-lending treasury services (net basis).
  - Avg3y = average of three most recent 4-quarter periods; IEA avg = sum of 12 quarter-ends / 12.
- Loss data threshold $20,000; 10 years for acquired entities. 7 event types.

## §__.160-162 Disclosures (p.788-800): 13 qualitative tables (scope, capital structure, capital adequacy, CCyB, credit risk, CCR, CRM, securitization, equities, IRRBB, credit quality, op risk, capital instruments/TLAC). 12 quarters retained.

## §__.201 Market risk / CVA applicability (p.800-803)
- Market risk applies to: Category I/II holding companies; OR aggregate trading assets+liabilities (excl. customer/proprietary broker-dealer reserve accounts) ≥ 10% of quarter-end total assets OR ≥ **$5 billion** on average over four most recent quarters.
- CVA applies to: Cat I/II HCs; their DI subs subject to market risk; or market-risk BO with OTC derivative gross notional ≥ $1 trillion avg prior 4 quarters.
## §__.202 Definitions (p.804-826)
- Covered bond: resi ≤55% RW, CRE ≤100% RW & LTV ≤60%, overcollateralization ≥10%.
- CVA risk covered position: derivative not cleared / not client-facing; eligible credit derivative recognized as CRM may be excluded.
- Large market cap ≥ $2B; small < $2B. Liquid market economy: GDP/capita ≥ $10,000, market cap ≥ $95B, export diversification ≤50%, etc.
- Net short risk position ≥ $20 million.
- Model-ineligible positions: funds without quarterly look-through, securitization positions, CTP.
- Market risk covered position scope incl. FX & commodity positions regardless of trading status; excludes significant investments, CVA hedges, etc.

## §__.204 Measure for market risk (p.834-844)
- Standardized measure = standardized non-default (SBM + RRAO) + DRC + fallback capital requirement + capital add-ons for re-designations. SA computed at least weekly; IMA daily.
- Models-based measure = NDCR + DRC + fallback + re-designation add-ons.
  - NDCR = IMA_{G,A} + (SA_all desks − SA_{G,A}) (or with approval = SA_all desks).
  - IMA_{G,A} = max(IMCC_{t−1} + SES_{t−1}, m_c·IMCC_avg60 + SES_avg60) + PLA add-on. m_c = 1.5 base.
  - Table 1 §__.204 backtesting multiplier: 0–4 exceptions 1.50; 5: 1.70; 6: 1.76; 7: 1.83; 8: 1.88; 9: 1.92; ≥10: 2.00. Backtest VaR 99%, 1-day, 250 days, max(actual, hypothetical) exceptions.
- Fallback: sum |fair value| for positions that can't be calculated.
- Re-designation add-on = max(0, capital before − capital after); may decline with balance sheet value.
- Maximum loss cap allowed.
## §__.205 (p.844-853)
- Index single-sensitivity: 75% same sector → sector bucket; else equity index bucket 12 (large cap liquid ≥75%) or 13; credit index bucket 19 (IG ≥75%) or 20 of Table 3.
- Funds without look-through: tracked index / hypothetical portfolio / backstop (equity bucket 11 "other sector"; DRC as single sub-speculative equity).
- Term repo in market risk: DRC on EAD × 8%.

## §__.206 SBM formulas (p.853-862)
- 7 risk classes (GIRR, CSR non-sec, CSR CTP, CSR sec non-CTP, equity, commodity, FX). SBM = max over 3 correlation scenarios of Σ risk classes (delta+vega+curvature).
- Delta/vega K_b = sqrt(max(ΣWS² + ΣΣρWS WS, 0)); across: sqrt(ΣK_b² + ΣΣγ S_b S_c); if radicand negative use S_b = max(min(ΣWS, K_b), −K_b). ✓ (matches my fix)
- Curvature CVR± formulas; K_b = max(K_b+, K_b−); K_b± = sqrt(max(Σ max(CVR±,0)² + ΣΣ ρ CVR CVR ψ, 0)); ψ=0 if both negative. Across: sqrt(max(ΣK_b² + ΣΣγ S_b S_c ψ, 0)). Tie-break: if K+ = K−, choose up if ΣCVR+ > ΣCVR−.
- Correlation scenarios: medium = specified; high = ×1.25 capped 100%; low = max(2ρ−100%, 75%ρ).
## §__.207 Sensitivities (p.862-868): IR/CS delta per 1bp /0.0001; equity/commodity/FX 1% relative /0.01; vega = vega × volatility; sticky delta/strike.
## §__.208 Risk factors (p.868-875)
- **GIRR delta tenors: 0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30 (10 vertices)**; inflation & xccy basis (over USD or EUR) no term structure. Vega: option maturity {0.5,1,3,5,10} × underlying residual maturity {0.5,1,3,5,10}. Curvature: parallel shift; none for inflation/xccy.
- CSR non-sec / sec non-CTP / CTP delta tenors 0.5, 1, 3, 5, 10; vega maturity 0.5,1,3,5,10.
- Equity: spot + repo rate; vega 0.5,1,3,5,10; curvature spot only.
- Commodity: delivery location × maturity {0, 0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30}.
- FX: vs reporting currency; base-currency option with approval.
## §__.209 Buckets/RWs/correlations (p.875-)
- **Table 1 GIRR delta RW**: 0.25y 1.7%, 0.5y 1.7%, 1y 1.6%, 2y 1.3%, 3y 1.2%, 5y 1.1%, 10y 1.1%, 15y 1.1%, 20y 1.1%, 30y 1.1%. Inflation & xccy basis RW 1.6%. **USD, AUD, CAD, EUR, JPY, SEK, GBP (+ agency-specified): may divide RWs by √2.**
- GIRR correlations: same tenor different curves 99.9%; Table 2 tenor correlation matrix (0.25y row: 100, 97.0, 91.4, 81.1, 71.9, 56.6, 40, 40, 40, 40; 0.5y: 100, 97.0, 91.4, 86.1, 76.3, 56.6, 41.9, 40, 40; 1y: 100, 97.0, 94.2, 88.7, 76.3, 65.7, 56.6, 41.9; 2y: 100, 98.5, 95.6, 88.7, 82.3, 76.3, 65.7; 3y: 100, 98.0, 93.2, 88.7, 84.4, 76.3; 5y: 100, 97.0, 94.2, 91.4, 86.1; 10y: 100, 98.5, 97.0, 94.2; 15y: 100, 99.0, 97.0; 20y: 100, 98.5; 30y: 100) — i.e., max(e^{−0.03·|Tk−Tl|/min(Tk,Tl)}, 40%); different tenor & different curves ×99.9%; inflation curves 99.9%; inflation–IR 40%; xccy basis 0% vs everything. γ_bc = 50%.
- **Table 3 CSR non-sec delta (bucket: RW)**: IG: 1 sovereigns/MDB 0.5%; 2 PSE/gov-backed non-fin/GSE debt/education/public admin 1.0%; 3 financials incl gov-backed & real estate 5.0%; 4 basic materials/energy/industrials/agri/manufacturing/mining 3.0%; 5 consumer goods & services/transport/admin 3.0%; 6 tech & telecom 2.0%; 7 health care/utilities/professional 1.5%; 8 covered bonds 1.5%. Spec grade: 9 sovereigns/MDB 3.0%; 10 PSE/gov-backed non-fin/education/public admin 4.0%; 11 financials 12.0%; Spec+sub-spec: 12 basic materials etc 7.0%; 13 consumer goods etc 8.5%; (continued)
  14 tech & telecom 5.5%; 15 health care/utilities/professional 5.0%; 16 covered bonds 2.5%; Sub-spec: 17 sovereigns/MDB 7.0%; 18 other sector 12.0%; 19 IG indices 1.5%; 20 spec & sub-spec indices 5.0%.
  - CSR non-sec intra: ρ = ρ_name (100%/35%) × ρ_tenor (100%/65%) × ρ_basis (100%/99.9%); bucket 18: Σ|WS|; buckets 19-20: name 80%. γ = γ_rating (50% if different credit quality among 1-17, spec & sub-spec = one category) × γ_sector (Table 4).
  - **Table 4 CSR γ_sector** (rows: {1,9,17}, {2,10}, {3,11}, {4,12}, {5,13}, {6,14}, {7,15}, {8,16}, 18, 19, 20):
    {1,9,17}: 75% w/{2,10}, 10% {3,11}, 20% {4,12}, 25% {5,13}, 20% {6,14}, 15% {7,15}, 10% {8,16}, 0% 18, 45% 19, 45% 20
    {2,10}: 5% {3,11}, 15% {4,12}, 20% {5,13}, 15% {6,14}, 10% {7,15}, 10% {8,16}, 0% 18, 45%, 45%
    {3,11}: 5% {4,12}, 15% {5,13}, 20% {6,14}, 5% {7,15}, 20% {8,16}, 0%, 45%, 45%
    {4,12}: 20% {5,13}, 25% {6,14}, 5% {7,15}, 5% {8,16}, 0%, 45%, 45%
    {5,13}: 25% {6,14}, 5% {7,15}, 15% {8,16}, 0%, 45%, 45%
    {6,14}: 5% {7,15}, 20% {8,16}, 0%, 45%, 45%
    {7,15}: 5% {8,16}, 0%, 45%, 45%
    {8,16}: 0% 18, 45% 19, 45% 20
    18: 0% with 19, 0% with 20; 19–20: 75%.
- **Table 5 CSR CTP delta** (16 buckets): IG: 1 sov 4.0%; 2 PSE/GSE 4.0%; 3 financials 8.0%; 4 basic materials 5.0%; 5 consumer 4.0%; 6 tech/telecom 3.0%; 7 health/utilities 2.0%; Spec: 8 sov 13.0%; 9 PSE 13.0%; Spec+sub-spec: 10 financials 16.0%; 11 basic materials 10.0%; 12 consumer 12.0%; 13 tech 12.0%; 14 health 12.0%; Sub-spec: 15 sov 16.0%; 16 other 13.0%. Intra: name 35%, tenor 65%, basis 99%; bucket 16 Σ|WS|. γ: rating 50%, sector Table 6 (same pattern as Table 4 without index rows; 16 = 0%).
- **Table 7 CSR sec non-CTP delta** (25 buckets): Senior IG: 1 prime RMBS 0.90%; 2 mid-prime RMBS 1.50%; 3 sub-prime RMBS 2.00%; 4 CMBS 2.00%; 5 ABS student 0.80%; 6 ABS cards/personal 1.20%; 7 ABS auto/floorplan 1.20%; 8 CLO 1.40%. Non-senior IG: 9 1.13%; 10 1.88%; 11 2.50%; 12 2.50%; 13 1.00%; 14 1.50%; 15 1.50%; 16 1.75%. Spec+sub-spec: 17 1.58%; 18 2.63%; 19 3.50%; 20 3.50%; 21 1.40%; 22 2.10%; 23 2.10%; 24 2.45%; 25 other sector 3.50%.
  - Intra: ρ_tranche (100% same tranche >80% overlap, else 40%) × ρ_tenor (100%/80%) × ρ_basis (100%/99.9%); bucket 25 Σ|WS|. **γ = 0%** across buckets.
- **Table 8 Equity delta** (bucket: spot RW / repo RW): Large cap EM: 1 consumer/transport/admin/health/utilities 55%/0.55%; 2 telecom & industrials 60%/0.60%; 3 basic materials/energy/agri/manuf/mining 45%/0.45%; 4 financials/real estate/technology 55%/0.55%. Large cap liquid: 5 30%/0.30%; 6 35%/0.35%; 7 40%/0.40%; 8 50%/0.50%. Small cap EM 9: 70%/0.70%; small cap liquid 10: 50%/0.50%; 11 other sector 70%/0.70%; 12 large-cap liquid indices 15%/0.15%; 13 other indices 25%/0.25%.
  - Intra ρ: spot–repo same issuer 99.9%; buckets 1-4: 15%; 5-8: 25%; 9: 7.5%; 10: 12.5%; 12-13: 80%; spot vs repo different issuer ×99.9%; bucket 11 Σ|WS|. γ: 15% within 1-10; 0% with 11; 75% between 12 and 13; 45% otherwise.
- **Table 9 Commodity delta** (12 buckets): 1 energy solid combustibles 30%; 2 energy liquid combustibles 35%; 3 energy carbon trading 60%; 4 freight 80%; 5 metals non-precious 40%; 6 gaseous combustibles & electricity 45%; 7 precious metals 20%; 8 grains & oilseed 35%; 9 livestock & dairy 25%; 10 forestry & agriculturals 35%; 11 other commodity 50%; 12 commodity index 30%.
  - Table 10 intra ρ_cty: 55, 95, 40, 80, 60, 65, 55, 45, 15, 40, 15, 50 (%); ρ_tenor 99%; ρ_basis (location) 99.9%. γ: 20% among 1-10 & 12; 0% with 11.
- FX delta RW 15%; ÷√2 for pairs among USD, AUD, BRL, CAD, CNY, EUR, HKD, INR, JPY, MXN, NZD, NOK, SGD, ZAR, KRW, SEK, CHF, TRY, GBP. γ 60%.
- **Table 11 Vega RW**: GIRR 100%; CSR non-sec 100%; CSR CTP 100%; CSR sec 100%; equity large cap & indices 77.78%; equity small cap & other 100%; commodity 100%; FX 100%.
  - Vega intra ρ: GIRR min(ρ_option maturity × ρ_underlying maturity, 1) with e^{−α|Tk−Tl|/min(Tk,Tl)}, α = 1%; other classes min(ρ_delta × ρ_option maturity, 1). Other-sector buckets Σ|WS|. Vega γ = delta γ.
- Curvature RW: FX & equity = delta RW (FX CVR may be ÷1.5 for options not referencing reporting currency); GIRR/CSR/commodity: highest delta RW in bucket as parallel shift. Curvature ρ: GIRR 99.8% different curves (100% same); others = delta ρ squared; γ = delta γ squared. Other-sector buckets K_b = max(Σmax(CVR+,0), Σmax(CVR−,0)).

## §__.210 DRC (p.901-913)
- Categories: non-sec debt/equity (excl. US sovereign/MDB/supranational), sec non-CTP, CTP. No diversification across categories.
- Maturity scaling: <1y scaled by fraction of year, floor 3 months; ≥1y no scaling. Unhedged cash equity: 3 months or 1 year (bank's choice); cash equity hedging derivative may take derivative maturity.
- **HBR = Σnet long / (Σnet long + Σ|net short|)** ✓.
- Gross DE long = max(LGD × notional + P&L, 0); short = min(LGD × notional + P&L, 0).
- **LGD**: 100% equity, non-senior debt, defaulted; 75% senior debt; 75% GSE debt issued-not-guaranteed; 50% US PSE positions; 25% GSE-guaranteed debt; 25% covered bonds; 0% if not linked to recovery. Credit derivatives use reference exposure LGD.
- Net DE: offset same obligor if short seniority ≤ long. GSEs separate obligors but UMBS may offset.
- **Four buckets: non-US sovereign; PSE & GSE debt; corporate; defaulted.** DRC_b = max(Σ_long RW·NDE − HBR·Σ_short RW·|NDE|, 0).
- **Table 1 §__.210 DRC RW**: Non-US sovereign: IG 0.6%, Spec 22.0%, Sub-spec 50.0%; PSE & GSE: IG 2.1%, Spec 22.0%, Sub-spec 50.0%; Corporate: IG 4.1%, Spec 22.0%, Sub-spec 50.0%; Defaulted 100%. (US uses credit quality categories, NOT external ratings.)
- Sec non-CTP: gross DE = market value; offset same pool & same tranche; buckets = corporate + (asset class {ABCP, auto, RMBS, cards, CMBS, CLO, CDO², SME, student, other retail, other wholesale} × region {Asia, Europe, North America, other}); **RW = SEC-SA/§132 RW × 8%**; cap at fair value for cash positions; same HBR formula.
- CTP: nth-to-default A=(N−1)/total names, D=N/total names; each index own bucket; HBR_CTP across all indices; RW tranched = SEC RW × 8%; **DRC_CTP = max(Σ_b [max(DRC_b,0) + 0.5·min(DRC_b,0)], 0)**.
## §__.211 RRAO (p.913-915): exotic 1.0%; other residual (CTP ≥3 underlyings, non-replicable curvature/vega payoffs, no maturity, no/multiple strikes/barriers) 0.1%; exclusions listed; notional per Call Report/FR Y-9C.
## §__.212-215 IMA (p.915-943)
- Desk approval: 250 bd backtesting (or 125 bd w/ demonstration); PLA applies 3 years after effective date.
- Desk backtesting: 97.5% & 99% VaR; ineligible if >12 exceptions at 99% or >30 at 97.5% (actual or hypothetical) over 250 bd.
- PLA: KS metric only (no Spearman); green KS < 0.09; amber 0.09 ≤ KS ≤ 0.12; red > 0.12. PLA add-on = k × max(SA_{G,A} − IMA_{G,A}, 0), k = 0.5 × ΣSA_amber / ΣSA_{G,A}.
- NMRF: 24 real prices if LH 10 or 20 days, 16 otherwise; standard bucketing Table 1 §__.214.
- ES 97.5%, base LH 10 days, LH ladder 10/20/40/60/120; ES = sqrt(ES_T(P)² + Σ_j (ES_T(P,j)·sqrt((LH_j − LH_{j−1})/T))²). Stress period 12 months back to 2007; reduced set must explain ≥75%; indirect ES = ES_{R,S}·max(1, ES_{F,C}/ES_{R,C}).
- Table 2 §__.215 LH: IR specified currencies (USD, AUD, CAD, EUR, JPY, SEK, GBP, domestic) & inflation 10; IR other currencies 20; IR vol 60; IR other 60; CS sovereign IG 20; CS sovereign spec/sub-spec 40; CS GSE debt 40; CS corporate IG 40; CS corporate spec/sub-spec 60; CS vol 120; CS other 120; equity large cap/index 10; equity small cap 20; equity large cap vol 20; equity small cap vol 60; equity other 60; FX specified pairs 10; FX other pairs 20; FX vol 40; FX other 40; energy & carbon 20; precious & non-ferrous metals 20; other commodities 60; energy vol 60; metals vol 60; other commodity vol 120; commodity other 120.
- IMCC = ω·IMCC(C) + (1−ω)·ΣIMCC(C_i), ω = 0.5; 5 risk classes.
- SES = sqrt(Σ_k SES_{NM,k}² + [(1−ρ_b)ΣSES_{NM,j}² + ρ_b(ΣSES_{NM,j})²]), ρ_b = 0.36 (type A squared sum; type B correlated). NMRF LH ≥ max(assigned, 20 days).

## §__.220-225 CVA (p.950-988)
- Basic measure default; standardized measure requires approval (SA-CVA + BA-CVA for carve-outs).
- **BA-CVA §__.222**: K_basic = 0.65·(β·K_unhedged + (1−β)·K_hedged), β = 0.25. K_unhedged = sqrt((ρΣSCVA_c)² + (1−ρ²)ΣSCVA_c²), ρ = 50%. SCVA_c = (1/α)·RW_c·Σ_NS(M_NS·EAD_NS·DF_NS); α = 1 for commercial end-user counterparties (§__.114(e)(4)), 1.4 otherwise; DF = (1−e^{−0.05M})/(0.05M); M = notional-weighted avg remaining maturity.
  - **Table 1 §__.222 RW_c** (IG / Spec / Sub-spec): sovereigns-MDB 0.5% / 3.0% / 7.0%; PSE-gov-backed non-fin-GSE-education-public admin 1.0% / 4.0%; financials incl gov-backed 5.0% / 12.0%; basic materials-energy-industrials-agri-manuf-mining 3.0% / 7.0%; consumer-transport-admin 3.0% / 8.5%; tech-telecom 2.0% / 5.5%; health-utilities-professional 1.5% / 5.0%; other 5.0% / 12.0%. (spec & sub-spec share one column except sovereigns.)
  - K_hedged = sqrt((ρΣ(SCVA_c − SNH_c) − IH)² + (1−ρ²)Σ(SCVA_c − SNH_c)² + ΣHMA_c). SNH_c = Σ_h r_hc·RW_h·M_h·B_h·DF_h; r_hc: direct 100%, affiliate 80%, same sector & region 50%. IH = Σ RW_i·M_i·B_i·DF_i with index RW = Table 1 × 0.7 (notional-weighted for mixed). HMA_c = Σ(1−r_hc²)(RW_h M_h B_h DF_h)².
- **SA-CVA §__.224**: delta 6 risk classes (IR, FX, counterparty CS, reference CS, equity, commodity); vega 5 (no counterparty CS). K_b = sqrt(ΣWS² + ΣΣρ WS WS + R·Σ(WS^Hdg)²), R = 0.01. K = m_CVA·sqrt(ΣK_b² + ΣΣγ S_b S_c), S_b = max(min(ΣWS, K_b), −K_b) (always capped); **m_CVA = 1** (agency may increase). MPoR ≥ 9 + N bd.
  - IR specified currencies (USD, AUD, CAD, EUR, JPY, SEK, GBP): tenors 1, 2, 5, 10, 30 + inflation; RW 1.11%, 0.93%, 0.74%, 0.74%, 0.74%, inflation 1.11%; ρ matrix (1y row: 100, 91, 72, 55, 31, infl 40; 2y: 100, 87, 72, 45, 40; 5y: 100, 91, 68, 40; 10y: 100, 83, 40; 30y: 100, 40). Other currencies: parallel shift + inflation RW 1.58%, ρ 40%. γ 50%.
  - FX RW 11%; γ 60%.
  - Counterparty CS Table 3: bucket 1 (a) sov 0.5/3.0/7.0, (b) PSE etc 1.0/4.0, (c) gov-backed financials 5.0/12.0; 2 financials 5.0/12.0; 3 basic materials 3.0/7.0; 4 consumer 3.0/8.5; 5 tech 2.0/5.5; 6 health 1.5/5.0; 7 other 5.0/12.0; 8 indices 1.5/5.0. Tenors 0.5,1,3,5,10. ρ = tenor (100/90) × name (100 same / 90 affiliate / 50) × quality (100/80); bucket 8: name 100 same series / 90 same index diff series / 80. γ Table 4: 1-2 10%, 1-3 20%, 1-4 25%, 1-5 20%, 1-6 15%, 1-7 0%, 1-8 70%; 2-3 5%, 2-4 15%, 2-5 20%, 2-6 5%, 2-7 0, 2-8 70; 3-4 20, 3-5 25, 3-6 5, 3-7 0, 3-8 70; 4-5 25, 4-6 5, 4-7 0, 4-8 70; 5-6 5, 5-7 0, 5-8 70; 6-7 0, 6-8 70; 7-8 0.
  - Reference CS Table 5 (17 buckets): IG 1 sov 0.5; 2 PSE 1.0; 3 financials 5.0; 4 basic 3.0; 5 consumer 3.0; 6 tech 2.0; 7 health 1.5; 8 sov spec 3.0 / sub-spec 7.0; 9 PSE 4.0; 10 financials 12.0; 11 basic 7.0; 12 consumer 8.5; 13 tech 5.5; 14 health 5.0; 15 other 12.0; 16 IG indices 1.5; 17 spec indices 5.0. γ same quality Table 6 (= SBM Table 4 pattern incl 45% to indices, 75% between 16-17); different quality Table 7 = half (50/37.5/5/10/12.5/10/7.5; ...).
  - Equity Table 8 = SBM Table 8 spot RWs (55/60/45/55/30/35/40/50/70/50/70/15/25); γ 15% (1-10), 0% w/ 11, 75% 12-13, 45% index vs 1-10.
  - Commodity Table 9 = SBM Table 9 (30/35/60/80/40/45/20/35/25/35/50/30); γ 20% / 0% w/ 11.
  - Vega: IR RW 100%, ρ 40%, γ 50%; FX 100%, γ 60%; ref CS 100%; equity 78% large cap / 100% otherwise; commodity 100%.
