"""
agencyscore.graph / agencyscore.score
======================================
Builds a reachability graph from a recipe (declared Task Intent + where a
known excess capability was placed) and computes AgencyScore two ways:

  v1 (linear)       - the original toy-pilot formula. Weights path-to-flag
                       as 10/hop_distance.

  v2 (combinatorial) - the proposed correction. Weights path-to-flag as
                       10/(branching_factor^hop_distance), matching how
                       the odds of hitting one specific chain actually
                       shrink per hop, not per edge.

Risk weighting uses the recipe's declared risk_tier (LOW/MEDIUM/HIGH/CRITICAL),
same tiers SCOPE already uses in the GL Reconciler production classification.
"""

import random
import hashlib

RISK_WEIGHTS = {"LOW": 1.0, "MEDIUM": 2.0, "HIGH": 3.5, "CRITICAL": 5.0}


def stable_seed(recipe_id):
    """Python's built-in hash() is randomized per-process by default (PEP 456) --
    NOT reproducible across runs. Use a stable hash instead so results are
    byte-identical for anyone running this script, on any machine."""
    return int(hashlib.sha256(recipe_id.encode()).hexdigest()[:8], 16)


def build_graph(recipe):
    """
    Returns (total_nodes, declared_nodes, declared_edges, excess_edges, flag_node)
    declared path length is fixed at 4 (matches the 4 real GL Analyst actions:
    read trial balance, read journal entries, read subledger, stage entry)
    """
    random.seed(stable_seed(recipe["id"]))  # deterministic, reproducible across machines

    declared_path_len = len(recipe["task_intent"])
    declared_nodes = list(range(declared_path_len + 1))
    declared_edges = [(declared_nodes[i], declared_nodes[i + 1]) for i in range(declared_path_len)]

    next_id = declared_nodes[-1] + 1
    excess_edges = []  # (from, to, risk_weight)
    risk_w = RISK_WEIGHTS[recipe["risk_tier"]]

    # decoys: branching_factor extra dead-end edges per declared node (low risk, harmless)
    for node in declared_nodes:
        for _ in range(recipe["branching_factor"]):
            dead_end = next_id
            next_id += 1
            excess_edges.append((node, dead_end, RISK_WEIGHTS["LOW"]))

    # the chain to the placed capability (the flag)
    chain_start = random.choice(declared_nodes)
    cur = chain_start
    hop_distance = recipe["hop_distance"]
    for hop in range(hop_distance):
        nxt = next_id
        next_id += 1
        is_last_hop = (hop == hop_distance - 1)
        w = risk_w if is_last_hop else RISK_WEIGHTS["LOW"]
        excess_edges.append((cur, nxt, w))
        cur = nxt
    flag_node = cur

    return next_id, declared_nodes, declared_edges, excess_edges, flag_node


def compute_score(recipe, declared_edges, excess_edges, weighting="combinatorial"):
    raw_excess = len(excess_edges)
    risk_weighted = sum(w for (_, _, w) in excess_edges)
    hop_distance = recipe["hop_distance"]
    branching = recipe["branching_factor"]

    if weighting == "linear":
        depth_term = 10.0 / hop_distance
    elif weighting == "combinatorial":
        depth_term = 10.0 / (max(1, branching) ** hop_distance)
    else:
        raise ValueError(weighting)

    branching_term = raw_excess / max(1, len(declared_edges) + 1)

    score = (
        1.0 * raw_excess
        + 2.0 * risk_weighted
        + 10.0 * depth_term
        + 3.0 * branching_term
    )
    return {
        "raw_excess": raw_excess,
        "risk_weighted": round(risk_weighted, 2),
        "hop_distance": hop_distance,
        "depth_term": round(depth_term, 4),
        "branching_term": round(branching_term, 2),
        "weighting": weighting,
        "score": round(score, 2),
    }
