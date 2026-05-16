# TESTS — Archivage des projets et sous-projets

> **Statut :** VALIDÉ — prêt pour implémentation
> **Date :** 2026-05-16 (validée Ping-Pong Cowork ↔ Claude Code)
> **Référence :** SPEC-ARCHIVAGE.md

> **Note transversale (sections A à E) :** chaque appel d'API mutant (archive, restore, delete) doit produire une entrée dans `history.jsonl` via `_log()`. La vérification de la trace `_log()` fait partie du critère d'acceptation de chaque test des sections A à E, même quand elle n'est pas explicitement répétée dans chaque cas (seul A1 la cite à titre d'exemple).
>
> **Libellés d'erreur canoniques** (alignés sur les handlers existants `_handle_remove_subproject` / `_handle_remove_project`) :
> - `400` → `"projectId et subprojectId requis"` (endpoints à 2 IDs : archive-subproject, restore-subproject, delete-archive-subproject)
> - `400` → `"projectId requis"` (endpoints à 1 ID : archive-project, restore-project, delete-archive-project)
> - `404` → `"Projet introuvable"` / `"Sous-projet introuvable"`
> - `409` → `"Conflit : un projet avec cet id existe déjà dans data.json"`

---

## Section A — Archivage d'un sous-projet

### A1 — Archivage nominal d'un SP (projet non vide)

**Prérequis :** Projet P1 avec SP S1, S2 dans `data.json`. `data-archives.json` absent ou vide.

**Action :** `POST /api/archive-subproject` `{ projectId: P1.id, subprojectId: S1.id }`

**Attendu :**
- Réponse `{ "ok": true, "projectEmpty": false }`
- `data.json` : P1 contient uniquement S2 ; S1 absent
- `data-archives.json` : contient P1 (métadonnées copiées) avec S1 dans `subprojects`
- `history.jsonl` : entrée `{ "action": "archive-subproject", "project": P1.id, "subproject": S1.id }`

### A2 — Archivage du dernier SP d'un projet

**Prérequis :** Projet P1 avec un seul SP S1 dans `data.json`.

**Action :** `POST /api/archive-subproject` `{ projectId: P1.id, subprojectId: S1.id }`

**Attendu :**
- Réponse `{ "ok": true, "projectEmpty": true }`
- `data.json` : P1 existe avec `subprojects: []`
- `data-archives.json` : contient P1 avec S1
- P1 n'est **pas** automatiquement archivé (c'est l'UI qui propose la seconde confirmation)

### A3 — Archivage d'un SP avec accumulation dans le projet archivé existant

**Prérequis :** `data-archives.json` contient déjà P1 avec S1. `data.json` contient P1 avec S2.

**Action :** `POST /api/archive-subproject` `{ projectId: P1.id, subprojectId: S2.id }`

**Attendu :**
- `data-archives.json` : P1 contient S1 **et** S2
- `data.json` : P1 existe avec `subprojects: []`
- Réponse `{ "ok": true, "projectEmpty": true }`

### A4 — projectId manquant

**Action :** `POST /api/archive-subproject` `{ subprojectId: "..." }`

**Attendu :** `400 { "error": "projectId et subprojectId requis" }` (libellé repris de `_handle_remove_subproject` qui contrôle les deux IDs ensemble)

### A5 — SP inexistant dans `data.json`

**Action :** `POST /api/archive-subproject` `{ projectId: P1.id, subprojectId: "fantome" }`

**Attendu :** `404 { "error": "Sous-projet introuvable" }`

### A6 — Projet inexistant dans `data.json`

**Action :** `POST /api/archive-subproject` `{ projectId: "fantome", subprojectId: "..." }`

**Attendu :** `404 { "error": "Projet introuvable" }`

---

## Section B — Archivage d'un projet

### B1 — Archivage nominal d'un projet non vide

**Prérequis :** Projet P1 avec S1, S2 dans `data.json`. `data-archives.json` absent.

**Action :** `POST /api/archive-project` `{ projectId: P1.id }`

**Attendu :**
- Réponse `{ "ok": true }`
- `data.json` : P1 absent
- `data-archives.json` : contient P1 avec S1 et S2

### B2 — Archivage d'un projet vide (suite à archivage du dernier SP)

**Prérequis :** P1 dans `data.json` avec `subprojects: []`. `data-archives.json` contient P1 avec S1.

**Action :** `POST /api/archive-project` `{ projectId: P1.id }`

**Attendu :**
- `data.json` : P1 absent
- `data-archives.json` : P1 existe avec S1 (les SP déjà archivés sont préservés, fusion)

### B3 — Archivage projet avec fusion (SP partiellement déjà archivés)

**Prérequis :** `data-archives.json` contient P1 avec S1. `data.json` contient P1 avec S2, S3.

**Action :** `POST /api/archive-project` `{ projectId: P1.id }`

**Attendu :**
- `data-archives.json` : P1 avec S1, S2, S3
- `data.json` : P1 absent

### B4 — Projet inexistant

**Action :** `POST /api/archive-project` `{ projectId: "fantome" }`

**Attendu :** `404`

---

## Section C — Restauration d'un sous-projet

### C1 — Restauration SP, projet présent dans `data.json`

**Prérequis :** `data-archives.json` contient P1 avec S1. `data.json` contient P1 avec S2.

**Action :** `POST /api/restore-subproject` `{ projectId: P1.id, subprojectId: S1.id }`

**Attendu :**
- `data.json` : P1 contient S2 **et** S1
- `data-archives.json` : P1 absent (plus de SP → projet retiré proprement)
- Réponse `{ "ok": true }`

### C2 — Restauration SP, projet absent de `data.json`

**Prérequis :** `data-archives.json` contient P1 (avec nom, alias, stack…) avec S1. `data.json` ne contient pas P1.

**Action :** `POST /api/restore-subproject` `{ projectId: P1.id, subprojectId: S1.id }`

**Attendu :**
- `data.json` : P1 créé (avec ses métadonnées — name, alias, desc, stack, category, folder — et `docs: []`) avec S1
- `data-archives.json` : P1 absent
- Réponse `{ "ok": true }`

### C3 — Restauration SP, projet archivé avec plusieurs SP restants

**Prérequis :** `data-archives.json` contient P1 avec S1, S2. `data.json` ne contient pas P1.

**Action :** `POST /api/restore-subproject` `{ projectId: P1.id, subprojectId: S1.id }`

**Attendu :**
- `data.json` : P1 recréé avec S1 uniquement (S2 reste dans les archives)
- `data-archives.json` : P1 avec S2 uniquement
- Réponse `{ "ok": true }`

### C4 — SP introuvable dans les archives

**Action :** `POST /api/restore-subproject` `{ projectId: P1.id, subprojectId: "fantome" }`

**Attendu :** `404`

---

## Section D — Restauration d'un projet

### D1 — Restauration projet en bloc (nominal)

**Prérequis :** `data-archives.json` contient P1 avec S1, S2. `data.json` ne contient pas P1.

**Action :** `POST /api/restore-project` `{ projectId: P1.id }`

**Attendu :**
- `data.json` : P1 avec S1 et S2 (tous les SPs restaurés)
- `data-archives.json` : P1 absent
- Réponse `{ "ok": true }`

### D2 — Conflit ID à la restauration

**Prérequis :** `data-archives.json` contient P1. `data.json` contient déjà un projet avec le même `id`.

**Action :** `POST /api/restore-project` `{ projectId: P1.id }`

**Attendu :** `409 { "error": "Conflit : un projet avec cet id existe déjà dans data.json" }`
- `data.json` : inchangé
- `data-archives.json` : inchangé

### D3 — Projet introuvable dans les archives

**Action :** `POST /api/restore-project` `{ projectId: "fantome" }`

**Attendu :** `404`

---

## Section E — Suppression définitive depuis les archives

### E1 — Suppression SP (projet avec autres SPs)

**Prérequis :** `data-archives.json` contient P1 avec S1, S2.

**Action :** `POST /api/delete-archive-subproject` `{ projectId: P1.id, subprojectId: S1.id }`

**Attendu :**
- `data-archives.json` : P1 avec S2 uniquement

### E2 — Suppression SP (dernier SP du projet archivé)

**Prérequis :** `data-archives.json` contient P1 avec S1 uniquement.

**Action :** `POST /api/delete-archive-subproject` `{ projectId: P1.id, subprojectId: S1.id }`

**Attendu :**
- `data-archives.json` : P1 absent (projet vide nettoyé automatiquement)

### E3 — Suppression projet complet

**Prérequis :** `data-archives.json` contient P1 avec S1, S2.

**Action :** `POST /api/delete-archive-project` `{ projectId: P1.id }`

**Attendu :**
- `data-archives.json` : P1 absent

### E4 — Suppression projet introuvable

**Action :** `POST /api/delete-archive-project` `{ projectId: "fantome" }`

**Attendu :** `404`

---

## Section F — Garantie d'unicité des IDs

### F1 — Création projet avec slug déjà utilisé dans les archives

**Prérequis :** `data-archives.json` contient P1 avec `id: "mon-projet"`. `data.json` ne contient pas de projet avec cet id.

**Action :** `POST /api/add-project` `{ name: "Mon Projet" }`

**Attendu :**
- Le nouveau projet reçoit un id différent (ex : `"mon-projet-2"`) — **pas** `"mon-projet"`

### F2 — Création SP avec slug déjà utilisé dans les archives du même projet

**Prérequis :** `data-archives.json` contient P1 avec SP `id: "feature-auth"`. `data.json` contient P1 sans SP d'id `"feature-auth"`.

**Action :** `POST /api/add-subproject` `{ projectId: P1.id, name: "Feature Auth" }`

**Attendu :**
- Le nouveau SP reçoit un id différent (ex : `"feature-auth-2"`)

---

## Section G — Endpoint `GET /api/archives`

### G1 — Archives vides

**Prérequis :** `data-archives.json` absent ou `{ "projects": [] }`.

**Action :** `GET /api/archives`

**Attendu :** `200 { "projects": [] }`

### G2 — Archives non vides

**Prérequis :** `data-archives.json` contient P1 avec S1.

**Action :** `GET /api/archives`

**Attendu :** `200 { "projects": [{ ...P1, "subprojects": [S1] }] }`

---

## Section H — UI et interactions

### H1 — Bouton Archiver visible au hover sur un SP

**Action :** Survoler un SP dans la vue Projets.

**Attendu :** Le bouton 🗃 apparaît (opacity 1), disparaît quand le curseur quitte la ligne.

### H2 — Bouton Archiver visible sur un projet

**Action :** Vue Projets, header d'un projet.

**Attendu :** Bouton 🗃 visible dans project-actions.

### H3 — Confirmation avant archivage SP

**Action :** Cliquer 🗃 sur un SP.

**Attendu :** Modal de confirmation affiché avec le nom du SP. Cliquer Annuler = aucune modification.

### H4 — Seconde confirmation si dernier SP archivé

**Prérequis :** Projet avec un seul SP.

**Action :** Cliquer 🗃 → confirmer l'archivage du SP.

**Attendu :** Une seconde modal apparaît : "Le projet [nom] n'a plus de sous-projets. L'archiver aussi ?"
- Cliquer OUI → projet archivé, retiré de la vue Projets
- Cliquer NON → projet vide reste dans la vue Projets, avec le message "Aucun sous-projet."

### H5 — Badge Archives mis à jour après archivage

**Action :** Archiver un SP.

**Attendu :** Le badge `(N)` sur l'onglet Archives est incrémenté immédiatement.

### H6 — Vue Archives affiche les projets et SP archivés

**Action :** Cliquer sur l'onglet Archives.

**Attendu :**
- Chargement des archives (si pas encore chargées)
- Affichage des projets archivés en accordéon
- Chaque projet affiche ses SP archivés
- Pas de boutons Renommer, Ajouter SP, Ouvrir dossier, Changer statut
- Présence des boutons Restaurer et 🗑 (suppression définitive)

### H7 — Restauration SP depuis les archives (projet présent dans Projets)

**Action :** Vue Archives → cliquer Restaurer sur un SP → confirmer.

**Attendu :**
- Toast "Sous-projet restauré."
- SP disparaît de la vue Archives
- SP réapparaît dans le projet correspondant en vue Projets
- Badge Archives décrémenté

### H8 — Restauration projet en bloc

**Action :** Vue Archives → cliquer Restaurer sur un projet → confirmer.

**Attendu :**
- Toast "Projet restauré."
- Projet disparaît de la vue Archives
- Projet réapparaît avec tous ses SPs en vue Projets

### H9 — Suppression définitive SP depuis les archives

**Action :** Vue Archives → cliquer 🗑 sur un SP → confirmer.

**Attendu :**
- Toast "Suppression définitive effectuée."
- SP disparu des archives
- Si c'était le dernier SP du projet : le projet disparaît aussi des archives

### H10 — Chargement lazy des archives

**Prérequis :** Premier démarrage du dashboard.

**Attendu :**
- Le badge Archives est initialisé au chargement (fetch silencieux de `/api/archives`)
- La vue Archives n'est chargée en détail qu'au premier clic sur l'onglet

### H11 — Vue Archives masque les éléments de la vue Projets

**Action :** Cliquer sur l'onglet Archives.

**Attendu :** Stats bar, filtres, barre GSheet, bouton "+ Nouveau projet" sont masqués. Seul `#archives-container` est visible.

---

## Section I — Cas limites et robustesse

### I1 — `data-archives.json` absent au démarrage

**Attendu :** Pas d'erreur. `GET /api/archives` retourne `{ "projects": [] }`. Tout fonctionnel.

### I2 — `data-archives.json` corrompu

**Action :** Mettre un JSON invalide dans `data-archives.json`, appeler `GET /api/archives`.

**Attendu :** `500 { "error": "data-archives.json corrompu (JSON invalide)" }`

### I3 — Archivage et restauration successifs du même SP

**Action :** Archiver S1, restaurer S1, archiver S1 à nouveau.

**Attendu :** Chaque opération se déroule sans erreur. L'état final est cohérent (S1 dans les archives).

### I4 — Archivage projet avec docs

**Prérequis :** P1 avec docs D1 dans `data.json`.

**Action :** `POST /api/archive-project` `{ projectId: P1.id }`

**Attendu :** `data-archives.json` contient P1 avec ses docs (D1 inclus). `data.json` : P1 absent.
