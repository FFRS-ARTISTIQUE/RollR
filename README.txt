# Système de Notation Roller Artistique – Régional

## 📌 Description

Ce logiciel est un **outil officiel de compétition** permettant la notation complète des programmes de freeskating régional. Il inclut :

* Saisie des éléments techniques 
* Composantes (Posture, Vitesse, Qualité, Chorégraphie, Implication, Attitudes)
* Pénalités/Déductions
* Génération de PDF officiels (individuels + cumulatif)
* Gestion des catégories et patineurs via CSV
* Affichage distant réseau (écran second)
* Mode plein écran compétition

Ce projet fonctionne sur **Windows 64 bits**, sans installation, sans dépendances externes.


## ▶️ Lancement

```
Cliquer sur le fichier RollR.exe qui se trouve dans le dossier dist.
```

Le logiciel démarre en **plein écran**.

---

## 📥 Import CSV depuis la création d'une compétition

Le fichier CSV doit être en **UTF-8**, avec les colonnes :

```
Ordre, Displine et Niveau, Catégorie, Nom, Prénom, Genre, Club
```
Le nom du fichier csv sera le nom de la compétition.
Tout doublon → erreur.
Tout ordre identique dans la même catégorie → erreur.

------

## 📥 Import CSV depuis la création d'une catégorie

Le fichier CSV doit être en **UTF-8**, avec les colonnes :

```
Nom, Prénom, Club, Ordre
```

Tout doublon → erreur.
Tout ordre identique dans la même catégorie → erreur.

---

## 🖨 PDF générés

* 1 PDF par patineur dans un dossier temp
* 1 PDF cumulatif par catégorie
* Format A4 Portrait
* Numérotation des éléments
* Scores

---

## 🌐 Affichage distant (réseau)

* Le juge = serveur
* L’affichage = client
* IP + port modifiable 
* Actualisation **uniquement quand le patineur est évalué**
* Reconnexion automatique
* Aucun bouton sur l’écran distant

---

## © Usage officiel

* Conçue pour fonctionner **hors-ligne**, sans mise à jour réseau
* Pas de version macOS / Linux

---

## ⚠️ Limite
* Le fichier DANSE_REG.exe et FREE_REG.exe ne doit jamais être lancé directement et le nom des fichiers ne doit pas être modifié.
* Il est conçu pour être lancé uniquement via le menu principal RollR.exe pour le module d'évaluation.
* Le fichier display.exe ou 2display doit être copié sur une clé USB et il faut l'executer sur le pc d'affichage. Le pc d'affichage et d'évaluation doivent être connectés en ethernet.
* Lors de la première ouverture du fichier sur le pc. Windows indique un message d'avertissement qu'il faut accepter pour executer le fichier.
* Seul le fichier competitions.db peut être supprimé pour réinitialiser toute la base de données.


---
