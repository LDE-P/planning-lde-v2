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
GIT_ROOT = BASE_DIR.parent.resolve()
HTML_FILE = BASE_DIR / 'DASHBOARD-V2.html'
DATA_FILE = BASE_DIR / 'data.json'
ARCHIVES_FILE = BASE_DIR / 'data-archives.json'
CONF_FILE = BASE_DIR / 'serve-v2.conf.json'
HISTORY_FILE = BASE_DIR / 'history.jsonl'
CLIENT_SECRET = BASE_DIR / 'client_secret.json'
TOKEN_FILE = BASE_DIR / 'token.json'

MAX_PAYLOAD = 1_000_000  # 1 Mo
PORT = 8001

_VALID_STATUSES = {'done', 'wip', 'review', 'spec', 'todo', 'blocked'}
_VALID_STEP_STATUSES = _VALID_STATUSES | {'na'}

_DOC_TYPES = {'spec', 'audit', 'tests', 'bilan', 'notes', 'autre'}
_DOC_STATUSES = {'draft', 'final', 'archived'}
_DOC_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_DOC_PATCH_FIELDS = {'file', 'title', 'desc', 'type', 'status', 'date', 'subproject'}

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


def _load_archives() -> dict:
    if not ARCHIVES_FILE.exists():
        return {'projects': []}
    try:
        return json.loads(ARCHIVES_FILE.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        raise ValueError('data-archives.json corrompu (JSON invalide)')


def _save_archives(data: dict):
    ARCHIVES_FILE.write_text(
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
    'Semaine', 'Année', 'ID',
]
def _tcd_headers() -> list:
    """Headers C1-G1 : formules GSheet auto-recalculées à l'ouverture (AUJOURDHUI()).

    Formules de référence : planning-lde/formules.md §"Ligne 1 (C1-G1)".
    Décalage en jours (±7) plutôt que ISOWEEKNUM()-1 pour gérer correctement
    les fins d'année (ISOWEEKNUM()-1 retourne 0 en semaine 1 au lieu de 52).
    """
    return [
        'Projet/Sous-projet',
        'Total RAF',
        '="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI()-7);"00")',
        '="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI());"00")&" (P0)"',
        '="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI()+7);"00")&" (P1)"',
        '="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI()+14);"00")&" (P2)"',
        '="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI()+21);"00")&" (P3)"',
    ]


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
    return '=SUM(ARRAYFORMULA(VALUE(SUBSTITUTE(C2:H2;" h.";""))))&" h."'


def _f_semaines_col2(col: str) -> str:
    """Cellule {col}2 Semaines — somme sous-projets heures (formules.md §TCD/C2)."""
    return f'=SOMME(FILTER(N({col}4:{col}) ; REGEXMATCH(A4:A ; "^- ")))&" h."'


def _f_semaines_b3() -> str:
    """Cellule B3 Semaines — total RAF jours (formules.md §TCD/B3)."""
    return '=SUM(ARRAYFORMULA(VALUE(SUBSTITUTE(C3:H3;" j.";""))))&" j."'


def _f_semaines_col3(col: str) -> str:
    """Cellule {col}3 Semaines — conversion heures → jours (formules.md §TCD/C3)."""
    return f'=CEILING(VALUE(SUBSTITUTE({col}2;" h.";""))/7;0,1)&" j."'


def _f_semaines_b_row(row: int) -> str:
    """Colonne B Semaines ligne row — somme C:H si sous-projet (formules.md §TCD/B4).

    Note : col H = "Autre" (RAF des SPs sans date cible) — incluse dans le total.
    """
    return f'=IF(AND(A{row}<>"";LEFT(A{row};2)="- ");SUM(C{row}:H{row});"")'


def _f_semaines_week(row: int, offset: int) -> str:
    """Colonne semaine Semaines ligne row — RAF semaine (formules.md §TCD/C4-G4).

    Décalage en jours (±7j) + TEXTE "00" pour matcher col K Tâches (qui produit
    "S"&TEXTE(xx;"00")). Sans TEXTE/padding, mismatch pour les semaines 1–9.
    """
    day_offset = offset * 7
    if day_offset == 0:
        wk = 'TEXTE(ISOWEEKNUM(AUJOURDHUI());"00")'
    elif day_offset < 0:
        wk = f'TEXTE(ISOWEEKNUM(AUJOURDHUI(){day_offset});"00")'
    else:
        wk = f'TEXTE(ISOWEEKNUM(AUJOURDHUI()+{day_offset});"00")'
    r = str(row)
    return (
        '=SI(REGEXMATCH(A' + r + ';"^- ");'
        'SIERREUR(SOMME(FILTER(\'Tâches\'!G:G;'
        '\'Tâches\'!B:B=SUBSTITUE(A' + r + ';"- ";"");'
        '\'Tâches\'!K:K="S"&' + wk + '));"");"")'
    )


def _f_semaines_autre(row: int) -> str:
    """Colonne H Semaines ligne row — RAF des SPs sans date cible (col K Tâches = "")."""
    r = str(row)
    return (
        '=SI(REGEXMATCH(A' + r + ';"^- ");'
        'SIERREUR(SOMME(FILTER(\'Tâches\'!G:G;'
        '\'Tâches\'!B:B=SUBSTITUE(A' + r + ';"- ";"");'
        '\'Tâches\'!K:K=""));"");"")'
    )


def _semaines_headers() -> list:
    """Headers A1:H1 pour l'onglet Semaines — 8 colonnes (A–G comme TCD + H=Autre)."""
    return _tcd_headers() + ['Autre']


# ── Initialisation GSheet ──────────────────────────────────────────────────────

def _gs_delete_if_exists(sh, title: str) -> None:
    """Supprime un onglet s'il existe (ignore si absent)."""
    import gspread
    try:
        sh.del_worksheet(sh.worksheet(title))
    except gspread.WorksheetNotFound:
        pass


def _gs_set_hidden(sh, ws, hidden: bool) -> None:
    """Masque ou démasque un onglet via l'API Sheets."""
    sh.batch_update({'requests': [{'updateSheetProperties': {
        'properties': {'sheetId': ws.id, 'hidden': hidden},
        'fields': 'hidden',
    }}]})


def _gs_init(spreadsheet_id: str) -> dict:
    """Réinitialise les 3 onglets (Tâches, Semaines, TCD Projets) — reset complet.

    Si un onglet modèle (_modèle_<nom>) existe, duplique depuis le modèle pour
    préserver la mise en forme (largeurs, MFC, filtres). Sinon, recrée à blanc
    (comportement historique) et ajoute un warning dans la réponse.

    Retourne {'message': str, 'warnings': list[str]}
    """
    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_id)
    import gspread

    warnings = []

    def _get_modele(title):
        try:
            return sh.worksheet(f'_modèle_{title}')
        except gspread.WorksheetNotFound:
            return None

    # GSheet refuse de supprimer le dernier onglet — s'assurer qu'un onglet
    # temporaire existe avant de supprimer les 3 cibles.
    tmp_title = '__init_tmp__'
    try:
        tmp = sh.worksheet(tmp_title)
    except gspread.WorksheetNotFound:
        tmp = sh.add_worksheet(title=tmp_title, rows=1, cols=1)

    for title in ('Tâches', 'Semaines', 'TCD Projets'):
        _gs_delete_if_exists(sh, title)

    # ── Onglet Tâches ──
    modele_t = _get_modele('Tâches')
    if modele_t:
        ws_t = sh.duplicate_sheet(source_sheet_id=modele_t.id, new_sheet_name='Tâches')
        _gs_set_hidden(sh, ws_t, False)       # le duplicata hérite hidden=True — forcer visible
        _gs_set_hidden(sh, modele_t, True)    # la duplication peut démasquer la source — remasquer
        # NE PAS réécrire A1:M1 : le modèle contient déjà les en-têtes avec leur mise en forme
        ws_t.batch_clear(['A2:M1000'])
    else:
        warnings.append('_modèle_Tâches absent — onglet recréé sans mise en forme')
        ws_t = sh.add_worksheet(title='Tâches', rows=1000, cols=13)
        ws_t.update('A1:M1', [_TACHES_HEADERS], raw=False)

    # ── Onglet Semaines ──
    modele_s = _get_modele('Semaines')
    if modele_s:
        ws_s = sh.duplicate_sheet(source_sheet_id=modele_s.id, new_sheet_name='Semaines')
        _gs_set_hidden(sh, ws_s, False)
        _gs_set_hidden(sh, modele_s, True)
    else:
        warnings.append('_modèle_Semaines absent — onglet recréé sans mise en forme')
        ws_s = sh.add_worksheet(title='Semaines', rows=200, cols=8)

    # Formules toujours réécrites (modèle ou non) : le modèle apporte la mise en forme,
    # pas les données — les formules doivent être fraîches après chaque init.
    ws_s.update('A1:H1', [_semaines_headers()], raw=False)
    row2 = ['', _f_semaines_b2()] + [_f_semaines_col2(c) for c in 'CDEFGH']
    row3 = ['', _f_semaines_b3()] + [_f_semaines_col3(c) for c in 'CDEFGH']
    ws_s.update('A2:H2', [row2], raw=False)
    ws_s.update('A3:H3', [row3], raw=False)
    ws_s.update('A4', [[_f_semaines_a4()]], raw=False)
    formulas_bg = []
    for r in range(4, _SEMAINES_MAX_ROWS + 1):
        formulas_bg.append([
            _f_semaines_b_row(r),
            _f_semaines_week(r, -1),
            _f_semaines_week(r, 0),
            _f_semaines_week(r, 1),
            _f_semaines_week(r, 2),
            _f_semaines_week(r, 3),
            _f_semaines_autre(r),
        ])
    ws_s.update(f'B4:H{_SEMAINES_MAX_ROWS}', formulas_bg, raw=False)

    # ── Onglet TCD Projets ──
    modele_tcd = _get_modele('TCD Projets')
    if modele_tcd:
        ws_tcd = sh.duplicate_sheet(source_sheet_id=modele_tcd.id, new_sheet_name='TCD Projets')
        _gs_set_hidden(sh, ws_tcd, False)
        _gs_set_hidden(sh, modele_tcd, True)
        ws_tcd.update('A1:G1', [_tcd_headers()], raw=False)
        ws_tcd.batch_clear(['A2:G1000'])
    else:
        warnings.append('_modèle_TCD Projets absent — onglet recréé sans mise en forme')
        ws_tcd = sh.add_worksheet(title='TCD Projets', rows=200, cols=7)
        ws_tcd.update('A1:G1', [_tcd_headers()], raw=False)

    # Supprime l'onglet temporaire
    sh.del_worksheet(tmp)

    if warnings:
        msg = 'Init terminée — certains onglets recréés sans modèle (mise en forme non restaurée).'
    else:
        msg = 'Init terminée — onglets recréés depuis les modèles, mise en forme restaurée.'
    return {'message': msg, 'warnings': warnings}


# ── Push data.json → Tâches, puis Semaines → TCD ──────────────────────────────

def _build_tcd_rows(data: dict) -> list:
    """Construit les lignes TCD (row 2+) depuis data.json — sans dépendre des formules Semaines.

    Col B est une FORMULE (mêmes formules que Semaines) pour que les éditions team
    en C-G recalculent automatiquement le total RAF de la ligne. Cols A et C-G sont
    écrites en valeurs statiques (calculées depuis data.json).
    """
    today_week = date.today().isocalendar()[1]
    window = [today_week + offset for offset in _WEEK_OFFSETS]

    def sp_target_week(sp: dict):
        t = sp.get('target', '')
        if not t:
            return None
        try:
            return datetime.strptime(t, '%Y-%m-%d').date().isocalendar()[1]
        except ValueError:
            return None

    body: list = []
    row_idx = 4  # première ligne de données (1-indexé, GSheet)

    for proj in data.get('projects', []):
        if proj.get('gsheet_hidden'):
            continue
        if not proj.get('subprojects'):
            continue
        alias = proj.get('alias') or proj['name']
        body.append([alias, _f_semaines_b_row(row_idx), '', '', '', '', ''])
        row_idx += 1
        for sp in proj.get('subprojects', []):
            raf = sp.get('raf', 0.0) or 0.0
            wk = sp_target_week(sp)
            row = [f"- {sp['name']}", _f_semaines_b_row(row_idx), '', '', '', '', '']
            if wk is not None and raf:
                for i, target_w in enumerate(window):
                    if wk == target_w:
                        row[2 + i] = raf
                        break
            body.append(row)
            row_idx += 1

    # Rows 2 et 3 : formules locale-aware (TCD à 7 colonnes — C:G, pas C:H).
    # NB : _f_semaines_b2/b3 ont été étendues à C:H pour l'onglet Semaines (col H = Autre).
    # Le TCD reste à 7 colonnes (Hors scope SPEC-RAF-OPTION-B) — on inline les formules
    # C:G ici pour ne pas hériter de la plage H qui ferait planter VALUE("") sur cellule vide.
    row2 = ['', '=SUM(ARRAYFORMULA(VALUE(SUBSTITUTE(C2:G2;" h.";""))))&" h."'] + [_f_semaines_col2(c) for c in 'CDEFG']
    row3 = ['', '=SUM(ARRAYFORMULA(VALUE(SUBSTITUTE(C3:G3;" j.";""))))&" j."'] + [_f_semaines_col3(c) for c in 'CDEFG']
    return [row2, row3] + body


def _gs_build_taches_rows(data: dict) -> list:
    """Construit la liste des lignes (A:M) à pousser dans l'onglet Tâches."""
    rows = []
    row_num = 2
    for proj in data.get('projects', []):
        if proj.get('gsheet_hidden'):
            continue
        alias = proj.get('alias') or proj['name']
        for sp in proj.get('subprojects', []):
            rows.append([
                alias,
                sp['name'],
                sp.get('type', ''),                      # C: Type
                sp.get('qualif', ''),                    # D: Prio.
                sp.get('target', ''),                    # E: Cible
                sp.get('charge', 0.0),                   # F: Charge (h)
                sp.get('raf', 0.0),                      # G: RAF (h)
                sp.get('titre', ''),                     # H: Titre
                _STATUS_TO_GS.get(sp.get('status', 'todo'), 'À FAIRE'),  # I: Avanc.
                sp.get('commentaire', ''),               # J: Commentaire
                _f_taches_k(row_num),                    # K: Semaine (formule)
                _f_taches_l(row_num),                    # L: Année (formule)
                sp.get('id', ''),                        # M: ID (clé stable pour le pull)
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

    # Met à jour les libellés semaines dynamiques dans Semaines (8 cols : A–G + H=Autre)
    # et dans TCD Projets (7 cols inchangé).
    ws_s.update('A1:H1', [_semaines_headers()], raw=False)
    ws_tcd.update('A1:G1', [_tcd_headers()], raw=False)

    # Préservation C (Type) et J (Commentaire) — read-before-clear (SPEC-GSHEET-HIDDEN §5.2).
    # Lecture de l'état actuel avant clear pour pouvoir réécrire C/J au bon emplacement
    # (sinon : décalage silencieux dès qu'un projet ou SP du milieu disparaît).
    existing = ws_t.get_all_values()
    hidden_aliases = {
        (p.get('alias') or p['name']).lower()
        for p in data.get('projects', [])
        if p.get('gsheet_hidden')
    }
    preserved_cj = {}  # (alias_lower, sp_name_lower) → (type, commentaire)
    for r in existing[1:]:  # skip header
        if len(r) < 2 or not r[0].strip() or not r[1].strip():
            continue
        alias_l = r[0].strip().lower()
        if alias_l in hidden_aliases:
            continue  # lignes d'un projet masqué : ne pas préserver
        sp_l = r[1].strip().lower()
        type_ = r[2] if len(r) > 2 else ''
        commentaire = r[9] if len(r) > 9 else ''
        preserved_cj[(alias_l, sp_l)] = (type_, commentaire)

    # Extension Tâches à 13 colonnes si nécessaire (col M ajoutée dans Option B).
    # Les GSheet créées avant Option B n'ont que 12 colonnes (A-L).
    if ws_t.col_count < 13:
        ws_t.resize(cols=13)

    # batch_clear étendu : on efface aussi C et J (réécrites ensuite via preserved_cj)
    # Col M (sp.id) : effacée et réécrite à chaque push pour permettre le matching pull stable.
    ws_t.batch_clear(['A2:B1000', 'C2:C1000', 'D2:I1000', 'J2:J1000', 'K2:L1000', 'M2:M1000'])
    if rows:
        last = n + 1
        ws_t.batch_update([
            {'range': f'A2:B{last}', 'values': [[r[0], r[1]] for r in rows]},
            {'range': f'D2:I{last}', 'values': [r[3:9] for r in rows]},
            {'range': f'K2:L{last}', 'values': [r[10:12] for r in rows]},
            {'range': f'M2:M{last}', 'values': [[r[12]] for r in rows]},
        ], value_input_option='USER_ENTERED')

        # Restauration C et J pour les lignes pushées (projets visibles uniquement)
        c_col = [[preserved_cj.get((r[0].lower(), r[1].lower()), ('', ''))[0]] for r in rows]
        j_col = [[preserved_cj.get((r[0].lower(), r[1].lower()), ('', ''))[1]] for r in rows]
        ws_t.batch_update([
            {'range': f'C2:C{last}', 'values': c_col},
            {'range': f'J2:J{last}', 'values': j_col},
        ], value_input_option='USER_ENTERED')

    # TCD Projets : construit directement depuis data.json (pas via les formules Semaines
    # qui recalculent de façon asynchrone — évite la race condition et garantit que TCD
    # reflète immédiatement l'état après push, alias renommés inclus).
    tcd_rows = _build_tcd_rows(data)
    ws_tcd.batch_clear(['A2:G1000'])
    if tcd_rows:
        # raw=False (USER_ENTERED) : les formules de col B sont interprétées par GSheet
        ws_tcd.update(f'A2:G{len(tcd_rows) + 1}', tcd_rows, raw=False)

    hidden_projects = [
        (p.get('alias') or p['name'])
        for p in data.get('projects', [])
        if p.get('gsheet_hidden')
    ]
    _log([{'action': 'push-to-gsheet', 'subprojects': n, 'hidden': len(hidden_projects)}])
    return {'ok': True, 'pushed': n, 'hidden_projects': hidden_projects}


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
    hidden_projects = [
        (p.get('alias') or p['name'])
        for p in data.get('projects', [])
        if p.get('gsheet_hidden')
    ]
    return {
        'ok': True,
        'count': len(preview),
        'rows': preview,
        'hidden_projects': hidden_projects,
    }


# ── Mise en forme GSheet (manuelle, une seule fois) ───────────────────────────

_TYPE_OPTIONS = ['Feature', 'BugFix', 'Récurrent', 'Support', 'Autre']
_QUALIF_OPTIONS = ['P0', 'P1', 'P2', 'P3']
_STATUT_OPTIONS = ['TERMINÉ', 'EN COURS', 'REVUE', 'SPEC', 'À FAIRE', 'STAND BY']


def _gs_format(spreadsheet_id: str) -> dict:
    """Configure les menus déroulants (data validation) sur Tâches.

    Col C (Type)  : Feature/BugFix/Récurrent/Support/Autre
    Col D (Prio.) : P0/P1/P2/P3
    Col I (Avanc.) : TERMINÉ/EN COURS/REVUE/SPEC/À FAIRE/STAND BY

    Appelé manuellement seulement — jamais lors du push/pull.
    """
    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_id)
    ws_t = sh.worksheet('Tâches')

    def _validation_request(col_index: int, values: list) -> dict:
        return {
            'setDataValidation': {
                'range': {
                    'sheetId': ws_t.id,
                    'startRowIndex': 1,
                    'endRowIndex': 1000,
                    'startColumnIndex': col_index,
                    'endColumnIndex': col_index + 1,
                },
                'rule': {
                    'condition': {
                        'type': 'ONE_OF_LIST',
                        'values': [{'userEnteredValue': v} for v in values],
                    },
                    'showCustomUi': True,
                    'strict': False,
                },
            },
        }

    sh.batch_update({
        'requests': [
            _validation_request(2, _TYPE_OPTIONS),
            _validation_request(3, _QUALIF_OPTIONS),
            _validation_request(8, _STATUT_OPTIONS),
        ],
    })
    return {'ok': True, 'type_options': _TYPE_OPTIONS, 'qualif_options': _QUALIF_OPTIONS, 'statut_options': _STATUT_OPTIONS}


# ── Sauvegarde des onglets modèles ────────────────────────────────────────────

_MODELE_SOURCES = ['Tâches', 'Semaines', 'TCD Projets']


def _gs_save_template(spreadsheet_id: str) -> dict:
    """Duplique les 3 onglets courants en onglets modèles masqués.

    Pour chaque onglet source dans _MODELE_SOURCES :
    - Supprime l'ancien _modèle_<nom> s'il existe
    - Duplique l'onglet source sous le nom _modèle_<nom>
    - Masque l'onglet modèle

    Appelé manuellement seulement — jamais lors du push/pull/init.
    """
    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_id)

    saved = []
    for title in _MODELE_SOURCES:
        ws = sh.worksheet(title)
        modele_title = f'_modèle_{title}'

        # Supprime l'ancien modèle s'il existe
        _gs_delete_if_exists(sh, modele_title)

        # Duplique l'onglet source (préserve largeurs, MFC, filtres, formats)
        new_ws = sh.duplicate_sheet(
            source_sheet_id=ws.id,
            insert_sheet_index=len(sh.worksheets()),
            new_sheet_name=modele_title,
        )

        # Masque l'onglet modèle
        sh.batch_update({
            'requests': [{
                'updateSheetProperties': {
                    'properties': {
                        'sheetId': new_ws.id,
                        'hidden': True,
                    },
                    'fields': 'hidden',
                },
            }],
        })

        saved.append(modele_title)

    return {'ok': True, 'saved': saved}


# ── Pull depuis Tâches ─────────────────────────────────────────────────────────

def _find_sp(data: dict, alias: str, sp_name: str):
    """Retourne (proj, sp) si les deux existent, (proj, None) si le projet existe
    mais pas le sous-projet, (None, None) si l'alias est introuvable."""
    for proj in data.get('projects', []):
        proj_alias = (proj.get('alias') or proj['name']).lower()
        if proj_alias == alias.lower():
            for sp in proj.get('subprojects', []):
                if sp['name'].lower() == sp_name.lower():
                    return proj, sp
            return proj, None  # projet trouvé, sous-projet absent
    return None, None


def _find_sp_by_id(data: dict, project_id: str, sp_id: str):
    """Retourne (proj, sp) en cherchant par project.id + sp.id.

    Utilisé par l'endpoint /api/gsheet/write-sp-field (SPEC-RAF-OPTION-B §11).
    Retourne (proj, None) si le projet existe mais pas le sp, (None, None) si introuvable.
    """
    for proj in data.get('projects', []):
        if proj.get('id') == project_id:
            for sp in proj.get('subprojects', []):
                if sp.get('id') == sp_id:
                    return proj, sp
            return proj, None
    return None, None


def _gs_pull_taches(spreadsheet_id: str) -> dict:
    """Tire depuis Tâches : type, qualif, target, charge, RAF, titre, statut, commentaire → data.json.

    Matching :
    - Priorité à col M (sp.id stable) — permet le renommage de col B (sp.name)
      sans casser la correspondance. Si col M trouvée et sp.name diffère, propage.
    - Fallback nom (col B) si col M absente (transition avant premier push post-déploiement).

    Diagnostic : retourne created_projects/created_subprojects pour signaler les
    créations à la volée dues à un alias/nom inconnu (SPEC-RAF-OPTION-B §12).

    Ne touche pas aux étapes.
    """
    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.worksheet('Tâches')
    rows = ws.get_all_values()

    if len(rows) < 2:
        return {
            'ok': True, 'updated': 0,
            'ignored_projects': [],
            'created_projects': [], 'created_subprojects': [],
        }

    data = _load_data()
    updated = 0
    hidden_aliases = {
        (p.get('alias') or p['name']).lower()
        for p in data.get('projects', [])
        if p.get('gsheet_hidden')
    }
    ignored: list = []
    created_projects: list = []
    created_subprojects: list = []

    for row in rows[1:]:  # saute header
        if len(row) < 2:
            continue
        alias, sp_name = row[0].strip(), row[1].strip()
        if not alias or not sp_name:
            continue

        # Filtre « masqué gagne » avant _find_sp : un alias correspondant
        # à un projet masqué est ignoré indépendamment de l'ordre des projets.
        if alias.lower() in hidden_aliases:
            if alias not in ignored:
                ignored.append(alias)
            continue

        # Col M : sp.id stable (transition supportée : col M peut être vide pour les
        # lignes ajoutées dans GSheet avant le premier push post-déploiement).
        sp_id_from_sheet = row[12].strip() if len(row) > 12 else ''

        # Recherche projet via alias (toujours).
        proj = next(
            (p for p in data.get('projects', [])
             if (p.get('alias') or p['name']).lower() == alias.lower()),
            None,
        )
        if proj is None:
            proj_ids = {p['id'] for p in data['projects']}
            new_id = _unique_id(_slugify(alias), proj_ids)
            proj = {
                'id': new_id, 'name': alias, 'alias': alias,
                'desc': '', 'stack': '', 'category': 'active',
                'folder': '', 'docs': [], 'subprojects': [],
            }
            data['projects'].append(proj)
            created_projects.append(alias)

        # Recherche sp : priorité id (col M), fallback nom.
        sp = None
        if sp_id_from_sheet:
            sp = next(
                (s for s in proj.get('subprojects', []) if s.get('id') == sp_id_from_sheet),
                None,
            )
            if sp and sp_name and sp_name != sp.get('name', ''):
                sp['name'] = sp_name  # renommage propagé
        if sp is None:
            # Fallback nom (col M vide, ou id non trouvé) — comportement historique.
            sp = next(
                (s for s in proj.get('subprojects', []) if s['name'].lower() == sp_name.lower()),
                None,
            )
        if sp is None:
            sp_ids = {s['id'] for s in proj.get('subprojects', [])}
            sp_id = _unique_id(_slugify(sp_name), sp_ids)
            sp = {
                'id': sp_id, 'name': sp_name, 'status': 'todo',
                'qualif': '', 'target': '', 'owner': None,
                'charge': 0.0, 'raf': 0.0, 'titre': '',
                'steps': [
                    {'name': 'Spécification', 'status': 'todo', 'charge': 0.0, 'raf': 0.0},
                    {'name': 'Développement', 'status': 'todo', 'charge': 0.0, 'raf': 0.0},
                    {'name': 'Tests',         'status': 'todo', 'charge': 0.0, 'raf': 0.0},
                    {'name': 'Mis en ligne',  'status': 'todo', 'charge': 0.0, 'raf': 0.0},
                ],
            }
            proj.setdefault('subprojects', []).append(sp)
            created_subprojects.append(sp_name)

        type_  = row[2].strip() if len(row) > 2 else ''
        qualif = row[3].strip() if len(row) > 3 else ''
        target = row[4].strip() if len(row) > 4 else ''
        charge = _to_float(row[5]) if len(row) > 5 and row[5].strip() else None
        raf    = _to_float(row[6]) if len(row) > 6 and row[6].strip() else None
        titre  = row[7].strip() if len(row) > 7 else ''
        statut = row[8].strip() if len(row) > 8 else ''
        commentaire = row[9].strip() if len(row) > 9 else ''

        if type_:
            sp['type'] = type_
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
        if statut and statut in _STATUS_FROM_GS:
            sp['status'] = _STATUS_FROM_GS[statut]
        if commentaire:
            sp['commentaire'] = commentaire
        updated += 1

    _save_data(data)
    _log([{'action': 'pull-from-gsheet', 'updated': updated, 'ignored': len(ignored),
           'created_projects': len(created_projects),
           'created_subprojects': len(created_subprojects)}])
    return {
        'ok': True,
        'updated': updated,
        'ignored_projects': ignored,
        'created_projects': created_projects,
        'created_subprojects': created_subprojects,
    }


def _gs_pull_taches_preview(spreadsheet_id: str) -> dict:
    """Aperçu du pull depuis Tâches — sans écrire dans data.json."""
    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.worksheet('Tâches')
    rows = ws.get_all_values()

    data = _load_data()
    hidden_aliases = {
        (p.get('alias') or p['name']).lower()
        for p in data.get('projects', [])
        if p.get('gsheet_hidden')
    }
    ignored: list = []
    changes = []
    for row in rows[1:]:
        if len(row) < 2:
            continue
        alias, sp_name = row[0].strip(), row[1].strip()
        if not alias or not sp_name:
            continue
        if alias.lower() in hidden_aliases:
            if alias not in ignored:
                ignored.append(alias)
            continue
        proj, sp = _find_sp(data, alias, sp_name)
        if proj is None:
            changes.append({'projet': alias, 'sous_projet': sp_name, 'action': 'nouveau-projet'})
            continue
        if sp is None:
            changes.append({'projet': alias, 'sous_projet': sp_name, 'action': 'nouveau-sous-projet'})
            continue
        diff = {}
        if len(row) > 2 and row[2].strip():
            new_t = row[2].strip()
            if new_t != sp.get('type', ''):
                diff['type'] = {'avant': sp.get('type', ''), 'apres': new_t}
        if len(row) > 5 and row[5].strip():
            new_c = _to_float(row[5])
            if new_c != sp.get('charge', 0.0):
                diff['charge'] = {'avant': sp.get('charge'), 'apres': new_c}
        if len(row) > 6 and row[6].strip():
            new_r = _to_float(row[6])
            if new_r != sp.get('raf', 0.0):
                diff['raf'] = {'avant': sp.get('raf'), 'apres': new_r}
        if len(row) > 8 and row[8].strip() in _STATUS_FROM_GS:
            new_s = _STATUS_FROM_GS[row[8].strip()]
            if new_s != sp.get('status'):
                diff['status'] = {'avant': sp.get('status'), 'apres': new_s}
        if len(row) > 9 and row[9].strip():
            new_co = row[9].strip()
            if new_co != sp.get('commentaire', ''):
                diff['commentaire'] = {'avant': sp.get('commentaire', ''), 'apres': new_co}
        if diff:
            changes.append({'projet': alias, 'sous_projet': sp_name, 'diff': diff})
    return {'ok': True, 'changes': changes, 'ignored_projects': ignored}


# ── Écriture ciblée d'un champ SP dans la GSheet (write-sp-field) ─────────────

_WRITE_SP_FIELD_TO_COL = {'charge': 'F', 'raf': 'G'}


def _gs_write_sp_field(spreadsheet_id: str, sp_id: str, sp_name: str, alias: str,
                      field: str, value) -> dict:
    """Écrit une cellule (col F=charge, col G=raf) directement dans Tâches sans push global.

    Identifie la ligne : col M (sp.id) en priorité, fallback alias (col A) + nom (col B).
    Retourne {'ok': True, 'row': N} ou un dict d'erreur. SPEC-RAF-OPTION-B §11.
    """
    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.worksheet('Tâches')
    rows = ws.get_all_values()

    target_row = None
    for i, row in enumerate(rows[1:], start=2):  # ligne GSheet = i (1-indexed, header=1)
        # Priorité col M (sp.id stable)
        if len(row) > 12 and row[12].strip() and row[12].strip() == sp_id:
            target_row = i
            break
    if target_row is None:
        # Fallback alias + nom
        for i, row in enumerate(rows[1:], start=2):
            if (len(row) > 1
                    and row[0].strip().lower() == alias.lower()
                    and row[1].strip().lower() == sp_name.lower()):
                target_row = i
                break

    if target_row is None:
        return {'ok': False, 'error': 'Ligne GSheet introuvable pour ce SP'}

    col = _WRITE_SP_FIELD_TO_COL[field]
    cell = f'{col}{target_row}'
    ws.update([[value]], cell)
    return {'ok': True, 'row': target_row}


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
        elif path == '/api/gsheet/status':
            self._handle_gsheet_status()
        elif path == '/api/local-folders':
            self._handle_local_folders()
        elif path == '/api/archives':
            self._handle_archives()
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
        elif path == '/api/gsheet/format':
            self._handle_gsheet_format()
        elif path == '/api/gsheet/save-template':
            self._handle_gsheet_save_template()
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
        elif path == '/api/gsheet/write-sp-field':
            self._handle_gsheet_write_sp_field()
        elif path == '/api/save-project':
            self._handle_save_project()
        elif path == '/api/remove-subproject':
            self._handle_remove_subproject()
        elif path == '/api/remove-project':
            self._handle_remove_project()
        elif path == '/api/toggle-gsheet-hidden':
            self._handle_toggle_gsheet_hidden()
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

    def _handle_gsheet_status(self):
        try:
            sid = _get_spreadsheet_id()
            gc = _get_gspread_client()
            gc.open_by_key(sid)
            url = f'https://docs.google.com/spreadsheets/d/{sid}/edit'
            self._json_ok({'connected': True, 'url': url})
        except Exception:
            self._json_ok({'connected': False})

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

    def _handle_toggle_gsheet_hidden(self):
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
        except ValueError as e:
            self._json_error(str(e), 500)
            return

        proj = next((p for p in data['projects'] if p['id'] == project_id), None)
        if not proj:
            self._json_error('Projet introuvable', 404)
            return

        new_value = not proj.get('gsheet_hidden', False)
        proj['gsheet_hidden'] = new_value
        _save_data(data)
        _log([{'action': 'toggle-gsheet-hidden', 'project': project_id, 'gsheet_hidden': new_value}])
        self._json_ok({'ok': True, 'gsheet_hidden': new_value})

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
            result = _gs_init(sid)
            self._json_ok({'ok': True, **result})
        except ValueError as e:
            self._json_error(str(e), 500)
        except Exception as e:
            self._json_error(f'Init GSheet échouée : {e}', 500)

    def _handle_gsheet_format(self):
        if not self._drain_body():
            return
        try:
            sid = _get_spreadsheet_id()
            result = _gs_format(sid)
            self._json_ok(result)
        except ValueError as e:
            self._json_error(str(e), 500)
        except Exception as e:
            self._json_error(f'Mise en forme GSheet échouée : {e}', 500)

    def _handle_gsheet_save_template(self):
        if not self._drain_body():
            return
        try:
            sid = _get_spreadsheet_id()
            result = _gs_save_template(sid)
            self._json_ok(result)
        except ValueError as e:
            self._json_error(str(e), 500)
        except Exception as e:
            self._json_error(f'Sauvegarde modèles GSheet échouée : {e}', 500)

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
        # Désactivé — refonte prévue dans un sprint dédié (SPEC-RAF-OPTION-B §8).
        # _gs_pull_tcd_preview reste défini pour réactivation future.
        if not self._drain_body():
            return
        self._json_ok({
            'ok': False,
            'disabled': True,
            'message': 'Pull TCD désactivé — refonte prévue (sprint suivant).',
        })

    def _handle_pull_tcd(self):
        # Désactivé — refonte prévue dans un sprint dédié (SPEC-RAF-OPTION-B §8).
        # _gs_pull_tcd reste défini pour réactivation future.
        if not self._drain_body():
            return
        self._json_ok({
            'ok': False,
            'disabled': True,
            'message': 'Pull TCD désactivé — refonte prévue (sprint suivant).',
        })

    def _handle_gsheet_write_sp_field(self):
        """Écriture ciblée d'un champ SP (raf|charge) dans GSheet (SPEC-RAF-OPTION-B §11).

        Réutilise le squelette de _handle_save_subproject : CORS (via _json_ok),
        MAX_PAYLOAD (via _read_json_body), validation payload, sanitisation, métier, JSON.
        """
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
        field = payload.get('field')
        value = payload.get('value')

        if not project_id:
            self._json_error('projectId manquant', 400)
            return
        if not sp_id:
            self._json_error('subprojectId manquant', 400)
            return
        if field not in _WRITE_SP_FIELD_TO_COL:
            self._json_error(
                f'field non autorisé : {field!r} (attendu : raf|charge)', 400,
            )
            return
        if value is None:
            self._json_error('value manquant', 400)
            return

        try:
            data = _load_data()
        except ValueError as e:
            self._json_error(str(e), 500)
            return

        proj, sp = _find_sp_by_id(data, project_id, sp_id)
        if proj is None or sp is None:
            self._json_ok({'ok': False, 'error': 'SP introuvable'})
            return

        alias = proj.get('alias') or proj.get('name', '')
        sp_name = sp.get('name', '')

        try:
            sid = _get_spreadsheet_id()
            result = _gs_write_sp_field(sid, sp_id, sp_name, alias, field, value)
            self._json_ok(result)
        except ValueError as e:
            # spreadsheet_id absent — config GSheet incomplète
            self._json_ok({'ok': False, 'gsheet_unavailable': True, 'error': str(e)})
        except Exception as e:
            # GSheet non joignable (token expiré, réseau, etc.) → non bloquant
            self._json_ok({'ok': False, 'gsheet_unavailable': True, 'error': str(e)})


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
