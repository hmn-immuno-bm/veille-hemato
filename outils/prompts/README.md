# Prompts des tâches planifiées — source de vérité

L'API `mcp__scheduled-tasks__list_scheduled_tasks` ne renvoie pas le contenu
des prompts (seulement les métadonnées). Pour contourner cette limitation,
les prompts sont stockés ICI et synchronisés vers le serveur via
`outils/sync_prompts.py`.

## Fichiers

- `_anti_hallucination.md` — snippet commun, prépendu automatiquement à TOUS
  les prompts par `sync_prompts.py`. Ne pas l'éditer dans les prompts
  individuels — il est ajouté à la volée.
- `hemato-weekly-search.md` — recherche hebdo PubMed/bioRxiv/web
- `hemato-weekly-summary.md` — résumés/critiques/scores
- `hemato-clinical-trials.md` — essais cliniques + conférences mensuels

## Workflow

1. Éditer le prompt voulu : `vim outils/prompts/hemato-weekly-summary.md`
2. Pousser vers le serveur :
   ```bash
   python3 outils/sync_prompts.py hemato-weekly-summary
   # ou tout pousser :
   python3 outils/sync_prompts.py --all
   ```
3. Vérifier dans Cowork (Settings → Scheduled tasks) que la modification est bien là.

## Convention

Chaque fichier `.md` contient le prompt brut. Le snippet
`_anti_hallucination.md` est concaténé en tête lors du `sync_prompts.py`.
Donc le contenu effectif sur le serveur est :

```
[contenu de _anti_hallucination.md]

---

[contenu du prompt spécifique]
```

## Bootstrap

À la création initiale, copier-coller le prompt actuel depuis l'interface
Cowork (Settings → Scheduled tasks → click sur la tâche → 'Copier le prompt')
et le coller dans le fichier `.md` correspondant.
