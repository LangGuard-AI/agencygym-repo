# Constructing a Live Sandbox

**Status: work in progress. This is a design document, not a build. Nothing described here exists yet.**

Current results (see `results/v2/summary.md`) run on a simulation sandbox — a constructed graph and a synthetic policy, not a real agent or real infrastructure. This document lays out what a live sandbox would actually require, category by category, so the gap between "simulated" and "real" is concrete rather than hand-waved.

## What a live sandbox needs, on top of the task dataset

1. **Genuine isolation.** No real credentials, no real production system reachable even if the placed capability is reached — the same principle ExploitGym holds to. A live sandbox that could actually leak into production would defeat its own purpose.
2. **A real agent, really wired.** Real tool-calling against the relevant connector, not a simulated graph walk.
3. **Full tool-call logging**, replacing the simulated graph-walk logic with an actual record of what the agent called and in what order — this is what `agencyscore.evaluate` would score against, in place of the simulated flag-node check.
4. **A teardown and reset cycle** between runs, so one run's state can't contaminate the next.

## Per-category difficulty

| Category | What's required | Difficulty |
|---|---|---|
| **Cloud Infrastructure** (AWS/GCP/Azure) | A disposable cloud account or scoped sub-project, real IAM roles, real S3/log resources, deliberately configured so the placed capability is genuinely reachable. Buildable with Terraform/CloudFormation — stand up per-task, tear down after. | **Easiest.** Cloud providers are built for exactly this kind of disposable, scripted environment. |
| **Data-store** (Postgres/Snowflake/MongoDB) | Containerized Postgres/MongoDB (trivial via Docker) seeded with synthetic data. Snowflake has a free trial tier. | **Easy**, similarly scriptable. |
| **Dev/Endpoint** (SSH/GitHub/GitLab) | SSH needs two real containers or instances sharing a network so "adjacent devpod" is a genuine, physical relationship, not a fiction. GitHub/GitLab need real disposable repos with real scoped tokens — GitLab CE self-hosted gives full control; GitHub needs a throwaway org and repos. | **Moderate.** More moving parts, nothing exotic. |
| **Financial** (NetSuite/SAP/QuickBooks) | Each platform's own sandbox tier (NetSuite has one; SAP has trial/demo systems; QuickBooks has a sandbox company API), seeded with fake GL entries, invoices, vendors resembling a real declared task. | **Harder.** Not built for disposable automated testing the way cloud platforms are — provisioning and seeding realistic data takes real manual setup per platform. |
| **Communications** (Gmail/Slack/Teams) | A Google Workspace test domain, Slack's free sandbox workspace tier, a Microsoft 365 developer tenant (Microsoft provides these free, specifically for this kind of testing). | **Moderate**, mostly account provisioning work. |

## The cost problem this creates

The simulation sandbox runs 300 episodes per task for free, in seconds. A live sandbox does not have that luxury: 300 runs per task, times 100 tasks, with a real LLM agent making real API calls, is expensive and slow in both money and wall-clock time.

This is exactly why `results/LIMITATIONS.md` already flags N=300 as picked arbitrarily, not from a power calculation. A live-agent version will almost certainly need:
- A much smaller N per task
- A real power calculation to justify whatever N gets chosen, rather than reusing the free-simulation number by default

## Recommended next step: a pilot, not the full 100

Building live sandbox infrastructure for all 100 tasks across 5 categories at once is a multi-month effort on its own, not a quick follow-up to the simulation work. The recommended path is a **pilot scope**, not the full build:

- **One category**: Cloud Infrastructure, since it's the easiest to stand up (disposable cloud accounts, scriptable teardown)
- **A handful of tasks** within that category, not all of them
- **A real agent**, wired to a real (disposable) AWS environment
- **A small N**, chosen deliberately rather than defaulted to 300

If the pilot validates the measurement approach at small scale, expand category by category, roughly in the difficulty order above (Cloud → Data-store → Dev/Endpoint → Communications → Financial), rather than attempting all five simultaneously.

## Open questions, not yet answered

- How does tool-call logging map cleanly onto `expected_tools` / `capability_placed` when a real agent's tool names may not match our synthetic task schema exactly?
- What's the actual teardown cost per run, and does it change the pilot's feasible N?
- Does a real agent's behavior even resemble the 12%-curiosity synthetic policy closely enough for the simulation results to be a meaningful prior, or does the live pilot need to start from scratch on that question too?
