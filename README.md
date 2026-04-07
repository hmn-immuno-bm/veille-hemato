# Veille Hémato-Immuno-Oncologie

Dashboard interactif de veille bibliographique en hémato-immuno-oncologie, avec focus sur la biopsie liquide (ctDNA) et les lymphomes B.

## Contenu

558 articles curés couvrant 2012–2026, répartis en 7 catégories : Lymphomes, ctDNA — Lymphomes, Immuno + ctDNA/Lymphome, ctDNA — Méthodo, Hémato générale, IA + Hémato, Preprints.

Le dashboard inclut également un suivi des essais cliniques en cours (lymphomes B), un calendrier des conférences hémato, des pistes de recherche transversales et un système de feedback pour affiner le scoring.

## Accès

Le dashboard est déployé via GitHub Pages : un fichier HTML unique (`index.html`) avec données embarquées, sans dépendance externe.

## Mise à jour

Les articles sont collectés automatiquement chaque semaine via des tâches planifiées (PubMed, bioRxiv, web) puis importés manuellement dans la base après vérification. Le dashboard est régénéré à chaque import.

Pour pousser une mise à jour :

```bash
cd ~/Library/CloudStorage/Dropbox/Veille/output
git add index.html
git commit -m "update dashboard"
git push
```

## Stack

HTML/CSS/JS vanilla (fichier unique) — Python pour l'outillage (import, validation, génération).
