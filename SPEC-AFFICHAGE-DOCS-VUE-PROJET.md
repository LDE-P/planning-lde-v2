# SPEC — Affichage docs dans Vue Projets et Archives (`affichage-docs-vue-projet`)

**Projet :** Planning LDE V2
**Sous-projet :** `affichage-docs-vue-projet`
**Statut :** SPEC (arbitrages LDE intégrés — prête pour ping-pong)
**Auteur :** LDE + Cowork
**Date :** 2026-05-20

---

## 1. Contexte et objectif

La Vue Docs (onglet dédié) est déjà implémentée et opérationnelle (SP `gestion-des-md`, archivé). Elle affiche tous les docs sous forme de catalogue filtrable, avec CRUD complet. Son rôle : **chercher un doc dans l'ensemble des projets**.

**Ce qui manque :** dans la Vue Projets (et Vue Archives), l'utilisateur ne voit pas les docs associés à un SP sans quitter sa vue. Il doit basculer vers l'onglet Docs, filtrer, puis revenir.

**Objectif :** afficher les docs **contextuellement au bon niveau** — SP ou projet — dans Vue Projets et Vue Archives :
- Les docs d'un SP apparaissent dans le panneau détail de ce SP (même section que les étapes).
- Les docs sans SP (et les vrais orphelins) apparaissent dans un bloc dépliable au pied de la carte projet.

Ce n'est **pas** un doublon de la Vue Docs : l'onglet Docs reste le catalogue de référence avec filtres, tri, CRUD. L'affichage inline est une vue en lecture (+ ouverture fichier) dans le contexte du travail en cours.

---

## 2. Décisions UX — arbitrages validés

### 2.1 — Deux niveaux d'affichage

| Niveau | Quels docs | Où s'affiche |
|--------|-----------|--------------|
| **SP** | `doc.subproject === sp.id` (SP actif uniquement) | Dans `stepsPanel` du SP, après les étapes |
| **Projet** | `doc.subproject` absent **ou** SP orphelin (introuvable) | Bloc dépliable `📄 Docs (N)` en pied de carte projet |

**Docs référençant un SP archivé :** **non affichés** (ni au niveau SP — le SP n'est plus dans la liste — ni au niveau projet). Ces docs restent dans la Vue Docs globale.

### 2.2 — Bloc dépliable au niveau projet

- **Option retenue :** bloc dépliable avec bouton `📄 Docs (N)`, positionné sous la liste SP.
- Fermé par défaut.
- Absent si aucun doc de niveau projet (aucun doc sans SP + aucun orphelin).

### 2.3 — Bloc SP : intégration dans le panneau détail

- Les docs SP sont visibles quand l'utilisateur ouvre le panneau détail du SP (clic sur ▶).
- Ils apparaissent **après** les étapes, dans le même `stepsPanel`.
- Pas de toggle séparé — la même commande ▶/▼ contrôle étapes et docs.
- Absent si aucun doc n'est associé à ce SP.

### 2.4 — Format des lignes (identique aux deux niveaux)

Format compact, une ligne par doc :

```
[TYPE] Titre du document                          [STATUS]  ↗ TextMate  📁 Finder
```

- Badge type : même CSS que Vue Docs (`doc-type-badge doc-type-{type}`)
- Badge statut : même CSS que Vue Docs (`doc-status-badge doc-status-{status}`)
- Liens TextMate et Finder : même logique que Vue Docs (lecture seule, pas d'édition ni suppression)
- **Niveau SP :** pas de ligne "SP : …" (on est déjà dans le contexte du SP)
- **Niveau projet, doc orphelin :** ligne `SP : id-sp (orphelin)` en rouge (`class="orphan"`) pour signaler l'incohérence

---

## 3. Implémentation — `ui.js` uniquement

**Aucun endpoint backend n'est nécessaire.** Les docs sont déjà dans la réponse `/api/state` (champ `proj.docs[]`). Aucune modification de `serve-v2.py` ou `api.js`.

### 3.1 — Fonction utilitaire `renderDocInlineRow(doc, absFile)`

Fonction partagée, utilisée aux deux niveaux.

```js
/**
 * Crée une ligne doc compacte (format inline).
 * @param {Object} doc - objet doc de data.json
 * @param {string} absFile - chemin absolu vers le fichier (git_root + doc.file)
 * @param {Object} [options]
 * @param {string} [options.orphanSpId] - si défini, affiche la mention orphelin
 * @returns {HTMLElement}
 */
function renderDocInlineRow(doc, absFile, options = {}) { ... }
```

Structure HTML produite :

```html
<div class="doc-inline-row">
  <div class="doc-inline-title-row">
    <span class="doc-type-badge doc-type-{type}">{typeLabel}</span>
    <span class="doc-inline-title">{title}</span>
    <span class="doc-status-badge doc-status-{status}">{statusLabel}</span>
    <a href="txmt://open?url=file://{absFile}" class="doc-inline-link" title="Ouvrir dans TextMate">↗ TextMate</a>
    <button class="doc-inline-finder" title="Révéler dans le Finder">📁 Finder</button>
  </div>
  <!-- uniquement si options.orphanSpId -->
  <div class="doc-inline-sp"><span class="orphan">SP : {orphanSpId} (orphelin)</span></div>
</div>
```

### 3.2 — Affichage docs dans le panneau SP

Dans `renderSubproject(projectId, sp)`, **après** `stepsPanel.appendChild(...)` des étapes et **avant** `main.appendChild(stepsPanel)` :

```js
// Docs du SP (lecture seule, inline dans le panneau détail)
const projDocs = _state.projects.find(p => p.id === projectId)?.docs || [];
const spDocs = projDocs.filter(d => d && d.subproject === sp.id);
if (spDocs.length > 0) {
  const gitRoot = _state.git_root || '';
  const docsSection = document.createElement('div');
  docsSection.className = 'sp-docs-section';

  const label = document.createElement('div');
  label.className = 'sp-docs-label';
  label.textContent = `📄 Docs (${spDocs.length})`;
  docsSection.appendChild(label);

  spDocs.forEach(doc => {
    const absFile = gitRoot ? `${gitRoot}/${doc.file}` : doc.file;
    docsSection.appendChild(renderDocInlineRow(doc, absFile));
  });
  stepsPanel.appendChild(docsSection);
}
```

### 3.3 — Fonction `renderProjectDocsBlock(proj, isArchive)`

Filtre les docs de niveau projet : sans SP, ou SP orphelin (introuvable dans actifs ET dans archives).

```js
/**
 * Crée le bloc dépliable "Docs" au niveau projet.
 * N'inclut PAS les docs associés à un SP actif (affichés dans le SP).
 * N'inclut PAS les docs associés à un SP archivé (non affichés).
 * Inclut les docs sans SP et les vrais orphelins.
 * @returns {HTMLElement|null} - null si aucun doc de niveau projet
 */
function renderProjectDocsBlock(proj, isArchive = false) {
  const allDocs = proj.docs || [];
  if (allDocs.length === 0) return null;

  // Set des SP actifs du projet (dans Vue Projets) ou vide (Vue Archives — tous sont archivés)
  const activeSpIds = isArchive
    ? new Set()
    : new Set((proj.subprojects || []).map(s => s.id));

  // Set des SP archivés du projet
  const archProj = _archivesState?.projects.find(p => p.id === proj.id);
  const archivedSpIds = new Set((archProj?.subprojects || []).map(s => s.id));

  const projectDocs = allDocs.filter(d => {
    if (!d || typeof d !== 'object') return false;
    if (!d.subproject) return true;                        // pas de SP → niveau projet
    if (activeSpIds.has(d.subproject)) return false;       // SP actif → affiché dans le SP
    if (archivedSpIds.has(d.subproject)) return false;     // SP archivé → non affiché
    return true;                                           // vrai orphelin → niveau projet
  });

  if (projectDocs.length === 0) return null;

  const block = document.createElement('div');
  block.className = 'docs-inline-block';

  const toggle = document.createElement('button');
  toggle.className = 'docs-inline-toggle';
  toggle.innerHTML = `▶ 📄 Docs (${projectDocs.length})`;
  block.appendChild(toggle);

  const list = document.createElement('div');
  list.className = 'docs-inline-list collapsed';
  block.appendChild(list);

  const gitRoot = _state.git_root || '';
  projectDocs.forEach(doc => {
    const absFile = gitRoot ? `${gitRoot}/${doc.file}` : doc.file;
    const isOrphan = !!doc.subproject; // si on arrive ici avec un subproject, c'est un orphelin
    list.appendChild(renderDocInlineRow(doc, absFile,
      isOrphan ? { orphanSpId: doc.subproject } : {}));
  });

  toggle.addEventListener('click', e => {
    e.stopPropagation();
    const collapsed = list.classList.toggle('collapsed');
    toggle.innerHTML = `${collapsed ? '▶' : '▼'} 📄 Docs (${projectDocs.length})`;
  });

  return block;
}
```

### 3.4 — Intégration dans `renderProject(proj)`

À la fin de `renderProject`, après `card.appendChild(list)` (liste des SP) et **avant** `return card` :

```js
const docsBlock = renderProjectDocsBlock(proj, false);
if (docsBlock) card.appendChild(docsBlock);
```

### 3.5 — Intégration dans la Vue Archives

La Vue Archives a ses propres fonctions de rendu (à partir de ~ligne 892 dans `ui.js`). Localiser la fonction qui construit la carte d'un projet archivé et ajouter :

```js
const docsBlock = renderProjectDocsBlock(archivedProj, true);
if (docsBlock) card.appendChild(docsBlock);
```

> **Note Vue Archives :** en Vue Archives, tous les SP sont archivés. Les docs sans SP s'affichent dans le bloc projet. Les docs associés à des SP archivés ne s'affichent nulle part (règle uniforme : SP archivé → doc non affiché). Seuls les vrais orphelins (id SP inconnu) s'affichent avec la mention rouge.

> **Avant d'implémenter :** lire les fonctions de rendu Archives pour identifier le bon point d'insertion. Appliquer la Règle 4.

### 3.6 — CSS à ajouter dans `DASHBOARD-V2.html`

```css
/* ── Docs inline dans SP panel ──────────────────────────────── */
.sp-docs-section {
  margin-top: 6px;
  padding-top: 4px;
  border-top: 1px dashed var(--border);
}

.sp-docs-label {
  font-size: 11px;
  color: var(--text-secondary);
  font-weight: 500;
  padding: 2px 0 3px 2px;
}

/* ── Bloc docs inline au niveau projet ──────────────────────── */
.docs-inline-block {
  margin: 4px 8px 8px 8px;
  border-top: 1px solid var(--border);
}

.docs-inline-toggle {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 8px;
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
}
.docs-inline-toggle:hover {
  color: var(--text);
}

.docs-inline-list {
  padding: 0 4px 4px 4px;
}
.docs-inline-list.collapsed {
  display: none;
}

/* ── Ligne doc commune aux deux niveaux ─────────────────────── */
.doc-inline-row {
  padding: 3px 4px;
  border-bottom: 1px solid var(--border-light, #eee);
  font-size: 12px;
}
.doc-inline-row:last-child {
  border-bottom: none;
}

.doc-inline-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.doc-inline-title {
  flex: 1;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-inline-link {
  font-size: 11px;
  color: var(--link, #0066cc);
  text-decoration: none;
  white-space: nowrap;
}
.doc-inline-link:hover {
  text-decoration: underline;
}

.doc-inline-finder {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 11px;
  padding: 0;
  color: var(--text-secondary);
}
.doc-inline-finder:hover {
  color: var(--text);
}

.doc-inline-sp {
  font-size: 11px;
  margin-left: 4px;
  margin-top: 1px;
}
.doc-inline-sp .orphan {
  color: var(--blocked);
}
```

---

## 4. Réponses aux questions ouvertes

### Q1 — Docs orphelins légitimes (SP archivé)

**Réponse :** les docs référençant un SP archivé sont **non affichés** dans la Vue Projets inline. Ils restent accessibles via la Vue Docs globale. Raison : le SP n'est plus actif, afficher ses docs dans le contexte de travail courant n'apporte pas de valeur — et signaler ces docs comme "archivés" risque de polluer le panneau détail avec des informations passées.

Les vrais orphelins (id SP totalement inconnu, ni actif ni archivé) sont **signalés** au niveau projet avec la classe `orphan` (texte rouge) pour indiquer une incohérence à corriger.

### Q2 — Impact process (checklist fin de session)

**Réponse :** l'étape 3bis de la checklist (`CLAUDE.md` racine) **couvre déjà ce besoin** : elle demande de proposer l'enregistrement des fichiers MD produits en session dans `data.json` avec le bon `subproject`. La visibilité accrue des docs dans la Vue Projets renforce la valeur de 3bis, mais n'exige aucune modification de la règle.

### Q3 — Impact agent de ménage

**Réponse :** le skill `rangement-git` pourra évoluer pour signaler les docs orphelins (SP introuvable) en parcourant `data.json`. Hors scope de cette spec — noté dans `suivi-planning-lde.md` comme TODO futur.

### Q4 — Docs provisoires créés en cours de session

**Réponse :** les docs de travail temporaires (notes de debug, journaux de tests, brouillons) n'ont **pas** à être obligatoirement enregistrés dans `data.json`. L'étape 3bis est optionnelle pour les fichiers purement techniques ou temporaires. Comportement inchangé.

---

## 5. Fichiers modifiés

| Fichier | Modification |
|---------|-------------|
| `ui.js` | `renderDocInlineRow()` + `renderProjectDocsBlock()` + intégration dans `renderSubproject()` (docs SP) + `renderProject()` + Vue Archives |
| `DASHBOARD-V2.html` | Règles CSS `.sp-docs-*` + `.docs-inline-*` + `.doc-inline-*` |

Aucune modification de `serve-v2.py`, `api.js`, `data.json`.

---

## 6. Évolutions non incluses dans ce scope

- Ajout d'un doc directement depuis le bloc inline (bouton ＋) — possible mais hors scope ; renvoie vers la Vue Docs pour le CRUD.
- Tri ou filtrage des docs dans le bloc inline — hors scope (la Vue Docs est là pour ça).
- Affichage d'un badge compteur de docs sur l'en-tête SP (hors panneau détail) — envisageable, hors scope.

---

## 7. Estimation de charge

| Composant | Charge estimée |
|-----------|---------------|
| `ui.js` — `renderDocInlineRow()` | 0,25 h |
| `ui.js` — intégration docs dans `renderSubproject()` | 0,25 h |
| `ui.js` — `renderProjectDocsBlock()` | 0,5 h |
| `ui.js` — intégration `renderProject()` + Vue Archives | 0,25 h |
| `DASHBOARD-V2.html` — règles CSS | 0,25 h |
| Tests manuels (SP avec docs, projet avec docs sans SP, orphelins, Vue Archives) | 0,5 h |
| **Total** | **~2 h** |

---

## 8. Questions ouvertes pour le ping-pong

1. **Docs SP archivé en Vue Archives :** en Vue Archives, tous les SP sont archivés. La règle actuelle dit "SP archivé → non affiché". Résultat : dans la Vue Archives, aucun doc SP n'est jamais affiché en inline (uniquement les docs sans SP et les orphelins). Est-ce le comportement voulu ? Ou dans la Vue Archives, les docs associés aux SP archivés devraient-ils s'afficher (puisque c'est précisément le contexte archive) ?

2. **Bloc projet fermé vs ouvert par défaut :** la spec choisit fermé. Valider ce choix.

3. **Lien TextMate comme action principale :** est-ce la bonne priorité ? (Cohérence avec le bouton 📁 de l'en-tête projet.)

---

## 9. Prompt de démarrage Claude Code

> Implémente la spec `planning-lde-v2/SPEC-AFFICHAGE-DOCS-VUE-PROJET.md`. Commence par lire ce fichier, `planning-lde-v2/CLAUDE.md` et `GIT/CLAUDE.md`. Puis lis `ui.js` en entier avant d'écrire quoi que ce soit.
>
> Points d'attention :
> (1) Les docs SP s'insèrent dans `stepsPanel` de `renderSubproject()`, après les étapes — pas dans un bloc séparé avec son propre toggle, la même commande ▶/▼ contrôle tout.
> (2) `renderProjectDocsBlock()` filtre soigneusement : SP actif → exclu (déjà dans le SP) ; SP archivé → exclu (non affiché) ; pas de SP ou SP orphelin → inclus.
> (3) Dans `renderSubproject()`, les docs sont récupérés via `_state.projects.find(p => p.id === projectId)?.docs || []` — pas passés en paramètre.
> (4) Les CSS doivent utiliser les variables existantes (`var(--border)`, `var(--text-secondary)`, `var(--blocked)`…) — ne pas introduire de valeurs brutes.
> (5) Aucune modification de `serve-v2.py` ou `api.js` — tout est dans `ui.js` et `DASHBOARD-V2.html`.
> (6) Lire les fonctions de rendu Archives (~ligne 892) avant d'y intégrer quoi que ce soit — appliquer la Règle 4.
