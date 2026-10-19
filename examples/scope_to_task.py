#!/usr/bin/env python3
"""
examples/scope_to_task.py
===========================
Thin wrapper so the translator runs without installing the package:

    python examples/scope_to_task.py examples/agents/coding-agent-github.json \\
        --scope-data ../scope-mcp/data --list-candidates

See docs/scope-to-task.md.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from agencyscore.scope_to_task import main

if __name__ == "__main__":
    sys.exit(main())
