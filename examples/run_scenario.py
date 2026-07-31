#!/usr/bin/env python3
"""
examples/run_scenario.py
==========================
Loads every recipe in recipes/, computes AgencyScore (both linear and
combinatorial depth-weighting), runs the synthetic policy 300x per recipe,
and reports whether each scoring version predicts observed behavior.

LIMITATION: the policy is a calibrated synthetic stand-in for a live LLM
agent, not a live model. See results/LIMITATIONS.md.
"""
import json
import glob
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from agencyscore import graph, policy

RECIPE_DIR = os.path.join(os.path.dirname(__file__), "..", "recipes")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results", "v1")


def pearson(xs, ys):
    n = len(xs)
    mx, my = statistics.mean(xs), statistics.mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = (sum((x - mx) ** 2 for x in xs)) ** 0.5
    sy = (sum((y - my) ** 2 for y in ys)) ** 0.5
    if sx == 0 or sy == 0:
        return float("nan")
    return cov / (sx * sy)


def main(n_runs=300):
    recipe_files = sorted(glob.glob(os.path.join(RECIPE_DIR, "*.json")))
    results = []

    for path in recipe_files:
        with open(path) as f:
            recipe = json.load(f)

        total_nodes, declared_nodes, declared_edges, excess_edges, flag_node = graph.build_graph(recipe)

        score_linear = graph.compute_score(recipe, declared_edges, excess_edges, weighting="linear")
        score_combo = graph.compute_score(recipe, declared_edges, excess_edges, weighting="combinatorial")

        sandbox = policy.run_recipe(
            total_nodes, declared_nodes, declared_edges, excess_edges, flag_node,
            n_episodes=n_runs, seed=graph.stable_seed(recipe["id"]) + 1  # offset from graph-build seed
        )

        results.append({
            "id": recipe["id"],
            "surface": recipe["surface"],
            "capability": recipe["capability_placed"],
            "hop_distance": recipe["hop_distance"],
            "risk_tier": recipe["risk_tier"],
            "negative_control": recipe["negative_control"],
            "score_linear": score_linear["score"],
            "score_combinatorial": score_combo["score"],
            "off_path_rate": sandbox["off_path_rate"],
            "flag_capture_rate": sandbox["flag_capture_rate"],
        })

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "raw.json"), "w") as f:
        json.dump(results, f, indent=2)

    # correlations
    linear_scores = [r["score_linear"] for r in results]
    combo_scores = [r["score_combinatorial"] for r in results]
    off_path = [r["off_path_rate"] for r in results]
    capture = [r["flag_capture_rate"] for r in results]

    corr = {
        "linear_vs_offpath": round(pearson(linear_scores, off_path), 3),
        "linear_vs_capture": round(pearson(linear_scores, capture), 3),
        "combinatorial_vs_offpath": round(pearson(combo_scores, off_path), 3),
        "combinatorial_vs_capture": round(pearson(combo_scores, capture), 3),
    }

    print(f"{'id':50} {'surface':9} {'hop':4} {'lin':>7} {'combo':>7} {'offpath%':>9} {'capture%':>9}")
    for r in results:
        print(f"{r['id']:50} {r['surface']:9} {r['hop_distance']:4} "
              f"{r['score_linear']:7.2f} {r['score_combinatorial']:7.2f} "
              f"{r['off_path_rate']*100:8.1f}% {r['flag_capture_rate']*100:8.1f}%")

    print()
    print(f"n = {len(results)} instances, {n_runs} runs each")
    print(f"Linear weighting        -> off-path r={corr['linear_vs_offpath']}, capture r={corr['linear_vs_capture']}")
    print(f"Combinatorial weighting -> off-path r={corr['combinatorial_vs_offpath']}, capture r={corr['combinatorial_vs_capture']}")

    with open(os.path.join(RESULTS_DIR, "correlations.json"), "w") as f:
        json.dump(corr, f, indent=2)

    return results, corr


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    main(n_runs=n)
