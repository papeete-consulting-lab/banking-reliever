#!/usr/bin/env python3
"""
Hook PreToolUse — protège process/{capability-id}/ contre toute modification
en dehors du skill /process.

Mécanisme :
  - Le skill /process « pose » un sentinelle /tmp/.claude-process-skill.active
    avant la première écriture, et le retire à la fin.
  - Ce hook intercepte les outils Write / Edit / MultiEdit / NotebookEdit.
  - Si la cible se trouve sous process/<CAP>/ (chemin direct, worktree kanban
    /tmp/kanban-worktrees/TASK-NNN-*/process/<CAP>/, OU worktree dédié au
    skill /process /tmp/process-worktrees/<CAP_ID>/process/<CAP>/) ET que le
    sentinelle est absent (ou périmé > 30 min), le call est bloqué avec
    exit code 2 et un message stderr destiné à Claude.

Limites :
  - Le hook ne lit pas les commandes Bash. Les contournements via
    `cat > process/foo`, `sed -i`, `tee`, etc. ne sont pas filtrés. Les
    instructions du skill /process et celles des skills consommateurs
    (/roadmap, /task, /code, /fix, /launch-task, /continue-work) imposent
    l'usage des outils Write/Edit/MultiEdit/NotebookEdit pour toute écriture
    de fichier — c'est la frontière de confiance.
  - Le sentinelle est partagé par session. Pour un usage multi-session
    concurrent, il faudrait le scoper par session_id du payload — ce n'est
    pas le mode opératoire actuel (un seul Claude Code à la fois).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

# Racine canonique du repo. La détection accepte aussi les worktrees kanban,
# qui exposent une copie de l'arbre sous /tmp/kanban-worktrees/TASK-NNN-*/.
PROJECT_ROOT = "/home/yoann/sources/banking"
PROCESS_REL = "process"
SENTINEL = "/tmp/.claude-process-skill.active"
SENTINEL_MAX_AGE_SECONDS = 30 * 60  # 30 min

# Narrow allowance for the /sketch-miro skill: it may write its two sidecar
# files at process/ root only — never inside a capability subfolder.
SKETCH_MIRO_SENTINEL = "/tmp/.claude-sketch-miro.active"
SKETCH_MIRO_ALLOWED_BASENAMES = {"banking-miro.url", ".banking-miro.state.json"}

# /tmp/kanban-worktrees/TASK-NNN-<slug>/...
WORKTREE_RE = re.compile(r"^/tmp/kanban-worktrees/TASK-[A-Za-z0-9-]+/")

# /tmp/process-worktrees/<CAP_ID>/...  (worktree dédié au skill /process)
# <CAP_ID> = forme pleine source-context-préfixée BNK.RLVR.CAP.… (CLI v1.0.0+),
# avec repli rétro-compatible sur l'ancienne forme courte CAP.… .
PROCESS_WORKTREE_RE = re.compile(
    r"^/tmp/process-worktrees/(?:[A-Z]{2,}\.[A-Z]{2,}\.)?CAP\.[A-Z0-9.]+/"
)

GUARDED_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def is_under_process(path: str) -> bool:
    """Retourne True si le chemin cible un fichier sous process/{cap}/.

    Cas couverts :
      1. <PROJECT_ROOT>/process/...
      2. /tmp/kanban-worktrees/TASK-NNN-<slug>/process/...
      3. /tmp/process-worktrees/<CAP_ID>/process/...
      4. Chemin relatif "process/..." (résolu par rapport au cwd implicite)
    """
    if not path:
        return False

    # 1. Chemin absolu sous le repo principal.
    abs_path = os.path.abspath(path)
    main_prefix = os.path.join(PROJECT_ROOT, PROCESS_REL) + os.sep
    if abs_path.startswith(main_prefix) or abs_path == main_prefix.rstrip(os.sep):
        return True

    # 2. Chemin absolu sous un worktree kanban.
    m = WORKTREE_RE.match(abs_path)
    if m:
        rest = abs_path[m.end():]
        # rest commence après le slash final du préfixe TASK-NNN-<slug>/
        first_seg = rest.split(os.sep, 1)[0] if rest else ""
        if first_seg == PROCESS_REL:
            return True

    # 3. Chemin absolu sous un worktree /process dédié.
    m = PROCESS_WORKTREE_RE.match(abs_path)
    if m:
        rest = abs_path[m.end():]
        first_seg = rest.split(os.sep, 1)[0] if rest else ""
        if first_seg == PROCESS_REL:
            return True

    # 4. Chemin relatif (rarement utilisé par les outils mais on couvre).
    if not os.path.isabs(path):
        norm = os.path.normpath(path)
        if norm.startswith(PROCESS_REL + os.sep) or norm == PROCESS_REL:
            return True

    return False


def sentinel_is_fresh() -> bool:
    """Le sentinelle /process existe-t-il, et a-t-il été touché dans la fenêtre récente ?"""
    try:
        st = os.stat(SENTINEL)
    except FileNotFoundError:
        return False
    except Exception:
        return False
    age = time.time() - st.st_mtime
    return age <= SENTINEL_MAX_AGE_SECONDS


def sketch_miro_sentinel_is_fresh() -> bool:
    """Le sentinelle /sketch-miro existe-t-il, et a-t-il été touché dans la fenêtre récente ?"""
    try:
        st = os.stat(SKETCH_MIRO_SENTINEL)
    except FileNotFoundError:
        return False
    except Exception:
        return False
    age = time.time() - st.st_mtime
    return age <= SENTINEL_MAX_AGE_SECONDS


def is_sketch_miro_sidecar(path: str) -> bool:
    """True iff path is one of the two whitelisted sidecar files at process/ root.

    Accepts both <PROJECT_ROOT>/process/<basename> and worktree variants
    /tmp/kanban-worktrees/TASK-NNN-<slug>/process/<basename>.
    """
    if not path:
        return False
    abs_path = os.path.abspath(path)
    basename = os.path.basename(abs_path)
    if basename not in SKETCH_MIRO_ALLOWED_BASENAMES:
        return False
    main_root = os.path.join(PROJECT_ROOT, PROCESS_REL)
    if os.path.dirname(abs_path) == main_root:
        return True
    m = WORKTREE_RE.match(abs_path)
    if m:
        rest = abs_path[m.end():]
        # rest must be exactly process/<basename>
        if rest == os.path.join(PROCESS_REL, basename):
            return True
    m = PROCESS_WORKTREE_RE.match(abs_path)
    if m:
        rest = abs_path[m.end():]
        if rest == os.path.join(PROCESS_REL, basename):
            return True
    return False


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        # Ne jamais bloquer la chaîne sur une erreur de parsing du payload.
        return 0

    tool_name = data.get("tool_name", "")
    if tool_name not in GUARDED_TOOLS:
        return 0

    tool_input = data.get("tool_input", {}) or {}
    file_path = (
        tool_input.get("file_path")
        or tool_input.get("notebook_path")
        or ""
    )

    if not is_under_process(file_path):
        return 0

    if sentinel_is_fresh():
        return 0

    # Narrow exception: /sketch-miro may write its two sidecar files at
    # process/ root, but nothing inside a capability subfolder.
    if sketch_miro_sentinel_is_fresh() and is_sketch_miro_sidecar(file_path):
        return 0

    # Refus : message clair pour Claude.
    print(
        "⛔ Refus d'écriture sous process/.\n"
        f"   Outil : {tool_name}\n"
        f"   Cible : {file_path}\n"
        "   process/{capability-id}/ est en LECTURE SEULE en dehors du skill /process.\n"
        "   Ni /roadmap, /task, /code, /fix, /launch-task, /continue-work, ni les agents\n"
        "   qu'ils spawnent (implement-capability, create-bff, code-web-frontend,\n"
        "   test-business-capability, test-app) ne peuvent modifier ce dossier.\n"
        "   Les PR/CI-CD ouverts par /launch-task, /code ou /fix ne doivent pas\n"
        "   inclure de modifications sous process/.\n"
        "   Pour modifier le process modelling d'une capacité, lance /process <CAP_ID>.",
        file=sys.stderr,
    )
    return 2  # exit 2 = block (Claude Code PreToolUse convention)


if __name__ == "__main__":
    sys.exit(main())
