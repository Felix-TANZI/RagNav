<!-- corpus/test/guide_prise_en_main.md -->
# Guide de prise en main de GANDAL

*Document de test fictif, rédigé pour valider le RAG navigation. Cellule Support (S1), version 2.0 du 15 octobre 2026.*

Ce guide accompagne un nouveau membre du projet, de la demande de compte à sa première connexion aux machines de GANDAL.

## 1. Obtenir un compte

La demande de compte se fait avec le formulaire « Nouveau compte GANDAL », disponible sur le Drive du projet. Le chef de cellule du demandeur valide la demande, puis la cellule Support crée le compte sous deux jours ouvrés.

L'identifiant a la forme prenom.nom. Le mot de passe initial est envoyé par message privé et doit être changé à la première connexion. Il doit compter au moins 12 caractères et il expire tous les 180 jours.

## 2. Se connecter au VPN

L'accès à GANDAL depuis l'extérieur passe obligatoirement par le VPN WireGuard.

1. Installer le client WireGuard sur son poste.
2. Importer le fichier de configuration gandal-prenom.nom.conf remis par la cellule Support.
3. Activer le tunnel.
4. Vérifier la connexion avec la commande `ping 10.10.10.1`, qui doit répondre.

En cas d'échec, vérifier que le réseau local n'utilise pas déjà la plage 10.10.0.0/16, puis contacter le support.

## 3. Accéder aux machines en SSH

Les connexions SSH passent toutes par le BASTION, sur le port 2222.

```
ssh -p 2222 prenom.nom@bastion.gandal.lan
```

Seules les clés de type ed25519 sont acceptées, la connexion par mot de passe est désactivée. La clé publique est déposée lors de la création du compte. Pour rebondir automatiquement par le BASTION, ajouter ce bloc au fichier ~/.ssh/config :

```
Host bastion
    HostName bastion.gandal.lan
    Port 2222
    User prenom.nom

Host *.gandal.lan !bastion.gandal.lan
    ProxyJump bastion
    User prenom.nom
```

Une fois ce bloc en place, la commande `ssh vm150.gandal.lan` passe directement par le BASTION.

## 4. Espace de stockage

Chaque cellule dispose d'un dossier sur le stockage SIRIUS, monté sur les machines virtuelles sous /projets/nom-de-la-cellule. Le quota est de 500 Go par cellule. Chaque utilisateur dispose en plus d'un dossier personnel de 50 Go.

Les données de travail, les modèles et les jeux de données doivent être rangés dans ces dossiers : ce sont les seuls emplacements protégés par les instantanés et les sauvegardes.

## 5. Utiliser JupyterLab

JupyterLab est accessible à l'adresse http://rem.gandal.lan:8888, avec le compte GANDAL. Une session inactive est fermée au bout de deux heures. Un notebook peut utiliser au plus 8 Go de mémoire GPU.

Pour un entraînement long ou qui demande plus de mémoire GPU, il faut soumettre un job avec l'ordonnanceur gandal-gpu, comme décrit dans la procédure de soumission d'un job GPU.

## 6. Interroger l'assistant GANDAL-AI

L'assistant GANDAL-AI répond aux questions sur le projet à partir de la documentation, en citant ses sources. Il est accessible depuis le VPN à l'adresse http://gandal-ai.gandal.lan:8090.

## 7. Obtenir de l'aide

Pour toute question ou tout incident, ouvrir un ticket dans le projet « Support » du gestionnaire de tickets, ou écrire sur le canal Mattermost ~gandal-support. La cellule Support répond sous un jour ouvré. Pour une panne urgente en dehors des heures ouvrées, contacter l'astreinte de la cellule Exploitation.

## 8. Règles d'usage

- Ne pas stocker de données personnelles sans l'accord du responsable du projet.
- Ne pas lancer de calcul sans lien avec le projet, en particulier du minage de cryptomonnaie.
- Ne jamais partager son fichier de configuration VPN ni sa clé SSH.
- Signaler tout comportement anormal d'une machine à la cellule Support.
