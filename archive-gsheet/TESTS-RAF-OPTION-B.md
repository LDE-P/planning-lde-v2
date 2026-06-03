# TESTS — Sprint RAF Option B

**Projet :** Planning LDE V2  
**Spec associée :** `planning-lde-v2/SPEC-RAF-OPTION-B.md`  
**Statut :** Draft (2026-05-17)

---

## Périmètre

Tests fonctionnels couvrant : suppression de `_recalc_charges`, éditabilité RAF/charge dans le dashboard, automatisme GSheet, matching col M, renommage SP, confirmation push, colonne "Autre" Semaines, diagnostic pull.

---

## 1. Suppression de `_recalc_charges`

### T1.0 — Vérification statique : `_recalc_charges` absente du code

**Action :** `grep -n "_recalc_charges" planning-lde-v2/serve-v2.py`  
**Attendu :** aucune occurrence (ni définition ni appel). Protège contre une ré-introduction silencieuse lors d'un futur merge.

### T1.1 — Changement de statut d'étape ne réinitialise plus sp.raf

**Précondition :** SP avec `sp.raf = 5.0` dans `data.json`.  
**Action :** changer le statut d'une étape via le dashboard.  
**Attendu :** `sp.raf` reste `5.0` dans `data.json` après la sauvegarde.  
**Ancien comportement (bug) :** `sp.raf` repassait à `0.0`.

### T1.2 — Changement de statut d'étape ne réinitialise plus sp.charge

**Précondition :** SP avec `sp.charge = 8.0`.  
**Action :** changer le statut d'une étape.  
**Attendu :** `sp.charge` reste `8.0`.

---

## 2. Éditabilité inline RAF/charge dans le dashboard

### T2.1 — Clic ouvre les deux inputs simultanément

**Action :** cliquer sur la zone charge/raf d'un SP.  
**Attendu :** deux inputs s'affichent (charge et raf), pré-remplis avec les valeurs actuelles.

### T2.2 — Validation par Enter sauvegarde les deux valeurs

**Action :** modifier charge à `4` et raf à `2` → appuyer Enter.  
**Attendu :** `data.json` sp.charge = 4.0, sp.raf = 2.0.

### T2.3 — Validation par blur sauvegarde les deux valeurs

**Action :** modifier les valeurs → cliquer ailleurs.  
**Attendu :** même résultat que T2.2.

### T2.4 — Escape annule sans sauvegarder

**Action :** modifier les valeurs → appuyer Escape.  
**Attendu :** valeurs initiales restaurées, aucun appel à `saveSubproject`.

### T2.5 — Saisie avec virgule FR acceptée

**Action :** saisir `3,5` dans le champ raf.  
**Attendu :** sp.raf = 3.5 (virgule normalisée en point avant parseFloat).

### T2.6 — Saisie non numérique rejetée

**Action :** saisir `abc` dans le champ charge.  
**Attendu :** aucune sauvegarde, input en état d'erreur (rouge ou message).

### T2.7 — Valeur négative rejetée

**Action :** saisir `-1` dans le champ raf (ou charge).  
**Attendu :** aucune sauvegarde, input en état d'erreur. Règle : toute valeur < 0 est invalide.

---

## 3. Automatisme écriture GSheet (write-sp-field)

### T3.1 — Édition RAF dashboard → mise à jour immédiate GSheet col G

**Précondition :** serveur connecté à GSheet.  
**Action :** éditer raf à `3.0` via le dashboard.  
**Attendu :** cellule GSheet Tâches col G du SP = 3.0 (sans push manuel).

### T3.2 — Édition charge dashboard → mise à jour immédiate GSheet col F

**Action :** éditer charge à `7.0` via le dashboard.  
**Attendu :** cellule GSheet Tâches col F du SP = 7.0.

### T3.3 — Automatisme échoue si GSheet déconnecté → toast warning

**Précondition :** GSheet non connecté (token OAuth expiré ou serveur sans gspread).  
**Action :** éditer raf via le dashboard.  
**Attendu :**
- `data.json` sp.raf mis à jour ✓
- Toast warning affiché : « Sauvegarde GSheet échouée — valeur enregistrée en local, pensez à pusher. »
- Pas d'erreur bloquante (le dashboard continue à fonctionner)

### T3.4 — Endpoint /api/gsheet/write-sp-field : champ interdit rejeté

**Action :** POST `{"projectId": "...", "subprojectId": "...", "field": "status", "value": "done"}`.  
**Attendu :** réponse 400 avec message d'erreur.

### T3.5 — Endpoint /api/gsheet/write-sp-field : sp inconnu retourne erreur propre

**Action :** POST avec `subprojectId` inexistant.  
**Attendu :** réponse `{"ok": false, "error": "SP introuvable"}` (pas de 500).

### T3.6 — Endpoint /api/gsheet/write-sp-field : payload mal formé

| Cas | Payload | Attendu |
|-----|---------|---------|
| projectId manquant | `{"subprojectId": "x", "field": "raf", "value": 3}` | 400 |
| value manquant | `{"projectId": "p", "subprojectId": "x", "field": "raf"}` | 400 |
| JSON invalide | body non-JSON | 400 |
| field inconnu | `{"field": "status", ...}` | 400 (field non autorisé) |

---

## 4. Matching col M et renommage SP

### T4.1 — Premier push post-déploiement remplit col M

**Action :** push depuis le dashboard.  
**Attendu :** toutes les lignes de Tâches ont leur col M remplie avec `sp.id` (aucune cellule vide pour les SPs existants).

### T4.2 — Renommage SP dans GSheet col B → propagation au pull

**Précondition :** col M remplie (après un premier push).  
**Action :** modifier col B d'un SP dans Tâches → pull.  
**Attendu :** `data.json` sp.name = nouveau nom. Pas de doublon SP créé.

### T4.3 — Pull avec col M vide (transition avant premier push)

**Précondition :** col M vide pour un SP (GSheet avant premier push).  
**Action :** pull.  
**Attendu :** matching par nom (fallback) — comportement identique à l'ancien code. Aucun doublon.

### T4.4 — Renommage alias projet col A → création nouveau projet (comportement documenté)

**Action :** modifier col A d'un projet dans Tâches → pull.  
**Attendu :** nouveau projet créé à la volée, signalé dans `created_projects` de la réponse. L'ancien projet reste intact dans `data.json`.

### T4.5 — Alias renommé puis remis à l'original → doublon visible, nettoyage manuel

**Précondition :** projet "Foo" dans `data.json`.  
**Action :** renommer col A → "Bar" → pull (crée projet "Bar") → renommer col A → "Foo" → pull.  
**Attendu :** deux projets coexistent dans le dashboard : "Foo" (original) et "Bar" (créé à la volée). Pas de fusion automatique. `created_projects` signale "Foo" au second pull. LDE supprime le doublon manuellement via le dashboard.

---

## 5. Diagnostic pull Tâches

### T5.1 — SP inconnu → créé à la volée et signalé

**Action :** ajouter une ligne dans Tâches avec un alias existant mais un nom SP inexistant → pull.  
**Attendu :** `created_subprojects` contient le nom du SP. Un nouveau SP apparaît dans le dashboard.

### T5.2 — Alias inconnu → projet créé et signalé

**Action :** ajouter une ligne dans Tâches avec un alias inconnu → pull.  
**Attendu :** `created_projects` contient l'alias. Un nouveau projet apparaît dans le dashboard.

### T5.3 — Pull normal sans anomalie → listes vides

**Action :** pull sur une GSheet cohérente avec `data.json`.  
**Attendu :** `created_projects = []`, `created_subprojects = []`.

---

## 6. Confirmation avant push (flags localStorage)

### T6.1 — Push après édition locale → modale affichée

**Action :** modifier le statut d'un SP dans le dashboard → cliquer Push.  
**Attendu :** modale de confirmation affichée.

### T6.2 — Push après pull → pas de modale

**Action :** pull → push (sans édition entre les deux).  
**Attendu :** push s'exécute directement sans modale.

### T6.3 — Persistance après reload : modale toujours affichée

**Action :** modifier un statut → recharger la page → cliquer Push.  
**Attendu :** modale affichée (flag `_localEditSinceLastPull` persisté en localStorage).

### T6.4 — Push après push sans pull intermédiaire → modale affichée

**Action :** push → (sans pull) → push à nouveau.  
**Attendu :** modale affichée car `_lastPullTime < _lastPushTime` (ou `_lastPullTime = null`).

### T6.5 — Annulation modale → push non exécuté

**Action :** déclencher la modale → cliquer Annuler.  
**Attendu :** aucun push, dashboard inchangé.

### T6.6 — Confirmation modale → push exécuté, _lastPushTime mis à jour

**Action :** déclencher la modale → cliquer Continuer.  
**Attendu :** push exécuté, `localStorage.getItem('planning_lastPushTime')` mis à jour.

---

## 7. Colonne "Autre" dans Semaines

### T7.1 — SP sans date cible → RAF visible dans col H (Autre)

**Précondition :** SP avec col E (Tâches) vide et RAF = 5h.  
**Action :** vérifier l'onglet Semaines.  
**Attendu :** col H de la ligne du SP affiche `5` (ou formule calculée = 5).

### T7.2 — SP avec date cible dans la fenêtre → RAF dans la colonne de semaine courante, pas dans H (Autre)

**Précondition :** SP avec date cible = vendredi de la semaine courante, RAF = 3h.  
**Attendu :** la colonne dont le header est `S<nn> (P0)` (semaine courante) affiche 3 ; col H (header "Autre") est vide ou 0.  
*(Référencer par header plutôt que par lettre — l'ordre des colonnes peut changer.)*

### T7.3 — Init GSheet crée Semaines avec 8 colonnes

**Action :** lancer `/api/gsheet/init`.  
**Attendu :** onglet Semaines a bien 8 colonnes, header H1 = "Autre".

### T7.4 — Push met à jour le header H1 de Semaines

**Action :** push depuis le dashboard.  
**Attendu :** Semaines H1 = "Autre" (header rafraîchi).

---

## 8. Formule Semaines — correction TEXTE "00"

### T8.1 — RAF d'un SP avec date cible en semaine < 10 apparaît dans la bonne colonne

**Précondition :** SP avec date cible = vendredi S01 (borne basse) ou S09 (borne haute avant à deux chiffres).  
**Action :** vérifier Semaines lors d'une semaine où S01 ou S09 est dans la fenêtre ±1.  
**Attendu :** RAF dans la colonne dont le header affiche S01 ou S09 (format TEXTE "00" correct — "S01" ≠ "S1"). Pas dans "Autre".

---

## 9. Pull TCD désactivé

### T9.1 — Bouton Pull TCD inactif

**Attendu :** `btn-pull-tcd` est `disabled` au chargement du dashboard. Pas de clic possible via souris.

### T9.2 — Endpoint /api/pull-from-tcd retourne disabled

**Action :** POST `/api/pull-from-tcd`.  
**Attendu :** `{"ok": false, "disabled": true, "message": "Pull TCD désactivé — refonte prévue (sprint suivant)."}`.

---

## Matrice de couverture scénarios

| Scénario | Tests couvrants |
|----------|----------------|
| push → GSheet edit → pull → push : données préservées | T3.1, T4.1 |
| push → GSheet edit → push → pull : données perdues (⚠️ modale) | T6.4 |
| Dashboard edit RAF → push : GSheet mis à jour | T3.1, T3.2 |
| Dashboard edit RAF → pull : idempotent (automatisme déjà sync) | T3.1 + T4.1 |
| Dashboard edit (autres champs) → pull : données écrasées (⚠️ modale) | T6.1, T6.3 |
| write-sp-field GSheet indisponible | T3.3 |
| Renommage SP via GSheet | T4.2 |
| Transition col M vide | T4.3 |
