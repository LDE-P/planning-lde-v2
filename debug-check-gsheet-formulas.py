#!/usr/bin/env python3
"""Debug P1 (SPEC-RAF-OPTION-B / DEBUG-TESTS-PUSH-PULL.md §P1).

Diagnostic : pourquoi `write-sp-field` confirme une écriture côté API mais
le browser GSheet n'affiche pas la nouvelle valeur ?

Hypothèse principale : ARRAYFORMULA en G1 (ou ailleurs col G) qui recalcule
et écrase les écritures faites en G2:G.

Le script :
  1. Lit Tâches!A1:M1 en mode FORMULA → repère toute formule en header
  2. Lit Tâches!G1:G20 en mode FORMULA → repère une formule cachée plus bas
  3. Liste les protected ranges sur l'onglet Tâches
  4. Conclusion automatique

Usage : python3 planning-lde-v2/debug-check-gsheet-formulas.py
"""

import importlib.util
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('serve_v2', BASE / 'serve-v2.py')
serve_v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve_v2)


def _get_cell_formula(ws, cell: str):
    """Retourne la formule/valeur brute d'une cellule, ou '' si vide."""
    try:
        result = ws.get(cell, value_render_option='FORMULA')
        if result and result[0]:
            return result[0][0]
        return ''
    except Exception as e:
        return f'<erreur : {e}>'


def _get_range_formulas(ws, rng: str):
    """Retourne la liste de cellules en mode FORMULA pour une plage."""
    try:
        return ws.get(rng, value_render_option='FORMULA')
    except Exception as e:
        print(f'  <erreur lecture {rng} : {e}>')
        return []


def main():
    sid = serve_v2._get_spreadsheet_id()
    gc = serve_v2._get_gspread_client()
    sh = gc.open_by_key(sid)
    ws = sh.worksheet('Tâches')

    print(f'Spreadsheet : https://docs.google.com/spreadsheets/d/{sid}/')
    print(f'Onglet Tâches : id={ws.id}, rows={ws.row_count}, cols={ws.col_count}')
    print()

    # ── 1. Headers ligne 1 ──
    print('── 1. Headers A1:M1 (mode FORMULA) ──')
    row1 = _get_range_formulas(ws, 'A1:M1')
    if row1:
        row1 = row1[0]
    arrayformula_found_in_header = False
    for i, val in enumerate(row1):
        col = chr(ord('A') + i)
        is_formula = isinstance(val, str) and val.startswith('=')
        marker = ''
        if is_formula:
            marker = ' ← FORMULE'
            if 'ARRAYFORMULA' in val.upper() or val.upper().startswith('=ARRAY'):
                marker = ' ← ⚠ ARRAYFORMULA'
                arrayformula_found_in_header = True
        print(f'  {col}1 : {val!r}{marker}')
    print()

    # ── 2. Échantillon col G (G1:G20) ──
    print('── 2. Échantillon Tâches!G1:G20 (mode FORMULA) ──')
    g_range = _get_range_formulas(ws, 'G1:G20')
    arrayformula_found_in_col_g = False
    formula_count = 0
    for i, row in enumerate(g_range, start=1):
        val = row[0] if row else ''
        is_formula = isinstance(val, str) and val.startswith('=')
        marker = ''
        if is_formula:
            formula_count += 1
            marker = ' ← FORMULE'
            if 'ARRAYFORMULA' in val.upper():
                marker = ' ← ⚠ ARRAYFORMULA'
                arrayformula_found_in_col_g = True
        # N'imprime que les non-vides + premières lignes
        if val or i <= 3:
            print(f'  G{i} : {val!r}{marker}')
    print(f'  ({formula_count} cellule(s) avec formule dans G1:G20)')
    print()

    # ── 3. Protections sur l'onglet Tâches ──
    print('── 3. Protected ranges sur Tâches ──')
    try:
        meta = sh.fetch_sheet_metadata(params={'includeGridData': 'false'})
        tache_sheet = next(
            (s for s in meta.get('sheets', [])
             if s['properties']['title'] == 'Tâches'),
            None,
        )
        if tache_sheet:
            pr = tache_sheet.get('protectedRanges', [])
            print(f'  Nombre de protections : {len(pr)}')
            for p in pr:
                rng = p.get('range', {})
                start_row = rng.get('startRowIndex', 0)
                end_row = rng.get('endRowIndex', '∞')
                start_col = rng.get('startColumnIndex', 0)
                end_col = rng.get('endColumnIndex', '∞')
                desc = p.get('description', '')
                editors = p.get('editors', {}).get('users', [])
                print(f'    - rows={start_row}..{end_row}, cols={start_col}..{end_col}, '
                      f'desc={desc!r}, editors={editors}')
        else:
            print('  Onglet Tâches introuvable dans metadata.')
    except Exception as e:
        print(f'  Erreur lecture protections : {e}')
    print()

    # ── 4. Conclusion ──
    print('── 4. Conclusion ──')
    if arrayformula_found_in_header:
        print('  ⚠ ARRAYFORMULA détectée dans la ligne 1 — cause très probable de P1.')
        print('    Une ARRAYFORMULA en ligne 1 propage des valeurs sur G2:G en continu,')
        print('    et chaque écriture en G{n} via API est écrasée au prochain recalc.')
        print('    Action : remplacer la formule par des valeurs statiques, ou utiliser')
        print('    une cellule dédiée hors col G pour les saisies dashboard.')
    elif arrayformula_found_in_col_g:
        print('  ⚠ ARRAYFORMULA détectée dans col G (au-delà de G1) — investiguer.')
    elif formula_count > 0:
        print('  ⚠ Formule(s) non-ARRAYFORMULA en col G — peuvent écraser les écritures.')
        print('    Si la formule recalcule sur trigger (ex. AUJOURDHUI()) elle peut')
        print('    invalider les écritures API au prochain ouverture du browser.')
    else:
        print('  ✓ Pas de formule en col G — P1 a une autre cause :')
        print('    - cache navigateur (test : navigation privée)')
        print('    - propagation Google (test : attendre 60s puis F5)')
        print('    - session WebSocket désynchronisée (test : nouvel onglet)')


if __name__ == '__main__':
    main()
