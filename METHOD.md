# Method

## The problem in one paragraph

A trophy's earn rate is `100 * E / N`: the players who earned it over the
players Exophase tracks. After a launch those two move very differently.
`N` jumps in big steps whenever Exophase refreshes its counts — on launch
night it went from 638 to 3,868 tracked players at a single refresh, which
dragged every rate down even though nobody un-earned a trophy — while `E`
grows steadily as players progress through the game. Extrapolating the rate
itself confuses the two. This program models `E` and `N` separately and
divides.

## Centre: median of four estimators in logit space

For each trophy, four logit-scale centre estimates are computed and their
median is the forecast median. A median resists any one estimator going
wrong, which matters because every estimator extrapolates 4.5 days from at
most 2.5 days of history.

1. **Power-law E/N.** Least-squares fits of `log E` and `log N` against
   `ln(1 + hours since release)`. Each trophy's `E` slope is shrunk toward
   the median slope of its class (story chapters, side-story strands,
   grinds, miscellaneous), because one trophy's early counts are too noisy
   to trust alone: trophies of a kind share a diffusion shape. The `N` fit
   is blended with a prior power law (exponent 0.7) by how many distinct
   `N` values the history shows, so a flat history still expects the
   tracked population to keep growing.
2. **Cohort lag.** A trophy is earned a while after a player starts, so
   `E(t)` is roughly `S * N(t - A)`: the saturation share `S` times the
   players who joined at least `A` hours ago. `A` is a class prior (18
   hours for story chapters, 40 for side strands, 60 for grinds, 30 for
   the rest); `S` is fitted per trophy from its latest reads. The rate at
   the target is `S * N(target - A) / N(target)`.
3. **Logit-linear rate trend.** A straight least-squares line of
   `logit(rate)` against `ln(1 + hours since release)`, read at the
   target: the house curve baseline's shape, fitted over the whole
   history rather than the last 24 hours.
4. **Persistence.** The last rate itself. Every growth model
   extrapolates; including the last rate keeps the median honest when
   they all run away together.

History is first compressed to distinct snapshots (a snapshot is kept when
`N` or the trophy's earners change), because Exophase refreshes every few
hours and most reads repeat the previous values exactly; fitting on the
repeats would overweight the stale stretches.

## Spread: honest and wide, then shrunk

Quantiles sit on the logit scale around the median, with sigma combining a
random-walk term (`0.5 * sqrt(horizon in days)`, the house baseline's
spread), a refresh term for the jump an Exophase refresh can still make
between the last read and the target, the disagreement of the centre
estimators, and a floor so no band ever collapses. The refresh term decays
with the horizon: the first refresh after launch moved the page by a
six-fold jump in tracked players, while a refresh a week in moves it by
only a few hours of steady growth, so at the final horizon it is worth far
less than over 90 minutes. The whole spread is shrunk by 0.7.

The shrink was tuned, not guessed. On the practice cases (which straddle
the first refresh) the spread scale trades directly against the refresh:
a full-size spread scores about 1.08 there, the chosen 0.7 about 1.23,
the house baseline 1.51. On a battery of synthetic week-long scenarios
the order reverses: the chosen 0.7 scores about 0.27 to 0.29 there,
against about 0.38 for the house baseline, and wider spreads score
worse. The battery's worlds share this model's family, so
its centre error is smaller than the real one will be; 0.7 is the middle
choice between the two measurements.

One trophy sits at 100% (every tracked player holds it, and that survived
a six-fold jump in tracked players). Its forecast is asymmetric — median
near 100% with the spread reaching down only — because a rate that high
can only really move one way.

## What the numbers were

- Practice (two cases, answers verified against a live read of the page
  at 2026-11-19 ~11:38 UTC, which reproduces the house baseline's
  published practice score of 1.51 / 0.68 / 0 almost exactly):
  this model 1.23, typical miss 0.68 points, coverage 0.02.
- Synthetic final battery (two world families — cohort maturation and
  logistic-in-log-time — tracked players growing 3x, 8x and 20x to the
  target, chapter saturations 30% to 60%, refreshes every 4 hours):
  this model 0.27 mean on the first battery and 0.29 on the
  misspecification battery (worst world 0.37), house baseline 0.38 mean.
- Runtime about 0.1 seconds per case; output byte-identical across runs.

## What it does not do

It does not fetch anything at run time and it carries no snapshot of the
live page: everything is fitted from the case file it is given. The one
live datapoint used while building it (the page at 2026-11-19 ~11:38 UTC,
fetched through a text reader because Exophase sits behind Cloudflare)
served only to verify the practice answers and to calibrate the refresh
term; the final case's own history, two days fresher, supersedes it.
