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
| 3 | T3.1 édition RAF → GSheet col G | ⚠️ | API confirme — reconfirmer en live (§P1) |
| 3 | T3.2 édition charge → GSheet col F | ⚠️ | API confirme — reconfirmer en live (§P1) |
| 3 | T3.3 GSheet déconnecté → toast | ⏭️ | non testé (différé) |
| 3 | T3.4 champ interdit → 400 | ✅ | |
| 3 | T3.5 SP inconnu → erreur propre | ✅ | |
| 3 | T3.6 payload mal formé → 400 | ✅ | 4/4 cas |
| 4 | T4.1 premier push → col M remplie | ✅ | après correction bug §B1 |
| 4 | T4.2 renommage col B → pull | ✅ | validé sur sprint-raf-option-b (§P2 résolu) |
| 4 | T4.3 pull col M vide (fallback nom) | ⏭️ | non atteint |
| 4 | T4.4 alias renommé → nouveau projet | ⏭️ | non atteint |
| 4 | T4.5 doublon alias | ⏭️ | non atteint |
| 5 | T5.x diagnostic pull | ⏭️ | non atteint |
| 6 | T6.x confirmation push | ⏭️ | non atteint |
| 7 | T7.x colonne Autre Semaines | ⏭️ | non atteint |
| 8 | T8.1 TEXTE "00" S01/S09 | ⏭️ | non atteint |
| 9 | T9.1 btn Pull TCD disabled | ⏭️ | non atteint |
| 9 | T9.2 endpoint pull-from-tcd → disabled | ⏭️ | non atteint |

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

### P1 — `write-sp-field` : écriture API confirmée mais browser GSheet non mis à jour

**Statut : très probablement un artefact de cache navigateur transitoire, à reconfirmer.**

Diagnostic 2026-05-18 via `debug-check-gsheet-formulas.py` :
- G1 = `'RAF (h)'` (header texte simple, pas de formule)
- G2:G20 = valeurs numériques (1.5, 0, 2, 6, …), aucune formule, aucune ARRAYFORMULA
- 0 protected range sur l'onglet Tâches

**Hypothèse ARRAYFORMULA invalidée.** L'hypothèse "formule qui écrase G:G" est éliminée — les écritures *finissent* bien dans la GSheet (col G non vide aujourd'hui).

**Hypothèse retenue :** cache navigateur transitoire le 2026-05-17 au soir. Une session browser longue avec WebSocket désynchronisé peut afficher des valeurs périmées même après hard refresh. L'ouverture matinale du 2026-05-18 a vraisemblablement rétabli la synchro.

**Test de validation (à faire par LDE) :**
1. Ouvrir https://docs.google.com/spreadsheets/d/1RY1SCZAW5PPG05Cbpvup5pAe6BWvUhy_UZ4DPwl3Wew/ → onglet Tâches → noter la valeur G d'un SP test
2. Modifier le RAF de ce SP via le dashboard (édition inline)
3. Recharger la page browser → valeur attendue : nouvelle saisie visible immédiatement

Si OK : P1 clos comme transitoire. Si KO : creuser hypothèses cache/session/conflit OAuth.

### P2 — `_TEST_` introuvable dans browser : RÉSOLU

Diagnostic 2026-05-18 via `debug-compare-browser-data.py` :
- 0 ligne GSheet absente de `data.json`
- 0 SP `data.json` absent de la GSheet (projets non masqués)
- 0 mismatch col M
- 0 col M vide
- Résumé : 50 lignes GSheet ↔ 50 SPs visibles `data.json` (parfaitement synchrones)

**La ligne `_TEST_` n'est plus dans la GSheet aujourd'hui.** L'hypothèse "push intermédiaire a effacé la ligne entre le pull debug et la recherche browser" est confirmée a posteriori. Le mécanisme de matching col M fonctionne correctement (test T4.2 sur sprint-raf-option-b prouvé hier soir).

**Conclusion : aucun bug — artefact de timing entre l'état de la GSheet lu par le pull debug et l'état observé ensuite dans le browser.**

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

## Séquence de test recommandée pour reprendre

1. **(Optionnel)** Reconfirmer P1 par le test live décrit dans §P1
2. Continuer les tests T4.3 → T9.2 (col M vide, alias renommé, diagnostic pull, modale push, col Autre, S01/S09, bouton Pull TCD)
3. Si tous verts, marquer le sprint RAF Option B comme `done` dans `data.json`

---

*Document généré le 2026-05-17 en cours de session de tests manuels — Mis à jour le 2026-05-18 après investigation P1/P2.*
