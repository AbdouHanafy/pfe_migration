# Backend detaille

## 1. Role du backend

Le backend est le coeur applicatif du projet. Il centralise :

- l'API REST exposee au frontend
- la decouverte des VMs cote serveur
- l'analyse de compatibilite
- la generation du plan de conversion
- le choix de strategie avec l'IA
- l'orchestration des migrations simulees ou reelles
- l'authentification
- l'acces aux outils OpenShift

Le backend a ete concu comme une couche unique de coordination pour eviter de disperser la logique dans plusieurs microservices alors que le projet reste un PFE/prototype avance.

## 2. Technologie choisie

Le backend repose principalement sur :

- `FastAPI`
- `SQLAlchemy`
- `SQLite`
- `PyJWT`
- `passlib`
- `scikit-learn`

Pourquoi FastAPI :

- creation rapide d'API REST propres
- typage clair avec Pydantic
- documentation automatique
- bonne lisibilite pour un projet academique

Pourquoi une architecture monolithique modulaire :

- la logique est fortement liee d'une etape a l'autre
- cela limite la complexite de deploiement
- le code reste decoupe par responsabilite sans introduire trop d'infrastructure supplementaire

## 3. Decoupage des modules backend

Le backend est organise en modules specialises.

### 3.1 `src/api/`

Ce module expose les routes HTTP et sert de point d'entree principal.

Responsabilites :

- declaration des endpoints
- gestion CORS
- auth JWT / API key / none
- coordination entre les autres modules
- lancement des taches de fond pour la migration reelle

Pourquoi ce decoupage :

- l'API reste une couche d'orchestration
- la logique metier est ensuite deleguee aux autres modules

### 3.2 `src/discovery/`

Ce module decouvre les VMs sources.

Sous-modules :

- `kvm_discoverer.py`
- `vmware_esxi_discoverer.py`
- `vmware_workstation_discoverer.py`

Pourquoi trois discoverers distincts :

- KVM et VMware Workstation n'exposent pas les memes sources d'information
- KVM passe par `libvirt` et le XML des domaines
- VMware Workstation passe par la lecture des fichiers `.vmx`

Avec l'ajout de VMware ESXi / vSphere, un troisieme mode de decouverte existe :

- ESXi / vSphere passe par `pyVmomi` et l'API VMware

Ce choix evite de melanger dans une seule classe trois mecanismes completement differents : API libvirt, fichiers locaux `.vmx` et inventaire distant vSphere.

Ce choix rend le code plus clair et permet d'ajouter plus tard d'autres hyperviseurs sans casser la logique existante.

### 3.3 `src/analysis/`

Ce module applique les regles de compatibilite OpenShift.

Il produit :

- un niveau de compatibilite
- un score
- une liste d'issues
- des recommandations

Pourquoi un module d'analyse separe :

- l'analyse est une etape metier distincte de la decouverte
- elle peut etre reutilisee depuis plusieurs parcours
- elle rend le pipeline explicable avant de lancer une vraie migration

### 3.4 `src/conversion/`

Ce module transforme le rapport d'analyse en plan d'actions techniques.

Exemples d'actions :

- conversion de format disque
- changement de bus disque
- changement de modele reseau

Pourquoi ce module existe :

- il separe la question "la VM est-elle compatible ?" de la question "que faut-il changer ?"
- cela donne un plan exploitable par l'utilisateur et par les etapes suivantes

### 3.5 `src/migration/`

Ce module contient :

- `strategy.py` pour choisir la strategie
- `orchestrator.py` pour lancer et suivre une migration simulee

Pourquoi ce decoupage :

- le choix de strategie est une decision
- l'orchestration est une execution
- les separer rend le pipeline plus lisible

### 3.6 `src/monitoring/`

Ce module gere le suivi des jobs.

Il fournit :

- un `job_store` en memoire
- un `reporter` pour produire un rapport JSON

Pourquoi ce choix :

- pour un prototype, un stockage memoire est simple et rapide
- il permet de montrer le cycle de vie d'une migration sans introduire un ordonnanceur externe

Limite assumee :

- si le processus redemarre, l'etat des jobs est perdu

### 3.7 `src/openshift/`

Ce module encapsule les operations reelles vers OpenShift.

Fonctions principales :

- verification des outils
- creation du namespace
- conversion de disque
- upload via `virtctl image-upload`
- generation du manifeste `VirtualMachine`
- application du manifeste via `oc`

Pourquoi ce module est important :

- il isole les appels systeme et les details de la CLI OpenShift
- l'API reste propre et plus facile a maintenir

### 3.8 `src/database/`

Ce module gere la base et le modele `User`.

Pourquoi ce choix minimal :

- le besoin actuel de persistance concerne surtout l'authentification
- SQLite est suffisant pour un prototype et pour la simplicite du deploiement

## 4. Flux backend d'un appel type

### 4.1 Analyse

Quand le frontend appelle `POST /api/v1/migration/analyze/{vm_name}` :

1. l'API recupere les details VM via le bon discoverer
2. elle transmet les details a `analyze_vm`
3. elle retourne le rapport d'analyse

Pourquoi ce flux :

- il est court
- il garde l'analyse synchrone
- il permet un retour immediat a l'utilisateur

### 4.2 Planification

Quand le frontend appelle `POST /api/v1/migration/plan/{vm_name}` :

1. decouverte
2. analyse
3. construction du plan de conversion
4. choix de strategie via l'IA
5. retour d'un objet complet au frontend

Pourquoi ce flux :

- l'utilisateur obtient une vision complete avant d'engager une migration
- le backend concentre la logique de decision

### 4.3 Migration reelle OpenShift

Quand le frontend appelle la route OpenShift :

1. creation d'un job
2. lancement en tache de fond
3. `ensure_namespace`
4. `convert_disk_if_needed`
5. `upload_disk`
6. `build_vm_manifest`
7. `apply_manifest`

Pourquoi en tache de fond :

- une migration reelle peut durer longtemps
- on evite de bloquer la requete HTTP
- le frontend peut suivre le job par polling

## 5. Endpoints principaux

Le backend expose notamment :

- `/health`
- `/api/v1/auth/register`
- `/api/v1/auth/login`
- `/api/v1/discovery/kvm`
- `/api/v1/discovery/vmware-esxi`
- `/api/v1/discovery/vmware-workstation`
- `/api/v1/migration/analyze/{vm_name}`
- `/api/v1/migration/plan/{vm_name}`
- `/api/v1/migration/start/{vm_name}`
- `/api/v1/migration/status/{job_id}`
- `/api/v1/migration/report/{job_id}`
- `/api/v1/migration/openshift/{vm_name}`
- `/api/v1/migration/analyze-upload`
- `/api/v1/migration/plan-upload`
- `/api/v1/migration/openshift-upload/{vm_name}`

Le choix de fournir a la fois des routes "par nom de VM" et des routes "upload" permet de couvrir deux mondes :

- les VMs que le backend voit deja
- les VMs locales envoyees depuis le poste utilisateur

## 6. Pourquoi certains choix ont ete retenus

### 6.1 Auth multi-mode

Le backend supporte `none`, `api_key` et `jwt`.

Pourquoi :

- `none` facilite certains tests locaux
- `api_key` est simple pour des tests backend
- `jwt` est le mode adapte au frontend React avec login/register

### 6.2 SQLite

Pourquoi SQLite au lieu de PostgreSQL :

- installation tres simple
- aucune infrastructure supplementaire
- suffisant pour stocker les utilisateurs dans un prototype

Ce choix est volontairement pragmatique.

### 6.3 Job store en memoire

Pourquoi :

- tres facile a comprendre et a demonstrer
- pas besoin de Redis ou de broker externe
- adapte a la simulation et au suivi simple

Ce n'est pas le meilleur choix pour la production, mais c'est un bon choix de PFE pour aller vite vers une preuve de fonctionnement.

### 6.4 Appels CLI plutot que SDK complet

Le module OpenShift passe par `oc`, `virtctl` et `qemu-img`.

Pourquoi :

- ces outils representent le chemin reel utilise par les administrateurs
- ils couvrent directement les besoins du projet
- cela evite de reimplementer des workflows deja standardises par l'ecosysteme

## 7. Forces de l'architecture backend

Les points forts du backend actuel sont :

- bonne separation par modules metier
- pipeline clair et explicable
- prise en charge de la simulation et de la migration reelle
- integration d'un moteur IA sans service separe
- compatibilite avec plusieurs sources de VMs

## 8. Limites actuelles

Les principales limites backend sont :

- persistance des jobs non durable
- peu de modeles de base de donnees au-dela des utilisateurs
- absence de file de messages ou de workers dedies
- forte dependance a des binaires externes pour la migration reelle

## 9. Conclusion

Le backend a ete divise en modules simples, lisibles et alignes sur le pipeline metier. Ce choix permet de garder une base technique solide sans complexifier artificiellement le projet. Pour un PFE, c'est un bon compromis entre rigueur architecturale, rapidite d'implementation et capacite de demonstration.
