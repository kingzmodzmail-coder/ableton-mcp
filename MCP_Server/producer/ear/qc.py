"""The QC gate: measured checks a render must pass before it is shared.

Two kinds of check:

* hard rules, independent of any reference (ceiling, mono low end, sub
  ownership) - these encode the standing taste rule that the kick owns the
  sub region;
* reference rules from a profile (docs/SUNO_V6_BENCHMARK.md), so the build is
  compared against approved reference renders instead of a guess.

A pass means "worth auditioning", never "this is good". Loudness passing is
not a reason to ship, and the gate never treats louder as better.
"""
from .reference import read_metric

# name -> (metric path, comparison, limit, why)
DEFAULT_RULES = (
    ("true_peak_ceiling", "true_peak_dbtp", "<=", -0.3,
     "Leave headroom for lossy encoders; clipping is not loudness."),
    ("low_end_mono", "low_end.side_to_mid_db", "<=", -6.0,
     "Below the cutoff the energy must sit centred, or big systems lose it."),
    ("low_end_phase", "low_end.low_correlation", ">=", 0.0,
     "Negative low-end correlation cancels on a mono rig."),
    ("sub_ownership", "kick_bass.between_to_kick_db", "<=", -6.0,
     "Kick weight first: nothing else may hold 30-120 Hz between kicks."),
)

COMPARISONS = {
    "<=": lambda value, limit: value <= limit,
    ">=": lambda value, limit: value >= limit,
}


def _check(name, value, ok, target, detail, status=None):
    return {"check": name, "value": value, "target": target,
            "status": status or ("pass" if ok else "fail"), "detail": detail}


def check(scan, profile=None, rules=DEFAULT_RULES, allow_unmeasured=False):
    """Run the gate over one scan. Returns a verdict plus every check."""
    checks = []

    if not scan.get("usable_signal", False):
        checks.append(_check("usable_signal", scan.get("sample_peak_dbfs"), False,
                             "audible signal",
                             "Silent or near-silent capture: fix routing before judging."))

    for name, metric, comparison, limit, why in rules:
        value = read_metric(scan, metric)
        target = "%s %s %s" % (metric, comparison, limit)
        if value is None:
            reason = scan.get("kick_bass", {}).get("reason") if metric.startswith("kick_bass") else None
            checks.append(_check(name, None, allow_unmeasured, target,
                                 reason or "%s was not measured. %s" % (metric, why),
                                 status="unmeasured"))
            continue
        ok = COMPARISONS[comparison](value, limit)
        checks.append(_check(name, round(value, 3), ok, target, why))

    if profile:
        for metric, target in sorted(profile.get("targets", {}).items()):
            value = read_metric(scan, metric)
            window = "%s..%s" % (target["low"], target["high"])
            if value is None:
                checks.append(_check("reference:" + metric, None, allow_unmeasured, window,
                                     "%s was not measured on this render (profile "
                                     "median %s)." % (metric, target["median"]),
                                     status="unmeasured"))
                continue
            ok = target["low"] <= value <= target["high"]
            checks.append(_check("reference:" + metric, round(value, 6), ok, window,
                                 "Reference median %s from %d render(s)."
                                 % (target["median"], target["references"])))

    failures = [c for c in checks if c["status"] == "fail"]
    unmeasured = [c for c in checks if c["status"] == "unmeasured"]
    passed = not failures and (allow_unmeasured or not unmeasured)
    return {
        "passed": passed,
        "profile": profile.get("name") if profile else None,
        "checks": checks,
        "failures": [c["check"] for c in failures],
        "unmeasured": [c["check"] for c in unmeasured],
        "next_step": ("Audition at matched loudness and record the verdict with "
                      "producer_remember." if passed else
                      "Fix the failing checks and re-capture. Do not post or "
                      "report this render as finished."),
        "note": ("A pass is permission to audition, not proof of quality. "
                 "Never widen a target or set allow_unmeasured to make a "
                 "failing render pass."),
    }
