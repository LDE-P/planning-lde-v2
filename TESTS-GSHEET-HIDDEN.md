# TESTS — Exclusion GSheet par projet (`gsheet_hidden`)

> **Statut :** VALIDÉ — prêt pour implémentation
> **Date :** 2026-05-16
> **Référence :** SPEC-GSHEET-HIDDEN.md

> **Note transversale :** les tests des sections A à D supposent un `data.json` de test avec au moins deux projets — un projet visible (P-visible, `gsheet_hidden` absent) et un projet masqué (P-masqué, `gsheet_hidden: true`). P-masqué possède au moins un sous-projet S1. P-visible possède au moins un sous-projet S2. Dans les tests Push/Pull (B, C, D), "GSheet" désigne l'onglet Tâches de la spreadsheet de test.

---

## Section A — Endpoint `/api/toggle-gsheet-hidden`

### A1 — Toggle nominal : visible → masqué

**Prérequis :** P-visible dans `data.json` sans champ `gsheet_hidden` (ou `gsheet_hidden: false`).

**Action :** `POST /api/toggle-gsheet-hidden` `{ "projectId": "p-visible" }`

**Attendu :**
- Réponse `200 { "ok": true, "gsheet_hidden": true }`
- `data.json` : P-visible contient `"gsheet_hidden": true`

### A2 — Toggle nominal : masqué → visible

**Prérequis :** P-masqué dans `data.json` avec `gsheet_hidden: true`.

**Action :** `POST /api/toggle-gsheet-hidden` `{ "projectId": "p-masque" }`

**Attendu :**
- Réponse `200 { "ok": true, "gsheet_hidden": false }`
- `data.json` : P-masqué contient `"gsheet_hidden": false`

### A3 — Double toggle → retour à l'état initial

**Prérequis :** P-visible sans `gsheet_hidden`.

**Action :** deux appels successifs `POST /api/toggle-gsheet-hidden` `{ "projectId": "p-visible" }`

**Attendu :**
- Après le 1er appel : `gsheet_hidden: true` dans `data.json`
- Après le 2ème appel : `gsheet_hidden: false` dans `data.json` (ou champ absent — les deux sont équivalents pour le comportement)

### A4 — projectId manquant

**Action :** `POST /api/toggle-gsheet-hidden` `{}`

**Attendu :** `400 { "error": "projectId requis" }` (libellé aligné sur `_handle_remove_project`)

### A5 — projectId inconnu

**Action :** `POST /api/toggle-gsheet-hidden` `{ "projectId": "inexistant" }`

**Attendu :** `404 { "error": "Projet introuvable" }`

### A6 — Payload trop grand

**Action :** `POST /api/toggle-gsheet-hidden` avec un corps > 1 Mo

**Attendu :** `413`

### A7 — Méthode GET refusée

**Action :** `GET /api/toggle-gsheet-hidden`

**Attendu :** `405` (ou `404` selon le routeur — cohérent avec les autres endpoints POST-only)

### A8 — Headers CORS présents

**Action :** `POST /api/toggle-gsheet-hidden` `{ "projectId": "p-visible" }`

**Attendu :** header `Access-Control-Allow-Origin: *` présent dans la réponse

---

## Section B — Push (`_gs_push` et `_gs_push_preview`)

### B1 — Push nominal : projet masqué absent de l'onglet Tâches

**Prérequis :** P-masqué (`gsheet_hidden: true`) avec SP S1. P-visible avec SP S2. GSheet initialisée (vide ou avec des données existantes).

**Action :** push complet (`/api/sync-to-gsheet`)

**Attendu :**
- Onglet Tâches : contient les lignes de P-visible (S2)
- Onglet Tâches : **aucune ligne** avec l'alias de P-masqué

### B2 — Push efface les lignes résiduelles d'un projet nouvellement masqué

**Prérequis :** P-masqué était visible lors du push précédent — ses lignes (incluant valeurs col C et col J non vides) sont présentes dans la GSheet. Entre-temps, `gsheet_hidden` a été passé à `true`.

**Action :** push complet

**Attendu :**
- Onglet Tâches : toutes les colonnes (A à L) des lignes de P-masqué sont vides — y compris **C (Type) et J (Commentaire)**
- Onglet Tâches : lignes de P-visible présentes et correctes (col C et J préservées si renseignées avant le push)

### B3 — Projet masqué absent du TCD Projets

**Prérequis :** idem B1.

**Action :** push complet

**Attendu :**
- Onglet TCD Projets : aucune ligne avec le nom/alias de P-masqué

### B4 — Preview push : `hidden_projects` présent

**Prérequis :** P-masqué (`gsheet_hidden: true`).

**Action :** `POST /api/sync-to-gsheet/preview`

**Attendu :**
- Réponse JSON contient `"hidden_projects": ["<alias ou name de P-masqué>"]`

### B5 — Preview push : `hidden_projects` vide si aucun projet masqué

**Prérequis :** aucun projet avec `gsheet_hidden: true` dans `data.json`.

**Action :** `POST /api/sync-to-gsheet/preview`

**Attendu :**
- Réponse JSON contient `"hidden_projects": []` (ou clé absente — à trancher à l'implémentation ; `[]` préféré pour cohérence UI)

### B6 — Push avec plusieurs projets masqués

**Prérequis :** deux projets avec `gsheet_hidden: true` (P-masqué-1 et P-masqué-2).

**Action :** push complet

**Attendu :**
- Aucune ligne de P-masqué-1 ni P-masqué-2 dans l'onglet Tâches
- Preview : `hidden_projects` contient les deux alias/noms

### B7 — Projet sans alias : utilisation du `name` dans `hidden_projects`

**Prérequis :** P-masqué sans champ `alias` dans `data.json`, `gsheet_hidden: true`.

**Action :** `POST /api/sync-to-gsheet/preview`

**Attendu :**
- `hidden_projects` contient `proj['name']` (pas d'erreur KeyError)

### B8 — Préservation C/J de P-visible quand un autre projet du milieu est exclu

> Test central du correctif §5.2 (Option 2). Vérifie l'absence de décalage des colonnes GSheet-only.

**Prérequis :**
- `data.json` contient dans cet ordre : P-A (visible, 2 SP), P-masqué (visible au moment du setup, 3 SP), P-B (visible, 2 SP)
- Push initial effectué → 7 lignes dans Tâches
- Dans la GSheet, l'équipe a renseigné **col C (Type)** et **col J (Commentaire)** pour les 7 lignes avec des valeurs distinctes par ligne (ex. `Type-A1`, `Comm-A1`, …, `Type-B2`, `Comm-B2`)
- Ensuite, P-masqué passe à `gsheet_hidden: true`

**Action :** push complet

**Attendu :**
- Lignes 2-3 (P-A) : col C = `Type-A1`/`Type-A2`, col J = `Comm-A1`/`Comm-A2` (inchangées)
- Lignes 4-5 (P-B) : col C = `Type-B1`/`Type-B2`, col J = `Comm-B1`/`Comm-B2` — **les valeurs de P-B sont là**, pas celles de P-masqué décalées
- Lignes 6+ : vides (col A à L)
- **Aucun décalage** : aucune valeur `Type-Masqué-*` ou `Comm-Masqué-*` ne subsiste dans la feuille

### B9 — Préservation C/J après simple suppression d'un SP du milieu (effet de bord positif)

> Vérifie que le correctif §5.2 corrige aussi le bug pré-existant.

**Prérequis :**
- P-visible avec 4 SP (S1, S2, S3, S4) dans cet ordre, push initial fait, col C et J renseignées pour les 4 lignes
- Suppression de S2 dans `data.json`

**Action :** push complet

**Attendu :**
- Ligne 2 (S1) : C/J inchangées
- Ligne 3 (S3) : col C = `Type-S3`, col J = `Comm-S3` — pas les valeurs de S2 décalées
- Ligne 4 (S4) : col C = `Type-S4`, col J = `Comm-S4`
- Ligne 5+ : vides

---

## Section C — TCD Projets (`_build_tcd_rows`)

### C1 — Projet masqué absent du TCD

**Prérequis :** P-masqué (`gsheet_hidden: true`) avec des sous-projets portant du RAF.

**Action :** push complet

**Attendu :**
- Onglet TCD Projets : aucune ligne avec le nom/alias de P-masqué
- Le total de RAF du TCD ne comprend pas les RAF de P-masqué

### C2 — Projet visible présent dans le TCD après push où un autre projet est masqué

**Prérequis :** P-masqué (`gsheet_hidden: true`) et P-visible avec RAF non nul.

**Action :** push complet

**Attendu :**
- TCD : P-visible présent avec ses valeurs correctes
- Pas de régression sur les lignes des projets visibles

---

## Section D — Pull (`_gs_pull_taches` et preview)

### D1 — Pull nominal : lignes d'un projet masqué ignorées

**Prérequis :** GSheet contient des lignes avec l'alias de P-masqué. P-masqué dans `data.json` avec `gsheet_hidden: true`.

**Action :** `POST /api/pull-from-gsheet`

**Attendu :**
- `data.json` : P-masqué et ses sous-projets **inchangés** (les valeurs GSheet ne sont pas importées)
- Réponse JSON contient `"ignored_projects"` incluant l'alias de P-masqué (dédupliqué)

### D2 — Pull : pas de création de projet fantôme pour un alias masqué inconnu

**Prérequis :** GSheet contient des lignes avec un alias X. Dans `data.json`, le projet portant cet alias a `gsheet_hidden: true` mais un `alias` différemment capitalisé (test de la comparaison insensible à la casse).

**Action :** `POST /api/pull-from-gsheet`

**Attendu :**
- Aucun nouveau projet créé dans `data.json` pour l'alias X
- L'alias X apparaît dans `ignored_projects`

### D3 — Pull : alias totalement inconnu → création normale (non masqué)

**Prérequis :** GSheet contient des lignes avec un alias Y absent de `data.json`. Aucun projet masqué ne porte cet alias.

**Action :** `POST /api/pull-from-gsheet`

**Attendu :**
- Comportement actuel non régressé : nouveau projet créé dans `data.json` pour Y
- Y n'apparaît **pas** dans `ignored_projects`

### D4 — Preview pull : `ignored_projects` présent si projet masqué dans GSheet

**Prérequis :** idem D1.

**Action :** `POST /api/pull-from-gsheet/preview`

**Attendu :**
- Réponse JSON contient `"ignored_projects"` avec l'alias de P-masqué

### D5 — Preview pull : `ignored_projects` vide si aucune ligne masquée dans GSheet

**Prérequis :** GSheet ne contient aucune ligne dont l'alias correspond à un projet masqué.

**Action :** `POST /api/pull-from-gsheet/preview`

**Attendu :**
- `"ignored_projects": []` (ou clé absente)

### D6 — Pull sur un projet masqué avec plusieurs sous-projets dans la GSheet

**Prérequis :** GSheet contient 5 lignes pour P-masqué (5 SP différents). `gsheet_hidden: true`.

**Action :** `POST /api/pull-from-gsheet`

**Attendu :**
- `data.json` : P-masqué inchangé (0 mise à jour)
- `ignored_projects` : alias de P-masqué cité **une seule fois** (dédupliqué)

---

## Section E — UI Dashboard

### E1 — Icône affichée dans l'en-tête de chaque projet

**Prérequis :** dashboard chargé avec P-visible et P-masqué.

**Attendu :**
- Chaque en-tête de projet affiche un bouton `btn-toggle-gsheet` avec l'icône `👁`
- Le bouton est positionné **avant** les boutons archiver et supprimer dans `.project-actions`

### E2 — Classe CSS selon l'état du projet

**Prérequis :** P-visible (`gsheet_hidden` absent), P-masqué (`gsheet_hidden: true`).

**Attendu :**
- Bouton de P-visible : possède la classe `gsheet-visible` → icône barrée (`text-decoration: line-through`)
- Bouton de P-masqué : **ne possède pas** la classe `gsheet-visible` → icône non barrée

### E3 — Tooltip correct selon l'état

**Attendu :**
- P-visible : `title="Ce projet est inclus dans la GSheet — cliquer pour l'exclure"`
- P-masqué : `title="Ce projet est exclu de la GSheet — cliquer pour le réinclure"`

### E4 — Modale d'exclusion (projet visible → masqué)

**Action :** clic sur le bouton `btn-toggle-gsheet` d'un projet visible

**Attendu :**
- Modale ouverte avec titre `"Exclure de la GSheet ?"`
- Corps contient le nom du projet et mentionne que le prochain push supprimera ses lignes
- Deux boutons : `[Annuler]` et `[Exclure]`

### E5 — Annuler la modale d'exclusion : pas de changement

**Action :** clic sur `[Annuler]` dans la modale d'exclusion

**Attendu :**
- `gsheet_hidden` non modifié dans `data.json` (pas d'appel API)
- Modale fermée, icône inchangée

### E6 — Confirmer l'exclusion : icône mise à jour immédiatement

**Action :** clic sur `[Exclure]` dans la modale d'exclusion d'un projet visible

**Attendu :**
- Appel `POST /api/toggle-gsheet-hidden`
- Classe `gsheet-visible` retirée du bouton → icône non barrée
- Tooltip mis à jour : `"Ce projet est exclu de la GSheet — cliquer pour le réinclure"`
- Modale fermée

### E7 — Modale de réinclusion (projet masqué → visible)

**Action :** clic sur le bouton d'un projet masqué

**Attendu :**
- Titre `"Réinclure dans la GSheet ?"`
- Corps mentionne que le projet réapparaîtra au prochain push
- Deux boutons : `[Annuler]` et `[Réinclure]`

### E8 — Confirmer la réinclusion : icône mise à jour

**Action :** clic sur `[Réinclure]`

**Attendu :**
- Classe `gsheet-visible` ajoutée au bouton → icône barrée
- Tooltip mis à jour : `"Ce projet est inclus dans la GSheet — cliquer pour l'exclure"`

### E9 — Modale push preview : avertissement si projets masqués

**Prérequis :** P-masqué dans `data.json`.

**Action :** ouvrir la modale push preview depuis le dashboard

**Attendu :**
- La modale affiche un bloc d'avertissement : `⚠ Projets exclus de la GSheet (leurs lignes seront supprimées) :` suivi de la liste des alias/noms masqués

### E10 — Modale push preview : pas d'avertissement si aucun projet masqué

**Prérequis :** aucun projet avec `gsheet_hidden: true`.

**Action :** ouvrir la modale push preview

**Attendu :**
- Le bloc d'avertissement est absent (pas de section `⚠ Projets exclus`)

### E11 — Modale pull result : signalement des lignes ignorées

**Prérequis :** GSheet contient des lignes de P-masqué. Pull lancé.

**Attendu :**
- La modale de résultat pull affiche : `ℹ X ligne(s) ignorées (projets exclus de la GSheet) :` + liste des alias

### E12 — Tooltips enrichis sur les autres boutons

**Attendu (non régressif) :**
- Bouton renommer SP : `title` contient `"sous-projet"` (ex. `"Renommer ce sous-projet"`)
- Bouton archiver SP : `title` contient `"sous-projet"` (ex. `"Archiver ce sous-projet"`)
- Bouton supprimer SP : `title` contient `"sous-projet"`

---

## Section F — Cas limites et rétrocompatibilité

### F1 — `gsheet_hidden: false` équivalent à champ absent

**Prérequis :** projet avec `gsheet_hidden: false` explicite.

**Action :** push + pull

**Attendu :**
- Comportement identique à un projet sans le champ : inclus dans push et pull
- Aucune erreur côté serveur

### F2 — Migration : projets existants sans le champ ne sont pas affectés

**Prérequis :** `data.json` de production (aucun projet avec `gsheet_hidden`).

**Action :** push puis pull (sans modification du code ni des données)

**Attendu :**
- Comportement identique à avant l'implémentation (aucune régression)

### F3 — Tous les projets masqués → push produit une GSheet vide (hors en-tête)

**Prérequis :** tous les projets dans `data.json` ont `gsheet_hidden: true`.

**Action :** push complet

**Attendu :**
- Onglet Tâches : seule la ligne d'en-tête subsiste (A1–K1), toutes les lignes de données sont vides
- Pas d'erreur serveur

### F4 — Projet masqué avec alias identique à un projet visible (collision)

> Ce cas ne devrait pas se produire en pratique (alias uniques), mais il est couvert pour robustesse. Garanti par la vérification `hidden_aliases` **avant** `_find_sp` (cf. §6.1).

**Prérequis :** P-masqué et P-visible ont le même alias dans `data.json`, **quel que soit leur ordre** dans `data['projects']`.

**Action :** pull — GSheet contient des lignes avec cet alias

**Attendu :**
- Les lignes sont **ignorées au pull** : la présence d'un projet masqué portant cet alias suffit, indépendamment de l'ordre dans `data['projects']`. C'est `hidden_aliases` (set) qui tranche, pas `_find_sp` (qui retournerait le premier projet trouvé).
- `ignored_projects` contient l'alias.
- Pas de crash.

> **Au push (hors scope F4)** : le filtre §5.1 itère par projet — le projet visible homonyme est tout de même pushé. Limitation acceptée : les alias sont supposés uniques en pratique. Si le besoin émerge, raffiner le filtre push pour exclure aussi les visibles partageant un alias masqué.

### F5 — `toggle-gsheet-hidden` sur un projet archivé (dans `data-archives.json`)

**Prérequis :** projet PA présent uniquement dans `data-archives.json`, absent de `data.json`.

**Action :** `POST /api/toggle-gsheet-hidden` `{ "projectId": "pa" }`

**Attendu :** `404 { "error": "Projet introuvable" }` — les projets archivés ne sont pas concernés par ce flag
