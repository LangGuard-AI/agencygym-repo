# AgencyGym

### The problem

Agents don't just execute a task. They probe, wander, and find new, unexpected paths to solve it — reaching for capability nobody pointed them toward, simply because it's reachable. That's their power. We call it Agency.

In a cyber-capable context, that same tendency turns adversarial. Recent incidents have made this concrete — and there has been no way to measure the tendency itself, before an agent is ever deployed.

The ExploitGym team saw a version of this directly while building an unrelated benchmark — not their headline result, a byproduct of it:

> "During development, we observed models probing the surrounding infrastructure for additional privileges or information beyond what was intended for the task."

AgencyGym exists to make that tendency a first-class, measurable question — not a byproduct discovered by accident.

### AgencyScore

AgencyScore is a pre-deployment measurement of an agent's excess reachability — the gap between what a task declares it needs (Task Intent) and everything the agent can actually reach beyond that (Tool Surface, Infrastructure Surface). Computed before the agent is deployed.

### AgencyGym

AgencyGym is a sandboxed benchmark that tests whether AgencyScore is real. It places a known excess capability at a known location, runs the agent blind to where it is, and checks whether the score predicted what actually happened.

### How they work together

Neither means anything alone. A score with no blind test behind it is a classification exercise. A blind test with no prior score is an anecdote. AgencyScore is the prediction; AgencyGym is the check. Fixing a known ground truth in advance and testing it blind is the same discipline ExploitGym uses to validate exploitation capability — applied here to a different question, and a different population of agents (see References).

![AgencyGym architecture: Task Intent as the fixed baseline, Tool Surface and Infrastructure Surface as what's reachable beyond it, AgencyScore as the measured gap, and AgencyGym as the sandbox that tests the gap against real behavior](diagram/architecture.svg)

### For the enterprise

Before any agent goes into production — a GL reconciliation agent, a support-triage agent, anything wired into real tools and real infrastructure — it can be scored, sandbox-tested, and tightened, the same way a car is crash-tested before it's sold, not after. Excess agency gets caught before it becomes an incident, not after one.

### The three surfaces

- **Task Intent** — what the agent is declared to do. Never a place excess lives; the baseline everything else is measured against.
- **Tool Surface** — what's authorized to reach (connectivity) and what's permitted once there (capability). Discoverable statically, by reading a registry (an MCP server's tool list, an API gateway's routes).
- **Infrastructure Surface** — what's reachable through shared runtime (IAM roles, containers, gateways), whether or not anything declares it. Discoverable statically only if configuration (IAM policy, network policy) is read directly — not by watching tool calls.

### Task ID format

`<surface>:<connector>/<scenario-id>`

```
declared:netsuite-mcp/gl-recon-approve-1hop
infra:aws-iam/gl-recon-adjacentservice-1hop
```

- **surface** — `declared` (found in a tool registry) or `infra` (reachable only through shared runtime, no registry entry)
- **connector** — the real platform/protocol the scenario is built on
- **scenario-id** — capability name + hop-count suffix (structural distance from the declared path to the placed capability)

See `data/task_ids/v1.txt` for the full v1 list (10 instances) and `docs/methodology.md` for how each instance is constructed.

### Status

v1, early scaffold. 10 instances, built around a single real production scenario (GL reconciliation on Oracle NetSuite). Not yet validated against a live foundation-model agent — current results use a calibrated synthetic policy standing in for one (see `results/LIMITATIONS.md`).

### Roadmap

- Depth-weighting correction: replace linear path-length weighting with combinatorial weighting, re-validate against capture rate
- Live-agent validation: replace the synthetic policy with a real foundation-model agent
- Enterprise leaderboard: fix the AgencyGym instance set and rank agents — letting an enterprise compare every candidate agent's AgencyScore, side by side, before any of them are deployed

We're building this in public. If you work on agent security, benchmark design, or graph-based reachability analysis, we're looking for collaborators to help extend and pressure-test it.

## Quick start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Compute AgencyScore for every instance (pre-deployment, no agent execution)
python -m agencyscore.score data/task_ids/v1.txt

# 3. Run the synthetic policy against every instance (see LIMITATIONS)
python examples/run_scenario.py data/task_ids/v1.txt --runs 300

# 4. Compare predicted score against observed outcome
python -m agencyscore.evaluate results/v1/
```

## Repository layout

```
data/task_ids/v1.txt      canonical instance list
recipes/                  one file per instance: declared Task Intent,
                          Tool Surface, Infrastructure Surface, hop placement
src/agencyscore/          pre-deployment scoring code
examples/run_scenario.py  runner: executes an agent/policy against a recipe
results/                  run output + findings per instance
docs/methodology.md       full construction and scoring methodology
diagram/                  architecture diagram
```

## References

AgencyScore and AgencyGym are built on a validation discipline used by [ExploitGym](https://github.com/sunblaze-ucb/exploitgym) (Wang, Schiller, Li, Sesha Narayana, Nasr, Carlini, Qi, Wallace, Bursztein, Invernizzi, Thomas, Shoshitaishvili, Guo, He, Holz, Song — UC Berkeley RDI): fix a known ground truth in advance, then test blind whether real behavior confirms it. ExploitGym targets frontier, cyber-capable models turning known vulnerabilities into working exploits; AgencyGym targets ordinary business agents wandering into undeclared capability. The classification underneath AgencyScore (reading a tool registry, an IAM policy) comes from reachability-analysis and attack-graph lineage, not from ExploitGym.

```
@article{wang2026exploitgym,
  title={ExploitGym: Can AI Agents Turn Security Vulnerabilities into Real Attacks?},
  author={Wang, Zhun and Schiller, Nico and Li, Hongwei and Sesha Narayana, Srijiith and Nasr, Milad and Carlini, Nicholas and Qi, Xiangyu and Wallace, Eric and Bursztein, Elie and Invernizzi, Luca and Thomas, Kurt and Shoshitaishvili, Yan and Guo, Wenbo and He, Jingxuan and Holz, Thorsten and Song, Dawn},
  journal={arXiv preprint arXiv:2605.11086},
  year={2026}
}
```

## License

Apache-2.0, matching ExploitGym.
