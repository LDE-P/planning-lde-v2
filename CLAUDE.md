# Planning LDE V2

Nouveau système de suivi des projets LDE — modèle Projet → Sous-projet → Étape.

> **⚠️ Les règles « Garde-fous avant implémentation » du CLAUDE.md racine s'appliquent ici.**

## En début de session

Lire **`notes-todo.md`** à la racine du projet : contient les notes inter-sessions (rappels, actions en attente, items à implémenter).

## Remote Git

- **URL** : https://github.com/LDE-P/planning-lde-v2 (repo privé, compte LDE-P)
- `data.json` et `data-archives.json` sont **versionnés** — commiter à chaque fin de session
- En cas de corruption : `git checkout data.json` (ne touche pas la GSheet — sync toujours manuelle)
- ⚠️ Après un revert de `data.json`, ne pas faire de push GSheet sans vérifier que l'état est cohérent

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
      "desc": "...",
      "stack": "...",
      "category": "active|infra|legacy|editorial",
      "folder": "...",
      "docs": ["..."],
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
- `type` et `commentaire` sont **GSheet-only** : lus au pull, jamais réécrits au push
- `folder` et `docs` peuvent être absents pour les projets créés via le pull (initialisés à vide)
- Au pull, si l'alias (col A) ou le nom SP (col B) n'existent pas dans `data.json`, le projet/sp est créé avec les 4 étapes par défaut

## Correspondance statuts

| Code | Label GSheet |
|------|-------------|
| `done` | TERMINÉ |
| `wip` | EN COURS |
| `review` | REVUE |
| `spec` | SPEC |
| `todo` | À FAIRE |
| `blocked` | STAND BY |
| `récurrent` | RÉCURRENT |
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

## Sync GSheet ↔ data.json (onglet Tâches)

| Col | Champ sp | Direction | Notes |
|-----|----------|-----------|-------|
| A | projet (alias) | dashboard → GSheet | identifie le projet |
| B | `name` | dashboard → GSheet | identifie le sp |
| C | `type` | **GSheet → data.json** | GSheet-only, jamais réécrit |
| D | `qualif` | bidirectionnel | |
| E | `target` | bidirectionnel | |
| F | `charge` | bidirectionnel | cellule vide au pull = pas d'écrasement |
| G | `raf` | bidirectionnel | cellule vide au pull = pas d'écrasement |
| H | `titre` | bidirectionnel | |
| I | `status` | bidirectionnel | converti via `_STATUS_TO_GS` / `_STATUS_FROM_GS` |
| J | `commentaire` | **GSheet → data.json** | GSheet-only, jamais réécrit |
| K, L | semaine / année | formules GSheet | calculées depuis E |

- **Push** : `batch_clear` et `batch_update` ciblent `A-B`, `D-I`, `K-L` uniquement (préservation C et J)
- **Pull** crée les projets/sp manquants si l'alias ou le nom n'existent pas dans `data.json`
- **TCD Projets** est reconstruit au push depuis `data.json` directement (via `_build_tcd_rows()`), pas une copie de Semaines — évite la race condition de recalcul asynchrone
- **TCD col B** + **rows 2/3 C-G** : formules Semaines réutilisées (`_f_semaines_b_row/b2/b3/col2/col3`) pour que les éditions team sur C-G recalculent automatiquement les totaux, et pour rester locale-aware (FR : virgules)

## Endpoints HTTP

GET :
- `/api/state` — lit `data.json`
- `/api/gsheet/status` — `{connected, url?}`
- `/api/local-folders` — liste les sous-dossiers de `GIT/`

POST (corps JSON) :
- `/api/save-subproject` — patch sp (name, status, qualif, target, owner, charge, raf, titre, steps)
- `/api/save-project` — patch projet (alias, name, desc, stack)
- `/api/add-subproject`, `/api/add-project`
- `/api/remove-subproject`, `/api/remove-project`
- `/api/open-folder`
- `/api/gsheet/init` — reset complet des 3 onglets
- `/api/gsheet/format` — **manuel uniquement** : pose les dropdowns col C et col I
- `/api/sync-to-gsheet[/preview]` — push
- `/api/pull-from-gsheet[/preview]` — pull Tâches
- `/api/pull-from-tcd[/preview]` — pull TCD (RAF + target par sp)

## Conventions UI

- **Boutons de suppression** (🗑) : toujours utiliser la classe `icon-btn-danger` — garantit la couleur rouge (`var(--blocked)`) au repos et au survol. Implémenté via `color: transparent; text-shadow: 0 0 0 var(--blocked)` car `color` n'a aucun effet sur les emoji.
- **Boutons d'archivage** (🗃) : utiliser `icon-btn` seul (couleur neutre) — l'archivage est réversible, pas une action destructive au sens rouge.

## Règles de développement

- Formules GSheet : référence absolue = `planning-lde-v2/formules.md` (jamais réinventer, recopier caractère par caractère — §5.5 SPEC)
- Bibliothèque GSheet : `gspread` (pas `google-api-python-client`)
- `data.json` : lecture/écriture atomique via `_load_data()` / `_save_data()`
- CORS : tous les endpoints renvoient `Access-Control-Allow-Origin: *`
- Payload max : 1 Mo (413 si dépassé)
- **APIs de mise en forme GSheet** (`setDataValidation`, formatting, conditional rules) : **uniquement** via `/api/gsheet/format`, appel manuel — interdit dans push/pull (§5.6 SPEC)
- Push et pull réécrivent les libellés C1–G1 des onglets Semaines et TCD avec `_tcd_headers()` (S-1 = `S<nn>`, S0→S+3 = `S<nn> (P0)`→`(P3)`, ISO week réel)

## Fin de session

Inclure la date et l'heure courantes dans le message de clôture.
`TZ="Europe/Paris" date "+%Y-%m-%d %H:%M"`
