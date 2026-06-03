#!/usr/bin/env python3
"""Serveur local Planning LDE V2 — port 8001."""

from __future__ import annotations

import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
GIT_ROOT = BASE_DIR.parent.resolve()
HTML_FILE = BASE_DIR / 'DASHBOARD-V2.html'
DATA_FILE = BASE_DIR / 'data.json'
ARCHIVES_FILE = BASE_DIR / 'data-archives.json'
HISTORY_FILE = BASE_DIR / 'history.jsonl'

MAX_PAYLOAD = 1_000_000  # 1 Mo
PORT = 8001

_VALID_STATUSES = {'done', 'wip', 'review', 'spec', 'todo', 'blocked', 'récurrent', 'fail'}
_VALID_STEP_STATUSES = _VALID_STATUSES | {'na'}

_DOC_TYPES = {'spec', 'audit', 'tests', 'bilan', 'notes', 'autre'}
_DOC_STATUSES = {'draft', 'final', 'archived'}
_DOC_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_DOC_PATCH_FIELDS = {'file', 'title', 'desc', 'type', 'status', 'date', 'subproject'}


_DEFAULT_STEPS = [
    {'name': 'Spécification', 'status': 'todo', 'charge': 0.0, 'raf': 0.0},
    {'name': 'Développement', 'status': 'todo', 'charge': 0.0, 'raf': 0.0},
    {'name': 'Tests',         'status': 'todo', 'charge': 0.0, 'raf': 0.0},
    {'name': 'Mis en ligne',  'status': 'todo', 'charge': 0.0, 'raf': 0.0},
]

_PROJECT_FOLDERS = {
    'dashboard-datamart': 'dashbord-datamart-V1/dashboard-datamart',
    'training-v7':        'opq-devcontainer-MHO/training-domain/training-v7',
    'examens-v7':         'opq-devcontainer-MHO/examens-domain/examens-v7',
    'planning-lde':       'planning-lde',
    'planning-lde-v2':    'planning-lde-v2',
    'cas-pratiques':      'CAS-PRATIQUES',
    'brief-equipe':       'brief-equipe',
}


# ── Data helpers ───────────────────────────────────────────────────────────────

def _load_data() -> dict:
    if not DATA_FILE.exists():
        return {'projects': []}
    try:
        return json.loads(DATA_FILE.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        raise ValueError('data.json corrompu (JSON invalide)')


# ── Écriture atomique + backups (blindage anti-perte, 2026-05-31) ──────────────
# Les backups sont relatifs au fichier écrit (path.parent/'backups-data') — pas
# d'état global, donc auto-isolant sous test (DATA_FILE patché vers un tmp).
_BACKUP_DIRNAME = 'backups-data'
_BACKUP_KEEP = 10              # backups horodatés gardés (par fichier)
_BACKUP_THROTTLE_S = 600       # au plus 1 backup horodaté / 10 min / fichier


class WipeRefused(Exception):
    """Levée quand une écriture viderait un état riche (garde anti-wipe).
    Interceptée dans do_POST → réponse 409, fichier préservé."""


def _count_projects(obj) -> int:
    return len(obj.get('projects', [])) if isinstance(obj, dict) else 0


def _fsync_dir(dirpath: Path):
    """fsync du dossier pour rendre durable le rename atomique."""
    fd = os.open(str(dirpath), os.O_RDONLY)
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _dump_rejected(path: Path, data):
    """Conserve un payload refusé par la garde anti-wipe (pour inspection)."""
    try:
        backup_dir = path.parent / _BACKUP_DIRNAME
        backup_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        (backup_dir / f'REJECTED_{path.name}_{ts}.json').write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    except OSError:
        pass


def _rotate_timestamped_backup(path: Path):
    """Backup horodaté de `path` dans <dir>/backups-data, throttlé
    (_BACKUP_THROTTLE_S) et tronqué aux _BACKUP_KEEP plus récents (par fichier)."""
    try:
        backup_dir = path.parent / _BACKUP_DIRNAME
        backup_dir.mkdir(exist_ok=True)
        pattern = path.name + '.*.json'
        existing = sorted(backup_dir.glob(pattern), key=lambda p: p.stat().st_mtime)
        now = datetime.now().timestamp()
        if existing and (now - existing[-1].stat().st_mtime) < _BACKUP_THROTTLE_S:
            return  # throttle : un backup horodaté trop récent existe déjà
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        shutil.copy2(path, backup_dir / f'{path.name}.{ts}.json')
        newest_first = sorted(backup_dir.glob(pattern),
                              key=lambda p: p.stat().st_mtime, reverse=True)
        for old in newest_first[_BACKUP_KEEP:]:
            try:
                old.unlink()
            except OSError:
                pass
    except OSError:
        pass


def _atomic_write_json(path: Path, data: dict, *, keep_prev: bool = True):
    """Écrit `data` en JSON de façon atomique et protégée contre la perte.

    1. Garde anti-wipe : refuse de remplacer un état riche (>0 projets) par un
       état à 0 projet (lève WipeRefused, payload refusé conservé).
    2. tmp (fsync) -> os.replace (rename atomique) -> fsync du dossier.
    3. Backups : `.prev` (1 cran) + horodaté rotatif (throttle 10 min, 10 gardés).
    """
    # 1. Garde anti-wipe
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            old = None
        if _count_projects(old) > 0 and _count_projects(data) == 0:
            _dump_rejected(path, data)
            raise WipeRefused(
                f'{path.name} : écriture refusée (passerait de '
                f'{_count_projects(old)} à 0 projet)')

    # 2. Écriture atomique
    tmp = path.parent / (path.name + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False))
        f.flush()
        os.fsync(f.fileno())

    # 3. Backups avant remplacement
    if keep_prev and path.exists():
        try:
            shutil.copy2(path, path.parent / (path.name + '.prev'))
        except OSError:
            pass
        _rotate_timestamped_backup(path)

    os.replace(tmp, path)        # rename atomique (tmp et cible dans le même dossier)
    _fsync_dir(path.parent)      # rend le rename durable


def _save_data(data: dict):
    _atomic_write_json(DATA_FILE, data)


def _load_archives() -> dict:
    if not ARCHIVES_FILE.exists():
        return {'projects': []}
    try:
        return json.loads(ARCHIVES_FILE.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        raise ValueError('data-archives.json corrompu (JSON invalide)')


def _save_archives(data: dict):
    _atomic_write_json(ARCHIVES_FILE, data)


def _log(entries: list):
    ts = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    with HISTORY_FILE.open('a', encoding='utf-8') as f:
        for entry in entries:
            entry.setdefault('ts', ts)
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')


# ── Utilities ──────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    nfkd = unicodedata.normalize('NFKD', name)
    ascii_str = ''.join(c for c in nfkd if not unicodedata.combining(c))
    ascii_str = ascii_str.lower()
    ascii_str = re.sub(r'[^a-z0-9]+', '-', ascii_str)
    return ascii_str.strip('-')


def _unique_id(base_id: str, existing: set) -> str:
    if base_id not in existing:
        return base_id
    n = 2
    while f'{base_id}-{n}' in existing:
        n += 1
    return f'{base_id}-{n}'


def _friday_of_isoweek(year: int, week: int) -> date:
    """Retourne le vendredi d'une semaine ISO donnée."""
    jan4 = date(year, 1, 4)
    mon_w1 = jan4 - timedelta(days=jan4.isoweekday() - 1)
    mon_target = mon_w1 + timedelta(weeks=week - 1)
    return mon_target + timedelta(days=4)


def _target_from_qualif(qualif: str) -> str | None:
    today = date.today()
    hour = datetime.now().hour
    if qualif == 'P0':
        d = today if hour < 17 else today + timedelta(days=1)
    elif qualif == 'P1':
        iso = today.isocalendar()
        d = _friday_of_isoweek(iso.year, iso.week)
    elif qualif == 'P2':
        iso = today.isocalendar()
        target_week = iso.week + 3
        target_year = iso.year
        max_week = date(target_year, 12, 28).isocalendar().week
        if target_week > max_week:
            target_week -= max_week
            target_year += 1
        d = _friday_of_isoweek(target_year, target_week)
    elif qualif == 'P3':
        return '2099-12-31'
    else:
        return None
    return d.isoformat()


def _resolve_project_path(project_id: str):
    """Retourne le chemin absolu du dossier du projet, ou None."""
    rel = _PROJECT_FOLDERS.get(project_id)
    if not rel:
        return None
    target = (GIT_ROOT / rel).resolve()
    if GIT_ROOT != target and GIT_ROOT not in target.parents:
        return None
    if not target.is_dir():
        return None
    return target


def _validate_doc_file(rel_path):
    """Valide qu'un chemin relatif désigne un fichier existant sous GIT_ROOT.

    Retourne (abs_path, None) en cas de succès, (None, error_msg) sinon.
    Anti-traversée : Path(GIT_ROOT, file).resolve() doit rester sous GIT_ROOT.
    """
    if not isinstance(rel_path, str) or not rel_path:
        return None, 'file manquant ou vide'
    try:
        abs_path = (GIT_ROOT / rel_path).resolve()
    except (OSError, ValueError) as e:
        return None, f'Chemin invalide : {e}'
    if not abs_path.is_relative_to(GIT_ROOT):
        return None, f'Chemin hors GIT_ROOT : {rel_path}'
    if not abs_path.is_file():
        return None, f'Fichier introuvable : {rel_path}'
    return abs_path, None


# ── HTTP Handler ───────────────────────────────────────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f'  {self.address_string()} — {fmt % args}')

    # ── Routing ───────────────────────────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        path = self.path.split('?')[0]
        if path in ('/', '/index.html'):
            self._serve_file(HTML_FILE, 'text/html; charset=utf-8')
        elif path in ('/app.js', '/ui.js', '/api.js'):
            self._serve_file(BASE_DIR / path.lstrip('/'),
                             'application/javascript; charset=utf-8')
        elif path == '/api/state':
            self._handle_state()
        elif path == '/api/local-folders':
            self._handle_local_folders()
        elif path == '/api/archives':
            self._handle_archives()
        else:
            self._json_error('Not Found', 404)

    def do_POST(self):
        path = self.path.split('?')[0]
        try:
            self._dispatch_post(path)
        except WipeRefused as e:
            # Garde anti-wipe : écriture refusée, data.json/archives préservés.
            self._json_error(f'Écriture refusée (garde anti-wipe) : {e}', 409)

    def _dispatch_post(self, path):
        if path == '/api/save-subproject':
            self._handle_save_subproject()
        elif path == '/api/add-subproject':
            self._handle_add_subproject()
        elif path == '/api/add-project':
            self._handle_add_project()
        elif path == '/api/open-folder':
            self._handle_open_folder()
        elif path == '/api/save-project':
            self._handle_save_project()
        elif path == '/api/remove-subproject':
            self._handle_remove_subproject()
        elif path == '/api/remove-project':
            self._handle_remove_project()
        elif path == '/api/add-doc':
            self._handle_add_doc()
        elif path == '/api/save-doc':
            self._handle_save_doc()
        elif path == '/api/remove-doc':
            self._handle_remove_doc()
        elif path == '/api/open-file':
            self._handle_open_file()
        elif path == '/api/archive-subproject':
            self._handle_archive_subproject()
        elif path == '/api/archive-project':
            self._handle_archive_project()
        elif path == '/api/restore-subproject':
            self._handle_restore_subproject()
        elif path == '/api/restore-project':
            self._handle_restore_project()
        elif path == '/api/delete-archive-subproject':
            self._handle_delete_archive_subproject()
        elif path == '/api/delete-archive-project':
            self._handle_delete_archive_project()
        else:
            self._json_error('Not Found', 404)

    def do_DELETE(self):
        self._json_error('Method Not Allowed', 405)

    def do_PUT(self):
        self._json_error('Method Not Allowed', 405)

    def do_PATCH(self):
        self._json_error('Method Not Allowed', 405)

    # ── Core helpers ──────────────────────────────────────────────────────────

    def _serve_file(self, path: Path, content_type: str):
        try:
            content = path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self._json_error('Not Found', 404)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get('Content-Length', 0))
        if length > MAX_PAYLOAD:
            raise OverflowError('Payload trop grand (> 1 Mo)')
        raw = self.rfile.read(length)
        return json.loads(raw.decode('utf-8'))

    def _json_ok(self, data=None):
        body = json.dumps(
            data if data is not None else {'ok': True},
            ensure_ascii=False,
        ).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def _json_error(self, msg: str, status: int = 500):
        body = json.dumps({'error': msg}, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    # ── GET handlers ─────────────────────────────────────────────────────────

    def _handle_state(self):
        try:
            data = _load_data()
            data['git_root'] = str(GIT_ROOT)
            self._json_ok(data)
        except ValueError as e:
            self._json_error(str(e), 500)
        except Exception as e:
            self._json_error(str(e), 500)

    def _handle_local_folders(self):
        result = {}
        for pid in _PROJECT_FOLDERS:
            p = _resolve_project_path(pid)
            result[pid] = str(p) if p else None
        self._json_ok(result)

    def _handle_archives(self):
        try:
            archives = _load_archives()
            self._json_ok(archives)
        except ValueError as e:
            self._json_error(str(e), 500)
        except Exception as e:
            self._json_error(str(e), 500)

    # ── POST handlers — Phase 1 ───────────────────────────────────────────────

    def _handle_save_subproject(self):
        try:
            payload = self._read_json_body()
        except OverflowError:
            self._json_error('Payload trop grand (> 1 Mo)', 413)
            return
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json_error(f'JSON invalide : {e}', 400)
            return

        project_id = payload.get('projectId')
        sp_id = payload.get('subprojectId')

        if not project_id:
            self._json_error('projectId manquant', 400)
            return
        if not sp_id:
            self._json_error('subprojectId manquant', 400)
            return

        status = payload.get('status')
        if status is not None and status not in _VALID_STATUSES:
            self._json_error(f'Statut invalide : {status!r}', 400)
            return

        try:
            data = _load_data()
        except ValueError as e:
            self._json_error(str(e), 500)
            return

        project = next((p for p in data['projects'] if p['id'] == project_id), None)
        if project is None:
            self._json_error(f'Projet inconnu : {project_id!r}', 404)
            return

        sp = next((s for s in project.get('subprojects', []) if s['id'] == sp_id), None)
        if sp is None:
            self._json_error(f'Sous-projet inconnu : {sp_id!r}', 404)
            return

        for field in ('status', 'qualif', 'target', 'owner', 'charge', 'raf', 'titre', 'name'):
            if field in payload:
                sp[field] = payload[field]

        # Merge steps par name — [] ou absent = no-op
        incoming_steps = payload.get('steps')
        if incoming_steps:
            existing_by_name = {s['name']: s for s in sp.setdefault('steps', [])}
            for step in incoming_steps:
                name = step.get('name')
                if not name:
                    continue
                if name in existing_by_name:
                    existing_by_name[name].update(step)
                else:
                    sp['steps'].append(dict(step))

        _save_data(data)
        _log([{'action': 'save-subproject', 'project': project_id, 'subproject': sp_id}])
        self._json_ok()

    def _handle_save_project(self):
        try:
            payload = self._read_json_body()
        except (OverflowError, json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json_error(str(e), 400)
            return
        project_id = payload.get('projectId', '')
        if not project_id:
            self._json_error('projectId requis', 400)
            return
        data = _load_data()
        proj = next((p for p in data['projects'] if p['id'] == project_id), None)
        if not proj:
            self._json_error('Projet introuvable', 404)
            return
        for field in ('alias', 'name', 'desc', 'stack'):
            if field in payload:
                proj[field] = payload[field]
        _save_data(data)
        self._json_ok({'ok': True})

    def _handle_remove_subproject(self):
        try:
            payload = self._read_json_body()
        except (OverflowError, json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json_error(str(e), 400)
            return
        project_id = payload.get('projectId', '')
        sp_id = payload.get('subprojectId', '')
        if not project_id or not sp_id:
            self._json_error('projectId et subprojectId requis', 400)
            return
        data = _load_data()
        proj = next((p for p in data['projects'] if p['id'] == project_id), None)
        if not proj:
            self._json_error('Projet introuvable', 404)
            return
        before = len(proj.get('subprojects', []))
        proj['subprojects'] = [s for s in proj.get('subprojects', []) if s['id'] != sp_id]
        if len(proj['subprojects']) == before:
            self._json_error('Sous-projet introuvable', 404)
            return
        _save_data(data)
        self._json_ok({'ok': True})

    def _handle_remove_project(self):
        try:
            payload = self._read_json_body()
        except (OverflowError, json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json_error(str(e), 400)
            return
        project_id = payload.get('projectId', '')
        if not project_id:
            self._json_error('projectId requis', 400)
            return
        data = _load_data()
        before = len(data['projects'])
        data['projects'] = [p for p in data['projects'] if p['id'] != project_id]
        if len(data['projects']) == before:
            self._json_error('Projet introuvable', 404)
            return
        _save_data(data)
        self._json_ok({'ok': True})

    # ── POST handlers — Archives ─────────────────────────────────────────────

    def _handle_archive_subproject(self):
        try:
            payload = self._read_json_body()
        except OverflowError:
            self._json_error('Payload trop grand (> 1 Mo)', 413)
            return
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json_error(f'JSON invalide : {e}', 400)
            return

        project_id = payload.get('projectId', '')
        sp_id = payload.get('subprojectId', '')
        if not project_id or not sp_id:
            self._json_error('projectId et subprojectId requis', 400)
            return

        try:
            data = _load_data()
            archives = _load_archives()
        except ValueError as e:
            self._json_error(str(e), 500)
            return

        project = next((p for p in data['projects'] if p['id'] == project_id), None)
        if not project:
            self._json_error('Projet introuvable', 404)
            return

        sp = next((s for s in project.get('subprojects', []) if s['id'] == sp_id), None)
        if not sp:
            self._json_error('Sous-projet introuvable', 404)
            return

        arch_proj = next((p for p in archives.get('projects', []) if p['id'] == project_id), None)
        if not arch_proj:
            arch_proj = {
                'id': project['id'],
                'name': project.get('name', ''),
                'alias': project.get('alias', ''),
                'desc': project.get('desc', ''),
                'stack': project.get('stack', ''),
                'category': project.get('category', 'active'),
                'folder': project.get('folder', ''),
                'docs': [],
                'subprojects': [],
            }
            archives.setdefault('projects', []).append(arch_proj)
        arch_proj.setdefault('subprojects', []).append(sp)

        project['subprojects'] = [s for s in project.get('subprojects', []) if s['id'] != sp_id]
        project_empty = len(project.get('subprojects', [])) == 0

        _save_data(data)
        _save_archives(archives)
        _log([{'action': 'archive-subproject', 'project': project_id, 'subproject': sp_id}])
        self._json_ok({'ok': True, 'projectEmpty': project_empty})

    def _handle_archive_project(self):
        try:
            payload = self._read_json_body()
        except OverflowError:
            self._json_error('Payload trop grand (> 1 Mo)', 413)
            return
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json_error(f'JSON invalide : {e}', 400)
            return

        project_id = payload.get('projectId', '')
        if not project_id:
            self._json_error('projectId requis', 400)
            return

        try:
            data = _load_data()
            archives = _load_archives()
        except ValueError as e:
            self._json_error(str(e), 500)
            return

        project = next((p for p in data['projects'] if p['id'] == project_id), None)
        if not project:
            self._json_error('Projet introuvable', 404)
            return

        arch_proj = next((p for p in archives.get('projects', []) if p['id'] == project_id), None)
        if arch_proj:
            # Fusion : ajouter les SP encore dans data à ceux déjà archivés
            arch_proj.setdefault('subprojects', []).extend(project.get('subprojects', []))
            if not arch_proj.get('docs'):
                arch_proj['docs'] = project.get('docs', [])
        else:
            archives.setdefault('projects', []).append(dict(project))

        data['projects'] = [p for p in data['projects'] if p['id'] != project_id]

        _save_data(data)
        _save_archives(archives)
        _log([{'action': 'archive-project', 'project': project_id}])
        self._json_ok({'ok': True})

    def _handle_restore_subproject(self):
        try:
            payload = self._read_json_body()
        except OverflowError:
            self._json_error('Payload trop grand (> 1 Mo)', 413)
            return
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json_error(f'JSON invalide : {e}', 400)
            return

        project_id = payload.get('projectId', '')
        sp_id = payload.get('subprojectId', '')
        if not project_id or not sp_id:
            self._json_error('projectId et subprojectId requis', 400)
            return

        try:
            data = _load_data()
            archives = _load_archives()
        except ValueError as e:
            self._json_error(str(e), 500)
            return

        arch_proj = next((p for p in archives.get('projects', []) if p['id'] == project_id), None)
        if not arch_proj:
            self._json_error('Projet introuvable', 404)
            return

        sp = next((s for s in arch_proj.get('subprojects', []) if s['id'] == sp_id), None)
        if not sp:
            self._json_error('Sous-projet introuvable', 404)
            return

        data_proj = next((p for p in data['projects'] if p['id'] == project_id), None)
        if not data_proj:
            data_proj = {
                'id': arch_proj['id'],
                'name': arch_proj.get('name', ''),
                'alias': arch_proj.get('alias', ''),
                'desc': arch_proj.get('desc', ''),
                'stack': arch_proj.get('stack', ''),
                'category': arch_proj.get('category', 'active'),
                'folder': arch_proj.get('folder', ''),
                'docs': [],
                'subprojects': [],
            }
            data['projects'].append(data_proj)

        data_proj.setdefault('subprojects', []).append(sp)

        arch_proj['subprojects'] = [s for s in arch_proj.get('subprojects', []) if s['id'] != sp_id]
        if not arch_proj.get('subprojects'):
            archives['projects'] = [p for p in archives.get('projects', []) if p['id'] != project_id]

        _save_data(data)
        _save_archives(archives)
        _log([{'action': 'restore-subproject', 'project': project_id, 'subproject': sp_id}])
        self._json_ok({'ok': True})

    def _handle_restore_project(self):
        try:
            payload = self._read_json_body()
        except OverflowError:
            self._json_error('Payload trop grand (> 1 Mo)', 413)
            return
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json_error(f'JSON invalide : {e}', 400)
            return

        project_id = payload.get('projectId', '')
        if not project_id:
            self._json_error('projectId requis', 400)
            return

        try:
            data = _load_data()
            archives = _load_archives()
        except ValueError as e:
            self._json_error(str(e), 500)
            return

        arch_proj = next((p for p in archives.get('projects', []) if p['id'] == project_id), None)
        if not arch_proj:
            self._json_error('Projet introuvable', 404)
            return

        if any(p['id'] == project_id for p in data['projects']):
            self._json_error('Conflit : un projet avec cet id existe déjà dans data.json', 409)
            return

        data['projects'].append(arch_proj)
        archives['projects'] = [p for p in archives.get('projects', []) if p['id'] != project_id]

        _save_data(data)
        _save_archives(archives)
        _log([{'action': 'restore-project', 'project': project_id}])
        self._json_ok({'ok': True})

    def _handle_delete_archive_subproject(self):
        try:
            payload = self._read_json_body()
        except OverflowError:
            self._json_error('Payload trop grand (> 1 Mo)', 413)
            return
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json_error(f'JSON invalide : {e}', 400)
            return

        project_id = payload.get('projectId', '')
        sp_id = payload.get('subprojectId', '')
        if not project_id or not sp_id:
            self._json_error('projectId et subprojectId requis', 400)
            return

        try:
            archives = _load_archives()
        except ValueError as e:
            self._json_error(str(e), 500)
            return

        arch_proj = next((p for p in archives.get('projects', []) if p['id'] == project_id), None)
        if not arch_proj:
            self._json_error('Projet introuvable', 404)
            return

        before = len(arch_proj.get('subprojects', []))
        arch_proj['subprojects'] = [s for s in arch_proj.get('subprojects', []) if s['id'] != sp_id]
        if len(arch_proj['subprojects']) == before:
            self._json_error('Sous-projet introuvable', 404)
            return

        if not arch_proj['subprojects']:
            archives['projects'] = [p for p in archives.get('projects', []) if p['id'] != project_id]

        _save_archives(archives)
        _log([{'action': 'delete-archive-subproject', 'project': project_id, 'subproject': sp_id}])
        self._json_ok({'ok': True})

    def _handle_delete_archive_project(self):
        try:
            payload = self._read_json_body()
        except OverflowError:
            self._json_error('Payload trop grand (> 1 Mo)', 413)
            return
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json_error(f'JSON invalide : {e}', 400)
            return

        project_id = payload.get('projectId', '')
        if not project_id:
            self._json_error('projectId requis', 400)
            return

        try:
            archives = _load_archives()
        except ValueError as e:
            self._json_error(str(e), 500)
            return

        before = len(archives.get('projects', []))
        archives['projects'] = [p for p in archives.get('projects', []) if p['id'] != project_id]
        if len(archives['projects']) == before:
            self._json_error('Projet introuvable', 404)
            return

        _save_archives(archives)
        _log([{'action': 'delete-archive-project', 'project': project_id}])
        self._json_ok({'ok': True})

    def _handle_add_subproject(self):
        try:
            payload = self._read_json_body()
        except OverflowError:
            self._json_error('Payload trop grand (> 1 Mo)', 413)
            return
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json_error(f'JSON invalide : {e}', 400)
            return

        project_id = payload.get('projectId')
        name = payload.get('name', '').strip()

        if not project_id:
            self._json_error('projectId manquant', 400)
            return
        if not name:
            self._json_error('name manquant ou vide', 400)
            return

        base_id = _slugify(name)
        if not base_id:
            self._json_error('name invalide (slug vide)', 400)
            return

        try:
            data = _load_data()
        except ValueError as e:
            self._json_error(str(e), 500)
            return

        project = next((p for p in data['projects'] if p['id'] == project_id), None)
        if project is None:
            self._json_error(f'Projet inconnu : {project_id!r}', 404)
            return

        existing_ids = {s['id'] for s in project.get('subprojects', [])}
        try:
            archives = _load_archives()
        except ValueError as e:
            self._json_error(str(e), 500)
            return
        arch_proj = next((p for p in archives.get('projects', []) if p['id'] == project_id), None)
        if arch_proj:
            existing_ids |= {s['id'] for s in arch_proj.get('subprojects', [])}
        sp_id = _unique_id(base_id, existing_ids)

        qualif = payload.get('qualif', '')
        target = payload.get('target') or (_target_from_qualif(qualif) if qualif else '') or ''

        incoming_steps = payload.get('steps')
        steps = [dict(s) for s in _DEFAULT_STEPS] if not incoming_steps else list(incoming_steps)

        sp = {
            'id': sp_id,
            'name': name,
            'titre': payload.get('titre', ''),
            'status': payload.get('status', 'todo'),
            'qualif': qualif,
            'target': target,
            'owner': payload.get('owner', None),
            'charge': float(payload.get('charge', 0.0)),
            'raf': float(payload.get('raf', 0.0)),
            'steps': steps,
        }

        project.setdefault('subprojects', []).append(sp)
        _save_data(data)
        _log([{'action': 'add-subproject', 'project': project_id, 'id': sp_id, 'name': name}])
        self._json_ok({'ok': True, 'id': sp_id})

    def _handle_add_project(self):
        try:
            payload = self._read_json_body()
        except OverflowError:
            self._json_error('Payload trop grand (> 1 Mo)', 413)
            return
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json_error(f'JSON invalide : {e}', 400)
            return

        name = payload.get('name', '').strip()
        if not name:
            self._json_error('name manquant ou vide', 400)
            return

        try:
            data = _load_data()
        except ValueError as e:
            self._json_error(str(e), 500)
            return

        existing_ids = {p['id'] for p in data['projects']}
        try:
            archives = _load_archives()
        except ValueError as e:
            self._json_error(str(e), 500)
            return
        existing_ids |= {p['id'] for p in archives.get('projects', [])}
        base_id = _slugify(name)
        proj_id = _unique_id(base_id, existing_ids)

        project = {
            'id': proj_id,
            'name': name,
            'alias': payload.get('alias', ''),
            'desc': payload.get('desc', ''),
            'stack': payload.get('stack', ''),
            'category': payload.get('category', 'active'),
            'folder': payload.get('folder', ''),
            'docs': [],
            'subprojects': [],
        }

        data['projects'].append(project)
        _save_data(data)
        _log([{'action': 'add-project', 'id': proj_id, 'name': name}])
        self._json_ok({'ok': True, 'id': proj_id})

    def _handle_open_folder(self):
        try:
            payload = self._read_json_body()
        except OverflowError:
            self._json_error('Payload trop grand (> 1 Mo)', 413)
            return
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json_error(f'JSON invalide : {e}', 400)
            return

        project_id = payload.get('projectId', '')

        # 1. Cherche dans le mapping statique
        folder = _resolve_project_path(project_id)

        # 2. Fallback : champ `folder` dans data.json
        if not folder:
            try:
                data = _load_data()
                proj = next((p for p in data['projects'] if p['id'] == project_id), None)
                if proj and proj.get('folder'):
                    candidate = (GIT_ROOT / proj['folder']).resolve()
                    if (GIT_ROOT == candidate or GIT_ROOT in candidate.parents) and candidate.is_dir():
                        folder = candidate
            except Exception:
                pass

        if not folder:
            self._json_error(f'Dossier introuvable pour : {project_id!r}', 404)
            return

        try:
            subprocess.Popen(['open', str(folder)])
            self._json_ok({'path': str(folder)})
        except Exception as e:
            self._json_error(str(e), 500)

    # ── POST handlers — Docs (SPEC-DOCS-MD.md §4) ─────────────────────────────

    def _handle_add_doc(self):
        try:
            payload = self._read_json_body()
        except OverflowError:
            self._json_error('Payload trop grand (> 1 Mo)', 413)
            return
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json_error(f'JSON invalide : {e}', 400)
            return

        project_id = payload.get('project_id')
        doc = payload.get('doc') if isinstance(payload.get('doc'), dict) else {}

        if not project_id or not isinstance(project_id, str):
            self._json_error('project_id manquant', 400)
            return

        file_rel = doc.get('file')
        title_raw = doc.get('title')
        title = title_raw.strip() if isinstance(title_raw, str) else ''
        doc_type = doc.get('type')
        status = doc.get('status')

        if not isinstance(file_rel, str) or not file_rel:
            self._json_error('file manquant', 400)
            return
        if not title:
            self._json_error('title manquant ou vide', 400)
            return
        if doc_type not in _DOC_TYPES:
            self._json_error(f'type invalide : {doc_type!r}', 400)
            return
        if status not in _DOC_STATUSES:
            self._json_error(f'status invalide : {status!r}', 400)
            return

        doc_date = doc.get('date')
        if doc_date not in (None, ''):
            if not isinstance(doc_date, str) or not _DOC_DATE_RE.match(doc_date):
                self._json_error(f'date invalide (format YYYY-MM-DD attendu) : {doc_date!r}', 400)
                return

        abs_path, err = _validate_doc_file(file_rel)
        if err:
            self._json_error(err, 400)
            return

        try:
            data = _load_data()
        except ValueError as e:
            self._json_error(str(e), 500)
            return

        project = next((p for p in data['projects'] if p['id'] == project_id), None)
        if project is None:
            self._json_error(f'project_id inconnu : {project_id!r}', 400)
            return

        docs_list = project.setdefault('docs', [])

        doc_id_raw = doc.get('id')
        doc_id = doc_id_raw.strip() if isinstance(doc_id_raw, str) else ''
        if not doc_id:
            doc_id = _slugify(title)
            if not doc_id:
                self._json_error(
                    'Impossible de générer un id depuis ce titre — fournis un id explicite',
                    400,
                )
                return

        existing_ids = {d['id'] for d in docs_list if isinstance(d, dict) and 'id' in d}
        if doc_id in existing_ids:
            self._json_error(
                'id déjà existant dans ce projet — modifie le titre ou fournis un id explicite',
                400,
            )
            return

        new_doc = {
            'id': doc_id,
            'file': file_rel,
            'title': title,
            'type': doc_type,
            'status': status,
        }
        if 'desc' in doc:
            new_doc['desc'] = doc['desc']
        if doc_date not in (None, ''):
            new_doc['date'] = doc_date
        if 'subproject' in doc:
            new_doc['subproject'] = doc['subproject']

        docs_list.append(new_doc)
        _save_data(data)
        _log([{'action': 'add-doc', 'project': project_id, 'id': doc_id, 'file': file_rel}])
        self._json_ok({'ok': True, 'doc': new_doc})

    def _handle_save_doc(self):
        try:
            payload = self._read_json_body()
        except OverflowError:
            self._json_error('Payload trop grand (> 1 Mo)', 413)
            return
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json_error(f'JSON invalide : {e}', 400)
            return

        project_id = payload.get('project_id')
        doc_id = payload.get('doc_id')
        patch = payload.get('patch') if isinstance(payload.get('patch'), dict) else {}

        if not project_id or not isinstance(project_id, str):
            self._json_error('project_id manquant', 400)
            return
        if not doc_id or not isinstance(doc_id, str):
            self._json_error('doc_id manquant', 400)
            return

        # Revalidation symétrique à add-doc (§4.2 SPEC, P7)
        if 'type' in patch and patch['type'] not in _DOC_TYPES:
            self._json_error(f'type invalide : {patch["type"]!r}', 400)
            return
        if 'status' in patch and patch['status'] not in _DOC_STATUSES:
            self._json_error(f'status invalide : {patch["status"]!r}', 400)
            return
        if 'date' in patch and patch['date'] != '':
            d = patch['date']
            if not isinstance(d, str) or not _DOC_DATE_RE.match(d):
                self._json_error(f'date invalide (format YYYY-MM-DD attendu) : {d!r}', 400)
                return
        if 'title' in patch:
            t = patch['title']
            if not isinstance(t, str) or not t.strip():
                self._json_error('title vide', 400)
                return
        if 'file' in patch:
            _, err = _validate_doc_file(patch['file'])
            if err:
                self._json_error(err, 400)
                return

        try:
            data = _load_data()
        except ValueError as e:
            self._json_error(str(e), 500)
            return

        project = next((p for p in data['projects'] if p['id'] == project_id), None)
        if project is None:
            self._json_error(f'project_id inconnu : {project_id!r}', 400)
            return

        doc = next(
            (d for d in project.get('docs', [])
             if isinstance(d, dict) and d.get('id') == doc_id),
            None,
        )
        if doc is None:
            self._json_error(f'doc_id inconnu dans ce projet : {doc_id!r}', 400)
            return

        # Champs inconnus dans patch → ignorés silencieusement (P4)
        for field in _DOC_PATCH_FIELDS:
            if field in patch:
                doc[field] = patch[field]

        _save_data(data)
        _log([{'action': 'save-doc', 'project': project_id, 'doc': doc_id}])
        self._json_ok({'ok': True})

    def _handle_remove_doc(self):
        try:
            payload = self._read_json_body()
        except OverflowError:
            self._json_error('Payload trop grand (> 1 Mo)', 413)
            return
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json_error(f'JSON invalide : {e}', 400)
            return

        project_id = payload.get('project_id')
        doc_id = payload.get('doc_id')

        if not project_id or not isinstance(project_id, str):
            self._json_error('project_id manquant', 400)
            return
        if not doc_id or not isinstance(doc_id, str):
            self._json_error('doc_id manquant', 400)
            return

        try:
            data = _load_data()
        except ValueError as e:
            self._json_error(str(e), 500)
            return

        project = next((p for p in data['projects'] if p['id'] == project_id), None)
        if project is None:
            self._json_error(f'project_id inconnu : {project_id!r}', 400)
            return

        docs_list = project.get('docs', [])
        before = len(docs_list)
        project['docs'] = [
            d for d in docs_list
            if not (isinstance(d, dict) and d.get('id') == doc_id)
        ]
        if len(project['docs']) == before:
            self._json_error(f'doc_id inconnu dans ce projet : {doc_id!r}', 400)
            return

        _save_data(data)
        _log([{'action': 'remove-doc', 'project': project_id, 'doc': doc_id}])
        self._json_ok({'ok': True})

    def _handle_open_file(self):
        try:
            payload = self._read_json_body()
        except OverflowError:
            self._json_error('Payload trop grand (> 1 Mo)', 413)
            return
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json_error(f'JSON invalide : {e}', 400)
            return

        file_rel = payload.get('file')
        if not isinstance(file_rel, str) or not file_rel:
            self._json_error('file manquant', 400)
            return

        abs_path, err = _validate_doc_file(file_rel)
        if err:
            self._json_error(err, 400)
            return

        try:
            subprocess.Popen(['open', '-R', str(abs_path)])
            self._json_ok({'ok': True})
        except Exception as e:
            self._json_error(str(e), 500)


# ── Entrypoint ─────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Planning LDE V2 — serveur local')
    parser.add_argument('--no-browser', action='store_true',
                        help='Ne pas ouvrir le navigateur au démarrage')
    parser.add_argument('--port', type=int, default=PORT,
                        help=f'Port (défaut : {PORT})')
    args = parser.parse_args()

    address = ('127.0.0.1', args.port)
    httpd = http.server.HTTPServer(address, Handler)
    url = f'http://localhost:{args.port}'
    print(f'Planning LDE V2 — {url}')
    if not args.no_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nServeur arrêté.')


if __name__ == '__main__':
    main()
