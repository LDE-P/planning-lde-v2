# BUG — Édition directe de data.json sans `id`

**Date de détection :** 2026-05-15  
**Détecté par :** LDE (Pull Tâches depuis le dashboard)  
**Origine :** Session Cowork "Livre OQ — Revue des tags 2 (objections)"

---

## Symptôme

Toast d'erreur dans le dashboard au moment du Pull Tâches :

```
Pull Tâches échoué : 'id'
```

## Cause racine

En fin de session Cowork, la mise à jour de `data.json` (ajout du sous-projet "Revue des tags 2 (objections)" dans le projet Livre OQ) a été faite par **édition directe du JSON**, sans passer par l'endpoint `/api/add-subproject`.

Résultat : l'entrée créée était invalide à deux niveaux :

1. **Champ `id` absent** — tous les sous-projets doivent avoir un `id` unique (slug kebab-case généré par `_unique_id()`)
2. **Format `steps` non standard** — les étapes utilisaient `label`/`done` au lieu de `name`/`status`/`charge`/`raf`

## Chaîne d'erreurs

1. Cowork écrit le sous-projet directement dans `data.json` → entrée sans `id`, format steps incorrect
2. LDE tente de renommer le sous-projet dans le dashboard → l'endpoint `/api/save-subproject` cherche le sp par `s['id']` → ne trouve rien → échec silencieux → le renommage ne persiste pas
3. LDE lance le Pull Tâches → `_gs_pull_taches()` construit `{s['id'] for s in proj.get('subprojects', [])}` → `KeyError: 'id'` → toast d'erreur

## Correction appliquée

Ajout manuel de `"id": "revue-tags-2-objections"` dans `data.json` sur l'entrée fautive (2026-05-15, par LDE avec assistance Cowork).

Le format des `steps` reste non standard dans cette entrée (non corrigé à ce stade — le dashboard les ignore pour les sous-projets sans étapes actives).

## Cause profonde

Le `CLAUDE.md` racine GIT était en contexte lors de la session. La Règle 4 (s'appuyer sur l'infrastructure existante) et la note de la checklist (lire `planning-lde-v2/CLAUDE.md` avant toute création structurelle) n'ont pas été appliquées parce que la tâche de fin de session a été perçue comme "mécanique" et donc traitée sans lecture préalable du CLAUDE.md du sous-projet.

**Constat clé : ajouter une règle ne suffit pas si l'agent peut la contourner par inattention sur les "petites" tâches.**

---

## Mesures prises

### 1. CLAUDE.md racine — note ajoutée à la checklist (point 1)

> ⚠️ **Ne jamais créer un sous-projet en éditant `data.json` directement** — utiliser l'endpoint `/api/add-subproject` qui génère l'`id` et garantit la cohérence du schéma.

### 2. Bilan de session documenté

Le bug et son analyse figurent dans `suivi-qualite/bilans/2026-05-15.md` (bilan 4).

---

## Mesures complémentaires proposées (non encore appliquées)

### A. Vérification d'intégrité à l'étape 3 de la checklist

Ajouter à l'étape 3 ("Vérifier la cohérence des données") un check bash concret à exécuter systématiquement en fin de session :

```bash
python3 -c "
import json
data = json.load(open('planning-lde-v2/data.json'))
errors = []
for p in data['projects']:
    if 'id' not in p:
        errors.append(f'Projet sans id : {p[\"name\"]}')
    for s in p.get('subprojects', []):
        if 'id' not in s:
            errors.append(f'SP sans id : {p[\"name\"]} / {s[\"name\"]}')
print('OK — data.json valide' if not errors else '\n'.join(errors))
"
```

Ce check aurait détecté le problème en fin de session hier soir, avant la clôture.

### B. Préciser le cas "serveur non démarré"

L'instruction actuelle suppose que `serve-v2.py` tourne (l'endpoint `/api/add-subproject` en dépend). Si le serveur n'est pas lancé en fin de session, l'agent n'a pas de chemin valide et risque de retomber sur l'édition directe.

Ajout proposé dans la note de la checklist :

> Si `serve-v2.py` n'est pas en cours d'exécution : **ne pas éditer `data.json` directement**. Soit lancer le serveur (`python3 planning-lde-v2/serve-v2.py`), soit demander à LDE de créer le sous-projet via le dashboard, soit noter la création comme tâche à faire au prochain démarrage du serveur.

---

## Statut

| Mesure | Statut |
|--------|--------|
| Correction du `id` manquant dans `data.json` | ✅ Appliqué |
| Note CLAUDE.md racine (interdiction édition directe) | ✅ Appliqué |
| Bilan de session documenté | ✅ Appliqué |
| Check d'intégrité à la checklist (proposition A) | ✅ Appliqué (2026-05-15) |
| Cas "serveur non démarré" (proposition B) | ✅ Appliqué (2026-05-15) |
