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

export async function addSubproject(payload) {
  return _post('/api/add-subproject', payload);
}

export async function addProject(payload) {
  return _post('/api/add-project', payload);
}

export async function openFolder(projectId) {
  return _post('/api/open-folder', { projectId });
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
