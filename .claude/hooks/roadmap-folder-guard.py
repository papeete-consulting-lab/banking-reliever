#!/usr/bin/env python3
"""
Hook PreToolUse — protège roadmap/{capability-id}/ contre toute modification
en dehors du skill /roadmap.

Mécanisme :
  - Le skill /roadmap « pose » un sentinelle /tmp/.claude-roadmap-skill.active
    avant la première écriture, et le retire à la fin.
  - Ce hook intercepte les outils Write / Edit / MultiEdit / NotebookEdit.
  - Si la cible se trouve sous roadmap/<CAP>/ (chemin direct, worktree kanban
    /tmp/kanban-worktrees/TASK-NNN-*/roadmap/<CAP>/, OU worktree dédié au
    skill /roadmap /tmp/roadmap-worktrees/<CAP_ID>/roadmap/<CAP>/) ET que le
    sentinelle est absent (ou périmé > 30 min), le call est bloqué avec
    exit code 2 et un message stderr destiné à Claude.

Limites :
  - Le hook ne lit pas les commandes Bash. Les contournements via
    `cat > roadmap/foo`, `sed -i`, `tee`, etc. ne sont pas filtrés. Les
    instructions du skill /roadmap et celles des skills consommateurs
    (/task, /code, /fix, /launch-task, /continue-work) imposent l'usage
    des outils Write/Edit/MultiEdit/NotebookEdit pour toute écriture de
    fichier — c'est la frontière de confiance.
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
PROJECT_ROOT = "/home/yoann/sources/banking/banking-reliever"
ROADMAP_REL = "roadmap"
SENTINEL = "/tmp/.claude-roadmap-skill.active"
SENTINEL_MAX_AGE_SECONDS = 30 * 60  # 30 min

# /tmp/kanban-worktrees/TASK-NNN-<slug>/...
WORKTREE_RE = re.compile(r"^/tmp/kanban-worktrees/TASK-[A-Za-z0-9-]+/")

# /tmp/roadmap-worktrees/<CAP_ID>/...  (worktree dédié au skill /roadmap)
ROADMAP_WORKTREE_RE = re.compile(r"^/tmp/roadmap-worktrees/CAP\.[A-Z0-9.]+/")

GUARDED_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def is_under_roadmap(path: str) -> bool:
    """Retourne True si le chemin cible un fichier sous roadmap/{cap}/.

    Cas couverts :
      1. <PROJECT_ROOT>/roadmap/...
      2. /tmp/kanban-worktrees/TASK-NNN-<slug>/roadmap/...
      3. /tmp/roadmap-worktrees/<CAP_ID>/roadmap/...
      4. Chemin relatif "roadmap/..." (résolu par rapport au cwd implicite)
    """
    if not path:
        return False

    # 1. Chemin absolu sous le repo principal.
    abs_path = os.path.abspath(path)
    main_prefix = os.path.join(PROJECT_ROOT, ROADMAP_REL) + os.sep
    if abs_path.startswith(main_prefix) or abs_path == main_prefix.rstrip(os.sep):
        return True

    # 2. Chemin absolu sous un worktree kanban.
    m = WORKTREE_RE.match(abs_path)
    if m:
        rest = abs_path[m.end():]
        first_seg = rest.split(os.sep, 1)[0] if rest else ""
        if first_seg == ROADMAP_REL:
            return True

    # 3. Chemin absolu sous un worktree /roadmap dédié.
    m = ROADMAP_WORKTREE_RE.match(abs_path)
    if m:
        rest = abs_path[m.end():]
        first_seg = rest.split(os.sep, 1)[0] if rest else ""
        if first_seg == ROADMAP_REL:
            return True

    # 4. Chemin relatif (rarement utilisé par les outils mais on couvre).
    if not os.path.isabs(path):
        norm = os.path.normpath(path)
        if norm.startswith(ROADMAP_REL + os.sep) or norm == ROADMAP_REL:
            return True

    return False


def sentinel_is_fresh() -> bool:
    """Le sentinelle /roadmap existe-t-il, et a-t-il été touché dans la fenêtre récente ?"""
    try:
        st = os.stat(SENTINEL)
    except FileNotFoundError:
        return False
    except Exception:
        return False
    age = time.time() - st.st_mtime
    return age <= SENTINEL_MAX_AGE_SECONDS


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

    if not is_under_roadmap(file_path):
        return 0

    if sentinel_is_fresh():
        return 0

    # Refus : message clair pour Claude.
    print(
        "⛔ Refus d'écriture sous roadmap/.\n"
        f"   Outil : {tool_name}\n"
        f"   Cible : {file_path}\n"
        "   roadmap/{capability-id}/ est en LECTURE SEULE en dehors du skill /roadmap.\n"
        "   Ni /task, /code, /fix, /launch-task, /continue-work, ni les agents\n"
        "   qu'ils spawnent (implement-capability, create-bff, code-web-frontend,\n"
        "   test-business-capability, test-app) ne peuvent modifier ce dossier.\n"
        "   Les PR/CI-CD ouverts par /launch-task, /code ou /fix ne doivent pas\n"
        "   inclure de modifications sous roadmap/.\n"
        "   Pour modifier le roadmap d'une capacité, lance /roadmap <CAP_ID>.",
        file=sys.stderr,
    )
    return 2  # exit 2 = block (Claude Code PreToolUse convention)


if __name__ == "__main__":
    sys.exit(main())
