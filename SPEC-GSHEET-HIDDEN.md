# SPEC — Exclusion GSheet par projet (`gsheet_hidden`)

**Projet :** Planning LDE V2
**Sous-projet :** à créer (ex : `exclusion-gsheet`)
**Statut :** SPEC (validée — prête pour implémentation)
**Auteur :** LDE + Cowork
**Date :** 2026-05-16

---

## 1. Contexte et objectif

Certains projets du dashboard (outils personnels, suivi éditorial, projets de réflexion…) n'ont pas vocation à apparaître dans la GSheet partagée avec l'équipe. Actuellement, tous les projets présents dans `data.json` sont pushés/pullés sans distinction.

**Objectif :** permettre d'exclure un projet de toute synchronisation GSheet (push et pull) via un flag `gsheet_hidden` dans `data.json`, géré depuis le dashboard.

---

## 2. Schéma `data.json`

Nouveau champ optionnel sur l'objet projet :

```json
{
  "id": "mon-projet",
  "name": "Mon Projet",
  "gsheet_hidden": true,
  ...
}
```

- **Absent ou `false`** → comportement actuel (projet inclus dans push/pull)
- **`true`** → projet exclu de toute opération GSheet

Aucune migration nécessaire : les projets existants sans ce champ continuent à se comporter normalement.

---

## 3. UI Dashboard (`ui.js`)

### 3.1 — Icône dans l'en-tête projet

Un bouton `icon-btn btn-toggle-gsheet` est ajouté dans `.project-actions` de chaque projet, **avant** les boutons archiver/supprimer :

| État | Icône | Style | Tooltip |
|------|-------|-------|---------|
| Projet visible dans GSheet (`gsheet_hidden` absent ou `false`) | `👁` | `text-decoration: line-through` | "Ce projet est inclus dans la GSheet — cliquer pour l'exclure" |
| Projet exclu (`gsheet_hidden: true`) | `👁` | aucun | "Ce projet est exclu de la GSheet — cliquer pour le réinclure" |

**Implémentation CSS :** `text-decoration: line-through` s'applique directement sur l'élément bouton contenant l'emoji — fonctionne sur tous les navigateurs modernes sans trick supplémentaire. Ajouter/retirer la classe `gsheet-visible` selon l'état :

```css
/* dans DASHBOARD-V2.html */
.btn-toggle-gsheet.gsheet-visible { text-decoration: line-through; }
```

**Tooltip enrichissement** : profiter de ce passage dans `ui.js` pour enrichir tous les `title` courts existants (`'Renommer'` → `'Renommer ce sous-projet'`, `'Archiver'` → `'Archiver ce sous-projet'`, etc.).

### 3.2 — Modale toggle

Cliquer sur l'icône ouvre une modale dédiée (réutiliser le pattern `modal-confirm` existant) :

**Si projet actuellement visible :**
```
Titre : Exclure de la GSheet ?
Corps : "Mon Projet" ne sera plus inclus dans les push ni les pull.
        Le prochain push supprimera ses lignes existantes dans l'onglet Tâches.
Boutons : [Annuler]  [Exclure]
```

**Si projet actuellement exclu :**
```
Titre : Réinclure dans la GSheet ?
Corps : "Mon Projet" sera à nouveau inclus dans les push et les pull.
        Il réapparaîtra dans l'onglet Tâches au prochain push.
Boutons : [Annuler]  [Réinclure]
```

L'action appelle un nouvel endpoint `/api/toggle-gsheet-hidden` (voir §4).

---

## 4. Nouvel endpoint (`serve-v2.py`)

### `POST /api/toggle-gsheet-hidden`

**Corps :**
```json
{ "projectId": "mon-projet" }
```

**Comportement :**
1. Charge `data.json`
2. Trouve le projet par `id`
3. Inverse le flag : `gsheet_hidden = not proj.get('gsheet_hidden', False)`
4. Sauvegarde via `_save_data()`
5. Retourne `{"ok": true, "gsheet_hidden": <nouvelle_valeur>}`

**Sécurité :** même squelette que les endpoints existants (CORS, payload max, `_read_json_body`, `_json_ok`/`_json_error`).

**Pattern d'exception :** suivre `_handle_save_subproject` (pas `_handle_remove_project`) pour le traitement des erreurs — `OverflowError` → 413 séparé, `json.JSONDecodeError`/`UnicodeDecodeError` → 400. `_handle_remove_project` sert de référence uniquement pour les **libellés** (`'projectId requis'`, `'Projet introuvable'`).

---

## 5. Push (`_gs_push` et `_gs_push_preview`)

### 5.1 — `_gs_build_taches_rows()`

Ajouter un filtre en tête de boucle :

```python
for proj in data.get('projects', []):
    if proj.get('gsheet_hidden'):
        continue  # projet exclu — ignoré
    ...
```

Même filtre dans `_build_tcd_rows()`.

### 5.2 — Préservation de C (Type) et J (Commentaire) lors de l'exclusion d'un projet

**Le `batch_clear` existant ne touche pas aux colonnes C et J** — elles sont volontairement préservées (GSheet-only, jamais réécrites par le push, cf. `_gs_push` qui ne clear que `A2:B1000`, `D2:I1000`, `K2:L1000`).

Si on se contente de filtrer dans `_gs_build_taches_rows()`, les valeurs C/J anciennes restent en place et se retrouvent **décalées et associées aux mauvais SP** dès qu'un projet du milieu est exclu. Ce bug existe déjà aujourd'hui sur la suppression d'un SP au milieu d'un projet — il devient critique avec l'exclusion d'un projet entier.

**Solution validée (Option 2) : read-before-clear + restauration ciblée des projets visibles.**

Étapes ajoutées dans `_gs_push()`, **avant** le `batch_clear` existant :

1. **Lire l'état actuel** de l'onglet Tâches via `ws_t.get('A2:J1000')` (une seule lecture).
2. **Construire `hidden_aliases`** (set des alias des projets `gsheet_hidden`).
3. **Construire `preserved_cj`** : map `(alias_lower, sp_name_lower) → (type, commentaire)` pour les couples appartenant à des projets **visibles uniquement**. Les couples appartenant à un projet masqué sont exclus → leurs C/J seront effacées au clear étendu.

Puis :

4. **Étendre le `batch_clear`** avec `'C2:C1000'` et `'J2:J1000'` (efface toutes les valeurs résiduelles, masquées et visibles).
5. **Après le `batch_update` A-B, D-I, K-L** existant, reconstruire C et J depuis `preserved_cj`, dans le même ordre que les lignes filtrées (deux `batch_update` ciblés `C2:C{last}` et `J2:J{last}`).

```python
# Dans _gs_push, AVANT batch_clear
# Note : le code existant utilise get_all_values() (pattern établi).
# Utiliser ws_t.get_all_values() puis rows[1:] limités à 10 colonnes (A–J),
# plutôt que ws_t.get('A2:J1000') dont la disponibilité dépend de la version gspread.
existing = ws_t.get_all_values()[1:]  # saute le header, colonnes A–L
hidden_aliases = {
    (p.get('alias') or p['name']).lower()
    for p in data.get('projects', [])
    if p.get('gsheet_hidden')
}
preserved_cj = {}  # (alias_lower, sp_name_lower) → (type, commentaire)
for r in existing:
    if len(r) < 2 or not r[0].strip() or not r[1].strip():
        continue
    alias_l = r[0].strip().lower()
    if alias_l in hidden_aliases:
        continue  # ligne d'un projet masqué → ne pas préserver
    sp_l = r[1].strip().lower()
    type_ = r[2] if len(r) > 2 else ''
    commentaire = r[9] if len(r) > 9 else ''
    preserved_cj[(alias_l, sp_l)] = (type_, commentaire)

# batch_clear étendu
ws_t.batch_clear(['A2:B1000', 'C2:C1000', 'D2:I1000', 'J2:J1000', 'K2:L1000'])

# batch_update A-B, D-I, K-L (logique existante)

# Restauration ciblée C et J pour les lignes pushées
if rows:
    c_col = [[preserved_cj.get((r[0].lower(), r[1].lower()), ('', ''))[0]] for r in rows]
    j_col = [[preserved_cj.get((r[0].lower(), r[1].lower()), ('', ''))[1]] for r in rows]
    last = n + 1
    ws_t.batch_update([
        {'range': f'C2:C{last}', 'values': c_col},
        {'range': f'J2:J{last}', 'values': j_col},
    ], value_input_option='USER_ENTERED')
```

**Coût supplémentaire :** 1 lecture GSheet + 1 batch_update supplémentaire (~0,5 s par push). Acceptable pour la robustesse gagnée.

**Effets de bord positifs :**
- Corrige le bug pré-existant de décalage C/J lors de la suppression d'un SP au milieu d'un projet.
- Aligne le comportement avec la doc : « col C et J GSheet-only » devient strict (pas de pollution par décalage).

### 5.3 — Preview (`_gs_push_preview`)

Ajouter dans le résultat de preview :

```python
hidden = [
    (proj.get('alias') or proj['name'])
    for proj in data.get('projects', [])
    if proj.get('gsheet_hidden')
]
```

Retourner `"hidden_projects": hidden` dans la réponse JSON de preview.

Côté UI (`ui.js`), si `r.hidden_projects` est non vide, ajouter dans la modale de résultat preview :

```
⚠ Projets exclus de la GSheet (leurs lignes seront supprimées) :
  • Amélioration Certification
  • Optimisation Prompts Claude
```

---

## 6. Pull (`_gs_pull_taches` et `_gs_pull_taches_preview`)

### 6.1 — Ignorer les lignes des projets masqués

Préparer en tête de `_gs_pull_taches()` **et** `_gs_pull_taches_preview()` un set des alias masqués :

```python
hidden_aliases = {
    (p.get('alias') or p['name']).lower()
    for p in data.get('projects', [])
    if p.get('gsheet_hidden')
}
```

Pour chaque ligne, **avant** `_find_sp()`, vérifier si l'alias correspond à un projet masqué :

```python
alias_l = row[0].strip().lower()
if alias_l in hidden_aliases:
    if alias not in ignored:
        ignored.append(alias)
    continue  # ne pas créer, ne pas pousser dans data.json
```

Retourner `"ignored_projects": ignored` dans la réponse JSON (liste dédupliquée).

**Côté preview (`_gs_pull_taches_preview`) :** même filtre — `ignored_projects` figure aussi dans le résultat, et les lignes masquées ne génèrent pas d'entrées dans `changes`.

> **Pourquoi vérifier avant `_find_sp` (et non après)** : garantit le comportement « masqué gagne » lors d'une collision d'alias (cf. §6.2 F4). Toute ligne dont l'alias correspond à un projet masqué est ignorée, indépendamment de l'ordre des projets dans `data['projects']`.

### 6.2 — Cas particuliers

**Alias inconnu d'un projet masqué :** si `_find_sp()` ne trouve pas l'alias ET que cet alias correspond à un projet masqué → ignorer sans créer de projet fantôme. Si l'alias est totalement inconnu (pas dans `data.json`) → comportement actuel (création du projet).

**Collision d'alias (masqué + visible) :** si deux projets partagent le même alias et que l'un est masqué, toutes les lignes portant cet alias sont ignorées au pull — le projet masqué "gagne" la comparaison. Cas non standard (alias supposés uniques), pas de crash attendu.

### 6.3 — Signalement dans la modale de résultat pull

Si `r.ignored_projects` est non vide, ajouter dans la modale après le compteur de mises à jour :

```
ℹ X ligne(s) ignorées (projets exclus de la GSheet) :
  • Amélioration Certification
```

---

## 7. Fichiers modifiés

| Fichier | Modification |
|---------|-------------|
| `data.json` | Nouveau champ `gsheet_hidden: true` sur les projets concernés |
| `DASHBOARD-V2.html` | Règle CSS `.btn-toggle-gsheet.gsheet-visible { text-decoration: line-through; }` |
| `ui.js` | Icône toggle + modale + affichage dans modales push/pull preview/result + enrichissement tooltips |
| `api.js` | Nouveau wrapper `toggleGsheetHidden(projectId)` |
| `serve-v2.py` | Endpoint `/api/toggle-gsheet-hidden` + filtres dans `_gs_build_taches_rows()` et `_build_tcd_rows()` + read-before-clear + restauration C/J dans `_gs_push()` + `hidden_projects` dans preview push + `ignored_projects` dans pull (et pull preview) |

---

## 8. How to Rollback

En cas de problème après implémentation :

1. **Retirer le champ `gsheet_hidden`** des projets concernés dans `data.json` (via édition directe ou dashboard)
2. **Relancer un push GSheet** → les projets réapparaissent dans l'onglet Tâches avec leurs sous-projets
3. **Données GSheet-only perdues** (col C Type, col J Commentaire) si un push a eu lieu après exclusion : à restaurer manuellement depuis un export xlsx de sauvegarde ou depuis la mémoire équipe

> ⚠ **Point de non-retour** : un push après exclusion supprime les colonnes C et J pour les projets masqués. Ces colonnes sont GSheet-only et ne sont jamais dans `data.json`. Toujours faire un export xlsx avant le premier push post-activation.

**Rollback côté code** : retirer le endpoint `/api/toggle-gsheet-hidden` de `serve-v2.py`, retirer le filtre dans `_gs_build_taches_rows()` et `_build_tcd_rows()`, retirer le bouton icône et la logique dans `ui.js` et `api.js`.

---

## 9. Estimation de charge

| Composant | Charge estimée |
|-----------|---------------|
| `serve-v2.py` — endpoint + filtres push/pull + read-before-clear + restauration C/J | 2 h |
| `ui.js` — icône, modale toggle, signalement modales + tooltips | 1,5 h |
| `api.js` — wrapper | 0,25 h |
| `DASHBOARD-V2.html` — règle CSS | 0,1 h |
| Tests manuels end-to-end (incl. vérif C/J résiduel) | 0,75 h |
| **Total** | **~4,6 h** |

---

## 10. Prompt de démarrage Claude Code

> Implémente la spec `planning-lde-v2/SPEC-GSHEET-HIDDEN.md`. Commence par lire ce fichier et `planning-lde-v2/CLAUDE.md` et `GIT/CLAUDE.md`. Lis les fonctions existantes avant d'en écrire de nouvelles — applique le même squelette de sécurité (Règle 4). Points d'attention :
> (1) §5.2 read-before-clear est **non négociable** — le batch_clear actuel ne touche pas C/J et produit un décalage silencieux si on filtre sans préserver ;
> (2) la vérification `hidden_aliases` au pull se fait **avant** `_find_sp` pour garantir « masqué gagne » sur collision d'alias ;
> (3) la logique de signalement dans les modales push preview et pull result est côté `ui.js` ;
> (4) pour le handler `/api/toggle-gsheet-hidden`, le traitement des exceptions doit suivre `_handle_save_subproject` (OverflowError → 413 séparé, JSON errors → 400) — **pas** `_handle_remove_project` qui retourne 400 pour tout. Les libellés d'erreur (`'projectId requis'`, `'Projet introuvable'`) s'alignent sur `_handle_remove_project` ;
> (5) pour le read-before-clear en §5.2, utiliser `ws_t.get_all_values()[1:]` (pattern du code existant) — **pas** `ws_t.get('A2:J1000')` dont la disponibilité dépend de la version gspread installée.
