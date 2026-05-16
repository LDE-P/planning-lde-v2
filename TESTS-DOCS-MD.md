# TESTS-DOCS-MD — Gestion des MD (Vue Docs)

> **Date :** 2026-05-15 (v2 — après résolution A9/A10/A11 : revalidation `save-doc`, uniformisation `GIT_ROOT`, lien SP → panneau détail)
> **Statut :** rédigé pendant la spec (avant implémentation).
> **Référence spec :** `SPEC-DOCS-MD.md`
> **Périmètre :** endpoints backend + check d'intégrité. Les comportements UI et les liens natifs (TextMate, Finder) sont couverts par des cas manuels en fin de fichier.

---

## Infrastructure

### Outil et style

Même infrastructure que `TESTS-V2.md` — les nouveaux fichiers s'ajoutent dans le même dossier.

| Propriété | Valeur |
|-----------|--------|
| Outil | `pytest` |
| Client HTTP | `requests` |
| Port de test | **8099** |
| Emplacement | `tests-e2e-python/planning-lde/` |
| Commande | `pytest tests-e2e-python/planning-lde/ -v -k docs` |

### Extension de la fixture `data.json`

Le `data.json` de test minimal existant doit être étendu :

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
      "docs": [
        {
          "id": "doc-existant",
          "file": "projet-alpha/SPEC-EXISTANT.md",
          "title": "Spec existante",
          "desc": "Une spec déjà dans le catalogue.",
          "type": "spec",
          "status": "final",
          "date": "2026-05-10",
          "subproject": "sp-existant"
        }
      ],
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
    },
    {
      "id": "projet-beta",
      "name": "Projet Beta",
      "alias": "Beta",
      "desc": "Projet sans docs.",
      "stack": "JS",
      "category": "active",
      "folder": "",
      "docs": [],
      "subprojects": []
    }
  ]
}
```

### Mécanique GIT_ROOT de test — décision tranchée

Le `conftest.py` existant patche déjà des variables module (`serve_v2.DATA_FILE`, `serve_v2.BASE_DIR`) avant de démarrer le serveur. La même mécanique s'applique à `GIT_ROOT`.

**Côté serveur (`serve-v2.py`) :** ajouter une variable module calculée une seule fois au chargement :

```python
GIT_ROOT = BASE_DIR.parent.resolve()  # ligne à ajouter après BASE_DIR
```

Tous les endpoints docs utilisent `GIT_ROOT`. **Et les deux occurrences existantes inline** (`_resolve_project_path` ligne 809, `_handle_open_folder` ligne 1219) sont remplacées par `GIT_ROOT` aussi — voir §6.1 SPEC. Sans cette uniformisation, le patch `serve_v2.GIT_ROOT = data_dir` ci-dessous ne couvrirait pas `_handle_open_folder` ni `_resolve_project_path`, qui resteraient accrochés au vrai filesystem en test.

**Côté tests (`conftest.py`) :** étendre la fixture `server_url` pour patcher `GIT_ROOT` et créer les fichiers `.md` physiques dans un sous-dossier du `data_dir` temporaire :

```python
@pytest.fixture(scope="session")
def server_url(data_dir):
    # Patchs existants
    serve_v2.DATA_FILE = data_dir / "data.json"
    serve_v2.BASE_DIR  = data_dir
    serve_v2.HTML_FILE = data_dir / "DASHBOARD-V2.html"

    # Patch GIT_ROOT — pointe vers data_dir (même tmp_path)
    serve_v2.GIT_ROOT = data_dir

    # Création des fichiers MD physiques nécessaires aux tests
    (data_dir / "projet-alpha").mkdir(exist_ok=True)
    (data_dir / "projet-alpha" / "SPEC-EXISTANT.md").write_text("# Spec existante\n")
    (data_dir / "projet-alpha" / "NOUVEAU-DOC.md").write_text("# Nouveau doc\n")

    shutil.copy(_FIXTURE_DATA, data_dir / "data.json")
    httpd = HTTPServer(("", TEST_PORT), serve_v2.Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://localhost:{TEST_PORT}"
    httpd.shutdown()
```

Avantages : zéro variable d'environnement, zéro argument CLI, cohérent avec l'infrastructure existante, les chemins `doc.file` dans `data.json` de test (`"projet-alpha/SPEC-EXISTANT.md"`) correspondent exactement aux fichiers créés par la fixture.

### Nouveaux fichiers de tests

```
tests-e2e-python/planning-lde/
  conftest.py               → étendu : patch serve_v2.GIT_ROOT + création fichiers MD physiques
  test_state_docs.py        → GET /api/state — présence de git_root
  test_add_doc.py           → POST /api/add-doc
  test_save_doc.py          → POST /api/save-doc
  test_remove_doc.py        → POST /api/remove-doc
  test_open_file.py         → POST /api/open-file
  test_cors_docs.py         → CORS + payload max sur les 4 nouveaux endpoints
  test_integrity_docs.py    → script check d'intégrité étendu (§8 SPEC)
```

---

## test_state_docs.py — GET /api/state

| # | Cas | Comportement attendu |
|---|-----|---------------------|
| 1 | GET `/api/state` nominal | Réponse contient une clé `git_root` |
| 2 | `git_root` est un chemin absolu | `body["git_root"].startswith("/")` |
| 3 | `git_root` correspond au dossier parent de `planning-lde-v2/` | Vérifiable par `os.path.isdir(git_root)` |
| 4 | Projet avec docs — champ `docs` est une liste d'objets | `isinstance(project["docs"][0], dict)` |
| 5 | Projet sans docs — champ `docs` est une liste vide | `project["docs"] == []` |
| 6 | Projet avec `docs: ["ancien.md", {"id": "nouveau", ...}]` (mix ancien/nouveau) | `docs` ne contient que les entrées objet — la chaîne est filtrée silencieusement (§3.5 SPEC) |
| 7 | Projet sans champ `docs` du tout (champ absent de `data.json`) | `docs` absent ou `[]` dans la réponse — pas de crash |

---

## test_add_doc.py — POST /api/add-doc

### Cas nominaux

| # | Cas | Payload | Effet attendu |
|---|-----|---------|--------------|
| 1 | Ajout minimal (sans `desc`, sans `subproject`) | `{project_id, file: "projet-alpha/NOUVEAU-DOC.md", title: "Nouveau doc", type: "audit", status: "draft", date: "2026-05-15"}` | 200 `{ok: true, doc: {...}}`, doc présent dans `/api/state` |
| 2 | `id` généré — cas simple | `title: "Mon Audit Mai"` | `doc.id == "mon-audit-mai"` |
| 2b | `id` généré — tiret long, parenthèses | `title: "Spec V2 — partie 2 (final)"` | `doc.id == "spec-v2-partie-2-final"` (règle §3.3 SPEC) |
| 2c | `id` généré — accents | `title: "Étude préalable"` | `doc.id == "etude-prealable"` |
| 2d | `id` généré — titre purement non-alphanumérique | `title: "—— !! ——"` | 400 `"Impossible de générer un id depuis ce titre"` |
| 2e | `id` généré — date dans le titre (slashs) | `title: "Bilan — 14/05/2026"` | `doc.id == "bilan-14-05-2026"` (les `/` sont des séparateurs non-alpha, traités comme `-`) |
| 3 | `desc` optionnel absent | Payload sans `desc` | 200, `doc.desc` absent ou null dans `data.json` — pas d'erreur |
| 4 | `subproject` null explicite | `subproject: null` | 200, persisté |
| 5 | `subproject` valide (SP existant) | `subproject: "sp-existant"` | 200, persisté |
| 6 | Ajout avec `id` explicite | `id: "mon-id-custom"` | `doc.id == "mon-id-custom"` |
| 7 | Double ajout — même `title` → id en doublon | Deux docs avec même `title` | **400** avec message `"id déjà existant dans ce projet — modifie le titre ou fournis un id explicite"` *(P1 tranché)* |
| 7b | Projet sans champ `docs` dans `data.json` (champ absent, pas `[]`) | Payload nominal vers ce projet | 200 — le champ `docs` est auto-initialisé à `[]` avant insertion (§4.1 étape 5) |

### Erreurs — champs manquants

| # | Cas | Code attendu |
|---|-----|-------------|
| 8 | `project_id` absent | 400 |
| 9 | `file` absent | 400 |
| 10 | `title` absent | 400 |
| 10b | `title` vide `""` — envoi direct via requête HTTP (bypass client) | 400 — valider côté serveur, indépendamment du blocage UI |
| 11 | `type` absent | 400 |
| 12 | `status` absent | 400 |
| 13 | `project_id` inconnu | 400 |
| 14 | JSON malformé | 400 |
| 15 | Payload vide `{}` | 400 |

### Erreurs — validation fichier

| # | Cas | Code attendu |
|---|-----|-------------|
| 16 | `file` inexistant sur disque | 400, message explicite (ex : `"Fichier introuvable : projet-alpha/INCONNU.md"`) |
| 17 | `file` vide `""` | 400 |
| 18 | `file` avec traversée de répertoire (`../../etc/passwd`) | 400 — le chemin résolu sort de `GIT_ROOT`, doit être rejeté même si le fichier existe |

### Erreurs — doublon

| # | Cas | Code attendu |
|---|-----|-------------|
| 19 | `id` identique à `doc-existant` dans le même projet | 400, message `"id déjà existant"` |

### Cas limites — migration ancien format

| # | Cas | Comportement attendu |
|---|-----|---------------------|
| 19b | `project_id` dont `docs` contient une chaîne `["ancien-fichier.md"]` (ancien format §3.5 SPEC) | Ajout d'un nouveau doc valide | 200 — le nouveau doc est ajouté, l'ancienne chaîne est **préservée telle quelle** dans `data.json` (pas de migration auto, le check d'intégrité #9 signalera) |

### Cas limites — vocabulaire et formats

| # | Cas | Comportement attendu |
|---|-----|---------------------|
| 20 | `type` hors vocabulaire (`type: "inconnu"`) | **400** — le badge UI repose sur un vocabulaire fixe, une valeur inconnue passerait en base sans badge *(P2 tranché)* |
| 21 | `status` hors vocabulaire (`status: "wip"`) | 400 |
| 22 | `date` format invalide (`date: "15/05/2026"`) | **400** — format `YYYY-MM-DD` imposé pour permettre un tri futur en V2 *(P3 tranché)* |
| 22b | `date` absente ou vide `""` | **Accepté** — date optionnelle ; si absente, aucun tri possible mais pas d'erreur |
| 23 | `subproject` pointant vers un SP inexistant | Accepté (détecté au check d'intégrité, pas bloqué à la saisie) |
| 24 | Rechargement `/api/state` après ajout | Le doc est présent avec tous ses champs |

---

## test_save_doc.py — POST /api/save-doc

### Cas nominaux

| # | Cas | Payload | Effet attendu |
|---|-----|---------|--------------|
| 1 | Mise à jour `status` seul | `{project_id, doc_id: "doc-existant", patch: {status: "archived"}}` | 200 `{ok: true}`, `status` mis à jour, autres champs inchangés |
| 2 | Mise à jour `title` | `patch: {title: "Nouveau titre"}` | 200, `title` mis à jour |
| 3 | Mise à jour `desc` | `patch: {desc: "Nouvelle description."}` | 200, `desc` mis à jour |
| 4 | Mise à jour `type` | `patch: {type: "bilan"}` | 200, `type` mis à jour |
| 5 | Mise à jour `subproject` | `patch: {subproject: null}` | 200, `subproject` null persisté |
| 6 | Patch vide `{}` | `{project_id, doc_id, patch: {}}` | 200, `data.json` inchangé |
| 7 | Mise à jour `file` vers un fichier existant (cf. §5.6 SPEC — champ éditable) | `patch: {file: "projet-alpha/NOUVEAU-DOC.md"}` | 200, `file` mis à jour — même validation anti-traversée qu'à l'ajout |

### Erreurs

| # | Cas | Code attendu |
|---|-----|-------------|
| 8 | `project_id` absent | 400 |
| 9 | `doc_id` absent | 400 |
| 10 | `project_id` inconnu | 400 |
| 11 | `doc_id` inconnu dans le projet | 400 |
| 12 | `patch.file` inexistant sur disque | 400 |
| 13 | `patch.file` avec traversée | 400 |
| 14 | JSON malformé | 400 |

### Erreurs — revalidation vocabulaire et formats (symétrique à `add-doc`)

> Couvrent la décision A9 — `save-doc` revalide les mêmes champs que `add-doc` (§4.2 SPEC). Sans cela, un client malveillant ou buggé pourrait introduire des valeurs invalides via le patch.

| # | Cas | Code attendu |
|---|-----|-------------|
| 15 | `patch: {type: "inconnu"}` (hors vocabulaire) | 400 |
| 16 | `patch: {status: "wip"}` (hors vocabulaire — `wip` est un statut SP, pas doc) | 400 |
| 17 | `patch: {date: "15/05/2026"}` (format invalide) | 400 |
| 17b | `patch: {date: ""}` (chaîne vide pour effacer la date) | 200 — chaîne vide acceptée, sert à effacer la date du doc |
| 18 | `patch: {title: ""}` (titre vide) | 400 — un doc sans titre n'est pas affichable dans la vue |

### Cas limites

| # | Cas | Comportement attendu |
|---|-----|---------------------|
| 19 | Deux patches successifs sur le même doc | Le second s'applique par-dessus le premier — pas de perte |
| 20 | Champ inconnu dans `patch` (ex : `patch: {foo: "bar"}`) | **Ignoré silencieusement** — cohérent avec `save-subproject`, compatible avec les évolutions futures du client *(P4 tranché)* |

---

## test_remove_doc.py — POST /api/remove-doc

### Cas nominaux

| # | Cas | Payload | Effet attendu |
|---|-----|---------|--------------|
| 1 | Suppression nominale | `{project_id: "projet-alpha", doc_id: "doc-existant"}` | 200 `{ok: true}`, doc absent de `/api/state` |
| 2 | `data.json` mis à jour | Rechargement `/api/state` après suppression | `docs` du projet ne contient plus le doc |
| 3 | Autres docs du projet inchangés | Projet avec plusieurs docs, on en supprime un | Seul le doc cible est retiré |

### Erreurs

| # | Cas | Code attendu |
|---|-----|-------------|
| 4 | `project_id` absent | 400 |
| 5 | `doc_id` absent | 400 |
| 6 | `project_id` inconnu | 400 |
| 7 | `doc_id` inconnu dans le projet | 400 |
| 8 | Double suppression du même doc | 400 au second appel |
| 9 | JSON malformé | 400 |

---

## test_open_file.py — POST /api/open-file

> Ces tests vérifient que le serveur construit correctement le chemin et valide l'existence du fichier. L'exécution effective de `open -R` est mockée (on ne peut pas tester l'ouverture Finder en CI).

### Cas nominaux

| # | Cas | Payload | Comportement attendu |
|---|-----|---------|---------------------|
| 1 | Fichier existant | `{file: "projet-alpha/SPEC-EXISTANT.md"}` | 200 `{ok: true}`, `subprocess.Popen` appelé avec `["open", "-R", <chemin_absolu>]` |
| 2 | Chemin absolu construit correctement | Idem | Le chemin passé à Popen = `GIT_ROOT + "/" + file` |

### Erreurs

| # | Cas | Code attendu |
|---|-----|-------------|
| 3 | `file` absent du payload | 400 |
| 4 | `file` inexistant sur disque | 400, message explicite |
| 5 | `file` avec traversée (`../../etc/passwd`) | 400 — `Path(GIT_ROOT, file).resolve()` doit rester strictement sous `GIT_ROOT` (`is_relative_to`) ; rejeté même si le fichier cible existe |
| 6 | `file` vide `""` | 400 |
| 7 | JSON malformé | 400 |

---

## test_cors_docs.py — CORS et payload max (nouveaux endpoints)

> Conformément à la Règle 4 du `CLAUDE.md` racine : les nouveaux endpoints doivent appliquer le même squelette de sécurité que les endpoints existants. Ces tests vérifient que les 4 nouveaux endpoints (`/api/add-doc`, `/api/save-doc`, `/api/remove-doc`, `/api/open-file`) ne font pas exception.

### Preflight OPTIONS

| # | Endpoint | Comportement attendu |
|---|----------|---------------------|
| 1 | `OPTIONS /api/add-doc` | 200, headers `Access-Control-Allow-Origin: *` présents |
| 2 | `OPTIONS /api/save-doc` | 200, headers CORS présents |
| 3 | `OPTIONS /api/remove-doc` | 200, headers CORS présents |
| 4 | `OPTIONS /api/open-file` | 200, headers CORS présents |

### Headers CORS sur les réponses POST

| # | Endpoint | Comportement attendu |
|---|----------|---------------------|
| 5 | `POST /api/add-doc` (nominal) | Réponse contient `Access-Control-Allow-Origin: *` |
| 6 | `POST /api/add-doc` (erreur 400) | Réponse d'erreur contient aussi le header CORS |

### Payload max (1 Mo)

| # | Endpoint | Comportement attendu |
|---|----------|---------------------|
| 7 | `POST /api/add-doc` avec payload > 1 Mo | 413 |
| 8 | `POST /api/save-doc` avec payload > 1 Mo | 413 |

> Les cas 7–8 suffisent comme smoke test — ne pas dupliquer pour chaque endpoint si la limite est gérée centralement dans le dispatcher.

---

## test_integrity_docs.py — Check d'intégrité étendu

> Teste le script Python de vérification défini dans `SPEC-DOCS-MD.md §8`. S'exécute directement sur un `data.json` en mémoire, sans serveur.

### Cas valides

| # | `data.json` | Résultat attendu |
|---|-------------|-----------------|
| 1 | Aucun doc dans aucun projet (`docs: []`) | `"OK"` |
| 2 | Doc bien formé avec `id`, `file`, `title`, `type`, `status`, `date` | `"OK"` |
| 3 | Doc avec `subproject` pointant vers un SP existant dans le même projet | `"OK"` |
| 4 | Doc avec `subproject: null` | `"OK"` |
| 5 | Deux projets, chacun avec des docs valides aux ids identiques (mais dans des projets différents) | `"OK"` — unicité vérifiée par projet, pas globalement |

### Cas d'erreur

| # | `data.json` | Erreur attendue |
|---|-------------|----------------|
| 6 | Doc sans `id` | `"Doc sans id : Projet Alpha / Spec existante"` |
| 7 | Deux docs avec le même `id` dans le même projet | `"Id doc en double : Projet Alpha / doc-existant"` |
| 8 | Doc avec `subproject` pointant vers un SP inexistant | `"Doc orphelin : Projet Alpha / doc-existant → SP \"sp-fantome\" introuvable"` |
| 9 | `docs` contenant une chaîne au lieu d'un objet (ancien format §3.5 SPEC) | `"doc non-objet dans Projet Alpha"` — signalé mais non bloquant : les autres docs et le serveur fonctionnent normalement |
| 10 | SP sans `id` (erreur existante) + doc orphelin (nouvelle erreur) | Les deux erreurs signalées dans le même run |

---

## Cas manuels (non automatisables en CI)

### Lien TextMate

| # | Action | Résultat attendu |
|---|--------|-----------------|
| M1 | Clic "↗ TextMate" sur une carte doc | TextMate s'ouvre sur le fichier exact |
| M2 | Fichier avec espace dans le chemin | TextMate s'ouvre correctement (URL-encoding du chemin vérifié) |
| M3 | `git_root` visible dans la source HTML via DevTools | Le `href` vaut bien `txmt://open?url=file:///[git_root]/[file]` |

### Lien Finder

| # | Action | Résultat attendu |
|---|--------|-----------------|
| M4 | Clic "📁 Finder" sur une carte doc | Finder s'ouvre avec le fichier sélectionné dans son dossier |
| M5 | Fichier dans un sous-dossier | Le bon dossier s'ouvre, le bon fichier est sélectionné |

### Filtres et toggle (UI)

| # | Action | Résultat attendu |
|---|--------|-----------------|
| M6 | Chargement initial de la vue Docs | Filtre statut = draft + final (archived masqués), filtre type = Tous |
| M7 | Activer filtre "Archivé" | Les docs archivés apparaissent |
| M8 | Activer filtre type "Spec" | Seules les cartes `type: spec` visibles |
| M9 | Combiner type "Audit" + statut "Final" | Seuls les docs `type:audit AND status:final` visibles |
| M10 | Toggle OFF + filtre actif masquant tous les docs d'un projet | Le projet disparaît de la vue (traité comme "sans docs" avec toggle OFF). Scénario exact : projet avec 2 docs `type:spec`, filtre type = "Audit" actif, toggle OFF → projet invisible. Activer le toggle → projet réapparaît en mode réduit malgré les filtres (le toggle prend le dessus sur le filtre pour l'affichage de l'en-tête). |
| M11 | Rechargement de la page | Filtres restaurés depuis `localStorage` |
| M11b | Vue Docs sur un projet avec 3 docs (dates 2026-05-15, 2026-05-10, sans date) | Affichés dans cet ordre : 15/05 → 10/05 → sans date (§3.4 SPEC) |
| M12 | Toggle "Afficher projets sans docs" activé | Projets vides apparaissent avec "+ Ajouter un doc" |

### CRUD

| # | Action | Résultat attendu |
|---|--------|-----------------|
| M13 | Clic "+ Ajouter un doc" | Modal s'ouvre, `project_id` pré-rempli |
| M14 | Soumission avec `title` vide | Soumission bloquée côté client, champ mis en évidence |
| M15 | Soumission avec `file` inexistant | Message d'erreur serveur affiché dans la modal |
| M16 | Ajout valide | Modal se ferme, carte apparaît, compteur en-tête incrémenté |
| M17 | Clic `✎` sur une carte | Modal pré-remplie avec valeurs actuelles |
| M18 | Modification puis annulation | Aucun changement dans la vue |
| M19 | Clic `🗑` puis annulation | Doc toujours présent |
| M20 | Clic `🗑` puis confirmation | Doc disparu, compteur décrémenté |

### Lien SP associé

| # | Action | Résultat attendu |
|---|--------|-----------------|
| M23 | Clic sur "SP : Nom SP" dans une doc card (SP existant) | Bascule sur l'onglet "Projets" + ouverture du panneau de détail du SP ciblé (§5.3 SPEC) |
| M24 | Clic sur "SP : Nom SP" pour un `subproject` orphelin (SP supprimé entre-temps) | Lien rendu inactif (style gris, pas de clic) — pas de crash, pas d'erreur silencieuse |

### Cohérence compteurs

| # | Cas | Résultat attendu |
|---|-----|-----------------|
| M21 | En-tête projet avec 3 docs | Affiche "Nom — 3 docs" indépendamment des filtres actifs |
| M22 | Onglet "Docs" dans la navigation | Affiche "Docs (N)" avec N = **total de tous les docs y compris archivés** — cohérent avec M21 (compteur projet aussi indépendant des filtres). Le compteur reflète le catalogue, pas la vue filtrée. |

---

## Récapitulatif des décisions — tous points tranchés

| # | Décision |
|---|----------|
| P1 | Double `title` → id en doublon → **400** avec message explicite |
| P2 | `type` hors vocabulaire → **400** |
| P3 | `date` fournie mais format invalide → **400** (YYYY-MM-DD strict) ; `date` absente → **acceptée** |
| P4 | Champ inconnu dans `patch` → **ignoré silencieusement** |
| P5 | `docs: ["chaine"]` (ancien format) → **ignorer silencieusement** les entrées non-objet ; le check d'intégrité #9 signale le problème sans bloquer le serveur |
| P6 | Règle de normalisation du slug : `unicodedata.normalize("NFKD")` → encode ASCII (ignore) → lowercase → `re.sub(r"[^a-z0-9]+", "-")` → `strip("-")`. Exemples de référence : `"Spec V2 — partie 2 (final)"` → `"spec-v2-partie-2-final"` ; `"Bilan — 14/05/2026"` → `"bilan-14-05-2026"` (les `/` sont des séparateurs, pas des caractères spéciaux) |
| P7 | `save-doc` revalide **symétriquement** `type`, `status`, `date`, `title`, `file` quand ces champs sont présents dans `patch` (§4.2 SPEC, cas 15–18 ci-dessus). `date: ""` accepté pour effacer la date. |
| P8 | Variable module `GIT_ROOT` : ajoutée dans `serve-v2.py` après `BASE_DIR`. **Remplace** aussi les deux occurrences inline existantes `BASE_DIR.parent.resolve()` (lignes 809 et 1219) pour que le patch test couvre tous les endpoints (§6.1 SPEC) |
| P9 | Clic "SP associé" sur une doc card → bascule onglet Projets + ouvre le panneau détail du SP. Si SP orphelin → lien inactif (§5.3 SPEC, cas M23/M24) |
