# Stage2_Watchlist
# Custom Quote / Watchlist column
# Shows: 2V (Stage 2 + vol), 2 (Stage 2), 4 (Stage 4), or - (other)
#
# Install: Watchlist gear → Customize → Custom Quotes →
#   thinkScript Editor → paste → name it Stage2 → add column

input sma150Length = 150;
input slopeLookback = 5;
input volAvgLength = 50;
input volConfirmMult = 1.3;

def sma150 = Average(close, sma150Length);
def slope = sma150 - sma150[slopeLookback];
def stage2 = close > sma150 and slope > 0;
def stage4 = close < sma150 and slope < 0;
def volAvg = Average(volume, volAvgLength);
def volOk = volume > volAvg * volConfirmMult;

plot stageCode =
    if stage2 and volOk then 2
    else if stage2 then 1
    else if stage4 then -4
    else 0;

stageCode.AssignValueColor(
    if stage2 and volOk then Color.GREEN
    else if stage2 then Color.DARK_GREEN
    else if stage4 then Color.RED
    else Color.GRAY
);

# Hover / label helpers via AddLabel not available in all quote contexts;
# numeric codes: 2=Stage2+Vol, 1=Stage2, -4=Stage4, 0=other
