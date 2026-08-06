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

**N=300 runs per task was picked arbitrarily** in the earliest version of
this project -- a round number, not the output of a power calculation --
and has been carried forward by convention since. Worked out properly now:
for a rate near 4% (our SSH result), the 95% confidence interval at n=300
is roughly ±2.2 percentage points -- the true rate could plausibly be
anywhere from about 1.8% to 6.2%. For the several tasks that returned
0/300, that does not mean the true rate is zero -- the standard rule of
thumb for zero-count binomial data ("rule of three") puts the 95% upper
bound at roughly 3/n, about 1% here. Read "0/300" as "likely under 1%,"
not "never happens." A target precision of ±1 percentage point at a 4%
rate would need roughly n≈1,400, not 300. This matters more, not less,
once live-agent validation replaces the free synthetic policy -- each real
agent run costs money and time, making "how many runs are actually needed"
a real budget question rather than an arbitrary convention.

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
