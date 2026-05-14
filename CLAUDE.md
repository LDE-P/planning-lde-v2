# Planning LDE V2

Nouveau système de suivi des projets LDE — modèle Projet → Sous-projet → Étape.

> **⚠️ Les règles « Garde-fous avant implémentation » du CLAUDE.md racine s'appliquent ici.**

## Stack

- HTML/JS vanilla (3 fichiers : `app.js`, `ui.js`, `api.js`) pour le dashboard
- Python 3.10+ pour le serveur local (`serve-v2.py`, port 8001)
- `gspread` pour la synchronisation Google Sheets (Phase 2)
- `data.json` comme source de vérité unique (remplace les sentinelles HTML de V1)

## Fichiers

| Fichier | Rôle |
|---------|------|
| `DASHBOARD-V2.html` | Shell UI pur — charge les données via `GET /api/state` |
| `app.js` | Point d'entrée JS — init, chargement des données |
| `ui.js` | Rendu, interactions, événements |
| `api.js` | Wrappers fetch vers `/api/*` |
| `serve-v2.py` | Serveur local (port 8001) |
| `serve-v2.conf.json` | Config : `spreadsheet_id` |
| `data.json` | Source de vérité des projets/sous-projets/étapes (gitignored ?) |
| `terminal.txt` | (gitignored) Commande de démarrage |

## Lancer le serveur

```bash
python3 serve-v2.py                    # ouvre http://localhost:8001
python3 serve-v2.py --no-browser       # sans ouvrir le navigateur
```

## Tests

```bash
pytest tests-e2e-python/planning-lde/ -v
```

Les tests se trouvent dans `tests-e2e-python/planning-lde/` (style pytest, port 8099).

## Spec et tests

- Spec : `planning-lde-v2/SPEC-PLANNING-V2.md`
- Tests : `planning-lde-v2/TESTS-V2.md`

## Modèle de données (`data.json`)

```json
{
  "projects": [
    {
      "id": "...",
      "name": "...",
      "alias": "...",
      "subprojects": [
        {
          "id": "...",
          "name": "...",
          "status": "todo|wip|review|spec|done|blocked",
          "qualif": "P0|P1|P2|P3",
          "target": "YYYY-MM-DD",
          "owner": "laurent|micka|elie|team|null",
          "charge": 0.0,
          "raf": 0.0,
          "steps": [
            { "name": "...", "status": "todo|...|na", "charge": 0.0, "raf": 0.0 }
          ]
        }
      ]
    }
  ]
}
```

## Correspondance statuts

| Code | Label GSheet |
|------|-------------|
| `done` | TERMINÉ |
| `wip` | EN COURS |
| `review` | REVUE |
| `spec` | SPEC |
| `todo` | À FAIRE |
| `blocked` | STAND BY |
| `na` | N/A (étapes uniquement) |

## Google Sheets V2 — Configuration

| Élément | Valeur |
|---------|--------|
| Spreadsheet ID | `1RY1SCZAW5PPG05Cbpvup5pAe6BWvUhy_UZ4DPwl3Wew` |
| URL | https://docs.google.com/spreadsheets/d/1RY1SCZAW5PPG05Cbpvup5pAe6BWvUhy_UZ4DPwl3Wew/ |
| `serve-v2.conf.json` | ✅ ID renseigné |
| `client_secret.json` | ✅ Copié depuis `planning-lde/` (gitignored) |
| `token.json` | Créé automatiquement au premier appel GSheet (gitignored) |

**Premier lancement avec GSheet :** le flow OAuth ouvre le navigateur — cliquer "Autoriser" **immédiatement** (le callback localhost a un timeout court). En cas de page d'erreur localhost, relancer une action GSheet pour obtenir un flow frais.

## Règles de développement

- Ne jamais écrire dans l'onglet TCD Projets ni Semaines côté Python (Phase 2)
- Formules GSheet : référence absolue = `planning-lde/formules.md`
- Bibliothèque GSheet : `gspread` (pas `google-api-python-client`)
- `data.json` : lecture/écriture atomique via `_load_data()` / `_save_data()`
- CORS : tous les endpoints renvoient `Access-Control-Allow-Origin: *`
- Payload max : 1 Mo (413 si dépassé)

## Fin de session

Inclure la date et l'heure courantes dans le message de clôture.
`TZ="Europe/Paris" date "+%Y-%m-%d %H:%M"`
