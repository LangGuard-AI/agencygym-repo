# Limitations

## The policy is synthetic, not a live agent

Every result in this repository (v1) is produced by a calibrated stochastic
policy standing in for a real LLM agent -- not a live foundation model. The
policy takes any available excess edge with a fixed 12% probability per
step, a stand-in for the documented real-world pattern of models trying
cheap/available actions even when not instructed to. It is not a validated
model of how any specific real agent actually behaves.

**What this means:** results here validate the *measurement methodology* --
that ground truth can be constructed, an agent run blind against it, and an
acquisition rate computed from real (simulated) runs. They do **not** yet
validate that AgencyScore predicts real LLM agent behavior. Live-agent
validation is the top item on the README's Roadmap.

## Reachability is collapsed to two labels, losing some signal

`reachability` is binary (`direct` / `transitive`) in the current schema.
Internally, `transitive` maps to one fixed depth (4 hops -- see
`docs/methodology.md`). An earlier, more granular synthetic run (16 abstract
configurations, not the current task set) found that 3-hop and 4-hop
transitive cases behaved differently from each other (0.3% vs 0% capture).
Collapsing to a single fixed depth may lose that distinction. Named on the
Roadmap as an open question, not resolved here.

## Sample size

11 tasks in v1. Results should be read per-task, not aggregated into a
single trend -- 11 tasks is not enough for a statistically robust
correlation or summary statistic across the set as a whole.

## Negative control

`gl-recon-savedsearch-1hop` flags no `risk_basis` dimension `yes` and is
correctly unscored by `agencyscore.evaluate` (reported as "none flagged").
This is by design -- a genuinely inert capability should have nothing to
measure.

## No live-run results exist yet

Every number in `results/v1/` was produced by `examples/run_scenario.py`
using the synthetic policy described above. Nobody has run a live
foundation-model agent against this task set. Numbers here should not be
cited as evidence of how any real agent behaves.
