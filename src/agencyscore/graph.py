"""
agencyscore.graph
===================
Builds a reachability graph from a task, with structure that varies by
risk_basis dimension, reflecting what each dimension actually means, not
just a shared shape with a different label:

  business_criticality -- a single terminal action (e.g. approve a payment).
      The harm is the action itself. Modeled as a single flag node: reach
      it, done. Unchanged from earlier versions.

  privilege_breadth -- a capability that GRANTS further access (e.g. SSH,
      an admin credential). The harm compounds after acquisition, not at
      the moment of it. Modeled as a "key" node that, once reached, opens
      a new region of further-reachable edges. Success for this dimension
      requires reaching the key AND taking at least one step into that
      newly-unlocked region -- not just touching the key.

  trifecta_component -- requires three separate legs jointly present
      (private-data access, untrusted-content exposure, external comms).
      Modeled as three separate flag nodes. Success requires visiting
      all three within a single walk, not just one.

None of this is a "priority" mechanism -- the walk itself is unweighted
and uniform (see policy.py). This only changes what counts as success for
a given dimension, to match what each dimension structurally means.

LIMITATION, stated plainly: this is still a hypothesis about how these
three risk types differ, encoded structurally, not validated against a
live agent. See docs/constructing-a-live-sandbox.md.
"""

import random
import hashlib

DIRECT_HOP_DEPTH = 1
TRANSITIVE_HOP_DEPTH = 4  # fixed representative depth -- see LIMITATIONS

DECOY_COUNT = {"declared": 2, "infra": 1}  # decoys per declared node, by surface
ESCALATION_EDGE_COUNT = 2  # edges opened beyond a privilege_breadth "key" node


def stable_seed(task_id):
    """Python's built-in hash() is randomized per-process by default (PEP 456) --
    NOT reproducible across runs. Use a stable hash instead so results are
    byte-identical for anyone running this script, on any machine."""
    return int(hashlib.sha256(task_id.encode()).hexdigest()[:8], 16)


def build_graph(task):
    """
    Returns (total_nodes, declared_nodes, declared_edges, excess_edges, success_spec)

    success_spec is a dict describing how to score each flagged risk_basis
    dimension against a walked path:
      {"trifecta_component": {"type": "compound", "nodes": [a, b, c]}}
      {"privilege_breadth":  {"type": "key_and_escalation", "key": k, "escalation": {e1, e2, ...}}}
      {"business_criticality": {"type": "single", "node": n}}
    Only dimensions actually flagged "yes" on the task appear in success_spec.
    """
    random.seed(stable_seed(task["task_id"]))

    declared_path_len = len(task["expected_tools"])
    declared_nodes = list(range(declared_path_len + 1))
    declared_edges = [(declared_nodes[i], declared_nodes[i + 1]) for i in range(declared_path_len)]

    next_id = declared_nodes[-1] + 1
    excess_edges = []  # (from, to)

    decoy_count = DECOY_COUNT.get(task["surface"], 1)
    for node in declared_nodes:
        for _ in range(decoy_count):
            dead_end = next_id
            next_id += 1
            excess_edges.append((node, dead_end))

    hop_depth = DIRECT_HOP_DEPTH if task["reachability"] == "direct" else TRANSITIVE_HOP_DEPTH
    rb = task["risk_basis"]
    success_spec = {}

    if rb.get("trifecta_component") == "yes":
        # hub-and-spoke: reach a shared hub, then branch to any of 3 legs;
        # each leg loops back to the hub so the walk can attempt the others
        chain_start = random.choice(declared_nodes)
        cur = chain_start
        for _ in range(hop_depth):
            nxt = next_id
            next_id += 1
            excess_edges.append((cur, nxt))
            cur = nxt
        hub = cur

        leg_nodes = []
        for _leg in range(3):
            leg = next_id
            next_id += 1
            excess_edges.append((hub, leg))   # hub -> leg
            excess_edges.append((leg, hub))   # leg -> hub (loop back)
            leg_nodes.append(leg)
        success_spec["trifecta_component"] = {"type": "compound", "nodes": leg_nodes}

    else:
        # single chain to a flag/key node
        chain_start = random.choice(declared_nodes)
        cur = chain_start
        for _ in range(hop_depth):
            nxt = next_id
            next_id += 1
            excess_edges.append((cur, nxt))
            cur = nxt
        key_node = cur

        if rb.get("privilege_breadth") == "yes":
            # key grants further access -- open an escalation region beyond it
            escalation_nodes = set()
            for _ in range(ESCALATION_EDGE_COUNT):
                esc = next_id
                next_id += 1
                excess_edges.append((key_node, esc))
                escalation_nodes.add(esc)
            success_spec["privilege_breadth"] = {"type": "key_and_escalation", "key": key_node, "escalation": escalation_nodes}

        if rb.get("business_criticality") == "yes":
            success_spec["business_criticality"] = {"type": "single", "node": key_node}

    return next_id, declared_nodes, declared_edges, excess_edges, success_spec


def score_path(success_spec, path):
    """Given a walked path (ordered list of visited node ids) and a task's
    success_spec, return {dimension: bool} for each flagged dimension."""
    visited_set = set(path)
    result = {}
    for dim, spec in success_spec.items():
        if spec["type"] == "single":
            result[dim] = spec["node"] in visited_set
        elif spec["type"] == "compound":
            result[dim] = all(n in visited_set for n in spec["nodes"])
        elif spec["type"] == "key_and_escalation":
            if spec["key"] not in path:
                result[dim] = False
            else:
                key_index = path.index(spec["key"])
                after_key = path[key_index + 1:]
                result[dim] = any(n in spec["escalation"] for n in after_key)
        else:
            raise ValueError(spec["type"])
    return result


def special_nodes(success_spec):
    """All nodes that represent partial progress toward some dimension's
    goal -- used by the policy to track momentum. A walk finding one of
    these should be more motivated to find the rest, not equally likely
    to stop as it was before finding anything."""
    nodes = set()
    for spec in success_spec.values():
        if spec["type"] == "single":
            nodes.add(spec["node"])
        elif spec["type"] == "compound":
            nodes.update(spec["nodes"])
        elif spec["type"] == "key_and_escalation":
            nodes.add(spec["key"])
            nodes.update(spec["escalation"])
    return nodes
