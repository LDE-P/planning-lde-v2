# SPEC — Vue "Docs" dans le Planning LDE V2

> **Date :** 2026-05-15 (v4 — après audit Claude Code, résolution A9/A10/A11)
> **Auteur :** Cowork (Claude) — session LDE
> **Projet :** Planning LDE V2
> **Sous-projet :** Gestion des MD — Étape 1 : Spécification
> **Statut :** Tous points ouverts résolus — prête pour implémentation

---

## 1. Objectif

Rendre les fichiers Markdown de travail (specs, audits, bilans, notes de session) directement accessibles depuis le dashboard Planning LDE V2, organisés par projet, avec des liens d'ouverture rapide (TextMate, Finder).

**Problème actuel :** ces fichiers ne sont accessibles que via le Finder macOS ou en naviguant dans les sessions Cowork. Il n'existe pas de vue d'ensemble par projet.

**Résultat attendu :** un onglet "Docs" dans `DASHBOARD-V2.html` affichant tous les documents MD catalogués, groupés par projet, avec métadonnées (type, statut, description courte) et liens d'ouverture. Le catalogue est alimenté manuellement et maintenu à jour via un process de fin de session Cowork.

---

## 2. Périmètre de la feature

### Ce qui est inclus (V1)

- Catalogue de documents MD géré **manuellement** dans `data.json`
- Vue "Docs" accessible via un onglet dans le header du dashboard
- Pour chaque document : type, titre, description, statut, date, lien vers sous-projet associé
- Compteur de docs dans l'en-tête de chaque bloc projet
- Lien d'ouverture dans **TextMate** (protocole `txmt://` — confirmé disponible)
- Lien d'ouverture dans **Finder** (révèle le fichier) via le nouvel endpoint `/api/open-file`
- Projets sans docs **masqués par défaut** (toggle pour les afficher)
- **Filtres** par type (spec/audit/tests/bilan/notes/autre) et par statut (draft/final/archived)
- CRUD basique : ajouter, modifier, supprimer un document (modal)
- **Intégration process Cowork** : prompt de fin de session dans `CLAUDE.md` pour alimenter le catalogue

### Ce qui n'est pas inclus (hors périmètre V1)

- Synchronisation Google Sheets pour les docs
- Affichage du contenu du fichier MD dans le dashboard
- Auto-scan du dossier GIT *(envisagé en V2 — voir §11)*

---

## 3. Modèle de données

### 3.1 Enrichissement du champ `docs` dans `data.json`

Le champ `docs` existe déjà dans chaque projet (actuellement `[]`). Il passe d'un tableau de chaînes à un tableau d'objets.

**Schéma d'un document :**

```json
{
  "id": "spec-planning-v2",
  "file": "planning-lde-v2/SPEC-PLANNING-V2.md",
  "title": "Spécification Planning LDE V2",
  "desc": "Architecture data.json, endpoints API, modèle Projet → SP → Étape.",
  "type": "spec",
  "status": "final",
  "date": "2026-05-10",
  "subproject": "simplification-v2"
}
```

**Champs :**

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `id` | string | ✅ | Slug kebab-case unique par projet. Généré automatiquement depuis `title` si absent (voir §3.3) |
| `file` | string | ✅ | Chemin relatif depuis la racine `GIT/` (ex : `planning-lde-v2/SPEC-PLANNING-V2.md`) |
| `title` | string | ✅ | Titre court affiché dans la liste |
| `desc` | string | ❌ | Description en une phrase : objectif, contenu principal |
| `type` | string | ✅ | Valeur **strictement** parmi : `spec`, `audit`, `tests`, `bilan`, `notes`, `autre` — toute autre valeur est rejetée (400) |
| `status` | string | ✅ | Valeur **strictement** parmi : `draft`, `final`, `archived` — toute autre valeur est rejetée (400) |
| `date` | string | ❌ | Format `YYYY-MM-DD`. Optionnel : absence acceptée (pas de tri possible). Si fournie, tout autre format → 400 |
| `subproject` | string\|null | ❌ | `id` du SP associé — validation au check d'intégrité, pas à la saisie |

**Chemin absolu** résolu côté serveur : `GIT_ROOT + "/" + doc.file`. Le `GIT_ROOT` est exposé dans `/api/state` (voir §6).

### 3.2 Exemple de projet enrichi

```json
{
  "id": "planning-lde-v2",
  "name": "Planning LDE",
  "alias": "Planning",
  "docs": [
    {
      "id": "spec-planning-v2",
      "file": "planning-lde-v2/SPEC-PLANNING-V2.md",
      "title": "Spécification Planning LDE V2",
      "desc": "Architecture data.json, endpoints API, modèle Projet → SP → Étape.",
      "type": "spec",
      "status": "final",
      "date": "2026-05-10",
      "subproject": "simplification-v2"
    },
    {
      "id": "audit-v2-2026-05-14",
      "file": "planning-lde-v2/AUDIT-2026-05-14.md",
      "title": "Audit Planning LDE V2 (14/05/2026)",
      "desc": "Audit complet : robustesse data.json, couverture tests GSheet, dette UI naissante.",
      "type": "audit",
      "status": "final",
      "date": "2026-05-14",
      "subproject": null
    }
  ],
  "subprojects": [ "..." ]
}
```

### 3.3 Génération automatique de l'`id`

Si le client ne fournit pas d'`id`, le serveur le génère depuis `title` selon l'algorithme :

```python
import unicodedata, re

def _slugify(title: str) -> str:
    # 1. Décomposer les accents (NFKD) puis retirer les diacritiques
    s = unicodedata.normalize("NFKD", title)
    s = s.encode("ascii", "ignore").decode("ascii")
    # 2. Minuscules
    s = s.lower()
    # 3. Remplacer toute séquence non [a-z0-9] par un seul "-"
    s = re.sub(r"[^a-z0-9]+", "-", s)
    # 4. Trim les "-" en début/fin
    return s.strip("-")
```

Résultats de référence (stables — `test_add_doc #2b/2c/2d` s'y appuie) :

| `title` | `id` généré |
|---------|------------|
| `"Mon Audit Mai"` | `"mon-audit-mai"` |
| `"Spec V2 — partie 2 (final)"` | `"spec-v2-partie-2-final"` |
| `"Bilan — 14/05/2026"` | `"bilan-14-05-2026"` |
| `"Étude préalable"` | `"etude-prealable"` |

Si le slug généré est vide (titre purement non-alphanumérique) → 400 : `"Impossible de générer un id depuis ce titre — fournis un id explicite"`.

### 3.4 Tri par défaut de la vue Docs

Dans la vue UI, les docs d'un projet sont triés par **date décroissante** (plus récent en premier). Les docs sans `date` apparaissent en queue, dans leur ordre d'insertion dans `data.json`.

Le serveur ne réordonne pas `data.json` : le tri est appliqué côté JS au rendu (`renderDocsView()`).

### 3.5 Compatibilité avec l'ancien format

Le champ `docs` était précédemment un tableau de chaînes. Comportement adopté :

- **À la lecture** (`/api/state`, dashboard) : les entrées non-objet sont filtrées silencieusement — elles n'apparaissent pas dans la vue Docs
- **Au check d'intégrité** : signalées par `"doc non-objet dans <projet>"` (voir §8) — l'utilisateur peut les nettoyer manuellement
- **À l'écriture** (`/api/add-doc`, `/api/save-doc`, `/api/remove-doc`) : opèrent uniquement sur les entrées de type `dict` ; les chaînes sont préservées telles quelles dans `data.json` jusqu'à nettoyage manuel
- **Pas de migration automatique** : évite toute perte de données silencieuse tout en n'empêchant pas le bon fonctionnement de la V1 sur des `data.json` non encore migrés

---

## 4. Backend — Nouveaux endpoints

### 4.1 Endpoint : `/api/add-doc`

**Méthode :** `POST`
**Corps :**

```json
{
  "project_id": "planning-lde-v2",
  "doc": {
    "file": "planning-lde-v2/SPEC-DOCS-MD.md",
    "title": "Spécification Vue Docs",
    "desc": "Vue catalogue des fichiers MD dans le dashboard V2.",
    "type": "spec",
    "status": "draft",
    "date": "2026-05-15",
    "subproject": "gestion-des-md"
  }
}
```

**Comportement :**
1. Valide la présence des champs obligatoires : `project_id`, `file`, `title`, `type`, `status`
2. Valide que `type` ∈ `{spec, audit, tests, bilan, notes, autre}` et `status` ∈ `{draft, final, archived}`
3. Si `date` fournie, valide le format `YYYY-MM-DD` (regex `^\d{4}-\d{2}-\d{2}$`)
4. Résout `abs = Path(GIT_ROOT, file).resolve()` ; vérifie `abs.is_relative_to(GIT_ROOT)` (anti-traversée) puis `abs.is_file()`
5. Si `docs` absent du projet (champ manquant), l'initialise à `[]` avant d'ajouter
6. Génère l'`id` via `_slugify(title)` si absent (§3.3) ; vérifie l'unicité au sein du projet
7. Ajoute le doc, sauvegarde `data.json`, retourne `{ok: true, doc: {...}}`

**Erreurs (400) :** champ obligatoire manquant ou `title` vide — `type` ou `status` hors vocabulaire — `date` au mauvais format — `project_id` introuvable — `file` hors `GIT_ROOT` ou inexistant — `id` déjà existant dans le projet — slug généré vide

### 4.2 Endpoint : `/api/save-doc`

**Méthode :** `POST`
**Corps :**

```json
{
  "project_id": "planning-lde-v2",
  "doc_id": "audit-v2-2026-05-14",
  "patch": {
    "title": "...",
    "desc": "...",
    "status": "archived"
  }
}
```

**Comportement :** patch les champs fournis (tous optionnels sauf `project_id` et `doc_id`). Validation **symétrique** à `/api/add-doc` sur les champs présents dans `patch` :
- Si `patch.type` est fourni → doit ∈ `{spec, audit, tests, bilan, notes, autre}`, sinon 400
- Si `patch.status` est fourni → doit ∈ `{draft, final, archived}`, sinon 400
- Si `patch.date` est fournie et non vide → format `YYYY-MM-DD` strict, sinon 400 (chaîne vide acceptée pour effacer la date)
- Si `patch.title` est fourni → ne peut pas être vide, sinon 400
- Si `patch.file` est fourni → même validation anti-traversée qu'à l'ajout (`Path(GIT_ROOT, file).resolve().is_relative_to(GIT_ROOT)` + `is_file()`)
- Champs inconnus dans `patch` → ignorés silencieusement (P4)

Retourne `{ok: true}`.

### 4.3 Endpoint : `/api/remove-doc`

**Méthode :** `POST`
**Corps :** `{"project_id": "...", "doc_id": "..."}`
**Comportement :** supprime le doc de `data.json`. Retourne `{ok: true}`.

### 4.4 Endpoint : `/api/open-file` *(nouveau)*

**Méthode :** `POST`
**Corps :** `{"file": "planning-lde-v2/SPEC-PLANNING-V2.md"}`

**Comportement :**
1. Résout le chemin absolu : `abs = Path(GIT_ROOT, file).resolve()`
2. Vérifie que `abs` est sous `GIT_ROOT` : `abs.is_relative_to(GIT_ROOT)` → 400 sinon (traversée)
3. Vérifie que le fichier existe : `abs.is_file()` → 400 sinon
4. Exécute `subprocess.Popen(["open", "-R", str(abs)])` — args en liste (`shell=False`), pas d'injection shell possible. La validation `is_relative_to(GIT_ROOT)` à l'étape 2 empêche d'ouvrir des fichiers hors périmètre.
5. Retourne `{ok: true}`

**Pourquoi un nouvel endpoint plutôt que réutiliser `/api/open-folder` :** l'endpoint existant attend un `projectId` et résout un dossier projet via un mapping statique ou `data.json`. Il ne peut pas prendre un chemin de fichier arbitraire. Les deux endpoints ont des responsabilités distinctes et coexistent sans conflit.

---

## 5. UI — Vue "Docs"

### 5.1 Navigation par onglets

Ajouter un sélecteur de vue dans le header, en dessous du titre `<h1>` et au-dessus de la barre de filtres actuelle :

```
[ Projets ]  [ Docs ]
```

- **Onglet "Projets"** (défaut) : comportement actuel, inchangé
- **Onglet "Docs"** : affiche la vue catalogue décrite ci-dessous
- La barre de filtres (wip/todo/spec…) et la barre GSheet restent visibles uniquement en vue "Projets"
- L'onglet "Docs" affiche un compteur global dans son label : `Docs (47)`

### 5.2 Structure de la vue Docs

```
[ 🔲 Afficher projets sans docs ]                   [ + Ajouter un doc ]

Planning LDE — 5 docs  ▾
  ┌──────────────────────────────────────────────────────────────────┐
  │ [SPEC] Spécification Planning LDE V2        [final]  2026-05-10  │
  │ Architecture data.json, endpoints API, modèle Projet → SP → Étape│
  │ SP : V2                         [↗ TextMate]  [📁 Finder]  [✎] [🗑]│
  └──────────────────────────────────────────────────────────────────┘
  ┌──────────────────────────────────────────────────────────────────┐
  │ [AUDIT] Audit V2 (14/05/2026)               [final]  2026-05-14  │
  │ Audit complet : robustesse data.json, tests GSheet, dette UI.    │
  │                                 [↗ TextMate]  [📁 Finder]  [✎] [🗑]│
  └──────────────────────────────────────────────────────────────────┘

Dashboard Datamart — 8 docs  ▾
  ...

Examens V7 — 0 docs  [masqué par défaut — visible si toggle activé]
```

**Barre de filtres** (au-dessus des accordéons, persistée en `localStorage`) :

```
Type :   [Tous] [Spec] [Audit] [Tests] [Bilan] [Notes] [Autre]
Statut : [Tous] [Brouillon] [Final] [Archivé]
[ 🔲 Afficher projets sans docs ]
```

- Les filtres type et statut sont combinés (ET logique) : seuls les docs correspondant aux deux critères sont affichés
- Un projet dont tous les docs sont masqués par les filtres est traité comme "sans docs" — il obéit au toggle
- Les docs archivés sont **masqués par défaut** (filtre statut initialisé sur `draft + final`) — activer "Archivé" pour les voir
- Les sélections sont mémorisées en `localStorage` entre les rechargements

**Compteur dans l'en-tête projet :** `Nom du projet — N docs` (avec `N` = nombre total de docs, indépendant des filtres actifs).

### 5.3 Carte document (doc card)

```
┌──────────────────────────────────────────────────────────────────┐
│ [TYPE] TITRE                              [STATUS]    YYYY-MM-DD  │
│ Description courte en une phrase.                                 │
│ SP associé : Nom SP (clic → panneau détail SP)                    │
│                                   [↗ TextMate] [📁 Finder] [✎] [🗑] │
└──────────────────────────────────────────────────────────────────┘
```

**Comportement du lien SP :** clic → bascule vers l'onglet "Projets" + ouvre le panneau de détail du sous-projet ciblé (même comportement que le clic sur une carte SP dans la vue Projets). Si le SP n'existe plus (`subproject` orphelin signalé par le check d'intégrité), le lien est rendu inactif (texte gris, pas de clic).

**Badges type** :

| Type | Label | Couleur |
|------|-------|---------|
| `spec` | SPEC | Bleu (`--accent`) |
| `audit` | AUDIT | Orange (`--spec`) |
| `tests` | TESTS | Violet (`--review`) |
| `bilan` | BILAN | Vert (`--done`) |
| `notes` | NOTES | Gris neutre |
| `autre` | AUTRE | Gris clair |

**Badges status** :

| Status | Label | Style |
|--------|-------|-------|
| `draft` | Brouillon | Fond orange clair |
| `final` | Final | Fond vert clair |
| `archived` | Archivé | Fond gris, texte atténué |

### 5.4 Lien TextMate (résolu)

Le protocole `txmt://` est confirmé disponible. Implémentation :

```html
<a href="txmt://open?url=file:///Users/laurentdenis/Documents/GIT/planning-lde-v2/SPEC-PLANNING-V2.md"
   title="Ouvrir dans TextMate">↗ TextMate</a>
```

Le chemin absolu est construit côté JS : `state.git_root + "/" + doc.file` (URL-encodé pour les espaces).

### 5.5 Lien Finder

Bouton "📁 Finder" → `POST /api/open-file` avec `{"file": doc.file}`. Le serveur exécute `open -R /chemin/absolu` qui révèle le fichier sélectionné dans son dossier Finder.

### 5.6 Gestion des documents (CRUD)

**Ajout :** bouton "+ Ajouter un doc" dans chaque en-tête de projet (et bouton global en haut de vue) → modal avec les champs : fichier (chemin relatif depuis `GIT/`), titre, description, type (dropdown), status (dropdown), date (défaut : aujourd'hui), sous-projet associé (dropdown optionnel parmi les SP du projet).

**Modification :** icône `✎` sur la carte → même modal en mode édition pré-rempli. Le champ `file` est éditable (utile pour corriger une faute de frappe ou suivre un renommage manuel du `.md`) — le serveur revalide existence + confinement `GIT_ROOT` à chaque patch.

**Suppression :** icône `🗑` → confirmation modale → appel `/api/remove-doc`.

---

## 6. Données du serveur — `GIT_ROOT`

### 6.1 Variable module `GIT_ROOT`

Ajouter dans `serve-v2.py`, juste après la définition de `BASE_DIR` :

```python
GIT_ROOT = BASE_DIR.parent.resolve()
```

**Uniformisation des usages existants :** les deux occurrences actuelles de `BASE_DIR.parent.resolve()` dans `serve-v2.py` (ligne 809 dans `_resolve_project_path`, ligne 1219 dans `_handle_open_folder`) doivent être remplacées par `GIT_ROOT`. Sans cette uniformisation, le patch `serve_v2.GIT_ROOT = data_dir` dans `conftest.py` ne couvrirait que les nouveaux endpoints docs et laisserait `_resolve_project_path` / `_handle_open_folder` accrochés au vrai filesystem en test.

### 6.2 Exposition dans `/api/state`

Le serveur ajoute `"git_root": "/Users/laurentdenis/Documents/GIT"` (valeur de la variable module `GIT_ROOT`, sérialisée en `str`) à la racine de la réponse de `/api/state`.

Côté JS, `app.js` stocke `state.git_root` au chargement. `ui.js` l'utilise pour construire les URLs `txmt://`.

---

## 7. Intégration process Cowork — Alimentation du catalogue en fin de session

### Objectif

Éviter que les fichiers MD produits lors d'une session restent hors catalogue. **L'agent en charge de la session (Cowork ou Claude Code)** doit proposer proactivement de les enregistrer au moment où LDE donne un signal de fin ou de pause.

### Règle à ajouter dans `CLAUDE.md` (checklist fin de session, étape 3bis)

Insérer entre l'étape 3 (vérification cohérence `data.json`) et l'étape 4 (date, objectif, fichiers) :

```
3bis. **Docs MD produits dans la session** — Si un ou plusieurs fichiers `.md` ont été
créés ou significativement modifiés (spec, audit, bilan, tests, notes…), et qu'ils ne
sont pas encore dans `data.json` (champ `docs` du projet concerné) :
  1. Lister les fichiers concernés avec leur chemin relatif depuis `GIT/`
  2. Pour chacun, proposer à LDE : titre, description courte (1 phrase), type
     (spec/audit/tests/bilan/notes/autre), statut (draft/final), sous-projet associé
  3. Une fois confirmé par LDE, écrire l'entrée dans `data.json` via l'outil `Edit`
     (ou `/api/add-doc` si le serveur tourne)

> Cette étape est optionnelle si aucun fichier MD n'a été produit dans la session,
> ou si les fichiers sont purement techniques (CLAUDE.md, README, formules.md…).
```

### Comportement attendu de Claude

**Déclencheur :** signal de fin ou de pause de LDE (« on s'arrête là », « stay tuned »…).

**Prompt type de l'agent (Cowork ou Claude Code) :**

> « Dans cette session, j'ai créé/modifié ces fichiers MD :
> - `planning-lde-v2/SPEC-DOCS-MD.md`
> - `suivi-qualite/bilans/2026-05-15.md`
>
> Est-ce que tu veux les ajouter au catalogue Docs ? Pour chacun, confirme ou ajuste :
> - SPEC-DOCS-MD.md → type `spec`, statut `draft`, desc : "Spécification de la vue Docs dans le dashboard V2." → SP : `gestion-des-md`
> - 2026-05-15.md → type `bilan`, statut `final`, desc : "Bilan de session du 2026-05-15." → pas de SP »

**LDE valide, ajuste ou passe.** Claude écrit ensuite les entrées dans `data.json`.

### Cas particuliers

- **Fichiers exclus du catalogue** : fichiers techniques de référence — `CLAUDE.md`, `README.md`, conventions, licences, changelogs, et tout fichier dont le nom ou le contenu indique qu'il s'agit d'une infrastructure IA ou de documentation de dépendances (pas besoin de liste ad hoc : la règle "est-ce un livrable de session ou un fichier de référence technique ?" suffit)
- Si le projet associé n'est pas encore dans `data.json`, le signaler à LDE plutôt que d'inventer une entrée
- Si LDE dit « passe » ou « pas maintenant », ne pas insister — noter éventuellement dans le message de clôture

---

## 8. Fichiers impactés

| Fichier | Nature des changements |
|---------|----------------------|
| `data.json` | `docs` passe de `string[]` à `object[]` (backward-compatible : `[]` reste valide) |
| `serve-v2.py` | Ajout de 4 endpoints : `/api/add-doc`, `/api/save-doc`, `/api/remove-doc`, `/api/open-file` + `git_root` dans `/api/state` |
| `DASHBOARD-V2.html` | Ajout du sélecteur d'onglets dans le header |
| `ui.js` | Ajout de `renderDocsView()`, `renderDocCard()`, gestion du switch d'onglet, modal add/edit doc, toggle projets vides |
| `api.js` | Ajout des wrappers : `addDoc()`, `saveDoc()`, `removeDoc()` |
| `CLAUDE.md` (racine GIT) | Ajout de l'étape 3bis dans la checklist fin de session |

**Fichiers NON modifiés :** `app.js` (init inchangé), `serve-v2.conf.json`, tests existants.

### Extension du check d'intégrité (checklist fin de session — étape 3)

Le script de vérification existant dans `CLAUDE.md` doit être étendu pour couvrir les docs :

```python
# À ajouter après la vérification ids SP existante
for p in data['projects']:
    seen_doc_ids = set()
    for d in p.get('docs', []):
        if not isinstance(d, dict):
            errors.append(f'doc non-objet dans {p["name"]}')
            continue
        if 'id' not in d:
            errors.append(f'Doc sans id : {p["name"]} / {d.get("title","?")}')
        elif d['id'] in seen_doc_ids:
            errors.append(f'Id doc en double : {p["name"]} / {d["id"]}')
        else:
            seen_doc_ids.add(d['id'])
        sp_id = d.get('subproject')
        if sp_id:
            sp_ids = {s['id'] for s in p.get('subprojects', []) if 'id' in s}
            if sp_id not in sp_ids:
                errors.append(f'Doc orphelin : {p["name"]} / {d["id"]} → SP "{sp_id}" introuvable')
```

---

## 9. Points ouverts résiduels

| # | Question | Statut |
|---|----------|--------|
| A1 | Protocole `txmt://` disponible ? | ✅ **Résolu** — lien direct `txmt://` |
| A2 | `/api/open-folder` réutilisable pour un fichier ? | ✅ **Résolu** — non réutilisable → nouvel endpoint `/api/open-file` avec `open -R` |
| A3 | `git_root` dans `/api/state` | ✅ **Résolu** — ajout dans `/api/state` |
| A4 | Projets sans docs masqués par défaut ? | ✅ **Résolu** — masqués, toggle pour afficher |
| A5 | Compteur de docs dans l'en-tête projet ? | ✅ **Résolu** — compteur affiché |
| A6 | Compatibilité ancien format `docs: ["string"]` ? | ✅ **Résolu** — filtrage silencieux à la lecture, voir §3.5 |
| A7 | Règle de normalisation du slug ? | ✅ **Résolu** — algorithme `_slugify()` en §3.3 |
| A8 | Tri par défaut de la vue Docs ? | ✅ **Résolu** — date décroissante, sans date en queue, voir §3.4 |
| A9 | `save-doc` revalide-t-il `type`/`status`/`date` ? | ✅ **Résolu** — oui, validation symétrique à `add-doc`, voir §4.2 |
| A10 | Variable module `GIT_ROOT` vs `BASE_DIR.parent.resolve()` inline existant ? | ✅ **Résolu** — uniformisation : les deux occurrences inline existantes sont remplacées par `GIT_ROOT`, voir §6.1 |
| A11 | Comportement du clic sur "SP associé" dans la doc card ? | ✅ **Résolu** — bascule onglet Projets + ouverture panneau détail SP, voir §5.3 |

---

## 10. Estimation de charge (indicative)

| Tâche | Estimation |
|-------|-----------|
| Backend (nouveaux endpoints + git_root dans `/api/state`) | 1,5 h |
| UI — onglet tabs + vue Docs + compteurs + toggle | 2 h |
| UI — modal add/edit doc | 1 h |
| Intégration `CLAUDE.md` (ajout étape 3bis) | 0,25 h |
| Initialisation catalogue (~35 docs existants — ~2–3 min/doc avec relecture) | 1,5 h |
| Tests e2e nouveaux endpoints | 1 h |
| Marge (imprévus, ajustements UI, campagne init) | 1 h |
| **Total** | **~8,25 h** |

---

## 11. Évolution future envisagée — Auto-scan

### Contexte

Une exploration réalisée lors de la session de spécification (2026-05-15) montre que le corpus MD du dossier GIT contient ~150 fichiers significatifs (hors node_modules, .venv, wp-includes…), dont un cœur de cible de ~35 fichiers (spec + audit + tests + plan). L'auto-scan pur pose trois problèmes : attribution ambiguë au bon projet, extraction automatique imparfaite des titres/descriptions, et 43 fichiers non catégorisés nécessitant un tri manuel.

### Approche recommandée pour une V2

**Import automatique une fois, maintenance manuelle ensuite.** Un endpoint `/api/scan-docs` parcourt le dossier GIT avec les exclusions standards (noise, CLAUDE.md, dossiers machine), applique les patterns de nommage (`SPEC-*`, `AUDIT-*`, `TESTS-*`, `PLAN-*`, `suivi-qualite/bilans/`…), extrait le titre depuis le premier H1 du fichier, et retourne la liste des fichiers **non encore présents dans `data.json`** (diff avec le catalogue existant).

Le dashboard affiche ces candidats dans un panneau "Docs à cataloguer" : LDE confirme ou rejette chaque fichier, ajuste titre/description/type si besoin, choisit le projet d'appartenance. Ce qui est validé entre dans `data.json` via `/api/add-doc`.

**Charge estimée :** +1 à 1,5 h (endpoint scan + UI de validation). À planifier comme étape 5 ou 6 du sous-projet Gestion des MD, une fois la V1 stabilisée.

---

## 12. Séquence d'implémentation recommandée

1. Résoudre le point ouvert A2 (comportement `/api/open-folder`)
2. Implémenter les endpoints backend (`/api/add-doc`, `/api/save-doc`, `/api/remove-doc`) + `git_root` dans `/api/state`
3. Enrichir `data.json` pour 2–3 projets pilotes (Planning LDE V2, Dashboard Datamart) — valide le schéma
4. Implémenter la vue UI (onglet + cartes + compteurs + toggle) sans le CRUD
5. Ajouter le CRUD (modal add/edit/delete)
6. Ajouter l'étape 3bis dans `CLAUDE.md`
7. Écrire les tests e2e des nouveaux endpoints
8. Remplir le catalogue pour tous les projets
9. *(futur)* Endpoint `/api/scan-docs` + UI de validation
