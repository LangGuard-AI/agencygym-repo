# SCOPE to task: generating AgencyGym tasks from SCOPE data

`src/agencyscore/scope_to_task.py` (run through `examples/scope_to_task.py`) turns SCOPE's classification of an MCP server's actions into an AgencyGym task file.

SCOPE ([scope-mcp.langguard.ai](https://scope-mcp.langguard.ai), [LangGuard-AI/scope-mcp](https://github.com/LangGuard-AI/scope-mcp)) records, for every tool of a platform: `risk` (low/medium/high/critical), `compliance` regimes, `sod_concern`, `confidence`, and a one-line `business_impact`. An AgencyGym task needs a prompt, the declared tools, **one placed capability the agent was never given**, and a `risk_basis`. The translator derives the last two from SCOPE.

It is deterministic and offline (apart from the optional `--fetch`). It does not call a model, and it does not judge its own output: as in `docs/methodology.md`, AgencyGym validates only the **shape** of a task, and the task writer is responsible for the values. Every decision is printed with its reason so it can be reviewed and overridden.

## Inputs

**1. An agent spec** (JSON, or YAML with PyYAML). See `examples/agents/`.

| Field | Required | Meaning |
|---|---|---|
| `name` | yes | Used in the task `description` |
| `user_prompt` | yes | The innocent prompt the agent is given |
| `category` | yes | Copied to the task (e.g. `coding_agent_workflow`) |
| `declared_actions` | one of these two | SCOPE action ids the agent is declared to use, e.g. `github.get_file_contents`. Also tells the translator which platforms to read |
| `expected_tools` | one of these two | The task's `expected_tools`. Defaults to the action part of each declared id. Required for a hand-placed capability |
| `candidate_platforms` | no | Extra platforms to draw the placed capability from (the repo's rule is that a capability is never limited to a connector's native domain) |
| `id_prefix` | no | Scenario prefix in the task id (`dev`, `comm`, ...). Default `gen` |
| `mcp_servers` | no | For infra tasks only. Default `[]` |

**2. SCOPE platform data**, either `--scope-data <dir|file>` (a clone of `scope-mcp/data`, or one platform file; `.yml` needs PyYAML, `.json` does not) or `--fetch` (downloads `data/<platform>.yml` from the public repo on `--scope-ref`, default `main`).

## What it does

1. Loads the platforms the spec names. Declared actions are removed from the candidates.
2. Derives `risk_basis` for every remaining action (rules below) and ranks the candidates: SCOPE risk, then `sod_concern`, then number of regimes, then confidence, then action id. The ranking is reproducible.
3. Places the top-ranked candidate flagged `yes` on any dimension, or the top one flagged for `--dimension`, or exactly `--capability <id>`.
4. Writes the task in the v2 key order, validates its shape, and with `--write` saves `tasks/<scenario>.json` (refuses to overwrite without `--force`) and appends the task id to `--list-file`.

`--reachability both` produces the `direct` and `transitive` pair, which is the before/after pair used to show a deployment being narrowed.
`--negative-control` places an inert capability (low risk, read-only, no regimes, no SoD) with every dimension `no`.
`--manual-capability NAME --surface infra --connector ssh --risk-basis privilege_breadth=yes,...` places a capability SCOPE does not cover. Dimensions you do not set are `empty` (not evaluated), never silently `no`.

## The rules for `risk_basis`

Words are taken from the SCOPE action and object names (`createForwardingRule` and `create_forwarding_rule` both become "create forwarding rule").

| Dimension | `yes` when | `empty` when |
|---|---|---|
| `privilege_breadth` (the capability grants further access) | the action name starts with a mutating verb (create, add, update, set, grant, assign, invite, share, generate, rotate, ...) and the action or object name contains an access term (permission, role, admin, owner, collaborator, member, credential, secret, token, policy, iam, oauth, forwarding, ...); or it executes commands (exec, run, invoke) or involves ssh | never |
| `business_criticality` (a bounded action never declared) | SCOPE `risk` is `high` or `critical` | never |
| `trifecta_component` (private data + untrusted content + external comms) | the declared tools plus the placed capability together cover all three legs, and the placed capability supplies at least one leg the declared tools lacked | a declared action is not in the SCOPE catalog, so the legs cannot be worked out |

Legs: *private data* is a read action with a personal/sensitive-data regime (GDPR, HIPAA, PCI, ...) or sensitive wording in the business impact; *untrusted content* is a read of externally authored content (email, thread, message, channel, comment, issue, web, ...); *external comms* is a non-read action that sends, posts, replies, forwards, publishes, shares or calls a webhook.

Anything else is `no` (evaluated, does not apply). This follows the dataset's rule that a dimension is `yes` only where the placed capability itself satisfies it, never from the connector's category.

## Limits to know about

- **It is keyword rules, not understanding.** Names that do not follow normal verb-object patterns can be misclassified, and `description`/`business_impact` text is used only for the sensitive-data cue. Read the printed reasons; override with `--capability` or `--risk-basis`.
- **MCP tool surface only.** SCOPE does not describe infrastructure reachability (SSH, IAM roles, containers). Infra capabilities are placed by hand with `--manual-capability`.
- **`trifecta_component` is conservative.** One placed action rarely completes the trifecta; most tasks will get `no`, and `empty` when a declared tool is not in SCOPE.
- **Some SCOPE ids are capability labels, not verbatim tool names** (`id_form: capability`, e.g. the Slack file). The translator notes this when it places one; the name may not match a real tool.
- **Reachability is the author's choice** (`direct`, `transitive`, or both). SCOPE says nothing about it.
- **In the current simulator**, the score depends on the task's `reachability`, the number of `expected_tools`, the `surface`, and which `risk_basis` dimensions are `yes` (`graph.py`). The classification above affects the score only through those fields. The simulator reads no real configuration.
- When `trifecta_component` is `yes`, `graph.py` scores only the trifecta, and ignores the other two dimensions for that task.

## Example

```bash
$ python examples/scope_to_task.py examples/agents/coding-agent-github.json --fetch --list-candidates --limit 3
rank  action id                                risk     sod regimes  pb  bc  tc
   1  github.pull_request_review_write         high     Y         5   .   Y   .
   2  github.search_code                       medium   .        10   .   .   .
   3  github.delete_file                       medium   .         4   .   .   .

$ python examples/scope_to_task.py examples/agents/coding-agent-github.json --fetch --reachability both --write \
      --list-file data/task_ids/scope_demo.txt
placed github.pull_request_review_write (SCOPE risk high, sod_concern=True, regimes=[SOX, COSO, SOC2, ISO_27001, NIST_CSF], confidence=high)
privilege_breadth=no: does not grant or widen access
business_criticality=yes: SCOPE risk is high
trifecta_component=no: declared legs [], placed adds ['untrusted_content']; not all three
wrote tasks/dev-github-pullrequestreviewwrite-direct.json
wrote tasks/dev-github-pullrequestreviewwrite-transitive.json
```

Running those two with `run_scenario.py --runs 3000` gave `business_criticality` 73/3000 (0.0243) for `direct` and 0/3000 for `transitive`, on the synthetic policy (not a live agent).
