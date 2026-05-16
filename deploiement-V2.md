# Déploiement V2 — Mise en place Opérationnelle

Spec du sous-projet « Mise en place Opérationnelle » du Planning LDE V2.

---

## Contexte

Le Planning LDE V2 (`data.json` + `serve-v2.py` + `DASHBOARD-V2.html`) est opérationnel depuis le 2026-05-15. À partir de cette date, il devient le système de suivi principal pour LDE.

La V1 (`planning-lde/AVANCEMENT-PROJETS.html`) reste en place mais n'est plus maintenue activement. Elle contient des données historiques pour les projets MHO qui n'ont pas encore été intégrés en V2.

---

## État de migration au 2026-05-15

### Projets déjà dans V2

| Projet | ID V2 |
|--------|-------|
| Dashboard Datamart | `dashboard-datamart` |
| Training V7 | `training-v7` |
| Examens V7 | `examens-v7` |
| Cas Pratiques | `cas-pratiques-project` |
| Planning LDE V2 | `planning-lde-v2` |
| Amélioration Quiz | `amelioration-quiz-training-examen` |

### Projets dans V1 uniquement (non encore migrés)

| Projet | ID V1 | Owner | Statut migration |
|--------|-------|-------|-----------------|
| Datamart API | `datamart` | MHO | À créer en V2 à la prochaine session |
| Opquast.com | `opquast-com` | MHO | À créer en V2 à la prochaine session |
| Opquast Companion | `opquast-companion` | MHO | À créer en V2 à la prochaine session |
| opq-devcontainer | `opq-devcontainer` | MHO | À créer en V2 à la prochaine session |
| Admin / PDN | `admin-pdn` | MHO | À créer en V2 à la prochaine session |
| SSO / Connect | `sso-connect` | MHO | À créer en V2 à la prochaine session |
| checklists.opquast.com | `checklist-opquast-com` | MHO | À créer en V2 à la prochaine session |
| directory.opquast.com | `directory-opquast-com` | MHO | À créer en V2 à la prochaine session |
| Planning LDE V1 | `planning-lde` | LDE | Archivé — remplacé par V2, pas de migration |

---

## Process de transfert V1 → V2

### Principe

Les groupes et features de la V1 sont trop denses et trop hétérogènes pour être importés en l'état. Une réorganisation manuelle sera nécessaire avant tout import.

**Le transfert se fait donc à la demande, session par session**, selon la règle suivante :

> **Quand une session de travail porte sur un projet encore absent de V2, créer ce projet dans V2 en début de session — structure minimale, sans import des features V1.**

### Ce qu'on crée en V2

Un projet minimal avec uniquement les métadonnées de base :

```json
{
  "id": "...",
  "name": "...",
  "alias": "...",
  "desc": "...",
  "stack": "...",
  "category": "active",
  "folder": "...",
  "docs": [],
  "subprojects": []
}
```

Les sous-projets et étapes sont créés **au fil des sessions**, en fonction du travail effectivement réalisé — pas de rétro-import des features V1.

### Ce qu'on fait des données V1

- Les features/groupes V1 restent dans `planning-lde/AVANCEMENT-PROJETS.html`, gelées.
- Elles servent de **référence historique** uniquement.
- Une réorganisation pour import partiel en V2 pourra être envisagée ultérieurement, projet par projet, selon les besoins.

### Checklist à l'ouverture d'une session sur un projet V1-only

1. Vérifier que le projet n'est pas déjà dans `data.json` (chercher son `id` ou son `name`)
2. Si absent : créer l'entrée minimale dans `data.json` via `POST /api/projects` ou édition directe
3. Créer les sous-projets correspondant au travail de la session (pas de rétro-import)
4. En fin de session : appliquer la checklist standard de fin de session (mettre à jour `data.json` V2)
5. Ne plus mettre à jour l'entrée V1 pour ce projet à partir de cette session

---

## Réorganisation future (optionnelle)

Si LDE décide d'importer des features V1 pour un projet migré, le process sera :

1. Relire les features V1 du projet concerné
2. Identifier les groupes/features pertinents (ignorer les features `done` sans valeur d'historique)
3. Proposer une réorganisation en sous-projets V2 (avec Ping-Pong si non trivial)
4. Importer manuellement après validation LDE

Ce chantier est **hors périmètre de la mise en place opérationnelle** — à planifier séparément.
