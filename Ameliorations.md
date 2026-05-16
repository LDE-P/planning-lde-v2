# Améliorations Dashboard V2

> Retours d'usage — à implémenter après la mise en ligne initiale.

## Process Cowork

- [ ] **Spec Claude Code + data.json** : quand la spec confie à Claude Code une création/mise à jour de SP dans `data.json`, inclure explicitement les champs et valeurs attendus — pour éviter que Claude Code copie des valeurs du contexte voisin (ex : incident commentaire "URGENT !" sur `spinners-dashboard`, session 2026-05-16).
- [ ] Enregistrement automatique des MD dans `data.json` docs — dès qu'un fichier `.md` est créé pour un sous-projet, l'enregistrer immédiatement (titre, desc, type, statut, subproject) plutôt qu'en fin de session via la checklist. Mettre à jour la règle 3bis du CLAUDE.md racine en conséquence.
- [ ] **Import d'un projet ancien dans GIT** : quand un projet créé dans une session ancienne (avant les conventions actuelles du dépôt) est importé dans GIT, ouvrir une session Cowork dédiée pour vérifier la cohérence — noms canoniques, alias, entrées `data.json`, tables `CLAUDE.md`. Ne pas le faire « à la rache » en fin d'une autre session.

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

- [ ] Init : restaurer les onglets dans le bon ordre (Tâches, Semaines, TCD Projets) — `duplicate_sheet` les insère en fin de liste. Utiliser `insert_sheet_index` pour contrôler la position.

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

## Vue Docs (post-impl 2026-05-15)

- [ ] **Modal d'ajout doc — inférence depuis le nom de fichier** : quand l'utilisateur saisit `planning-lde-v2/SPEC-DOCS-MD.md`, pré-remplir automatiquement `type=spec` et `title="Spécification Vue Docs"` (déduire du préfixe `SPEC-`/`AUDIT-`/`TESTS-`/`BILAN-`/etc.). Évite les saisies à valeurs par défaut peu utiles.
- [ ] **Auto-scan `/api/scan-docs`** — voir §11 SPEC-DOCS-MD.md : endpoint qui parcourt GIT/ avec exclusions standards et propose les fichiers non encore catalogués. Charge estimée : +1 à 1,5 h.

## Tests e2e

- [ ] **`test_gsheet_status_no_credentials` et `test_gsheet_init_no_credentials_returns_error` flaky par environnement** : ces tests supposent l'absence de `token.json` mais celui-ci est présent sur la machine de LDE. Ajouter `pytest.mark.skipif(token_file.exists(), reason="token.json présent — flow OAuth réussit")` pour rendre ces tests proprement skippables.
- [ ] **`tests-e2e-python/` pas dans un repo git** : décision à prendre — soit init d'un repo dédié, soit intégration dans un repo existant. Sans versioning, les 7 nouveaux fichiers de tests de la vue Docs ne sont pas traçables.
