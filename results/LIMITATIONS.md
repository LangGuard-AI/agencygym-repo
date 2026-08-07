# Limitations

## The policy is synthetic, not a live agent

Every result in this repository is produced by a calibrated stochastic
policy standing in for a real LLM agent -- not a live foundation model. It
is not a validated model of how any specific real agent actually behaves.

The policy uses a **momentum model**: the initial decision to leave the
declared path uses a fixed 12% probability, but once off-path, the
probability of continuing to explore increases each time the walk finds a
node representing partial progress toward a multi-part goal (see
`src/agencyscore/policy.py`). This replaced an earlier uniform model, which
made compound (multi-node) goals like `trifecta_component` mathematically
undetectable at any reasonable sample size, not just rare -- every off-path
step had no declared-path fallback and used the same flat 12% probability
whether the walk had found nothing yet or had already found two of three
required pieces. The momentum increment itself (30 percentage points per
node found) was chosen to test the hypothesis, not derived from data or
validated against a live agent.

**What this means:** results here validate the *measurement methodology* --
that ground truth can be constructed, an agent run blind against it, and an
acquisition rate computed from real (simulated) runs. They do **not** yet
validate that AgencyScore predicts real LLM agent behavior, or that the
momentum hypothesis itself reflects how a real agent's motivation actually
works. Live-agent validation is the top item on the README's Roadmap.

## Risk dimensions have different success structures, by design

`business_criticality` is a single terminal node -- reach it, done.
`privilege_breadth` requires reaching a "key" node and then taking at least
one further step into a newly-opened region beyond it. `trifecta_component`
requires visiting three separate nodes within the same walk. These
structural differences were added specifically because an earlier, simpler
version -- where every dimension used the same single-node structure --
produced no meaningful separation between the three dimensions at all. The
current structures are a stated hypothesis about how these risk types
differ, encoded into the graph, not a validated finding. See
`docs/methodology.md`.

## Reachability is collapsed to two labels, losing some signal

`reachability` is binary (`direct` / `transitive`) in the current schema.
Internally, `transitive` maps to one fixed depth (4 hops -- see
`docs/methodology.md`). An earlier, more granular synthetic run (16 abstract
configurations, not the current task set) found that 3-hop and 4-hop
transitive cases behaved differently from each other. Collapsing to a
single fixed depth may lose that distinction. Named on the Roadmap as an
open question, not resolved here.

## Sample size

100 tasks in the current dataset. Results should be read per-task, not
aggregated into a single trend across the whole set.

**N=3,000 runs per task is the current default**, increased from an earlier
N=300 specifically because 300 was not enough to detect the rare,
compound-requirement `trifecta_component` dimension at all -- it returned
exact zero across every trifecta task at N=300, not because the event was
impossible, but because a roughly 1-in-3,000 event needs closer to 3,000
trials to show up even once. N=3,000 is still not derived from a formal
power calculation -- it was chosen empirically, by testing what was needed
to observe the rarest tier, not computed in advance. For the more common
dimensions, N=3,000 is comfortably more than sufficient: at the
privilege_breadth rate observed in the SSH worked example (1.77%), only
about 668 runs would be needed for a ±1 percentage point margin at 95%
confidence; N=3,000 gives roughly ±0.24 percentage points there. For
`trifecta_component` specifically, a single observed success out of 3,000
runs should be read as "this event is real and roughly this rare," not as
a precise rate -- one more or one fewer observed hit would meaningfully
change the estimate. A task that returned zero hits even at N=3,000 has a
95% upper bound of roughly 0.1% (the "rule of three": 3/n), tighter than
N=300's 1% bound, but still not proof the true rate is exactly zero.

## Negative controls

Ten tasks (two per category) flag no `risk_basis` dimension `yes` and are
correctly unscored by `agencyscore.evaluate` (reported as "none flagged").
This is by design -- a genuinely inert capability should have nothing to
measure.

## No live-run results exist yet

Every number in `results/v2/` was produced by `examples/run_scenario.py`
using the synthetic policy described above. Nobody has run a live
foundation-model agent against this task set. Numbers here should not be
cited as evidence of how any real agent behaves. See
`docs/constructing-a-live-sandbox.md` for what that would require.
