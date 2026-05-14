#!/usr/bin/env python3
"""Serveur local Planning LDE V2 — port 8001."""

from __future__ import annotations

import http.server
import json
import math
import re
import subprocess
import sys
import unicodedata
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
HTML_FILE = BASE_DIR / 'DASHBOARD-V2.html'
DATA_FILE = BASE_DIR / 'data.json'
CONF_FILE = BASE_DIR / 'serve-v2.conf.json'
HISTORY_FILE = BASE_DIR / 'history.jsonl'
CLIENT_SECRET = BASE_DIR / 'client_secret.json'
TOKEN_FILE = BASE_DIR / 'token.json'

MAX_PAYLOAD = 1_000_000  # 1 Mo
PORT = 8001

_VALID_STATUSES = {'done', 'wip', 'review', 'spec', 'todo', 'blocked'}
_VALID_STEP_STATUSES = _VALID_STATUSES | {'na'}

_STATUS_TO_GS = {
    'done': 'TERMINÉ', 'wip': 'EN COURS', 'review': 'REVUE',
    'spec': 'SPEC', 'todo': 'À FAIRE', 'blocked': 'STAND BY',
}
_STATUS_FROM_GS = {v: k for k, v in _STATUS_TO_GS.items()}

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


def _save_data(data: dict):
    DATA_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )


def _log(entries: list):
    ts = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    with HISTORY_FILE.open('a', encoding='utf-8') as f:
        for entry in entries:
            entry.setdefault('ts', ts)
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')


# ── Config ─────────────────────────────────────────────────────────────────────

def _load_conf() -> dict:
    if not CONF_FILE.exists():
        return {}
    return json.loads(CONF_FILE.read_text(encoding='utf-8'))


def _get_spreadsheet_id() -> str:
    sid = _load_conf().get('spreadsheet_id', '').strip()
    if not sid:
        raise ValueError('spreadsheet_id absent de serve-v2.conf.json')
    return sid


# ── GSheet (gspread) ───────────────────────────────────────────────────────────

def _get_gspread_client():
    import gspread
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET.exists():
                raise FileNotFoundError(
                    f'{CLIENT_SECRET.name} introuvable — OAuth non configuré.'
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), scopes)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return gspread.authorize(creds)


# ── GSheet opérations (Phase 2) ───────────────────────────────────────────────

# Nombre de lignes max pour les formules Semaines (couverture jusqu'à 100 sous-projets)
_SEMAINES_MAX_ROWS = 100
_WEEK_OFFSETS = [-1, 0, 1, 2, 3]  # S-1 à S+3
_TACHES_HEADERS = [
    'Projet', 'Sous-projet', 'Type', 'Prio.', 'Cible',
    'Charge (h)', 'RAF (h)', 'Titre', 'Avanc.', 'Commentaire',
    'Semaine', 'Année',
]
_TCD_HEADERS = ['Projet/Sous-projet', 'Total RAF', 'S-1', 'S0', 'S+1', 'S+2', 'S+3']


def _to_float(val) -> float:
    """Convertit une valeur GSheet (str ou number) en float, 0.0 si vide/invalide."""
    try:
        if isinstance(val, (int, float)):
            return float(val)
        return float(str(val).strip().replace(',', '.'))
    except (ValueError, TypeError):
        return 0.0


def _h_to_j(h: float) -> float:
    """Heures → jours, arrondi au 0,1j supérieur. Base : 1j = 7h."""
    return math.ceil((h / 7) * 10) / 10 if h else 0.0


def _friday_from_week_offset(offset: int) -> str:
    """Retourne la date ISO du vendredi de la semaine (ISO courante + offset)."""
    today = date.today()
    iso = today.isocalendar()
    target_week = iso.week + offset
    target_year = iso.year
    max_week = date(target_year, 12, 28).isocalendar().week
    if target_week < 1:
        target_year -= 1
        max_week = date(target_year, 12, 28).isocalendar().week
        target_week += max_week
    elif target_week > max_week:
        target_week -= max_week
        target_year += 1
    return _friday_of_isoweek(target_year, target_week).isoformat()


# ── Constructeurs de formules (depuis formules.md — référence absolue) ─────────

def _f_taches_k(row: int) -> str:
    """Colonne K Tâches — Semaine (formules.md §Tâches/K)."""
    return f'=SI(E{row}="";"";\"S\"&TEXTE(ISOWEEKNUM(E{row});\"00\"))'


def _f_taches_l(row: int) -> str:
    """Colonne L Tâches — Année (formules.md §Tâches/L)."""
    return f'=SI(E{row}="";"";ANNEE(E{row}))'


def _f_semaines_a4() -> str:
    """Cellule A4 Semaines — QUERY/REDUCE (formules.md §TCD/A4)."""
    return (
        """=QUERY(REDUCE("" ; UNIQUE(FILTER('Tâches'!A2:A ; 'Tâches'!A2:A<>"")) ; """
        """LAMBDA(acc ; p ; VSTACK(acc ; p ; ARRAYFORMULA("- "&FILTER('Tâches'!B2:B ; """
        """'Tâches'!A2:A=p))))) ; "where Col1 is not null" ; 0)"""
    )


def _f_semaines_b2() -> str:
    """Cellule B2 Semaines — total RAF heures (formules.md §TCD/B2)."""
    return '=SUM(ARRAYFORMULA(VALUE(SUBSTITUTE(C2:G2;" h.";""))))&" h."'


def _f_semaines_col2(col: str) -> str:
    """Cellule {col}2 Semaines — somme sous-projets heures (formules.md §TCD/C2)."""
    return f'=SOMME(FILTER(N({col}4:{col}) ; REGEXMATCH(A4:A ; "^- ")))&" h."'


def _f_semaines_b3() -> str:
    """Cellule B3 Semaines — total RAF jours (formules.md §TCD/B3)."""
    return '=SUM(ARRAYFORMULA(VALUE(SUBSTITUTE(C3:G3;" j.";""))))&" j."'


def _f_semaines_col3(col: str) -> str:
    """Cellule {col}3 Semaines — conversion heures → jours (formules.md §TCD/C3)."""
    return f'=CEILING(VALUE(SUBSTITUTE({col}2;" h.";""))/7;0,1)&" j."'


def _f_semaines_b_row(row: int) -> str:
    """Colonne B Semaines ligne row — somme C:G si sous-projet (formules.md §TCD/B4)."""
    return f'=IF(AND(A{row}<>"";LEFT(A{row};2)="- ");SUM(C{row}:G{row});"")'


def _f_semaines_week(row: int, offset: int) -> str:
    """Colonne semaine Semaines ligne row — RAF semaine (formules.md §TCD/C4-G4)."""
    if offset == 0:
        wk = 'ISOWEEKNUM(AUJOURDHUI())'
    elif offset < 0:
        wk = f'(ISOWEEKNUM(AUJOURDHUI()){offset})'
    else:
        wk = f'(ISOWEEKNUM(AUJOURDHUI())+{offset})'
    return (
        f"=SI(REGEXMATCH(A{row};\"^- \");"
        f"SIERREUR(SOMME(FILTER('Tâches'!G:G;"
        f"'Tâches'!B:B=SUBSTITUE(A{row};\"- \";\"\");"
        f"'Tâches'!K:K=\"S\"&{wk}));\"\")\";\"\")"
    )


# ── Initialisation GSheet ──────────────────────────────────────────────────────

def _gs_get_or_create(sh, title: str, rows: int = 1000, cols: int = 14):
    """Retourne un worksheet existant ou le crée."""
    import gspread
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=title, rows=rows, cols=cols)


def _gs_init(spreadsheet_id: str) -> str:
    """Initialise les 3 onglets (Tâches, Semaines, TCD Projets).

    Retourne un message de résumé.
    """
    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_id)

    # ── Onglet Tâches ──
    ws_t = _gs_get_or_create(sh, 'Tâches', rows=1000, cols=12)
    ws_t.update('A1:L1', [_TACHES_HEADERS], raw=False)

    # ── Onglet Semaines ──
    ws_s = _gs_get_or_create(sh, 'Semaines', rows=200, cols=7)
    ws_s.update('A1:G1', [_TCD_HEADERS], raw=False)

    # Ligne 2 : totaux heures
    row2 = [
        '',
        _f_semaines_b2(),
        _f_semaines_col2('C'),
        _f_semaines_col2('D'),
        _f_semaines_col2('E'),
        _f_semaines_col2('F'),
        _f_semaines_col2('G'),
    ]
    ws_s.update('A2:G2', [row2], raw=False)

    # Ligne 3 : totaux jours
    row3 = [
        '',
        _f_semaines_b3(),
        _f_semaines_col3('C'),
        _f_semaines_col3('D'),
        _f_semaines_col3('E'),
        _f_semaines_col3('F'),
        _f_semaines_col3('G'),
    ]
    ws_s.update('A3:G3', [row3], raw=False)

    # A4 : QUERY/REDUCE (spilling)
    ws_s.update('A4', [[_f_semaines_a4()]], raw=False)

    # B4:G100 : formules par ligne
    formulas_bg = []
    for r in range(4, _SEMAINES_MAX_ROWS + 1):
        formulas_bg.append([
            '',  # A : géré par QUERY spilling
            _f_semaines_b_row(r),
            _f_semaines_week(r, -1),
            _f_semaines_week(r, 0),
            _f_semaines_week(r, 1),
            _f_semaines_week(r, 2),
            _f_semaines_week(r, 3),
        ])
    ws_s.update(f'A4:G{_SEMAINES_MAX_ROWS}', formulas_bg, raw=False)

    # ── Onglet TCD Projets ──
    ws_tcd = _gs_get_or_create(sh, 'TCD Projets', rows=200, cols=7)
    ws_tcd.update('A1:G1', [_TCD_HEADERS], raw=False)

    return f'Init terminée — onglets Tâches, Semaines, TCD Projets créés/mis à jour.'


# ── Push data.json → Tâches, puis Semaines → TCD ──────────────────────────────

def _gs_build_taches_rows(data: dict) -> list:
    """Construit la liste des lignes (A:L) à pousser dans l'onglet Tâches."""
    rows = []
    row_num = 2
    for proj in data.get('projects', []):
        alias = proj.get('alias') or proj['name']
        for sp in proj.get('subprojects', []):
            rows.append([
                alias,
                sp['name'],
                '',                                       # C: Type (GSheet only)
                sp.get('qualif', ''),                    # D: Prio.
                sp.get('target', ''),                    # E: Cible
                sp.get('charge', 0.0),                   # F: Charge (h)
                sp.get('raf', 0.0),                      # G: RAF (h)
                sp.get('titre', ''),                     # H: Titre
                _STATUS_TO_GS.get(sp.get('status', 'todo'), 'À FAIRE'),  # I: Avanc.
                '',                                       # J: Commentaire (GSheet only)
                _f_taches_k(row_num),                    # K: Semaine (formule)
                _f_taches_l(row_num),                    # L: Année (formule)
            ])
            row_num += 1
    return rows


def _gs_push(spreadsheet_id: str) -> dict:
    """Pousse data.json → Tâches, puis copie Semaines → TCD Projets."""
    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_id)
    data = _load_data()

    ws_t = sh.worksheet('Tâches')
    ws_s = sh.worksheet('Semaines')
    ws_tcd = sh.worksheet('TCD Projets')

    rows = _gs_build_taches_rows(data)
    n = len(rows)

    # Efface les données existantes (hors header)
    ws_t.batch_clear([f'A2:L1000'])
    if rows:
        ws_t.update(f'A2:L{n + 1}', rows, raw=False)

    # Lit les valeurs calculées de Semaines (après recalcul automatique GSheet)
    semaines_vals = ws_s.get_all_values()

    # Copie Semaines → TCD Projets (valeurs brutes, pas de formules)
    ws_tcd.batch_clear(['A2:G1000'])
    if len(semaines_vals) > 1:
        # rows 2+ de Semaines (index 1+) → TCD à partir de row 2
        tcd_data = semaines_vals[1:]  # saute la ligne d'entête
        ws_tcd.update(f'A2:G{len(tcd_data) + 1}', tcd_data, raw=True)

    _log([{'action': 'push-to-gsheet', 'subprojects': n}])
    return {'ok': True, 'pushed': n}


def _gs_push_preview(data: dict) -> dict:
    """Retourne un aperçu des lignes qui seraient poussées, sans écrire."""
    rows = _gs_build_taches_rows(data)
    preview = []
    for r in rows:
        preview.append({
            'projet': r[0],
            'sous_projet': r[1],
            'qualif': r[3],
            'target': r[4],
            'charge': r[5],
            'raf': r[6],
            'titre': r[7],
            'statut': r[8],
        })
    return {'ok': True, 'count': len(preview), 'rows': preview}


# ── Pull depuis Tâches ─────────────────────────────────────────────────────────

def _find_sp(data: dict, alias: str, sp_name: str):
    """Recherche un sous-projet par (alias de projet, nom de sous-projet)."""
    for proj in data.get('projects', []):
        proj_alias = (proj.get('alias') or proj['name']).lower()
        if proj_alias == alias.lower():
            for sp in proj.get('subprojects', []):
                if sp['name'].lower() == sp_name.lower():
                    return proj, sp
    return None, None


def _gs_pull_taches(spreadsheet_id: str) -> dict:
    """Tire depuis Tâches : charge, RAF, qualif, titre, target (col E) → data.json.

    Ne touche PAS aux statuts ni aux étapes.
    """
    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.worksheet('Tâches')
    rows = ws.get_all_values()

    if len(rows) < 2:
        return {'ok': True, 'updated': 0}

    data = _load_data()
    updated = 0

    for row in rows[1:]:  # saute header
        if len(row) < 9:
            continue
        alias, sp_name = row[0].strip(), row[1].strip()
        if not alias or not sp_name:
            continue

        proj, sp = _find_sp(data, alias, sp_name)
        if sp is None:
            continue  # orpheline — ignorée

        qualif = row[3].strip() if len(row) > 3 else ''
        target = row[4].strip() if len(row) > 4 else ''
        charge = _to_float(row[5]) if len(row) > 5 else None
        raf    = _to_float(row[6]) if len(row) > 6 else None
        titre  = row[7].strip() if len(row) > 7 else ''

        if qualif and qualif != sp.get('qualif', ''):
            sp['qualif'] = qualif
            new_target = _target_from_qualif(qualif)
            if new_target:
                sp['target'] = new_target
        if target:
            sp['target'] = target
        if charge is not None:
            sp['charge'] = charge
        if raf is not None:
            sp['raf'] = raf
        if titre:
            sp['titre'] = titre
        updated += 1

    _save_data(data)
    _log([{'action': 'pull-from-gsheet', 'updated': updated}])
    return {'ok': True, 'updated': updated}


def _gs_pull_taches_preview(spreadsheet_id: str) -> dict:
    """Aperçu du pull depuis Tâches — sans écrire dans data.json."""
    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.worksheet('Tâches')
    rows = ws.get_all_values()

    data = _load_data()
    changes = []
    for row in rows[1:]:
        if len(row) < 2:
            continue
        alias, sp_name = row[0].strip(), row[1].strip()
        if not alias or not sp_name:
            continue
        _, sp = _find_sp(data, alias, sp_name)
        if sp is None:
            changes.append({'projet': alias, 'sous_projet': sp_name, 'action': 'orpheline'})
            continue
        diff = {}
        if len(row) > 5 and row[5].strip():
            new_c = _to_float(row[5])
            if new_c != sp.get('charge', 0.0):
                diff['charge'] = {'avant': sp.get('charge'), 'apres': new_c}
        if len(row) > 6 and row[6].strip():
            new_r = _to_float(row[6])
            if new_r != sp.get('raf', 0.0):
                diff['raf'] = {'avant': sp.get('raf'), 'apres': new_r}
        if diff:
            changes.append({'projet': alias, 'sous_projet': sp_name, 'diff': diff})
    return {'ok': True, 'changes': changes}


# ── Pull depuis TCD Projets ────────────────────────────────────────────────────

def _find_sp_by_name(data: dict, sp_name: str):
    """Recherche un sous-projet par nom seul (pour le pull TCD)."""
    for proj in data.get('projects', []):
        for sp in proj.get('subprojects', []):
            if sp['name'].lower() == sp_name.lower():
                return proj, sp
    return None, None


def _gs_pull_tcd(spreadsheet_id: str) -> dict:
    """Tire depuis TCD Projets : raf + target → data.json.

    Seules les lignes '- ...' (sous-projets) sont traitées.
    Ne touche PAS aux statuts, étapes, charge des étapes.
    """
    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.worksheet('TCD Projets')
    rows = ws.get_all_values()

    if len(rows) < 4:
        return {'ok': True, 'updated': 0}

    data = _load_data()
    updated = 0

    # Lignes de données = rows[3:] (indices 3+, après header + 2 lignes totaux)
    for row in rows[3:]:
        if not row or not row[0]:
            continue
        cell_a = row[0].strip()
        if not cell_a.startswith('- '):
            continue  # ligne projet — ignorée

        sp_name = cell_a[2:].strip()
        _, sp = _find_sp_by_name(data, sp_name)
        if sp is None:
            continue

        # Cols C-G (indices 2-6) = S-1 à S+3
        raf_cols = [_to_float(row[i]) if len(row) > i else 0.0 for i in range(2, 7)]
        total_raf = sum(raf_cols)
        sp['raf'] = total_raf

        # target = vendredi de la dernière semaine avec RAF > 0
        last_nonzero = -1
        for i, v in enumerate(raf_cols):
            if v > 0:
                last_nonzero = i
        if last_nonzero >= 0:
            offset = _WEEK_OFFSETS[last_nonzero]
            sp['target'] = _friday_from_week_offset(offset)
        # si toutes à 0 : target inchangée

        updated += 1

    _save_data(data)
    _log([{'action': 'pull-from-tcd', 'updated': updated}])
    return {'ok': True, 'updated': updated}


def _gs_pull_tcd_preview(spreadsheet_id: str) -> dict:
    """Aperçu du pull TCD — sans écrire dans data.json."""
    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.worksheet('TCD Projets')
    rows = ws.get_all_values()

    data = _load_data()
    changes = []
    for row in rows[3:]:
        if not row or not row[0]:
            continue
        cell_a = row[0].strip()
        if not cell_a.startswith('- '):
            continue
        sp_name = cell_a[2:].strip()
        _, sp = _find_sp_by_name(data, sp_name)
        if sp is None:
            continue
        raf_cols = [_to_float(row[i]) if len(row) > i else 0.0 for i in range(2, 7)]
        new_raf = sum(raf_cols)
        if new_raf != sp.get('raf', 0.0):
            changes.append({'sous_projet': sp_name,
                            'raf_avant': sp.get('raf'), 'raf_apres': new_raf})
    return {'ok': True, 'changes': changes}


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


def _recalc_charges(sp: dict):
    """Recalcule charge/raf du sous-projet comme somme des étapes non-na."""
    active = [s for s in sp.get('steps', []) if s.get('status') != 'na']
    sp['charge'] = sum(s.get('charge', 0.0) for s in active)
    sp['raf'] = sum(s.get('raf', 0.0) for s in active)


def _resolve_project_path(project_id: str):
    """Retourne le chemin absolu du dossier du projet, ou None."""
    rel = _PROJECT_FOLDERS.get(project_id)
    if not rel:
        return None
    root = BASE_DIR.parent.resolve()
    target = (root / rel).resolve()
    if root != target and root not in target.parents:
        return None
    if not target.is_dir():
        return None
    return target


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
        elif path == '/api/gsheet/status':
            self._handle_gsheet_status()
        elif path == '/api/local-folders':
            self._handle_local_folders()
        else:
            self._json_error('Not Found', 404)

    def do_POST(self):
        path = self.path.split('?')[0]
        if path == '/api/save-subproject':
            self._handle_save_subproject()
        elif path == '/api/add-subproject':
            self._handle_add_subproject()
        elif path == '/api/add-project':
            self._handle_add_project()
        elif path == '/api/open-folder':
            self._handle_open_folder()
        elif path == '/api/gsheet/init':
            self._handle_gsheet_init()
        elif path == '/api/sync-to-gsheet/preview':
            self._handle_sync_preview()
        elif path == '/api/sync-to-gsheet':
            self._handle_sync()
        elif path == '/api/pull-from-gsheet/preview':
            self._handle_pull_taches_preview()
        elif path == '/api/pull-from-gsheet':
            self._handle_pull_taches()
        elif path == '/api/pull-from-tcd/preview':
            self._handle_pull_tcd_preview()
        elif path == '/api/pull-from-tcd':
            self._handle_pull_tcd()
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
            self._json_ok(data)
        except ValueError as e:
            self._json_error(str(e), 500)
        except Exception as e:
            self._json_error(str(e), 500)

    def _handle_gsheet_status(self):
        try:
            _get_spreadsheet_id()
            gc = _get_gspread_client()
            gc.open_by_key(_get_spreadsheet_id())
            self._json_ok({'connected': True})
        except Exception:
            self._json_ok({'connected': False})

    def _handle_local_folders(self):
        result = {}
        for pid in _PROJECT_FOLDERS:
            p = _resolve_project_path(pid)
            result[pid] = str(p) if p else None
        self._json_ok(result)

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

        for field in ('status', 'qualif', 'target', 'owner', 'charge', 'raf', 'titre'):
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
            _recalc_charges(sp)

        _save_data(data)
        _log([{'action': 'save-subproject', 'project': project_id, 'subproject': sp_id}])
        self._json_ok()

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
                    root = BASE_DIR.parent.resolve()
                    candidate = (root / proj['folder']).resolve()
                    if (root == candidate or root in candidate.parents) and candidate.is_dir():
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

    # ── GSheet handlers (Phase 2) ─────────────────────────────────────────────

    def _drain_body(self) -> bool:
        """Draine le body et retourne True, ou envoie 413 et retourne False."""
        length = int(self.headers.get('Content-Length', 0))
        if length > MAX_PAYLOAD:
            self._json_error('Payload trop grand (> 1 Mo)', 413)
            return False
        self.rfile.read(min(length, MAX_PAYLOAD))
        return True

    def _handle_gsheet_init(self):
        if not self._drain_body():
            return
        try:
            sid = _get_spreadsheet_id()
            msg = _gs_init(sid)
            self._json_ok({'ok': True, 'message': msg})
        except ValueError as e:
            self._json_error(str(e), 500)
        except Exception as e:
            self._json_error(f'Init GSheet échouée : {e}', 500)

    def _handle_sync_preview(self):
        if not self._drain_body():
            return
        try:
            data = _load_data()
            result = _gs_push_preview(data)
            self._json_ok(result)
        except Exception as e:
            self._json_error(str(e), 500)

    def _handle_sync(self):
        if not self._drain_body():
            return
        try:
            sid = _get_spreadsheet_id()
            result = _gs_push(sid)
            self._json_ok(result)
        except ValueError as e:
            self._json_error(str(e), 500)
        except Exception as e:
            self._json_error(f'Push GSheet échoué : {e}', 500)

    def _handle_pull_taches_preview(self):
        if not self._drain_body():
            return
        try:
            sid = _get_spreadsheet_id()
            result = _gs_pull_taches_preview(sid)
            self._json_ok(result)
        except ValueError as e:
            self._json_error(str(e), 500)
        except Exception as e:
            self._json_error(f'Preview pull Tâches échoué : {e}', 500)

    def _handle_pull_taches(self):
        if not self._drain_body():
            return
        try:
            sid = _get_spreadsheet_id()
            result = _gs_pull_taches(sid)
            self._json_ok(result)
        except ValueError as e:
            self._json_error(str(e), 500)
        except Exception as e:
            self._json_error(f'Pull Tâches échoué : {e}', 500)

    def _handle_pull_tcd_preview(self):
        if not self._drain_body():
            return
        try:
            sid = _get_spreadsheet_id()
            result = _gs_pull_tcd_preview(sid)
            self._json_ok(result)
        except ValueError as e:
            self._json_error(str(e), 500)
        except Exception as e:
            self._json_error(f'Preview pull TCD échoué : {e}', 500)

    def _handle_pull_tcd(self):
        if not self._drain_body():
            return
        try:
            sid = _get_spreadsheet_id()
            result = _gs_pull_tcd(sid)
            self._json_ok(result)
        except ValueError as e:
            self._json_error(str(e), 500)
        except Exception as e:
            self._json_error(f'Pull TCD échoué : {e}', 500)


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
