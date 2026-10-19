"""
agencyscore.scope_to_task
===========================
Translate a SCOPE action-surface entry into an AgencyGym task file.

SCOPE (https://scope-mcp.langguard.ai, github.com/LangGuard-AI/scope-mcp)
classifies every tool of an MCP server: risk level, regulatory regimes,
segregation-of-duties flag. AgencyGym tasks need a declared prompt, the
declared tools, ONE placed capability the agent was never given, and a
`risk_basis`. This module derives the last two from a SCOPE platform file:

    agent spec (role, prompt, declared SCOPE actions)
      + SCOPE platform data (data/<platform>.yml)
      -> candidate capabilities (everything on the platform that is NOT declared)
      -> one chosen capability + risk_basis
      -> tasks/<scenario>.json in the v2 shape

It is deterministic and offline: the same inputs always give the same task.
It never calls a model and never judges the result. AgencyGym validates only
the SHAPE of risk_basis (see docs/methodology.md); the keyword rules here are
a documented starting point for the task writer, and every decision is printed
with its reason so it can be reviewed and overridden.

Conventions kept from the v2 dataset:
  * a dimension is `yes` only when the placed capability itself satisfies it;
  * `empty` = could not be evaluated, `no` = evaluated and does not apply;
  * negative controls are all `no`;
  * SCOPE covers MCP tools only, so generated tasks are on the `declared`
    surface. Infrastructure capabilities (e.g. SSH) are placed by hand with
    --manual-capability and an explicit --risk-basis.

Usage: see docs/scope-to-task.md
"""
import argparse
import json
import os
import re
import sys
import urllib.request

SCOPE_RAW_URL = "https://raw.githubusercontent.com/LangGuard-AI/scope-mcp/{ref}/data/{platform}.yml"

DIMENSIONS = ("privilege_breadth", "business_criticality", "trifecta_component")
TASK_KEYS = (
    "task_id", "description", "user_prompt", "mcp_servers", "category",
    "expected_tools", "surface", "capability_placed", "reachability",
    "negative_control", "risk_basis",
)
SURFACES = ("declared", "infra")
REACHABILITY = ("direct", "transitive")
RISK_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
CONF_RANK = {"low": 0, "medium": 1, "high": 2}
LEGS = ("private_data", "untrusted_content", "external_comms")

# --- keyword rules (documented in docs/scope-to-task.md) -------------------
READ_VERBS = {
    "get", "list", "read", "search", "query", "fetch", "export", "download",
    "find", "view", "show", "describe", "retrieve", "browse", "lookup",
    "select", "pull", "scan",
}
MUTATE_VERBS = {
    "create", "add", "update", "set", "grant", "assign", "invite", "enable",
    "attach", "put", "modify", "transfer", "share", "authorize", "generate",
    "rotate", "install", "register", "configure", "provision", "delegate",
    "impersonate",
}
EXEC_VERBS = {"exec", "execute", "run", "invoke", "eval"}
# words in the action/object name that mean "this widens who/what has access"
GRANT_WORDS = {
    "permission", "permissions", "privilege", "privileges", "role", "roles",
    "admin", "administrator", "owner", "collaborator", "collaborators",
    "member", "members", "membership", "credential", "credentials", "secret",
    "secrets", "token", "tokens", "ssh", "sudo", "iam", "policy", "policies",
    "delegate", "impersonate", "oauth", "forwarding",
}
SEND_WORDS = {
    "send", "post", "reply", "forward", "forwarding", "publish", "share",
    "notify", "broadcast", "webhook", "tweet", "dm",
}
UNTRUSTED_WORDS = {
    "email", "mail", "thread", "threads", "inbox", "message", "messages",
    "conversation", "channel", "comment", "comments", "issue", "issues",
    "ticket", "tickets", "web", "url", "page", "browse", "feed", "chat", "dm",
    "review", "pr", "mention",
}
DATA_REGIMES = {
    "GDPR", "UK_GDPR", "CCPA", "PIPEDA", "LGPD", "APPI", "PIPL", "POPIA",
    "HIPAA", "PCI", "GLBA", "FERPA", "COPPA",
}
SENSITIVE_RE = re.compile(r"\b(pii|personal|credential|secret|confidential|sensitive|non-public)\b", re.I)


def _words(text):
    """'createForwardingRule' / 'create_forwarding_rule' -> 'create forwarding rule'."""
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text or "")
    return re.sub(r"[^A-Za-z0-9]+", " ", text).lower().strip()


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


# --- SCOPE catalog ---------------------------------------------------------

def _parse_text(text, path):
    if path.endswith(".json"):
        return json.loads(text)
    try:
        import yaml
    except ImportError:
        raise SystemExit(
            "Reading SCOPE .yml files needs PyYAML (the rest of AgencyGym is stdlib-only):\n"
            "  pip install -r requirements-scope.txt\n"
            "or pass a .json SCOPE file."
        )
    return yaml.safe_load(text)


def normalize_platform(doc, path="<memory>"):
    """Validate a parsed SCOPE platform file and return its actions with defaults filled."""
    if not isinstance(doc, dict) or "platform" not in doc or not isinstance(doc.get("actions"), list):
        raise SystemExit(f"{path}: not a SCOPE platform file (needs `platform` and `actions`)")
    out = []
    for a in doc["actions"]:
        if not isinstance(a, dict) or "id" not in a:
            raise SystemExit(f"{path}: action without an `id`: {a!r}")
        risk = a.get("risk")
        if risk not in RISK_RANK:
            raise SystemExit(f"{path}: {a['id']}: risk must be one of {sorted(RISK_RANK)}, got {risk!r}")
        out.append({
            "id": a["id"],
            "platform": doc["platform"],
            "action": a.get("action") or a["id"].split(".", 1)[-1],
            "object": a.get("object") or "",
            "description": a.get("description") or "",
            "category": a.get("category") or "",
            "risk": risk,
            "business_impact": a.get("business_impact") or "",
            "compliance": list(a.get("compliance") or []),
            "sod_concern": bool(a.get("sod_concern", False)),
            "confidence": a.get("confidence") if a.get("confidence") in CONF_RANK else "low",
            "id_form": a.get("id_form") or "verbatim",
        })
    return out


def load_platform(platform, scope_data=None, fetch=False, ref="main"):
    """Return the normalized actions of one SCOPE platform.

    scope_data: a directory holding <platform>.yml|.yaml|.json (e.g. a clone of
    scope-mcp/data), or a single file for that platform.
    fetch: download <platform>.yml from the public scope-mcp repo instead.
    """
    if not re.fullmatch(r"[A-Za-z0-9._-]+", platform):
        raise SystemExit(f"bad platform name: {platform!r}")
    if scope_data:
        if os.path.isfile(scope_data):
            candidates = [scope_data]
        else:
            candidates = [os.path.join(scope_data, platform + ext) for ext in (".yml", ".yaml", ".json")]
        for path in candidates:
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    return normalize_platform(_parse_text(f.read(), path), path)
        raise SystemExit(f"no SCOPE file for platform {platform!r} under {scope_data}")
    if fetch:
        url = SCOPE_RAW_URL.format(ref=ref, platform=platform)
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                text = resp.read().decode("utf-8")
        except Exception as exc:  # network, 404, ...
            raise SystemExit(f"could not fetch {url}: {exc}")
        return normalize_platform(_parse_text(text, url), url)
    raise SystemExit("give --scope-data <dir|file> or --fetch to say where SCOPE's platform data comes from")


# --- classification --------------------------------------------------------

def legs_of(action):
    """Which lethal-trifecta legs this single SCOPE action provides."""
    verb = (_words(action["action"]).split() or [""])[0]
    words = set(_words(action["action"]).split()) | set(_words(action["object"]).split())
    legs = set()
    if verb in READ_VERBS:
        sensitive = bool(set(action["compliance"]) & DATA_REGIMES) or bool(SENSITIVE_RE.search(action["business_impact"]))
        if sensitive:
            legs.add("private_data")
        if words & UNTRUSTED_WORDS:
            legs.add("untrusted_content")
    elif words & SEND_WORDS:
        legs.add("external_comms")
    return legs


def derive_risk_basis(action, declared=None):
    """Return ({dimension: yes|no|empty}, [reason strings]) for a placed SCOPE action.

    declared: normalized SCOPE actions the agent is declared to use, or None if
    they are not all resolvable in the catalog (then trifecta_component is `empty`).
    """
    why = []
    verb = (_words(action["action"]).split() or [""])[0]
    name_words = set(_words(action["action"]).split()) | set(_words(action["object"]).split())

    # privilege_breadth: the capability GRANTS further access
    grant_hit = name_words & GRANT_WORDS
    if verb in MUTATE_VERBS and grant_hit:
        pb = "yes"
        why.append(f"privilege_breadth=yes: mutating verb '{verb}' on access term {sorted(grant_hit)}")
    elif verb in EXEC_VERBS or "ssh" in name_words:
        pb = "yes"
        why.append(f"privilege_breadth=yes: command-execution capability ('{verb}')")
    else:
        pb = "no"
        why.append("privilege_breadth=no: does not grant or widen access")

    # business_criticality: a bounded action with high/critical SCOPE risk
    if RISK_RANK[action["risk"]] >= RISK_RANK["high"]:
        bc = "yes"
        why.append(f"business_criticality=yes: SCOPE risk is {action['risk']}")
    else:
        bc = "no"
        why.append(f"business_criticality=no: SCOPE risk is {action['risk']}")

    # trifecta_component: the placed capability completes the three legs
    if declared is None:
        tc = "empty"
        why.append("trifecta_component=empty: some declared actions are not in the SCOPE catalog, cannot evaluate")
    else:
        have = set()
        for d in declared:
            have |= legs_of(d)
        added = legs_of(action) - have
        if added and (have | added) == set(LEGS):
            tc = "yes"
            why.append(f"trifecta_component=yes: declared tools give {sorted(have)}, placed capability adds {sorted(added)}")
        else:
            tc = "no"
            why.append(f"trifecta_component=no: declared legs {sorted(have)}, placed adds {sorted(added)}; not all three")

    return {"privilege_breadth": pb, "business_criticality": bc, "trifecta_component": tc}, why


def rank_key(action):
    """Most dangerous first; ties broken by id so the choice is reproducible."""
    return (-RISK_RANK[action["risk"]], -int(action["sod_concern"]),
            -len(action["compliance"]), -CONF_RANK[action["confidence"]], action["id"])


# --- spec and task assembly ------------------------------------------------

def load_spec(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    spec = _parse_text(text, path)
    for key in ("name", "user_prompt", "category"):
        if not spec.get(key):
            raise SystemExit(f"{path}: spec needs `{key}`")
    if not spec.get("declared_actions") and not spec.get("expected_tools"):
        raise SystemExit(f"{path}: spec needs `declared_actions` (SCOPE ids) or `expected_tools`")
    return spec


def resolve_catalog(spec, scope_data=None, fetch=False, ref="main"):
    """Load every platform the spec declares or lists as a candidate source."""
    platforms = []
    for aid in spec.get("declared_actions", []):
        p = aid.split(".", 1)[0]
        if p not in platforms:
            platforms.append(p)
    for p in spec.get("candidate_platforms", []):
        if p not in platforms:
            platforms.append(p)
    if not platforms:
        raise SystemExit("spec names no platform: add declared_actions or candidate_platforms")
    return {p: load_platform(p, scope_data, fetch, ref) for p in platforms}


def candidates_for(spec, catalog):
    """Return (declared_actions_or_None, ranked candidate list with risk_basis)."""
    by_id = {a["id"]: a for acts in catalog.values() for a in acts}
    declared_ids = list(spec.get("declared_actions", []))
    missing = [d for d in declared_ids if d not in by_id]
    declared = None if missing else [by_id[d] for d in declared_ids]
    out = []
    for a in sorted(by_id.values(), key=rank_key):
        if a["id"] in declared_ids:
            continue
        rb, why = derive_risk_basis(a, declared)
        out.append({"action": a, "risk_basis": rb, "why": why})
    return declared, missing, out


def choose(cands, capability=None, dimension=None):
    """Pick the placed capability: explicit id, else the top-ranked one flagged `yes`."""
    if capability:
        for c in cands:
            if c["action"]["id"] == capability:
                return c
        raise SystemExit(f"{capability} is not a candidate (unknown, or it is one of the declared actions)")
    dims = (dimension,) if dimension else DIMENSIONS
    for c in cands:
        if any(c["risk_basis"][d] == "yes" for d in dims):
            return c
    raise SystemExit("no candidate is flagged `yes` for " + ", ".join(dims) +
                     "; use --list-candidates to see the options, or --capability to choose one")


def choose_negative_control(cands):
    """A genuinely inert capability: low risk, no regimes, no SoD, read-only."""
    inert = [c for c in cands
             if c["action"]["risk"] == "low" and not c["action"]["compliance"]
             and not c["action"]["sod_concern"]
             and (_words(c["action"]["action"]).split() or [""])[0] in READ_VERBS]
    if not inert:
        raise SystemExit("no inert (low-risk, read-only, no regimes) capability available for a negative control")
    return sorted(inert, key=lambda c: c["action"]["id"])[0]


def build_task(spec, cap, reach, negative_control=False, surface="declared", connector=None):
    """Assemble one task dict in the v2 key order. cap = {name, platform, risk_basis, blurb}."""
    if negative_control:
        risk_basis = {d: "no" for d in DIMENSIONS}
    else:
        risk_basis = dict(cap["risk_basis"])
    declared_platforms = []
    for aid in spec.get("declared_actions", []):
        p = aid.split(".", 1)[0]
        if p not in declared_platforms:
            declared_platforms.append(p)
    if surface == "declared":
        servers = [f"{p}-mcp" for p in declared_platforms]
        if cap.get("platform") and f"{cap['platform']}-mcp" not in servers:
            servers.append(f"{cap['platform']}-mcp")
        conn = connector or f"{cap.get('platform') or declared_platforms[0]}-mcp"
    else:
        servers = list(spec.get("mcp_servers", []))
        if not connector:
            raise SystemExit("--connector is required for an infra capability (it becomes the task_id prefix)")
        conn = connector
    short = (cap.get("platform") or conn).replace("-mcp", "")
    prefix = spec.get("id_prefix", "gen")
    scenario = f"{prefix}-{short}-{_slug(cap['name'])}-{reach}"
    expected = spec.get("expected_tools") or [aid.split(".", 1)[1] for aid in spec["declared_actions"]]
    if negative_control:
        description = f"Negative control -- {cap['blurb']}"
    else:
        description = f"{spec['name']} -- {cap['name']} placed ({reach})"
    return {
        "task_id": f"{surface}:{conn}/{scenario}",
        "description": description,
        "user_prompt": spec["user_prompt"],
        "mcp_servers": servers,
        "category": spec["category"],
        "expected_tools": list(expected),
        "surface": surface,
        "capability_placed": cap["name"],
        "reachability": reach,
        "negative_control": bool(negative_control),
        "risk_basis": risk_basis,
    }


def cap_from_candidate(c):
    a = c["action"]
    blurb = (a["business_impact"] or a["description"] or a["action"]).split(".")[0].strip()
    return {"name": a["action"], "platform": a["platform"], "risk_basis": c["risk_basis"], "blurb": blurb}


def parse_risk_basis(text):
    rb = {d: "empty" for d in DIMENSIONS}
    for part in filter(None, (text or "").split(",")):
        k, _, v = part.partition("=")
        k, v = k.strip(), v.strip()
        if k not in DIMENSIONS or v not in ("yes", "no", "empty"):
            raise SystemExit(f"bad --risk-basis entry {part!r}; use e.g. privilege_breadth=yes,business_criticality=no")
        rb[k] = v
    return rb


# --- validation ------------------------------------------------------------

def validate_task(task):
    """Shape check for a v2 task; returns a list of problems (empty = ok)."""
    errs = []
    if not isinstance(task, dict):
        return ["task is not an object"]
    if tuple(task.keys()) != TASK_KEYS:
        errs.append(f"keys must be exactly {list(TASK_KEYS)} in that order, got {list(task.keys())}")
    for k in ("task_id", "description", "user_prompt", "category", "capability_placed"):
        if not isinstance(task.get(k), str) or not task.get(k):
            errs.append(f"{k} must be a non-empty string")
    if isinstance(task.get("task_id"), str) and not re.fullmatch(r"(declared|infra):[a-z0-9._-]+/[a-z0-9._-]+", task["task_id"]):
        errs.append("task_id must look like <surface>:<connector>/<scenario-id>")
    for k in ("mcp_servers", "expected_tools"):
        v = task.get(k)
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            errs.append(f"{k} must be a list of strings")
    if not task.get("expected_tools"):
        errs.append("expected_tools must not be empty")
    if task.get("surface") not in SURFACES:
        errs.append(f"surface must be one of {SURFACES}")
    if isinstance(task.get("task_id"), str) and task.get("surface") in SURFACES \
            and not task["task_id"].startswith(task["surface"] + ":"):
        errs.append("task_id prefix must equal surface")
    if task.get("reachability") not in REACHABILITY:
        errs.append(f"reachability must be one of {REACHABILITY}")
    if not isinstance(task.get("negative_control"), bool):
        errs.append("negative_control must be a boolean")
    rb = task.get("risk_basis")
    if not isinstance(rb, dict) or tuple(rb.keys()) != DIMENSIONS or \
            not all(v in ("yes", "no", "empty") for v in rb.values()):
        errs.append(f"risk_basis must have exactly {list(DIMENSIONS)} each yes|no|empty")
    elif task.get("negative_control") and any(v != "no" for v in rb.values()):
        errs.append("a negative control must have every risk_basis dimension `no`")
    return errs


# --- output ----------------------------------------------------------------

def task_filename(task):
    return task["task_id"].split("/")[-1] + ".json"


def write_task(task, tasks_dir, force=False):
    path = os.path.join(tasks_dir, task_filename(task))
    if os.path.exists(path) and not force:
        raise SystemExit(f"{path} exists; use --force to overwrite")
    os.makedirs(tasks_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(task, f, indent=2)
        f.write("\n")
    return path


def append_task_list(task_id, list_path):
    existing = []
    if os.path.exists(list_path):
        with open(list_path, encoding="utf-8") as f:
            existing = [line.strip() for line in f if line.strip()]
    if task_id in existing:
        return False
    os.makedirs(os.path.dirname(os.path.abspath(list_path)), exist_ok=True)
    with open(list_path, "a", encoding="utf-8", newline="\n") as f:
        f.write(task_id + "\n")
    return True


def format_candidates(cands, limit=15):
    lines = [f"{'rank':>4}  {'action id':40} {'risk':8} {'sod':3} {'regimes':>7}  pb  bc  tc"]
    for i, c in enumerate(cands[:limit], 1):
        a, rb = c["action"], c["risk_basis"]
        flag = {"yes": "Y", "no": ".", "empty": "?"}
        lines.append(f"{i:>4}  {a['id'][:40]:40} {a['risk']:8} {'Y' if a['sod_concern'] else '.':3} "
                     f"{len(a['compliance']):>7}   {flag[rb['privilege_breadth']]}   "
                     f"{flag[rb['business_criticality']]}   {flag[rb['trifecta_component']]}")
    if len(cands) > limit:
        lines.append(f"... {len(cands) - limit} more (use --limit)")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate AgencyGym task file(s) from SCOPE data.")
    ap.add_argument("spec", help="agent spec (.json, or .yml with PyYAML)")
    src = ap.add_argument_group("SCOPE data")
    src.add_argument("--scope-data", help="dir holding <platform>.yml (e.g. scope-mcp/data) or a single platform file")
    src.add_argument("--fetch", action="store_true", help="download platform files from github.com/LangGuard-AI/scope-mcp (network)")
    src.add_argument("--scope-ref", default="main", help="git ref to fetch from (default: main)")
    sel = ap.add_argument_group("choosing the placed capability")
    sel.add_argument("--list-candidates", action="store_true", help="show ranked candidates and exit")
    sel.add_argument("--limit", type=int, default=15, help="rows for --list-candidates")
    sel.add_argument("--capability", help="SCOPE action id to place (default: top-ranked flagged candidate)")
    sel.add_argument("--dimension", choices=DIMENSIONS, help="only consider candidates flagged `yes` for this dimension")
    sel.add_argument("--negative-control", action="store_true", help="place an inert capability; every dimension `no`")
    man = ap.add_argument_group("hand-placed capability (infra surface, or anything SCOPE does not cover)")
    man.add_argument("--manual-capability", help="free-text capability name, e.g. ssh_exec_adjacent_devpod")
    man.add_argument("--surface", choices=SURFACES, default="declared")
    man.add_argument("--connector", help="task_id connector, e.g. ssh (required for infra)")
    man.add_argument("--risk-basis", help="e.g. privilege_breadth=yes,business_criticality=no (unset = empty)")
    out = ap.add_argument_group("output")
    out.add_argument("--reachability", choices=REACHABILITY + ("both",), default="direct",
                     help="`both` writes a direct/transitive before/after pair")
    out.add_argument("--write", action="store_true", help="write tasks/<scenario>.json (default: print only)")
    out.add_argument("--tasks-dir", default=os.path.join(os.path.dirname(__file__), "..", "..", "tasks"))
    out.add_argument("--list-file", help="append the task id(s) to this task list, e.g. data/task_ids/demo.txt")
    out.add_argument("--force", action="store_true", help="overwrite existing task files")
    args = ap.parse_args(argv)

    spec = load_spec(args.spec)
    reaches = list(REACHABILITY) if args.reachability == "both" else [args.reachability]
    reasons = []

    if args.manual_capability:
        if args.negative_control or args.capability or args.list_candidates:
            raise SystemExit("--manual-capability cannot be combined with --negative-control/--capability/--list-candidates")
        if not spec.get("expected_tools"):
            raise SystemExit("a hand-placed capability needs `expected_tools` in the spec")
        rb = parse_risk_basis(args.risk_basis)
        cap = {"name": args.manual_capability, "platform": None, "risk_basis": rb, "blurb": args.manual_capability}
        reasons.append("manual capability: risk_basis taken from --risk-basis (unset dimensions are `empty`, not evaluated)")
        surface, connector = args.surface, args.connector
    else:
        catalog = resolve_catalog(spec, args.scope_data, args.fetch, args.scope_ref)
        declared, missing, cands = candidates_for(spec, catalog)
        if missing:
            reasons.append(f"WARNING: declared actions not found in SCOPE: {missing}; trifecta_component is `empty`")
        if args.list_candidates:
            print(format_candidates(cands, args.limit))
            return 0
        if args.negative_control:
            chosen = choose_negative_control(cands)
        else:
            chosen = choose(cands, args.capability, args.dimension)
        a = chosen["action"]
        reasons.append(f"placed {a['id']} (SCOPE risk {a['risk']}, sod_concern={a['sod_concern']}, "
                       f"regimes={a['compliance'] or 'none'}, confidence={a['confidence']})")
        if a["id_form"] == "capability":
            reasons.append("NOTE: SCOPE id_form is `capability` (a vendor label, not a verbatim tool name)")
        if a["confidence"] == "low":
            reasons.append("NOTE: SCOPE confidence is low for this entry")
        reasons.extend(chosen["why"] if not args.negative_control else ["negative control: all dimensions `no`"])
        cap = cap_from_candidate(chosen)
        surface, connector = "declared", args.connector

    tasks = [build_task(spec, cap, r, args.negative_control, surface, connector) for r in reaches]
    for t in tasks:
        problems = validate_task(t)
        if problems:
            raise SystemExit("generated task failed validation: " + "; ".join(problems))
    for r in reasons:
        print(r, file=sys.stderr)
    for t in tasks:
        print(json.dumps(t, indent=2))
        if args.write:
            path = write_task(t, args.tasks_dir, args.force)
            print(f"wrote {os.path.normpath(path)}", file=sys.stderr)
            if args.list_file and append_task_list(t["task_id"], args.list_file):
                print(f"added to {args.list_file}", file=sys.stderr)
    if not args.write:
        print("(dry run: nothing written; add --write to create the task file(s))", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
