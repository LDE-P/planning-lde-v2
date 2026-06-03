# SPEC — Découplage total Dashboard ↔ Google Sheet

> **Statut : RÉALISÉ — 2026-06-03**
> Sous-projet associé : Planning LDE (data.json). Tag de restauration git : `decouplage-gsheet-baseline-2026-06-03`.

## Contexte et décision

La synchronisation entre le Dashboard Planning LDE V2 et la Google Sheet
(`1RY1SCZAW5PPG05Cbpvup5pAe6BWvUhy_UZ4DPwl3Wew`) était devenue instable
(incident de perte de données du 2026-05-28 : pull non capté, push écrasant
les colonnes Type/Commentaire ; boutons désactivés depuis). LDE décide
d'**abandonner définitivement** cette synchronisation.

**Décision actée le 2026-06-03 :** le dashboard devient 100 % autonome sur
`data.json`. Plus aucune action n'est émise vers la GSheet. La Google Sheet
existante poursuit sa vie de façon indépendante — **son contenu ne doit jamais
être modifié par le dashboard**. Aucune connexion réseau vers la GSheet n'est
plus établie.

## Décisions de périmètre (validées par LDE avant implémentation)

1. **Code** : suppression totale (pas de neutralisation). Le code reste
   récupérable via git (tag baseline).
2. **`gsheet_hidden`** : champ retiré des 21 projets de `data.json` (devenu mort).
3. **Fichiers** : secrets OAuth supprimés, specs GSheet archivées.
4. **Gestion projet** : les 2 SP GSheet encore ouverts passés en statut `fail`.

## Modifications réalisées

### Code applicatif — suppression totale GSheet

| Fichier | Nature |
|---------|--------|
| `serve-v2.py` | Retrait de ~1240 lignes : `_load_conf`, `_get_spreadsheet_id`, client gspread/OAuth, tous les `_gs_*`, constructeurs de formules `_f_*`, `_to_float`, `_h_to_j`, `_friday_from_week_offset`, `_find_sp`/`_find_sp_by_id`/`_find_sp_by_name`, `_STATUS_TO_GS`/`_STATUS_FROM_GS`, `_drain_body`, tous les handlers GSheet et leurs routes. `import math` et `CONF_FILE` retirés (devenus inutiles). **Conservés** : `_target_from_qualif`, `_friday_of_isoweek`, `_slugify`, `_unique_id`, écriture atomique, garde anti-wipe, backups, CORS. |
| `api.js` | Retrait des wrappers : `fetchGsheetStatus`, `initGsheet`, `formatGsheet`, `saveGsheetTemplate`, `pushToGsheet`, `pullFromGsheet`, `pullFromTcd`, `writeSpField`, `toggleGsheetHidden`. |
| `ui.js` | Retrait : tracking push/pull (localStorage + `_mark*`/`_needsPushConfirm`), `openPushConfirm`, `showResults`, `setLoading`, bouton 👁 toggle GSheet + handler, écriture GSheet ciblée dans l'édition inline charge/raf, `updateGsheetStatus`, bloc handlers boutons GSheet, affichage `#gsheet-bar`. Libellé bouton ✎ relabellé « Renommer l'alias ». |
| `app.js` | Retrait de l'appel `fetchGsheetStatus()`/`updateGsheetStatus` au boot. |
| `DASHBOARD-V2.html` | Retrait de `#gsheet-bar` + 6 boutons + `#gsheet-status`, CSS `#gsheet-bar`/`.btn-spinner`/keyframe spin/`#gsheet-status`/`.btn-toggle-gsheet`, modale `#modal-results`. Libellés « Alias (GSheet) » → « Alias (nom court) ». |

### Statut `fail` (ajouté au passage — pré-requis de `notes-todo.md`)

| Fichier | Ajout |
|---------|-------|
| `serve-v2.py` | `'fail'` ajouté à `_VALID_STATUSES`. |
| `ui.js` | `fail: 'ÉCHEC'` dans `STATUS_LABELS` ; `'fail'` dans `SP_STATUSES`. |
| `DASHBOARD-V2.html` | Variable CSS `--fail: #f97316` (orange brûlé) ; classe `.status-fail`. |

### Données (`data.json`)

- Champ `gsheet_hidden` retiré des 21 projets.
- SP `push-auto-apres-toggle-gsheet` (todo → **fail**) et `phase-6-cible-date-tcd`
  (spec → **fail**), commentaire « Abandonné — découplage total Dashboard ↔ GSheet ».
- Chemins `file` des 7 docs GSheet catalogués mis à jour vers `archive-gsheet/`.

### Tests

- `tests-e2e-python/planning-lde/test_gsheet.py` et `test_toggle_gsheet_hidden.py`
  supprimés (endpoints retirés).
- Suite restante : **158 passed, 0 échec, 0 skip** (baseline : 168 passed
  + 13 skip + 2 fail, ces 2 fail étant dans `test_gsheet.py`).

### Fichiers annexes

- **Supprimés** : `client_secret.json`, `token.json` (secrets OAuth),
  `serve-v2.conf.json` (plus lue), `debug-check-gsheet-formulas.py`,
  `debug-compare-browser-data.py`.
- **Archivés dans `archive-gsheet/`** : `SPEC-GSHEET-HIDDEN.md`,
  `TESTS-GSHEET-HIDDEN.md`, `mise-en-forme-gsheet.md`,
  `notes-gsheet-gemini-2026-05-28.md`, `SPEC-RAF-OPTION-B.md`,
  `TESTS-RAF-OPTION-B.md`, `SPEC-FIX-ENTETES-SEMAINES-TCD.md`,
  `DEBUG-TESTS-PUSH-PULL.md`, `formules.md`.

## Conservé volontairement

- L'**alias** projet (chip d'affichage du dashboard) et sa modale de renommage.
- Le statut `récurrent` et tout le modèle Projet → SP → Étape.
- La GSheet en ligne (non touchée).

## Hors périmètre

- SP `charge-previsionnelle` et `mise-en-place-operationnelle` : non-GSheet, inchangés.
- CLAUDE.md racine : les mentions GSheet caduques (colonnes de sync, alias GSheet)
  sont signalées à LDE pour décision séparée — non modifiées par cette session.
