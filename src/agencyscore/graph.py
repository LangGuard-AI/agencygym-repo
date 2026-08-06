"""
agencyscore.graph
===================
Builds a reachability graph from a task: a declared path from `expected_tools`,
plus one placed capability (`capability_placed`) at a location implied by
`reachability` ("direct" or "transitive").

No scoring formula lives here. AgencyScore is computed entirely from sandbox
runs (see agencyscore.evaluate) -- this module only builds the graph the
policy walks.

LIMITATION, stated plainly: "transitive" is a single fixed internal depth
(TRANSITIVE_HOP_DEPTH), not a range. Our own earlier synthetic runs showed
3-hop and 4-hop transitive cases behave differently from each other (0.3%
vs 0% capture) -- collapsing them to one binary label loses that distinction.
Named on the Roadmap as an open question, not hidden here.

Decoy count (how many harmless dead-end edges surround the declared path)
is a fixed simulation parameter, not a per-task field -- it describes how
noisy the simulation is, not a property of the task itself.
"""

import random
import hashlib

DIRECT_HOP_DEPTH = 1
TRANSITIVE_HOP_DEPTH = 4  # fixed representative depth -- see LIMITATIONS

DECOY_COUNT = {"declared": 2, "infra": 1}  # decoys per declared node, by surface


def stable_seed(task_id):
    """Python's built-in hash() is randomized per-process by default (PEP 456) --
    NOT reproducible across runs. Use a stable hash instead so results are
    byte-identical for anyone running this script, on any machine."""
    return int(hashlib.sha256(task_id.encode()).hexdigest()[:8], 16)


def build_graph(task):
    """
    Returns (total_nodes, declared_nodes, declared_edges, excess_edges, flag_node)
    """
    random.seed(stable_seed(task["task_id"]))

    declared_path_len = len(task["expected_tools"])
    declared_nodes = list(range(declared_path_len + 1))
    declared_edges = [(declared_nodes[i], declared_nodes[i + 1]) for i in range(declared_path_len)]

    next_id = declared_nodes[-1] + 1
    excess_edges = []  # (from, to) -- no risk weighting; that lived in the dropped formula

    decoy_count = DECOY_COUNT.get(task["surface"], 1)
    for node in declared_nodes:
        for _ in range(decoy_count):
            dead_end = next_id
            next_id += 1
            excess_edges.append((node, dead_end))

    hop_depth = DIRECT_HOP_DEPTH if task["reachability"] == "direct" else TRANSITIVE_HOP_DEPTH
    chain_start = random.choice(declared_nodes)
    cur = chain_start
    for _ in range(hop_depth):
        nxt = next_id
        next_id += 1
        excess_edges.append((cur, nxt))
        cur = nxt
    flag_node = cur

    return next_id, declared_nodes, declared_edges, excess_edges, flag_node
