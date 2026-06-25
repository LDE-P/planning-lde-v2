> **⚠️ RÈGLE OBLIGATOIRE — Contexte GIT racine :**
> Ce projet est un sous-dossier de `/Users/laurentdenis/Documents/GIT/`.
> **Avant toute action**, lire le fichier d'instructions racine correspondant à votre assistant :
> - Codex / Cowork → `/Users/laurentdenis/Documents/GIT/AGENTS.md`
> - Antigravity → `/Users/laurentdenis/Documents/GIT/GEMINI.md`
>
> Si le dossier GIT racine n'est pas accessible depuis votre workspace, **signaler à LDE** :
> « Session ouverte hors process — je n'ai pas accès au AGENTS.md / GEMINI.md racine GIT. Merci de m'y donner accès ou de relancer depuis GIT/. »

# Planning LDE V2

Nouveau système de suivi des projets LDE — modèle Projet → Sous-projet → Étape.

> **⚠️ Les règles « Garde-fous avant implémentation » du AGENTS.md racine s'appliquent ici.**

## En début de session

Lire **`notes-todo.md`** à la racine du projet : contient les notes inter-sessions (rappels, actions en attente, items à implémenter).

## Remote Git

- **URL** : https://github.com/LDE-P/planning-lde-v2 (repo privé, compte LDE-P)
- `data.json` et `data-archives.json` sont **versionnés** — commiter à chaque fin de session
- En cas de corruption : `git checkout data.json`

### Commit et push depuis Cowork (sandbox)

**Cowork peut commit ET push directement** — authentification configurée via token OAuth dans `.git/config` (jamais versionné).

Pattern standard à utiliser dans chaque bash git :

```bash
cd /sessions/<session>/mnt/GIT/planning-lde-v2
rm -f .git/HEAD.lock .git/index.lock 2>/dev/null   # nettoie les locks résiduels
git add <fichiers>
git commit -m "..."
git push
```

**Si `rm .git/HEAD.lock` échoue** (Operation not permitted) : appeler `allow_cowork_file_delete` sur le chemin `.git/HEAD.lock` avant de relancer.

**Hook pre-push** : les tests e2e sont ignorés automatiquement si pytest est absent ou si le serveur n'est pas joignable (comportement sandbox normal). Sur le Mac de LDE avec le serveur en cours, ils s'exécutent normalement.

> **⚠️ Synchronisation Google Sheets ABANDONNÉE (2026-06-03).** Le dashboard est
> 100 % autonome sur `data.json` — il n'émet plus aucune action vers une GSheet.
> Tout le code de sync (gspread, OAuth, push/pull/TCD, `gsheet_hidden`) a été
> retiré. Voir `SPEC-DECOUPLAGE-GSHEET.md` et les anciennes specs dans
> `archive-gsheet/`. Ne pas réintroduire de dépendance GSheet sans nouvelle décision LDE.

## Stack

- HTML/JS vanilla (3 fichiers : `app.js`, `ui.js`, `api.js`) pour le dashboard
- Python 3.10+ pour le serveur local (`serve-v2.py`, port 8001) — aucune dépendance externe
- `data.json` comme source de vérité unique (remplace les sentinelles HTML de V1)

## Fichiers

| Fichier | Rôle |
|---------|------|
| `DASHBOARD-V2.html` | Shell UI pur — charge les données via `GET /api/state` |
| `app.js` | Point d'entrée JS — init, chargement des données |
| `ui.js` | Rendu, interactions, événements |
| `api.js` | Wrappers fetch vers `/api/*` |
| `serve-v2.py` | Serveur local (port 8001) |
| `data.json` | Source de vérité des projets/sous-projets/étapes (versionné) |
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
      "desc": "...",
      "stack": "...",
      "category": "active|infra|legacy|editorial",
      "folder": "...",
      "docs": [
        {
          "id": "...",
          "file": "chemin/relatif/depuis/GIT_ROOT.md",
          "title": "...",
          "desc": "...",
          "type": "spec|audit|tests|bilan|notes|autre",
          "status": "draft|final|archived",
          "date": "YYYY-MM-DD",
          "subproject": "id-du-sp|null"
        }
      ],
      "subprojects": [
        {
          "id": "...",
          "name": "...",
          "status": "todo|wip|review|spec|done|blocked|fail",
          "qualif": "P0|P1|P2|P3",
          "target": "YYYY-MM-DD",
          "owner": "laurent|micka|elie|team|null",
          "charge": 0.0,
          "raf": 0.0,
          "titre": "...",
          "type": "Feature|BugFix|Récurrent|Support|Autre",
          "commentaire": "...",
          "steps": [
            { "name": "...", "status": "todo|...|na", "charge": 0.0, "raf": 0.0 }
          ]
        }
      ]
    }
  ]
}
```

Notes :
- Le champ `alias` a été **supprimé** de tous les projets (2026-06-04, commit `f029467`). Ne pas le réintroduire.
- `type` et `commentaire` (sur les SP) sont des champs **locaux** — vestiges de l'ancienne sync GSheet, ils restent dans le schéma.
- `folder` et `docs` peuvent être absents pour certains projets (initialisés à vide).

## Correspondance statuts

| Code | Libellé affiché |
|------|-------------|
| `done` | TERMINÉ |
| `wip` | EN COURS |
| `review` | REVUE |
| `spec` | SPEC |
| `todo` | À FAIRE |
| `blocked` | STAND BY |
| `récurrent` | RÉCURRENT |
| `fail` | ÉCHEC |
| `na` | N/A (étapes uniquement) |

Codes définis dans `_VALID_STATUSES` (`serve-v2.py`) et `STATUS_LABELS` (`ui.js`).

## Endpoints HTTP

GET :
- `/api/state` — lit `data.json`
- `/api/local-folders` — liste les sous-dossiers de `GIT/`
- `/api/archives` — lit `data-archives.json`

POST (corps JSON) :
- `/api/save-subproject` — patch sp (name, status, qualif, target, owner, charge, raf, titre, steps)
- `/api/save-project` — patch projet (alias, name, desc, stack)
- `/api/add-subproject`, `/api/add-project`
- `/api/remove-subproject`, `/api/remove-project`
- `/api/open-folder`, `/api/open-file`
- `/api/add-doc`, `/api/save-doc`, `/api/remove-doc`
- `/api/archive-subproject`, `/api/archive-project`, `/api/restore-subproject`, `/api/restore-project`
- `/api/delete-archive-subproject`, `/api/delete-archive-project`

## Conventions UI

- **Boutons de suppression** (🗑) : toujours utiliser la classe `icon-btn-danger` — garantit la couleur rouge (`var(--blocked)`) au repos et au survol. Implémenté via `color: transparent; text-shadow: 0 0 0 var(--blocked)` car `color` n'a aucun effet sur les emoji.
- **Boutons d'archivage** (🗃) : utiliser `icon-btn` seul (couleur neutre) — l'archivage est réversible, pas une action destructive au sens rouge.

## Règles de développement

- `data.json` / `data-archives.json` : lecture via `_load_data()`/`_load_archives()` ; **écriture atomique** via `_save_data()`/`_save_archives()` → `_atomic_write_json()` (blindage 2026-05-31). Garanties : écriture `tmp` + `fsync` → `os.replace` (rename atomique) → `fsync` du dossier ; **garde anti-wipe** (refuse de remplacer un état à N>0 projets par 0 projet → `WipeRefused` → HTTP 409, payload refusé conservé) ; **backups** `.prev` (1 cran, chaque save) + horodatés rotatifs dans `backups-data/` (throttle 10 min, 10 gardés). `.prev`/`.tmp`/`backups-data/` sont gitignorés ; `data.json` reste versionné.
- **⚠️ Édition concurrente de `data.json` (incident 2026-06-11)** : le serveur (et d'autres sessions) réécrivent `data.json` en continu. **Ne pas l'éditer via l'outil fichier Read/Edit** (copie potentiellement périmée → un commit peut écraser le travail d'une autre session). Éditer en bash dans une seule passe (relecture disque → script Python → `git add`/`commit` immédiat), et **vérifier avant push** que le nombre de projets/SP n'a pas régressé vs `git show HEAD:data.json`. Détail dans le `AGENTS.md` racine, section « `data.json` — copie périmée via l'outil fichier ».
- CORS : tous les endpoints renvoient `Access-Control-Allow-Origin: *`
- Payload max : 1 Mo (413 si dépassé)
- **Aucune dépendance externe** : le serveur n'utilise que la bibliothèque standard Python. La synchronisation Google Sheets a été retirée (2026-06-03, voir `SPEC-DECOUPLAGE-GSHEET.md`).

## Fin de session

Inclure la date et l'heure courantes dans le message de clôture.
`TZ="Europe/Paris" date "+%Y-%m-%d %H:%M"`
