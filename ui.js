// Rendu, interactions, événements

import { saveSubproject, addSubproject, addProject, openFolder, pushToGsheet, pullFromGsheet, pullFromTcd } from './api.js';

// ── État global ────────────────────────────────────────────────────────────────

let _state = { projects: [] };
let _filter = 'all';
let _statusMenuTarget = null;

// ── Labels ─────────────────────────────────────────────────────────────────────

const STATUS_LABELS = {
  done: 'TERMINÉ', wip: 'EN COURS', review: 'REVUE',
  spec: 'SPEC', todo: 'À FAIRE', blocked: 'STAND BY', na: 'N/A',
};

const SP_STATUSES = ['wip', 'todo', 'spec', 'review', 'blocked', 'done'];
const STEP_STATUSES = ['todo', 'wip', 'done', 'na'];

// ── Toast ──────────────────────────────────────────────────────────────────────

let _toastTimer = null;

function toast(msg, type = 'success') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `show ${type}`;
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => { el.className = ''; }, 3000);
}

// ── Stats bar ──────────────────────────────────────────────────────────────────

function updateStats() {
  const sps = _state.projects.flatMap(p => p.subprojects || []);
  document.getElementById('stat-total').textContent = sps.length;
  document.getElementById('stat-wip').textContent = sps.filter(s => s.status === 'wip').length;
  document.getElementById('stat-todo').textContent = sps.filter(s => s.status === 'todo').length;
  document.getElementById('stat-done').textContent = sps.filter(s => s.status === 'done').length;
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

// ── Project card ───────────────────────────────────────────────────────────────

function renderProject(proj) {
  const sps = (proj.subprojects || []).filter(shouldShow);
  const total = (proj.subprojects || []).length;
  const done = (proj.subprojects || []).filter(s => s.status === 'done').length;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  const card = document.createElement('div');
  card.className = 'project-card';
  card.dataset.projectId = proj.id;

  // Header
  const hdr = document.createElement('div');
  hdr.className = 'project-header';
  hdr.innerHTML = `
    <span class="project-toggle">▶</span>
    <span class="project-name">${esc(proj.name)}</span>
    <span class="project-stack">${esc(proj.stack || '')}</span>
    <div class="project-progress">
      <div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>
      <span>${done}/${total}</span>
    </div>
    <div class="project-actions">
      <button class="icon-btn btn-open-folder" title="Ouvrir le dossier">📁</button>
      <button class="icon-btn btn-add-sp" title="Nouveau sous-projet">＋</button>
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

  hdr.addEventListener('click', () => {
    card.classList.toggle('open');
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
    const charge = sp.charge ?? '?';
    const raf = sp.raf ?? '?';
    charges.innerHTML = `${charge}h / <span class="raf">${raf}h</span>`;
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

// ── Modals ─────────────────────────────────────────────────────────────────────

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
  const container = document.getElementById('projects-container');
  container.innerHTML = '';

  const visible = _state.projects.filter(p =>
    _filter === 'all' || (p.subprojects || []).some(shouldShow)
  );

  visible.forEach(p => container.appendChild(renderProject(p)));
}

// ── GSheet status ──────────────────────────────────────────────────────────────

export function updateGsheetStatus(connected) {
  const el = document.getElementById('gsheet-status');
  el.textContent = connected ? 'GSheet : ✓' : 'GSheet : non connecté';
  el.className = connected ? 'connected' : '';
}

// ── Init ───────────────────────────────────────────────────────────────────────

export function init(state) {
  _state = state;

  // Filters
  document.getElementById('filters').addEventListener('click', e => {
    const btn = e.target.closest('.filter-btn');
    if (!btn) return;
    _filter = btn.dataset.filter;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderAll();
  });

  // GSheet buttons
  document.getElementById('btn-push-gsheet').addEventListener('click', () => {
    pushToGsheet()
      .then(() => toast('Push GSheet effectué.'))
      .catch(err => toast(err.message, 'error'));
  });

  document.getElementById('btn-pull-gsheet').addEventListener('click', () => {
    pullFromGsheet()
      .then(() => toast('Pull Tâches effectué.'))
      .catch(err => toast(err.message, 'error'));
  });

  document.getElementById('btn-pull-tcd').addEventListener('click', () => {
    pullFromTcd()
      .then(r => toast(`Pull TCD : ${r.updated ?? '?'} mis à jour.`))
      .catch(err => toast(err.message, 'error'));
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

  // Show container
  document.getElementById('loading').style.display = 'none';
  document.getElementById('projects-container').style.display = 'block';
  document.getElementById('add-project-btn').style.display = 'flex';

  renderAll();
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
