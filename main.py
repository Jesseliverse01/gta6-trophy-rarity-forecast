"""GTA VI trophy rarity forecast for make.fun's gta6-trophy-rarity-forecast-01.

Forecasts, for every trophy of Grand Theft Auto VI on PlayStation 5, five
quantiles (0.05 / 0.25 / 0.5 / 0.75 / 0.95) of its Exophase earn rate in
percent at the case's target, from the case's history of Exophase reads.

Method (all fitted at run time from the case file; no network, no files
beyond the case, standard library only, deterministic):

The earn rate is a ratio, rate = 100 * E / N, where E is the number of
tracked players who have earned the trophy and N the number of players
Exophase tracks. The two move differently after a launch: N jumps in big
steps whenever Exophase refreshes its counts (on launch night it went from
638 to 3,868 tracked players at one refresh, which dragged every rate down
even though nobody un-earned a trophy), while E grows steadily as players
progress through the game. So the forecast models E and N separately and
divides, instead of extrapolating the rate itself.

Three centre estimators are computed per trophy and combined by their
median in logit space (a median resists any one estimator going wrong),
with the last rate itself as a fourth member:

  C1  Power-law E/N.  log E and log N are each fitted by least squares
      against ln(1 + hours since release).  Each trophy's E slope is
      shrunk toward the median slope of its class (story / side-story /
      grind / misc), because one trophy's early counts are too noisy to
      trust alone -- trophies of a kind share a diffusion shape.  The N
      fit is blended with a prior power law (exponent 0.7) by how many
      distinct N values the history actually shows, so a flat history
      still expects the tracked population to keep growing.
  C2  Cohort lag.  A trophy is earned a while after a player starts, so
      E(t) is roughly S * N(t - A): the saturation share S times the
      players who joined at least A hours ago.  A is a class prior
      (story chapters fast, grinds slow); S is fitted per trophy from its
      latest reads.  The rate at the target is then
      S * N(target - A) / N(target).
  C3  Logit-linear rate trend.  A straight least-squares line of
      logit(rate) against ln(1 + hours since release), read at the
      target -- the house curve baseline's shape, fitted over the whole
      history rather than the last 24 hours.

Spread: quantiles sit on the logit scale around the median centre, with
    sigma combining (a) a random-walk term 0.5 * sqrt(horizon in days), the
house baseline's spread, (b) a refresh term for the jump an Exophase
refresh can still make between the last read and the target -- a term
that decays with the horizon, because the first refresh after launch
moved the page by a six-fold jump in tracked players while a refresh a
week in moves it by only a few hours of steady growth, (c) the
disagreement of the centre estimators, and (d) a floor, so the band
never collapses on a trophy the history says nothing about.  Wider for
uncertain trophies, narrower where the estimators agree.  The whole
spread is shrunk by 0.7, tuned on the backtest battery (see METHOD.md):
a full-size spread pays pinball at every trophy, and the fitted centre
earns the narrower band.

One trophy sits at 100% in the data (every tracked player holds it, and
that survived a six-fold jump in tracked players).  Its forecast is
asymmetric: the median stays near 100% with the spread reaching down,
because a rate that high can only really move one way.

Rates are clamped to 0.01..99.99 before any logit, matching the scorer.
"""

import json
import math
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so a module
# shipped beside this file imports. (This entry is one file, but the line
# keeps the door open without changing the program.)
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# Standard normal quantiles at the scored levels.
Z = [-1.645, -0.674, 0, 0.674, 1.645]

# The release day began 2026-11-19T00:00:00Z; every time axis is hours
# since then, so ln(1 + h) is 0 at release and grows slowly after.
RELEASE = datetime(2026, 11, 19, tzinfo=timezone.utc)

# Prior power-law exponent for the tracked-player count: N ~ (1 + h)**B.
N_PRIOR_B = 0.7
# How many distinct N values it takes for the fitted N law to earn most
# of the weight over the prior (weight = m / (m + N_FIT_HALF)).
N_FIT_HALF = 3.0
# Prior log-time slopes of log E per trophy class, and lag hours A for the
# cohort model: how long after joining a player typically holds the trophy.
CLASS_PRIOR_SLOPE = {"story": 1.2, "side": 1.0, "grind": 0.8, "misc": 1.0}
CLASS_LAG_HOURS = {"story": 18.0, "side": 40.0, "grind": 60.0, "misc": 30.0}
# How many distinct E values a trophy needs before its own slope earns
# most of the weight over its class median (weight = n / (n + SLOPE_HALF)).
SLOPE_HALF = 4.0

# Spread pieces, in logit units.
SIGMA_WALK = 0.5       # per sqrt(day), the house baseline's spread
SIGMA_REFRESH = 0.7    # one Exophase refresh can still move a rate
SIGMA_BASE = 0.3       # floor piece, so no band ever collapses
SIGMA_FLOOR = 0.75
SIGMA_CAP = 2.4
# Overall shrink of the spread, tuned on the backtest battery:
# a full-size spread pays pinball at every trophy, and the fitted centre
# earns the narrower band.  (Battery: scale 1.0 -> mean 0.40, 0.7 -> 0.32,
# 0.6 -> 0.30; 0.7 chosen because the battery's worlds share this model's
# family, so the real centre error is wider than the battery shows.)
SIGMA_SCALE = 0.7


def clamp(x: float) -> float:
    return min(99.99, max(0.01, x))


def logit(pct: float) -> float:
    p = clamp(pct)
    return math.log(p / (100.0 - p))


def inv_logit(lg: float) -> float:
    if lg >= 0:
        return 100.0 / (1.0 + math.exp(-lg))
    e = math.exp(lg)
    return 100.0 * e / (1.0 + e)


def round4(x: float):
    """x rounded to 4 decimals, half up, as JavaScript rounds it."""
    scaled = x * 10000
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000
    return int(value) if value == int(value) else value


def parse_time(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def hours_since_release(dt: datetime) -> float:
    return max(0.0, (dt - RELEASE).total_seconds() / 3600.0)


def classify(trophy: dict) -> str:
    """Story chapters, side-story strands, grinds, or everything else."""
    desc = (trophy.get("description") or "").lower()
    if "complete chapter" in desc or desc == "complete the final mission.":
        return "story"
    if "final mission for" in desc or "mission strands" in desc:
        return "side"
    if any(w in desc for w in ("complete 250", "complete 50", "complete 3 ",
                               "complete 8 ", "100%", "100 locations",
                               "100 vehicles", "20 different", "every spot",
                               "every location", "all shooting", "10 vehicles",
                               "all garage", "all of leonida")):
        return "grind"
    return "misc"


def linfit(xs, ys):
    """Least-squares line y ~ a + b*x; returns (a, b) or None."""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 1e-12:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return (my - b * mx, b)


def distinct_snapshots(case, idx):
    """Compress history to (hours, N, E) points where N or E changed.

    Exophase refreshes its counts every few hours, so most reads repeat
    the previous values exactly; fitting on the repeats would overweight
    the stale stretches.  A snapshot is kept when N or this trophy's
    earners differ from the previous kept one.
    """
    snaps = []
    prev_n = None
    prev_e = None
    for read in case["history"]:
        n = read.get("players_tracked")
        rates = read.get("rates") or []
        if n is None or idx >= len(rates) or rates[idx] is None:
            continue
        e = rates[idx] * n / 100.0
        if prev_n is not None and n == prev_n and abs(e - prev_e) < 0.5:
            continue
        h = hours_since_release(parse_time(read["at"]))
        snaps.append((h, float(n), float(e)))
        prev_n, prev_e = n, e
    return snaps


def interp_log_n(snaps, h):
    """log N at hour h, linearly interpolated in (ln(1+h), log N)."""
    if not snaps:
        return None
    xs = [math.log1p(s[0]) for s in snaps]
    ys = [math.log(s[1]) for s in snaps]
    x = math.log1p(h)
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        # Extrapolate with the last segment's slope, damped toward flat.
        if len(xs) >= 2 and xs[-1] > xs[0]:
            slope = (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
            return ys[-1] + 0.5 * slope * (x - xs[-1])
        return ys[-1]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            f = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + f * (ys[i] - ys[i - 1])
    return ys[-1]


def forecast_trophy(case, idx, trophy, class_slopes, n_model):
    """Return (median_rate, sigma) for one trophy."""
    target = parse_time(case["target"])
    h_t = hours_since_release(target)
    x_t = math.log1p(h_t)
    horizon_days = case["horizon_minutes"] / 1440.0
    snaps = distinct_snapshots(case, idx)
    last = case["history"][-1]
    last_rate = last["rates"][idx]
    if last_rate is None:
        last_rate = 1.0
    cls = classify(trophy)

    centres = []  # logit-scale centre estimates

    # ---- C1: power-law E / power-law N -------------------------------
    if len(snaps) >= 2:
        xs = [math.log1p(s[0]) for s in snaps]
        # N at target from the blended N model (fitted law + prior).
        log_n_t = n_model(x_t)
        n_t = math.exp(log_n_t)
        # E: log-linear fit, slope shrunk to the class median.
        ys_e = [math.log(max(s[2], 0.5)) for s in snaps]
        fit_e = linfit(xs, ys_e)
        if fit_e is not None:
            a_e, b_e = fit_e
            b_class = class_slopes.get(cls, CLASS_PRIOR_SLOPE[cls])
            w = len(snaps) / (len(snaps) + SLOPE_HALF)
            b_e = w * b_e + (1 - w) * b_class
            # Re-anchor the level at the last snapshot so shrinkage of
            # the slope does not drag the level with it.
            a_e = ys_e[-1] - b_e * xs[-1]
            e_t = math.exp(a_e + b_e * x_t)
            centres.append(logit(100.0 * e_t / n_t))

    # ---- C2: cohort lag E(t) ~ S * N(t - A) --------------------------
    lag = CLASS_LAG_HOURS[cls]
    if len(snaps) >= 2 and h_t > lag:
        # S from the last few snapshots: E / N(t - A).
        ss = []
        for h, n, e in snaps[-4:]:
            h_lag = max(h - lag, snaps[0][0])
            ln_lag = interp_log_n(snaps, h_lag)
            if ln_lag is None:
                continue
            ss.append(e / math.exp(ln_lag))
        if ss:
            s_val = statistics.median(ss)
            s_val = min(max(s_val, 0.0), 0.99)
            ln_t = n_model(x_t)
            ln_lag_t = n_model(math.log1p(max(h_t - lag, 0.0)))
            rate_c2 = 100.0 * s_val * math.exp(ln_lag_t - ln_t)
            centres.append(logit(rate_c2))

    # ---- C3: logit-linear rate trend ---------------------------------
    if len(snaps) >= 2:
        xs = [math.log1p(s[0]) for s in snaps]
        ys_r = [logit(100.0 * s[2] / s[1]) for s in snaps]
        fit_r = linfit(xs, ys_r)
        if fit_r is not None:
            a_r, b_r = fit_r
            centres.append(a_r + b_r * x_t)

    # The last rate itself is a centre member: every growth model
    # extrapolates, and the median then resists all of them running away
    # together in the same direction.
    centres.append(logit(last_rate))
    if not centres:
        centres = [logit(last_rate)]

    centre = statistics.median(centres)
    if len(centres) > 1:
        disag = statistics.pstdev(centres)
    else:
        disag = 0.0

    # The refresh term decays with the horizon: the first refresh after
    # launch moved the page by a six-fold jump in tracked players, but a
    # refresh a week in moves it by only a few hours of steady growth, so
    # at the final horizon it is worth far less than over 90 minutes.
    refresh = SIGMA_REFRESH / (1.0 + horizon_days / 2.0)
    sigma = math.sqrt(
        (SIGMA_WALK ** 2) * horizon_days
        + refresh ** 2
        + disag ** 2
        + SIGMA_BASE ** 2
    )
    sigma = min(SIGMA_CAP, max(SIGMA_FLOOR, sigma)) * SIGMA_SCALE
    return centre, sigma, last_rate


def build_n_model(case):
    """Return log N as a function of x = ln(1 + hours since release).

    Least-squares power law over the distinct N values, blended with the
    prior exponent by how many distinct N values the history shows.
    """
    snaps_n = []
    prev = None
    for read in case["history"]:
        n = read.get("players_tracked")
        if n is None:
            continue
        if prev is not None and n == prev:
            continue
        h = hours_since_release(parse_time(read["at"]))
        snaps_n.append((h, float(n)))
        prev = n
    if len(snaps_n) < 2:
        n_last = snaps_n[-1][1] if snaps_n else 638.0
        h_last = snaps_n[-1][0] if snaps_n else 0.0
        x_last = math.log1p(h_last)

        def prior_only(x, n_last=n_last, x_last=x_last):
            return math.log(n_last) + N_PRIOR_B * (x - x_last)
        return prior_only

    xs = [math.log1p(s[0]) for s in snaps_n]
    ys = [math.log(s[1]) for s in snaps_n]
    fit = linfit(xs, ys)
    m = len(snaps_n)
    w = m / (m + N_FIT_HALF)
    if fit is None:
        a_fit, b_fit = ys[-1], N_PRIOR_B
    else:
        a_fit, b_fit = fit
    # Blend slope and level: re-anchor the fitted line at the last point
    # so the blend cannot drag the level away from the last read.
    a_fit = ys[-1] - b_fit * xs[-1]
    b_blend = w * b_fit + (1 - w) * N_PRIOR_B
    a_blend = ys[-1] - b_blend * xs[-1]

    def blended(x, a=a_blend, b=b_blend):
        return a + b * x
    return blended


def forecast_case(case, name):
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    if not case["history"]:
        raise ValueError(f"{name} has no history")

    n_model = build_n_model(case)

    # Class median E slopes, from trophies with enough movement.
    per_class_slopes = {}
    for cls in ("story", "side", "grind", "misc"):
        slopes = []
        for idx, trophy in enumerate(case["trophies"]):
            if classify(trophy) != cls:
                continue
            snaps = distinct_snapshots(case, idx)
            if len(snaps) < 3:
                continue
            xs = [math.log1p(s[0]) for s in snaps]
            ys = [math.log(max(s[2], 0.5)) for s in snaps]
            fit = linfit(xs, ys)
            if fit is not None:
                slopes.append(fit[1])
        if slopes:
            per_class_slopes[cls] = statistics.median(slopes)
        else:
            per_class_slopes[cls] = CLASS_PRIOR_SLOPE[cls]

    rows = []
    for idx, trophy in enumerate(case["trophies"]):
        centre, sigma, last_rate = forecast_trophy(
            case, idx, trophy, per_class_slopes, n_model)
        if last_rate >= 99.99:
            # Everybody holds it and that survived a six-fold jump in
            # tracked players: median stays near 100%, spread reaches
            # down only.
            q = [99.0, 99.9, 99.98, 99.99, 99.99]
        else:
            q = [round4(clamp(inv_logit(centre + z * sigma))) for z in Z]
            q = sorted(q)
            # Keep the median honest: never let rounding push a quantile
            # past its neighbour.
            for i in range(1, 5):
                if q[i] < q[i - 1]:
                    q[i] = q[i - 1]
        rows.append({"id": trophy["id"], "q": q})
    return {"trophies": rows}


def forecast_case_safe(case, name):
    """Never crash a case: on any failure, fall back to persistence."""
    try:
        return forecast_case(case, name)
    except Exception:
        last = case["history"][-1] if case.get("history") else None
        spread = SIGMA_WALK * math.sqrt(case["horizon_minutes"] / 1440.0)
        rows = []
        for i, trophy in enumerate(case["trophies"]):
            rate = 1.0
            if last and last.get("rates") and last["rates"][i] is not None:
                rate = last["rates"][i]
            lg = logit(rate)
            q = [round4(clamp(inv_logit(lg + z * spread))) for z in Z]
            rows.append({"id": trophy["id"], "q": sorted(q)})
        return {"trophies": rows}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case_safe(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
