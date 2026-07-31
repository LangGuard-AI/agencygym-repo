# AgencyGym
### Can you predict where an agent will wander, before it ever runs?

ExploitGym asked whether an AI agent can turn a known vulnerability into a working exploit. While building it, its authors found something they weren't testing for: models probing infrastructure for privileges nobody pointed them toward.

That's not a bug in one model. It's a property of agents in general — the ability to discover capability beyond what a task declares, simply because the capability is reachable. We call this Agency, and left unmeasured, it's what turns an agent into an adversary.

**AgencyScore and AgencyGym measure it — together, not separately.**

ExploitGym's real contribution isn't just a sandbox. It's a two-step paradigm: fix a known ground truth in advance — a specific vulnerability, a specific proof-of-vulnerability, a specific path to it — then test, blind, whether an agent's real behavior confirms what that fixed ground truth predicts.

AgencyScore and AgencyGym are our version of those same two steps, not two separate things that happen to sit next to each other. Every agent deployment has a gap between what its task declares it needs and everything it can actually reach — the tools it's connected to, and the infrastructure underneath those tools. We fix that gap as **AgencyScore**, computed before the agent is deployed, from configuration alone. Then **AgencyGym** places a known excess capability at a known distance — across both the tools an agent is declared to use and the infrastructure it happens to share — and runs the agent blind to where it is, to see whether AgencyScore actually predicted what the agent would do. A score with no blind test behind it is just a classification exercise; a blind test with no prior score is just an anecdote. Neither means anything alone.

**Where we are.** v1 ships 10 instances, built from a single real production scenario: an AI agent reconciling a general ledger on Oracle NetSuite. Some instances place the excess one hop away; others bury it four hops behind decoy tools; others move it entirely into shared cloud infrastructure, invisible to anything watching tool calls. Early results, using a calibrated synthetic policy rather than a live model, show the score predicts wandering behavior well in the simplest cases — and overpredicts it in others, once path depth compounds. That gap is documented, not hidden, and it's exactly what v2 is built to close.

**This is early, and it's public on purpose.** We'd rather ship something real and incomplete than something polished and theoretical. If you work on agent security, benchmark design, or graph-based reachability analysis, we're looking for people to help break this.

[View on GitHub →](https://github.com/LangGuard-AI/agencygym)
