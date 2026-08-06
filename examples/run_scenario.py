#!/usr/bin/env python3
"""
examples/run_scenario.py
==========================
Loads every task in data/task_ids/v1.txt, builds its graph, runs the
synthetic policy N times, and writes results/v1/raw.json.

LIMITATION: the policy is a calibrated synthetic stand-in for a live LLM
agent, not a live model. See results/LIMITATIONS.md.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from agencyscore import graph, policy

TASKS_DIR = os.path.join(os.path.dirname(__file__), "..", "tasks")
TASK_LIST = os.path.join(os.path.dirname(__file__), "..", "data", "task_ids", "v1.txt")


def results_dir_for(task_list_path):
    version = os.path.splitext(os.path.basename(task_list_path))[0]  # "v1" or "v2"
    return os.path.join(os.path.dirname(__file__), "..", "results", version)


def load_task(task_id):
    slug = task_id.split("/")[-1]
    path = os.path.join(TASKS_DIR, f"{slug}.json")
    with open(path) as f:
        return json.load(f)


def main(task_list_path=TASK_LIST, n_runs=300):
    with open(task_list_path) as f:
        task_ids = [line.strip() for line in f if line.strip()]

    results = []
    for task_id in task_ids:
        task = load_task(task_id)
        total_nodes, declared_nodes, declared_edges, excess_edges, flag_node = graph.build_graph(task)
        sandbox = policy.run_task(
            total_nodes, declared_edges, excess_edges, flag_node,
            n_episodes=n_runs, seed=graph.stable_seed(task["task_id"]) + 1
        )
        results.append({
            "task_id": task["task_id"],
            "surface": task["surface"],
            "capability_placed": task["capability_placed"],
            "reachability": task["reachability"],
            "negative_control": task["negative_control"],
            "risk_basis": task["risk_basis"],
            "n_episodes": sandbox["n_episodes"],
            "acquired_count": sandbox["acquired_count"],
        })

    os.makedirs(results_dir_for(task_list_path), exist_ok=True)
    out_path = os.path.join(results_dir_for(task_list_path), "raw.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"{'task_id':55} {'surface':9} {'reach':11} {'acquired/N':>12}")
    for r in results:
        frac = f"{r['acquired_count']}/{r['n_episodes']}"
        print(f"{r['task_id']:55} {r['surface']:9} {r['reachability']:11} {frac:>12}")

    print(f"\nWrote {out_path}")
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("task_list", nargs="?", default=TASK_LIST)
    parser.add_argument("--runs", type=int, default=300)
    args = parser.parse_args()
    main(task_list_path=args.task_list, n_runs=args.runs)
