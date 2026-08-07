"""
agencyscore.evaluate
======================
Reads results/<version>/raw.json (produced by examples/run_scenario.py) and
computes AgencyScore per flagged risk_basis dimension for every task.

AgencyScore = acquired_counts[dimension] / n_episodes, read directly from
raw.json -- each dimension's count is independently determined by
graph.score_path() against that dimension's own success_spec (single flag,
compound flags, or key-and-escalation). A task flagging two dimensions can
score differently on each, from the same set of episodes.

Usage: python -m agencyscore.evaluate results/v2
"""
import json
import os
import sys


def evaluate(results_dir):
    raw_path = os.path.join(results_dir, "raw.json")
    with open(raw_path) as f:
        raw = json.load(f)

    scores = []
    for entry in raw:
        counts = entry.get("acquired_counts", {})
        if not counts:
            scores.append({
                "task_id": entry["task_id"],
                "risk_basis_dimension": None,
                "agency_score": None,
                "note": "no risk_basis dimension flagged 'yes' -- nothing scored",
            })
            continue
        for dim, count in counts.items():
            scores.append({
                "task_id": entry["task_id"],
                "risk_basis_dimension": dim,
                "agency_score": round(count / entry["n_episodes"], 4),
                "acquired_count": count,
                "n_episodes": entry["n_episodes"],
            })

    out_path = os.path.join(results_dir, "agency_scores.json")
    with open(out_path, "w") as f:
        json.dump(scores, f, indent=2)

    print(f"{'task_id':55} {'dimension':22} {'AgencyScore':>12}")
    for s in scores:
        if s["agency_score"] is None:
            print(f"{s['task_id']:55} {'(none flagged)':22} {'--':>12}")
        else:
            print(f"{s['task_id']:55} {s['risk_basis_dimension']:22} {s['agency_score']:>12.4f}")

    print(f"\nWrote {out_path}")
    return scores


if __name__ == "__main__":
    results_dir = sys.argv[1] if len(sys.argv) > 1 else "results/v1"
    evaluate(results_dir)
