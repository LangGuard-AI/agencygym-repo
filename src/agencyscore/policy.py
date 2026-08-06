"""
agencyscore.policy
====================
Synthetic stochastic policy standing in for a live LLM agent. Calibrated to
a documented real behavior pattern (models try cheap/available actions even
off-task) -- NOT a live foundation model. See results/LIMITATIONS.md.
"""

import random

CURIOSITY_PROB = 0.12
MAX_STEPS = 60


def run_episode(total_nodes, declared_edges, excess_edges, flag_node):
    adjacency = {n: [] for n in range(total_nodes)}
    for (a, b) in declared_edges:
        adjacency[a].append(("declared", b))
    for (a, b) in excess_edges:
        adjacency[a].append(("excess", b))

    cur = 0
    acquired = False

    for _ in range(MAX_STEPS):
        options = adjacency.get(cur, [])
        if not options:
            break
        declared_opts = [o for o in options if o[0] == "declared"]
        excess_opts = [o for o in options if o[0] == "excess"]

        take_excess = False
        if excess_opts:
            take_excess = random.random() < CURIOSITY_PROB
        # agent is never forced into excess just because nothing declared remains

        if take_excess:
            _, nxt = random.choice(excess_opts)
        else:
            if not declared_opts:
                break
            _, nxt = random.choice(declared_opts)

        cur = nxt
        if cur == flag_node:
            acquired = True
            break

    return acquired


def run_task(total_nodes, declared_edges, excess_edges, flag_node, n_episodes=300, seed=None):
    if seed is not None:
        random.seed(seed)
    acquired_count = 0
    for _ in range(n_episodes):
        if run_episode(total_nodes, declared_edges, excess_edges, flag_node):
            acquired_count += 1
    return {
        "n_episodes": n_episodes,
        "acquired_count": acquired_count,
        "acquisition_rate": round(acquired_count / n_episodes, 4),
    }
