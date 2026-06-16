#!/usr/bin/env python3
"""
Hook PreToolUse — protège tasks/ contre toute écriture non autorisée.

Deux zones distinctes, deux contrats indépendants :

  A. tasks/{capability-id}/TASK-NNN-*.md
     Écriture autorisée uniquement si le sentinelle « task-pipeline »
     /tmp/.claude-task-pipeline.active est présent et frais (≤ 30 min).
     Ce sentinelle est posé par l'un quelconque des sept skills habilités
     à muter le frontmatter d'une carte TASK :
       /task               (création)
       /task-refinement    (résolution des Open Questions)
       /launch-task        (transitions status: todo → in_progress)
       /code               (loop_count, max_loops, pr_url, stalled_reason,
                            status: in_progress → in_review / stalled)
       /fix                (loop_count, pr_url, fix_pr_urls, stalled_reason,
                            transitions de remédiation)
       /continue-work      (reset loop_count, status: stalled → todo/in_progress)
       /pr-merge-watcher   (status: in_review → done après merge GitHub)
     Tout autre appelant (agents implementation-capability, create-bff,
     code-web-frontend, test-business-capability, test-app, harness-backend,
     ou édition ad-hoc) est bloqué.

  B. tasks/BOARD.md
     Écriture autorisée uniquement si le sentinelle « sort-task »
     /tmp/.claude-sort-task-skill.active est présent et frais (≤ 30 min).
     Ce sentinelle est posé exclusivement par /sort-task — l'unique
     algorithme de rendu du kanban. Les skills qui doivent voir leurs
     changements reflétés sur le board (/launch-task, /pr-merge-watcher,
     /code, /fix, …) écrivent leurs transitions dans le frontmatter de la
     carte TASK puis invoquent /sort-task, qui régénère BOARD.md depuis
     zéro à partir de l'état canonique des cartes.

Mécanisme :
  - Le hook intercepte les outils Write / Edit / MultiEdit / NotebookEdit.
  - Le chemin cible est classé : BOARD, TASK card, ou hors-périmètre.
  - BOARD hors-périmètre → laisser passer.
  - Sinon, vérifier le sentinelle approprié.
  - Si absent / périmé → exit 2 avec message stderr destiné à Claude.

Limites :
  - Le hook ne lit pas les commandes Bash. Les contournements via
    `cat > tasks/foo`, `sed -i`, `tee`, etc. ne sont pas filtrés. Les
    instructions des skills imposent l'usage des outils Write/Edit/
    MultiEdit/NotebookEdit pour toute écriture de fichier — c'est la
    frontière de confiance.
  - Le sentinelle est partagé par session. Pour un usage multi-session
    concurrent, il faudrait le scoper par session_id du payload — ce
    n'est pas le mode opératoire actuel.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

# Racine canonique du repo. La détection accepte aussi les worktrees kanban,
# qui exposent une copie de l'arbre sous /tmp/kanban-worktrees/TASK-NNN-*/.
PROJECT_ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
TASKS_REL = "tasks"

TASK_SENTINEL = "/tmp/.claude-task-pipeline.active"
BOARD_SENTINEL = "/tmp/.claude-sort-task-skill.active"
SENTINEL_MAX_AGE_SECONDS = 30 * 60  # 30 min

# /tmp/kanban-worktrees/TASK-NNN-<slug>/...
WORKTREE_RE = re.compile(r"^/tmp/kanban-worktrees/TASK-[A-Za-z0-9-]+/")

# Relative-to-tasks/ matchers:
#   - BOARD.md at the root → board
#   - <CAP-ID>/TASK-<anything>.md exactly two segments deep → card
BOARD_REL_RE = re.compile(r"^BOARD\.md$")
TASK_CARD_REL_RE = re.compile(r"^[^/]+/TASK-[^/]+\.md$")

GUARDED_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def classify(path: str) -> str:
    """Retourne 'board', 'card', or '' (out of scope).

    Cas couverts pour la résolution de la racine tasks/ :
      1. <PROJECT_ROOT>/tasks/...
      2. /tmp/kanban-worktrees/TASK-NNN-<slug>/tasks/...
      3. Chemin relatif "tasks/..." (rare mais on couvre)
    """
    if not path:
        return ""

    rel = None

    abs_path = os.path.abspath(path)

    # 1. Chemin absolu sous le repo principal.
    main_prefix = os.path.join(PROJECT_ROOT, TASKS_REL) + os.sep
    if abs_path.startswith(main_prefix):
        rel = abs_path[len(main_prefix):]

    # 2. Chemin absolu sous un worktree kanban.
    if rel is None:
        m = WORKTREE_RE.match(abs_path)
        if m:
            rest = abs_path[m.end():]
            # rest doit commencer par "tasks/"
            tasks_prefix = TASKS_REL + os.sep
            if rest.startswith(tasks_prefix):
                rel = rest[len(tasks_prefix):]

    # 3. Chemin relatif "tasks/..."
    if rel is None and not os.path.isabs(path):
        norm = os.path.normpath(path)
        tasks_prefix = TASKS_REL + os.sep
        if norm.startswith(tasks_prefix):
            rel = norm[len(tasks_prefix):]

    if rel is None:
        return ""

    if BOARD_REL_RE.match(rel):
        return "board"
    if TASK_CARD_REL_RE.match(rel):
        return "card"
    return ""


def sentinel_is_fresh(path: str) -> bool:
    """True iff *path* exists and was touched within the freshness window."""
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return False
    except Exception:
        return False
    age = time.time() - st.st_mtime
    return age <= SENTINEL_MAX_AGE_SECONDS


def deny(tool_name: str, file_path: str, kind: str) -> None:
    if kind == "board":
        msg = (
            "⛔ Refus d'écriture sur tasks/BOARD.md.\n"
            f"   Outil : {tool_name}\n"
            f"   Cible : {file_path}\n"
            "   tasks/BOARD.md est en LECTURE SEULE en dehors du skill /sort-task.\n"
            "   /sort-task est l'unique algorithme de rendu du kanban : il lit\n"
            "   tous les TASK-*.md et régénère BOARD.md depuis zéro. Pour refléter\n"
            "   une transition (status: in_progress, status: done, stalled, …),\n"
            "   modifie le frontmatter de la carte TASK concernée (cf. le guard\n"
            "   tasks/<CAP>/TASK-*.md), puis invoque /sort-task. Les skills\n"
            "   /launch-task, /pr-merge-watcher, /code, /fix appliquent déjà ce\n"
            "   protocole — ne réimplémente pas la logique de score / dérivation\n"
            "   d'état ici."
        )
    else:  # card
        msg = (
            "⛔ Refus d'écriture sur tasks/{capability-id}/TASK-*.md.\n"
            f"   Outil : {tool_name}\n"
            f"   Cible : {file_path}\n"
            "   Les cartes TASK sont mutables uniquement par l'un des sept skills\n"
            "   du pipeline qui posent le sentinelle\n"
            "   /tmp/.claude-task-pipeline.active :\n"
            "     /task               (création)\n"
            "     /task-refinement    (Open Questions)\n"
            "     /launch-task        (status: todo → in_progress)\n"
            "     /code               (loop_count, pr_url, status: in_review/stalled)\n"
            "     /fix                (loop_count, fix_pr_urls, stalled_reason)\n"
            "     /continue-work      (reset loop_count, status: stalled → todo)\n"
            "     /pr-merge-watcher   (status: in_review → done)\n"
            "   Les agents (implement-capability, create-bff, code-web-frontend,\n"
            "   test-business-capability, test-app, harness-backend) ne modifient\n"
            "   jamais une carte TASK directement — ils renvoient leur verdict\n"
            "   au skill orchestrateur qui l'applique."
        )
    print(msg, file=sys.stderr)


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

    kind = classify(file_path)
    if not kind:
        return 0

    if kind == "board":
        if sentinel_is_fresh(BOARD_SENTINEL):
            return 0
        deny(tool_name, file_path, "board")
        return 2

    # kind == "card"
    if sentinel_is_fresh(TASK_SENTINEL):
        return 0
    deny(tool_name, file_path, "card")
    return 2


if __name__ == "__main__":
    sys.exit(main())
