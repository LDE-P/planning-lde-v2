# Notes & Todo — Planning LDE V2

> Fichier de continuité inter-sessions. Mis à jour à chaque fin de session.
> Dernière mise à jour : 2026-06-04

---

## ✅ Découplage total Dashboard ↔ GSheet (2026-06-03)

La synchronisation Google Sheets a été **définitivement abandonnée**. Le dashboard
est désormais 100 % autonome sur `data.json`. Tout le code de sync (gspread, OAuth,
push/pull/TCD, `gsheet_hidden`, boutons) a été retiré. Voir `SPEC-DECOUPLAGE-GSHEET.md`.

Conséquences (tous les anciens todos GSheet sont **clos / sans objet**) :
- ✅ Statut `fail` ajouté au dashboard (serve-v2.py + ui.js + CSS) — *était le 1er todo*
- ✅ ~~Régénérer le token OAuth Google Sheets~~ — sans objet (OAuth retiré)
- ✅ ~~Réactiver boutons Push/Pull/Init/Modèles~~ — sans objet (boutons retirés)
- ✅ ~~DEBUG pull non capté / push écrasant col C-J~~ — sans objet (sync retirée)
- ✅ ~~Note Gemini #REF! pour V3~~ — sans objet (archivée dans `archive-gsheet/`)
- ✅ ~~Supprimer lignes TestsQuiz dans la GSheet via push~~ — sans objet (plus de push)
- Les 2 SP GSheet ouverts (`push-auto-apres-toggle-gsheet`, `phase-6-cible-date-tcd`)
  sont passés en statut **`fail`** dans data.json.

---

## Rappel prochaine session

### ✅ P1 — `affichage-docs-vue-projet` — LIVRÉ (2026-06-04)

Docs inline dans Vue Projets + Vue Archives + panneau latéral slide-in.
SP `affichage-docs-vue-projet` passé en `done` dans data.json.

### ✅ P3 — `favicons-planning/` — DÉCIDÉ (2026-06-04)

Pas de copie dans le repo. Favicon choisie déjà versionnée comme `favicon.svg`.

### P2 — Bouton carto dans `DASHBOARD-V2.html` (~15 min)

Ajouter un bouton dans le dashboard V2 ouvrant [carto-projets-git.html](computer:///Users/laurentdenis/Documents/GIT/suivi-qualite/carto-projets-git.html).

### À surveiller — PAT GitHub en clair dans les transcripts

Le token `gho_…` dans `.git/config` est apparu dans les transcripts des sessions 2026-06-03/04.
Proposer à LDE de le régénérer (GitHub → Settings → Developer settings → Personal access tokens).

---

## Backups ponctuels disponibles

- [backups/data-2026-05-28.json](computer:///Users/laurentdenis/Documents/GIT/planning-lde-v2/backups/data-2026-05-28.json) — état avant ajout 12 SPs GSheet Datamart
- [backups/data-archives-2026-05-28.json](computer:///Users/laurentdenis/Documents/GIT/planning-lde-v2/backups/data-archives-2026-05-28.json) — idem côté archives
- Tag git `decouplage-gsheet-baseline-2026-06-03` — état avant le découplage GSheet
