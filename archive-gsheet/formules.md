# Référence Google Sheets — Planning projets

## Onglet : Tâches

### Colonne K — Semaine

```gs
=SI(E2="";"";"S"&TEXTE(ISOWEEKNUM(E2);"00"))
```

Description : transforme la date de la colonne E en numéro de semaine

Exemple :
- `15/05/2026`
→ `S20`


---

### Colonne L — Année

```gs
=SI(E2="";"";ANNEE(E2))
```

Description : transforme la date de la colonne E en année

Exemple :
- `15/05/2026`
→ `2026`

## Onglets : Semaines et TCD Projets

### Ligne 1 (C1-G1) — En-têtes de semaine (formules dynamiques)

Ces formules remplacent les valeurs statiques "S19", "S20 (P0)"… afin que les en-têtes se recalculent automatiquement à chaque ouverture, sans push.

> ⚠️ Utiliser des **décalages en jours** (±7, ±14…) plutôt que `ISOWEEKNUM()-1` : l'arithmétique directe sur ISOWEEKNUM retourne 0 en semaine 1 (au lieu de 52). Le décalage en jours délègue le calcul à ISOWEEKNUM sur une date valide, ce qui gère correctement les fins d'année.

**C1 — Semaine -1**
```gs
="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI()-7);"00")
```

**D1 — Semaine en cours (P0)**
```gs
="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI());"00")&" (P0)"
```

**E1 — Semaine +1 (P1)**
```gs
="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI()+7);"00")&" (P1)"
```

**F1 — Semaine +2 (P2)**
```gs
="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI()+14);"00")&" (P2)"
```

**G1 — Semaine +3 (P3)**
```gs
="S"&TEXTE(ISOWEEKNUM(AUJOURDHUI()+21);"00")&" (P3)"
```

---

## Onglet : TCD Projets


### Cellule A4 

```gs
=QUERY(REDUCE("" ; UNIQUE(FILTER('Tâches'!A2:A ; 'Tâches'!A2:A<>"")) ; LAMBDA(acc ; p ; VSTACK(acc ; p ; ARRAYFORMULA("- "&FILTER('Tâches'!B2:B ; 'Tâches'!A2:A=p))))) ; "where Col1 is not null" ; 0)
```

Description : Obtient la liste des projets et sous-projets à partir des colonnes A et B de l'onglet Tâches

### Cellule B2

```gs
=SUM(ARRAYFORMULA(VALUE(SUBSTITUTE(C2:G2;" h.";""))))&" h."
```
`
Description : Calcule la somme totale des colonnes C2 à G2 (totaux de chaque semaine) en les convertissant préalablement en valeurs numériques : `34 h.` devient `34`. Donne le RAF total toutes semaines confondues.


### Cellules C2

```gs
=SOMME(FILTER(N(C4:C) ; REGEXMATCH(A4:A ; "^- ")))&" h."
```
`
Description : Calcule la somme des cellules de la colonne C à partir de C:4, en filtrant pour ne retenir que celles dont la colonne A commence par `- ` (items de sous-projets) pour ne pas afficher de résultat pour les lignes de Projets

Cette formule doit être transposée dans les cellules D2, E2, F2 et G2

### Cellule B3

```gs
=SUM(ARRAYFORMULA(VALUE(SUBSTITUTE(C3:G3;" j.";""))))&" j."
```
`
Description : Calcule la somme des valeurs des colonnes C3 à G3 en les convertissant aupoaravant en données numériques : `4,9 j.` devient `4,9.`


### Cellules C3

```gs
=CEILING(VALUE(SUBSTITUTE(C2;" h.";""))/7;0,1)&" j."
```
`
Description : Convertis le contenu de C2 (heures) en jours, avec un arrondis au dixième

Cette formule doit être transposée dans les cellules D3, E3, F3 et G3


### Cellules B4

```gs
=IF(AND(A4<>"";LEFT(A4;2)="- ");SUM(C4:G4);"")
```
`
Description : Calcule la somme des valeurs des colonnes C4 à G4 si le contenu de la cellule A4 commence par `- ` (ligne de sous-projet) et n'est pas vide

Cette formule doit être transposée dans les cellules de plage B5 à B100

### Cellules C4 à G4 — RAF par semaine (S-1 à S+3)

Les 5 variantes ci-dessous s'appliquent colonne par colonne, puis sont transposées sur les lignes 5 à 100.

**C4 — Semaine -1**
```gs
=SI(REGEXMATCH(A4;"^- ");SIERREUR(SOMME(FILTER('Tâches'!G:G;'Tâches'!B:B=SUBSTITUE(A4;"- ";"");'Tâches'!K:K="S"&(ISOWEEKNUM(AUJOURDHUI())-1)));"");"")
```

**D4 — Semaine en cours (S0)**
```gs
=SI(REGEXMATCH(A4;"^- ");SIERREUR(SOMME(FILTER('Tâches'!G:G;'Tâches'!B:B=SUBSTITUE(A4;"- ";"");'Tâches'!K:K="S"&ISOWEEKNUM(AUJOURDHUI())));"");"")
```

**E4 — Semaine +1**
```gs
=SI(REGEXMATCH(A4;"^- ");SIERREUR(SOMME(FILTER('Tâches'!G:G;'Tâches'!B:B=SUBSTITUE(A4;"- ";"");'Tâches'!K:K="S"&(ISOWEEKNUM(AUJOURDHUI())+1)));"");"")
```

**F4 — Semaine +2**
```gs
=SI(REGEXMATCH(A4;"^- ");SIERREUR(SOMME(FILTER('Tâches'!G:G;'Tâches'!B:B=SUBSTITUE(A4;"- ";"");'Tâches'!K:K="S"&(ISOWEEKNUM(AUJOURDHUI())+2)));"");"")
```

**G4 — Semaine +3**
```gs
=SI(REGEXMATCH(A4;"^- ");SIERREUR(SOMME(FILTER('Tâches'!G:G;'Tâches'!B:B=SUBSTITUE(A4;"- ";"");'Tâches'!K:K="S"&(ISOWEEKNUM(AUJOURDHUI())+3)));"");"")
```

Description : pour chaque sous-projet (lignes commençant par `- `), somme le RAF des tâches dont le nom de sous-projet (col B de Tâches) correspond à la ligne courante et dont la semaine (col K de Tâches) correspond à la semaine cible. Renvoie `""` pour les lignes de projet (sans `- `).

Ces formules sont transposées dans les cellules C5:C100, D5:D100, E5:E100, F5:F100 et G5:G100.





