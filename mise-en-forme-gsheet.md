# Mise en forme GSheet — Plan d'avancement

> Sous-projet du projet **Planning LDE V2** (`planning-lde-v2`)  
> Objectif : préserver la mise en forme manuelle (largeurs colonnes, MFC, filtres) lors des réinitialisations GSheet.

---

## Contexte et problème

Lors d'une réinitialisation via `/api/gsheet/init`, les 3 onglets (Tâches, Semaines, TCD Projets) sont **supprimés puis recréés from scratch** (`add_worksheet`). Toute mise en forme appliquée manuellement est perdue :

- largeurs de colonnes
- mises en forme conditionnelles (statuts colorés, priorités…)
- filtres actifs

La mise en forme via l'API a été abandonnée (bugs trop nombreux) — elle n'est pas dans le scope du script. Seuls les dropdowns (col C et I) sont gérés par `/api/gsheet/format`.

---

## Solution retenue : onglets modèles

Maintenir dans le spreadsheet des onglets cachés (`_modèle_Tâches`, `_modèle_Semaines`, `_modèle_TCD`) avec toute la mise en forme appliquée une seule fois. Lors du reinit, `_gs_init()` duplique ces onglets au lieu de créer des onglets vierges.

**Avantages :**
- La mise en forme vit dans la GSheet elle-même, pas dans le code Python
- Mettre à jour la mise en forme = éditer le modèle manuellement dans Sheets, sans toucher au script
- La duplication via gspread (`sh.duplicate_sheet()`) préserve largeurs, MFC et filtres
- Aucun code de formatage à maintenir

**Risque principal :** suppression accidentelle d'un onglet modèle → mise en forme perdue au prochain reinit. Mitigation : protéger les onglets modèles (lecture seule) ou nommage avec préfixe `_` comme signal visuel.

### Mise à jour de la mise en forme

Pour modifier la mise en forme après la mise en place initiale, il suffit de modifier les onglets modèles (`_modèle_*`). La prochaine réinitialisation recrée les onglets courants à partir des modèles mis à jour. Si le changement doit être visible immédiatement sans reinit, modifier aussi l'onglet courant en plus du modèle.

### Protections de plage

GSheets permet de protéger des plages spécifiques (colonnes, lignes, cellules) indépendamment de la feuille entière, via *Données → Protéger les feuilles et les plages*. Deux modes : blocage complet ou avertissement (warning) laissant l'édition possible avec confirmation.

**Comportement lors de la duplication :** ❌ **les protections de plage ne sont pas préservées** par `duplicate_sheet` (vérifié par test le 2026-05-16). Elles doivent être reposées manuellement sur les onglets courants après chaque reinit.

**Conséquence pour le process :** après un reinit, appliquer les protections de plage directement sur les onglets Tâches, Semaines, TCD Projets — pas sur les modèles. Les modèles conservent les autres éléments (largeurs, MFC, filtres).

---

## Étapes

| # | Étape | Statut | Notes |
|---|-------|--------|-------|
| 1 | [Créer les onglets modèles dans la GSheet](#étape-1--créer-les-onglets-modèles) | ✅ Fait | Bouton « ⊡ Modèles » + endpoint `/api/gsheet/save-template` |
| 2 | [Modifier `_gs_init()` pour dupliquer au lieu de créer](#étape-2--modifier-_gs_init) | ✅ Fait | `duplicate_sheet` + gestion visibilité + Semaines formules réécrites |
| 3 | [Gérer le fallback si onglet modèle absent](#étape-3--fallback) | ✅ Fait | Warning dans réponse + comportement actuel en secours |
| 4 | [Tests](#étape-4--tests) | ✅ Fait | Cas A (1 modèle absent) et B (0 modèle) validés le 2026-05-16 |

---

## Étape 1 — Créer les onglets modèles

**Principe :** les onglets modèles sont des copies des onglets actuels, avec toute la mise en forme désirée appliquée, sauvegardées sous les noms `_modèle_Tâches`, `_modèle_Semaines`, `_modèle_TCD`.

### Process

1. **Vérifier / appliquer la mise en forme** sur les onglets courants (Tâches, Semaines, TCD Projets) dans l'interface GSheet. C'est le seul moment de travail manuel : colonnes dimensionnées, MFC posées, filtres activés.

2. **Sauvegarder en tant que modèles** via un nouvel endpoint `/api/gsheet/save-template` qui duplique les 3 onglets et les renomme avec le préfixe `_modèle_`.

3. **Protéger les onglets modèles** dans l'interface GSheet (optionnel mais recommandé).

### Spécification de l'endpoint `/api/gsheet/save-template`

```
POST /api/gsheet/save-template
```

Comportement :
- Pour chaque onglet source dans `['Tâches', 'Semaines', 'TCD Projets']` :
  - Si un onglet `_modèle_<nom>` existe déjà → le supprimer
  - Dupliquer l'onglet source → renommer en `_modèle_<nom>`
  - Masquer l'onglet modèle (`hidden: true`)
- Renvoie `{ "saved": ["_modèle_Tâches", "_modèle_Semaines", "_modèle_TCD"] }`

### Implémentation gspread

```python
sh.duplicate_sheet(
    source_sheet_id=ws.id,
    insert_sheet_index=len(sh.worksheets()),
    new_sheet_name=f'_modèle_{ws.title}'
)
```

La duplication préserve intégralement : largeurs de colonnes, règles MFC, filtres, formats de cellules.

---

## Étape 2 — Modifier `_gs_init()`

> ℹ️ **Protections de plage :** non préservées par `duplicate_sheet` (vérifié 2026-05-16) — à reposer manuellement sur les onglets courants après reinit, pas sur les modèles.

> ℹ️ **Visibilité après duplication :** `duplicate_sheet` hérite `hidden=True` du modèle source et peut démasquer la source. Fix appliqué : `_gs_set_hidden(ws, False)` sur le duplicata + `_gs_set_hidden(modele, True)` sur la source après chaque duplication.

> ℹ️ **Semaines — formules :** le modèle apporte la mise en forme uniquement. Les formules (A1:G1 + A2:G3 + A4 + B4:G100) sont toujours réécrites après duplication pour garantir leur fraîcheur.

Remplacer le `add_worksheet` pour chaque onglet par :
1. Vérifier si `_modèle_<nom>` existe
2. Si oui → `duplicate_sheet` + renommer en nom canonique
3. Si non → fallback sur `add_worksheet` (comportement actuel) + warning dans la réponse

---

## Étape 3 — Fallback

Si un onglet modèle est absent lors d'un reinit :
- Le reinit se déroule normalement (comportement actuel)
- La réponse JSON inclut `"warnings": ["Onglet modèle _modèle_Tâches absent — mise en forme non restaurée"]`
- Aucune erreur bloquante

---

## Étape 4 — Tests

Cas à couvrir :

| Cas | Résultat attendu |
|-----|-----------------|
| Reinit avec les 3 modèles présents | Les 3 onglets sont recréés avec la mise en forme intacte |
| Reinit avec 1 modèle manquant | L'onglet manquant est recréé vierge, warning dans la réponse |
| Reinit sans aucun modèle | Comportement actuel (onglets vierges), warnings pour les 3 |
| **⚠️ Après tests de fallback** | Toujours cliquer **⊡ Modèles** pour remettre les modèles en place |
| `save-template` sur GSheet vierge | Crée les 3 modèles sans erreur |
| `save-template` avec modèles existants | Écrase les anciens modèles |
| Largeurs / MFC / filtres après reinit avec modèle | Identiques à l'onglet source au moment du `save-template` |

---

## Procédures opérationnelles

### Mettre à jour la mise en forme

1. Modifier la mise en forme sur les onglets courants dans GSheets (largeurs, MFC, filtres)
2. **⊡ Modèles** — sauvegarde les 3 onglets comme templates

### Réinitialiser la GSheet

1. **Init** — recrée les 3 onglets depuis les templates (mise en forme restaurée, données effacées)
2. **Push** — repopule les données depuis `data.json`
3. **Format** *(uniquement si les dropdowns sont absents)* — repose les dropdowns col C (Type) et col I (Avanc.). Inutile si les templates ont été sauvegardés avec les dropdowns déjà en place (ils sont restaurés automatiquement par l'Init).

> ⚠️ Toujours faire **⊡ Modèles avant Init**, jamais après.  
> ⚠️ Après des tests de fallback (suppression de modèles), toujours terminer par **⊡ Modèles** pour remettre les templates en place.

## Fichiers concernés

| Fichier | Modification |
|---------|-------------|
| `serve-v2.py` | Ajout `_gs_save_template()` + endpoint POST `/api/gsheet/save-template` |
| `serve-v2.py` | Modification `_gs_init()` pour dupliquer si modèle présent |
| `DASHBOARD-V2.html` | Ajout bouton « Sauvegarder comme modèle » dans le panneau GSheet |
