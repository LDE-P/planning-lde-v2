// Wrappers fetch vers /api/*

const BASE = '';

async function _post(path, body) {
  const r = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

async function _get(path) {
  const r = await fetch(BASE + path);
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

export async function fetchState() {
  return _get('/api/state');
}

export async function fetchGsheetStatus() {
  return _get('/api/gsheet/status');
}

export async function saveSubproject(payload) {
  return _post('/api/save-subproject', payload);
}

export async function saveProject(payload) {
  return _post('/api/save-project', payload);
}

export async function addSubproject(payload) {
  return _post('/api/add-subproject', payload);
}

export async function addProject(payload) {
  return _post('/api/add-project', payload);
}

export async function openFolder(projectId) {
  return _post('/api/open-folder', { projectId });
}

export async function initGsheet() {
  return _post('/api/gsheet/init', {});
}

export async function formatGsheet() {
  return _post('/api/gsheet/format', {});
}

export async function saveGsheetTemplate() {
  return _post('/api/gsheet/save-template', {});
}

export async function pushToGsheet() {
  return _post('/api/sync-to-gsheet', {});
}

export async function pullFromGsheet() {
  return _post('/api/pull-from-gsheet', {});
}

export async function pullFromTcd() {
  return _post('/api/pull-from-tcd', {});
}

export async function writeSpField(payload) {
  return _post('/api/gsheet/write-sp-field', payload);
}

export async function removeSubproject(payload) {
  return _post('/api/remove-subproject', payload);
}

export async function removeProject(projectId) {
  return _post('/api/remove-project', { projectId });
}

export async function toggleGsheetHidden(projectId) {
  return _post('/api/toggle-gsheet-hidden', { projectId });
}

// ── Docs (SPEC-DOCS-MD.md §4) ──────────────────────────────────────────────────

export async function addDoc(projectId, doc) {
  return _post('/api/add-doc', { project_id: projectId, doc });
}

export async function saveDoc(projectId, docId, patch) {
  return _post('/api/save-doc', { project_id: projectId, doc_id: docId, patch });
}

export async function removeDoc(projectId, docId) {
  return _post('/api/remove-doc', { project_id: projectId, doc_id: docId });
}

export async function openFile(file) {
  return _post('/api/open-file', { file });
}

// ── Archives (SPEC-ARCHIVAGE.md §7) ────────────────────────────────────────────

export async function fetchArchives() {
  return _get('/api/archives');
}

export async function archiveSubproject(projectId, subprojectId) {
  return _post('/api/archive-subproject', { projectId, subprojectId });
}

export async function archiveProject(projectId) {
  return _post('/api/archive-project', { projectId });
}

export async function restoreSubproject(projectId, subprojectId) {
  return _post('/api/restore-subproject', { projectId, subprojectId });
}

export async function restoreProject(projectId) {
  return _post('/api/restore-project', { projectId });
}

export async function deleteArchiveSubproject(projectId, subprojectId) {
  return _post('/api/delete-archive-subproject', { projectId, subprojectId });
}

export async function deleteArchiveProject(projectId) {
  return _post('/api/delete-archive-project', { projectId });
}
