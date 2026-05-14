# TESTS-V2 — serve-v2.py

> **Date :** 2026-05-14
> **Statut :** rédigé pendant la spec (avant implémentation), conformément à la stratégie définie dans `planning-lde/TESTS.md`.
> **Référence spec :** `SPEC-PLANNING-V2.md`

---

## Infrastructure

### Outil et style

Même style que `tests-e2e-python/cas-pratiques/` :

| Propriété | Valeur |
|-----------|--------|
| Outil | `pytest` |
| Client HTTP | `requests` |
| Port de test | **8099** (inchangé vs V1) |
| Emplacement | `tests-e2e-python/planning-lde/` |
| Commande | `pytest tests-e2e-python/planning-lde/ -v` |

### Fixture principale

Le serveur V2 lit et écrit un fichier `data.json` (plus de HTML avec sentinelles). La fixture de session crée un répertoire temporaire, y copie un `data.json` de test minimal, puis patche `serve_v2.DATA_FILE` pour pointer dessus.

```
conftest.py
  ├── data.json de test minimal (fixture statique dans tests-e2e-python/fixtures/planning-lde/)
  ├── fixture session : démarre serve-v2 sur port 8099, patche DATA_FILE
  └── fixture fonction : recopie data.json avant chaque test (isolation)
```

> **Import du serveur :** `serve-v2.py` contient un tiret — utiliser `importlib.util` comme dans `tests_serve.py` V1.

### data.json de test minimal

```json
{
  "projects": [
    {
      "id": "projet-alpha",
      "name": "Projet Alpha",
      "alias": "Alpha",
      "desc": "Projet de test.",
      "stack": "Python",
      "category": "active",
      "folder": "",
      "docs": [],
      "subprojects": [
        {
          "id": "sp-existant",
          "name": "Sous-projet existant",
          "titre": "Description courte.",
          "status": "wip",
          "qualif": "P1",
          "target": "2026-05-16",
          "owner": null,
          "charge": 8.0,
          "raf": 4.0,
          "steps": [
            { "name": "Spécification", "status": "done", "charge": 2.0, "raf": 0 },
            { "name": "Développement", "status": "wip",  "charge": 4.0, "raf": 4.0 },
            { "name": "Tests",         "status": "todo", "charge": 1.5, "raf": 1.5 },
            { "name": "Mis en ligne",  "status": "todo", "charge": 0.5, "raf": 0.5 }
          ]
        }
      ]
    }
  ]
}
```

---

## Fichiers de tests

```
tests-e2e-python/planning-lde/
  conftest.py
  test_static.py           → GET /
  test_state.py            → GET /api/state
  test_save_subproject.py  → POST /api/save-subproject
  test_add_subproject.py   → POST /api/add-subproject
  test_add_project.py      → POST /api/add-project
  test_gsheet.py           → endpoints GSheets (mockés / skipif)
  test_cors.py             → preflight OPTIONS
```

---

## test_static.py — GET /

| # | Cas | Réponse attendue |
|---|-----|-----------------|
| 1 | GET `/` | 200, Content-Type `text/html` |
| 2 | GET `/app.js` | 200, Content-Type `application/javascript` |
| 3 | GET `/ui.js` | 200 |
| 4 | GET `/api.js` | 200 |
| 5 | GET `/fichier-inexistant.xyz` | 404 |

---

## test_state.py — GET /api/state

| # | Cas | Réponse attendue |
|---|-----|-----------------|
| 1 | GET `/api/state` nominal | 200, JSON avec clés `projects` |
| 2 | Structure : `projects` est une liste | `isinstance(body["projects"], list)` |
| 3 | Projet de test présent | `body["projects"][0]["id"] == "projet-alpha"` |
| 4 | Sous-projet présent avec ses champs | `id`, `name`, `status`, `steps` présents |
| 5 | `data.json` absent au démarrage | 200, `{"projects": []}` (pas de crash) |

---

## test_save_subproject.py — POST /api/save-subproject

### Cas nominaux

| # | Cas | Payload | Effet attendu |
|---|-----|---------|--------------|
| 1 | Mise à jour du statut | `{projectId, subprojectId, status: "done"}` | 200 `{"ok": true}`, `data.json` mis à jour |
| 2 | Mise à jour du RAF | `{projectId, subprojectId, raf: 2.0}` | 200, `raf` modifié dans `data.json` |
| 3 | Mise à jour d'une étape (merge par name) | `{..., steps: [{name: "Développement", status: "done"}]}` | 200, étape "Développement" mise à jour, 3 autres étapes **inchangées** |
| 4 | Mise à jour partielle (merge) | Payload sans `charge` | `charge` existant conservé dans `data.json` |
| 5 | Mise à jour `target` | `{..., target: "2026-06-01"}` | 200, `target` mis à jour |
| 6 | Mise à jour `titre` | `{..., titre: "Nouveau titre."}` | 200, `titre` mis à jour |

### Erreurs

| # | Cas | Code attendu |
|---|-----|-------------|
| 7 | `projectId` absent du payload | 400 |
| 8 | `subprojectId` absent du payload | 400 |
| 9 | `projectId` inconnu | 404 |
| 10 | `subprojectId` inconnu dans le projet | 404 |
| 11 | JSON malformé | 400 |
| 12 | Payload vide `{}` | 400 |
| 13 | `status` invalide (valeur hors vocabulaire) | 400 |

### Cas limites

| # | Cas | Comportement attendu |
|---|-----|---------------------|
| 14 | `steps: []` dans le payload | Étapes inchangées — tableau vide = no-op (même comportement que steps absent) |
| 15 | `steps` absent du payload | Étapes existantes inchangées |
| 16 | `raf: 0` explicite | Accepté et persisté (0 est une valeur valide) |
| 17 | Deux appels successifs sur le même sous-projet | Le second écrase le premier — pas de doublon |

### Ajout d'étapes post-création (merge par name)

| # | Cas | Payload | Effet attendu |
|---|-----|---------|--------------|
| 18 | Ajout d'une étape (name inconnu) | `steps: [{name: "Recette", status: "todo", charge: 1.0, raf: 1.0}]` | 200, `data.json` contient 5 étapes (4 existantes + Recette) |
| 19 | Étape marquée N/A (= désactivée) | `steps: [{name: "Tests", status: "na"}]` | 200, étape "Tests" à `na`, 3 autres inchangées |
| 20 | Name inconnu dans merge | `steps: [{name: "Étape Inexistante", status: "done"}]` | Créée et ajoutée (même comportement que cas 18) |

### Resynchronisation de la charge

| # | Cas | Payload | Effet attendu |
|---|-----|---------|--------------|
| 21 | Save avec steps dont charges modifiées | Steps avec charges = [2, 4, 1, 0.5] | `charge` du sous-projet = 7.5 dans `data.json` |
| 22 | Étape N/A ignorée dans le calcul | Steps = [{charge:2,status:"na"}, {charge:4}] | `charge` du sous-projet = 4 (étape na exclue) |
| 23 | Steps absent du payload | Payload sans `steps` | `charge` du sous-projet inchangée |

---

## test_add_subproject.py — POST /api/add-subproject

### Cas nominaux

| # | Cas | Payload | Effet attendu |
|---|-----|---------|--------------|
| 1 | Ajout minimal | `{projectId, name}` | 200, `{"ok": true, "id": "..."}`, sous-projet présent dans `data.json` |
| 2 | `id` généré = slug du `name` | `name: "Migration GitLab"` | `id == "migration-gitlab"` |
| 3 | Étapes standardisées créées par le serveur | Payload avec `steps: []` | 4 étapes par défaut présentes dans `data.json` après l'appel |
| 4 | Étapes explicites fournies | `{..., steps: [{name: "Analyse", ...}]}` | Étapes fournies utilisées, pas les defaults |
| 5 | Ajout avec `qualif` | `{..., qualif: "P2"}` | `target` calculé automatiquement (vendredi S+3) |
| 6 | Deux sous-projets même nom | Second appel | `id` suffixé `-2` |

### Erreurs

| # | Cas | Code attendu |
|---|-----|-------------|
| 7 | `projectId` absent | 400 |
| 8 | `name` absent | 400 |
| 9 | `projectId` inconnu | 404 |
| 10 | JSON malformé | 400 |

### Cas limites

| # | Cas | Comportement attendu |
|---|-----|---------------------|
| 11 | `name` avec caractères spéciaux | Slug nettoyé (`é` → `e`, espaces → `-`) |
| 12 | `name` vide `""` | 400 |
| 13 | `qualif` absente | `target` absent ou null (pas de crash) |

---

## test_add_project.py — POST /api/add-project

### Cas nominaux

| # | Cas | Payload | Effet attendu |
|---|-----|---------|--------------|
| 1 | Ajout minimal | `{name, alias}` | 200 `{"ok": true}`, projet présent dans `data.json` |
| 2 | `id` généré = slug du `name` | `name: "Nouveau Projet"` | `id == "nouveau-projet"` |
| 3 | `subprojects: []` à la création | — | Tableau vide, pas d'erreur |

### Erreurs

| # | Cas | Code attendu |
|---|-----|-------------|
| 4 | `name` absent | 400 |
| 5 | Projet avec même `id` déjà existant | `id` suffixé `-2` (cohérent avec `add-subproject`) |
| 6 | JSON malformé | 400 |

---

## test_gsheet.py — Endpoints GSheets

### Bibliothèque : `gspread`

Le serveur V2 utilise **gspread** (pas `google-api-python-client`). Les mocks ciblent l'API gspread.

### Stratégie

Les endpoints GSheets (`/api/gsheet/init`, `/api/sync-to-gsheet`, `/api/pull-from-gsheet` et leurs previews) font des appels réseau réels vers Google Sheets. Ils sont **mockés ou skipés** dans la suite automatique.

```python
import pytest

GSHEET_AVAILABLE = False  # passer à True pour tests d'intégration manuels

skip_gsheet = pytest.mark.skipif(
    not GSHEET_AVAILABLE,
    reason="Tests GSheets désactivés — nécessitent credentials OAuth et spreadsheet de test"
)
```

### GET /api/gsheet/status

| # | Cas | Comportement attendu |
|---|-----|---------------------|
| 1 | Sans credentials | 200, `{"connected": false}` (pas de crash) |
| 2 | Avec credentials valides (skipif) | 200, `{"connected": true}` |

### POST /api/gsheet/init (mocké)

| # | Cas | Mock | Assertion |
|---|-----|------|-----------|
| 3 | Init nominale | `gspread.open_by_key` mocké → feuille vide | 200 `{"ok": true}` |
| 4 | Spreadsheet introuvable | Mock lève `gspread.SpreadsheetNotFound` | 404 ou 500 avec message clair |
| 5 | `spreadsheet_id` absent de la config | — | 500 avec message clair |

> **Règle §5.6 :** vérifier dans le mock que **aucune API de formatage** (`batchUpdate` avec `format`, `setDataValidation`, `addConditionalFormatRule`) n'est appelée — uniquement `values.update` / `values.append`.

### POST /api/pull-from-gsheet (mocké) — depuis Tâches

| # | Cas | Mock | Assertion |
|---|-----|------|-----------|
| 6 | Pull nominal | Retourne des lignes valides (projet + sous-projet existants) | 200, `data.json` mis à jour avec charge/RAF |
| 7 | Pull ne modifie pas les statuts | Ligne GSheet avec colonne statut différente | Statut dans `data.json` **inchangé** |
| 8 | `target` modifiée manuellement dans Tâches col E | Ligne GSheet avec date différente en col E | `target` dans `data.json` **mis à jour** |
| 9 | Nouveau sous-projet dans GSheet | Ligne avec sous-projet inconnu | Créé dans `data.json` |
| 10 | Ligne GSheet orpheline (projet inconnu) | — | Ignorée sans crash |

### POST /api/pull-from-tcd (mocké)

| # | Cas | Mock TCD | Assertion |
|---|-----|----------|-----------|
| 11 | RAF déplacé de S-1 vers S+1 | Ligne "- sp-existant" : S-1=0, S0=0, S+1=8 | `raf=8`, `target`=vendredi S+1 dans `data.json` |
| 12 | RAF réparti sur plusieurs semaines | S0=4, S+1=4 | `raf=8`, `target`=vendredi S+1 (dernière semaine non nulle) |
| 13 | Toutes colonnes semaines à 0 | S-1=0…S+3=0 | `raf=0`, `target` **inchangée** |
| 14 | Ligne projet (sans "- ") | Ligne sans préfixe "- " | Ignorée — seules les lignes sous-projet sont lues |
| 15 | Pull TCD ne modifie pas les statuts ni les étapes | — | Statuts et steps dans `data.json` **inchangés** |
| 16 | Réponse : nombre de sous-projets mis à jour | 3 lignes "- " trouvées | `{"ok": true, "updated": 3}` |

---

## test_cors.py — Preflight OPTIONS

| # | Cas | Réponse attendue |
|---|-----|-----------------|
| 1 | OPTIONS `/api/save-subproject` | 200, header `Access-Control-Allow-Origin` présent |
| 2 | OPTIONS `/api/add-subproject` | 200 |
| 3 | GET avec Origin non autorisée | Headers CORS présents (politique définie dans serve-v2.py) |

---

## Cas limites transversaux

| # | Cas | Endpoint(s) | Comportement attendu |
|---|-----|-------------|---------------------|
| T1 | Payload > 1 Mo | Tous les POST | 413 ou 400 |
| T2 | `data.json` corrompu (JSON invalide) | GET /api/state, POST save/add | 500 avec message clair, pas d'exception non catchée |
| T3 | `data.json` absent | GET /api/state | 200 `{"projects": []}` |
| T4 | `data.json` absent | POST /api/save-subproject | 404 (rien à modifier) |
| T5 | Requête non-JSON sur endpoint POST | Tous les POST | 400 |
| T6 | Méthode non autorisée (ex: DELETE /) | — | 405 |

---

## Transition vers la suite définitive

Une fois la suite V2 stable et validée :

1. `tests_serve.py` (V1, unittest) est **retiré explicitement** — pas d'abandon silencieux.
2. La suite pytest `tests-e2e-python/planning-lde/` devient la référence unique.
3. La migration est notée dans `planning-lde/TESTS.md`.

---

## Référence

- Style et fixtures : `tests-e2e-python/cas-pratiques/`
- Spec globale des tests : `tests-e2e-python/SPEC.md`
- Spec serveur V2 : `planning-lde-v2/SPEC-PLANNING-V2.md`
- Stratégie de test V2 : `planning-lde/TESTS.md`
