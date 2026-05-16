# SPEC — Spinners dashboard (Planning LDE V2)

**Date :** 2026-05-16  
**Statut :** draft — à valider avant implémentation  
**Prompt de démarrage Claude Code :**
> Implémente la spec `planning-lde-v2/SPEC-SPINNERS.md`. Commence par lire ce fichier et le `CLAUDE.md` du projet (`planning-lde-v2/CLAUDE.md`). Lis les handlers existants dans `ui.js` avant d'en modifier.

---

## Objectif

Rendre visible qu'une action GSheet est en cours : remplacer le simple changement de texte `"En cours…"` par un **ring spinner CSS** (option A) injecté dans le bouton actif.

---

## Fichiers modifiés

| Fichier | Nature de la modification |
|---------|--------------------------|
| `DASHBOARD-V2.html` | Ajout CSS : keyframe `@keyframes spin` + classe `.btn-spinner` |
| `ui.js` | Ajout helper `setLoading(btn, loading)` + mise à jour des 6 handlers GSheet |

Aucune modification de `api.js`, `app.js`, `serve-v2.py` ou `data.json`.

---

## 1. CSS à ajouter dans `DASHBOARD-V2.html`

**Emplacement :** section `/* ── GSheet toolbar ── */` (après la règle `.btn:disabled`).

```css
/* Spinner ring (actions GSheet) */
@keyframes spin { to { transform: rotate(360deg); } }
.btn-spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  vertical-align: middle;
  margin-right: 5px;
  flex-shrink: 0;
}
```

---

## 2. Helper `setLoading` à ajouter dans `ui.js`

**Emplacement :** après les variables globales (lignes 5–19), avant la fonction `toast`.

```js
function setLoading(btn, loading) {
  if (loading) {
    btn._origHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-spinner" aria-hidden="true"></span>' + btn._origHTML.trim();
  } else {
    btn.disabled = false;
    if (btn._origHTML !== undefined) {
      btn.innerHTML = btn._origHTML;
      delete btn._origHTML;
    }
  }
}
```

**Principe :** sauvegarde le `innerHTML` d'origine (texte + éventuels caractères comme `⊡`) dans `btn._origHTML`, injecte le spinner, restaure proprement dans le `finally`.

---

## 3. Mise à jour des 6 handlers dans `ui.js`

Pour chaque handler, remplacer le pattern actuel :
```js
const orig = btn.textContent;
btn.disabled = true; btn.textContent = 'En cours…';
// ...
finally { btn.disabled = false; btn.textContent = orig; }
```
par :
```js
setLoading(btn, true);
// ...
finally { setLoading(btn, false); }
```

### Détail par bouton

#### `btn-init-gsheet` (lignes ~979–988)
Actuellement **sans** état de chargement. Ajouter le pattern complet :

```js
document.getElementById('btn-init-gsheet').addEventListener('click', async () => {
  const btn = document.getElementById('btn-init-gsheet');
  setLoading(btn, true);
  try {
    const r = await initGsheet();
    if (r.warnings && r.warnings.length) {
      showResults('GSheet initialisée — warnings', r.warnings);
    } else {
      toast('GSheet initialisée — mise en forme restaurée.');
    }
  } catch (err) { toast(err.message, 'error'); }
  finally { setLoading(btn, false); }
});
```

#### `btn-format-gsheet` (lignes ~990–1002)
Remplacer `orig` / `textContent` par `setLoading`.

#### `btn-save-template` (lignes ~1004–1013)
Remplacer `orig` / `textContent` par `setLoading`.

#### `btn-push-gsheet` (lignes ~1017–1032)
Remplacer `orig` / `textContent` par `setLoading`. Conserver le verrouillage des boutons voisins (`gsBtns`).

#### `btn-pull-gsheet` (lignes ~1034–1048)
Remplacer `orig` / `textContent` par `setLoading`. Conserver le verrouillage `gsBtns`.

#### `btn-pull-tcd` (lignes ~1050–1064)
Remplacer `orig` / `textContent` par `setLoading`. Conserver le verrouillage `gsBtns`.

---

## 4. Comportement attendu

| Situation | Résultat visible |
|-----------|-----------------|
| Clic sur un bouton GSheet | Ring spinner bleu apparaît à gauche du texte d'origine, bouton grisé (opacity 0.4 via `.btn:disabled`) |
| Autres boutons GSheet (push/pull) | Désactivés pendant l'opération (comportement inchangé) |
| Fin de l'opération (succès ou erreur) | Texte d'origine restauré, spinner retiré, bouton réactivé |
| Bouton `⊡ Modèles` | Texte et caractère `⊡` préservés (innerHTML, pas textContent) |

---

## 5. Points à ne pas toucher

- Aucune modification de la logique de désactivation des boutons voisins (`gsBtns`)
- Aucune modification des appels API (`initGsheet`, `formatGsheet`, etc.)
- Aucune modification du `showResults` ou du `toast`
- Ne pas utiliser `textContent` (perdrait le `⊡` de `btn-save-template`) — utiliser `innerHTML` via le helper

---

## 6. Impact sur les tests

Aucun test e2e existant ne teste l'état visuel des boutons GSheet. Pas d'adaptation requise.
