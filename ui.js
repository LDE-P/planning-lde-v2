// Rendu, interactions, événements

import { saveSubproject, addSubproject, addProject, saveProject, openFolder, removeSubproject, removeProject, addDoc, saveDoc, removeDoc, openFile, fetchArchives, archiveSubproject, archiveProject, restoreSubproject, restoreProject, deleteArchiveSubproject, deleteArchiveProject } from './api.js';

// ── État global ────────────────────────────────────────────────────────────────

let _state = { projects: [] };
let _filter = 'all';
let _statusMenuTarget = null;
let _fetchStateCallback = null;
let _openProjects = new Set();

let _view = 'projects';            // 'projects' | 'docs' | 'archives'
let _docFilterTypes = new Set();   // vide = tous
let _docFilterStatuses = new Set(['draft', 'final']);  // archived masqués par défaut
let _showEmptyProjects = false;
let _docModalMode = 'add';         // 'add' | 'edit'
let _docModalCtx = { projectId: null, docId: null };

let _archivesState = { projects: [] };  // cache local des archives
let _archivesLoaded = false;            // lazy-loading : chargé au premier accès

const DOC_TYPES = ['spec', 'audit', 'tests', 'bilan', 'notes', 'autre'];
const DOC_STATUSES = ['draft', 'final', 'archived'];

const DOC_TYPE_LABELS = { spec: 'SPEC', audit: 'AUDIT', tests: 'TESTS', bilan: 'BILAN', notes: 'NOTES', autre: 'AUTRE' };
const DOC_STATUS_LABELS = { draft: 'Brouillon', final: 'Final', archived: 'Archivé' };

export function setFetchStateCallback(fn) { _fetchStateCallback = fn; }

function fetchStateAndRefresh() {
  if (_fetchStateCallback) _fetchStateCallback().then(s => { _state = s; renderAll(); });
}

// ── Labels ─────────────────────────────────────────────────────────────────────

const STATUS_LABELS = {
  done: 'TERMINÉ', wip: 'EN COURS', review: 'REVUE',
  spec: 'SPEC', todo: 'À FAIRE', blocked: 'STAND BY', na: 'N/A',
  récurrent: 'RÉCURRENT', fail: 'ÉCHEC',
};

const SP_STATUSES = ['wip', 'récurrent', 'todo', 'spec', 'review', 'blocked', 'done', 'fail'];
const STEP_STATUSES = ['todo', 'wip', 'récurrent', 'done', 'na'];

// ── Toast ──────────────────────────────────────────────────────────────────────

let _toastTimer = null;

function toast(msg, type = 'success') {
  const el = document.getElementById('toast');
  clearTimeout(_toastTimer);
  if (type === 'error') {
    el.innerHTML = '';
    const txt = document.createElement('span');
    txt.textContent = msg;
    const btn = document.createElement('button');
    btn.className = 'toast-close';
    btn.textContent = '✕';
    btn.addEventListener('click', () => { el.className = ''; });
    el.append(txt, btn);
    el.className = 'show error';
  } else {
    el.textContent = msg;
    el.className = `show ${type}`;
    _toastTimer = setTimeout(() => { el.className = ''; }, 3000);
  }
}

// ── Stats bar ──────────────────────────────────────────────────────────────────

function updateStats() {
  const sps = _state.projects.flatMap(p => p.subprojects || []);
  document.getElementById('stat-total').textContent = sps.length;
  document.getElementById('stat-wip').textContent = sps.filter(s => s.status === 'wip').length;
  document.getElementById('stat-todo').textContent = sps.filter(s => s.status === 'todo').length;
  document.getElementById('stat-done').textContent = sps.filter(s => s.status === 'done').length;
  document.getElementById('stat-récurrent').textContent = sps.filter(s => s.status === 'récurrent').length;
}

// ── Filter ─────────────────────────────────────────────────────────────────────

function shouldShow(sp) {
  if (_filter === 'all') return true;
  return sp.status === _filter;
}

// ── Status badge ───────────────────────────────────────────────────────────────

function makeBadge(status, cls = 'status-badge') {
  const span = document.createElement('span');
  span.className = `${cls} status-${status}`;
  span.textContent = STATUS_LABELS[status] || status;
  return span;
}

// ── Doc inline helpers ─────────────────────────────────────────────────────────

/**
 * Crée une ligne doc compacte (format inline).
 * @param {Object} doc - objet doc de data.json
 * @param {string} absFile - chemin absolu vers le fichier (git_root + doc.file)
 * @param {Object} [options]
 * @param {string} [options.orphanSpId] - si défini, affiche la mention orphelin (rouge)
 * @param {boolean} [options.spArchived] - si true, affiche la mention "SP archivé" (atténué)
 * @returns {HTMLElement}
 */
function renderDocInlineRow(doc, absFile, options = {}) {
  const row = document.createElement('div');
  row.className = 'doc-inline-row';

  const titleRow = document.createElement('div');
  titleRow.className = 'doc-inline-title-row';

  const typeBadge = document.createElement('span');
  typeBadge.className = `doc-type-badge doc-type-${doc.type}`;
  typeBadge.textContent = DOC_TYPE_LABELS[doc.type] || (doc.type || '').toUpperCase();
  titleRow.appendChild(typeBadge);

  const titleEl = document.createElement('span');
  titleEl.className = 'doc-inline-title';
  titleEl.textContent = doc.title || '(sans titre)';
  titleRow.appendChild(titleEl);

  const statusBadge = document.createElement('span');
  statusBadge.className = `doc-status-badge doc-status-${doc.status}`;
  statusBadge.textContent = DOC_STATUS_LABELS[doc.status] || doc.status;
  titleRow.appendChild(statusBadge);

  const tmLink = document.createElement('a');
  tmLink.href = `txmt://open?url=file://${encodeURI(absFile)}`;
  tmLink.className = 'doc-inline-link';
  tmLink.title = 'Ouvrir dans TextMate';
  tmLink.textContent = '↗ TextMate';
  titleRow.appendChild(tmLink);

  const finderBtn = document.createElement('button');
  finderBtn.className = 'doc-inline-finder';
  finderBtn.title = 'Révéler dans le Finder';
  finderBtn.textContent = '📁 Finder';
  finderBtn.addEventListener('click', e => {
    e.stopPropagation();
    openFile(doc.file)
      .then(() => toast('Finder ouvert.'))
      .catch(err => toast(err.message, 'error'));
  });
  titleRow.appendChild(finderBtn);

  row.appendChild(titleRow);

  if (options.orphanSpId) {
    const spLine = document.createElement('div');
    spLine.className = 'doc-inline-sp';
    const orphan = document.createElement('span');
    orphan.className = 'orphan';
    orphan.textContent = `SP : ${options.orphanSpId} (orphelin)`;
    spLine.appendChild(orphan);
    row.appendChild(spLine);
  } else if (options.spArchived) {
    const spLine = document.createElement('div');
    spLine.className = 'doc-inline-sp';
    const archived = document.createElement('span');
    archived.className = 'sp-archived';
    archived.textContent = 'SP archivé';
    spLine.appendChild(archived);
    row.appendChild(spLine);
  }

  return row;
}

/**
 * Crée le bloc dépliable "Docs" au niveau projet.
 * Vue Projets : inclut sans-SP + orphelins. Exclut SP actif et SP archivé.
 * Vue Archives : inclut sans-SP + orphelins + SP archivé (avec classe sp-archived).
 * @param {Object} proj - projet (actif ou archivé)
 * @param {boolean} [isArchive=false]
 * @returns {HTMLElement|null} - null si aucun doc de niveau projet
 */
function renderProjectDocsBlock(proj, isArchive = false) {
  const allDocs = (proj.docs || []).filter(d => d && typeof d === 'object');
  if (allDocs.length === 0) return null;

  // SP actifs du projet (vide en Vue Archives — tous archivés)
  const activeSpIds = isArchive
    ? new Set()
    : new Set((proj.subprojects || []).map(s => s.id));

  // SP archivés du projet
  const archProj = _archivesState.projects.find(p => p.id === proj.id);
  const archivedSpIds = new Set((archProj?.subprojects || []).map(s => s.id));

  const projectDocs = allDocs
    .filter(d => {
      if (!d.subproject) return true;                          // pas de SP → niveau projet
      if (activeSpIds.has(d.subproject)) return false;         // SP actif → affiché dans le SP
      if (archivedSpIds.has(d.subproject)) return isArchive;   // SP archivé → Archives seulement
      return true;                                             // vrai orphelin → niveau projet
    })
    .map(d => ({
      ...d,
      _spArchived: !!d.subproject && archivedSpIds.has(d.subproject),
    }));

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
    const isOrphan = !!doc.subproject && !doc._spArchived;
    list.appendChild(renderDocInlineRow(doc, absFile, {
      ...(isOrphan        ? { orphanSpId: doc.subproject } : {}),
      ...(doc._spArchived ? { spArchived: true }           : {}),
    }));
  });

  toggle.addEventListener('click', e => {
    e.stopPropagation();
    const collapsed = list.classList.toggle('collapsed');
    toggle.innerHTML = `${collapsed ? '▶' : '▼'} 📄 Docs (${projectDocs.length})`;
  });

  return block;
}

// ── Project card ───────────────────────────────────────────────────────────────

function renderProject(proj) {
  const sps = (proj.subprojects || []).filter(shouldShow);
  const countable = (proj.subprojects || []).filter(s => s.status !== 'récurrent');
  const total = countable.length;
  const done = countable.filter(s => s.status === 'done').length;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  const card = document.createElement('div');
  card.className = 'project-card';
  card.dataset.projectId = proj.id;
  if (_openProjects.has(proj.id)) card.classList.add('open');

  // Header
  const hdr = document.createElement('div');
  hdr.className = 'project-header';
  const alias = proj.alias || '';
  hdr.innerHTML = `
    <span class="project-toggle">▶</span>
    <span class="project-name">${esc(proj.name)}</span>
    ${alias ? `<span class="proj-alias">${esc(alias)}</span>` : ''}
    <span class="project-stack">${esc(proj.stack || '')}</span>
    <div class="project-progress">
      <div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>
      <span>${done}/${total}</span>
    </div>
    <div class="project-actions">
      <button class="icon-btn btn-open-folder" title="Ouvrir le dossier">📁</button>
      <button class="icon-btn btn-add-sp" title="Nouveau sous-projet">＋</button>
      <button class="icon-btn btn-rename-alias" title="Renommer l'alias">✎</button>
      <button class="icon-btn btn-archive-proj" title="Archiver le projet">🗃</button>
      <button class="icon-btn icon-btn-danger btn-del-proj" title="Supprimer le projet">🗑</button>
    </div>
  `;
  card.appendChild(hdr);

  hdr.querySelector('.btn-open-folder').addEventListener('click', e => {
    e.stopPropagation();
    openFolder(proj.id).then(() => toast('Dossier ouvert.')).catch(err => toast(err.message, 'error'));
  });

  hdr.querySelector('.btn-add-sp').addEventListener('click', e => {
    e.stopPropagation();
    openAddSpModal(proj.id);
  });

  hdr.querySelector('.btn-rename-alias').addEventListener('click', e => {
    e.stopPropagation();
    openRenameAliasModal(proj);
  });

  hdr.querySelector('.btn-archive-proj').addEventListener('click', e => {
    e.stopPropagation();
    openConfirm(
      'Archiver le projet ?',
      `"${proj.name}" et tous ses sous-projets seront archivés et consultables dans l'onglet Archives.`,
      () => {
        archiveProject(proj.id)
          .then(() => {
            // Mise à jour de _archivesState : merge ou ajout
            const archProj = _archivesState.projects.find(p => p.id === proj.id);
            if (archProj) {
              archProj.subprojects = (archProj.subprojects || []).concat(proj.subprojects || []);
            } else {
              _archivesState.projects.push(JSON.parse(JSON.stringify(proj)));
            }
            _state.projects = _state.projects.filter(p => p.id !== proj.id);
            toast(`Projet "${proj.name}" archivé.`);
            renderAll();
          })
          .catch(err => toast(err.message, 'error'));
      },
      'Archiver'
    );
  });

  hdr.querySelector('.btn-del-proj').addEventListener('click', e => {
    e.stopPropagation();
    openConfirm(
      'Supprimer le projet ?',
      `"${proj.name}" et tous ses sous-projets seront définitivement supprimés.`,
      () => {
        removeProject(proj.id)
          .then(() => {
            _state.projects = _state.projects.filter(p => p.id !== proj.id);
            toast(`Projet "${proj.name}" supprimé.`);
            renderAll();
          })
          .catch(err => toast(err.message, 'error'));
      }
    );
  });

  hdr.addEventListener('click', () => {
    const isOpen = card.classList.toggle('open');
    if (isOpen) _openProjects.add(proj.id);
    else _openProjects.delete(proj.id);
  });

  // Subprojects list
  const list = document.createElement('div');
  list.className = 'subprojects-list';

  if (sps.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = _filter === 'all' ? 'Aucun sous-projet.' : 'Aucun sous-projet correspondant au filtre.';
    list.appendChild(empty);
  } else {
    sps.forEach(sp => list.appendChild(renderSubproject(proj.id, sp)));
  }

  card.appendChild(list);

  const docsBlock = renderProjectDocsBlock(proj, false);
  if (docsBlock) card.appendChild(docsBlock);

  return card;
}

// ── Subproject row ─────────────────────────────────────────────────────────────

function renderSubproject(projectId, sp) {
  const row = document.createElement('div');
  row.className = 'subproject-row';
  row.dataset.spId = sp.id;

  const expandBtn = document.createElement('button');
  expandBtn.className = 'sp-expand';
  expandBtn.textContent = '▶';
  row.appendChild(expandBtn);

  const main = document.createElement('div');
  main.className = 'sp-main';

  // Title row
  const titleRow = document.createElement('div');
  titleRow.className = 'sp-title-row';

  const nameEl = document.createElement('span');
  nameEl.className = 'sp-name';
  nameEl.textContent = sp.name;
  titleRow.appendChild(nameEl);

  const renameBtn = document.createElement('button');
  renameBtn.className = 'icon-btn';
  renameBtn.title = 'Renommer ce sous-projet';
  renameBtn.textContent = '✎';
  renameBtn.style.cssText = 'font-size:11px;opacity:0;transition:opacity 0.15s;';
  renameBtn.addEventListener('click', e => {
    e.stopPropagation();
    startInlineEdit(nameEl, sp.name, newName => {
      sp.name = newName;
      nameEl.textContent = newName;
      saveSubproject({ projectId, subprojectId: sp.id, name: newName })
        .then(() => toast('Sous-projet renommé.'))
        .catch(err => toast(err.message, 'error'));
    });
  });
  titleRow.appendChild(renameBtn);

  const archBtn = document.createElement('button');
  archBtn.className = 'icon-btn';
  archBtn.title = 'Archiver ce sous-projet';
  archBtn.textContent = '🗃';
  archBtn.className = 'icon-btn';
  archBtn.style.cssText = 'font-size:11px;opacity:0;transition:opacity 0.15s;';
  archBtn.addEventListener('click', e => {
    e.stopPropagation();
    openConfirm(
      'Archiver le sous-projet ?',
      `"${sp.name}" sera archivé et consultable dans l'onglet Archives.`,
      () => {
        archiveSubproject(projectId, sp.id)
          .then(res => {
            const proj = _state.projects.find(p => p.id === projectId);
            if (!proj) return;
            // Maj _archivesState : merge ou créer projet shell
            let archProj = _archivesState.projects.find(p => p.id === projectId);
            if (!archProj) {
              archProj = {
                id: proj.id, name: proj.name, alias: proj.alias || '',
                desc: proj.desc || '', stack: proj.stack || '',
                category: proj.category || 'active', folder: proj.folder || '',
                docs: [], subprojects: [],
              };
              _archivesState.projects.push(archProj);
            }
            archProj.subprojects = archProj.subprojects || [];
            archProj.subprojects.push(JSON.parse(JSON.stringify(sp)));
            proj.subprojects = proj.subprojects.filter(s => s.id !== sp.id);
            toast(`"${sp.name}" archivé.`);
            renderAll();
            // Seconde confirmation si projet vide
            if (res && res.projectEmpty) {
              openConfirm(
                'Archiver aussi le projet ?',
                `Le projet "${proj.name}" n'a plus de sous-projets. L'archiver aussi ?`,
                () => {
                  archiveProject(projectId)
                    .then(() => {
                      _state.projects = _state.projects.filter(p => p.id !== projectId);
                      toast(`Projet "${proj.name}" archivé.`);
                      renderAll();
                    })
                    .catch(err => toast(err.message, 'error'));
                },
                'Archiver'
              );
            }
          })
          .catch(err => toast(err.message, 'error'));
      },
      'Archiver'
    );
  });
  titleRow.appendChild(archBtn);

  const delBtn = document.createElement('button');
  delBtn.className = 'icon-btn';
  delBtn.title = 'Supprimer ce sous-projet';
  delBtn.textContent = '🗑';
  delBtn.className = 'icon-btn icon-btn-danger';
  delBtn.style.cssText = 'font-size:11px;opacity:0;transition:opacity 0.15s;';
  delBtn.addEventListener('click', e => {
    e.stopPropagation();
    openConfirm(
      'Supprimer le sous-projet ?',
      `"${sp.name}" sera définitivement supprimé.`,
      () => {
        removeSubproject({ projectId, subprojectId: sp.id })
          .then(() => {
            const proj = _state.projects.find(p => p.id === projectId);
            if (proj) proj.subprojects = proj.subprojects.filter(s => s.id !== sp.id);
            toast(`"${sp.name}" supprimé.`);
            renderAll();
          })
          .catch(err => toast(err.message, 'error'));
      }
    );
  });
  titleRow.appendChild(delBtn);

  row.addEventListener('mouseenter', () => { renameBtn.style.opacity = '1'; archBtn.style.opacity = '1'; delBtn.style.opacity = '1'; });
  row.addEventListener('mouseleave', () => { renameBtn.style.opacity = '0'; archBtn.style.opacity = '0'; delBtn.style.opacity = '0'; });

  const badge = makeBadge(sp.status);
  badge.addEventListener('click', e => {
    e.stopPropagation();
    openStatusMenu(badge, projectId, sp.id, sp.status, SP_STATUSES, newStatus => {
      sp.status = newStatus;
      badge.className = `status-badge status-${newStatus}`;
      badge.textContent = STATUS_LABELS[newStatus];
      saveSubproject({ projectId, subprojectId: sp.id, status: newStatus })
        .then(() => { toast('Statut mis à jour.'); updateStats(); renderAll(); })
        .catch(err => toast(err.message, 'error'));
    });
  });
  titleRow.appendChild(badge);

  if (sp.qualif) {
    const q = document.createElement('span');
    q.className = 'sp-qualif';
    q.textContent = sp.qualif;
    titleRow.appendChild(q);
  }

  main.appendChild(titleRow);

  if (sp.titre) {
    const titre = document.createElement('div');
    titre.className = 'sp-titre';
    titre.textContent = sp.titre;
    main.appendChild(titre);
  }

  // Meta row
  const meta = document.createElement('div');
  meta.className = 'sp-meta';

  if (sp.charge !== undefined || sp.raf !== undefined) {
    const charges = document.createElement('span');
    charges.className = 'sp-charges';
    charges.title = 'Cliquer pour modifier charge / RAF';
    const renderCharges = () => {
      const charge = sp.charge ?? '?';
      const raf = sp.raf ?? '?';
      charges.innerHTML = `${charge}h / <span class="raf">${raf}h</span>`;
    };
    renderCharges();
    charges.addEventListener('click', () => startInlineEditCharges(charges, sp, projectId, renderCharges));
    meta.appendChild(charges);
  }

  if (sp.target) {
    const targetEl = document.createElement('span');
    targetEl.className = 'sp-target';
    targetEl.textContent = sp.target;
    targetEl.title = 'Cliquer pour modifier';
    targetEl.addEventListener('click', () => startInlineEdit(targetEl, sp.target, newVal => {
      sp.target = newVal;
      targetEl.textContent = newVal;
      saveSubproject({ projectId, subprojectId: sp.id, target: newVal })
        .then(() => toast('Date mise à jour.'))
        .catch(err => toast(err.message, 'error'));
    }));
    meta.appendChild(targetEl);
  }

  main.appendChild(meta);

  // Steps panel
  const stepsPanel = document.createElement('div');
  stepsPanel.className = 'steps-panel';
  (sp.steps || []).forEach(step => {
    stepsPanel.appendChild(renderStep(projectId, sp, step));
  });

  // Docs du SP (lecture seule, inline dans le panneau détail)
  const projDocs = _state.projects.find(p => p.id === projectId)?.docs || [];
  const spDocs = projDocs.filter(d => d && typeof d === 'object' && d.subproject === sp.id);
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

  main.appendChild(stepsPanel);
  row.appendChild(main);

  expandBtn.addEventListener('click', () => {
    const open = stepsPanel.classList.toggle('open');
    expandBtn.textContent = open ? '▼' : '▶';
  });

  return row;
}

// ── Step row ───────────────────────────────────────────────────────────────────

function renderStep(projectId, sp, step) {
  const row = document.createElement('div');
  row.className = 'step-row';

  const badge = document.createElement('span');
  badge.className = `step-status-badge status-${step.status}`;
  badge.textContent = STATUS_LABELS[step.status] || step.status;
  badge.addEventListener('click', () => {
    openStatusMenu(badge, projectId, sp.id, step.status, STEP_STATUSES, newStatus => {
      step.status = newStatus;
      badge.className = `step-status-badge status-${newStatus}`;
      badge.textContent = STATUS_LABELS[newStatus];
      nameEl.className = `step-name${newStatus === 'done' ? ' done' : ''}`;
      saveSubproject({ projectId, subprojectId: sp.id, steps: [{ name: step.name, status: newStatus }] })
        .then(() => toast('Étape mise à jour.'))
        .catch(err => toast(err.message, 'error'));
    });
  });

  const nameEl = document.createElement('span');
  nameEl.className = `step-name${step.status === 'done' ? ' done' : ''}`;
  nameEl.textContent = step.name;

  const charges = document.createElement('span');
  charges.className = 'step-charges';
  if (step.status !== 'na') {
    charges.textContent = `${step.charge ?? 0}h / ${step.raf ?? 0}h`;
  }

  row.appendChild(badge);
  row.appendChild(nameEl);
  row.appendChild(charges);
  return row;
}

// ── Status dropdown ────────────────────────────────────────────────────────────

function openStatusMenu(anchor, projectId, spId, current, options, onSelect) {
  const menu = document.getElementById('status-menu');

  if (_statusMenuTarget === anchor && menu.classList.contains('open')) {
    closeStatusMenu();
    return;
  }

  closeStatusMenu();
  _statusMenuTarget = anchor;

  menu.innerHTML = '';
  options.forEach(s => {
    const item = document.createElement('div');
    item.className = 'status-menu-item';
    item.style.color = `var(--${s === 'blocked' ? 'blocked' : s === 'na' ? 'na' : s})`;
    item.textContent = STATUS_LABELS[s];
    if (s === current) item.style.fontWeight = '700';
    item.addEventListener('click', e => {
      e.stopPropagation();
      closeStatusMenu();
      onSelect(s);
    });
    menu.appendChild(item);
  });

  const rect = anchor.getBoundingClientRect();
  menu.style.top = `${rect.bottom + window.scrollY + 4}px`;
  menu.style.left = `${rect.left + window.scrollX}px`;
  menu.classList.add('open');
}

function closeStatusMenu() {
  document.getElementById('status-menu').classList.remove('open');
  _statusMenuTarget = null;
}

function openConfirm(title, msg, onConfirm, okLabel = 'Supprimer') {
  document.getElementById('modal-confirm-title').textContent = title;
  document.getElementById('modal-confirm-msg').textContent = msg;
  document.getElementById('modal-confirm').classList.add('open');
  const ok = document.getElementById('modal-confirm-ok');
  const cancel = document.getElementById('modal-confirm-cancel');
  const close = () => document.getElementById('modal-confirm').classList.remove('open');
  const okClone = ok.cloneNode(true);
  okClone.textContent = okLabel;
  ok.replaceWith(okClone);
  okClone.addEventListener('click', () => { close(); onConfirm(); }, { once: true });
  cancel.onclick = close;
}

// ── Inline edit ────────────────────────────────────────────────────────────────

function startInlineEdit(el, current, onSave) {
  const input = document.createElement('input');
  input.className = 'inline-edit';
  input.value = current;
  const w = el.offsetWidth || 100;
  input.style.width = `${Math.max(w, 100)}px`;

  el.replaceWith(input);
  input.focus();
  input.select();

  const commit = () => {
    const val = input.value.trim();
    input.replaceWith(el);
    if (val && val !== current) onSave(val);
  };

  input.addEventListener('blur', commit);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); commit(); }
    if (e.key === 'Escape') { input.replaceWith(el); }
  });
}

// Édition inline charge/raf (sauvegarde locale via /api/save-subproject).
function startInlineEditCharges(el, sp, projectId, renderCharges) {
  const initialCharge = sp.charge ?? 0;
  const initialRaf = sp.raf ?? 0;

  const wrapper = document.createElement('span');
  wrapper.className = 'sp-charges-edit';

  const inCharge = document.createElement('input');
  inCharge.className = 'inline-edit';
  inCharge.value = String(initialCharge);
  inCharge.style.width = '50px';
  inCharge.title = 'Charge (h)';

  const sep = document.createElement('span');
  sep.textContent = ' h / ';

  const inRaf = document.createElement('input');
  inRaf.className = 'inline-edit';
  inRaf.value = String(initialRaf);
  inRaf.style.width = '50px';
  inRaf.title = 'RAF (h)';

  const suffix = document.createElement('span');
  suffix.textContent = ' h';

  wrapper.append(inCharge, sep, inRaf, suffix);
  el.replaceWith(wrapper);
  inCharge.focus();
  inCharge.select();

  let committed = false;
  const parse = v => {
    const s = String(v).trim().replace(',', '.');
    if (s === '') return null;
    const n = parseFloat(s);
    if (Number.isNaN(n) || n < 0) return NaN;
    return n;
  };

  const cancel = () => {
    if (committed) return;
    committed = true;
    wrapper.replaceWith(el);
  };

  const commit = async () => {
    if (committed) return;
    const newCharge = parse(inCharge.value);
    const newRaf = parse(inRaf.value);
    if (Number.isNaN(newCharge) || Number.isNaN(newRaf)) {
      // Saisie invalide (non numérique ou négative) — feedback inline, pas de sauvegarde.
      inCharge.style.borderColor = Number.isNaN(newCharge) ? 'var(--blocked)' : '';
      inRaf.style.borderColor = Number.isNaN(newRaf) ? 'var(--blocked)' : '';
      toast('Valeur invalide : nombre positif attendu (virgule ou point).', 'error');
      return;
    }
    committed = true;
    const charge = newCharge ?? initialCharge;
    const raf = newRaf ?? initialRaf;

    // Restitue l'affichage avant les appels réseau pour ne pas bloquer l'UI.
    sp.charge = charge;
    sp.raf = raf;
    wrapper.replaceWith(el);
    renderCharges();

    try {
      await saveSubproject({ projectId, subprojectId: sp.id, charge, raf });
    } catch (err) {
      toast(err.message || 'Erreur sauvegarde locale', 'error');
      return;
    }

    fetchStateAndRefresh();
  };

  let blurTimer = null;
  const onBlur = () => {
    // blur peut être déclenché par le passage d'un input à l'autre — laisser une frame.
    clearTimeout(blurTimer);
    blurTimer = setTimeout(() => {
      if (document.activeElement !== inCharge && document.activeElement !== inRaf) {
        commit();
      }
    }, 50);
  };
  inCharge.addEventListener('blur', onBlur);
  inRaf.addEventListener('blur', onBlur);

  const onKey = e => {
    if (e.key === 'Enter') { e.preventDefault(); commit(); }
    if (e.key === 'Escape') { e.preventDefault(); cancel(); }
  };
  inCharge.addEventListener('keydown', onKey);
  inRaf.addEventListener('keydown', onKey);
}

// ── Modals ─────────────────────────────────────────────────────────────────────

function openRenameAliasModal(proj) {
  document.getElementById('modal-rename-alias-desc').textContent = `Projet : ${proj.name}`;
  const input = document.getElementById('modal-rename-alias-input');
  input.value = proj.alias || proj.name;
  document.getElementById('modal-rename-alias').classList.add('open');
  input.focus();
  input.select();

  const saveBtn = document.getElementById('modal-rename-alias-save');
  const clone = saveBtn.cloneNode(true);
  saveBtn.replaceWith(clone);
  clone.addEventListener('click', () => {
    const newAlias = input.value.trim();
    if (!newAlias) return;
    document.getElementById('modal-rename-alias').classList.remove('open');
    proj.alias = newAlias;
    saveProject({ projectId: proj.id, alias: newAlias })
      .then(() => { toast('Alias mis à jour.'); renderAll(); })
      .catch(err => toast(err.message, 'error'));
  }, { once: true });
  document.getElementById('modal-rename-alias-cancel').onclick = () =>
    document.getElementById('modal-rename-alias').classList.remove('open');
}

function openAddSpModal(projectId) {
  document.getElementById('modal-sp-project-id').value = projectId;
  document.getElementById('modal-sp-name').value = '';
  document.getElementById('modal-sp-titre').value = '';
  document.getElementById('modal-sp-qualif').value = '';
  document.getElementById('modal-sp-status').value = 'todo';
  document.getElementById('modal-add-sp').classList.add('open');
  document.getElementById('modal-sp-name').focus();
}

function closeAddSpModal() {
  document.getElementById('modal-add-sp').classList.remove('open');
}

function openAddProjModal() {
  document.getElementById('modal-proj-name').value = '';
  document.getElementById('modal-proj-alias').value = '';
  document.getElementById('modal-proj-desc').value = '';
  document.getElementById('modal-proj-stack').value = '';
  document.getElementById('modal-add-proj').classList.add('open');
  document.getElementById('modal-proj-name').focus();
}

function closeAddProjModal() {
  document.getElementById('modal-add-proj').classList.remove('open');
}

// ── Render all ─────────────────────────────────────────────────────────────────

export function renderAll() {
  updateStats();
  updateDocsCountBadge();
  updateArchivesCountBadge();

  if (_view === 'docs') {
    renderDocsView();
    return;
  }
  if (_view === 'archives') {
    renderArchivesView();
    return;
  }

  const container = document.getElementById('projects-container');
  container.innerHTML = '';

  const visible = _state.projects.filter(p =>
    _filter === 'all' || (p.subprojects || []).some(shouldShow)
  );

  visible.forEach(p => container.appendChild(renderProject(p)));
}

// ── Docs view ──────────────────────────────────────────────────────────────────

function getProjectDocs(proj) {
  return (proj.docs || []).filter(d => d && typeof d === 'object');
}

function getTotalDocsCount() {
  return _state.projects.reduce((acc, p) => acc + getProjectDocs(p).length, 0);
}

function updateDocsCountBadge() {
  const el = document.getElementById('docs-count-badge');
  if (!el) return;
  const n = getTotalDocsCount();
  el.textContent = n > 0 ? `(${n})` : '';
}

function docMatchesFilters(doc) {
  if (_docFilterTypes.size > 0 && !_docFilterTypes.has(doc.type)) return false;
  if (!_docFilterStatuses.has(doc.status)) return false;
  return true;
}

function sortDocs(docs) {
  // Date décroissante, sans date en queue (§3.4 SPEC). Tri stable.
  return docs
    .map((d, i) => ({ d, i }))
    .sort((a, b) => {
      const da = a.d.date || '';
      const db = b.d.date || '';
      if (!da && !db) return a.i - b.i;
      if (!da) return 1;
      if (!db) return -1;
      if (da > db) return -1;
      if (da < db) return 1;
      return a.i - b.i;
    })
    .map(x => x.d);
}

function renderDocsView() {
  const container = document.getElementById('docs-container');
  container.innerHTML = '';

  _state.projects.forEach(proj => {
    const allDocs = getProjectDocs(proj);
    const filtered = sortDocs(allDocs.filter(docMatchesFilters));

    // Projet "sans docs" si aucun ne passe les filtres
    const isEmpty = filtered.length === 0;
    if (isEmpty && !_showEmptyProjects) return;

    const card = document.createElement('div');
    card.className = 'project-card open';
    card.dataset.projectId = proj.id;

    const hdr = document.createElement('div');
    hdr.className = 'project-header';
    const alias = proj.alias || '';
    hdr.innerHTML = `
      <span class="project-toggle">▶</span>
      <span class="project-name">${esc(proj.name)}</span>
      ${alias ? `<span class="proj-alias">${esc(alias)}</span>` : ''}
      <span class="project-stack">${allDocs.length} doc${allDocs.length > 1 ? 's' : ''}</span>
      <div style="flex:1"></div>
      <div class="project-actions">
        <button class="icon-btn btn-add-doc-here" title="Ajouter un doc à ce projet">＋</button>
      </div>
    `;
    card.appendChild(hdr);

    hdr.querySelector('.btn-add-doc-here').addEventListener('click', e => {
      e.stopPropagation();
      openDocModal('add', { projectId: proj.id });
    });
    hdr.addEventListener('click', () => {
      card.classList.toggle('open');
    });

    const list = document.createElement('div');
    list.className = 'subprojects-list';

    if (filtered.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'doc-empty';
      empty.textContent = allDocs.length === 0
        ? 'Aucun doc enregistré pour ce projet.'
        : 'Aucun doc ne correspond aux filtres actifs.';
      list.appendChild(empty);
    } else {
      filtered.forEach(doc => list.appendChild(renderDocCard(proj, doc)));
    }

    card.appendChild(list);
    container.appendChild(card);
  });
}

function renderDocCard(proj, doc) {
  const card = document.createElement('div');
  card.className = `doc-card${doc.status === 'archived' ? ' archived' : ''}`;
  card.dataset.docId = doc.id;

  // Title row : [TYPE] Titre ... [STATUS] DATE
  const titleRow = document.createElement('div');
  titleRow.className = 'doc-title-row';

  const typeBadge = document.createElement('span');
  typeBadge.className = `doc-type-badge doc-type-${doc.type}`;
  typeBadge.textContent = DOC_TYPE_LABELS[doc.type] || (doc.type || '').toUpperCase();
  titleRow.appendChild(typeBadge);

  const title = document.createElement('span');
  title.className = 'doc-title';
  title.textContent = doc.title || '(sans titre)';
  titleRow.appendChild(title);

  const statusBadge = document.createElement('span');
  statusBadge.className = `doc-status-badge doc-status-${doc.status}`;
  statusBadge.textContent = DOC_STATUS_LABELS[doc.status] || doc.status;
  titleRow.appendChild(statusBadge);

  if (doc.date) {
    const date = document.createElement('span');
    date.className = 'doc-date';
    date.textContent = doc.date;
    titleRow.appendChild(date);
  }

  card.appendChild(titleRow);

  if (doc.desc) {
    const desc = document.createElement('div');
    desc.className = 'doc-desc';
    desc.textContent = doc.desc;
    card.appendChild(desc);
  }

  // SP associé : lien → panneau détail SP (P9)
  if (doc.subproject) {
    const sp = (proj.subprojects || []).find(s => s.id === doc.subproject);
    const spLink = document.createElement('a');
    spLink.className = 'doc-sp-link';
    if (sp) {
      spLink.textContent = `SP : ${sp.name}`;
      spLink.addEventListener('click', e => {
        e.preventDefault();
        switchView('projects');
        // Bascule + ouvre le panneau détail (steps) du SP ciblé
        setTimeout(() => focusSubproject(proj.id, sp.id), 50);
      });
    } else {
      spLink.classList.add('orphan');
      spLink.textContent = `SP : ${doc.subproject} (introuvable)`;
    }
    card.appendChild(spLink);
  }

  // Actions
  const actions = document.createElement('div');
  actions.className = 'doc-actions';

  const gitRoot = _state.git_root || '';
  const absFile = gitRoot ? `${gitRoot}/${doc.file}` : doc.file;
  const tmLink = document.createElement('a');
  tmLink.href = `txmt://open?url=file://${encodeURI(absFile)}`;
  tmLink.title = 'Ouvrir dans TextMate';
  tmLink.textContent = '↗ TextMate';
  actions.appendChild(tmLink);

  const finderBtn = document.createElement('button');
  finderBtn.textContent = '📁 Finder';
  finderBtn.title = 'Révéler dans le Finder';
  finderBtn.addEventListener('click', () => {
    openFile(doc.file)
      .then(() => toast('Finder ouvert.'))
      .catch(err => toast(err.message, 'error'));
  });
  actions.appendChild(finderBtn);

  const editBtn = document.createElement('button');
  editBtn.textContent = '✎';
  editBtn.title = 'Modifier';
  editBtn.addEventListener('click', () => openDocModal('edit', { projectId: proj.id, docId: doc.id }));
  actions.appendChild(editBtn);

  const delBtn = document.createElement('button');
  delBtn.textContent = '🗑';
  delBtn.title = 'Supprimer';
  delBtn.className = 'icon-btn icon-btn-danger';
  delBtn.addEventListener('click', () => {
    openConfirm(
      'Supprimer le document ?',
      `"${doc.title}" sera retiré du catalogue. Le fichier .md sur disque n'est pas supprimé.`,
      () => {
        removeDoc(proj.id, doc.id)
          .then(() => {
            const p = _state.projects.find(x => x.id === proj.id);
            if (p) p.docs = (p.docs || []).filter(d => !(d && d.id === doc.id));
            toast('Document supprimé.');
            renderAll();
          })
          .catch(err => toast(err.message, 'error'));
      }
    );
  });
  actions.appendChild(delBtn);

  card.appendChild(actions);
  return card;
}

// ── View switch + SP focus ─────────────────────────────────────────────────────

function switchView(view) {
  _view = view;
  document.querySelectorAll('.view-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.view === view);
  });
  const isProj = view === 'projects';
  const isDocs = view === 'docs';
  const isArch = view === 'archives';
  document.getElementById('stats-bar').style.display = isProj ? '' : 'none';
  document.getElementById('filters').style.display = isProj ? '' : 'none';
  document.getElementById('add-project-btn').style.display = isProj ? 'flex' : 'none';
  document.getElementById('projects-container').style.display = isProj ? 'block' : 'none';
  document.getElementById('docs-filters').style.display = isDocs ? 'flex' : 'none';
  document.getElementById('docs-actions').style.display = isDocs ? 'flex' : 'none';
  document.getElementById('docs-container').style.display = isDocs ? 'block' : 'none';
  const archContainer = document.getElementById('archives-container');
  if (archContainer) archContainer.style.display = isArch ? 'block' : 'none';

  if (isArch && !_archivesLoaded) {
    fetchArchives()
      .then(a => {
        _archivesState = a || { projects: [] };
        _archivesLoaded = true;
        renderAll();
      })
      .catch(err => toast(err.message, 'error'));
    return;
  }
  renderAll();
}

// ── Archives view ──────────────────────────────────────────────────────────────

function getTotalArchivedSpCount() {
  return _archivesState.projects.reduce(
    (acc, p) => acc + ((p.subprojects || []).length), 0
  );
}

function updateArchivesCountBadge() {
  const el = document.getElementById('archives-count-badge');
  if (!el) return;
  const n = getTotalArchivedSpCount();
  el.textContent = n > 0 ? `(${n})` : '';
}

function renderArchivesView() {
  const container = document.getElementById('archives-container');
  if (!container) return;
  container.innerHTML = '';

  if (!_archivesState.projects.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.style.cssText = 'padding:24px;color:var(--muted);text-align:center;';
    empty.textContent = 'Aucune archive.';
    container.appendChild(empty);
    return;
  }

  _archivesState.projects.forEach(proj => {
    container.appendChild(renderArchivedProject(proj));
  });
}

function renderArchivedProject(proj) {
  const sps = proj.subprojects || [];
  const card = document.createElement('div');
  card.className = 'project-card';
  card.dataset.projectId = proj.id;

  const hdr = document.createElement('div');
  hdr.className = 'project-header';
  const alias = proj.alias || '';
  hdr.innerHTML = `
    <span class="project-toggle">▶</span>
    <span class="project-name">${esc(proj.name)}</span>
    ${alias ? `<span class="proj-alias">${esc(alias)}</span>` : ''}
    <span class="project-stack">${sps.length} SP archivé${sps.length > 1 ? 's' : ''}</span>
    <div style="flex:1"></div>
    <div class="project-actions">
      <button class="icon-btn btn-restore-proj" title="Restaurer le projet">↩</button>
      <button class="icon-btn icon-btn-danger btn-delete-archive-proj" title="Supprimer définitivement">🗑</button>
    </div>
  `;
  card.appendChild(hdr);

  hdr.querySelector('.btn-restore-proj').addEventListener('click', e => {
    e.stopPropagation();
    openConfirm(
      'Restaurer le projet ?',
      `"${proj.name}" et tous ses sous-projets archivés seront restaurés.`,
      () => {
        restoreProject(proj.id)
          .then(() => {
            _archivesState.projects = _archivesState.projects.filter(p => p.id !== proj.id);
            _state.projects.push(JSON.parse(JSON.stringify(proj)));
            toast('Projet restauré.');
            renderAll();
          })
          .catch(err => toast(err.message, 'error'));
      },
      'Restaurer'
    );
  });

  hdr.querySelector('.btn-delete-archive-proj').addEventListener('click', e => {
    e.stopPropagation();
    openConfirm(
      'Suppression définitive',
      `"${proj.name}" et ses sous-projets archivés seront définitivement supprimés. Cette action est irréversible.`,
      () => {
        deleteArchiveProject(proj.id)
          .then(() => {
            _archivesState.projects = _archivesState.projects.filter(p => p.id !== proj.id);
            toast('Suppression définitive effectuée.');
            renderAll();
          })
          .catch(err => toast(err.message, 'error'));
      }
    );
  });

  hdr.addEventListener('click', () => { card.classList.toggle('open'); });

  const list = document.createElement('div');
  list.className = 'subprojects-list';
  if (sps.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = 'Aucun sous-projet archivé.';
    list.appendChild(empty);
  } else {
    sps.forEach(sp => list.appendChild(renderArchivedSubproject(proj.id, sp)));
  }
  card.appendChild(list);

  const docsBlock = renderProjectDocsBlock(proj, true);
  if (docsBlock) card.appendChild(docsBlock);

  return card;
}

function renderArchivedSubproject(projectId, sp) {
  const row = document.createElement('div');
  row.className = 'subproject-row';
  row.dataset.spId = sp.id;

  const main = document.createElement('div');
  main.className = 'sp-main';
  main.style.marginLeft = '12px';

  const titleRow = document.createElement('div');
  titleRow.className = 'sp-title-row';

  const nameEl = document.createElement('span');
  nameEl.className = 'sp-name';
  nameEl.textContent = sp.name;
  titleRow.appendChild(nameEl);

  // Badge de statut — non cliquable
  const badge = makeBadge(sp.status);
  badge.style.cursor = 'default';
  titleRow.appendChild(badge);

  if (sp.qualif) {
    const q = document.createElement('span');
    q.className = 'sp-qualif';
    q.textContent = sp.qualif;
    titleRow.appendChild(q);
  }

  const restoreBtn = document.createElement('button');
  restoreBtn.className = 'icon-btn';
  restoreBtn.title = 'Restaurer';
  restoreBtn.textContent = '↩';
  restoreBtn.style.cssText = 'font-size:11px;opacity:0;transition:opacity 0.15s;';
  restoreBtn.addEventListener('click', e => {
    e.stopPropagation();
    openConfirm(
      'Restaurer le sous-projet ?',
      `"${sp.name}" sera restauré dans le projet.`,
      () => {
        restoreSubproject(projectId, sp.id)
          .then(() => {
            // Maj _archivesState
            const archProj = _archivesState.projects.find(p => p.id === projectId);
            if (archProj) {
              archProj.subprojects = (archProj.subprojects || []).filter(s => s.id !== sp.id);
              if (!archProj.subprojects.length) {
                _archivesState.projects = _archivesState.projects.filter(p => p.id !== projectId);
              }
            }
            // Maj _state : trouver/créer le projet
            let dataProj = _state.projects.find(p => p.id === projectId);
            if (!dataProj && archProj) {
              dataProj = {
                id: archProj.id, name: archProj.name, alias: archProj.alias || '',
                desc: archProj.desc || '', stack: archProj.stack || '',
                category: archProj.category || 'active', folder: archProj.folder || '',
                docs: [], subprojects: [],
              };
              _state.projects.push(dataProj);
            }
            if (dataProj) {
              dataProj.subprojects = dataProj.subprojects || [];
              dataProj.subprojects.push(JSON.parse(JSON.stringify(sp)));
            }
            toast('Sous-projet restauré.');
            renderAll();
          })
          .catch(err => toast(err.message, 'error'));
      },
      'Restaurer'
    );
  });
  titleRow.appendChild(restoreBtn);

  const delBtn = document.createElement('button');
  delBtn.className = 'icon-btn';
  delBtn.title = 'Supprimer définitivement';
  delBtn.textContent = '🗑';
  delBtn.className = 'icon-btn icon-btn-danger';
  delBtn.style.cssText = 'font-size:11px;opacity:0;transition:opacity 0.15s;';
  delBtn.addEventListener('click', e => {
    e.stopPropagation();
    openConfirm(
      'Suppression définitive',
      `"${sp.name}" sera définitivement supprimé des archives. Cette action est irréversible.`,
      () => {
        deleteArchiveSubproject(projectId, sp.id)
          .then(() => {
            const archProj = _archivesState.projects.find(p => p.id === projectId);
            if (archProj) {
              archProj.subprojects = (archProj.subprojects || []).filter(s => s.id !== sp.id);
              if (!archProj.subprojects.length) {
                _archivesState.projects = _archivesState.projects.filter(p => p.id !== projectId);
              }
            }
            toast('Suppression définitive effectuée.');
            renderAll();
          })
          .catch(err => toast(err.message, 'error'));
      }
    );
  });
  titleRow.appendChild(delBtn);

  row.addEventListener('mouseenter', () => { restoreBtn.style.opacity = '1'; delBtn.style.opacity = '1'; });
  row.addEventListener('mouseleave', () => { restoreBtn.style.opacity = '0'; delBtn.style.opacity = '0'; });

  main.appendChild(titleRow);

  if (sp.titre) {
    const titre = document.createElement('div');
    titre.className = 'sp-titre';
    titre.textContent = sp.titre;
    main.appendChild(titre);
  }

  row.appendChild(main);
  return row;
}

function focusSubproject(projectId, spId) {
  _openProjects.add(projectId);
  renderAll();
  const card = document.querySelector(`.project-card[data-project-id="${projectId}"]`);
  if (!card) return;
  card.classList.add('open');
  const row = card.querySelector(`.subproject-row[data-sp-id="${spId}"]`);
  if (!row) return;
  // Ouvre le panneau de détail (steps) du SP
  const panel = row.querySelector('.steps-panel');
  const expandBtn = row.querySelector('.sp-expand');
  if (panel && !panel.classList.contains('open')) {
    panel.classList.add('open');
    if (expandBtn) expandBtn.textContent = '▼';
  }
  row.scrollIntoView({ behavior: 'smooth', block: 'center' });
  row.style.transition = 'background 0.4s';
  row.style.background = 'rgba(59,130,246,.12)';
  setTimeout(() => { row.style.background = ''; }, 1200);
}

// ── Doc filters persistence ────────────────────────────────────────────────────

const LS_KEY = 'planning-v2-docs-filters';

function saveDocFiltersToLS() {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({
      types: Array.from(_docFilterTypes),
      statuses: Array.from(_docFilterStatuses),
      showEmpty: _showEmptyProjects,
    }));
  } catch (e) { /* ignore quota / private mode */ }
}

function loadDocFiltersFromLS() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return;
    const obj = JSON.parse(raw);
    if (Array.isArray(obj.types)) _docFilterTypes = new Set(obj.types);
    if (Array.isArray(obj.statuses)) _docFilterStatuses = new Set(obj.statuses);
    if (typeof obj.showEmpty === 'boolean') _showEmptyProjects = obj.showEmpty;
  } catch (e) { /* ignore */ }
}

// ── Doc modal ──────────────────────────────────────────────────────────────────

function openDocModal(mode, ctx) {
  _docModalMode = mode;
  _docModalCtx = ctx || {};
  const modal = document.getElementById('modal-doc');
  document.getElementById('modal-doc-title').textContent =
    mode === 'edit' ? 'Modifier le document' : 'Nouveau document';

  // Remplit le dropdown projets
  const projSelect = document.getElementById('modal-doc-project');
  projSelect.innerHTML = '';
  _state.projects.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.name;
    projSelect.appendChild(opt);
  });

  let doc = null;
  if (mode === 'edit' && ctx.projectId && ctx.docId) {
    const proj = _state.projects.find(p => p.id === ctx.projectId);
    if (proj) doc = getProjectDocs(proj).find(d => d.id === ctx.docId) || null;
  }

  projSelect.value = ctx.projectId || (_state.projects[0] && _state.projects[0].id) || '';
  projSelect.disabled = (mode === 'edit');

  document.getElementById('modal-doc-file').value = doc ? doc.file : '';
  document.getElementById('modal-doc-title-input').value = doc ? doc.title : '';
  document.getElementById('modal-doc-desc').value = doc ? (doc.desc || '') : '';
  document.getElementById('modal-doc-type').value = doc ? doc.type : 'spec';
  document.getElementById('modal-doc-status').value = doc ? doc.status : 'draft';
  document.getElementById('modal-doc-date').value = doc ? (doc.date || '') : todayISO();
  document.getElementById('modal-doc-id-existing').value = doc ? doc.id : '';

  refreshDocSpDropdown(projSelect.value, doc ? doc.subproject : '');

  // Re-binde le changement de projet pour rafraîchir la liste de SP
  projSelect.onchange = () => refreshDocSpDropdown(projSelect.value, '');

  modal.classList.add('open');
  document.getElementById('modal-doc-title-input').focus();
}

function refreshDocSpDropdown(projectId, selectedSpId) {
  const sel = document.getElementById('modal-doc-sp');
  sel.innerHTML = '<option value="">— aucun —</option>';
  const proj = _state.projects.find(p => p.id === projectId);
  if (!proj) return;
  (proj.subprojects || []).forEach(sp => {
    const opt = document.createElement('option');
    opt.value = sp.id;
    opt.textContent = sp.name;
    if (sp.id === selectedSpId) opt.selected = true;
    sel.appendChild(opt);
  });
}

function closeDocModal() {
  document.getElementById('modal-doc').classList.remove('open');
}

function todayISO() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

async function submitDocModal() {
  const projectId = document.getElementById('modal-doc-project').value;
  const file = document.getElementById('modal-doc-file').value.trim();
  const title = document.getElementById('modal-doc-title-input').value.trim();
  const desc = document.getElementById('modal-doc-desc').value.trim();
  const type = document.getElementById('modal-doc-type').value;
  const status = document.getElementById('modal-doc-status').value;
  const date = document.getElementById('modal-doc-date').value.trim();
  const spId = document.getElementById('modal-doc-sp').value;
  const existingId = document.getElementById('modal-doc-id-existing').value;

  if (!file) { toast('Le chemin du fichier est obligatoire.', 'error'); return; }
  if (!title) { toast('Le titre est obligatoire.', 'error'); return; }

  const payload = { file, title, type, status };
  if (desc) payload.desc = desc;
  if (date) payload.date = date;
  payload.subproject = spId || null;

  try {
    if (_docModalMode === 'edit' && existingId) {
      await saveDoc(projectId, existingId, {
        file, title, desc, type, status, date,
        subproject: spId || null,
      });
      // Mise à jour locale
      const proj = _state.projects.find(p => p.id === projectId);
      const doc = proj && getProjectDocs(proj).find(d => d.id === existingId);
      if (doc) Object.assign(doc, { file, title, desc, type, status, date, subproject: spId || null });
      toast('Document mis à jour.');
    } else {
      const r = await addDoc(projectId, payload);
      const proj = _state.projects.find(p => p.id === projectId);
      if (proj) {
        proj.docs = proj.docs || [];
        proj.docs.push(r.doc);
      }
      toast('Document ajouté.');
    }
    closeDocModal();
    renderAll();
  } catch (err) {
    toast(err.message, 'error');
  }
}

// ── Init ───────────────────────────────────────────────────────────────────────

export function init(state) {
  _state = state;

  // Filters
  document.getElementById('filters').addEventListener('click', e => {
    const btn = e.target.closest('.filter-btn');
    if (!btn || !btn.dataset.filter) return;
    _filter = btn.dataset.filter;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderAll();
    if (_filter !== 'all') {
      document.querySelectorAll('.project-card').forEach(card => {
        card.classList.add('open');
      });
      _state.projects.forEach(p => _openProjects.add(p.id));
    }
  });

  // Tout ouvrir / Tout fermer
  document.getElementById('btn-open-all').addEventListener('click', () => {
    document.querySelectorAll('.project-card').forEach(c => c.classList.add('open'));
    _state.projects.forEach(p => _openProjects.add(p.id));
  });
  document.getElementById('btn-close-all').addEventListener('click', () => {
    document.querySelectorAll('.project-card').forEach(c => c.classList.remove('open'));
    _openProjects.clear();
  });

  // Rename alias modal
  document.getElementById('modal-rename-alias').addEventListener('click', e => {
    if (e.target === e.currentTarget) document.getElementById('modal-rename-alias').classList.remove('open');
  });
  document.getElementById('modal-rename-alias-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('modal-rename-alias-save').click();
    if (e.key === 'Escape') document.getElementById('modal-rename-alias').classList.remove('open');
  });

  // Add project button
  document.getElementById('add-project-btn').addEventListener('click', openAddProjModal);

  // Add subproject modal
  document.getElementById('modal-sp-cancel').addEventListener('click', closeAddSpModal);
  document.getElementById('modal-add-sp').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeAddSpModal();
  });

  document.getElementById('modal-sp-save').addEventListener('click', async () => {
    const projectId = document.getElementById('modal-sp-project-id').value;
    const name = document.getElementById('modal-sp-name').value.trim();
    const titre = document.getElementById('modal-sp-titre').value.trim();
    const qualif = document.getElementById('modal-sp-qualif').value;
    const status = document.getElementById('modal-sp-status').value;

    if (!name) { toast('Le nom est obligatoire.', 'error'); return; }

    try {
      const r = await addSubproject({ projectId, name, titre, qualif, status });
      closeAddSpModal();
      // Ajoute dans l'état local (4 étapes par défaut créées côté serveur)
      const proj = _state.projects.find(p => p.id === projectId);
      if (proj) {
        proj.subprojects = proj.subprojects || [];
        proj.subprojects.push({
          id: r.id, name, titre, qualif, status,
          target: '', owner: null, charge: 0, raf: 0,
          steps: [
            { name: 'Spécification', status: 'todo', charge: 0, raf: 0 },
            { name: 'Développement', status: 'todo', charge: 0, raf: 0 },
            { name: 'Tests',         status: 'todo', charge: 0, raf: 0 },
            { name: 'Mis en ligne',  status: 'todo', charge: 0, raf: 0 },
          ],
        });
      }
      toast(`Sous-projet "${name}" créé.`);
      renderAll();
    } catch (err) {
      toast(err.message, 'error');
    }
  });

  // Add project modal
  document.getElementById('modal-proj-cancel').addEventListener('click', closeAddProjModal);
  document.getElementById('modal-add-proj').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeAddProjModal();
  });

  document.getElementById('modal-proj-save').addEventListener('click', async () => {
    const name = document.getElementById('modal-proj-name').value.trim();
    const alias = document.getElementById('modal-proj-alias').value.trim();
    const desc = document.getElementById('modal-proj-desc').value.trim();
    const stack = document.getElementById('modal-proj-stack').value.trim();

    if (!name) { toast('Le nom est obligatoire.', 'error'); return; }

    try {
      const r = await addProject({ name, alias, desc, stack });
      closeAddProjModal();
      _state.projects.push({ id: r.id, name, alias, desc, stack, category: 'active', subprojects: [] });
      toast(`Projet "${name}" créé.`);
      renderAll();
    } catch (err) {
      toast(err.message, 'error');
    }
  });

  // Close status menu on outside click
  document.addEventListener('click', e => {
    if (!e.target.closest('#status-menu') && !e.target.closest('.status-badge') && !e.target.closest('.step-status-badge')) {
      closeStatusMenu();
    }
  });

  // View tabs (Projets / Docs)
  document.getElementById('view-tabs').addEventListener('click', e => {
    const btn = e.target.closest('.view-tab');
    if (!btn) return;
    switchView(btn.dataset.view);
  });

  // Docs filters
  loadDocFiltersFromLS();
  applyDocFiltersToUI();

  document.getElementById('docs-filters').addEventListener('click', e => {
    const btn = e.target.closest('.filter-btn');
    if (!btn) return;
    if (btn.dataset.docType) {
      const v = btn.dataset.docType;
      if (v === 'all') {
        _docFilterTypes.clear();
      } else {
        // Si "all" était actif et qu'on clique un type, on isole ce type
        if (_docFilterTypes.size === 0) {
          _docFilterTypes.add(v);
        } else if (_docFilterTypes.has(v)) {
          _docFilterTypes.delete(v);
        } else {
          _docFilterTypes.add(v);
        }
      }
      applyDocFiltersToUI();
      saveDocFiltersToLS();
      if (_view === 'docs') renderAll();
    } else if (btn.dataset.docStatus) {
      const v = btn.dataset.docStatus;
      if (_docFilterStatuses.has(v)) _docFilterStatuses.delete(v);
      else _docFilterStatuses.add(v);
      applyDocFiltersToUI();
      saveDocFiltersToLS();
      if (_view === 'docs') renderAll();
    }
  });

  const toggle = document.getElementById('toggle-empty-projects');
  toggle.checked = _showEmptyProjects;
  toggle.addEventListener('change', () => {
    _showEmptyProjects = toggle.checked;
    saveDocFiltersToLS();
    if (_view === 'docs') renderAll();
  });

  // Bouton global "+ Ajouter un doc"
  document.getElementById('btn-add-doc').addEventListener('click', () => openDocModal('add', {}));

  // Modal doc — cancel / overlay / save
  document.getElementById('modal-doc-cancel').addEventListener('click', closeDocModal);
  document.getElementById('modal-doc').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeDocModal();
  });
  document.getElementById('modal-doc-save').addEventListener('click', submitDocModal);

  // Chargement initial des archives (fire-and-forget) — initialise le badge
  // Le renderAll() final corrige l'affichage des docs liés à des SP archivés (§3.6 spec).
  fetchArchives()
    .then(a => {
      _archivesState = a || { projects: [] };
      _archivesLoaded = true;
      updateArchivesCountBadge();
      renderAll();
    })
    .catch(() => { /* archives indisponibles : badge reste vide */ });

  // Show container
  document.getElementById('loading').style.display = 'none';
  document.getElementById('projects-container').style.display = 'block';
  document.getElementById('add-project-btn').style.display = 'flex';

  renderAll();
}

function applyDocFiltersToUI() {
  document.querySelectorAll('#docs-filters [data-doc-type]').forEach(b => {
    const v = b.dataset.docType;
    const active = (v === 'all') ? _docFilterTypes.size === 0 : _docFilterTypes.has(v);
    b.classList.toggle('active', active);
  });
  document.querySelectorAll('#docs-filters [data-doc-status]').forEach(b => {
    b.classList.toggle('active', _docFilterStatuses.has(b.dataset.docStatus));
  });
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
