# StageAnalysis_Scan
# Stock Hacker / Options Hacker scan filter
# True when: Stage 2 (close > rising SMA150) AND volume > 1.3x 50-day avg volume
#
# Install: Scan → Stock Hacker → Add filter → Study →
#   thinkScript Editor → paste → OK → Scan
# Tip: also filter price > 5, avg volume > 200000, market cap as you like

input sma150Length = 150;
input slopeLookback = 5;
input volAvgLength = 50;
input volConfirmMult = 1.3;
input requireVolumeConfirm = yes;

def sma150 = Average(close, sma150Length);
def slope = sma150 - sma150[slopeLookback];
def stage2 = close > sma150 and slope > 0;
def volAvg = Average(volume, volAvgLength);
def volOk = volume > volAvg * volConfirmMult;

plot scan = if requireVolumeConfirm then stage2 and volOk else stage2;
