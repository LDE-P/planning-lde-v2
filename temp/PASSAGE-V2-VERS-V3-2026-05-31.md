# Passage de relais — Planning LDE V2 → nouvelle session « PLANNING LDE V3 »

> **🛑 DOC LARGEMENT OBSOLÈTE (2026-06-04)** — la synchronisation GSheet a été
> **définitivement abandonnée et supprimée du code** le 2026-06-03 (découplage total).
> Les sections §2 (statut `fail` : FAIT), §3.2 (boutons : supprimés), §3.3 (OAuth : supprimé),
> §5 (bugs push/pull : sans objet) et §8 ne doivent **plus être exécutées**.
> → Lire à la place : **`temp/PASSAGE-RELAIS-MAINTENANCE-2026-06-04.md`**

**Date du passage** : 2026-05-31 (dimanche, ~15h15 Europe/Paris)
**Modèle source** : claude-opus-4-7 (Cowork)
**Modèle cible** : nouvelle session (changement de modèle Claude par LDE)
**Auteur du passage** : session Cowork ayant travaillé les 2026-05-28 et 2026-05-31

> ⚠️ **Note sur le nom « V3 »** : ce nom de session ne correspond **pas** (à ma connaissance) à une nouvelle version du dashboard Planning. C'est simplement le nom retenu par LDE pour la nouvelle session après changement de modèle. La référence « V3 » apparaît néanmoins dans `notes-todo.md` comme **futur scope** pour la consolidation GSheet (note Gemini). À clarifier avec LDE si confusion.

---

## 1. À LIRE DANS CET ORDRE EXACT — avant toute action

1. **`/Users/laurentdenis/Documents/GIT/CLAUDE.md`** — règles transverses GIT (priorité absolue, contient les Garde-fous 1-10 et la checklist de fin de session)
2. **`planning-lde-v2/CLAUDE.md`** — règles du projet (schéma `data.json`, push/pull GSheet, conventions)
3. **`planning-lde-v2/notes-todo.md`** — todos prioritaires pour la reprise (lecture obligatoire en début de session selon convention)
4. **`planning-lde-v2/notes-gsheet-gemini-2026-05-28.md`** — note Gemini marquée « pour V3 » (consolidation GSheet)
5. **Ce document** (`temp/PASSAGE-V2-VERS-V3-2026-05-31.md`) — synthèse de la mémoire de session

---

## 2. TÂCHE PRIORITAIRE À LA REPRISE — ajout du statut `fail` au dashboard

**LDE a explicitement noté cette tâche comme « À TRAITER EN PREMIER »** dans `notes-todo.md` (commit `f69a6de`).

### Contexte

Le statut `fail` a été ajouté au schéma `data.json` (cf. `planning-lde-v2/CLAUDE.md`) pour tracer les sous-projets abandonnés après échec. **Il est déjà utilisé dans `data.json`** :
- SP `generation-snippets-v1` sous **Banc de tests** (status `fail`, commit `df264fe` fait par une session parallèle entre le 28 et le 31 mai)
- Une step « Audit persona — ÉCHEC » dans ce même SP

### Trois fichiers à modifier (ordre suggéré)

#### 2.1 `serve-v2.py`
- Ajouter `'fail'` dans `_VALID_STATUSES` (ligne ~30)
- Ajouter `'fail'` dans `_STATUS_TO_GS` (valeur GSheet suggérée : `'FAIL'`)
- `_STATUS_FROM_GS` est généré automatiquement par dict comprehension → pas de changement

#### 2.2 `DASHBOARD-V2.html`
- Ajouter la variable CSS `--fail` (couleur suggérée : `#f97316`, orange brûlé — distinct de `blocked`/rouge et `todo`/gris)
- Ajouter `.status-fail` dans le bloc des status-badge (vers ligne 331-337 dans le HTML actuel — vérifier) — même pattern que `.status-blocked`
- Ajouter le label d'affichage `'fail'` dans la fonction JS qui traduit les statuts en texte lisible (chercher les labels `'blocked'`, `'done'`, etc.) — label suggéré : **« Échec »**
- Ajouter la même classe dans le bloc `.step-status-badge` si les steps ont leur propre jeu de badges

#### 2.3 (Implicite) `ui.js` ou `app.js`
Vérifier que la fonction de rendu des badges connaît `fail`. Probablement dans `ui.js` ou via une constante partagée. Lire avant éditer.

### Contraintes (de LDE)

- **Lire les blocs concernés avant d'éditer** (ne pas modifier à l'aveugle)
- **Pas de modification hors des trois points ci-dessus**
- Commit dans `planning-lde-v2/` après validation

### Vérification attendue

Après modification, ouvrir `data.json`, confirmer que le SP `generation-snippets-v1` (status `"fail"`) s'affiche correctement dans le dashboard avec le badge orange **« Échec »**.

---

## 3. ÉTAT DU PROJET AU PASSAGE

### 3.1 Git

- **Dépôt** : `https://github.com/LDE-P/planning-lde-v2` (compte LDE-P, token OAuth dans `.git/config`)
- **Cowork peut commit ET push** sans intervention LDE
- **Branche active** : `main`
- **Dernier commit poussé** : `bfa5036` (commentaire debug-synchro-icloud — scope toutes sessions Cowork)
- **Modification non-commitée** au passage : `Ameliorations.md` (modifs d'une session parallèle, non touchées par moi)

### 3.2 Boutons GSheet désactivés dans le dashboard

**Mesure de protection temporaire** ajoutée le 2026-05-28 (commit `29e8ec8`) suite à un incident de perte de données :

| Bouton | État |
|---|---|
| Init | 🔒 disabled |
| Format | ✅ actif (manuel, peu de risque) |
| ⊡ Modèles | 🔒 disabled |
| ← Pull TCD | 🔒 disabled |
| ← Pull Tâches | 🔒 disabled |
| Push → | 🔒 disabled |

Réactiver (retirer `disabled` dans `DASHBOARD-V2.html`) **uniquement après** diagnostic des bugs pull/push (cf. §5).

### 3.3 Token OAuth Google Sheets

**EXPIRÉ** depuis le 2026-05-28 (`invalid_grant: Token has been expired or revoked.`).

Procédure de régénération :
1. Lancer `serve-v2.py` (port 8001)
2. `rm token.json`
3. Déclencher une action GSheet (mais boutons désactivés — il faudra peut-être réactiver Pull TCD temporairement, ou appeler l'API directement via curl)
4. Cliquer **Autoriser** immédiatement dans la fenêtre OAuth (timeout court côté callback localhost)
5. Vérifier que `token.json` est régénéré

L'app étant en mode test côté Google Cloud Console, les refresh tokens expirent automatiquement au bout de 7 jours s'ils ne sont pas utilisés.

### 3.4 favicon et `favicons-planning/`

- **`favicon.svg` à la racine** du projet : lettre P bleu (#3b82f6) — versionné (commit `3f59396`)
- **Lien `<link rel="icon">` dans `DASHBOARD-V2.html`** : versionné
- **`favicons-planning/`** (6 SVG + preview.html) : **hors du repo git**, dans le folder Cowork `Planning LDE V2/favicons-planning/` (folder utilisateur séparé) — à décider si on les copie dans le repo pour versionnement

---

## 4. CHRONOLOGIE DE LA SESSION 2026-05-28 — incident GSheet

Ordre des événements (mémoire critique pour comprendre le contexte) :

1. **Demande initiale** : créer backup data.json + ajouter 12 sous-projets au projet `gsheet-datamart`
2. **Backup ponctuel** créé dans `planning-lde-v2/backups/` :
   - `data-2026-05-28.json` (snapshot pré-modifs)
   - `data-archives-2026-05-28.json`
3. **12 SPs ajoutés** à GSheet Datamart (commit `d85c3f5`) avec champs minimaux (Récurrent pour 2, vide pour les autres)
4. **Désarchivage `generateur-cas-pratiques-v2`** côté `data-archives.json` (commit `8a59356`) — modification d'une session parallèle, non liée à mon scope mais récupérée dans mes commits
5. **Action LDE en parallèle** dans le dashboard et la GSheet :
   - Push 1 (réussi, propage les 12 SPs)
   - Init (vide les 3 onglets)
   - Push 2 (restauration affichage 12 SPs)
   - Édition manuelle GSheet : Type, prio, Cible, Titre, Commentaire
   - Pull (silencieusement non capté côté `data.json` — bug)
   - Édition charge/raf dans le dashboard
   - Push final (qui a écrasé col D-I + col C et J malgré spec — **deuxième bug**)
6. **Token OAuth expire** à un moment de la chaîne
7. **Constat de la perte** : Type/prio/Cible/Titre/Commentaire vides côté GSheet ET côté data.json
8. **Tentative de récupération** via Google Sheets version history : impossible (dernière version utile = 2026-05-27)
9. **LDE fournit un CSV** (`uploads/gsheet-planning.csv`, encodage mac_roman) avec les valeurs
10. **Reconstruction** des 12 SPs depuis le CSV (commit `9fec061`)
11. **Désactivation préventive** des boutons GSheet (commit `29e8ec8`)
12. **Création favicon** lettre P (commit `3f59396`)
13. **Sauvegarde note Gemini** TCD sur recommandations GSheet (commits `ab5f513`, `0c485e7`) — pour V3
14. **Mise à jour `notes-todo.md`** + tâche prioritaire `fail` (commits `4f49d4e`, `f69a6de`)

### Commits poussés par cette session (8 au total)

```
d85c3f5  feat(gsheet-datamart): backup data 2026-05-28 + ajout 12 sous-projets
8a59356  chore(archives): retrait generateur-cas-pratiques-v2
9fec061  feat(gsheet-datamart): reconstruction 12 SPs depuis CSV utilisateur
29e8ec8  chore(dashboard): désactivation temporaire Init/Modèles/Push/Pull GSheet
3f59396  feat(dashboard): favicon lettre P (#3b82f6)
4f49d4e  docs(notes-todo): maj session 2026-05-28
ab5f513  docs: note Gemini sur erreurs TCD GSheet
0c485e7  docs(notes-todo): marquer note Gemini comme reprise V3
f69a6de  docs(notes-todo): tâche prioritaire reprise — ajouter statut 'fail'
```

### Commits faits PAR D'AUTRES sessions entre mes interventions

```
873d4f0  chore: gestion-compte — +SP formules-rtv-v4 + simulation-retraite (entre 28 et 31)
f742554, d515f4e, 9c782de  (commits Training V7 docs, génération snippets, jouabilité)
b64a8fc  feat(planning): blindage écriture atomique data.json + garde anti-wipe + backups
df264fe  chore(planning): génération snippets V1 (fail) + V2 sous Banc de tests
4493fc3, 807f146, bfa5036  (SP debug-synchro-icloud-git)
```

**Notable** : `b64a8fc` adresse un des bugs que j'avais noté (anti-wipe data.json). À vérifier si ça aussi le bug push/pull GSheet, ou seulement l'atomicité d'écriture.

---

## 5. BUGS OUVERTS — pull et push GSheet

### Bug 1 : pull silencieusement non capté

**Symptôme** : le pull du 2026-05-28 (depuis la GSheet vers `data.json`) n'a pas écrit les éditions manuelles GSheet (Type, qualif, target, titre, commentaire) dans `data.json`.

**Évidence** : après le pull, `data.json` n'avait toujours pas les valeurs saisies à la main par LDE dans la GSheet. Seuls les `charge`/`raf` (édités ensuite dans le dashboard) sont apparus.

**Hypothèses** :
- Le pull a peut-être échoué silencieusement (auth ou autre) sans toaster d'erreur
- Le pull a réussi mais l'écriture vers `data.json` a un bug (peut-être lié au blindage atomique de `b64a8fc` ?)
- Le matching par alias/nom (col A/B) ne fonctionnait pas — les espaces fantômes signalés par Gemini ont peut-être joué ici

**À investiguer** : `serve-v2.py`, fonctions `_pull_from_gsheet()` ou équivalent. Vérifier réponse 200 + flux d'écriture vers `data.json`. Logs.

### Bug 2 : push écrasant col C (Type) et J (Commentaire) malgré spec

**Symptôme** : le push final du 2026-05-28 a vidé col C et col J côté GSheet, alors que la spec dit explicitement que push ne touche que A-B, D-I, K-L.

**Évidence** : LDE confirme « les colonnes Type/prio/Cible/Titre/Commentaire de toutes les lignes du projet GSheet Datamart sont à nouveau vides » après le push final.

**Hypothèses** :
- Le `batch_clear` cible peut-être plus que prévu (range mal défini)
- Un Init précédent a peut-être laissé les colonnes vides et push 2 + push final n'ont jamais eu d'occasion de les remplir — mais ça n'explique pas pourquoi LDE pense les avoir saisies (vérifier la chronologie)
- Le code a peut-être divergé de la spec depuis qu'elle a été écrite

**À investiguer** : `serve-v2.py`, fonction `_push_to_gsheet()`. Vérifier les ranges des `batch_clear` et `batch_update`.

### Conseil

**Avant de toucher au code push/pull**, lire `notes-gsheet-gemini-2026-05-28.md` (recommandations Gemini sur les espaces fantômes, Tableaux Dynamiques Google, etc.) — peut éclairer le bug 1.

---

## 6. MÉMOIRE DE SESSION — détails non écrits ailleurs

### 6.1 Conventions utilisateur observées (LDE)

- **Style très direct, peu de cérémonie** : LDE écrit court, parfois avec typos (« vives » au lieu de « vides », « elis » au lieu de « relis »)
- **Aime les listes structurées et les tableaux** dans les réponses
- **Travaille parfois de nuit** (l'incident GSheet a commencé à 3h du matin) — la convention CLAUDE.md de signaler l'heure entre 0h-6h s'applique
- **Préfère les commits séparés** quand plusieurs changements n'ont pas le même contexte (cf. choix « commits séparés » pour data-archives + GSheet Datamart)
- **Apostrophe courbe obligatoire** dans tous les libellés (U+2019, convention CLAUDE.md racine)

### 6.2 Détails techniques découverts dans cette session

- **Encodage des CSV exportés depuis macOS** : `mac_roman` (pas UTF-8 ni Windows-1252) — important pour parser les exports manuels de LDE
- **Format `target` dans `data.json`** : DD/MM/YYYY en pratique (pas YYYY-MM-DD comme indiqué dans la spec). Match l'existant pour rester cohérent.
- **`target=""` est très fréquent** dans les SPs (champ optionnel)
- **`charge=0.0`, `raf=0.0`** est la valeur par défaut pour les SPs sans estimation
- **`type=""` (vide)** est valide en `data.json` même si la spec autorise Feature/BugFix/Récurrent/Support/Autre

### 6.3 Décisions prises (à respecter ou à reconsidérer)

- **`favicon.svg` au choix lettre P (option 03)** parmi 6 propositions. Les 5 autres sont conservées dans `Planning LDE V2/favicons-planning/` (folder Cowork hors repo).
- **Boutons Init/Modèles/Push/Pull/Pull TCD désactivés** (Format laissé actif). Bouton **Format** est resté actif car « manuel, peu de risque » — décision validée par LDE.
- **Note Gemini déplacée vers le scope V3** par LDE — pas urgent en V2.

### 6.4 Convention « Maintenance en cours / terminée »

LDE a une convention de verrou de coordination entre sessions parallèles via `GIT/.maintenance-lock`. Vérifier en début de session. Au passage : **pas de verrou actif**.

---

## 7. FICHIERS CRÉÉS OU MODIFIÉS PAR CETTE SESSION

### Versionnés sur `LDE-P/planning-lde-v2`

| Fichier | Action |
|---|---|
| `data.json` | Modifié — 12 SPs ajoutés/reconstruits dans GSheet Datamart |
| `data-archives.json` | Modifié — retrait `generateur-cas-pratiques-v2` |
| `DASHBOARD-V2.html` | Modifié — boutons GSheet disabled + lien favicon |
| `favicon.svg` | Créé — lettre P |
| `notes-todo.md` | Modifié — tâche prioritaire `fail` + récap session |
| `notes-gsheet-gemini-2026-05-28.md` | Créé — note Gemini TCD pour V3 |
| `backups/data-2026-05-28.json` | Créé — snapshot pré-modifs |
| `backups/data-archives-2026-05-28.json` | Créé — idem |

### Hors repo git (folder Cowork `Planning LDE V2/`)

| Fichier | Action |
|---|---|
| `favicons-planning/preview.html` | Créé |
| `favicons-planning/01-calendar-check.svg` | Créé |
| `favicons-planning/02-gantt-bars.svg` | Créé |
| `favicons-planning/03-letter-p.svg` | Créé (= favicon retenu) |
| `favicons-planning/04-kanban.svg` | Créé |
| `favicons-planning/05-clipboard-list.svg` | Créé |
| `favicons-planning/06-target-arrow.svg` | Créé |

### Documents de référence (extérieurs au projet mais consultés)

- `/Users/laurentdenis/Documents/GIT/CLAUDE.md` — règles transverses
- `/Users/laurentdenis/Documents/GIT/planning-lde-v2/CLAUDE.md` — règles projet

---

## 8. ACTIONS À FAIRE DANS L'ORDRE — pour la nouvelle session

1. **Lire CLAUDE.md racine + CLAUDE.md projet + notes-todo.md + ce passage**
2. **Vérifier l'heure** (rappel coucher si > 21h)
3. **Vérifier `.maintenance-lock`** : `ls /Users/laurentdenis/Documents/GIT/.maintenance-lock`
4. **`git status` et `git log -5`** dans `planning-lde-v2/` pour voir l'état exact à l'instant de reprise
5. **Demander à LDE confirmation du périmètre** : « la tâche prioritaire est-elle bien `ajout statut fail` ? Y a-t-il d'autres choses à reprendre avant ? »
6. **Si confirmation `fail`** : appliquer la procédure en §2 (lire avant éditer chaque fichier, faire un plan, valider avant commit)
7. **À la fin** : checklist de fin de session (CLAUDE.md §Mise à jour en fin de session)

---

## 9. POINTS D'ATTENTION TRANSVERSES

- **Ne pas pusher sur GitLab** (Dashboard Datamart, autre projet — Cowork interdit côté GitLab)
- **Ne pas modifier de fichiers sous `opq-devcontainer-MHO/`** sans validation explicite (dépôt partagé équipe)
- **Apostrophe courbe** dans tous les libellés générés
- **Liens `computer://` systématiques** après chaque modification de fichier (rendu Finder peu fiable autrement)
- **Format commits sur une ligne** avec `\n` pour les messages multilignes (sinon casse au copié-collé terminal macOS)

---

## 10. CONTACTS / RESSOURCES

- **LDE** : Laurent Denis — laurent.denis@opquast.com
- **Repo planning** : https://github.com/LDE-P/planning-lde-v2
- **GSheet planning** : https://docs.google.com/spreadsheets/d/1RY1SCZAW5PPG05Cbpvup5pAe6BWvUhy_UZ4DPwl3Wew/
- **Dashboard local** : http://localhost:8001 (lancement : `python3 serve-v2.py`)

---

*Fin du passage de relais. Bonne reprise.*
