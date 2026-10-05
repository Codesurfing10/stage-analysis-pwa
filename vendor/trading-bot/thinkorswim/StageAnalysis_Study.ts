# StageAnalysis_Study
# Weinstein-style Stage Analysis for Thinkorswim charts
# Matches New Bot equity-scan rules:
#   Stage 2 = close > SMA150 AND SMA150 slope > 0
#   Stage 4 = close < SMA150 AND SMA150 slope < 0
#   Volume confirm = Stage 2 AND volume > 1.3 * SMA(volume, 50)
#   Extended = (close - SMA50) / SMA50
#
# Install: Studies → Edit Studies → Create → paste → Apply
# Timeframe: Daily recommended

declare upper;

input sma150Length = 150;
input sma50Length = 50;
input slopeLookback = 5;          # bars used to measure SMA150 slope
input volAvgLength = 50;
input volConfirmMult = 1.3;
input showBubbles = yes;
input paintBars = yes;

def sma150 = Average(close, sma150Length);
def sma50 = Average(close, sma50Length);
def volAvg = Average(volume, volAvgLength);

# Positive slope ≈ rising 30-week / 150-day MA
def slope = sma150 - sma150[slopeLookback];
def rising = slope > 0;
def falling = slope < 0;

def stage2 = close > sma150 and rising;
def stage4 = close < sma150 and falling;
def stage1or3 = !stage2 and !stage4;

def volConfirmed = stage2 and volume > volAvg * volConfirmMult;
def extendedPct = if sma50 != 0 then (close - sma50) / sma50 else 0;

plot SMA150 = sma150;
SMA150.SetDefaultColor(Color.CYAN);
SMA150.SetLineWeight(2);

plot SMA50 = sma50;
SMA50.SetDefaultColor(Color.YELLOW);
SMA50.SetStyle(Curve.SHORT_DASH);

# Stage entry / exit markers
plot Stage2Entry = if stage2 and !stage2[1] then low * 0.99 else Double.NaN;
Stage2Entry.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
Stage2Entry.SetDefaultColor(Color.GREEN);
Stage2Entry.SetLineWeight(3);

plot Stage2Exit = if !stage2 and stage2[1] then high * 1.01 else Double.NaN;
Stage2Exit.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
Stage2Exit.SetDefaultColor(Color.RED);
Stage2Exit.SetLineWeight(3);

plot VolConfirmDot = if volConfirmed then low * 0.985 else Double.NaN;
VolConfirmDot.SetPaintingStrategy(PaintingStrategy.POINTS);
VolConfirmDot.SetDefaultColor(Color.LIME);
VolConfirmDot.SetLineWeight(3);

AssignPriceColor(
    if !paintBars then Color.CURRENT
    else if volConfirmed then Color.GREEN
    else if stage2 then Color.DARK_GREEN
    else if stage4 then Color.RED
    else Color.GRAY
);

AddLabel(yes,
    if volConfirmed then "STAGE 2 + VOL ✓"
    else if stage2 then "STAGE 2"
    else if stage4 then "STAGE 4 — AVOID"
    else "STAGE 1/3",
    if volConfirmed then Color.GREEN
    else if stage2 then Color.DARK_GREEN
    else if stage4 then Color.RED
    else Color.GRAY
);

AddLabel(yes,
    "SMA150 slope " + (if rising then "UP" else if falling then "DOWN" else "FLAT"),
    if rising then Color.GREEN else if falling then Color.RED else Color.GRAY
);

AddLabel(yes,
    "Vol/Avg " + Round(volume / volAvg, 2) + "x",
    if volume > volAvg * volConfirmMult then Color.GREEN else Color.GRAY
);

AddLabel(yes,
    "Ext vs SMA50 " + Round(extendedPct * 100, 1) + "%",
    if extendedPct > 0.15 then Color.ORANGE
    else if AbsValue(extendedPct) < 0.05 then Color.CYAN
    else Color.GRAY
);

# Optional cloud when Stage 2
AddCloud(
    if stage2 then sma150 else Double.NaN,
    if stage2 then sma50 else Double.NaN,
    Color.DARK_GREEN, Color.DARK_GREEN
);
