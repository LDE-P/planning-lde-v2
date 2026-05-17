# SPEC — Sprint RAF Option B

**Projet :** Planning LDE V2  
**Fichier :** `planning-lde-v2/SPEC-RAF-OPTION-B.md`  
**Statut :** Validé (Ping-Pong Cowork ↔ Claude Code, 2026-05-17)  
**Prompt de démarrage :**
> Implémente la spec `planning-lde-v2/SPEC-RAF-OPTION-B.md`. Commence par lire ce fichier et le `CLAUDE.md` du projet. Lis les fonctions existantes avant d'en modifier — applique le même squelette.

---

## Contexte

Le RAF (Reste À Faire) au niveau sous-projet (`sp.raf`) n'est actuellement ni gérable dans le dashboard (pas de champ éditable) ni correctement gérable via la GSheet (la saisie est effacée dès qu'une étape change de statut, par `_recalc_charges`).

**Option B retenue :** `sp.raf` et `sp.charge` sont des données portées **au niveau SP**, indépendantes des étapes. `_recalc_charges` est supprimé.

---

## Fichiers modifiés

| Fichier | Nature |
|---------|--------|
| `planning-lde-v2/serve-v2.py` | 12 modifications §1–§12 (détaillées ci-dessous, ordre d'implémentation recommandé) |
| `planning-lde-v2/ui.js` | 6 modifications |
| `planning-lde-v2/api.js` | 1 ajout |

**Fichiers non modifiés :** `app.js`, `data.json`, `DASHBOARD-V2.html`

---

## serve-v2.py — Modifications

### 1. Suppression de `_recalc_charges`

Supprimer la fonction `_recalc_charges` (actuellement L.979–983) et son unique appel dans `_handle_save_subproject` (actuellement L.1259).

```python
# AVANT (à supprimer) :
def _recalc_charges(sp: dict):
    active = [s for s in sp.get('steps', []) if s.get('status') != 'na']
    sp['charge'] = sum(s.get('charge', 0.0) for s in active)
    sp['raf'] = sum(s.get('raf', 0.0) for s in active)

# Et dans _handle_save_subproject, supprimer :
_recalc_charges(sp)
```

`sp.charge` et `sp.raf` ne sont plus jamais recalculés automatiquement. Ils ne sont mis à jour que par : saisie directe dans le dashboard, ou pull GSheet.

---

### 2. Correction de `_f_semaines_week` — format TEXTE "00"

**Problème actuel :** la formule compare `'Tâches'!K:K` avec `"S"&ISOWEEKNUM()-1` (sans TEXTE, sans padding). Col K produit `"S"&TEXTE(xx;"00")`. Mismatch pour les semaines 1–9.

**Correction :** utiliser des décalages en jours (±7j) + TEXTE "00", comme les headers (conforme à `formules.md §TCD/C1–G1`).

```python
def _f_semaines_week(row: int, offset: int) -> str:
    """Colonne semaine Semaines ligne row — RAF semaine (formules.md §TCD/C4-G4)."""
    day_offset = offset * 7
    if day_offset == 0:
        wk = 'TEXTE(ISOWEEKNUM(AUJOURDHUI());"00")'
    elif day_offset < 0:
        wk = f'TEXTE(ISOWEEKNUM(AUJOURDHUI(){day_offset});"00")'
    else:
        wk = f'TEXTE(ISOWEEKNUM(AUJOURDHUI()+{day_offset});"00")'
    r = str(row)
    return (
        '=SI(REGEXMATCH(A' + r + ';"^- ");'
        'SIERREUR(SOMME(FILTER(\'Tâches\'!G:G;'
        '\'Tâches\'!B:B=SUBSTITUE(A' + r + ';"- ";"");'
        '\'Tâches\'!K:K="S"&' + wk + '));"");"")'
    )
```

---

### 3. Nouvelle fonction `_f_semaines_autre(row)`

Colonne H de Semaines — RAF des SPs sans date cible (col K de Tâches = `""`).

```python
def _f_semaines_autre(row: int) -> str:
    """Colonne H Semaines ligne row — RAF des SPs sans date cible."""
    r = str(row)
    return (
        '=SI(REGEXMATCH(A' + r + ';"^- ");'
        'SIERREUR(SOMME(FILTER(\'Tâches\'!G:G;'
        '\'Tâches\'!B:B=SUBSTITUE(A' + r + ';"- ";"");'
        '\'Tâches\'!K:K=""));"");"")'
    )
```

---

### 4. Nouvelle fonction `_semaines_headers()`

`_tcd_headers()` reste à 7 colonnes (A–G, inchangé — le TCD n'est pas retouché dans ce sprint).  
Nouvelle fonction `_semaines_headers()` = `_tcd_headers()` + colonne "Autre" → 8 éléments.

```python
def _semaines_headers() -> list:
    """Headers A1:H1 pour l'onglet Semaines — 8 colonnes (A–G comme TCD + H=Autre)."""
    return _tcd_headers() + ['Autre']
```

---

### 5. Mise à jour des formules `_f_semaines_b*` et `_f_semaines_b_row`

Étendre de G à H pour inclure la colonne "Autre".

```python
def _f_semaines_b2() -> str:
    return '=SUM(ARRAYFORMULA(VALUE(SUBSTITUTE(C2:H2;" h.";""))))&" h."'

def _f_semaines_b3() -> str:
    return '=SUM(ARRAYFORMULA(VALUE(SUBSTITUTE(C3:H3;" j.";""))))&" j."'

def _f_semaines_b_row(row: int) -> str:
    return f'=IF(AND(A{row}<>"";LEFT(A{row};2)="- ");SUM(C{row}:H{row});"")'
```

---

### 6. Mise à jour de `_gs_init` — Semaines passe à 8 colonnes

Dans `_gs_init`, section `# ── Onglet Semaines ──` :

- `sh.add_worksheet(title='Semaines', rows=200, cols=7)` → `cols=8`
- `ws_s.update('A1:G1', [_tcd_headers()], ...)` → `ws_s.update('A1:H1', [_semaines_headers()], ...)`
- `row2` : ajouter `_f_semaines_col2('H')` en fin de liste
- `row3` : ajouter `_f_semaines_col3('H')` en fin de liste
- `ws_s.update('A2:G2', [row2], ...)` → `ws_s.update('A2:H2', [row2], ...)`
- `ws_s.update('A3:G3', [row3], ...)` → `ws_s.update('A3:H3', [row3], ...)`
- Dans la boucle `formulas_bg`, ajouter `_f_semaines_autre(r)` comme 7e élément (après `_f_semaines_week(r, 3)`)
- `ws_s.update(f'B4:G{_SEMAINES_MAX_ROWS}', ...)` → `ws_s.update(f'B4:H{_SEMAINES_MAX_ROWS}', ...)`

---

### 7. Mise à jour de `_gs_push` — headers Semaines

```python
# AVANT :
ws_s.update('A1:G1', [dyn_headers], raw=False)

# APRÈS :
ws_s.update('A1:H1', [_semaines_headers()], raw=False)
```

Le TCD reste : `ws_tcd.update('A1:G1', [_tcd_headers()], raw=False)` — inchangé.

> **Note :** le push ne réécrit pas les formules des lignes 4–100 de Semaines (elles sont écrites une fois à l'init et s'auto-actualisent via REGEXMATCH/SUBSTITUTE sur col A). Seuls les headers sont mis à jour au push. Les formules couvrent jusqu'à `_SEMAINES_MAX_ROWS` (actuellement 100) lignes — si le nombre total de projets + SPs dépasse 100, les nouvelles lignes ne seront pas couvertes. À relancer via init si nécessaire.

---

### 8. Désactivation des endpoints pull TCD

Dans le handler HTTP, les deux endpoints retournent immédiatement sans appeler `_gs_pull_tcd` :

```python
# /api/pull-from-tcd et /api/pull-from-tcd/preview
self._json_response({
    'ok': False,
    'disabled': True,
    'message': 'Pull TCD désactivé — refonte prévue (sprint suivant).'
})
```

Les fonctions `_gs_pull_tcd` et `_gs_pull_tcd_preview` sont conservées dans le code (commentées ou laissées en place) pour le sprint suivant.

---

### 9. Nouveau helper `_find_sp_by_id`

Pour l'endpoint `/api/gsheet/write-sp-field` (§11), ajouter un helper distinct de `_find_sp` :

```python
def _find_sp_by_id(data: dict, project_id: str, sp_id: str):
    """Retourne (proj, sp) en cherchant par project.id + sp.id.
    Retourne (None, None) si introuvable."""
    for proj in data.get('projects', []):
        if proj.get('id') == project_id:
            for sp in proj.get('subprojects', []):
                if sp.get('id') == sp_id:
                    return proj, sp
            return proj, None
    return None, None
```

---

### 10. Colonne M (sp.id) dans Tâches — clé stable pour le pull

Objectif : permettre le renommage d'un SP dans GSheet col B et le répercuter dans `data.json`.

> **Renommage d'alias projet (col A) :** hors scope du matching par col M. Si col A change dans GSheet, `_find_sp` ne trouve pas le projet → création d'un nouveau projet à la volée, signalé dans `created_projects`. C'est le comportement actuel, volontairement conservé.

**`_TACHES_HEADERS`** : ajouter `'ID'` en 13e position.

```python
_TACHES_HEADERS = [
    'Projet', 'Sous-projet', 'Type', 'Prio.', 'Cible',
    'Charge (h)', 'RAF (h)', 'Titre', 'Avanc.', 'Commentaire',
    'Semaine', 'Année', 'ID',
]
```

**`_gs_build_taches_rows`** : ajouter `sp['id']` comme 13e élément (col M).

```python
rows.append([
    alias,           # A
    sp['name'],      # B
    sp.get('type', ''),          # C
    sp.get('qualif', ''),        # D
    sp.get('target', ''),        # E
    sp.get('charge', 0.0),       # F
    sp.get('raf', 0.0),          # G
    sp.get('titre', ''),         # H
    _STATUS_TO_GS.get(sp.get('status', 'todo'), 'À FAIRE'),  # I
    sp.get('commentaire', ''),   # J
    _f_taches_k(row_num),        # K
    _f_taches_l(row_num),        # L
    sp['id'],                    # M — clé stable
])
```

**`_gs_push`** : étendre le `batch_update` pour écrire col M.

```python
# Ajouter dans la liste batch_update :
{'range': f'M2:M{last}', 'values': [[r[12]] for r in rows]},
```

**`_gs_pull_taches`** : modifier la logique de matching.

```python
# Lire col M (sp.id stable)
sp_id_from_sheet = row[12].strip() if len(row) > 12 else ''

# Matching : priorité à l'id (col M), fallback sur le nom (col B)
if sp_id_from_sheet:
    # Recherche par id dans le projet trouvé via alias
    sp = next((s for s in proj.get('subprojects', []) if s.get('id') == sp_id_from_sheet), None)
    if sp and row[1].strip() and row[1].strip() != sp['name']:
        sp['name'] = row[1].strip()  # renommage propagé
else:
    # Fallback : comportement actuel (matching par nom)
    _, sp = _find_sp(data, alias, row[1].strip())
```

Transition : les lignes GSheet sans col M (avant le premier push post-déploiement) utilisent automatiquement le fallback nom — aucune migration manuelle requise.

---

### 11. Nouvel endpoint `/api/gsheet/write-sp-field`

> **Règle 4 CLAUDE.md :** lire un handler POST existant avant d'écrire celui-ci. Appliquer dans le même ordre : CORS/preflight OPTIONS, validation payload (400 si champ manquant), limite taille (`_check_payload_size` ou constante `MAX_PAYLOAD`), sanitisation, logique métier, réponse JSON.

Écriture ciblée d'un champ SP directement dans la GSheet (sans push global). Utilisé par l'automatisme dashboard pour RAF et charge.

**Payload JSON :**
```json
{ "projectId": "...", "subprojectId": "...", "field": "raf|charge", "value": 3.5 }
```

**Comportement :**
1. Valider `field` ∈ `{'raf', 'charge'}` — refuser tout autre champ (400)
2. Charger `data.json`, trouver le SP par `projectId` + `subprojectId`
3. Identifier la ligne GSheet du SP : lire Tâches col M pour trouver la ligne correspondant à `sp.id` ; fallback : chercher par alias (col A) + nom (col B)
4. Écrire la valeur dans la cellule : col F pour `charge`, col G pour `raf`
5. Retourner `{'ok': True, 'row': N}` ou `{'ok': False, 'error': '...'}` si GSheet non connecté ou SP introuvable

**Erreurs :** si GSheet non connecté → `{'ok': False, 'gsheet_unavailable': True}` (le dashboard affiche un toast d'avertissement, mais la sauvegarde data.json a déjà eu lieu en amont via `/api/save-subproject`).

---

### 12. Diagnostic dans `_gs_pull_taches`

La réponse ajoute deux listes pour exposer les mismatches :

```python
return {
    'ok': True,
    'updated': updated,
    'ignored_projects': ignored,
    'created_projects': created_projects,    # alias créés à la volée
    'created_subprojects': created_subprojects,  # noms SP créés à la volée
}
```

Alimenter `created_projects` quand `proj is None` (nouveau projet créé), `created_subprojects` quand `sp is None` (nouveau SP créé).

---

## ui.js — Modifications

### 1. sp.charge et sp.raf éditables inline avec automatisme GSheet

**Comportement actuel :** `charges.innerHTML = \`${charge}h / <span class="raf">${raf}h</span>\`` (affichage seul).

**Comportement cible :** clic sur la zone charge/raf → remplace par deux inputs inline (charge | raf) → Enter ou blur → séquence suivante :

```
1. saveSubproject({ projectId, subprojectId: sp.id, charge: newCharge, raf: newRaf })
   → met à jour data.json (toujours, même si GSheet indisponible)
2. writeSpField({ projectId, subprojectId, field: 'charge', value: newCharge })
   writeSpField({ projectId, subprojectId, field: 'raf', value: newRaf })
   → écriture ciblée dans GSheet col F et col G
   → si réponse { gsheet_unavailable: true } : toast("Sauvegarde GSheet échouée — valeur enregistrée en local, pensez à pusher.", 'warning')
3. fetchStateAndRefresh()
```

Modèle à suivre : même pattern que l'édition inline de la date cible (input temporaire, validation blur/Enter, annulation Escape).

Les valeurs sont des flottants — normaliser la virgule FR avant parsing : `parseFloat(str.replace(',', '.'))`, rejeter si `NaN`.

L'étape 2 (écriture GSheet) est **non bloquante** : une erreur n'empêche pas la sauvegarde locale ni le refresh du dashboard.

### 2. Tracking push/pull — flag et timestamps (persistés localStorage)

Déclarer en module-level dans `ui.js`, persistés dans `localStorage` pour survivre aux reloads :

```javascript
// Clés localStorage
const LS_LAST_PULL   = 'planning_lastPullTime';
const LS_LAST_PUSH   = 'planning_lastPushTime';
const LS_LOCAL_EDIT  = 'planning_localEditSinceLastPull';

// Lecture initiale (null si absent)
let _lastPullTime  = localStorage.getItem(LS_LAST_PULL)  ? new Date(localStorage.getItem(LS_LAST_PULL))  : null;
let _lastPushTime  = localStorage.getItem(LS_LAST_PUSH)  ? new Date(localStorage.getItem(LS_LAST_PUSH))  : null;
let _localEditSinceLastPull = localStorage.getItem(LS_LOCAL_EDIT) === 'true';
```

Helpers de mise à jour (toujours passer par ces helpers, jamais écrire directement les variables) :

```javascript
function _markPull()      { _lastPullTime = new Date(); localStorage.setItem(LS_LAST_PULL, _lastPullTime.toISOString()); _localEditSinceLastPull = false; localStorage.setItem(LS_LOCAL_EDIT, 'false'); }
function _markPush()      { _lastPushTime = new Date(); localStorage.setItem(LS_LAST_PUSH, _lastPushTime.toISOString()); }
function _markLocalEdit() { _localEditSinceLastPull = true; localStorage.setItem(LS_LOCAL_EDIT, 'true'); }
```

- **Après pull réussi :** `_markPull()`
- **Après push réussi :** `_markPush()`
- **Après toute édition locale** (status, target, titre, qualif, owner, renommage — **pas** RAF/charge qui sont écrits directement en GSheet) : `_markLocalEdit()`

### 3. Confirmation avant push

Avant d'exécuter le push, vérifier :

```javascript
const needsConfirm = _localEditSinceLastPull ||
    (_lastPushTime !== null && (_lastPullTime === null || _lastPullTime < _lastPushTime));
```

Si `needsConfirm` → afficher une modale de confirmation :

> *« Attention : vous n'avez pas fait de pull depuis votre dernier push ou depuis vos dernières modifications locales. Des données saisies dans la GSheet pourraient être écrasées. Continuer le push ? »*

Boutons : **Continuer** (exécute le push) / **Annuler** (retour sans push).

Si l'utilisateur confirme → push normal, puis `_lastPushTime = new Date()`.

### 4. Bouton Pull TCD désactivé

```javascript
// Ajouter disabled + title sur le bouton btn-pull-tcd au chargement :
document.getElementById('btn-pull-tcd').disabled = true;
document.getElementById('btn-pull-tcd').title = 'Désactivé — refonte en cours (sprint suivant)';
```

Si le handler click est toujours déclenché (ex. via clavier), afficher le message retourné par le serveur via `toast(r.message, 'info')`.

### 5. Diagnostic pull Tâches dans showResults

Après le pull Tâches, si `r.created_projects` ou `r.created_subprojects` sont non vides, les afficher dans `showResults` :

```javascript
if (r.created_projects?.length) {
    lines.push('');
    lines.push(`⚠ ${r.created_projects.length} projet(s) créé(s) à la volée (alias inconnu) :`);
    r.created_projects.forEach(a => lines.push(`  • ${a}`));
}
if (r.created_subprojects?.length) {
    lines.push('');
    lines.push(`⚠ ${r.created_subprojects.length} SP créé(s) à la volée (nom inconnu) :`);
    r.created_subprojects.forEach(n => lines.push(`  • ${n}`));
}
```

---

## api.js — Modification

### 1. Nouvelle fonction `writeSpField`

```javascript
export async function writeSpField(payload) {
  return _post('/api/gsheet/write-sp-field', payload);
}
```

À importer dans `ui.js` au même titre que `saveSubproject`.

---

## Scénarios couverts

| Scénario | Comportement | Couverture |
|----------|-------------|------------|
| push → GSheet edit → pull → push | Données GSheet préservées | ✅ natif |
| push → GSheet edit → push → pull | Données GSheet écrasées | ⚠️ confirmation si `needsConfirm` |
| dashboard edit RAF/charge → push | GSheet mis à jour (automatisme) | ✅ automatisme write-sp-field |
| dashboard edit RAF/charge → pull | GSheet déjà à jour → pull idempotent | ✅ automatisme |
| dashboard edit (autres champs) → pull | Données dashboard écrasées si GSheet différent | ⚠️ confirmation si `needsConfirm` |
| write-sp-field échoue (GSheet indisponible) | data.json mis à jour, toast warning | ✅ gestion erreur |

---

## Hors scope de ce sprint

- Refonte du pull TCD (sprint dédié)
- `_build_tcd_rows` : inchangé (TCD reste 7 colonnes côté push)
- `formules.md` : pas mis à jour (les formules GSheet sont dans `serve-v2.py`)
- Étapes (`sp.steps`) : `step.charge` et `step.raf` restent éditables depuis le dashboard, mais ne remontent plus vers `sp.charge` / `sp.raf`

---

## Action post-déploiement (LDE)

Après le commit et le redémarrage du serveur :

1. **Initialiser GSheet** (bouton Init dans le dashboard) — obligatoire pour que Semaines passe à 8 colonnes et que les nouvelles formules (TEXTE "00" + Autre) soient écrites.
2. **Push** — remplit col M (sp.id) pour tous les SPs existants.
3. Vérifier que col M est bien remplie pour tous les SPs dans l'onglet Tâches (pas de cellule vide en M pour les lignes existantes).
4. Vérifier que la colonne "Autre" apparaît bien dans Semaines (col H).
5. **Test RAF depuis GSheet :** saisir une valeur dans Tâches col G pour un SP existant → pull → vérifier la valeur dans le dashboard.
6. **Test RAF depuis dashboard :** éditer RAF inline dans le dashboard → vérifier que la cellule GSheet col G se met à jour immédiatement (sans push).
7. **Test renommage SP :** renommer un SP dans Tâches col B → pull → vérifier que le nom est mis à jour dans le dashboard (pas de doublon).
8. **Test confirmation push :** éditer un statut dans le dashboard → tenter un push → vérifier que la modale de confirmation s'affiche. Recharger la page → re-tenter un push → vérifier que la modale s'affiche toujours (localStorage persistant).

## How to Rollback

En cas de problème après déploiement :

1. `git revert <commit>` ou `git checkout HEAD~1 -- planning-lde-v2/serve-v2.py planning-lde-v2/ui.js`
2. Redémarrer `serve-v2.py`
3. Relancer `/api/gsheet/init` pour revenir à Semaines 7 colonnes (sinon la colonne H "Autre" reste dans GSheet mais est ignorée — sans impact fonctionnel)
4. Col M (ID) peut rester dans GSheet sans impact — elle est ignorée par l'ancienne version du code
