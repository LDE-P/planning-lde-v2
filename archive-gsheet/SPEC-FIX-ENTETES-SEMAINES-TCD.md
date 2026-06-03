# SPEC — En-têtes dynamiques des onglets Semaines et TCD Projets

**Projet :** Planning LDE V2
**Sous-projet :** à créer (`fix-entetes-semaines-tcd`)
**Statut :** SPEC (validée — prête pour implémentation)
**Auteur :** LDE + Cowork
**Date :** 2026-05-16

---

## 1. Contexte et problème

L'onglet **Semaines** a une architecture en deux couches :

- **Lignes 4+ (données)** — formules SIERREUR/FILTER/SOMME utilisant `ISOWEEKNUM(AUJOURDHUI())` : recalcul automatique au changement de semaine. ✓
- **Ligne 1 (en-têtes)** — valeurs statiques écrites par `_tcd_headers()` à chaque init ou push (ex. `"S19"`, `"S20 (P0)"`…) : ne bougent pas entre deux pushs. ✗

L'onglet **TCD Projets** a le même problème sur la ligne 1. Ses données (lignes 4+) sont des valeurs écrites depuis `data.json` au push — elles restent statiques par conception, ce qui est acceptable. Mais ses en-têtes doivent eux aussi être dynamiques.

**Résultat observable :** après un changement de semaine sans push, les en-têtes de colonnes (S19, S20 (P0)…) ne correspondent plus aux données affichées dans les colonnes. La colonne labellée "S20 (P0)" peut afficher du RAF de semaine S21.

Ce n'est **pas** un problème de réinitialisation : un init écrit les mêmes en-têtes statiques, corrects au moment de l'appel mais à nouveau décalés la semaine suivante.

---

## 2. Cause racine

La fonction `_tcd_headers()` retourne une liste de **chaînes Python** calculées une fois à l'appel :

```python
def _tcd_headers() -> list:
    today = date.today()
    prev_week = (today - timedelta(weeks=1)).isocalendar()[1]
    cols = ['Projet/Sous-projet', 'Total RAF', f'S{prev_week:02d}']
    for i, prio in enumerate(['P0', 'P1', 'P2', 'P3']):
        w = (today + timedelta(weeks=i)).isocalendar()[1]
        cols.append(f'S{w:02d} ({prio})')
    return cols
```

Ces chaînes sont écrites en valeurs dans la GSheet. Il suffit que les 5 colonnes semaine (C à G) soient des **formules GSheet** utilisant `AUJOURDHUI()` pour que les en-têtes se recalculent automatiquement à chaque ouverture de la GSheet.

---

## 3. Solution

Modifier `_tcd_headers()` pour que les colonnes C à G retournent des formules GSheet au lieu de chaînes statiques. Les colonnes A et B restent des chaînes statiques.

### 3.1 — Formules cibles

| Col | Rôle | Formule GSheet |
|-----|------|----------------|
| A1 | Libellé fixe | `'Projet/Sous-projet'` (inchangé) |
| B1 | Libellé fixe | `'Total RAF'` (inchangé) |
| C1 | S-1 | `="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI()-7);"00")` |
| D1 | S0 (P0) | `="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI());"00")&" (P0)"` |
| E1 | S+1 (P1) | `="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI()+7);"00")&" (P1)"` |
| F1 | S+2 (P2) | `="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI()+14);"00")&" (P2)"` |
| G1 | S+3 (P3) | `="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI()+21);"00")&" (P3)"` |

**Pourquoi des décalages en jours plutôt que `ISOWEEKNUM()-1` :**
L'approche `ISOWEEKNUM(AUJOURDHUI())-1` donne `0` en semaine 1 (au lieu de 52). L'approche par décalage de ±7 jours délègue le calcul à `ISOWEEKNUM()` sur une date valide — elle gère correctement les fins d'année, exactement comme le fait déjà `_friday_from_week_offset()` côté Python.

### 3.2 — Code modifié

```python
def _tcd_headers() -> list:
    """Headers C1-G1 : formules GSheet auto-recalculées à l'ouverture (AUJOURDHUI())."""
    return [
        'Projet/Sous-projet',
        'Total RAF',
        '="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI()-7);"00")',
        '="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI());"00")&" (P0)"',
        '="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI()+7);"00")&" (P1)"',
        '="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI()+14);"00")&" (P2)"',
        '="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI()+21);"00")&" (P3)"',
    ]
```

Le paramètre `raw=False` (déjà présent sur tous les appels `update()`) équivaut à `value_input_option='USER_ENTERED'` : GSheet interprète les chaînes commençant par `=` comme des formules. Aucune modification des sites d'appel.

---

## 4. Sites d'appel — aucune modification nécessaire

`_tcd_headers()` est appelée à 4 endroits, tous avec `raw=False` :

| Lieu | Appel | Impact |
|------|-------|--------|
| `_gs_init()` — init Semaines | `ws_s.update('A1:G1', [_tcd_headers()], raw=False)` | ✓ formules écrites |
| `_gs_init()` — init TCD | `ws_tcd.update('A1:G1', [_tcd_headers()], raw=False)` | ✓ formules écrites |
| `_gs_push()` — push Semaines | `ws_s.update('A1:G1', [dyn_headers], raw=False)` | ✓ formules réécrites |
| `_gs_push()` — push TCD | `ws_tcd.update('A1:G1', [dyn_headers], raw=False)` | ✓ formules réécrites |

---

## 5. Impact sur les autres fonctions

### Pull TCD (`_gs_pull_tcd`)

Lit les colonnes C-G par **position** (indices 2-6) et les mappe via `_WEEK_OFFSETS = [-1, 0, 1, 2, 3]`. Ne lit jamais les valeurs d'en-tête. **Aucun impact.**

### Pull Tâches (`_gs_pull_taches`)

Ne lit pas l'onglet Semaines ni ses en-têtes. **Aucun impact.**

### Preview push (`_gs_push_preview`)

Opère uniquement sur `data.json` en mémoire. Ne lit pas la GSheet. **Aucun impact.**

### Formules des lignes 4+ de Semaines

Utilisent déjà `ISOWEEKNUM(AUJOURDHUI())` indépendamment des en-têtes. **Aucun impact.**

---

## 6. Comportement après implémentation

### Semaines

- Ligne 1 : recalculée automatiquement à chaque ouverture GSheet. Toujours cohérente avec les données des lignes 4+.
- Pas de push requis pour mettre les en-têtes à jour.

### TCD Projets

- Ligne 1 : recalculée automatiquement.
- Lignes 4+ : toujours statiques (valeurs du dernier push). Un push hebdo reste nécessaire pour que les données soient à jour. Les en-têtes resteront cohérents avec la semaine courante même sans push, mais les valeurs RAF reflèteront l'état au moment du dernier push.

> **Note :** entre deux pushs, il peut y avoir un décalage apparent dans le TCD : les en-têtes (dynamiques) avancent mais les valeurs RAF (statiques) restent. C'est le comportement attendu et documenté — le TCD est un outil de pilotage actif, pas un tableau en lecture seule. Un push est la façon normale de le rafraîchir.

---

## 7. Bug pré-existant hors périmètre

Les formules de données des lignes 4+ de Semaines (`_f_semaines_week`) comparent `'Tâches'!K:K` à `"S"&ISOWEEKNUM(AUJOURDHUI())` sans zero-padding. Or la colonne K stocke `"S01"`, `"S02"`… (zero-paddé via `TEXTE(ISOWEEKNUM(F);"00")`). En semaines 1-9, le FILTER retourne 0 au lieu du RAF réel.

Ce bug est indépendant du présent fix, ne doit pas être corrigé dans cette PR, et sera traité dans un sous-projet séparé.

---

## 8. Fichiers modifiés

| Fichier | Modification |
|---------|-------------|
| `serve-v2.py` | `_tcd_headers()` uniquement — retourne des formules GSheet pour C1-G1 |

Aucune modification de `ui.js`, `api.js`, `DASHBOARD-V2.html`, `data.json`.

---

## 9. How to Rollback

Restaurer le corps de `_tcd_headers()` à son état précédent (calcul Python + chaînes statiques). Relancer un push pour récrire les en-têtes statiques dans la GSheet.

---

## 10. Estimation de charge

| Composant | Charge |
|-----------|--------|
| Modification `_tcd_headers()` | 0,25 h |
| Test manuel (init + push + vérification J+7) | 0,25 h |
| **Total** | **~0,5 h** |

---

## 11. Procédure de test manuel

> Un fichier TESTS séparé n'est pas justifié pour une modification aussi localisée (0,5 h total, 1 seule fonction). La procédure ci-dessous est suffisante.

### Étapes

1. **Avant** : noter les valeurs actuelles de C1-G1 dans Semaines et TCD Projets (ex. "S19", "S20 (P0)"…).
2. Déployer la modification de `_tcd_headers()`.
3. Lancer un **push** depuis le dashboard (`/api/sync-to-gsheet`).
4. Dans la GSheet, vérifier que C1-G1 des deux onglets affichent bien des formules (cliquer sur une cellule → la barre de formule doit montrer `="S"&TEXTE(…)` et non une valeur statique).
5. Vérifier que les libellés affichés correspondent à la semaine ISO courante (S-1, S0, S+1, S+2, S+3).
6. **Test de robustesse fin d'année** (optionnel, simulable en changeant la date système) : les formules en décalage de jours ne doivent pas retourner "S00" en semaine 1.

### Vérification de non-régression

- Lancer un **pull TCD** : le résultat (`updated`, `target` recalculés) ne doit pas changer par rapport à avant la modification.
- Lancer un **push preview** : les lignes prévisualisées restent identiques.

### Note sur les tests e2e

Si des tests dans `tests-e2e-python/planning-lde/` vérifient le contenu de la ligne 1 de Semaines ou TCD Projets après un push (assertions sur des valeurs statiques type `"S19"`), ils sont à adapter : les assertions doivent désormais vérifier que la cellule contient une formule (chaîne commençant par `=`), ou vérifier la valeur calculée au moment du test via `ISOWEEKNUM` de la date courante.

---

## 12. Prompt de démarrage Claude Code

> Implémente la spec `planning-lde-v2/SPEC-FIX-ENTETES-SEMAINES-TCD.md`. Seul fichier modifié : `serve-v2.py`, uniquement la fonction `_tcd_headers()`. Lis `planning-lde-v2/CLAUDE.md` et au moins un handler existant avant de modifier (Règle 4). Vérifie que `raw=False` est bien présent sur tous les sites d'appel. Les formules de référence sont dans `planning-lde/formules.md` (section "Ligne 1 (C1-G1)") — recopier caractère par caractère.
