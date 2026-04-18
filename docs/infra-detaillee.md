# Infrastructure detaillee

## 1. Role de l'infrastructure dans le projet

L'infrastructure du projet n'est pas un simple support d'execution. Elle fait partie du probleme a resoudre, car la migration d'une VM vers OpenShift Virtualization depend directement :

- de la machine depuis laquelle on voit la VM source
- de la machine depuis laquelle on lance les outils de migration
- de la disponibilite du stockage sur le cluster cible
- de la presence des outils `oc`, `virtctl` et `qemu-img`
- de la separation entre le poste utilisateur, le bastion et le cluster

Le projet a donc retenu une architecture en plusieurs zones, car une seule machine ne pouvait pas couvrir proprement tous les cas reels.

## 2. Architecture retenue

L'architecture actuellement adoptee est la suivante :

1. un frontend React execute sur le poste local de l'utilisateur
2. un backend FastAPI execute sur un bastion
3. un cluster OpenShift cible avec OpenShift Virtualization
4. des VMs sources qui peuvent etre :
   - visibles depuis le bastion, par exemple KVM ou VMware accessibles sur l'hote backend
   - visibles uniquement depuis le poste utilisateur, par exemple une VM VMware Workstation locale
   - visibles sur une infrastructure distante VMware ESXi / vSphere accessible par API

Cette architecture a ete choisie parce qu'une VM locale VMware sur le PC utilisateur n'est pas forcement visible depuis le bastion. Si tout etait centralise cote backend, une partie importante des cas d'usage ne fonctionnerait pas.

## 3. Composants d'infrastructure utilises

### 3.1 Poste utilisateur

Le poste utilisateur heberge :

- le frontend React/Vite
- le navigateur qui pilote le workflow
- les fichiers locaux `.vmx`, `.vmdk`, `-s001.vmdk`, etc.

Pourquoi ce choix :

- c'est le seul endroit ou certaines VMs VMware locales existent vraiment
- le navigateur peut lire les petits fichiers de description et faire un precheck sans attendre le backend
- cela evite d'envoyer immediatement de gros disques au bastion

### 3.2 Bastion / serveur backend

Le bastion heberge :

- l'API FastAPI
- la logique de decouverte KVM/VMware cote serveur
- l'analyse, la planification et l'orchestration
- les outils de migration reelle
- la base SQLite et le stockage temporaire dans `data/`

Pourquoi ce choix :

- le bastion centralise les traitements lourds et les acces vers OpenShift
- il peut executer `oc`, `virtctl` et `qemu-img`
- il peut aussi se connecter a une plateforme VMware ESXi / vSphere distante via `pyVmomi`
- il permet de separer le pilotage web de l'execution systeme

### 3.3 Cluster OpenShift

Le cluster cible heberge :

- OpenShift Virtualization / KubeVirt
- CDI pour l'upload d'images disque
- les `PersistentVolumeClaim`
- les ressources `VirtualMachine`

Pourquoi ce choix :

- OpenShift Virtualization est la cible du PFE
- KubeVirt permet d'executer des VMs de maniere native dans le cluster
- CDI est necessaire pour injecter les disques dans le stockage du cluster

## 4. Chemin technique d'une migration reelle

Le pipeline reel suit en pratique les etapes suivantes :

1. le frontend collecte les informations sur la VM
2. le backend verifie la compatibilite et genere un plan
3. le backend prepare un job de migration
4. `qemu-img` convertit le disque si le format n'est pas directement acceptable
5. `virtctl image-upload` envoie le disque vers un PVC cible
6. le backend construit un manifeste `VirtualMachine`
7. `oc apply` cree la VM dans OpenShift

Ce decoupage a ete choisi pour garder une chaine explicable : chaque etape est visible, testable et peut echouer de maniere isolee.

## 5. Choix d'installation et de deploiement

### 5.1 Environnement Python

Le projet utilise Python 3.11 avec FastAPI, SQLAlchemy, scikit-learn et les bibliotheques associees.

Pourquoi :

- Python simplifie l'integration entre API, logique metier, parsing systeme et ML
- FastAPI permet d'exposer rapidement une API claire et documentee
- scikit-learn est suffisant pour la couche IA du projet

### 5.2 Conteneurisation

Le `Dockerfile` construit une image basee sur `python:3.11-slim` et ajoute :

- `libvirt-dev`
- `qemu-utils`
- les dependances Python du projet

Pourquoi :

- le backend peut etre deploie de facon reproductible
- `qemu-img` est indispensable pour la conversion
- l'image reste relativement simple pour les tests

### 5.3 Deploiement OpenShift

Le dossier `k8s/openshift/` contient les manifests principaux :

- `namespace.yaml`
- `imagestream.yaml`
- `buildconfig.yaml`
- `deployment.yaml`
- `service.yaml`
- `route.yaml`
- `pvc.yaml`
- `configmap.yaml`

Pourquoi cette organisation :

- elle suit une logique OpenShift classique
- elle separe la construction d'image, le runtime, le stockage et l'exposition reseau
- elle permet de rejouer facilement le deploiement

## 6. Difficultes rencontrees et solutions retenues

### 6.1 VM locale invisible depuis le bastion

Probleme :

- certaines VMs VMware existaient uniquement sur le PC utilisateur
- le backend ne pouvait donc ni les decouvrir ni les analyser directement

Solution :

- ajouter un precheck local dans le frontend
- parser le `.vmx` dans le navigateur
- reconstruire localement les details VM, l'analyse et le plan

Pourquoi cette solution :

- elle respecte la realite reseau du projet
- elle evite d'imposer un acces disque direct du bastion vers le poste utilisateur

### 6.2 Disques VMware split

Probleme :

- plusieurs VMs avaient un disque principal descripteur et plusieurs segments `-s001`, `-s002`, etc.
- traiter uniquement le fichier principal cassait l'analyse ou la conversion

Solution :

- prise en charge d'un bundle de fichiers
- selection du disque principal et conservation des morceaux associes

Pourquoi cette solution :

- c'est le comportement reel des VMs VMware volumineuses
- cela rend le pipeline compatible avec les cas de test terrain

### 6.3 Upload navigateur des gros disques

Probleme :

- les uploads tres volumineux depuis le navigateur ont provoque des erreurs de type `Failed to fetch`

Solution :

- utiliser le navigateur surtout pour le pilotage, l'analyse et le precheck
- garder la migration lourde cote bastion quand le disque est deja accessible cote serveur

Pourquoi cette solution :

- un navigateur n'est pas le meilleur canal pour des dizaines de Go
- l'architecture devient plus robuste en separant controle leger et transfert lourd

### 6.4 Probleme de stockage OpenShift

Probleme :

- absence de `StorageClass`
- PVC en `Pending`
- blocage du pipeline au niveau CDI / provisionnement

Solution :

- ajout et correction du provisionnement de stockage
- verification du comportement du `HostPathProvisioner`
- adaptation du `StorageClass` et du mode de binding

Pourquoi cette solution :

- la logique applicative etait deja correcte
- le vrai blocage etait dans la couche plateforme, pas dans le code Python

### 6.5 Incoherence du pool `legacy`

Probleme :

- le provisioner cherchait un pool `legacy` qui ne correspondait pas a la configuration initiale

Solution :

- aligner le nom du pool et son chemin avec la configuration attendue

Pourquoi cette solution :

- sans alignement exact, `virtctl image-upload` ne pouvait pas finaliser la creation du volume

### 6.6 Authentification frontend/backend

Probleme :

- le frontend travaillait en JWT alors que le backend n'etait pas toujours lance en mode JWT

Solution :

- activer `AUTH_MODE=jwt`
- definir `JWT_SECRET`
- relancer l'API avec une configuration coherente

Pourquoi cette solution :

- elle evite un comportement incoherent entre UI et API
- elle rend le parcours login/register exploitable

## 7. Pourquoi cette architecture est pertinente pour le PFE

Cette infrastructure a ete retenue parce qu'elle repond a quatre contraintes reelles en meme temps :

1. gerer des VMs visibles localement ou cote bastion
2. separer le pilotage utilisateur de l'execution systeme
3. integrer un vrai cluster OpenShift comme cible
4. conserver une architecture pedagogique, explicable et testable

Autrement dit, l'architecture n'a pas ete choisie pour etre "complexe", mais parce qu'une architecture plus simple aurait masque les vrais problemes de migration observes pendant les essais.

## 8. Limites actuelles

Les principales limites d'infrastructure restantes sont :

- le stockage des jobs est encore en memoire pour la partie suivi de migration
- SQLite convient bien au prototype, mais pas a une charge multi-instance
- l'upload navigateur reste fragile pour les tres gros volumes
- la creation de la VM OpenShift peut reussir avant que le disque migre soit totalement bootable

## 9. Conclusion

L'infrastructure du projet est deja suffisante pour demontrer une vraie chaine de migration vers OpenShift Virtualization. Les difficultes les plus importantes n'ont pas uniquement ete des difficultes de code, mais surtout des difficultes d'accessibilite des VMs, de stockage et d'orchestration entre plusieurs environnements. C'est justement cette realite qui justifie les choix d'architecture retenus.
