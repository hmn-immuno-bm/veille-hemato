#!/usr/bin/env python3
"""
Synchronise les prompts versionnés (outils/prompts/*.md) vers les tâches
planifiées Cowork via mcp__scheduled-tasks__update_scheduled_task.

Le snippet `_anti_hallucination.md` est prépendu automatiquement à tous
les prompts.

⚠️ Ce script ne peut PAS appeler les MCP directement (il s'exécute dans
un sandbox Python isolé). Il sert à PRÉPARER le contenu final à pousser
et l'imprime sur stdout, à charge pour Cowork de faire l'appel MCP.

Usage :
  python3 outils/sync_prompts.py hemato-weekly-summary  # affiche le prompt complet
  python3 outils/sync_prompts.py --all                  # affiche tous les prompts
  python3 outils/sync_prompts.py --list                 # liste les prompts disponibles
"""
import os, sys

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prompts')
ANTI_HALLUC = '_anti_hallucination.md'

VALID_TASKS = {
    'hemato-weekly-search',
    'hemato-weekly-summary',
    'hemato-clinical-trials',
}


def build_prompt(task_id):
    """Concatène _anti_hallucination.md + le prompt spécifique."""
    anti_path = os.path.join(PROMPTS_DIR, ANTI_HALLUC)
    task_path = os.path.join(PROMPTS_DIR, f'{task_id}.md')
    if not os.path.exists(task_path):
        return None, f"Fichier introuvable: {task_path}"
    with open(anti_path, encoding='utf-8') as f:
        anti = f.read().strip()
    with open(task_path, encoding='utf-8') as f:
        body = f.read().strip()
    full = f"{anti}\n\n---\n\n{body}\n"
    return full, None


def list_prompts():
    if not os.path.isdir(PROMPTS_DIR):
        print("Aucun dossier prompts/")
        return
    files = sorted(f for f in os.listdir(PROMPTS_DIR)
                   if f.endswith('.md') and not f.startswith('_'))
    for f in files:
        task_id = f[:-3]
        path = os.path.join(PROMPTS_DIR, f)
        size = os.path.getsize(path)
        marker = "✅" if task_id in VALID_TASKS else "⚠️ "
        print(f"  {marker} {task_id}  ({size} octets)")


def main():
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return 0

    if args[0] == '--list':
        list_prompts()
        return 0

    if args[0] == '--all':
        targets = sorted(VALID_TASKS)
    else:
        targets = [args[0]]

    for task_id in targets:
        if task_id not in VALID_TASKS:
            print(f"⚠️  Tâche inconnue: {task_id}", file=sys.stderr)
            continue
        full, err = build_prompt(task_id)
        if err:
            print(f"❌ {task_id}: {err}", file=sys.stderr)
            continue
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"  TASK: {task_id}  ({len(full)} caractères)")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(full)
        print()
        # Note pour Cowork : copier-coller dans
        # mcp__scheduled-tasks__update_scheduled_task(taskId=task_id, prompt=full)
    return 0


if __name__ == '__main__':
    sys.exit(main())
