# SPEC — Planning LDE V2

> Statut : **SPEC VALIDÉE** — prête pour implémentation Claude Code.
> Rédigé en Cowork le 2026-05-13. Dernière mise à jour : 2026-05-14.

---

## Contexte et objectifs

Le Planning LDE V1 (`planning-lde/`) souffre de plusieurs problèmes de lisibilité :
- Le champ `group` sur chaque feature n'est pas une entité propre — juste un label libre, source d'incohérences.
- Les features V1 mélangent tâches macro et micro-détails d'implémentation (ex : "Formules Année/Semaine (séparateur point-virgule locale FR)").
- La GSheet résultante est illisible à l'usage : des centaines de lignes techniques, pas un outil de pilotage hebdo.

**Objectifs V2 :**
- Un modèle de données en 3 niveaux clairs : Projet → Sous-projet → Étape.
- Un dashboard plus lisible : chaque projet affiche ses sous-projets avec leur avancement synthétique.
- Une GSheet simplifiée : 1 ligne = 1 sous-projet, vue semaine pour le point équipe hebdo.
- Un workflow Cowork explicite : chaque session mappe sur un sous-projet nommé.

**Périmètre V2 :** projets LDE uniquement (pas MHO/ESL).
**Stratégie de déploiement :** V1 (port 8000) et V2 (port 8001) tournent en parallèle. Migration V1 → V2 après validation.

---

## 1. Modèle de données

### 1.1 Hiérarchie

```
PROJET
  └── SOUS-PROJET  (= une tâche Cowork, un bloc de travail cohérent)
        └── ÉTAPE  (= 3 à 6 jalons synthétiques, standardisés par défaut)
```

### 1.2 Structure de données

**Choix d'architecture : `data.json` externe, HTML = shell UI pur.**

Le HTML V2 ne contient **aucune donnée embarquée** : pas de `const PROJECTS = [...]`, pas de blocs sentinelles regex. Le serveur lit et écrit un fichier `data.json` unique. Le dashboard charge les données via un appel `GET /api/state` au démarrage. Cette approche élimine la fragilité des sentinelles regex de V1 et rend `data.json` versionnable indépendamment.

> **SQLite** : option écartée pour V2 (surpuissant, dépendance supplémentaire). Peut être envisagé en V3 si le volume de données le justifie.

**Structure de `data.json` :**

```json
{
  "projects": [
    {
      "id": "dashboard-datamart",
      "name": "Dashboard Datamart",
      "alias": "Datamart",
      "desc": "Description courte.",
      "stack": "JS · Chart.js · Python proxy",
      "category": "active",
      "folder": "dashbord-datamart-V1/dashboard-datamart",
      "docs": [],
      "subprojects": [
        {
          "id": "editorial-examen-s1",
          "name": "Éditorial Examen — Sprint 1",
          "titre": "Révision éditoriale complète des questions d'examen.",
          "status": "done",
          "qualif": "P1",
          "target": "2026-05-16",
          "owner": "laurent",
          "charge": 12.0,
          "raf": 0,
          "steps": [
            { "name": "Spécification", "status": "done", "charge": 2.0, "raf": 0 },
            { "name": "Développement", "status": "done", "charge": 8.0, "raf": 0 },
            { "name": "Tests",         "status": "done", "charge": 1.5, "raf": 0 },
            { "name": "Mis en ligne",  "status": "done", "charge": 0.5, "raf": 0 }
          ]
        }
      ]
    }
  ]
}
```

**Structure JS du dashboard (3 fichiers séparés) :**

| Fichier | Rôle |
|---------|------|
| `app.js` | Point d'entrée — charge les données, initialise l'UI |
| `ui.js` | Rendu, interactions, gestion des événements |
| `api.js` | Appels fetch vers le serveur (`/api/*`) |

Le HTML se limite à la structure DOM et à `<script type="module" src="app.js">`. Aucune logique ni donnée inline.

### 1.3 Règles du modèle

**Identifiants :**
- `id` de sous-projet : unique au sein du projet, kebab-case, généré automatiquement à la création (slug du nom). En cas de collision, suffixe `-2`, `-3`.

**Champ `owner` :**
- Optionnel, nullable (`null` si non renseigné). Valeurs : `"laurent"`, `"micka"`, `"elie"`, `"team"`.
- Pas de colonne dédiée dans la GSheet V2 (périmètre LDE uniquement).
- Conservé dans `data.json` pour traçabilité et extension future.

**Champ `titre` :**
- Description courte du sous-projet (une phrase). Complète le `name` sans le remplacer.
- Affiché dans le dashboard (sous le nom du sous-projet) et dans la colonne Titre de la GSheet.
- Optionnel. Modifiable dans les deux sens (dashboard + GSheet).

**Vocabulaire des statuts — unifié dashboard et GSheet :**

| Code interne | Label affiché (dashboard + GSheet) | Description |
|-------------|-----------------------------------|-------------|
| `done`    | TERMINÉ  | Livré, clôturé |
| `wip`     | EN COURS | En développement actif |
| `review`  | REVUE    | Phase de tests ou de relecture |
| `spec`    | SPEC     | En cours de spécification |
| `todo`    | À FAIRE  | Planifié, pas encore démarré |
| `blocked` | STAND BY | Bloqué, en attente |

**Statut du sous-projet :**
- Le statut est **géré exclusivement dans le dashboard** (ou via une session Cowork). Il n'est **jamais écrasé** par un pull GSheet.
- Pas de calcul automatique depuis les étapes : le statut est déclaratif, mis à jour intentionnellement.

**Qualif et date cible — règles de calcul :**

La qualif détermine automatiquement la date cible au moment de la création du sous-projet (ou lors d'un changement de qualif). Le calcul se fait côté serveur.

| Qualif | Signification | Date cible calculée |
|--------|--------------|-------------------|
| P0 | Urgence | Aujourd'hui (si créé avant 17h) ou demain |
| P1 | Cette semaine | Vendredi de la semaine ISO en cours |
| P2 | Prochaines semaines | Vendredi de la semaine ISO S+3 |
| P3 | Backlog sans échéance | 2099-12-31 (sentinel — toujours en bas de tri) |

Ce comportement s'applique identiquement dans le dashboard et lors d'un pull GSheet modifiant la qualif.

La colonne `Cible Date` de la GSheet est **en lecture seule** (calculée). Si une deadline externe précise s'impose (ex : livraison le mercredi de S+1 plutôt que vendredi), elle est notée en **commentaire** — voir point ouvert §6.y sur un éventuel champ `deadline` séparé.

**Date de création :** automatique côté serveur (date du jour à la création). Non modifiable.

**Pull GSheet — ce qui est récupéré :**

| Donnée | Pull autorisé | Remarque |
|--------|--------------|---------|
| Nouveau projet créé dans GSheet | ✅ | Crée l'entrée dans `data.json` |
| Nouveau sous-projet créé dans GSheet | ✅ | Crée l'entrée dans le projet concerné |
| Nouvelle étape créée dans un sous-projet | ✅ | Crée l'étape dans le sous-projet concerné |
| Nom modifié d'un sous-projet | ✅ | Dashboard wins en cas de conflit simultané (⚠ flag de conflit affiché) |
| Nom modifié d'une étape | ✅ | Idem |
| Qualif (P0 à P3) | ✅ | Recalcule automatiquement la date cible |
| Charge (h) | ✅ | Récupérable au niveau sous-projet ET étape |
| RAF (h) | ✅ | Idem |
| Titre | ✅ | Description courte — GSheet souverain au pull si conflit |
| Commentaire | ✅ | GSheet uniquement — créé et modifié dans la GSheet, rapatrié au pull |
| Date cible (`target`) depuis Tâches col E | ✅ | Via `pull-from-gsheet` — si modifiée manuellement dans Tâches col E |
| Date cible (`target`) depuis TCD Projets | ✅ | Via `pull-from-tcd` — vendredi de la dernière semaine avec RAF non nul |
| Statut d'une étape | ❌ | Source de vérité = dashboard uniquement |
| Type (feature, bugfix, récurrent…) | ❌ | Champ GSheet uniquement — non pullé |

> **Acté :** `charge` et `raf` sont des **champs stockés** dans `data.json` au niveau sous-projet — ils alimentent la GSheet (colonnes F/G de l'onglet Tâches) et sont pullables depuis la GSheet. Dans le dashboard, la charge affichée est déduite de la somme des étapes à l'affichage ; mais la valeur stockée dans `data.json` sert de référence pour le sync GSheet.

**Étapes :**
- 4 étapes par défaut à la création d'un sous-projet (voir §1.4), insérées par le serveur.
- La charge et le RAF d'une étape sont renseignés à la création dans Cowork.
- Une étape peut être marquée `na` (désactivée) sans bloquer le statut global du sous-projet.
- Un sous-projet sans étapes est valide (affichage : statut seul).

**Gestion des étapes post-création :**
- **Mise à jour** : `steps` dans le payload fait un **merge par `name`**. Seules les étapes présentes dans le payload sont mises à jour ; les autres restent inchangées. Si `steps` est absent du payload ou vide `[]`, les étapes ne sont pas touchées.
- **Ajout** : inclure dans `steps` une entrée avec un `name` inconnu → créée et ajoutée au sous-projet.
- **Suppression** : marquer l'étape avec `status: "na"` — elle reste dans `data.json` mais est ignorée dans les calculs de charge. La suppression physique d'une étape n'est pas supportée en V2.
- **Réordonnancement** : non supporté en V2. L'ordre des étapes est celui de la création.

**Resynchronisation de la charge sous-projet :**
À chaque appel `POST /api/save-subproject` incluant un champ `steps`, le serveur recalcule et met à jour `charge` du sous-projet comme la somme des `charge` de ses étapes. Le `raf` du sous-projet est recalculé de la même façon. Ces valeurs recalculées sont celles écrites dans `data.json` et poussées vers la GSheet.

**Statut `na` :**
Ajouté au vocabulaire des statuts d'étape uniquement (pas applicable aux sous-projets).

| Code | Label | Description |
|------|-------|-------------|
| `na` | N/A | Étape non applicable à ce sous-projet — ignorée dans les calculs de charge |

### 1.4 Étapes standardisées par défaut

> Version initiale — à réviser après les premières semaines de fonctionnement de V2.

| # | Nom par défaut | Exemples d'usage |
|---|---------------|-----------------|
| 1 | Spécification | Spec rédigée, plan validé en Ping-Pong |
| 2 | Développement | Implémentation complète |
| 3 | Tests         | Tests passants, revue effectuée |
| 4 | Mis en ligne  | Déployé en production ou livré |

Les noms sont modifiables inline dans le dashboard et persistés dans `data.json` via `POST /api/save-subproject`.

### 1.5 data.json remplace les sentinelles V1

En V1, les données dynamiques étaient stockées dans des blocs sentinelles regex directement dans le HTML (`SAVED_STATUS`, `NEW_FEATURES`, `SAVED_DATES`, `SAVED_GSHEET_DATA`). En V2, **tout est dans `data.json`**. Il n'y a aucune sentinelle dans le HTML.

| Donnée V1 (sentinelle HTML) | Équivalent V2 (dans `data.json`) |
|-----------------------------|----------------------------------|
| `SAVED_STATUS` | Champs directs sur les sous-projets (`status`, `steps`, `target`…) |
| `NEW_FEATURES` | Ajout direct dans `projects[n].subprojects` |
| `NEW_PROJECTS` | Ajout direct dans `projects` |
| `SAVED_GSHEET_DATA` | Champs `charge`, `raf`, `commentaire` sur les sous-projets |
| `SAVED_DATES` | Champ `target` sur les sous-projets (supprimé comme sentinelle) |

---

## 2. Workflow Cowork

### 2.1 Ouverture de session

À l'ouverture d'une session Cowork sur un projet, l'agent doit poser la question :

> « Quel projet ? Est-ce un nouveau sous-projet ou la continuation d'un sous-projet existant ? »

- **Nouveau sous-projet** → demander le nom (métier, parlant), créer l'entrée via `POST /api/add-subproject`, déclarer les étapes prévues.
- **Sous-projet existant** → lister les sous-projets `wip`/`spec`/`todo` du projet, sélectionner, charger le contexte.

### 2.2 Clôture de session

À chaque signal de fin ou de pause, l'agent met à jour :
- Le statut du sous-projet (via `POST /api/save-subproject`).
- Les étapes complétées dans la session.

### 2.3 CLAUDE.md — consigne d'ouverture

Le `CLAUDE.md` racine devra être mis à jour pour V2 : la checklist de fin de session cible `planning-lde-v2/DASHBOARD-V2.html` et le modèle sous-projets.

---

## 3. Endpoints serveur V2

Port : **8001**. Fichier serveur : `planning-lde-v2/serve-v2.py`.

### 3.1 Inventaire — comparaison V1 → V2

| Endpoint | V1 | V2 | Décision |
|----------|----|----|---------|
| `GET /` | Sert le HTML | Identique | ✅ Conservé |
| `GET /api/state` | SAVED_DATES + SAVED_STATUS | Retourne `data.json` complet — `{ "projects": [...] }` | ✅ Adapté |
| `GET /api/gsheet/status` | Vérifie connexion GSheets | Identique | ✅ Conservé |
| `GET /api/local-folders` | Liste les dossiers locaux | Identique | ✅ Conservé |
| `POST /api/save-subproject` | — (n'existe pas) | **Nouveau** | 🆕 Clé de voûte V2 |
| `POST /api/add-subproject` | ≈ add-feature | **Nouveau** | 🆕 Remplace add-feature |
| `POST /api/add-project` | Existe | Identique (sans catégorie editorial) | ✅ Conservé simplifié |
| `POST /api/open-folder` | Existe | Identique | ✅ Conservé |
| `POST /api/gsheet/init` | Existe | Adapté (nouveau schéma) | ✅ Adapté |
| `POST /api/sync-to-gsheet/preview` | Existe | Adapté | ✅ Adapté |
| `POST /api/sync-to-gsheet` | Existe | Adapté (1 ligne = 1 sous-projet) | ✅ Adapté |
| `POST /api/pull-from-gsheet/preview` | Existe | Adapté | ✅ Adapté |
| `POST /api/pull-from-gsheet` | Existe | Adapté — lit Tâches (charge/RAF/qualif/commentaire/target col E) | ✅ Adapté |
| `POST /api/pull-from-tcd/preview` | — | **Nouveau** | 🆕 Prévisualise le pull depuis TCD Projets |
| `POST /api/pull-from-tcd` | — | **Nouveau** — lit TCD Projets (raf redistribué + target semaine) | 🆕 |
| `POST /api/save-dates` | Existe | **Supprimé** | ❌ Fusionné dans save-subproject |
| `POST /api/save-features` | Existe | **Supprimé** | ❌ Remplacé par save-subproject |
| `POST /api/move-feature` | Existe | **Supprimé** | ❌ Pas de déplacement dans V2 |

### 3.2 Spécification des endpoints clés

#### `POST /api/save-subproject`

Met à jour un sous-projet existant (statut, steps, dates, owner, charge, raf).
Écrit directement dans `data.json` (merge sur l'id du sous-projet).

```json
Payload : {
  "projectId": "dashboard-datamart",
  "subprojectId": "editorial-examen-s1",
  "status": "done",
  "target": "2026-06-01",
  "charge": 12.0,
  "raf": 0,
  "steps": [
    { "name": "Spécification", "status": "done" },
    { "name": "Développement", "status": "wip" }
  ]
}
Réponse : { "ok": true }
```

Champs optionnels : si un champ est absent du payload, il n'est pas écrasé (merge).

#### `POST /api/add-subproject`

Ajoute un nouveau sous-projet directement dans `data.json` (append dans `projects[n].subprojects`).

```json
Payload : {
  "projectId": "dashboard-datamart",
  "name": "Migration GitLab",
  "status": "todo",
  "owner": "laurent",   // optionnel — nullable
  "target": "2026-06",
  "steps": []   // vide = le serveur insère les 4 étapes standardisées dans data.json
}
Réponse : { "ok": true, "id": "migration-gitlab" }
```

L'`id` est généré par le serveur (slug du `name`). En cas de collision, suffixe `-2`, `-3`, etc.

#### `GET /api/state`

Retourne le contenu complet de `data.json` :

```json
{
  "projects": [
    {
      "id": "dashboard-datamart",
      "name": "Dashboard Datamart",
      "subprojects": [ ... ]
    }
  ]
}
```

#### `POST /api/pull-from-tcd`

Lit l'onglet TCD Projets et met à jour `data.json` avec la répartition ajustée par l'équipe.

Pour chaque ligne sous-projet (préfixe `"- "`) :
- `raf` = somme des colonnes semaines S−1 à S+3
- `target` = vendredi de la **dernière** colonne semaine avec RAF > 0. Python calcule la date ISO réelle depuis la date du jour (ex : S+1 → vendredi de la semaine ISO courante + 1).
- Si toutes les colonnes semaines sont à 0 → `raf = 0`, `target` inchangée.
- Les lignes de projet (sans `"- "`) et la ligne Total sont ignorées.

Les statuts, étapes, charge des étapes et tout autre champ ne sont **pas modifiés** par ce pull.

```
Réponse : { "ok": true, "updated": 5 }  // nombre de sous-projets mis à jour
```

---

## 4. Dashboard HTML V2

Fichier : `planning-lde-v2/DASHBOARD-V2.html`

### 4.1 Structure visuelle

```
┌─────────────────────────────────────────────────┐
│  Stats bar : total sous-projets / wip / todo     │
│  Filtres : [En cours] [À faire] [Spec] [Tous]    │
├─────────────────────────────────────────────────┤
│  ▶ Dashboard Datamart                            │
│     Éditorial Examen S1     ● done   12h / 0h   │
│     Migration GitLab        ○ todo    1h / 1h   │
│     ─ Onglet Cas Pratiques  ◐ wip    3h / 0.5h  │
│       ├ Spécification  ✓                         │
│       ├ Développement  ◐                         │
│       ├ Tests          ○                         │
│       └ Mis en ligne   ○                         │
├─────────────────────────────────────────────────┤
│  ▶ Training V7                                   │
│    ...                                           │
└─────────────────────────────────────────────────┘
```

### 4.2 Comportement

- Projets repliés par défaut (amélioration UX vs V1).
- Clic sur un projet → déplie la liste des sous-projets.
- Clic sur un sous-projet → affiche les étapes (mini-tableau 1 colonne).
- Statut du sous-projet : badge cliquable → menu déroulant (done/wip/review/todo/blocked/spec).
- Statut d'une étape : checkbox ou badge cliquable.
- Dates `created` / `target` : champ inline éditable (comme V1).
- Barre de progression par projet : ratio sous-projets done / total.
- Bouton 📁 sur chaque projet → `POST /api/open-folder`.
- Bouton "+ Sous-projet" sur chaque projet → modal de création.

### 4.3 Périmètre — projets LDE dans V2

À initialiser dans `data.json` :

| Projet | Sous-projets initiaux à créer |
|--------|------------------------------|
| Dashboard Datamart | Éditorial Examen S1, Dashboard Training, Migration GitLab, Cas Pratiques |
| Training V7 | Métadonnées Quiz, Nouvelles modalités (Méli-mélo), Textes à trous |
| Examens V7 | Migration V7 |
| Cas Pratiques | Convertisseur WpProQuiz |
| Planning LDE | Simplification V2 (ce projet !) |
| Brief Équipe | (à définir) |

Les projets MHO/ESL (Datamart API, Opquast Companion, SSO, Admin, etc.) sont **exclus** de `data.json` V2.

---

## 5. Google Sheets V2

**Nouvelle Google Sheets V2** — nouveau fichier, nouvelle authentification OAuth (pas de réutilisation du spreadsheet V1). Le `spreadsheet_id` sera renseigné dans `serve-v2.conf.json` après création.

3 onglets : **Tâches**, **Semaines** (masqué), **TCD Projets**.

**Architecture GSheet :**

```
data.json → push → Tâches
                     ↓ (formules GSheet)
                  Semaines  ← masqué, lecture seule
                     ↓ (Python copie les valeurs au push)
                  TCD Projets ← l'équipe édite la répartition
                     ↓ (pull)
data.json ← raf + target mis à jour
```

- Python pousse les données vers **Tâches** uniquement.
- **Semaines** est une feuille masquée 100 % formules — elle calcule automatiquement le RAF par sous-projet par semaine depuis Tâches. Jamais éditée directement.
- Au push, Python copie les valeurs calculées de Semaines dans **TCD Projets** (écrasement). L'équipe peut ensuite y redistribuer le RAF entre semaines.
- Au pull, Python lit TCD Projets et met à jour `raf` et `target` dans `data.json` (voir §1.3).
- Pas de référence circulaire : Semaines lit Tâches, TCD est écrit par Python — les deux ne se référencent pas.

**Bibliothèque Python GSheet : `gspread`.** Dépendance à ajouter : `pip install gspread`. Ne pas utiliser `google-api-python-client` (V1) — V2 repart sur gspread.

### 5.1 Onglet "Tâches"

1 ligne = 1 sous-projet. Structure validée sur le modèle `modeles-formules.xlsx` (2026-05-14).

| Col | Nom | Source de vérité | Contenu |
|-----|-----|-----------------|---------|
| A | Projet | Dashboard (push) | Alias du projet |
| B | Sous-projet | Dashboard (push) | Nom du sous-projet |
| C | Type | **GSheet uniquement** | Feature / Bugfix / Récurrent / Support / Autre — non pullé |
| D | Prio. | Dashboard (push) | P0 / P1 / P2 / P3 |
| E | Cible | Calculée (qualif) | Lecture seule — calculée côté serveur depuis la qualif |
| F | Charge (h) | GSheet | Estimé total en heures |
| G | RAF (h) | GSheet | Reste à faire en heures |
| H | Titre | Dashboard / GSheet | Description courte du sous-projet — GSheet souverain au pull si conflit |
| I | Avanc. | Dashboard (push) | TERMINÉ / EN COURS / REVUE / SPEC / À FAIRE / STAND BY |
| J | Commentaire | **GSheet uniquement** | Notes libres — non pullé vers le dashboard |
| K | Semaine | Formule | Voir `formules.md` |
| L | Année | Formule | Voir `formules.md` |

### 5.2 Onglet "Semaines" (masqué)

Feuille de calcul intermédiaire, **masquée dans GSheet** ("Masquer la feuille"). 100 % formules — jamais éditée directement, jamais poussée par Python.

- Col A : liste des projets et sous-projets, auto-peuplée via QUERY/REDUCE depuis Tâches.
- Col B : total RAF toutes semaines.
- Cols C–G : RAF par sous-projet par semaine S−1 à S+3 (formules SIERREUR/SOMME/FILTER depuis Tâches).
- Lignes 2–3 : totaux heures et jours.

Rôle : servir de source de valeurs précalculées que Python copie dans TCD Projets au push. Toutes les formules sont définies dans `formules.md` (référence absolue — voir §5.4).

### 5.3 Onglet "TCD Projets"

Vue synthétique hebdo S−1 / S0 / S+1 / S+2 / S+3, **éditable par l'équipe** pour ajuster la répartition de la charge.

**Au push :** Python copie les valeurs calculées de l'onglet Semaines dans TCD Projets (écrasement complet). Les cellules contiennent des valeurs brutes, pas des formules — elles sont donc modifiables.

**Après le push :** l'équipe peut redistribuer le RAF entre semaines (ex : déplacer des heures de S-1 à S+1 pour un sous-projet qui a pris du retard).

**Au pull :** Python lit TCD Projets et met à jour dans `data.json` pour chaque ligne sous-projet :
- `raf` = somme des colonnes semaines (RAF total redistribué)
- `target` = vendredi de la dernière semaine avec RAF non nul (= semaine de livraison prévue). Python convertit S−1/S0/S+1… en date ISO réelle à partir de la date du jour.
- Si toutes les colonnes semaines sont à 0 → `raf = 0`, `target` inchangée.

Col A (liste projets/sous-projets) : copiée depuis Semaines au push — non modifiable par l'équipe.

### 5.4 Règles de conversion heures → jours

**Base : 1 jour = 7 heures. Arrondi au 0,1j supérieur.**

Formule GSheet : `=PLAFOND(h/7;0,1)`

| Heures | Calcul | Résultat |
|--------|--------|---------|
| 0h | 0/7=0 | 0j |
| 1h | 1/7=0,14 | 0,2j |
| 3h | 3/7=0,43 | 0,5j |
| 3,5h | 3,5/7=0,5 | 0,5j |
| 4h | 4/7=0,57 | 0,6j |
| 7h | 7/7=1 | 1j |
| 8h | 8/7=1,14 | 1,2j |
| 14h | 14/7=2 | 2j |

Formule Python : `math.ceil((h / 7) * 10) / 10` (arrondi au 0,1 supérieur).

### 5.5 Référence obligatoire pour les formules GSheet

**Toutes les formules GSheet insérées par le code Python (init, push) sont celles définies dans `planning-lde/formules.md`. Ce fichier est la référence absolue.**

Règles :
- Ne jamais convertir une formule depuis l'xlsx ni la réécrire à partir de la spec — utiliser uniquement la formule GSheet du `formules.md`.
- Si une formule du `formules.md` semble incohérente avec la spec, signaler à LDE plutôt qu'improviser.
- `formules.md` fait foi sur toute autre source (spec, xlsx, mémoire de session).

> Ce fichier documente les formules testées et validées directement dans GSheet (syntaxe locale FR, séparateurs `;`).

### 5.6 Règle : non-intervention sur la mise en forme

**L'initialisation (`POST /api/gsheet/init`) et le pull (`POST /api/pull-from-gsheet`) ne touchent jamais à la mise en forme de la GSheet.**

Sont explicitement hors périmètre de ces opérations :

- Largeur des colonnes et hauteur des lignes
- Couleur de texte et couleur d'arrière-plan des cellules
- Police et taille du texte
- Mise en forme conditionnelle
- Filtres actifs
- Listes de validation de saisie (menus déroulants)

Ces éléments de mise en forme sont créés et gérés manuellement dans la GSheet. Le code Python n'utilise que les API de lecture/écriture de valeurs et de formules (`values.update`, `values.append`). Toute API de formatage (`batchUpdate` sur `format`, `setDataValidation`, `addConditionalFormatRule`…) est interdite dans ces endpoints.

> **Raison :** la mise en forme est investie une fois (création + ajustements manuels) et doit survivre aux pushs et pulls quotidiens. La laisser sous contrôle humain évite les régressions visuelles.

### 5.7 Ce qui disparaît vs V1

- Onglet "Liste Projet" (absorbé par TCD Projets)
- Onglet "Semaines" V1 visible → remplacé par Semaines masqué (moteur de calcul) + TCD Projets éditable
- Colonne `Cible Date` éditable (remplacée par calcul depuis qualif)
- Colonnes `Dev`, `Créé le`, `Catégorie`, `NEW` (supprimées)
- Sentinelles HTML `NEW_FEATURES` / `SAVED_DATES` / `SAVED_STATUS` / `SAVED_GSHEET_DATA` (supprimées — tout dans `data.json`)

---

## 6. Points ouverts (à valider en Ping-Pong avant implémentation)

| # | Question | Décision |
|---|----------|---------|
| 6.1 | Faut-il un onglet "Terminés" dans la GSheet V2, ou les done sont filtrés par défaut ? | ✅ Filtre sur statut dans Tâches, TERMINÉ inclus dans les options |
| 6.2 | Les étapes d'un sous-projet "todo" sont-elles créées avec le sous-projet, ou à la demande ? | ✅ Par défaut : 4 étapes standardisées créées à la création |
| 6.3 | Doit-on conserver l'historique JSONL dans V2 ? | ✅ Oui |
| 6.4 | Port 8001 : `terminal.txt` séparé pour V2 ? | ✅ Oui |
| 6.5 | GSheet V2 = nouveau fichier + nouvelle OAuth | ✅ Nouveau fichier (`spreadsheet_id`: `1RY1SCZAW5PPG05Cbpvup5pAe6BWvUhy_UZ4DPwl3Wew`), `client_secret.json` copié depuis V1, `token.json` auto-créé au premier appel |
| 6.y | Champ `deadline` séparé vs commentaire ? | ✅ Dans le commentaire |
| 6.z | Structure détaillée des onglets GSheet | ✅ Validée sur `modeles-formules.xlsx` (2026-05-14) |
| 6.f | Mise en forme GSheet : intervention du code Python ? | ✅ Jamais — init et pull n'écrivent que les valeurs/formules, pas le format (§5.6) |
| 6.v | Statut `REVUE` : statut à part entière ou sous-état de EN COURS ? | ✅ Statut à part entière — phase de tests/relecture |
| 6.w | Règles de conversion heures → jours (base + arrondi) | ✅ 1j = 7h, `PLAFOND(h/7;0,1)` GSheet — `math.ceil((h/7)*10)/10` Python |

---

## 7. Plan d'implémentation (pour Claude Code)

Ordre séquentiel recommandé :

1. **Scaffold** : créer `planning-lde-v2/`, CLAUDE.md local, `DASHBOARD-V2.html` (shell UI pur, sans données), `data.json` vide (`{"projects": []}`).
2. **serve-v2.py Phase 1** : serveur minimal — sert le HTML, `/api/state`, `/api/save-subproject`, `/api/add-subproject`, `/api/add-project`, `/api/open-folder`. Tests fonctionnels.
3. **Dashboard HTML** : render des projets/sous-projets, badges de statut, étapes, barre de progression. Fonctionnel en `file://`.
4. **serve-v2.py Phase 2** : sync GSheets (init, push, pull) avec le nouveau schéma 1 ligne = 1 sous-projet. **Formules GSheet : utiliser exclusivement `planning-lde/formules.md` — aucune conversion depuis l'xlsx ni réécriture.**
5. **Données initiales** : remplir `data.json` avec les projets LDE et leurs sous-projets (voir §4.3).
6. **CLAUDE.md racine** : ajouter `planning-lde-v2` dans la table des projets, mettre à jour la checklist de fin de session.

---

## 8. Fichiers à créer

| Fichier | Rôle |
|---------|------|
| `planning-lde-v2/SPEC-PLANNING-V2.md` | Ce document |
| `planning-lde-v2/CLAUDE.md` | Instructions projet V2 |
| `planning-lde-v2/DASHBOARD-V2.html` | Dashboard source de vérité V2 |
| `planning-lde-v2/serve-v2.py` | Serveur local V2 (port 8001) |
| `planning-lde-v2/serve-v2.conf.json` | Config : spreadsheet_id |
| GSheet — onglet **Semaines** | Feuille masquée, formules depuis `formules.md`, jamais modifiée par Python |
| GSheet — onglet **TCD Projets** | Feuille éditable, valeurs poussées depuis Semaines au push, pullée pour raf + target |
| `tests-e2e-python/planning-lde/` | Suite pytest V2 (multi-fichiers, style cas-pratiques) |
| `planning-lde-v2/terminal.txt` | (gitignored) Commande de démarrage |

---

## Notes à voir

- **Checklist de fin de session** : ajouter un "Ce qui a été livré aujourd'hui" dans le retour Cowork ou Claude Code — résumé synthétique des sous-projets avancés ou terminés dans la session.
