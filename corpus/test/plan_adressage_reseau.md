<!-- corpus/test/plan_adressage_reseau.md -->
# Plan d'adressage et services réseau

*Document de test fictif, rédigé pour valider le RAG navigation. Cellule Réseau (R1), version 1.0 du 12 octobre 2026.*

## 1. Réseau interne

Le réseau interne de GANDAL utilise la plage privée 10.10.0.0/16, découpée en un VLAN par usage. Le domaine interne est gandal.lan.

Le pare-feu GARDIEN (10.10.10.1) assure le routage entre les VLAN, le filtrage, le VPN et la résolution DNS avec Unbound. Il sert aussi de serveur de temps NTP pour toutes les machines.

## 2. VLAN

| VLAN | Nom | Plage | Passerelle | Contenu |
| --- | --- | --- | --- | --- |
| 10 | Administration | 10.10.10.0/24 | 10.10.10.1 | GARDIEN, hyperviseurs NOVA, interfaces d'administration |
| 20 | Services | 10.10.20.0/24 | 10.10.20.1 | EMILIA, BASTION, VM150, VM160 et autres machines virtuelles de service |
| 30 | Calcul | 10.10.30.0/24 | 10.10.30.1 | Nœud GPU REM |
| 40 | Stockage | 10.10.40.0/24 | 10.10.40.1 | SIRIUS, ARCHIVE, réseau Ceph |
| 50 | VPN | 10.10.50.0/24 | 10.10.50.1 | Postes des utilisateurs connectés en WireGuard |

Le VLAN 40 ne transporte que du trafic de stockage. Il est joignable depuis les VLAN 10, 20 et 30, jamais depuis le VLAN 50.

## 3. Noms DNS

| Nom | Adresse IP | Machine |
| --- | --- | --- |
| gardien.gandal.lan | 10.10.10.1 | Pare-feu |
| nova.gandal.lan | 10.10.10.10 | Adresse virtuelle du cluster NOVA |
| emilia.gandal.lan | 10.10.20.31 | Passerelle LiteLLM |
| bastion.gandal.lan | 10.10.20.110 | Point d'entrée SSH |
| gandal-ai.gandal.lan | 10.10.20.150 | VM150, service GANDAL-AI |
| grafana.gandal.lan | 10.10.20.160 | VM160, supervision |
| rem.gandal.lan | 10.10.30.40 | Nœud GPU |
| sirius.gandal.lan | 10.10.40.20 | Stockage |
| archive.gandal.lan | 10.10.40.30 | Sauvegardes |

Toute nouvelle machine doit recevoir un nom DNS avant sa mise en service.

## 4. Règles du pare-feu

Par défaut, tout trafic entrant est refusé. Les règles principales sont les suivantes.

| Source | Destination | Port | Décision |
| --- | --- | --- | --- |
| Internet | GARDIEN | 51820/udp (WireGuard) | Autorisé |
| VLAN 50 (VPN) | BASTION | 2222/tcp (SSH) | Autorisé |
| VLAN 50 (VPN) | VM150 | 8090/tcp (GANDAL-AI) | Autorisé |
| VLAN 50 (VPN) | VM160 | 3000/tcp (Grafana) | Autorisé |
| VLAN 50 (VPN) | REM | 8888/tcp (JupyterLab) | Autorisé |
| VLAN 50 (VPN) | Toute autre machine | 22/tcp (SSH) | Refusé |
| VLAN 20 (Services) | EMILIA | 4000/tcp (LiteLLM) | Autorisé |
| EMILIA | REM | 11434/tcp (Ollama) | Autorisé |

Une connexion SSH directe vers une machine autre que le BASTION est refusée : il faut toujours passer par le BASTION.

## 5. VPN WireGuard

Le VPN est le seul moyen d'accéder à GANDAL depuis l'extérieur. Il écoute sur le port 51820/udp de GARDIEN. Chaque utilisateur reçoit une adresse fixe dans le VLAN 50 et un fichier de configuration nominatif, remis par la cellule Support.

Les clés WireGuard sont renouvelées tous les six mois. Un compte inactif depuis 90 jours voit son accès VPN désactivé automatiquement.

## 6. Demander une modification

Toute demande d'ouverture de port, de nouveau nom DNS ou de nouvelle règle se fait par un ticket dans le projet « Réseau » du gestionnaire de tickets. La cellule Réseau valide ou refuse la demande sous 48 heures ouvrées.
