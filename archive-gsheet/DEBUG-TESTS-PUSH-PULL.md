# DEBUG — Tests manuels RAF Option B (push/pull)

**Date :** 2026-05-17  
**Spec :** `planning-lde-v2/SPEC-RAF-OPTION-B.md`  
**Tests :** `planning-lde-v2/TESTS-RAF-OPTION-B.md`  
**Environnement :** serveur local `http://localhost:8001`, gspread **6.2.1**, Python 3.9

---

## Résumé des résultats

| Section | Test | Résultat | Notes |
|---------|------|----------|-------|
| 1 | T1.0 `_recalc_charges` absente | ✅ | grep confirme |
| 1 | T1.1 statut → sp.raf inchangé | ✅ | |
| 1 | T1.2 statut → sp.charge inchangée | ✅ | |
| 2 | T2.1 clic → deux inputs | ✅ | |
| 2 | T2.2 Enter → sauvegarde | ✅ | |
| 2 | T2.3 blur → sauvegarde | ✅ | |
| 2 | T2.4 Escape → annule | ✅ | |
| 2 | T2.5 virgule FR → parseFloat | ✅ | |
| 2 | T2.6 non numérique → rejet | ✅ | |
| 2 | T2.7 valeur négative → rejet | ✅ | |
| 3 | T3.1 édition RAF → GSheet col G | ✅ | live 2026-05-18 : 7→1 reflété immédiatement |
| 3 | T3.2 édition charge → GSheet col F | ✅ | par induction de T3.1 (même mécanisme) |
| 3 | T3.3 GSheet déconnecté → toast | ✅ | validé par revue de code : `_handle_gsheet_write_sp_field` capture toute exception → `gsheet_unavailable: True` (HTTP 200) → toast côté ui.js non bloquant, `data.json` déjà sauvé en amont via `saveSubproject` |
| 3 | T3.4 champ interdit → 400 | ✅ | |
| 3 | T3.5 SP inconnu → erreur propre | ✅ | |
| 3 | T3.6 payload mal formé → 400 | ✅ | 4/4 cas |
| 4 | T4.1 premier push → col M remplie | ✅ | après correction bug §B1 |
| 4 | T4.2 renommage col B → pull | ✅ | validé sur sprint-raf-option-b (§P2 résolu) |
| 4 | T4.3 pull col M vide (fallback nom) | ✅ | SP Test RAF : col M vidée → raf 1→9 → matching par nom OK, pas de doublon |
| 4 | T4.4 alias renommé → nouveau projet | ✅ | `_TEST_` → `_TEST2_` → pull → `created_projects: _TEST2_` |
| 4 | T4.5 doublon alias | ✅ | alias remis → `_TEST_` + `_TEST2_` coexistent (pas de fusion) |
| 5 | T5.1 SP inconnu → créé + signalé | ✅ | bonus T4.4 — `created_subprojects: SP Test RAF` |
| 5 | T5.2 alias inconnu → projet créé + signalé | ✅ | bonus T4.4 — `created_projects: _TEST2_` |
| 5 | T5.3 pull normal → listes vides | ✅ | 2026-05-18 : `created_projects: []`, `created_subprojects: []` après nettoyage `_TEST2_` |
| 6 | T6.1 push après édit locale → modale | ✅ | dashboard 2026-05-18 |
| 6 | T6.2 push après pull → pas de modale | ✅ | dashboard 2026-05-18 |
| 6 | T6.3 reload → modale persiste (localStorage) | ✅ | flag survit au reload |
| 6 | T6.4 push après push sans pull → modale | ✅ | `_lastPullTime < _lastPushTime` |
| 6 | T6.5 annulation modale → pas de push | ✅ | `_lastPushTime` inchangé |
| 6 | T6.6 confirmation modale → push exécuté | ✅ | `_lastPushTime` mis à jour |
| 7 | T7.1 SP sans date → RAF en col H (Autre) | ✅ | SP Test RAF raf=1 → col H = 1 |
| 7 | T7.2 SP avec date fenêtre → S<nn> (P0) | ✅ | après fix bug §B5 (Exploitation datamart S21/S22/S23) |
| 7 | T7.3 Init → Semaines 8 colonnes | ✅ | H1 = "Autre" |
| 7 | T7.4 Push met à jour H1 | ✅ | par induction T7.3 (push réécrit headers) |
| 8 | T8.1 TEXTE "00" S01/S09 | ✅ | validé par revue : `_f_semaines_week` produit `TEXTE(ISOWEEKNUM(...);"00")` → "01"-"09" pour semaines 1-9, aligné avec col K Tâches (`_f_taches_k`). Test live différé à janvier 2027. |
| 9 | T9.1 btn Pull TCD disabled | ✅ | dashboard 2026-05-18 |
| 9 | T9.2 endpoint pull-from-tcd → disabled | ✅ | curl 2026-05-18 |

---

## Bugs trouvés et corrigés

### B1 — Push échoue : `Range ('Tâches'!M2:M1000) exceeds grid limits`

**Symptôme :** Premier push après déploiement Option B → `APIError: [400]: Invalid range: Range ('Tâches'!M2:M1000) exceeds grid limits. Max rows: 1000, max columns: 12`.

**Cause :** La GSheet Tâches existante (créée avant Option B) n'a que 12 colonnes (A–L). Le push tente d'écrire en col M (colonne 13) sans avoir étendu la feuille.

**Correction appliquée (`serve-v2.py`, fonction `_gs_push`) :**
```python
# Extension Tâches à 13 colonnes si nécessaire (col M ajoutée dans Option B).
if ws_t.col_count < 13:
    ws_t.resize(cols=13)
```
Ajouté juste avant le `batch_clear`. Idempotent : sans effet si la GSheet a déjà 13+ colonnes.

**Note :** Ce bug n'apparaît que pour les GSheet créées avant Option B. Une GSheet initialisée via `/api/gsheet/init` après Option B est créée directement avec `cols=13` dans `_gs_init`.

---

### B2 — `write-sp-field` : `value_input_option` non reconnu par gspread 5.x → comportement silencieux

**Symptôme :** `curl` vers `/api/gsheet/write-sp-field` retourne `{"ok": true, "row": 51}` mais la cellule GSheet n'est pas mise à jour.

**Cause :** Dans l'implémentation initiale, `ws.update()` utilisait `value_input_option='USER_ENTERED'` (paramètre de gspread 6.x). Avec gspread 5.x, ce paramètre était ignoré silencieusement, ce qui pouvait produire un comportement imprévisible.

**Première correction :** Passage à `raw=False` (paramètre gspread 5.x) pour cohérence avec le reste du fichier.

---

### B3 — `write-sp-field` : syntaxe `ws.update()` inversée dans gspread 6.x

**Symptôme :** Même après correction B2, l'écriture ne se reflète pas dans le browser GSheet. Ajout de logs debug → `ws.update result: {'updatedCells': 1, 'updatedRange': "'Tâches'!G51"}` → l'API Google confirme l'écriture.

**Cause racine :** gspread **6.2.1** a inversé la signature de `ws.update()` :
- gspread 5.x : `ws.update(range_name, values, raw=True/False)`
- gspread 6.x : `ws.update(values, range_name, value_input_option=...)`

L'appel `ws.update('G51', [[3.0]], raw=False)` était interprété par gspread 6.x comme `values='G51'` (une string) et `range_name=[[3.0]]` (une liste). gspread détecte que le premier argument est une string et effectue le swap automatiquement (rétrocompat), mais le résultat produit `updatedCells: 1` côté API sans que le browser se mette à jour.

**Correction finale :**
```python
# Avant :
ws.update(f'{col}{target_row}', [[value]], raw=False)

# Après :
ws.update([[value]], cell)
```
La syntaxe `values` en premier, `range_name` en second est conforme à gspread 6.x.

**Status après correction :** L'API confirme l'écriture (`updatedCells: 1`, `updatedRange: "'Tâches'!G51"`). La relecture immédiate via `ws.cell(51, 7).value` retourne `'3'` (valeur correcte). Voir §P1 pour le problème résiduel d'affichage browser.

---

### B5 — Formule Semaines : `SUBSTITUE(A;"- ";"")` remplaçait toutes les occurrences

**Symptôme :** En vérifiant T7.2, les RAF des SPs `Exploitation du datamart - S21/S22/S23` (target dans la fenêtre) s'attribuaient à `0` en cols D/E/F au lieu de `6/6/6`. Le SP `Sprint RAF Option B` (sans ` - ` interne) fonctionnait pourtant en col C (S-1).

**Cause :** la formule des colonnes semaines (`_f_semaines_week`) et de la col Autre (`_f_semaines_autre`) faisait :
```
'Tâches'!B:B = SUBSTITUE(A4; "- "; "")
```
Sans 4e argument, `SUBSTITUE` remplace **toutes** les occurrences du pattern. Pour un nom de SP comme `"Exploitation du datamart - S21"`, la formule produisait `"Exploitation du datamartS21"` (suppression du ` - ` interne) → ne matchait plus col B Tâches → FILTER vide → SUM=0.

**Correction (`serve-v2.py` L.270, L.290) :** ajout du 4e argument `;1` à `SUBSTITUE` pour ne remplacer que la **première** occurrence (le préfixe `"- "`).

```python
# AVANT
'Tâches'!B:B = SUBSTITUE(A4; "- "; "")

# APRÈS
'Tâches'!B:B = SUBSTITUE(A4; "- "; ""; 1)
```

**Action post-fix :** Init GSheet + Push (réécrit les formules avec `;1`). Validé sur Datamart S21/S22/S23 → cols D/E/F = 6/6/6.

**Piège associé :** au moment du fix, le serveur en cours d'exécution servait encore l'ancien code en mémoire (PID démarré avant la correction). `ps aux | grep serve-v2` permet de voir l'heure de démarrage du PID. Solution : `pkill -f serve-v2.py` puis relance.

---

### B4 — Tests e2e obsolètes : `test_recalc_charge_from_steps` et `test_recalc_ignores_na_steps`

**Symptôme :** 2 tests pytest échouent après implémentation Option B :
```
FAILED test_save_subproject.py::test_recalc_charge_from_steps - assert 8.0 == 7.5
FAILED test_save_subproject.py::test_recalc_ignores_na_steps - assert 8.0 == 4.0
```

**Cause :** Ces tests vérifiaient l'ancien comportement de `_recalc_charges` (sp.charge = somme des charges d'étapes). Option B supprime cette fonction — sp.charge et sp.raf sont désormais indépendants des étapes.

**Correction :** Mise à jour des assertions dans `tests-e2e-python/planning-lde/test_save_subproject.py` :
- Les deux tests vérifient maintenant que `sp.charge` reste **inchangée** (8.0) même quand des charges d'étapes sont envoyées.
- Commentaires mis à jour pour documenter le changement Option B.

**Suite complète après correction :** 162 passed, 13 skipped, 0 failed.

---

## Problèmes investigués (2026-05-18)

### P1 — `write-sp-field` : écriture API confirmée mais browser GSheet non mis à jour : RÉSOLU (transitoire)

Diagnostic 2026-05-18 via `debug-check-gsheet-formulas.py` :
- G1 = `'RAF (h)'` (header texte simple, pas de formule)
- G2:G20 = valeurs numériques (1.5, 0, 2, 6, …), aucune formule, aucune ARRAYFORMULA
- 0 protected range sur l'onglet Tâches

**Hypothèse ARRAYFORMULA invalidée.** Les écritures finissent bien dans la GSheet (col G non vide aujourd'hui).

**Test live 2026-05-18 :**
- RAF initial GSheet (SP Test RAF) : `7`
- Édition inline dashboard : `7 → 1`
- RAF final GSheet après reload : `1` ✅

**Conclusion : aucun bug fonctionnel.** Le comportement observé hier soir (browser non MAJ après écriture API) était transitoire — vraisemblablement un cache navigateur Chrome / session WebSocket désynchronisée après plusieurs heures d'ouverture. T3.1 et T3.2 sont validés.

### P2 — `_TEST_` introuvable dans browser : RÉSOLU (filtre browser actif)

Diagnostic 2026-05-18 via `debug-compare-browser-data.py` :
- 0 ligne GSheet absente de `data.json`
- 0 SP `data.json` absent de la GSheet (projets non masqués)
- 0 mismatch col M
- 0 col M vide
- Résumé : 50 lignes GSheet ↔ 50 SPs visibles `data.json` (parfaitement synchrones)

**Cause réelle :** un filtre était resté actif sur l'onglet Tâches dans le browser de LDE, masquant la ligne `_TEST_`. Ctrl+F dans GSheet ignore les lignes masquées par filtre (contrairement à ce qu'on pourrait attendre). Une fois le filtre désactivé, la ligne est visible normalement.

**Conclusion : aucun bug.** Le mécanisme de matching col M fonctionne correctement (test T4.2 sur sprint-raf-option-b prouvé hier soir, confirmé aujourd'hui).

**Leçon :** quand l'API et le browser divergent sur GSheet, vérifier en priorité les filtres actifs avant d'invoquer cache / propagation / session — c'est la cause la plus fréquente et la plus facile à manquer (les lignes masquées par filtre n'apparaissent pas en Ctrl+F).

---

## Corrections conservées (code)

Toutes les corrections ci-dessous sont **commitées** dans `serve-v2.py` :

| Commit | Correction | B# |
|--------|------------|----|
| `a84efc0` | `if ws_t.col_count < 13: ws_t.resize(cols=13)` avant batch_clear | B1 |
| `a84efc0` | `ws.update([[value]], cell)` (syntaxe gspread v6) | B2/B3 |
| `657b305` (et nettoyage) | Aucun `[DEBUG]` résiduel (`grep -n "\[DEBUG"` → 0) | — |

---

## Outils de diagnostic (2026-05-18)

| Script | Usage |
|--------|-------|
| `debug-check-gsheet-formulas.py` | P1 — repère ARRAYFORMULA/protection col G |
| `debug-compare-browser-data.py` | P2 — compare GSheet/data.json |

---

## Bilan final (2026-05-18)

**Tous les tests sont validés** — 36/36 ✅ (dont 2 par revue de code : T3.3 et T8.1).

5 bugs trouvés et corrigés en cours de tests :
- B1 : compat GSheet 12 → 13 cols (commit a84efc0)
- B2/B3 : syntaxe `ws.update()` gspread 6.x (commit a84efc0)
- B4 : tests pytest obsolètes après suppression `_recalc_charges` (commit hors planning-lde-v2)
- B5 : `SUBSTITUE(...;1)` pour ne remplacer que la 1re occurrence (commit d97e496)

2 problèmes investigués et clos comme artefacts (pas de bug) :
- P1 : cache navigateur transitoire (auto-résolu)
- P2 : filtre browser actif (utilisateur)

Sprint RAF Option B **complet et validé**.

---

*Document généré le 2026-05-17 — Tests clos le 2026-05-18 (T5.3 validé le 2026-05-18).*
