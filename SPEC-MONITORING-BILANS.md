# SPEC — Monitoring automatique des bilans de session

**Projet :** Planning LDE V2  
**Sous-projet :** Monitoring bilans de fin de session  
**Statut :** SPEC (draft)  
**Auteur :** LDE + Cowork  
**Date :** 2026-05-16  

---

## 1. Contexte et objectif

Les bilans de session (`suivi-qualite/bilans/YYYY-MM-DD[-sujet].md`) sont produits à chaque clôture de session Cowork. Ils contiennent deux sections à haute valeur :

- **Prompt initial** — évaluation de la qualité du prompt de démarrage
- **Suggestions d'amélioration** — pistes workflow, process, outillage identifiées en cours de session

Aujourd'hui ces données sont produites mais jamais agrégées : les suggestions restent dans chaque bilan individuel, certaines ✅ marquées comme intégrées, d'autres perdues dans le flux. Il n'existe pas de vue d'ensemble permettant de décider quoi prioriser, ni de suivi de l'intégration des suggestions dans le process.

**Objectif :** mettre en place un monitoring qui :
1. Extrait automatiquement les deux sections cibles de chaque bilan
2. Produit un **document de synthèse des prompts** (support de session de réflexion)
3. Produit un **tableau de suivi des suggestions** (backlog priorisé, état d'avancement)

---

## 2. Périmètre

### Fichiers source

- Répertoire : `GIT/suivi-qualite/bilans/`
- Format : `YYYY-MM-DD.md`, `YYYY-MM-DD-sujet.md`
- Exclusion : `README.md`
- Tous les bilans existants + nouveaux bilans au fil du temps

### Sections à extraire (fuzzy matching sur les titres H2)

Les titres de sections varient d'un bilan à l'autre. Le parser doit reconnaître les variantes observées :

| Section cible | Variantes observées |
|---|---|
| **Prompt initial** | `## Le prompt initial était-il suffisant ?` · `## Prompt initial — évaluation` · `## Le prompt initial a-t-il suffisamment défini la tâche ?` · `## Le prompt initial a-t-il bien défini la tâche ?` |
| **Suggestions** | `## Suggestions d'amélioration` · `## Suggestions d'amélioration workflow` · `## Suggestions d'amélioration du workflow` · `## Suggestions d'amélioration du workflow Cowork ↔ Claude Code` |

**Stratégie de matching :** correspondance exacte sur les titres canoniques en priorité. Fallback fuzzy (mots-clés `prompt initial`, `suggestions` sur le texte normalisé du titre H2) uniquement si la correspondance exacte échoue — filet de sécurité pour les bilans futurs qui s'écarteraient du template.

> ✅ Tous les bilans existants ont été normalisés le 2026-05-16 — le fallback fuzzy ne s'applique pas au corpus actuel.

### Métadonnées extraites depuis le frontmatter / entête

| Champ | Source | Exemple |
|---|---|---|
| `date` | nom de fichier | `2026-05-15` |
| `sujet` | nom de fichier (après la date) | `livre-oq`, `vue-docs` |
| `projet` | champ `**Projet :**` dans l'entête | `Planning LDE V2`, `Livre OQ` |
| `clôture` | champ `**Clôture :**` ou `**Heure de clôture :**` | `16:50` |

---

## 3. Livrables

### 3.1 — Synthèse des retours sur les prompts initiaux

**Fichier :** `suivi-qualite/synthese-prompts.md`  
**Régénéré** à chaque exécution de l'agent (fichier écrasé ou versionné par date — point ouvert A1)

**Structure proposée :**

```markdown
# Synthèse — Qualité des prompts initiaux

> Généré le YYYY-MM-DD depuis N bilans. Dernière session incluse : YYYY-MM-DD.

## Vue d'ensemble

- Sessions analysées : N
- Prompts jugés suffisants : X (xx%)
- Prompts partiellement suffisants : Y
- Prompts insuffisants : Z

## Ce qui manque systématiquement dans les prompts

[Synthèse thématique des lacunes récurrentes]

## Ce qui fonctionne bien

[Patterns de prompts efficaces]

## Extrait par session

| Session | Projet | Évaluation | Résumé |
|---|---|---|---|
| 2026-05-15 (vue-docs) | Planning LDE V2 | ✅ Suffisant | ... |
| 2026-05-15 (livre-oq) | Livre OQ | ⚠️ Partiel | ... |
| ...

## Recommandations pour les prochains prompts

[Liste actionnelle des améliorations à apporter aux prompts de démarrage]
```

La synthèse thématique (section "Ce qui manque / Ce qui fonctionne") est produite par appel LLM sur le corpus agrégé des sections prompt (voir §4 — Agent).

### 3.2 — Tableau de suivi des suggestions

**Fichier :** `suivi-qualite/suivi-suggestions.md`  
**Mode :** append intelligent — les nouvelles suggestions sont ajoutées, les existantes ne sont pas dupliquées (déduplication par similarité — point ouvert A2)

**Structure proposée :**

```markdown
# Suivi des suggestions d'amélioration

> Mis à jour le YYYY-MM-DD. N suggestions totales · X intégrées · Y en attente · Z à arbitrer.

## Backlog actif

| # | Suggestion | Projet | Source | Statut | Priorité | Complexité | Notes |
|---|---|---|---|---|---|---|---|
| 1 | Toujours proposer le commit compact (1 ligne) en zsh | — | 2026-05-15 | ⏳ À faire | P2 | Faible | ... |
| 2 | Audit des fichiers sources en début de session | — | 2026-05-15 (livre-oq) | ⏳ À faire | P1 | Faible | ... |
| ... |

## Suggestions intégrées

| # | Suggestion | Source | Intégré le | Où |
|---|---|---|---|---|
| — | Règle pour les tests destructifs (Règle 9) | 2026-05-16 | 2026-05-15 | CLAUDE.md |
| — | Vérifier l'heure en début de session | 2026-05-16 | 2026-05-15 | CLAUDE.md |
| ... |
```

**Colonnes — définitions :**

| Colonne | Valeurs | Source |
|---|---|---|
| Statut | `⏳ À faire` · `🔄 En cours` · `✅ Intégré` · `❌ Rejeté` · `🔍 À arbitrer` | Agent (initial) + LDE (validation) |
| Priorité | `P0` à `P3` (selon impact estimé sur le workflow) | Agent (proposition LLM) + LDE |
| Complexité | `Faible` · `Moyenne` · `Élevée` | Agent (proposition) + LDE |
| Projet | Nom canonique si la suggestion est spécifique à un projet, sinon `—` | Extrait du bilan ou inféré |

**Règle de déduplication :** deux suggestions sont considérées identiques si leur représentation normalisée (lowercase, sans ponctuation) a un score de similarité > 85% (cosine sur TF-IDF ou Levenshtein selon implémentation — point ouvert A3).

---

## 4. Agent de monitoring

### 4.1 — Rôle

L'agent parcourt le répertoire `bilans/`, extrait les sections cibles, génère les deux livrables, et s'arrête. Il ne modifie aucun bilan existant (lecture seule).

### 4.2 — Mode d'exécution (point ouvert A4)

Trois options :

| Option | Description | Avantages | Inconvénients |
|---|---|---|---|
| **A — Manuel** | Script Python lancé par LDE (`python3 monitor-bilans.py`) | Simplicité, contrôle total | Oublié si non lancé |
| **B — Schedulé** | Tâche Cowork déclenchée après chaque session close (ex. quotidienne à minuit) | Automatique | Peut tourner sans bilan nouveau |
| **C — Hook post-bilan** | Déclenché automatiquement après création d'un fichier dans `bilans/` | Temps réel | Dépend de la disponibilité d'un hook FS |

**✅ Décision (2026-05-16) :** option A (script manuel) pour le MVP — V1. Option B (tâche Cowork schedulée) en V2 une fois la logique stabilisée.

### 4.3 — Architecture technique (option A — script manuel)

```
monitor-bilans.py
├── parse_bilans()          → lit tous les .md de bilans/, extrait sections + métadonnées
├── build_synthese_prompts() → agrège les sections prompt + appel LLM pour synthèse thématique
├── build_suivi_suggestions() → extrait suggestions, déduplique, enrichit (priorité/complexité)
├── write_outputs()         → écrit synthese-prompts.md et met à jour suivi-suggestions.md
└── main()                  → orchestration + log d'exécution
```

**Dépendances :**
- Python 3.10+ (déjà disponible)
- `anthropic` SDK (appel LLM pour synthèse thématique et proposition priorité/complexité)
- `re`, `pathlib`, `datetime` (stdlib)
- Pas de dépendance réseau autre que l'API Anthropic

**Appels LLM :** deux appels distincts par exécution
1. Synthèse thématique des sections prompt (haiku-4-5 suffit, texte court)
2. Pour chaque suggestion nouvelle : proposition priorité + complexité + détection projet (haiku-4-5)

### 4.4 — Interface dédiée (point ouvert A5)

La question est de savoir si le suivi des suggestions mérite une interface spécifique dans le dashboard V2 ou si les fichiers MD suffisent.

**Arguments pour une interface dashboard :**
- Filtrage par statut / priorité / projet sans éditer le fichier
- Mise à jour du statut d'une suggestion en un clic (P0 → P1, À faire → Intégré)
- Vue triée dynamiquement

**Arguments pour rester en MD :**
- Simplicité maximale
- Editabilité directe dans VS Code
- Pas de développement frontend supplémentaire

**✅ Décision (2026-05-16) :** MD pur en V1. Interface dashboard V2 (vue lecture seule + filtres statut/priorité/projet) en V2. Le tableau MD reste la source de vérité dans les deux phases.

---

## 5. Arbitrages — tous fermés ✅

| Ref | Question | ✅ Décision (2026-05-16) |
|---|---|---|
| **A1** | Versionnage de `synthese-prompts.md` | Fichier unique écrasé + git pour l'historique |
| **A2** | Stratégie de mise à jour de `suivi-suggestions.md` | Append intelligent — préserve les annotations manuelles de LDE |
| **A3** | Algorithme de déduplication | Levenshtein pour la détection, LLM en fallback (pas de dépendance scipy) |
| **A4** | Mode d'exécution | V1 : script manuel · V2 : tâche Cowork schedulée |
| **A5** | Interface | V1 : MD pur · V2 : vue dashboard (lecture seule + filtres) |
| **A6** | Emplacement des livrables | `suivi-qualite/` (cohérence avec les bilans) |
| **A7** | Clé de déduplication | Similarité fuzzy (> 85%) + hash exact en fallback |
| **A8** | Suggestions déjà ✅ dans les bilans | Importées avec statut `✅ Intégré` — historique complet dès le premier run |
| **A9** | Appel LLM | Oui — haiku-4-5 pour synthèse thématique + enrichissement des suggestions |

---

## 6. Estimation de charge

| Composant | Charge estimée |
|---|---|
| Script `monitor-bilans.py` — parsing + extraction sections | 1 h |
| Build `synthese-prompts.md` + appel LLM thématique | 1 h |
| Build `suivi-suggestions.md` — déduplication + enrichissement LLM | 1,5 h |
| Tests (unitaires parsing + intégration end-to-end) | 1 h |
| Premier run manuel + correction / ajustement | 0,5 h |
| **Total MVP (script manuel, MD pur)** | **~5 h** |
| Phase 2 — vue dashboard V2 (lecture + filtres) | +3 à 4 h |

---

## 7. Fichiers produits / modifiés par l'implémentation

| Fichier | Action | Notes |
|---|---|---|
| `GIT/planning-lde-v2/monitor-bilans.py` | Créer | Script principal |
| `GIT/suivi-qualite/synthese-prompts.md` | Créer (généré) | Régénéré à chaque run |
| `GIT/suivi-qualite/suivi-suggestions.md` | Créer (généré, append) | Source de vérité du backlog |
| `GIT/planning-lde-v2/data.json` | Modifier | Ajouter le sous-projet + les docs |

---

## 8. Prochaine étape

Tous les arbitrages sont fermés. La spec est prête à être transmise à Claude Code.

**Prompt de démarrage type pour la session d'implémentation :**

> Implémente la spec `GIT/planning-lde-v2/SPEC-MONITORING-BILANS.md`. Le répertoire de travail est `GIT/planning-lde-v2/`. Commence par lire ce fichier et `GIT/CLAUDE.md`. Le script à créer est `monitor-bilans.py` à la racine de `planning-lde-v2/`. Les livrables générés vont dans `GIT/suivi-qualite/`. L'appel LLM utilise le SDK `anthropic` (haiku-4-5) — vérifier que la clé `ANTHROPIC_API_KEY` est disponible dans l'environnement avant d'implémenter.
