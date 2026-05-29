# Note Gemini — Résolution des erreurs et optimisation du planning LDE

> **Source** : réponse de Gemini Gsheet (assistant intégré à Google Sheets), 2026-05-28.  
> **Contexte** : interventions faites **directement dans la GSheet en ligne**, indépendamment du Dashboard Planning. Ces correctifs n'ont pas transité par `serve-v2.py`.  
> **Portée** : l'onglet **TCD Projets** de la GSheet Planning LDE V2.

---

## 1. Problème constaté

L'onglet **TCD Projets** présentait des instabilités (erreurs `#REF!` et incohérences de calcul) dues à trois facteurs principaux :

- **Rupture de liens** : l'insertion manuelle de lignes prévisionnelles en bas de tableau (ex. lignes `A47:A50`) créait des conflits avec les formules existantes ou bloquait l'expansion des plages de données.
- **Incohérence des noms (espaces fantômes)** : la présence d'espaces en fin de texte dans les noms de projets (ex. `"Banc test "` au lieu de `"Banc test"`) empêchait les formules de calcul de reconnaître les projets comme étant identiques, créant des doublons ou des oublis dans les totaux.
- **Structure rigide** : l'utilisation de notes textuelles directement sous les colonnes de données empêchait le tableau de s'étendre naturellement lors de l'ajout de nouvelles tâches.

## 2. Solution appliquée

- **Nettoyage des données** : suppression systématique de tous les espaces finaux dans les colonnes « Projet » et « Sous-projet » de l'onglet **Tâches**.
- **Recalage des lignes** : déplacement des blocs de lignes pour rétablir la continuité des formules et supprimer les messages d'erreur `#REF!`.

## 3. Recommandations pour l'avenir (bonnes pratiques)

Pour ajouter des lignes prévisionnelles sans casser le fichier :

- **Libérer l'espace sous le tableau** : ne jamais écrire de notes ou de commentaires directement sous la dernière ligne de données. Si le tableau doit s'agrandir, il doit avoir le « champ libre ».
  - *Astuce* : placer les notes dans une colonne dédiée à droite (ex. col I ou J) ou dans un onglet « Notes » séparé.
- **Utiliser les Tableaux Dynamiques** : convertir les onglets sources (**Tâches** et **Semaines**) en « Tableaux » (menu **Format → Convertir en tableau**).
  - *Avantage* : toute nouvelle ligne ajoutée en bas du tableau sera automatiquement « aspirée » par les formules de synthèse, sans aucune manipulation manuelle.
- **Saisie des projets prévisionnels** : plutôt que de créer des lignes isolées dans le TCD, saisir les futurs projets directement dans l'onglet **Tâches**. Leur donner une charge de `0` ou un statut « À voir ». Ils remonteront automatiquement dans la synthèse de manière propre et structurée.

---

## Implications pour le code du Dashboard

Ces correctifs étant faits **côté GSheet uniquement**, les conséquences à anticiper côté `serve-v2.py` quand on rouvrira pull/push :

- **Espaces fantômes** : la prochaine fois qu'on pullera, vérifier que `serve-v2.py` strip bien les noms de projets/SPs avant matching (col A et col B). Sinon un pull pourrait recréer des doublons ou ne pas matcher les SPs existants dans `data.json`.
- **Tableaux dynamiques** : si Gemini a converti Tâches et Semaines en « Tableaux » Google natifs, vérifier que les appels `gspread` à `serve-v2.py` continuent de fonctionner (range A:L, plage nommée, etc.). Possible impact sur les méthodes `batch_clear` et `batch_update` selon la façon dont gspread gère les Tableaux.
- **Notes hors tableau** : la nouvelle convention (notes en col I/J ou onglet séparé) doit être prise en compte dans les futures évolutions du push (ne pas écrire en col I si elle devient une colonne « Notes » utilisateur, par exemple).

À investiguer en même temps que les bugs déjà notés (`pull silencieusement non capté`, `push écrasant col C et J`).
