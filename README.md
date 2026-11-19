# gta6-trophy-rarity-forecast

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/Jesseliverse01/gta6-trophy-rarity-forecast/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/Jesseliverse01/gta6-trophy-rarity-forecast/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

Forecasts, for every trophy of Grand Theft Auto VI on PlayStation 5, five quantiles of its Exophase earn rate at 2026-11-26T00:00:00Z, from the house's recorded reads of the game's trophy page up to the deadline. The earn rate is a ratio, so the program models its two halves separately: the earners E(t) and the tracked players N(t), each projected to the target, then divides. Three centre estimators (a power-law E/N fit, a cohort-lag model, and a logit-linear rate trend) are combined by their median in logit space, with the last rate as a fourth member, and the spread combines a random-walk term, a refresh term, and the estimators' disagreement. See METHOD.md for how it works.

On the two practice cases it scores a mean pinball loss of about 1.23, against about 1.51 for the house baseline — the practice straddles Exophase's first refresh of the game's counts (638 to 3,868 players tracked), so it mostly tests whether the spread survives a refresh the history has not seen. On a battery of synthetic week-long scenarios (two world families, tracked players growing 3x to 20x to the target, chapter saturations 30% to 60%) it scores about 0.27 to 0.29, against about 0.38 for the house baseline.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Python 3.13, standard library only, no network, about 0.1 seconds per case. Reads every `*.in` file in the input directory and writes one `<id>.out` per case.

---

<sub>Entered on [make.fun](https://make.fun/?ref=bssn477j&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
