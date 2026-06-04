# Passage de relais — Maintenance Planning LDE V2 (post-découplage GSheet)

> **Rédigé le 2026-06-04 ~06h10 (Europe/Paris)** par la session Claude Code « Découplage GSheet » (2026-06-03).
> Destinataire : la **nouvelle session de maintenance du Planning LDE**.

---

## 0. ⚠️ CE DOC SUPPLANTE `PASSAGE-V2-VERS-V3-2026-05-31.md`

L'autre doc de passage présent dans `temp/` a été rédigé par la session « incident GSheet »
(2026-05-28 → 2026-06-04) **avant** le découplage du 2026-06-03. Ses sections suivantes sont
**caduques — NE PAS les exécuter** :

| Section de l'ancien doc | Pourquoi caduque |
|---|---|
| §2 « Tâche prioritaire : ajout statut `fail` » | ✅ FAIT le 2026-06-03 (serve-v2.py + ui.js + CSS, badge orange « ÉCHEC ») |
| §3.2 « Boutons GSheet désactivés » | Boutons **supprimés** — toute la barre GSheet n'existe plus |
| §3.3 « Token OAuth à régénérer » | OAuth/gspread **supprimés** du code — plus aucun token nécessaire |
| §5 « Bugs ouverts pull/push » | Sans objet — le code de sync n'existe plus |
| §8 « Actions dans l'ordre » | Remplacées par §5 ci-dessous |

Restent valables dans l'ancien doc : §1 (ordre de lecture), §4 (chronologie historique de
l'incident), §6 (conventions LDE observées), §9-10 (points transverses, ressources).

---

## 1. À LIRE AVANT TOUTE ACTION

1. `/Users/laurentdenis/Documents/GIT/CLAUDE.md` (racine — règles obligatoires, garde-fous, checklist fin de session)
2. `planning-lde-v2/CLAUDE.md` (projet — mis à jour post-découplage : plus de sections GSheet)
3. `planning-lde-v2/notes-todo.md` (todos courants)
4. `planning-lde-v2/SPEC-DECOUPLAGE-GSHEET.md` (référence du découplage)

## 2. DÉCISION STRUCTURANTE — GSheet abandonnée (2026-06-03)

**La synchronisation Google Sheets est définitivement abandonnée.** Décision LDE, exécutée
le 2026-06-03 (plan validé, 4 questions de périmètre tranchées) :

- Le dashboard est **100 % autonome sur `data.json`**. Plus aucune connexion ni écriture GSheet.
- La GSheet en ligne (`1RY1SCZAW5…`) vit sa vie indépendamment — **ne jamais y toucher depuis le dashboard**.
- **Ne pas réintroduire** de dépendance GSheet sans nouvelle décision explicite de LDE.

### Ce qui a été supprimé
- `serve-v2.py` : −1242 lignes (gspread/OAuth, `_gs_*`, formules, handlers, routes `/api/gsheet|sync|pull*`, `_STATUS_TO_GS/FROM_GS`, `CONF_FILE`, `import math`)
- `api.js` : 9 wrappers GSheet · `app.js` : statut GSheet au boot · `ui.js` : −279 lignes (tracking push/pull localStorage, toggle 👁, écriture inline GSheet, handlers boutons, `updateGsheetStatus`, `setLoading`, `showResults`, `openPushConfirm`)
- `DASHBOARD-V2.html` : barre `#gsheet-bar` + 6 boutons, CSS associé, modale `#modal-results`
- Fichiers : `client_secret.json`, `token.json`, `serve-v2.conf.json`, `debug-*-gsheet.py`
- Tests : `test_gsheet.py`, `test_toggle_gsheet_hidden.py`
- `data.json` : champ `gsheet_hidden` retiré des 21 projets

### Ce qui a été conservé
- `alias` projet (chip d'affichage + modale « Renommer l'alias » — plus rien à voir avec la GSheet)
- Champs `type`/`commentaire` des SP (ex-GSheet-only, désormais simples champs locaux)
- Écriture atomique + garde anti-wipe + backups (`_atomic_write_json`), CORS, payload max 1 Mo
- `_target_from_qualif`, `_friday_of_isoweek`, `_slugify`, `_unique_id` (utilisés hors GSheet)

### Archivage
9 specs GSheet déplacées dans `planning-lde-v2/archive-gsheet/` (chemins `file` des docs
mis à jour dans `data.json`). Récupération complète du code possible via le tag git
**`decouplage-gsheet-baseline-2026-06-03`**.

## 3. ÉTAT GIT AU PASSAGE (2026-06-04 06h05)

- Dépôt `planning-lde-v2` : **propre, à jour avec `origin/main`** (poussé).
- Commit du découplage : **`3d5d791`** « feat(planning): découplage total Dashboard ↔ GSheet + statut fail » (11 fichiers, +135/−2028).
- `data.json` + `archive-gsheet/` avaient été commités séparément par une session concurrente (message « chore(banc)… » — contenu vérifié correct).
- Tests e2e : **158 passed, 0 échec, 0 skip** (`pytest tests-e2e-python/planning-lde/ -q`).

## 4. STATUT `fail` — LIVRÉ

- `serve-v2.py` : `'fail'` dans `_VALID_STATUSES`
- `ui.js` : `fail: 'ÉCHEC'` (STATUS_LABELS) + `'fail'` dans `SP_STATUSES` (menu de statut)
- CSS : `--fail: #f97316` + `.status-fail` (badge orange)
- Utilisé dans `data.json` : `generation-snippets-cas-pratiques-v1`, `push-auto-apres-toggle-gsheet`, `phase-6-cible-date-tcd` (+ des SP banc-de-tests passés en fail par une autre session)
- Non couvert : `STEP_STATUSES` ne contient pas `fail` (choix volontaire — les étapes utilisent `na`)

## 5. ACTIONS RESTANTES (par priorité)

1. ~~Enregistrer `SPEC-DECOUPLAGE-GSHEET.md` comme doc dans `data.json`~~ → fait lors de l'archivage de la session découplage (vérifier sa présence dans la vue Docs).
2. **P1 — `affichage-docs-vue-projet`** (~2h, spec prête : `SPEC-AFFICHAGE-DOCS-VUE-PROJET.md`)
3. **P2 — Bouton carto** dans `DASHBOARD-V2.html` (~15 min, ouvre `suivi-qualite/carto-projets-git.html`)
4. **P3 — Sort de `favicons-planning/`** (folder Cowork, hors repo — copier ou laisser)
5. **CLAUDE.md racine** : mentions GSheet caduques à nettoyer **après validation LDE** (table « Noms canoniques » colonne alias = OK car affichage ; mais les références aux « colonnes GSheet », au push/pull `serve-avancement.py` et à la « synchronisation vers Google Sheets » en fin de checklist sont obsolètes pour ce projet)
6. **Sécurité (optionnel)** : le PAT GitHub du remote (`gho_…` dans `.git/config`) est apparu en clair dans les transcripts des sessions des 2026-06-03/04 — proposer à LDE de le régénérer.

## 6. ⚠️ POINTS D'ATTENTION — MÉMOIRE DE SESSION

### Sessions concurrentes sur ce dépôt (vécu deux fois dans ma session)
Plusieurs sessions commitent `planning-lde-v2` en parallèle. Conséquences observées :
- Mes modifs `data.json` + mes `git mv` stagés ont été **embarqués dans le commit d'une autre session** sous un message sans rapport.
- Mon bilan `suivi-qualite/bilans/2026-06-03.md` a été **écrasé** par le bilan d'une autre session (restauré sous `2026-06-03-decouplage-gsheet.md`).

**Réflexes** :
- Avant d'éditer `data.json` : `git status` + si un doute, `git log -3 -- data.json`.
- Si un fichier modifié n'apparaît pas dans `git status` : comparer disque/index/HEAD (`git hash-object <f>` vs `git ls-files -s <f>` + `git log -- <f>`) → révèle un commit concurrent.
- Bilans : utiliser un nom suffixé `YYYY-MM-DD-<sujet>.md` d'emblée, jamais le nom nu si plusieurs sessions tournent le même jour.
- Suggestion de verrou léger notée dans `Ameliorations.md` (« Sessions concurrentes sur data.json — 2026-06-03 »).

### Conventions vérifiées en pratique
- Messages de commit multi-lignes **exécutés par l'agent** : utiliser plusieurs `-m` (un par paragraphe). La forme `-m "...\n..."` produit des `\n` littéraux (le format `\n` du CLAUDE.md racine est réservé aux commandes transmises à LDE pour copier-coller).
- Trailer obligatoire des commits agent : `Co-Authored-By: Claude <modèle> <noreply@anthropic.com>`.
- `data.json` : écrire avec `json.dumps(data, indent=2, ensure_ascii=False)` + newline final pour matcher le format du serveur (diffs propres).
- Avant de déplacer un `.md` du projet : vérifier s'il est référencé comme doc (`grep '"file":' data.json`) et mettre à jour le chemin.
- Apostrophe courbe `'` (U+2019) dans tout libellé généré (règle racine).

### Environnement
- Dépôt perso LDE-P → l'agent peut commit **et** push (token dans `.git/config`).
- Le serveur tourne sur **port 8001** (`python3 serve-v2.py`) ; le sandbox de l'agent **ne peut pas joindre localhost** — validation visuelle = LDE.
- LDE doit **redémarrer `serve-v2.py`** après le découplage s'il ne l'a pas déjà fait (le process en mémoire peut encore être l'ancienne version).

## 7. RÉFÉRENCES

- SPEC du découplage : `planning-lde-v2/SPEC-DECOUPLAGE-GSHEET.md`
- Bilan de la session découplage : `suivi-qualite/bilans/2026-06-03-decouplage-gsheet.md`
- Bilan de la session incident GSheet (historique) : `suivi-qualite/bilans/2026-06-04-planning-incident-gsheet-passage-v3.md`
- Anciennes specs GSheet : `planning-lde-v2/archive-gsheet/`
- Tag de restauration : `decouplage-gsheet-baseline-2026-06-03`
