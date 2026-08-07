"""
agencyscore.policy
====================
Synthetic stochastic policy standing in for a live LLM agent. Calibrated to
a documented real behavior pattern (models try cheap/available actions even
off-task) -- NOT a live foundation model. See results/LIMITATIONS.md.

MOMENTUM MODEL (current):
The walk's decision to continue exploring off-path is not a flat, memoryless
probability. It increases each time the walk finds a node representing
partial progress toward some dimension's goal (see graph.special_nodes) --
the hypothesis being that finding one piece of a multi-part goal increases
an agent's motivation to find the rest, not leaves it unchanged. This
replaces an earlier uniform model, which made compound (multi-node) goals
like trifecta_component mathematically undetectable at any reasonable
sample size -- not rare, actually undetectable, because every off-path step
had no declared-path fallback and used the same flat probability whether
the walk had found nothing yet or had already found two of three required
pieces.

BASE_CURIOSITY governs the initial decision to leave the declared path.
Once off-path, continuation probability = BASE_CURIOSITY + MOMENTUM_PER_FOUND
per special node already visited, capped at MAX_CONTINUE.

These three constants are chosen to test the hypothesis, not derived from
data or validated against a live agent. See results/LIMITATIONS.md.
"""

import random

BASE_CURIOSITY = 0.12
MOMENTUM_PER_FOUND = 0.30
MAX_CONTINUE = 0.90
MAX_STEPS = 60


def run_episode(total_nodes, declared_edges, excess_edges, special_node_set):
    """Returns the ordered list of node ids visited, starting at node 0."""
    adjacency = {n: [] for n in range(total_nodes)}
    for (a, b) in declared_edges:
        adjacency[a].append(("declared", b))
    for (a, b) in excess_edges:
        adjacency[a].append(("excess", b))

    cur = 0
    path = [cur]
    off_path = False
    found = set()

    for _ in range(MAX_STEPS):
        options = adjacency.get(cur, [])
        if not options:
            break
        declared_opts = [o for o in options if o[0] == "declared"]
        excess_opts = [o for o in options if o[0] == "excess"]

        if off_path:
            p_continue = min(MAX_CONTINUE, BASE_CURIOSITY + MOMENTUM_PER_FOUND * len(found))
            take_excess = bool(excess_opts) and (random.random() < p_continue)
        else:
            take_excess = bool(excess_opts) and (random.random() < BASE_CURIOSITY)

        if take_excess:
            _, nxt = random.choice(excess_opts)
            off_path = True
        else:
            if not declared_opts:
                break
            _, nxt = random.choice(declared_opts)

        cur = nxt
        path.append(cur)
        if cur in special_node_set:
            found.add(cur)

    return path


def run_task(total_nodes, declared_edges, excess_edges, success_spec, n_episodes=300, seed=None):
    """Runs n_episodes, scores each against success_spec, returns per-dimension
    acquired counts: {dimension: count_of_episodes_that_succeeded}."""
    if seed is not None:
        random.seed(seed)

    from .graph import score_path, special_nodes
    special = special_nodes(success_spec)

    counts = {dim: 0 for dim in success_spec}
    for _ in range(n_episodes):
        path = run_episode(total_nodes, declared_edges, excess_edges, special)
        result = score_path(success_spec, path)
        for dim, success in result.items():
            if success:
                counts[dim] += 1

    return {
        "n_episodes": n_episodes,
        "acquired_counts": counts,
    }
