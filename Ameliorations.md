# Améliorations Dashboard V2

> Retours d'usage — à implémenter après la mise en ligne initiale.

## Process Cowork

- [ ] **Spec Claude Code + data.json** : quand la spec confie à Claude Code une création/mise à jour de SP dans `data.json`, inclure explicitement les champs et valeurs attendus — pour éviter que Claude Code copie des valeurs du contexte voisin (ex : incident commentaire "URGENT !" sur `spinners-dashboard`, session 2026-05-16).
- [ ] Enregistrement automatique des MD dans `data.json` docs — dès qu'un fichier `.md` est créé pour un sous-projet, l'enregistrer immédiatement (titre, desc, type, statut, subproject) plutôt qu'en fin de session via la checklist. Mettre à jour la règle 3bis du CLAUDE.md racine en conséquence.
- [ ] **Import d'un projet ancien dans GIT** : quand un projet créé dans une session ancienne (avant les conventions actuelles du dépôt) est importé dans GIT, ouvrir une session Cowork dédiée pour vérifier la cohérence — noms canoniques, alias, entrées `data.json`, tables `CLAUDE.md`. Ne pas le faire « à la rache » en fin d'une autre session.
- [ ] **Projet sans répertoire au moment de la création** : la procédure « Création d'un nouveau projet » du `CLAUDE.md` racine présuppose qu'un projet GIT a un dossier dès le départ. Cas observé en session 2026-05-17 (`Notification Front`) : l'outil a été créé d'abord dans Cowork (artifact sous `~/Documents/Claude/Artifacts/`, tâche planifiée sous `~/Documents/Claude/Scheduled/`), puis rattaché à un dossier `projets-divers/notifications-front` créé a posteriori. Soit autoriser explicitement l'absence de `folder` dans `data.json` (et documenter le cas), soit imposer la création d'un dossier vide dans GIT dès l'apparition du projet — pour qu'aucun projet ne vive entièrement hors du périmètre versionné. Statuer et mettre à jour la section « Création d'un nouveau projet » en conséquence.
- [ ] **Propager la convention d'estimation 4 dimensions au CLAUDE.md racine** — mémoire Cowork `spec-estimation-format` validée en session 2026-05-23 : ne plus chiffrer les SPECs en heures-agent (écart x12 constaté), remplacer par complexité/volume/risque/charge-LDE. Actuellement visible uniquement aux sessions Cowork via `MEMORY.md`, invisible aux sessions Claude Code qui s'appuient sur les CLAUDE.md du dépôt. Conséquence : CC continuera à proposer des SPECs avec des heures tant que la convention n'est pas dans le CLAUDE.md racine ou projet.
- [ ] **rangement-git : vérifier SPECs untracked** dans les sous-projets — pattern observé en session 2026-05-23 (3 SPECs `SPEC-RATIONALISATION*.md` puis 2 SPECs `SPEC-CORRECTIONS-TABLEAU*.md` non commitées en fin de session). Étendre le skill `rangement-git` pour signaler les fichiers `SPEC-*.md` / `AUDIT-*.md` / `TESTS-*.md` untracked dans les dossiers de projets. Probablement reproductible sur d'autres projets perso.

## UI Dashboard

- [ ] Ajouter le statut `blocked` (STAND BY) dans le dashboard V2 — correspondance GSheet : `STD BY`.
- [x] Bugfix : message "Not Found" dans le toast après suppression d'un projet + débugger la suppression de projet (routing corrigé — handler `/api/remove-project` présent et fonctionnel)
- [x] Bugfix : clic sur `.status-badge` (changement de statut) ne doit pas refermer le bloc projet (corrigé via `_openProjects` Set — état open/fermé persisté à travers les `renderAll()`)
- [x] Bouton pour retirer un projet / un sous-projet du dashboard
- [x] Bouton pour renommer un sous-projet
- [x] Charte graphique : fond blanc, style de la V1
- [x] Filtres (En cours, À faire, Spec, Revue, Tous) → ouvrent automatiquement les blocs affichés
- [x] Liens "Tout ouvrir" / "Tout fermer" (tout déplier / tout plier) comme dans la V1
- [x] Bugfix : "Tout ouvrir" et "Tout fermer" font disparaître tous les projets (guard `!btn.dataset.filter` dans le handler filter)

## GSheet

- [x] **Check intégrité — docs orphelins** : le script de check (CLAUDE.md racine) ne cherche le SP référencé par un doc que dans `data['projects'][x]['subprojects']`. Si le SP est archivé (`data-archives.json`), le doc est faussement signalé comme orphelin. Corrigé le 2026-05-17 — le script vérifie maintenant aussi dans les archives avant de lever l'alerte.
- [ ] Init : restaurer les onglets dans le bon ordre (Tâches, Semaines, TCD Projets) — `duplicate_sheet` les insère en fin de liste. Utiliser `insert_sheet_index` pour contrôler la position.
- [ ] **Modale de confirmation avant Init GSheet** : l'init recrée les onglets à blanc (perte des col C/J GSheet-only non préservées si pas pushées avant). Demander confirmation explicite avant exécution. Constaté 2026-05-18 lors des tests RAF Option B.

- [x] Quand la connexion GSheet est active, le texte `#gsheet-status` devient un lien vers la GSheet (ouvert en `target="_blank"`)
- [x] Au push et au pull : afficher un état d'avancement animé ("En cours…") puis une modale de résultats listant ce qui a été pushé / pullé
- [x] GSheet onglets Semaines et TCD Projets : libellés colonnes C1–G1 dynamiques au push — format `S<nn>` pour S-1, `S<nn> (P0)`→`(P3)` pour S0→S+3 (fonction `_tcd_headers()`, ISO week réel)
- [x] Bugfix : ajout d'un projet dans la GSheet → non créé dans `data.json` au pull (pull crée le projet si alias inconnu)
- [x] Bugfix : ajout d'un sous-projet dans la GSheet → non récupéré au pull (pull crée le sous-projet si nom inconnu dans le projet)
- [x] Bouton sur la ligne de projet + modale pour renommer l'alias (nom court utilisé dans la GSheet) (bouton ✎ + `#modal-rename-alias` + `/api/save-project`)
- [x] Bugfix : alias renommé non répercuté dans TCD Projets après push (résolu — `_build_tcd_rows()` construit TCD depuis `data.json`, plus de dépendance aux formules Semaines)
- [x] Bugfix : push écrase Type (col C) et Commentaire (col J) — `batch_clear` et `batch_update` ne touchent plus que A-B, D-I, K-L
- [x] Endpoint `POST /api/gsheet/format` + bouton "Format" : `_gs_format()` avec `setDataValidation` sur col C (Type) et col I (Avanc.). Appelé manuellement uniquement.
- [x] TCD Projets — colonne RAF (col B) : formules Semaines réutilisées (`_f_semaines_b2/b3/b_row`), update en `USER_ENTERED` → les éditions team sur C-G recalculent B automatiquement
- [x] Bouton Push : harmoniser la mise en forme avec les boutons Pull (classe `primary` retirée)
- [x] Bugfix : formule B2 de TCD Projets en erreur ("Impossible d'analyser le paramètre 0.9 de VALUE en tant que nombre") — cause : C2-G2 étaient des strings statiques Python avec décimale anglaise ("0.9 h."), `VALUE("0.9")` échoue en locale française. Fix : C2-G2 et C3-G3 sont désormais aussi des formules (`_f_semaines_col2/3`), GSheet calcule les valeurs en locale native.

## Historique / Traçabilité

- [ ] **Diff complet dans `history.jsonl`** — logger les valeurs avant/après sur `save-subproject` (nom, statut, charge, raf…) et les champs modifiés sur `pull-from-gsheet` (projet, sp, champ, ancienne valeur, nouvelle valeur). Actuellement seule l'action est tracée, pas ce qui a changé.
- [ ] **Endpoint `/api/history`** — exposer l'historique depuis le dashboard, filtrable par projet/sous-projet/action/date. Permettrait de détecter les écrasements silencieux (ex. pull GSheet renommant des sous-projets) avant de clore une session.

## Cowork / Workflow

- [ ] Si un fichier utilisé dans une session comporte un espace dans son nom, proposer à LDE de le renommer.
- [ ] Lien sous-projet ↔ session Cowork : ajouter un champ `session` (texte libre) sur les sous-projets dans `data.json`, affiché comme badge dans le dashboard. Prévoir l'évolution vers un lien cliquable si Cowork expose un jour des URLs de session. À traiter dans une session dédiée.
- [ ] **Automatiser le suffixe `(CLOS)`** sur le renommage de la session Cowork à la clôture, plutôt que LDE doive le faire manuellement (cf. checklist étape 5 du CLAUDE.md racine). Slash command ou hook au niveau de l'app Cowork. Source : bilan session 2026-05-23.
- [ ] **Récap visuel auto dans les longues sessions de définition** : sur les sessions de définition ligne par ligne (cas typique : refonte de tableau, audit avec actions cumulées), proposer un mini-widget de progression qui résume automatiquement l'état cumulé toutes les N décisions. Évite que Cowork doive ré-énoncer manuellement l'état à chaque étape. Source : bilan session 2026-05-23 (10 décisions consécutives sur le tableau du simulateur).
- [ ] **AskUserQuestion : passer de 4 à 5-6 options maximum** sur des questions de design qui nécessitent de couvrir plus de variantes. La limite à 4 force à condenser ou à utiliser le fallback "Autre — à préciser" plus souvent que souhaitable. Source : bilan session 2026-05-23.

## Vue Docs (post-impl 2026-05-15)

- [ ] **Modal d'ajout doc — inférence depuis le nom de fichier** : quand l'utilisateur saisit `planning-lde-v2/SPEC-DOCS-MD.md`, pré-remplir automatiquement `type=spec` et `title="Spécification Vue Docs"` (déduire du préfixe `SPEC-`/`AUDIT-`/`TESTS-`/`BILAN-`/etc.). Évite les saisies à valeurs par défaut peu utiles.
- [ ] **Auto-scan `/api/scan-docs`** — voir §11 SPEC-DOCS-MD.md : endpoint qui parcourt GIT/ avec exclusions standards et propose les fichiers non encore catalogués. Charge estimée : +1 à 1,5 h.

## Tests e2e

- [ ] **`test_gsheet_status_no_credentials` et `test_gsheet_init_no_credentials_returns_error` flaky par environnement** : ces tests supposent l'absence de `token.json` mais celui-ci est présent sur la machine de LDE. Ajouter `pytest.mark.skipif(token_file.exists(), reason="token.json présent — flow OAuth réussit")` pour rendre ces tests proprement skippables.
- [ ] **`tests-e2e-python/` pas dans un repo git** : décision à prendre — soit init d'un repo dédié, soit intégration dans un repo existant. Sans versioning, les 7 nouveaux fichiers de tests de la vue Docs ne sont pas traçables.
