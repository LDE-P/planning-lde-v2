#!/usr/bin/env python3
"""Debug P2 (SPEC-RAF-OPTION-B / DEBUG-TESTS-PUSH-PULL.md §P2).

Diagnostic : pourquoi le pull debug lit `alias='_TEST_'` mais le browser
GSheet (Ctrl+F) ne trouve aucune occurrence ?

Le script compare les SPs présents dans `data.json` avec les lignes de
l'onglet Tâches GSheet (col A=alias, col B=nom, col M=sp.id). Sortie :
  - Lignes uniques GSheet (alias/nom présents dans la sheet mais pas data.json)
  - SPs uniques data.json (présents en data mais pas en sheet, projets non masqués)
  - Mismatches col M (id GSheet ≠ id data.json pour même alias+nom)

Usage : python3 planning-lde-v2/debug-compare-browser-data.py
"""

import importlib.util
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('serve_v2', BASE / 'serve-v2.py')
serve_v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve_v2)


def main():
    # ── 1. Lire la GSheet ──
    sid = serve_v2._get_spreadsheet_id()
    gc = serve_v2._get_gspread_client()
    sh = gc.open_by_key(sid)
    ws = sh.worksheet('Tâches')
    rows = ws.get_all_values()

    print(f'Spreadsheet : https://docs.google.com/spreadsheets/d/{sid}/')
    print(f'Onglet Tâches : id={ws.id}, lignes lues={len(rows)} (header inclus)')
    print()

    sheet_rows = []  # liste (row_num, alias, sp_name, sp_id)
    for i, row in enumerate(rows[1:], start=2):  # skip header
        if len(row) < 2:
            continue
        alias = row[0].strip()
        sp_name = row[1].strip()
        sp_id = row[12].strip() if len(row) > 12 else ''
        if not alias or not sp_name:
            continue
        sheet_rows.append((i, alias, sp_name, sp_id))

    # ── 2. Lire data.json ──
    data = serve_v2._load_data()
    data_sps = []  # liste (alias, sp_name, sp_id, project_hidden)
    for proj in data.get('projects', []):
        alias = proj.get('alias') or proj.get('name', '')
        hidden = bool(proj.get('gsheet_hidden'))
        for sp in proj.get('subprojects', []):
            data_sps.append((alias, sp.get('name', ''), sp.get('id', ''), hidden))

    # Index pour matching croisé
    sheet_by_alias_name = {(a.lower(), n.lower()): (rn, sid_) for (rn, a, n, sid_) in sheet_rows}
    data_by_alias_name = {(a.lower(), n.lower()): (sid_, hidden) for (a, n, sid_, hidden) in data_sps}

    # ── 3. Lignes uniques GSheet ──
    print('── 3. Lignes GSheet absentes de data.json ──')
    unique_sheet = [(rn, a, n, sid_) for (rn, a, n, sid_) in sheet_rows
                    if (a.lower(), n.lower()) not in data_by_alias_name]
    if not unique_sheet:
        print('  (aucune)')
    else:
        print(f'  {len(unique_sheet)} ligne(s) :')
        for rn, a, n, sid_ in unique_sheet:
            print(f'    - ligne {rn} : alias={a!r}  nom={n!r}  id={sid_!r}')
    print()

    # ── 4. SPs uniques data.json (projets non masqués) ──
    print('── 4. SPs data.json absents de GSheet (projets NON masqués uniquement) ──')
    unique_data = [(a, n, sid_) for (a, n, sid_, hidden) in data_sps
                   if not hidden and (a.lower(), n.lower()) not in sheet_by_alias_name]
    if not unique_data:
        print('  (aucun)')
    else:
        print(f'  {len(unique_data)} SP(s) :')
        for a, n, sid_ in unique_data:
            print(f'    - alias={a!r}  nom={n!r}  id={sid_!r}')
    print()

    # ── 5. SPs présents des deux côtés mais avec id col M ≠ data.json ──
    print('── 5. Mismatches col M (id GSheet ≠ id data.json) ──')
    mismatches = []
    for rn, a, n, sheet_id in sheet_rows:
        key = (a.lower(), n.lower())
        if key in data_by_alias_name:
            data_id, _ = data_by_alias_name[key]
            if sheet_id and data_id and sheet_id != data_id:
                mismatches.append((rn, a, n, sheet_id, data_id))
    if not mismatches:
        print('  (aucun)')
    else:
        for rn, a, n, sid_, did_ in mismatches:
            print(f'    - ligne {rn} : alias={a!r} nom={n!r} sheet_id={sid_!r} ≠ data_id={did_!r}')
    print()

    # ── 6. Lignes GSheet avec col M vide (transition) ──
    print('── 6. Lignes GSheet avec col M vide (avant premier push post-deploy) ──')
    empty_m = [(rn, a, n) for (rn, a, n, sid_) in sheet_rows if not sid_]
    if not empty_m:
        print('  (aucune — toutes les lignes ont leur col M remplie)')
    else:
        print(f'  {len(empty_m)} ligne(s) sans col M :')
        for rn, a, n in empty_m[:20]:
            print(f'    - ligne {rn} : alias={a!r} nom={n!r}')
        if len(empty_m) > 20:
            print(f'    … ({len(empty_m) - 20} de plus)')
    print()

    # ── 7. Résumé numérique ──
    n_sheet = len(sheet_rows)
    n_data = len(data_sps)
    n_data_visible = sum(1 for (_a, _n, _i, h) in data_sps if not h)
    n_data_hidden = n_data - n_data_visible
    print('── 7. Résumé ──')
    print(f'  Lignes GSheet (alias+nom non vides)  : {n_sheet}')
    print(f'  SPs data.json (visibles + masqués)   : {n_data} ({n_data_visible} visibles, {n_data_hidden} masqués)')
    print(f'  Lignes uniques GSheet                : {len(unique_sheet)}')
    print(f'  SPs uniques data.json (non masqués)  : {len(unique_data)}')
    print(f'  Mismatches col M                     : {len(mismatches)}')
    print(f'  Col M vide                           : {len(empty_m)}')


if __name__ == '__main__':
    main()
