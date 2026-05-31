# Notes & Todo — Planning LDE V2

> Fichier de continuité inter-sessions. Mis à jour à chaque fin de session.  
> Dernière mise à jour : 2026-05-28

---

## Rappel prochaine session

### 🥇 À TRAITER EN PREMIER — Ajouter le statut `fail` dans le dashboard

**Tâche unique à la reprise**, avant tout autre travail.

**Contexte** : le statut `fail` vient d'être ajouté au schéma `data.json` (cf `planning-lde-v2/CLAUDE.md`) pour tracer les sous-projets abandonnés après échec. Déjà utilisé dans `data.json` :
- SP `generation-snippets-cas-pratiques-v1` sous **Banc de tests**
- step « Audit persona — ÉCHEC » dans ce même SP

**Préalable** : lire d'abord [/Users/laurentdenis/Documents/GIT/CLAUDE.md](computer:///Users/laurentdenis/Documents/GIT/CLAUDE.md) puis `planning-lde-v2/CLAUDE.md`.

**Trois fichiers à modifier** :

1. **`serve-v2.py`**
   - Ajouter `'fail'` dans `_VALID_STATUSES` (ligne ~30)
   - Ajouter `'fail'` dans `_STATUS_TO_GS` (valeur GSheet suggérée : `'FAIL'`)
   - `_STATUS_FROM_GS` est généré automatiquement par dict comprehension → pas de changement

2. **`DASHBOARD-V2.html`**
   - Ajouter la variable CSS `--fail` (couleur suggérée : `#f97316`, orange brûlé — distinct de `blocked`/rouge et de `todo`/gris)
   - Ajouter `.status-fail` dans le bloc des status-badge (ligne ~331–337) — même pattern que `.status-blocked`
   - Ajouter le label d'affichage `'fail'` dans la fonction JS qui traduit les statuts en texte lisible (chercher les labels `'blocked'`, `'done'`, etc.) — label suggéré : **« Échec »**
   - Ajouter la même classe dans le bloc `.step-status-badge` si les steps ont leur propre jeu de badges

**Contraintes** :
- Lire les blocs concernés avant d'éditer (ne pas modifier à l'aveugle)
- Pas de modification hors des trois points ci-dessus
- Commit dans `planning-lde-v2/` après validation

**Vérification attendue** : après modification, ouvrir `data.json`, confirmer que le SP `generation-snippets-cas-pratiques-v1` (status: `"fail"`) s'affiche correctement dans le dashboard avec le badge orange **« Échec »**.

---

### 🚨 P0 — Régénérer le token OAuth Google Sheets

Token expiré le 2026-05-28 (`invalid_grant: Token has been expired or revoked`). Procédure :
1. Lancer `serve-v2.py` (port 8001)
2. `rm token.json`
3. Déclencher une action GSheet (mais boutons désactivés, cf P0 suivant) → autoriser dans navigateur
4. Vérifier que `token.json` est régénéré

### 🚨 P0 — Réactiver boutons Push/Pull/Init/Modèles (après debug)

Boutons désactivés dans `DASHBOARD-V2.html` (commit `29e8ec8`) suite à incident perte de données GSheet Datamart le 2026-05-28. Réactiver en retirant `disabled` une fois les bugs ci-dessous diagnostiqués.

### 🐛 DEBUG — Pull silencieusement non capté

Le pull du 2026-05-28 n'a pas écrit dans `data.json` les éditions manuelles GSheet (Type/qualif/target/titre/commentaire). À investiguer dans `serve-v2.py` : `_pull_from_gsheet()` (ou équivalent). Vérifier réponse 200 + flux d'écriture vers `data.json`.

### 🐛 DEBUG — Push écrasant col C et J malgré spec

Le push du 2026-05-28 a vidé col C (Type) et col J (Commentaire) côté GSheet — alors que la spec dit que push ne touche que A-B, D-I, K-L. À investiguer dans `serve-v2.py` : `_push_to_gsheet()` et le `batch_clear`.

### 📘 Référence — Note Gemini sur erreurs #REF! et structure GSheet (2026-05-28) — **POUR V3**

Gemini a corrigé directement dans la GSheet en ligne (indépendamment du Dashboard) des erreurs `#REF!` et a fait des recommandations sur les Tableaux Dynamiques + espaces fantômes dans les noms.

**À reprendre lors de la consolidation GSheet en V3** (pas urgent, à archiver dans le scope V3).

→ [notes-gsheet-gemini-2026-05-28.md](computer:///Users/laurentdenis/Documents/GIT/planning-lde-v2/notes-gsheet-gemini-2026-05-28.md)

Impacts probables côté code à vérifier en V3 : strip systématique sur col A/B au pull, compatibilité gspread avec les Tableaux Dynamiques Google natifs, repenser la convention de notes hors tableau.

### P1 — `affichage-docs-vue-projet` (~2h, spec prête)

Affichage des documents associés dans la vue projet du dashboard V2. SPEC prête, en attente d'implémentation.

### P2 — Bouton carto dans `DASHBOARD-V2.html` (~15 min)

Ajouter un bouton dans le dashboard V2 ouvrant [carto-projets-git.html](computer:///Users/laurentdenis/Documents/GIT/suivi-qualite/carto-projets-git.html).

### P3 — Décider du sort de `favicons-planning/`

Les 6 SVG + preview.html sont actuellement dans le folder Cowork `Planning LDE V2/favicons-planning/`, **PAS dans le repo git**. À décider : les copier dans le repo pour versionnement, ou les laisser hors repo. La favicon choisie (lettre P, option 03) est déjà versionnée comme `favicon.svg` à la racine.

### P3 — Fusion Schmoll + TestsQuiz → Cas Pratiques ✅ FAIT (2026-05-25)

`generateur-snippets-schmoll` et `tests-quiz-plateformes` archivés. 10 SPs fusionnés dans `cas-pratiques-project`.

**Action manuelle restante :** supprimer lignes `TestsQuiz` dans la GSheet → push depuis le dashboard (à faire après réactivation push).

---

## Backups ponctuels disponibles

- [backups/data-2026-05-28.json](computer:///Users/laurentdenis/Documents/GIT/planning-lde-v2/backups/data-2026-05-28.json) — état avant ajout 12 SPs GSheet Datamart
- [backups/data-archives-2026-05-28.json](computer:///Users/laurentdenis/Documents/GIT/planning-lde-v2/backups/data-archives-2026-05-28.json) — idem côté archives
