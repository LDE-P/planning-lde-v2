# SPEC — Archivage des projets et sous-projets

> **Statut :** VALIDÉ — prêt pour implémentation
> **Date :** 2026-05-16 (validée Ping-Pong Cowork ↔ Claude Code)
> **Projet :** Planning LDE V2 (`planning-lde-v2/`)
> **Implémentation :** Claude Code — après validation de cette spec + TESTS-ARCHIVAGE.md

---

## 1. Objectif

Le dashboard s'allonge continuellement au fil des projets et sous-projets terminés. La feature d'archivage permet de retirer de la vue courante les projets/SP qui n'ont plus besoin d'apparaître, tout en les conservant accessibles dans un onglet dédié.

---

## 2. Fichier de données : `data-archives.json`

- **Chemin :** `planning-lde-v2/data-archives.json`
- **Structure :** identique à `data.json` — `{ "projects": [...] }`
- **Création :** automatique à la première opération d'archivage (si le fichier n'existe pas)
- **Gitignore :** oui — à ajouter dans `.gitignore` au même niveau que `data.json`
- **Accès :** via les helpers `_load_archives()` / `_save_archives()` (symétrique à `_load_data()` / `_save_data()`)

### Règle de stockage dans les archives

Quand un SP est archivé, il est rangé dans l'entrée projet correspondante dans `data-archives.json` :
- Si le projet existe déjà dans les archives → le SP est **ajouté** à `archives_project.subprojects`
- Si le projet n'existe pas encore dans les archives → une entrée projet est **créée** (copie des métadonnées : `id`, `name`, `alias`, `desc`, `stack`, `category`, `folder`, `docs: []`) avec ce SP dans `subprojects`

---

## 3. Garantie d'unicité des IDs

Les IDs de projets et sous-projets sont des slugs générés par `_unique_id()`. Pour éviter les collisions entre `data.json` et `data-archives.json` (cas : projet archivé, puis nouveau projet créé avec le même nom) :

- `_handle_add_project` : enrichir `existing_ids` avec les IDs de `data-archives.json`
- `_handle_add_subproject` : enrichir `existing_ids` avec les IDs de SPs archivés pour ce projet (si le projet existe dans les archives)

```python
# Dans _handle_add_project
archives = _load_archives()
existing_ids |= {p['id'] for p in archives.get('projects', [])}

# Dans _handle_add_subproject
archives = _load_archives()
arch_proj = next((p for p in archives.get('projects', []) if p['id'] == project_id), None)
if arch_proj:
    existing_ids |= {s['id'] for s in arch_proj.get('subprojects', [])}
```

---

## 4. Nouveaux endpoints Python (`serve-v2.py`)

### 4.1 `GET /api/archives`

Retourne le contenu de `data-archives.json`.

```json
// Réponse 200
{ "projects": [...] }
```

### 4.2 `POST /api/archive-subproject`

Archive un sous-projet. Le projet reste dans `data.json`.

**Body :** `{ "projectId": "...", "subprojectId": "..." }`

**Comportement :**
1. Valide que le projet et le SP existent dans `data.json`
2. Copie le SP dans `data-archives.json` (sous son projet parent)
3. Retire le SP de `data.json[project.subprojects]`
4. Si le projet n'a plus de SP après retrait : **ne pas archiver automatiquement** — renvoyer `{ "ok": true, "projectEmpty": true }` pour que l'UI propose la deuxième confirmation côté client
5. Sauvegarde `data.json` et `data-archives.json`
6. Appel `_log({ "action": "archive-subproject", "project": ..., "subproject": ... })`

**Réponses :**
- `200 { "ok": true, "projectEmpty": false }` — SP archivé, projet non vide
- `200 { "ok": true, "projectEmpty": true }` — SP archivé, projet désormais vide
- `400` si IDs manquants
- `404` si projet ou SP introuvable

### 4.3 `POST /api/archive-project`

Archive un projet entier (avec tous ses SP, docs inclus).

**Body :** `{ "projectId": "..." }`

**Comportement :**
1. Valide que le projet existe dans `data.json`
2. Copie le projet complet dans `data-archives.json`
   - Si le projet existe déjà dans les archives (suite à des archivages de SP partiels) : **fusion** — les SP déjà archivés restent, les SP encore dans `data.json` sont ajoutés
3. Retire le projet de `data.json`
4. Sauvegarde les deux fichiers
5. Appel `_log({ "action": "archive-project", "project": ... })`

**Réponses :** `200 { "ok": true }` / `400` / `404`

### 4.4 `POST /api/restore-subproject`

Restaure un sous-projet des archives vers `data.json`.

**Body :** `{ "projectId": "...", "subprojectId": "..." }` (IDs tels que dans `data-archives.json`)

**Comportement :**
1. Valide que le projet et le SP existent dans `data-archives.json`
2. Cherche le projet dans `data.json` par `id` :
   - **Projet trouvé :** append le SP dans `data.json[project.subprojects]`
   - **Projet absent :** crée une entrée projet dans `data.json` (copie des métadonnées depuis les archives : `id`, `name`, `alias`, `desc`, `stack`, `category`, `folder`, `docs: []`) avec ce SP
3. Retire le SP de `data-archives.json[project.subprojects]`
4. Si le projet dans les archives n'a plus de SP après le retrait → retire le projet vide de `data-archives.json`
5. Sauvegarde les deux fichiers
6. Appel `_log({ "action": "restore-subproject", "project": ..., "subproject": ... })`

**Réponses :** `200 { "ok": true }` / `400` / `404`

### 4.5 `POST /api/restore-project`

Restaure un projet entier (en bloc) des archives vers `data.json`.

**Body :** `{ "projectId": "..." }`

**Comportement :**
1. Valide que le projet existe dans `data-archives.json`
2. Vérifie qu'aucun projet avec le même `id` n'existe dans `data.json` → si conflit : erreur `409`
3. Copie le projet complet dans `data.json`
4. Retire le projet de `data-archives.json`
5. Sauvegarde les deux fichiers
6. Appel `_log({ "action": "restore-project", "project": ... })`

**Réponses :** `200 { "ok": true }` / `400` / `404` / `409 { "error": "Conflit : un projet avec cet id existe déjà dans data.json" }`

### 4.6 `POST /api/delete-archive-subproject`

Suppression définitive d'un SP des archives.

**Body :** `{ "projectId": "...", "subprojectId": "..." }`

**Comportement :**
1. Retire le SP de `data-archives.json[project.subprojects]`
2. Si le projet n'a plus de SP → retire aussi le projet vide des archives
3. Appel `_log({ "action": "delete-archive-subproject", "project": ..., "subproject": ... })`

**Réponses :** `200 { "ok": true }` / `400` / `404`

### 4.7 `POST /api/delete-archive-project`

Suppression définitive d'un projet (et tous ses SP) des archives.

**Body :** `{ "projectId": "..." }`

**Comportement :**
1. Retire le projet complet de `data-archives.json`
2. Appel `_log({ "action": "delete-archive-project", "project": ... })`

**Réponses :** `200 { "ok": true }` / `400` / `404`

---

## 5. Routing dans `do_POST`

Ajouter dans le bloc `do_POST` de `Handler` :

```python
elif path == '/api/archive-subproject':
    self._handle_archive_subproject()
elif path == '/api/archive-project':
    self._handle_archive_project()
elif path == '/api/restore-subproject':
    self._handle_restore_subproject()
elif path == '/api/restore-project':
    self._handle_restore_project()
elif path == '/api/delete-archive-subproject':
    self._handle_delete_archive_subproject()
elif path == '/api/delete-archive-project':
    self._handle_delete_archive_project()
```

Et dans `do_GET` :

```python
elif path == '/api/archives':
    self._handle_archives()
```

---

## 6. Nouveaux helpers Python

Pattern symétrique à `_load_data()` : `_load_archives()` lève `ValueError` sur JSON invalide. Le handler `GET /api/archives` doit catcher cette exception et renvoyer `500` (même squelette que `_handle_state()`).

```python
ARCHIVES_FILE = BASE_DIR / 'data-archives.json'

def _load_archives() -> dict:
    if not ARCHIVES_FILE.exists():
        return {'projects': []}
    try:
        return json.loads(ARCHIVES_FILE.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        raise ValueError('data-archives.json corrompu (JSON invalide)')

def _save_archives(data: dict):
    ARCHIVES_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )
```

---

## 7. Modifications `api.js`

Ajouter les wrappers fetch suivants (même pattern que les fonctions existantes) :

```js
export async function fetchArchives() { ... }                             // GET /api/archives
export async function archiveSubproject(projectId, subprojectId) { ... } // POST
export async function archiveProject(projectId) { ... }                  // POST
export async function restoreSubproject(projectId, subprojectId) { ... } // POST
export async function restoreProject(projectId) { ... }                  // POST
export async function deleteArchiveSubproject(projectId, subprojectId) { ... } // POST
export async function deleteArchiveProject(projectId) { ... }            // POST
```

---

## 8. Modifications `DASHBOARD-V2.html`

### 8.1 Tab Archives

Dans `#view-tabs`, ajouter après le tab Docs :

```html
<button class="view-tab" data-view="archives">Archives <span id="archives-count-badge"></span></button>
```

### 8.2 Container Archives

Ajouter après `#docs-container` :

```html
<div id="archives-container" style="display:none"></div>
```

### 8.3 Aucun autre élément de barre d'outils spécifique aux archives
(Pas de filtres, pas de bouton GSheet, pas de stats bar dans la vue Archives)

---

## 9. Modifications `ui.js`

### 9.1 Nouvelles variables d'état

```js
let _archivesState = { projects: [] };   // cache local des archives
let _archivesLoaded = false;             // lazy-loading : chargé au premier accès
```

### 9.2 Imports supplémentaires depuis `api.js`

```js
import { ..., fetchArchives, archiveSubproject, archiveProject,
         restoreSubproject, restoreProject,
         deleteArchiveSubproject, deleteArchiveProject } from './api.js';
```

### 9.3 Bouton Archiver sur les projets

Dans `renderProject()`, dans `project-actions`, ajouter avant le bouton 🗑 :

```html
<button class="icon-btn btn-archive-proj" title="Archiver le projet">🗃</button>
```

Handler : `openConfirm()` → `archiveProject(proj.id)` → retirer de `_state.projects` → `renderAll()` + `updateArchivesCountBadge()`.

### 9.4 Bouton Archiver sur les sous-projets

Dans `renderSubproject()`, dans `titleRow`, ajouter un `archBtn` (même style opacity-0 que renameBtn/delBtn) :

```js
const archBtn = document.createElement('button');
archBtn.className = 'icon-btn';
archBtn.title = 'Archiver';
archBtn.textContent = '🗃';
archBtn.style.cssText = 'font-size:11px;opacity:0;transition:opacity 0.15s;';
```

Handler :
1. `openConfirm()` avec message `"${sp.name}" sera archivé et consultable dans l'onglet Archives.`
2. Appel `archiveSubproject(projectId, sp.id)`
3. Si réponse `projectEmpty: true` → enchaîner une **seconde** `openConfirm()` : `"Le projet [nom] n'a plus de sous-projets. L'archiver aussi ?"` → si OUI : `archiveProject(projectId)`
4. Mise à jour de `_state` + `renderAll()` + `updateArchivesCountBadge()`

### 9.5 Fonction `renderArchivesView()`

Structure analogue à `renderDocsView()` — itère sur `_archivesState.projects`, produit des cartes. Chaque carte appelle `renderArchivedProject(proj)`.

### 9.6 Fonction `renderArchivedProject(proj)`

Structure analogue à `renderProject()` mais :
- Pas de boutons : `btn-open-folder`, `btn-add-sp`, `btn-rename-alias`
- Boutons présents : `btn-restore-proj` (Restaurer) et `btn-delete-archive-proj` (🗑 définitif)
- `btn-restore-proj` → `openConfirm()` → `restoreProject(proj.id)` → MAJ des deux états + `renderAll()`
- `btn-delete-archive-proj` → `openConfirm('Suppression définitive', ...)` → `deleteArchiveProject(proj.id)` → MAJ `_archivesState` + `renderAll()`

### 9.7 Fonction `renderArchivedSubproject(projectId, sp)`

Structure analogue à `renderSubproject()` mais :
- Read-only : pas de badge de statut cliquable, pas de renommage inline, pas de target éditable
- Le badge de statut est affiché mais non cliquable
- Pas de bouton Renommer, pas de bouton Archiver
- Boutons : `btn-restore-sp` (Restaurer) et `btn-delete-archive-sp` (🗑 définitif)
- `btn-restore-sp` → `openConfirm()` → `restoreSubproject(projectId, sp.id)` → MAJ des deux états + `renderAll()`
- `btn-delete-archive-sp` → `openConfirm('Suppression définitive', ...)` → `deleteArchiveSubproject(projectId, sp.id)` → MAJ `_archivesState` + `renderAll()`

### 9.8 Badge de comptage Archives

```js
function updateArchivesCountBadge() {
  const el = document.getElementById('archives-count-badge');
  if (!el) return;
  const n = _archivesState.projects.reduce(
    (acc, p) => acc + (p.subprojects || []).length, 0
  );
  el.textContent = n > 0 ? `(${n})` : '';
}
```

Le badge compte les **SP archivés** (pas les projets), cohérent avec le badge Docs qui compte les docs.

### 9.9 `switchView()` — vue archives

Ajouter la gestion de `view === 'archives'` :
- Masquer : `stats-bar`, `filters`, `gsheet-bar`, `add-project-btn`, `projects-container`, `docs-filters`, `docs-actions`, `docs-container`
- Afficher : `archives-container`
- Si `!_archivesLoaded` → `fetchArchives()` pour initialiser `_archivesState`, puis `renderAll()`
- `_archivesLoaded = true` après le premier chargement

### 9.10 Chargement initial des archives

Dans `init()`, après le chargement de l'état principal, charger les archives en parallèle (fire-and-forget) pour initialiser le badge dès le démarrage :

```js
fetchArchives().then(a => {
  _archivesState = a;
  _archivesLoaded = true;
  updateArchivesCountBadge();
}).catch(() => {});
```

---

## 10. Comportements spéciaux — récapitulatif

| Cas | Comportement |
|-----|-------------|
| Archive SP (projet non vide) | SP → archives, projet reste dans `data.json` |
| Archive SP (dernier SP du projet) | SP → archives, projet reste vide dans `data.json`, UI propose d'archiver aussi le projet |
| Archive projet non vide | Projet + tous ses SP → archives |
| Archive projet vide (manuellement) | Projet vide → archives |
| Archive projet — SP partiellement déjà archivés | Fusion dans l'entrée projet existante dans les archives |
| Restaure SP — projet dans `data.json` | SP → `data.json[project.subprojects]` |
| Restaure SP — projet absent de `data.json` | Projet recréé (coquille) + SP dans `data.json` |
| Restaure SP — dernier SP du projet dans les archives | SP restauré → projet vide retiré des archives |
| Restaure projet (en bloc) | Projet + tous ses SP → `data.json` |
| Restaure projet — conflit ID | Erreur 409, message explicite |
| Suppression définitive SP | SP supprimé des archives, projet vide nettoyé |
| Suppression définitive projet | Projet + tous ses SP supprimés des archives |

---

## 11. Fichiers modifiés

| Fichier | Nature |
|---------|--------|
| `serve-v2.py` | +`ARCHIVES_FILE`, +`_load_archives()`, +`_save_archives()`, +7 handlers, routing GET+POST, modification `_handle_add_project` + `_handle_add_subproject` (unicité IDs) |
| `api.js` | +7 fonctions fetch |
| `ui.js` | +`_archivesState`, +`_archivesLoaded`, +boutons Archiver sur projets/SP, +`renderArchivesView()`, +`renderArchivedProject()`, +`renderArchivedSubproject()`, +`updateArchivesCountBadge()`, modification `switchView()`, modification `init()` |
| `DASHBOARD-V2.html` | +tab Archives, +`#archives-container`, +`#archives-count-badge` |
| `.gitignore` | +`data-archives.json` |

---

## 12. Points ouverts résolus

| Point | Décision |
|-------|----------|
| Structure `data-archives.json` | Identique à `data.json` |
| Archivage dernier SP | Projet reste vide dans `data.json` ; seconde confirmation proposée |
| Restauration projet en bloc | En bloc (Option 2) ; sélection granulaire = amélioration future |
| Conflit ID à la restauration | Erreur 409 |
| Garantie unicité IDs | Vérification dans les archives lors de la création |
| Docs à l'archivage | Suivent le projet/SP |
| GSheet et archivage | Pas de push automatique |
| Suppression définitive | Oui, avec confirmation |
| Badge Archives | Oui — compte les SP archivés |
| `archived_at` (timestamp d'archivage) | Non en V1 — copie exacte du SP, aucun champ supplémentaire |
| Ordre des SP à la restauration | Pas de contrainte — ordre de `data-archives.json` |
| `steps` du SP archivé | Suivent le SP (copie atomique de l'objet complet) |
| Vocabulaire des erreurs / messages | À aligner sur les handlers existants — voir §13 |

---

## 13. Consignes d'implémentation

Avant d'écrire chaque handler, **lire le handler équivalent existant** dans `serve-v2.py` pour reprendre exactement :

- Le squelette CORS / vérification de secret / limite payload
- Le pattern d'erreurs (codes HTTP, libellés FR exacts)
- L'usage de `_log()` (`HISTORY_FILE`)

| Nouveau handler | Handler de référence à lire |
|-----------------|----------------------------|
| `_handle_archives` (GET) | `_handle_state` (lecture + 500 sur JSON corrompu) |
| `_handle_archive_subproject` | `_handle_remove_subproject` (errors, logs) + `_handle_save_subproject` (lecture SP) |
| `_handle_archive_project` | `_handle_remove_project` |
| `_handle_restore_subproject` | `_handle_add_subproject` (unicité ID) + `_handle_remove_subproject` (errors) |
| `_handle_restore_project` | `_handle_add_project` + `_handle_remove_project` |
| `_handle_delete_archive_subproject` | `_handle_remove_subproject` |
| `_handle_delete_archive_project` | `_handle_remove_project` |

**Libellés d'erreur canoniques** (vérifiés par lecture des handlers existants) :

- `400 { "error": "projectId et subprojectId requis" }` — pour les endpoints qui prennent 2 IDs (archive-subproject, restore-subproject, delete-archive-subproject), aligné sur `_handle_remove_subproject`
- `400 { "error": "projectId requis" }` — pour les endpoints qui prennent 1 ID (archive-project, restore-project, delete-archive-project), aligné sur `_handle_remove_project`
- `404 { "error": "Projet introuvable" }`
- `404 { "error": "Sous-projet introuvable" }`
- `409 { "error": "Conflit : un projet avec cet id existe déjà dans data.json" }` (nouveau code, libellé libre mais FR)

Conformément à la **Règle 4** du `CLAUDE.md` racine (« toujours s'appuyer sur l'infrastructure existante »).
