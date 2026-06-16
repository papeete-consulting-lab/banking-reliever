#!/usr/bin/env python3
"""c4_export.py — render the product business-capability tree as
Structurizr DSL files.

Reads upstream BCM via `kpack` only — never touches /bcm/, /adr/,
/func-adr/, /tech-adr/, /tech-vision/, /domain-vision/, /business-vision/
on disk. The implementation overlay is taken from `sources/<CAP>/{backend,
stub,bff,frontend}/` in the working tree.

Outputs:

    docs/c4/
        enterprise/
            workspace.dsl          one System Landscape view, every L2
                                   as a container, grouped by zone
            zone-<ZONE>.dsl        per-zone view, every L2 in that zone
                                   as a container, with cross-cap event flows
        <CAP_L2>/
            workspace.dsl          per-L2 detail — implementation artifacts
                                   (backend / stub / BFF / frontend) as
                                   containers, DDD elements (aggregates,
                                   read-models, business-event publishers)
                                   as components. ADR refs as properties.

All cross-capability flows are drawn from BUSINESS event subscriptions
only — the business-layer items of the `consumed_events` / `emitted_events`
slices and `paired_business_event:` entries of the capability's bus model
(logical artifact `process/<CAP>/bus.yaml`, now consumed via `kpack process`).
The resource-event layer (RVT.*) is intentionally hidden as it is an
implementation detail of the bus rail.

The DDD process model (aggregates, read-models, policies, bus topology) is
authored by the `/process` skill in the **product knowledge repo** and
consumed here **read-only** via `kpack process <CAP_ID>` — exactly like
the BCM corpus via `kpack pack`. It does not live in this repo.

The product capability-map context (`<PRODUCT_CTX>`) and the GitHub blob base
URLs are NOT hardcoded: the context comes from the C4_PRODUCT_CTX env var (or
the repo's `.kpack.yaml` / governance contexts registry), and the ADR / source
blob URLs come from the C4_KNOWLEDGE_BLOB / C4_SOURCE_BLOB env vars.

Run from the repo root:

    python3 .claude/skills/c4-export/c4_export.py            # everything
    python3 .claude/skills/c4-export/c4_export.py --cap <PRODUCT_CTX>.CAP.BSP.001.SCO
    python3 .claude/skills/c4-export/c4_export.py --enterprise-only
    python3 .claude/skills/c4-export/c4_export.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS_C4 = REPO_ROOT / "docs" / "c4"
SOURCES_DIR = REPO_ROOT / "sources"

# The product capability-map context kpack selects on. Resolved from the
# C4_PRODUCT_CTX env var (set from the repo's .kpack.yaml / governance contexts
# registry) — never hardcoded to a specific enterprise/product.
PRODUCT_CTX = os.environ.get("C4_PRODUCT_CTX", "").strip() or "<PRODUCT_CTX>"

# GitHub blob base URLs. The knowledge blob points at the product knowledge
# repo (ADR links); the source blob points at this implementation repo
# (sources/ links). Both come from the contexts registry via env vars rather
# than being hardcoded to a specific GitHub org/repo.
BANKING_KNOWLEDGE_BLOB = (
    os.environ.get("C4_KNOWLEDGE_BLOB", "").strip()
    or "<PRODUCT_KNOWLEDGE_REPO_URL>/blob/main"
)
BANKING_BLOB = (
    os.environ.get("C4_SOURCE_BLOB", "").strip() or "<THIS_REPO_URL>/blob/main"
)

# Human-readable product name shown as the root software-system label in the
# enterprise C4 view. Resolved from C4_PRODUCT_NAME (or the contexts registry)
# — never hardcoded to a specific product.
PRODUCT_NAME = os.environ.get("C4_PRODUCT_NAME", "").strip() or "The Product"

# Zone abbreviation used to name per-zone Structurizr files (zone-<abbrev>.dsl)
# and the OTel `zone` resource tag — NOT the on-disk layout, which is uniformly
# sources/<CAP_ID>/{backend,stub,bff,frontend}/ regardless of zone.
ZONE_ABBREV = {
    "BUSINESS_SERVICE_PRODUCTION": "bsp",
    "SUPPORT": "sup",
    "REFERENTIAL": "ref",
    "CHANNEL": "chn",
    "EXCHANGE_B2B": "b2b",
    "DATA_ANALYTICS": "dat",
    "STEERING": "str",
}


# ─────────────────────────────────────────────────────────────────────
# kpack invocation
# ─────────────────────────────────────────────────────────────────────


def run_bcm_pack(*args: str) -> str:
    """Invoke `kpack` and return stdout. The first '[kpack] fetching ...'
    log line on stdout is stripped — only the JSON / TSV payload is returned."""
    cmd = ["kpack", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        print(f"!! kpack {' '.join(args)} failed:", file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        sys.exit(proc.returncode)
    # kpack prints "[kpack] fetching ..." on stdout before the payload.
    lines = proc.stdout.splitlines()
    payload = "\n".join(line for line in lines if not line.startswith("[kpack]"))
    return payload


def list_capabilities() -> list[dict]:
    """Return every capability kpack knows about. Each entry has
    id / level / zone / name."""
    raw = run_bcm_pack("list", "--context", PRODUCT_CTX)
    out: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"\s+", line, maxsplit=3)
        if len(parts) < 4:
            continue
        cap_id, level, zone, name = parts
        out.append(
            {"id": cap_id, "level": level.strip(), "zone": zone.strip(), "name": name}
        )
    return out


def pack_capability(cap_id: str) -> dict:
    """Return the kpack --deep --compact payload for one capability."""
    raw = run_bcm_pack("pack", cap_id, "--deep", "--compact")
    return json.loads(raw)


# Cache of fetched process-model envelopes so we hit the CLI once per cap.
_PROCESS_CACHE: dict[str, dict | None] = {}


def fetch_process_model(cap_id: str) -> dict | None:
    """Fetch one capability's DDD process model via `kpack process
    <cap_id> --compact` and return the parsed JSON envelope.

    The process model lives in the product knowledge repo and is served
    read-only by the CLI — exactly like the BCM corpus via `kpack pack`.
    Returns None (treated everywhere as "no process model") when:
      - kpack is not installed / not on PATH,
      - the CLI exits non-zero (e.g. exit 3 = no model for this id),
      - the payload is not valid JSON.
    """
    if cap_id in _PROCESS_CACHE:
        return _PROCESS_CACHE[cap_id]
    try:
        proc = subprocess.run(
            ["kpack", "process", cap_id, "--compact"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        print("!! kpack not found on PATH — treating as no process model",
              file=sys.stderr)
        _PROCESS_CACHE[cap_id] = None
        return None
    if proc.returncode != 0:
        _PROCESS_CACHE[cap_id] = None
        return None
    lines = proc.stdout.splitlines()
    payload = "\n".join(line for line in lines if not line.startswith("[kpack]"))
    try:
        env = json.loads(payload)
    except json.JSONDecodeError:
        print(f"!! kpack process {cap_id} returned non-JSON output",
              file=sys.stderr)
        _PROCESS_CACHE[cap_id] = None
        return None
    _PROCESS_CACHE[cap_id] = env
    return env


def process_model_text(env: dict | None, stem: str) -> str:
    """Return the raw YAML text of one process-model file from the envelope.

    `_scan_yaml_ids` text-scans, so we hand it `.model.<stem>.raw`, which is
    present whether or not `.parsed` is null (commands.yaml / read-models.yaml
    frequently fail strict YAML on `{path: /x/{id}}` flow mappings)."""
    if not env:
        return ""
    entry = (env.get("model") or {}).get(stem) or {}
    return entry.get("raw") or ""


# ─────────────────────────────────────────────────────────────────────
# Implementation overlay (filesystem-driven)
# ─────────────────────────────────────────────────────────────────────


@dataclass
class ImplStatus:
    has_mode_a: bool = False     # sources/<CAP>/backend/
    has_stub: bool = False       # sources/<CAP>/stub/
    has_frontend: bool = False   # sources/<CAP>/frontend/
    has_bff: bool = False        # sources/<CAP>/bff/
    has_process: bool = False    # kpack process <CAP> resolves (exit 0)

    @property
    def label(self) -> str:
        """Single-word status label suitable for a tag."""
        if self.has_mode_a:
            return "mode-a"
        if self.has_stub:
            return "stub"
        if self.has_bff or self.has_frontend:
            return "channel-impl"
        return "not-scaffolded"


def detect_impl(cap_id: str, zone: str) -> ImplStatus:
    s = ImplStatus()
    cap_dir = SOURCES_DIR / cap_id
    if (cap_dir / "backend").is_dir():
        s.has_mode_a = True
    if (cap_dir / "stub").is_dir():
        s.has_stub = True
    if (cap_dir / "frontend").is_dir():
        s.has_frontend = True
    if (cap_dir / "bff").is_dir():
        s.has_bff = True

    # has_process is True iff `kpack process <cap_id>` resolves (exit 0).
    s.has_process = fetch_process_model(cap_id) is not None
    return s


# ─────────────────────────────────────────────────────────────────────
# DDD components, mined from the `kpack process` model (logical
# process/<CAP>/ artifacts) when present
# ─────────────────────────────────────────────────────────────────────


@dataclass
class DddComponents:
    aggregates: list[str] = field(default_factory=list)
    read_models: list[str] = field(default_factory=list)
    policies: list[str] = field(default_factory=list)
    publishers: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (
            self.aggregates or self.read_models or self.policies or self.publishers
        )


_YAML_ID_RE = re.compile(r"^\s*-\s*id:\s*([A-Z][A-Z0-9._-]+)\s*$")


def _scan_yaml_ids(text: str, prefixes: tuple[str, ...]) -> list[str]:
    """Lightweight YAML scan — collect every `- id: X` entry whose value
    starts with one of `prefixes`. Avoids a pyyaml dependency AND filters
    out nested invariant / open-question IDs (which sit under each
    aggregate entry but use a different prefix).

    Operates on raw YAML TEXT (the `.model.<stem>.raw` string from the
    `kpack process` envelope) so it works whether or not `.parsed` is
    null for that file."""
    if not text:
        return []
    out = []
    for line in text.splitlines():
        m = _YAML_ID_RE.match(line)
        if m and m.group(1).startswith(prefixes):
            out.append(m.group(1))
    return out


def mine_ddd(cap_id: str) -> DddComponents:
    env = fetch_process_model(cap_id)
    if env is None:
        return DddComponents()
    out = DddComponents()
    out.aggregates = _scan_yaml_ids(
        process_model_text(env, "aggregates"), ("AGG.",)
    )
    out.read_models = _scan_yaml_ids(
        process_model_text(env, "read-models"), ("PRJ.", "QRY.")
    )
    out.policies = _scan_yaml_ids(
        process_model_text(env, "policies"), ("POL.",)
    )
    bus_text = process_model_text(env, "bus")
    if bus_text:
        # One publisher concept per published business event. Pull from
        # `paired_business_event:` (under each routing key) or a top-level
        # `business_event:` form — never from resource events (RVT.*).
        seen: set[str] = set()
        for line in bus_text.splitlines():
            m = re.match(
                # Business-event IDs carry an optional source-context prefix
                # (e.g. <PRODUCT_CTX>.EVT.…) since the CLI v2.0.0 namespacing.
                r"\s*(?:paired_business_event|business_event):\s*"
                r"((?:[A-Z]{2,}\.[A-Z]{2,}\.)?EVT\.[A-Z0-9._-]+)",
                line,
            )
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                out.publishers.append(m.group(1))
    return out


# ─────────────────────────────────────────────────────────────────────
# ADR URLs — derived from the `files` slice of kpack pack output
# ─────────────────────────────────────────────────────────────────────


def adr_urls(pack: dict, adr_ids: list[str]) -> list[tuple[str, str]]:
    """For every ADR id we are asked about, find a matching file path in
    the pack's `files` slice and return (adr_id, github_url) pairs.

    Falls back to a None URL if no file path can be matched — caller decides
    whether to emit anyway."""
    files = pack.get("files", []) or []
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for adr_id in adr_ids:
        if adr_id in seen:
            continue
        seen.add(adr_id)
        match = next(
            (
                f["path"]
                for f in files
                if adr_id in f.get("path", "")
            ),
            None,
        )
        if match:
            out.append((adr_id, f"{BANKING_KNOWLEDGE_BLOB}/{match}"))
    return out


# ─────────────────────────────────────────────────────────────────────
# Structurizr DSL helpers
# ─────────────────────────────────────────────────────────────────────


_IDENT_SCRUB = re.compile(r"[^A-Za-z0-9_]")


def dsl_id(raw: str) -> str:
    """Turn an arbitrary string into a Structurizr-safe identifier."""
    s = _IDENT_SCRUB.sub("_", raw).strip("_")
    if not s:
        s = "x"
    if s[0].isdigit():
        s = "_" + s
    return s


def dsl_str(s: str | None) -> str:
    """Quote a Structurizr string literal — escape backslashes and double
    quotes, collapse newlines."""
    if s is None:
        return "\"\""
    s = s.replace("\\", "\\\\").replace("\"", "\\\"")
    s = re.sub(r"\s+", " ", s).strip()
    return f"\"{s}\""


def display_label(raw_id: str) -> str:
    """Strip the namespace prefix of a dotted process/BCM ID and turn
    underscores into spaces. Examples:

        EVT.BSP.001.TIER_UPGRADED → "TIER UPGRADED"
        AGG.BSP.001.TIER_MANAGEMENT → "TIER MANAGEMENT"
        POL.BSP.001.AUTO_DEMOTE → "AUTO DEMOTE"
        SUB.BUSINESS.BSP.001.005 → "005"
    """
    if not raw_id:
        return raw_id
    last = raw_id.rsplit(".", 1)[-1]
    return last.replace("_", " ")


def zone_display(zone: str) -> str:
    """Pretty-print a zone code: BUSINESS_SERVICE_PRODUCTION → 'Business Service Production'."""
    if not zone:
        return zone
    return " ".join(w.capitalize() for w in zone.split("_"))


# ─────────────────────────────────────────────────────────────────────
# Per-L2 DSL emission
# ─────────────────────────────────────────────────────────────────────


_STYLES_BLOCK = """\
        styles {
            element "capability-self" {
                background "#1168bd"
                color "#ffffff"
                shape RoundedBox
            }
            element "external-capability" {
                background "#999999"
                color "#ffffff"
                shape RoundedBox
            }
            element "implemented:mode-a" {
                background "#2e7d32"
                color "#ffffff"
            }
            element "implemented:stub" {
                background "#fbc02d"
                color "#000000"
            }
            element "implemented:bff" {
                background "#0288d1"
                color "#ffffff"
            }
            element "implemented:frontend" {
                background "#7b1fa2"
                color "#ffffff"
            }
            element "not-scaffolded" {
                background "#bdbdbd"
                color "#000000"
                border Dashed
            }
            element "ddd:aggregate" {
                background "#ffd54f"
                color "#000000"
                shape Hexagon
            }
            element "ddd:read-model" {
                background "#a5d6a7"
                color "#000000"
                shape Cylinder
            }
            element "ddd:policy" {
                background "#ce93d8"
                color "#000000"
            }
            element "ddd:publisher" {
                background "#ffab91"
                color "#000000"
                shape Pipe
            }
            element "zone:BSP" {
                background "#e8eaf6"
            }
            element "zone:SUP" {
                background "#fce4ec"
            }
            element "zone:REF" {
                background "#f1f8e9"
            }
            element "zone:CHN" {
                background "#e0f7fa"
            }
            element "zone:CHANNEL" {
                background "#e0f7fa"
            }
            element "zone:B2B" {
                background "#fff8e1"
            }
            element "zone:DAT" {
                background "#ede7f6"
            }
            element "zone:STR" {
                background "#efebe9"
            }
            element "level:L1" {
                strokeWidth 4
            }
            element "level:L2" {
                strokeWidth 2
            }
            relationship "upstream-event" {
                dashed true
                color "#ff7043"
            }
            relationship "downstream-event" {
                dashed true
                color "#42a5f5"
            }
        }"""


def emit_l2_workspace(
    cap_id: str, pack: dict, cap_names: dict[str, str] | None = None
) -> str:
    self_slice = (pack.get("slices", {}).get("capability_self") or [{}])[0]
    name = self_slice.get("name", cap_id)
    parent = self_slice.get("parent")
    zone = self_slice.get("zoning", "")
    description = self_slice.get("description", "").strip()
    owner = self_slice.get("owner", "")

    slices = pack.get("slices", {})
    tactical = (slices.get("tactical_stack") or [{}])[0]
    stack_tags = tactical.get("tags", []) or []
    tech_stack = "+".join(
        t for t in stack_tags
        if t in {"python", "dotnet", "fastapi", "aspnet", "csharp",
                 "postgresql", "mongodb", "rabbitmq", "kafka"}
    ) or "stack-not-decided"

    domain_class = (
        (slices.get("capability_definition") or [{}])[0]
        .get("domain_classification", {})
        .get("type", "")
    )

    impl = detect_impl(cap_id, zone)
    ddd = mine_ddd(cap_id)

    # Collect ADRs referenced anywhere in the pack.
    referenced: list[str] = []
    referenced.extend(self_slice.get("adrs", []) or [])
    if tactical.get("id"):
        referenced.append(tactical["id"])
    for slice_name in (
        "capability_definition",
        "governing_urba",
        "governing_tech_strat",
        "governance_adrs",
        "domain_vision",
        "tech_vision",
    ):
        for item in slices.get(slice_name, []) or []:
            if item.get("id"):
                referenced.append(item["id"])
    adr_props = adr_urls(pack, referenced)

    # Upstream capabilities (consumed BUSINESS events only — resource
    # subscriptions are an implementation detail of the bus layer and are
    # intentionally hidden from the C4 view).
    upstream: dict[str, dict] = {}
    for sub in slices.get("consumed_events", []) or []:
        if sub.get("layer") != "business":
            continue
        ev = sub.get("subscribed_event", {})
        emitter = ev.get("emitting_capability")
        if not emitter or emitter == cap_id:
            continue
        upstream.setdefault(emitter, {"events": []})
        upstream[emitter]["events"].append(ev.get("id", ""))

    emitted_events = [
        e.get("id")
        for e in slices.get("emitted_events", []) or []
        if e.get("layer") == "business"
    ]

    self_ident = dsl_id(cap_id)

    lines: list[str] = []
    lines.append(f"workspace {dsl_str(f'{name} ({cap_id})')} {dsl_str(description)} {{")
    lines.append("")
    lines.append("    !identifiers hierarchical")
    lines.append("")
    lines.append("    model {")

    # External upstream capabilities (emitters of business events this
    # capability subscribes to).
    names = cap_names or {}
    upstream_idents: dict[str, str] = {}
    for ext_id in sorted(upstream.keys()):
        ident = dsl_id(ext_id)
        upstream_idents[ext_id] = ident
        ext_name = names.get(ext_id) or display_label(ext_id)
        lines.append(
            f"        {ident} = softwareSystem {dsl_str(ext_name)} "
            f"{dsl_str(f'Upstream capability ({ext_id}).')} {{"
        )
        lines.append(f"            tags \"external-capability\"")
        lines.append("            properties {")
        lines.append(
            f"                {dsl_str('capability-id')} {dsl_str(ext_id)}"
        )
        lines.append("            }")
        lines.append("        }")

    # The capability itself, with implementation containers.
    lines.append("")
    self_tags = [
        "capability-self",
        f"level:L2",
        f"zone:{ZONE_ABBREV.get(zone, zone).upper()}",
    ]
    if domain_class:
        self_tags.append(f"domain:{domain_class}")
    lines.append(
        f"        {self_ident} = softwareSystem {dsl_str(name)} "
        f"{dsl_str(description or cap_id)} {{"
    )
    lines.append(f"            tags {' '.join(dsl_str(t) for t in self_tags)}")
    lines.append("            properties {")
    lines.append(f"                {dsl_str('capability-id')} {dsl_str(cap_id)}")
    if parent:
        lines.append(f"                {dsl_str('parent')} {dsl_str(parent)}")
    lines.append(f"                {dsl_str('zoning')} {dsl_str(zone)}")
    if owner:
        lines.append(f"                {dsl_str('owner')} {dsl_str(owner)}")
    lines.append(f"                {dsl_str('tech-stack')} {dsl_str(tech_stack)}")
    lines.append(
        f"                {dsl_str('implementation-status')} {dsl_str(impl.label)}"
    )
    for adr_id, url in adr_props:
        lines.append(f"                {dsl_str('adr:' + adr_id)} {dsl_str(url)}")
    lines.append("            }")

    # Containers — one per implementation artifact (real or placeholder).
    container_idents: list[str] = []

    if impl.has_mode_a:
        loc = f"sources/{cap_id}/backend"
        lines.extend(
            _emit_container(
                "backend",
                "Backend microservice",
                f"{tech_stack} · Mode A",
                ["implemented:mode-a", f"tech:{tech_stack}"],
                {"loc": loc, "github": f"{BANKING_BLOB}/{loc}"},
                ddd,
                indent="            ",
            )
        )
        container_idents.append("backend")
    elif impl.has_stub:
        loc = f"sources/{cap_id}/stub"
        lines.extend(
            _emit_container(
                "stub",
                "Contract stub",
                f"{tech_stack} · Mode B (contract stub)",
                ["implemented:stub", f"tech:{tech_stack}"],
                {"loc": loc, "github": f"{BANKING_BLOB}/{loc}"},
                ddd,
                indent="            ",
            )
        )
        container_idents.append("stub")
    elif not (impl.has_bff or impl.has_frontend):
        # Backend planned but not started — emit a placeholder Container.
        lines.extend(
            _emit_container(
                "backend",
                "Backend (planned)",
                f"{tech_stack} · not scaffolded yet",
                ["not-scaffolded", f"tech:{tech_stack}"],
                {},
                ddd,
                indent="            ",
            )
        )
        container_idents.append("backend")

    if impl.has_bff:
        loc = f"sources/{cap_id}/bff"
        lines.extend(
            _emit_container(
                "bff",
                "Backend-for-Frontend",
                ".NET 10 Minimal API",
                ["implemented:bff", "tech:dotnet"],
                {"loc": loc, "github": f"{BANKING_BLOB}/{loc}"},
                DddComponents(),
                indent="            ",
            )
        )
        container_idents.append("bff")

    if impl.has_frontend:
        loc = f"sources/{cap_id}/frontend"
        lines.extend(
            _emit_container(
                "frontend",
                "Web frontend",
                "vanilla HTML5 / CSS3 / JS",
                ["implemented:frontend", "tech:vanilla-js"],
                {"loc": loc, "github": f"{BANKING_BLOB}/{loc}"},
                DddComponents(),
                indent="            ",
            )
        )
        container_idents.append("frontend")

    lines.append("        }")  # close softwareSystem

    # Relationships from upstream capabilities to this one.
    for ext_id, info in sorted(upstream.items()):
        ext_ident = upstream_idents[ext_id]
        # Pick the first sensible target container (backend / stub / bff).
        target = container_idents[0] if container_idents else None
        target_path = f"{self_ident}.{target}" if target else self_ident
        events_desc = (
            ", ".join(sorted({display_label(e) for e in info["events"] if e}))
            or "business events"
        )
        lines.append("")
        lines.append(
            f"        {ext_ident} -> {target_path} "
            f"{dsl_str(events_desc)} \"Business event subscription\" \"upstream-event\""
        )

    # Outgoing relationships — note emitted business events on the self node
    # via a synthetic "downstream consumers" software system, so the view
    # still shows we publish something.
    if emitted_events:
        cons_ident = f"{self_ident}_downstream_consumers"
        lines.append("")
        lines.append(
            f"        {cons_ident} = softwareSystem "
            f"{dsl_str('Downstream consumers')} "
            f"{dsl_str('Any capability subscribed to the business events emitted by this one.')} {{"
        )
        lines.append("            tags \"external-capability\"")
        lines.append("        }")
        target = container_idents[0] if container_idents else None
        src_path = f"{self_ident}.{target}" if target else self_ident
        events_desc = ", ".join(
            sorted({display_label(e) for e in emitted_events if e})
        )
        lines.append(
            f"        {src_path} -> {cons_ident} "
            f"{dsl_str(events_desc)} \"Business event\" \"downstream-event\""
        )

    lines.append("    }")  # close model
    lines.append("")
    lines.append("    views {")
    lines.append(f"        systemContext {self_ident} \"L2-Context\" {{")
    lines.append("            include *")
    lines.append("            autoLayout lr")
    lines.append("        }")
    lines.append(f"        container {self_ident} \"L2-Containers\" {{")
    lines.append("            include *")
    lines.append("            autoLayout lr")
    lines.append("        }")
    for ident in container_idents:
        if not ddd.is_empty() and ident in {"backend", "stub"}:
            lines.append(
                f"        component {self_ident}.{ident} "
                f"\"L2-Components-{ident}\" {{"
            )
            lines.append("            include *")
            lines.append("            autoLayout lr")
            lines.append("        }")
    lines.append(_STYLES_BLOCK)
    lines.append("    }")  # close views
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def _emit_container(
    ident: str,
    name: str,
    technology: str,
    tags: list[str],
    properties: dict[str, str],
    ddd: DddComponents,
    indent: str,
) -> list[str]:
    # Structurizr DSL signature: container <name> [description] [technology]
    description = name
    out = [
        f"{indent}{ident} = container {dsl_str(name)} "
        f"{dsl_str(description)} {dsl_str(technology)} {{"
    ]
    out.append(f"{indent}    tags {' '.join(dsl_str(t) for t in tags)}")
    if properties:
        out.append(f"{indent}    properties {{")
        for k, v in properties.items():
            out.append(f"{indent}        {dsl_str(k)} {dsl_str(v)}")
        out.append(f"{indent}    }}")

    if ident in {"backend", "stub"} and not ddd.is_empty():
        for agg in ddd.aggregates:
            cid = dsl_id(agg)
            out.append(
                f"{indent}    {cid} = component {dsl_str(display_label(agg))} "
                f"{dsl_str(f'Aggregate (DDD) — {agg}')} {{"
            )
            out.append(f"{indent}        tags \"ddd:aggregate\"")
            out.append(
                f"{indent}        properties {{ {dsl_str('id')} {dsl_str(agg)} }}"
            )
            out.append(f"{indent}    }}")
        for rm in ddd.read_models:
            cid = dsl_id(rm)
            out.append(
                f"{indent}    {cid} = component {dsl_str(display_label(rm))} "
                f"{dsl_str(f'Read model / CQRS — {rm}')} {{"
            )
            out.append(f"{indent}        tags \"ddd:read-model\"")
            out.append(
                f"{indent}        properties {{ {dsl_str('id')} {dsl_str(rm)} }}"
            )
            out.append(f"{indent}    }}")
        for pol in ddd.policies:
            cid = dsl_id(pol)
            out.append(
                f"{indent}    {cid} = component {dsl_str(display_label(pol))} "
                f"{dsl_str(f'Policy / reactive saga — {pol}')} {{"
            )
            out.append(f"{indent}        tags \"ddd:policy\"")
            out.append(
                f"{indent}        properties {{ {dsl_str('id')} {dsl_str(pol)} }}"
            )
            out.append(f"{indent}    }}")
        for pub in ddd.publishers:
            cid = dsl_id(pub)
            out.append(
                f"{indent}    {cid} = component {dsl_str(display_label(pub))} "
                f"{dsl_str(f'Business event publisher — {pub}')} {{"
            )
            out.append(f"{indent}        tags \"ddd:publisher\"")
            out.append(
                f"{indent}        properties {{ {dsl_str('id')} {dsl_str(pub)} }}"
            )
            out.append(f"{indent}    }}")
    out.append(f"{indent}}}")
    return out


# ─────────────────────────────────────────────────────────────────────
# Per-zone DSL emission
# ─────────────────────────────────────────────────────────────────────


def emit_zone_workspace(
    zone: str,
    l2_caps: list[dict],
    packs: dict[str, dict],
    cap_names: dict[str, str] | None = None,
) -> str:
    """One zone = one Software System; each L2 in the zone is a Container.
    Cross-cap flows are wired exclusively from business-event subscriptions
    (resource events are not surfaced at this level)."""
    zabbr = ZONE_ABBREV.get(zone, zone.lower()).upper()
    system_ident = dsl_id(f"zone_{zabbr}")
    zone_label = zone_display(zone)

    lines: list[str] = []
    lines.append(
        f"workspace {dsl_str(f'Zone — {zone_label}')} "
        f"{dsl_str(f'C4 container view of the {zone_label} zone — each L2 capability is a container.')} {{"
    )
    lines.append("")
    lines.append("    !identifiers hierarchical")
    lines.append("")
    lines.append("    model {")
    lines.append(
        f"        {system_ident} = softwareSystem {dsl_str(zone_label)} "
        f"{dsl_str(f'{zone_label} zone of the {PRODUCT_NAME} business capability model.')} {{"
    )
    lines.append(
        f"            tags \"capability-self\" \"zone:{zabbr}\""
    )
    lines.append("            properties {")
    lines.append(f"                {dsl_str('zone-code')} {dsl_str(zone)}")
    lines.append("            }")

    # Each L2 cap = a container.
    cap_idents: dict[str, str] = {}
    for cap in sorted(l2_caps, key=lambda c: c["id"]):
        cap_id = cap["id"]
        ident = dsl_id(cap_id)
        cap_idents[cap_id] = ident
        pack = packs.get(cap_id, {})
        self_slice = (pack.get("slices", {}).get("capability_self") or [{}])[0]
        cap_name = self_slice.get("name") or cap["name"]
        cap_description = (self_slice.get("description") or "").strip() or cap_name
        impl = detect_impl(cap_id, zone)
        tactical_tags = (
            ((pack.get("slices", {}).get("tactical_stack") or [{}])[0]).get("tags", [])
            or []
        )
        tech = "python" if "python" in tactical_tags else (
            "dotnet" if "dotnet" in tactical_tags or "aspnet" in tactical_tags
            else "stack-tbd"
        )
        parent = self_slice.get("parent", "")
        impl_tag = f"implemented:{impl.label}" if impl.label != "not-scaffolded" else "not-scaffolded"
        tags = [impl_tag, f"tech:{tech}", f"parent:{parent}"]
        lines.append(
            f"            {ident} = container {dsl_str(cap_name)} "
            f"{dsl_str(cap_description)} {dsl_str(tech)} {{"
        )
        lines.append(f"                tags {' '.join(dsl_str(t) for t in tags)}")
        lines.append(f"                properties {{")
        lines.append(
            f"                    {dsl_str('capability-id')} {dsl_str(cap_id)}"
        )
        lines.append(
            f"                    {dsl_str('detail-view')} "
            f"{dsl_str(f'../{cap_id}/workspace.dsl')}"
        )
        if parent:
            lines.append(f"                    {dsl_str('parent')} {dsl_str(parent)}")
        lines.append(f"                }}")
        lines.append(f"            }}")

    lines.append("        }")  # close zone softwareSystem

    # External capabilities (emitters in other zones).
    external_caps: dict[str, tuple[str, str]] = {}  # emitter_id -> (ident, name)
    relationships: list[tuple[str, str, str]] = []  # (src, dst, label)

    # Inbound: each cap consumes business events from emitters; if the
    # emitter is in another zone (or another cap in this zone), draw a
    # relationship. Resource subscriptions are intentionally omitted.
    for cap in l2_caps:
        cap_id = cap["id"]
        pack = packs.get(cap_id, {})
        cap_ident = cap_idents[cap_id]
        for sub in pack.get("slices", {}).get("consumed_events", []) or []:
            if sub.get("layer") != "business":
                continue
            ev = sub.get("subscribed_event", {})
            emitter = ev.get("emitting_capability")
            if not emitter or emitter == cap_id:
                continue
            if emitter in cap_idents:
                src_path = f"{system_ident}.{cap_idents[emitter]}"
            else:
                if emitter not in external_caps:
                    ext_name = (cap_names or {}).get(emitter) or display_label(emitter)
                    external_caps[emitter] = (dsl_id(emitter), ext_name)
                src_path = external_caps[emitter][0]
            relationships.append(
                (src_path, f"{system_ident}.{cap_ident}", display_label(ev.get("id", "")))
            )

    for emitter, (ident, ext_name) in external_caps.items():
        lines.append("")
        lines.append(
            f"        {ident} = softwareSystem {dsl_str(ext_name)} "
            f"{dsl_str(f'External capability ({emitter}) — emits business events consumed by this zone.')} {{"
        )
        lines.append("            tags \"external-capability\"")
        lines.append("            properties {")
        lines.append(
            f"                {dsl_str('capability-id')} {dsl_str(emitter)}"
        )
        lines.append("            }")
        lines.append("        }")

    # Deduplicate relationships and merge labels for repeated (src, dst) pairs.
    pair_labels: dict[tuple[str, str], set[str]] = {}
    pair_order: list[tuple[str, str]] = []
    for src, dst, label in relationships:
        key = (src, dst)
        if key not in pair_labels:
            pair_labels[key] = set()
            pair_order.append(key)
        if label:
            pair_labels[key].add(label)
    for src, dst in pair_order:
        label = ", ".join(sorted(pair_labels[(src, dst)])) or "business events"
        lines.append(
            f"        {src} -> {dst} {dsl_str(label)} \"Business event subscription\" \"upstream-event\""
        )

    lines.append("    }")  # close model
    lines.append("")
    lines.append("    views {")
    lines.append(f"        systemContext {system_ident} \"Zone-Context\" {{")
    lines.append("            include *")
    lines.append("            autoLayout lr")
    lines.append("        }")
    lines.append(f"        container {system_ident} \"Zone-Containers\" {{")
    lines.append("            include *")
    lines.append("            autoLayout lr")
    lines.append("        }")
    lines.append(_STYLES_BLOCK)
    lines.append("    }")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────
# Enterprise (L1 product) DSL emission
# ─────────────────────────────────────────────────────────────────────


def emit_enterprise_workspace(
    l2_caps: list[dict], packs: dict[str, dict]
) -> str:
    """One Software Landscape: the product as a system, every zone as a container,
    every L2 as a component."""
    lines: list[str] = []
    lines.append(
        f"workspace {dsl_str(f'{PRODUCT_NAME} — Enterprise C4')} "
        f"{dsl_str('System landscape — every L2 capability grouped by zone.')} {{"
    )
    lines.append("")
    lines.append("    !identifiers hierarchical")
    lines.append("")
    lines.append("    model {")

    # Actors (external).
    lines.append(f"        beneficiary = person \"Beneficiary\" {dsl_str(f'Recipient of the {PRODUCT_NAME} programme.')}")
    lines.append("        prescriber = person \"Prescriber\" \"Social worker or programme prescriber.\"")
    lines.append("        regulator = person \"Regulator\" \"Programme governance, compliance auditor.\"")
    lines.append("        partner_bank = softwareSystem \"Partner bank\" \"Financial institution providing card and payment rails.\" {")
    lines.append("            tags \"external-system\"")
    lines.append("        }")

    product_ident = "product"
    lines.append("")
    lines.append(
        f"        {product_ident} = softwareSystem {dsl_str(PRODUCT_NAME)} "
        f"{dsl_str('Product capability map rendered as a C4 system landscape.')} {{"
    )
    lines.append("            tags \"capability-self\"")

    # Group L2 caps by zone.
    by_zone: dict[str, list[dict]] = {}
    for cap in l2_caps:
        by_zone.setdefault(cap["zone"], []).append(cap)

    zone_idents: dict[str, str] = {}
    cap_idents: dict[str, str] = {}

    for zone in sorted(by_zone.keys()):
        zabbr = ZONE_ABBREV.get(zone, zone.lower()).upper()
        zone_ident = dsl_id(f"zone_{zabbr}")
        zone_idents[zone] = zone_ident
        zone_label = zone_display(zone)
        lines.append(
            f"            {zone_ident} = container {dsl_str(zone_label)} "
            f"{dsl_str(f'{zone_label} zone of the product.')} {dsl_str('group')} {{"
        )
        lines.append(f"                tags \"zone:{zabbr}\" \"capability-self\"")
        lines.append("                properties {")
        lines.append(
            f"                    {dsl_str('zone-code')} {dsl_str(zone)}"
        )
        lines.append("                }")
        for cap in sorted(by_zone[zone], key=lambda c: c["id"]):
            cap_id = cap["id"]
            ident = dsl_id(cap_id)
            cap_idents[cap_id] = ident
            pack = packs.get(cap_id, {})
            self_slice = (pack.get("slices", {}).get("capability_self") or [{}])[0]
            cap_name = self_slice.get("name") or cap["name"]
            cap_description = (self_slice.get("description") or "").strip() or cap_name
            tactical_tags = (
                ((pack.get("slices", {}).get("tactical_stack") or [{}])[0])
                .get("tags", []) or []
            )
            tech = "python" if "python" in tactical_tags else (
                "dotnet" if "dotnet" in tactical_tags or "aspnet" in tactical_tags
                else "stack-tbd"
            )
            impl = detect_impl(cap_id, zone)
            impl_tag = (
                f"implemented:{impl.label}"
                if impl.label != "not-scaffolded"
                else "not-scaffolded"
            )
            lines.append(
                f"                {ident} = component {dsl_str(cap_name)} "
                f"{dsl_str(cap_description)} {dsl_str(tech)} {{"
            )
            lines.append(
                f"                    tags {dsl_str(impl_tag)} {dsl_str('tech:' + tech)} {dsl_str('level:L2')}"
            )
            lines.append("                    properties {")
            lines.append(
                f"                        {dsl_str('capability-id')} {dsl_str(cap_id)}"
            )
            lines.append("                    }")
            lines.append("                }")
        lines.append("            }")

    lines.append("        }")  # close product softwareSystem

    # Coarse-grained actor relationships.
    if "CHANNEL" in by_zone:
        chn_ident = zone_idents.get("CHANNEL")
        if chn_ident:
            lines.append("")
            lines.append(
                f"        beneficiary -> {product_ident}.{chn_ident} "
                f"\"Uses the beneficiary journey\" \"HTTPS\""
            )
            lines.append(
                f"        prescriber -> {product_ident}.{chn_ident} "
                f"\"Uses the prescriber portal\" \"HTTPS\""
            )
    if "EXCHANGE_B2B" in by_zone:
        b2b_ident = zone_idents.get("EXCHANGE_B2B")
        if b2b_ident:
            lines.append(
                f"        partner_bank -> {product_ident}.{b2b_ident} "
                f"\"Card / Open Banking flows\" \"HTTPS\""
            )
    if "STEERING" in by_zone:
        str_ident = zone_idents.get("STEERING")
        if str_ident:
            lines.append(
                f"        regulator -> {product_ident}.{str_ident} "
                f"\"Audits programme governance\" \"HTTPS\""
            )

    # Zone-to-zone relationships (one per directed pair where ≥1 cross-zone
    # BUSINESS-event flow exists; resource subscriptions are not surfaced).
    zone_edges: set[tuple[str, str]] = set()
    cap_zone: dict[str, str] = {c["id"]: c["zone"] for c in l2_caps}
    for cap in l2_caps:
        cap_id = cap["id"]
        pack = packs.get(cap_id, {})
        for sub in pack.get("slices", {}).get("consumed_events", []) or []:
            if sub.get("layer") != "business":
                continue
            ev = sub.get("subscribed_event", {})
            emitter = ev.get("emitting_capability")
            if not emitter:
                continue
            src_zone = cap_zone.get(emitter)
            dst_zone = cap_zone.get(cap_id)
            if src_zone and dst_zone and src_zone != dst_zone:
                zone_edges.add((src_zone, dst_zone))

    for src_zone, dst_zone in sorted(zone_edges):
        src = zone_idents.get(src_zone)
        dst = zone_idents.get(dst_zone)
        if src and dst:
            lines.append(
                f"        {product_ident}.{src} -> {product_ident}.{dst} "
                f"\"Business events\" \"Business event subscription\" \"upstream-event\""
            )

    lines.append("    }")  # close model
    lines.append("")
    lines.append("    views {")
    lines.append(f"        systemLandscape \"Enterprise-Landscape\" {{")
    lines.append("            include *")
    lines.append("            autoLayout lr")
    lines.append("        }")
    lines.append(f"        systemContext {product_ident} \"Product-Context\" {{")
    lines.append("            include *")
    lines.append("            autoLayout lr")
    lines.append("        }")
    lines.append(f"        container {product_ident} \"Product-Zones\" {{")
    lines.append("            include *")
    lines.append("            autoLayout lr")
    lines.append("        }")
    for zone, zone_ident in zone_idents.items():
        view_id = f"Zone-{ZONE_ABBREV.get(zone, zone).upper()}-L2s"
        lines.append(
            f"        component {product_ident}.{zone_ident} {dsl_str(view_id)} {{"
        )
        lines.append("            include *")
        lines.append("            autoLayout lr")
        lines.append("        }")
    lines.append(_STYLES_BLOCK)
    lines.append("    }")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────


def write_file(path: Path, content: str, dry_run: bool) -> str:
    if dry_run:
        return f"DRY-RUN would write {path.relative_to(REPO_ROOT)} ({len(content)} bytes)"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"wrote {path.relative_to(REPO_ROOT)}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Render the product capability tree to Structurizr DSL."
    )
    ap.add_argument(
        "--cap",
        help="emit only this capability's per-L2 workspace.dsl",
    )
    ap.add_argument(
        "--enterprise-only",
        action="store_true",
        help="emit only the enterprise + zone workspaces, no per-L2 files",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be written but make no filesystem change",
    )
    args = ap.parse_args()

    caps = list_capabilities()
    # Global name map (any level) so external-capability software systems
    # show their real BCM name rather than just their last-segment label.
    cap_names: dict[str, str] = {c["id"]: c["name"] for c in caps}
    l2_caps = [c for c in caps if c["level"] == "L2"]
    if args.cap:
        target = next((c for c in l2_caps if c["id"] == args.cap), None)
        if target is None:
            print(f"!! Unknown L2 capability {args.cap!r}", file=sys.stderr)
            return 2
        l2_caps = [target]

    print(f"[c4-export] L2 capabilities discovered: {len(l2_caps)}")

    packs: dict[str, dict] = {}
    for cap in l2_caps:
        cap_id = cap["id"]
        packs[cap_id] = pack_capability(cap_id)
        print(f"[c4-export] packed {cap_id}")

    log: list[str] = []

    if not args.enterprise_only:
        for cap in l2_caps:
            cap_id = cap["id"]
            dsl = emit_l2_workspace(cap_id, packs[cap_id], cap_names)
            path = DOCS_C4 / cap_id / "workspace.dsl"
            log.append(write_file(path, dsl, args.dry_run))

    # For enterprise + zone we want the FULL set, not a single --cap.
    if args.cap and not args.enterprise_only:
        # If the user asked for a single cap, skip enterprise/zone re-rendering
        # (would be incomplete). They can re-run without --cap to refresh those.
        print(
            "[c4-export] --cap given: skipping enterprise/zone rendering "
            "(re-run without --cap to refresh those)"
        )
    else:
        # Need packs for all L2s to render enterprise + zone correctly.
        all_l2 = [c for c in caps if c["level"] == "L2"]
        for cap in all_l2:
            if cap["id"] not in packs:
                packs[cap["id"]] = pack_capability(cap["id"])
                print(f"[c4-export] packed {cap['id']} (for enterprise/zone)")

        # Zone files.
        by_zone: dict[str, list[dict]] = {}
        for cap in all_l2:
            by_zone.setdefault(cap["zone"], []).append(cap)
        for zone, zcaps in sorted(by_zone.items()):
            dsl = emit_zone_workspace(zone, zcaps, packs, cap_names)
            abbrev = ZONE_ABBREV.get(zone, zone.lower())
            path = DOCS_C4 / "enterprise" / f"zone-{abbrev}.dsl"
            log.append(write_file(path, dsl, args.dry_run))

        # Enterprise file.
        dsl = emit_enterprise_workspace(all_l2, packs)
        path = DOCS_C4 / "enterprise" / "workspace.dsl"
        log.append(write_file(path, dsl, args.dry_run))

    for entry in log:
        print(f"[c4-export] {entry}")
    print(f"[c4-export] done — {len(log)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
