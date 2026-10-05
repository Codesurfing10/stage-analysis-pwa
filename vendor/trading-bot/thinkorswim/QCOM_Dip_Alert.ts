# QCOM_Dip_Alert
# Marks a 3–5% pullback from a reference high / prior close zone
# while still Stage 2. Attach to QCOM (or any symbol) on Daily.
#
# Set refClose to the pre-dip reference (for QCOM scenario: 201.97)
# or leave useAutoRef = yes to use highest close of last refLookback bars.

declare upper;

input useAutoRef = yes;
input refClose = 201.97;          # manual override when useAutoRef = no
input refLookback = 20;
input dipLowPct = 0.03;           # -3%
input dipHighPct = 0.05;          # -5%
input sma150Length = 150;
input slopeLookback = 5;

def sma150 = Average(close, sma150Length);
def slope = sma150 - sma150[slopeLookback];
def stage2 = close > sma150 and slope > 0;

def autoRef = Highest(close, refLookback);
def ref = if useAutoRef then autoRef else refClose;

def dip3 = ref * (1 - dipLowPct);
def dip5 = ref * (1 - dipHighPct);

# In the buy zone: between -5% and -3% of ref, still Stage 2
def inZone = stage2 and close <= dip3 and close >= dip5;

plot RefLevel = ref;
RefLevel.SetDefaultColor(Color.WHITE);
RefLevel.SetStyle(Curve.SHORT_DASH);

plot Dip3 = dip3;
Dip3.SetDefaultColor(Color.YELLOW);

plot Dip5 = dip5;
Dip5.SetDefaultColor(Color.ORANGE);

plot BuyZone = if inZone then low * 0.99 else Double.NaN;
BuyZone.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
BuyZone.SetDefaultColor(Color.CYAN);
BuyZone.SetLineWeight(3);

AddLabel(yes,
    if inZone then "DIP ZONE 3–5% — Stage 2"
    else if stage2 then "Stage 2 — waiting for dip"
    else "Not Stage 2",
    if inZone then Color.CYAN else if stage2 then Color.GREEN else Color.GRAY
);

AddLabel(yes, "Ref " + Round(ref, 2), Color.WHITE);
AddLabel(yes, "-3% " + Round(dip3, 2) + " / -5% " + Round(dip5, 2), Color.YELLOW);

# Alert when entering zone (Studies → Alerts on study)
Alert(inZone and !inZone[1], "Stage2 dip zone entered", Alert.BAR, Sound.Ring);
