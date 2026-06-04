#!/usr/bin/env python3
"""Verify that the natural language used under sources/ and src/ matches the BCM.

The BCM is the source of truth for the project's ubiquitous language. Since
neither the BCM nor the process-modelling layer lives in this repo any more
(both are hosted in the external `reliever-knowledge` repo and consumed via the
single `kpack` knowledge engine), this script:

  1. Discovers the capabilities to check via `kpack process <CTX> --list` — the
     capability ids that have a process model published upstream. The positional
     id only supplies the context (`BNK.RLVR`); the corpus is resolved from it.
  2. For each capability, calls `kpack pack <CAP_ID> --deep --compact` to fetch
     the upstream prose (capability descriptions, FUNC ADR decision /
     context / consequences, business-object definitions, vision narratives).
  3. Aggregates the prose, runs a stop-word language detector, and picks the
     dominant language.
  4. Compares it to the dominant language found in code under `sources/` and
     `src/`. Mismatch ⇒ exit 1.

Detection is stop-word based: tiny, no extra deps beyond `kpack` itself
and the standard library.

Exit codes:
  0 — BCM and code agree, OR there is nothing to check yet (no process model
      published upstream, no source code, or `kpack` unavailable).
  1 — BCM and code disagree.
  2 — `kpack` is installed but every invocation failed (hard error).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRS = [ROOT / "sources", ROOT / "src"]

# The Reliever BCM/process corpus context (id segments 0–1). kpack resolves the
# corpus repo from this prefix; it supplies the context for `process --list`.
RLVR_CONTEXT = "BNK.RLVR"

SOURCE_EXTS = {
    ".cs", ".fs", ".vb",
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".py", ".java", ".kt", ".go", ".rs",
    ".rb", ".php", ".swift",
    ".html", ".htm", ".vue", ".svelte",
    ".css", ".scss",
    ".md", ".txt",
}

# Slices that carry natural-language prose (as opposed to identifiers,
# IDs, enums…). Anything else in the pack is structural and would only
# muddy the language detection. These are kpack's normalized slice names
# (e.g. business-/platform-/governance-vision all normalize to `domain_vision`).
PROSE_SLICES = {
    "capability_self",
    "capability_ancestors",
    "capability_definition",
    "carried_objects",
    "carried_concepts",
    "governing_urba",
    "governing_tech_strat",
    "governance_adrs",
    "product_vision",
    "domain_vision",
    "tech_vision",
}

# Within those slices, only collect string values whose length suggests
# prose rather than an identifier. 30 chars filters out things like
# "BUSINESS_SERVICE_PRODUCTION" or "OBJ.REF.001.BENEFICIAIRE".
MIN_PROSE_LEN = 30

STOPWORDS: dict[str, set[str]] = {
    "en": {
        "the", "of", "and", "to", "in", "is", "that", "for", "with", "on",
        "as", "by", "this", "be", "are", "from", "or", "an", "at", "have",
        "has", "it", "not", "but", "they", "we", "you", "their", "our",
        "your", "which", "when", "what", "where", "how", "can", "must",
        "should", "will", "may", "any", "all", "into", "between",
    },
    "fr": {
        "le", "la", "les", "de", "du", "des", "et", "à", "en", "un", "une",
        "dans", "sur", "pour", "avec", "que", "qui", "est", "sont", "par",
        "se", "ne", "pas", "ce", "cette", "ces", "il", "elle", "ils",
        "elles", "nous", "vous", "leur", "leurs", "au", "aux", "ou", "mais",
        "comme", "plus", "si", "sa", "son", "ses", "mon", "ma", "mes",
        "ton", "ta", "tes", "notre", "votre", "être", "avoir",
    },
    "es": {
        "el", "la", "los", "las", "de", "y", "a", "en", "un", "una", "que",
        "es", "son", "por", "con", "para", "del", "al", "se", "no", "su",
        "sus", "como", "pero", "más", "ser", "estar", "este", "esta",
        "estos", "estas", "lo", "le", "les", "yo", "tu", "él", "ella",
    },
}

WORD_RE = re.compile(r"[A-Za-zÀ-ÿ]+")
CAP_ID_RE = re.compile(r"^[A-Z0-9.]*CAP\.[A-Z0-9.]+$")


def discover_capabilities() -> list[str]:
    """List CAP_IDs that have a process model published upstream.

    Source of truth is `kpack process <CTX> --list` (the process layer lives in
    reliever-knowledge now, not in this repo). The positional id only supplies
    the context. Stdout is JSON ({"models": [...]}) — older builds emitted one id
    per line; both shapes are handled. The provenance header goes to stderr.
    """
    try:
        result = subprocess.run(
            ["kpack", "process", RLVR_CONTEXT, "--list", "--compact"],
            capture_output=True, text=True, timeout=60, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        print(
            f"  ⚠ kpack process {RLVR_CONTEXT} --list: exit {result.returncode}\n"
            f"    stderr: {result.stderr.strip()[:300]}",
            file=sys.stderr,
        )
        return []

    out = result.stdout.strip()
    ids: list[str] = []
    if out.startswith("{") or out.startswith("["):
        try:
            payload = json.loads(out)
            models = payload.get("models", payload) if isinstance(payload, dict) else payload
            for m in models:
                cid = m.get("id") if isinstance(m, dict) else m
                if isinstance(cid, str):
                    ids.append(cid.strip())
        except json.JSONDecodeError:
            pass
    else:
        ids = [line.strip() for line in out.splitlines()]

    return sorted(c for c in ids if CAP_ID_RE.match(c))


def fetch_pack(cap_id: str) -> dict | None:
    """Run `kpack pack <cap_id> --deep --compact` and return parsed JSON, or None on failure."""
    try:
        result = subprocess.run(
            ["kpack", "pack", cap_id, "--deep", "--compact"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError:
        return None  # kpack not installed — caller decides what to do
    except subprocess.TimeoutExpired:
        print(f"  ⚠ kpack pack {cap_id}: timed out after 60s", file=sys.stderr)
        return None

    if result.returncode != 0:
        print(
            f"  ⚠ kpack pack {cap_id}: exit {result.returncode}\n"
            f"    stderr: {result.stderr.strip()[:300]}",
            file=sys.stderr,
        )
        return None

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"  ⚠ kpack pack {cap_id}: invalid JSON ({exc})", file=sys.stderr)
        return None


def extract_prose(node, accumulator: list[str]) -> None:
    """Walk a JSON sub-tree and collect string values long enough to be prose."""
    if isinstance(node, str):
        if len(node) >= MIN_PROSE_LEN:
            accumulator.append(node)
    elif isinstance(node, list):
        for item in node:
            extract_prose(item, accumulator)
    elif isinstance(node, dict):
        for value in node.values():
            extract_prose(value, accumulator)


def collect_bcm_text(capabilities: list[str]) -> tuple[str, int]:
    """Aggregate prose across every capability's pack. Returns (text, packs_seen)."""
    chunks: list[str] = []
    packs_seen = 0
    for cap_id in capabilities:
        print(f"  · kpack pack {cap_id} --deep --compact")
        pack = fetch_pack(cap_id)
        if pack is None:
            continue
        packs_seen += 1
        slices = pack.get("slices") or {}
        for slice_name in PROSE_SLICES:
            extract_prose(slices.get(slice_name), chunks)
    return "\n".join(chunks), packs_seen


def collect_code_text(roots: list[Path], exts: set[str]) -> str:
    chunks: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in exts:
                continue
            try:
                chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
    return "\n".join(chunks)


def detect_language(text: str) -> tuple[str | None, dict[str, int]]:
    counts = {lang: 0 for lang in STOPWORDS}
    if not text:
        return None, counts
    for raw in WORD_RE.findall(text):
        token = raw.lower()
        for lang, words in STOPWORDS.items():
            if token in words:
                counts[lang] += 1
    if all(c == 0 for c in counts.values()):
        return None, counts
    return max(counts, key=counts.get), counts


def main() -> int:
    # Skip cleanly when kpack is not installed (e.g. CI runs without access to
    # the private corpora). The check is advisory in that case rather than a
    # hard CI failure.
    if shutil.which("kpack") is None:
        print(
            "ℹ kpack CLI not on PATH — skipping language check.\n"
            "  To enable this check in CI, make `kpack` available (the bin/kpack\n"
            "  container wrapper, or a pipx-installed console script) with read\n"
            "  access to the private corpora."
        )
        return 0

    capabilities = discover_capabilities()
    if not capabilities:
        print("ℹ `kpack process` returned no models — no capability modeled yet, skipping.")
        return 0

    print(f"Discovered {len(capabilities)} capabilities with an upstream process model:")
    for cap in capabilities:
        print(f"  - {cap}")

    print("\nFetching prose from kpack:")
    bcm_text, packs_seen = collect_bcm_text(capabilities)
    if packs_seen == 0:
        print(
            "ERROR: kpack is installed but every `kpack pack` call failed.\n"
            "       Check the messages above (auth, network, missing capability…).",
            file=sys.stderr,
        )
        return 2

    code_text = collect_code_text(SOURCE_DIRS, SOURCE_EXTS)

    bcm_lang, bcm_counts = detect_language(bcm_text)
    code_lang, code_counts = detect_language(code_text)

    print(f"\nBCM  stop-word counts (over {packs_seen} pack(s)): {bcm_counts}")
    print(f"Code stop-word counts: {code_counts}")
    print(f"BCM  language: {bcm_lang}")
    print(f"Code language: {code_lang}")

    if bcm_lang is None:
        print(
            "ERROR: unable to determine BCM language — packs returned no detectable prose.",
            file=sys.stderr,
        )
        return 2

    if code_lang is None:
        print("No source language detected (no code under sources/ or src/). Skipping.")
        return 0

    if bcm_lang != code_lang:
        print(
            f"\nERROR: source code is written in '{code_lang}' but the BCM is written in '{bcm_lang}'.\n"
            f"       The code must use the same natural language as the BCM (the ubiquitous-language source of truth).",
            file=sys.stderr,
        )
        return 1

    print(f"\n✓ Code and BCM agree on language ({bcm_lang}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
