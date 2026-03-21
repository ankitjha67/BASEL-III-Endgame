"""
FRTB Phase 1B: Trading Position Generation And Full Calculation
Generates ~10,000 realistic trading positions across 7 risk classes,
computes sensitivities, runs through the SBM+DRC+RRAO engine.
"""

from frtb_phase1a import *
import warnings
warnings.filterwarnings('ignore')

np.random.seed(20260321)

print("╔═══════════════════════════════════════════════════════════════╗")
print("║  FRTB Phase 1B: Full Market Risk Calculation From Positions  ║")
print("╚═══════════════════════════════════════════════════════════════╝\n")

frtb = FrtbCalculator()

# ═══════════════════════════════════════════════════════════════════
# STEP 1: GENERATE GIRR POSITIONS AND SENSITIVITIES
# ~3,500 positions across 10 currencies × 10 tenors
# ═══════════════════════════════════════════════════════════════════

print("Step 1: Generating GIRR Sensitivities (Rates Trading)")
print("─" * 55)

CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "SEK", "NOK", "NZD"]
GIRR_INSTRUMENTS = ["Government Bond", "Interest Rate Swap", "Swaption", "Cap/Floor",
                     "Cross-Currency Swap", "FRA", "Bond Future", "Treasury Future"]

girrCount = 0
for ccy_idx, ccy in enumerate(CURRENCIES):
    # Number of positions per currency (USD heaviest)
    nPos = 500 if ccy == "USD" else (200 if ccy in ["EUR","GBP","JPY"] else 80)
    
    for i in range(nPos):
        tenor = np.random.choice(list(GIRR_TENORS.keys()))
        tenorYears = GIRR_TENORS[tenor]
        rw = GIRR_DELTA_RW[tenor]
        instrument = np.random.choice(GIRR_INSTRUMENTS)
        
        # DV01 (dollar value of 1bp shift) — realistic for a GSIB
        # Short-tenor positions have smaller DV01 per notional
        notional = np.random.lognormal(np.log(500), 1.5)
        dv01 = notional * tenorYears * 0.0001 * np.random.uniform(0.7, 1.3)
        direction = np.random.choice([-1, 1])
        sensitivity = direction * dv01
        
        frtb.addDeltaSensitivity(RiskFactorSensitivity(
            positionId=f"GIRR-{ccy}-{i:04d}",
            riskClass="GIRR",
            riskFactor=f"{ccy}_{tenor}",
            bucket=ccy_idx + 1,  # Each currency = one bucket
            tenor=tenor,
            sensitivity=sensitivity,
            riskWeight=rw,
        ))
        
        # Vega for options
        if instrument in ["Swaption", "Cap/Floor"]:
            vegaRw = VEGA_BASE_RW["GIRR"]
            vegaSens = abs(dv01) * np.random.uniform(0.5, 2.0) * np.random.choice([-1, 1])
            frtb.addVegaSensitivity(RiskFactorSensitivity(
                positionId=f"GIRR-V-{ccy}-{i:04d}",
                riskClass="GIRR", riskFactor=f"{ccy}_{tenor}_vol",
                bucket=ccy_idx + 1, tenor=tenor,
                sensitivity=vegaSens, riskWeight=vegaRw,
            ))
            
            # Curvature for options
            shift = rw * notional * 0.01
            pnlUp = sensitivity * shift * np.random.uniform(0.8, 1.2)
            pnlDown = -sensitivity * shift * np.random.uniform(0.8, 1.2)
            frtb.addCurvaturePosition(CurvaturePosition(
                positionId=f"GIRR-C-{ccy}-{i:04d}",
                riskClass="GIRR", bucket=ccy_idx + 1,
                riskFactor=f"{ccy}_{tenor}", fairValue=notional * 0.01,
                fairValueUp=notional * 0.01 + pnlUp,
                fairValueDown=notional * 0.01 + pnlDown,
                delta=sensitivity, shiftSize=shift,
            ))
        
        girrCount += 1

print(f"  {girrCount:,} GIRR Delta Sensitivities Across {len(CURRENCIES)} Currencies")
print(f"  {len(frtb.vegaSensitivities.get('GIRR', []))} GIRR Vega Sensitivities")
print(f"  {len(frtb.curvaturePositions.get('GIRR', []))} GIRR Curvature Positions")

# ═══════════════════════════════════════════════════════════════════
# STEP 2: GENERATE CSR NON-SECURITIZATION SENSITIVITIES
# ~2,000 positions (corporate bonds, CDS, index CDS)
# ═══════════════════════════════════════════════════════════════════

print("\nStep 2: Generating CSR Non-Sec Sensitivities (Credit Trading)")
print("─" * 55)

csrNonSecCount = 0
ISSUERS = [f"ISSUER-{i:04d}" for i in range(500)]

for bucket_id, bucket_def in CSR_NONSEC_BUCKETS.items():
    nPos = 200 if bucket_id in [4,5,6,7,8,9,16,17] else 50  # More in financials/corporates
    
    for i in range(nPos):
        issuer = np.random.choice(ISSUERS)
        tenor = np.random.choice(list(CSR_NONSEC_TENORS.keys()))
        rw = bucket_def["RW"]
        
        # CS01 (credit spread 01) — dollar change per 1bp spread move
        notional = np.random.lognormal(np.log(200), 1.3)
        cs01 = notional * 0.0001 * float(tenor.replace("Y", "")) * np.random.uniform(0.5, 1.5)
        direction = np.random.choice([-1, 1])
        
        frtb.addDeltaSensitivity(RiskFactorSensitivity(
            positionId=f"CSR-{bucket_id}-{i:04d}",
            riskClass="CSR_NonSec",
            riskFactor=f"{issuer}_{tenor}",
            bucket=bucket_id,
            tenor=tenor,
            sensitivity=direction * cs01,
            riskWeight=rw,
        ))
        csrNonSecCount += 1
        
        # DRC position
        quality = bucket_def["Quality"]
        if quality == "IG":
            creditRating = np.random.choice(["AA", "A", "A-", "BBB+", "BBB", "BBB-"])
        elif quality == "HY":
            creditRating = np.random.choice(["BB+", "BB", "BB-", "B+", "B"])
        else:
            creditRating = "NR"
        
        seniority = np.random.choice(["Senior Unsecured", "Subordinated", "Equity"],
                                      p=[0.65, 0.25, 0.10])
        
        frtb.addDrcPosition(DrcPosition(
            positionId=f"DRC-{bucket_id}-{i:04d}",
            issuerId=issuer, issuerSector=bucket_def["Name"],
            creditQuality=creditRating, seniority=seniority,
            notional=notional, fairValue=notional * np.random.uniform(-0.1, 0.1),
            isLong=(direction > 0), maturity=float(tenor.replace("Y", "")),
        ))

print(f"  {csrNonSecCount:,} CSR Non-Sec Sensitivities Across {len(CSR_NONSEC_BUCKETS)} Buckets")
print(f"  {len(frtb.drcPositions):,} DRC Positions")

# ═══════════════════════════════════════════════════════════════════
# STEP 3: GENERATE EQUITY SENSITIVITIES
# ~2,000 positions
# ═══════════════════════════════════════════════════════════════════

print("\nStep 3: Generating Equity Sensitivities")
print("─" * 55)

eqCount = 0
for bucket_id, bucket_def in EQUITY_BUCKETS.items():
    nPos = 250 if bucket_id in [6,7,8,9,10,12] else 80  # More in AE large cap
    
    for i in range(nPos):
        rw = bucket_def["RW"]
        notional = np.random.lognormal(np.log(50), 1.0)
        eqDelta = notional * rw * np.random.uniform(-1, 1)
        
        frtb.addDeltaSensitivity(RiskFactorSensitivity(
            positionId=f"EQ-{bucket_id}-{i:04d}",
            riskClass="Equity", riskFactor=f"EQ_{bucket_id}_{i:04d}",
            bucket=bucket_id, tenor="Spot",
            sensitivity=eqDelta, riskWeight=rw,
        ))
        
        # Vega for equity options (~40% of positions)
        if np.random.random() < 0.40:
            vegaSens = abs(eqDelta) * np.random.uniform(0.3, 0.8)
            frtb.addVegaSensitivity(RiskFactorSensitivity(
                positionId=f"EQ-V-{bucket_id}-{i:04d}",
                riskClass="Equity", riskFactor=f"EQ_{bucket_id}_{i:04d}_vol",
                bucket=bucket_id, tenor="Spot",
                sensitivity=vegaSens, riskWeight=VEGA_BASE_RW["Equity"],
            ))
        
        eqCount += 1

print(f"  {eqCount:,} Equity Delta Sensitivities Across {len(EQUITY_BUCKETS)} Buckets")

# ═══════════════════════════════════════════════════════════════════
# STEP 4: GENERATE COMMODITY SENSITIVITIES
# ~800 positions
# ═══════════════════════════════════════════════════════════════════

print("\nStep 4: Generating Commodity Sensitivities")
print("─" * 55)

comCount = 0
for bucket_id, bucket_def in COMMODITY_BUCKETS.items():
    nPos = 120 if bucket_id in [1,2,3,6,7] else 40  # More in energy/metals
    
    for i in range(nPos):
        rw = bucket_def["RW"]
        notional = np.random.lognormal(np.log(100), 1.2)
        comDelta = notional * rw * np.random.uniform(-1, 1)
        
        frtb.addDeltaSensitivity(RiskFactorSensitivity(
            positionId=f"COM-{bucket_id}-{i:04d}",
            riskClass="Commodity", riskFactor=f"COM_{bucket_id}_{i:04d}",
            bucket=bucket_id, tenor="Spot",
            sensitivity=comDelta, riskWeight=rw,
        ))
        comCount += 1

print(f"  {comCount:,} Commodity Sensitivities Across {len(COMMODITY_BUCKETS)} Buckets")

# ═══════════════════════════════════════════════════════════════════
# STEP 5: GENERATE FX SENSITIVITIES
# ~1,200 positions across major currency pairs
# ═══════════════════════════════════════════════════════════════════

print("\nStep 5: Generating FX Sensitivities")
print("─" * 55)

FX_PAIRS = ["USD/EUR","USD/JPY","USD/GBP","USD/CAD","USD/CHF","USD/AUD",
             "EUR/GBP","EUR/JPY","EUR/CHF","GBP/JPY","USD/MXN","USD/BRL",
             "USD/CNY","USD/INR","USD/KRW"]

fxCount = 0
for pair_idx, pair in enumerate(FX_PAIRS):
    nPos = 150 if pair in FX_SPECIFIED_PAIRS else 50
    
    for i in range(nPos):
        notional = np.random.lognormal(np.log(500), 1.3)
        fxDelta = notional * FX_DELTA_RW * np.random.uniform(-1, 1)
        
        frtb.addDeltaSensitivity(RiskFactorSensitivity(
            positionId=f"FX-{pair_idx}-{i:04d}",
            riskClass="FX", riskFactor=pair,
            bucket=pair_idx + 1,
            tenor="Spot",
            sensitivity=fxDelta, riskWeight=FX_DELTA_RW,
        ))
        
        # Vega for FX options (~30%)
        if np.random.random() < 0.30:
            frtb.addVegaSensitivity(RiskFactorSensitivity(
                positionId=f"FX-V-{pair_idx}-{i:04d}",
                riskClass="FX", riskFactor=f"{pair}_vol",
                bucket=pair_idx + 1, tenor="Spot",
                sensitivity=abs(fxDelta) * np.random.uniform(0.2, 0.6),
                riskWeight=VEGA_BASE_RW["FX"],
            ))
        fxCount += 1

print(f"  {fxCount:,} FX Sensitivities Across {len(FX_PAIRS)} Currency Pairs")

# ═══════════════════════════════════════════════════════════════════
# STEP 6: GENERATE RRAO POSITIONS
# ═══════════════════════════════════════════════════════════════════

print("\nStep 6: Generating RRAO Positions")
print("─" * 55)

# All trading positions contribute to RRAO
for rc, sens_list in frtb.deltaSensitivities.items():
    for s in sens_list:
        isExotic = np.random.random() < 0.03  # 3% exotic
        isExempt = np.random.random() < 0.15  # 15% exempt (listed options, etc.)
        
        frtb.addRraoPosition(RraoPosition(
            positionId=s.positionId,
            notional=abs(s.sensitivity / max(s.riskWeight, 0.001)),
            instrumentType="exotic" if isExotic else "standard",
            underlyingType="correlation" if isExotic else "standard",
            isExotic=isExotic,
            isExempt=isExempt,
        ))

print(f"  {len(frtb.rraoPositions):,} RRAO Positions ({sum(1 for p in frtb.rraoPositions if p.isExotic)} Exotic)")

# ═══════════════════════════════════════════════════════════════════
# STEP 7: RUN THE FULL FRTB CALCULATION
# ═══════════════════════════════════════════════════════════════════

print("\n" + "═" * 60)
print("RUNNING FULL FRTB CALCULATION")
print("═" * 60)

totalPositions = (sum(len(v) for v in frtb.deltaSensitivities.values()) +
                  sum(len(v) for v in frtb.vegaSensitivities.values()) +
                  sum(len(v) for v in frtb.curvaturePositions.values()))
print(f"\n  Total Positions: {totalPositions:,}")
print(f"  Delta Sensitivities: {sum(len(v) for v in frtb.deltaSensitivities.values()):,}")
print(f"  Vega Sensitivities: {sum(len(v) for v in frtb.vegaSensitivities.values()):,}")
print(f"  Curvature Positions: {sum(len(v) for v in frtb.curvaturePositions.values()):,}")
print(f"  DRC Positions: {len(frtb.drcPositions):,}")
print(f"  RRAO Positions: {len(frtb.rraoPositions):,}")

results = frtb.calculate()
print(frtb.summary())

# ═══════════════════════════════════════════════════════════════════
# STEP 8: DETAILED BREAKDOWN
# ═══════════════════════════════════════════════════════════════════

print("\nDETAILED BREAKDOWN BY RISK CLASS:")
print("─" * 55)

print(f"\n  {'Risk Class':25s} {'Delta':>12s} {'Vega':>12s} {'Curvature':>12s} {'Total':>12s}")
print(f"  {'─'*73}")

allRiskClasses = set(list(results["Delta"].keys()) + list(results["Vega"].keys()) + list(results["Curvature"].keys()))
for rc in sorted(allRiskClasses):
    d = results["Delta"].get(rc, {}).get("Medium", 0)
    v = results["Vega"].get(rc, {}).get("Medium", 0)
    c = results["Curvature"].get(rc, {}).get("Medium", 0)
    t = d + v + c
    print(f"  {rc:25s} ${d:>10,.0f}M ${v:>10,.0f}M ${c:>10,.0f}M ${t:>10,.0f}M")

sbm = results["SBM"]["Capital"]
drc = results["DRC"]
rrao = results["RRAO"]
total = results["TotalMrCapital"]
rwa = results["TotalMrRwa"]

print(f"\n  {'SBM Capital':25s}                                      ${sbm:>10,.0f}M")
print(f"  {'DRC Capital':25s}                                      ${drc:>10,.0f}M")
print(f"  {'RRAO':25s}                                      ${rrao:>10,.0f}M")
print(f"  {'─'*73}")
print(f"  {'TOTAL MR CAPITAL':25s}                                      ${total:>10,.0f}M")
print(f"  {'TOTAL MR RWA (×12.5)':25s}                                      ${rwa:>10,.0f}M")

# Line count
print(f"\n  Phase 1A (Parameters): 829 lines")
print(f"  Phase 1B (Positions + Calculation): ~400 lines")
print(f"  Total FRTB Module So Far: ~1,229 lines")
print(f"  Remaining To Build: ~6,771 lines (IMA, P&L attribution, backtesting, desk infrastructure)")
