# Rapport d'avancement - PFE Migration Intelligente de VMs vers OpenShift

## Resume

Ce projet de fin d'etudes a pour finalite la conception et la mise en oeuvre d'une plateforme capable d'accompagner la migration de machines virtuelles vers **OpenShift Virtualization**. L'objectif n'est pas seulement de deplacer une VM d'un environnement a un autre, mais de proposer une chaine de traitement complete comprenant la decouverte, l'analyse de compatibilite, la preparation technique, la recommandation d'une strategie de migration et, a terme, l'execution effective de la migration.

Au cours de l'avancement actuel, plusieurs briques fonctionnelles ont ete implementees et validees. Le projet dispose aujourd'hui d'un backend FastAPI, d'un frontend React, d'un moteur d'analyse de compatibilite, d'un planificateur de conversion, d'un composant de recommandation base sur l'IA, ainsi que d'une integration reelle avec OpenShift via `oc`, `virtctl` et `qemu-img`. Des tests ont ete realises aussi bien sur une VM locale volumineuse que sur une petite VM de validation, ce qui a permis d'identifier les veritables points de blocage restants.

Le present document tient lieu a la fois de presentation academique du projet et de rapport d'avancement des travaux deja accomplis.

## 1. Contexte et problematique

Dans les infrastructures modernes, la migration d'applications virtualisees vers des plateformes cloud-native represente un enjeu important. Toutefois, le passage d'une VM classique vers OpenShift ne peut pas etre traite comme une simple copie de disque. Il faut tenir compte :

- du format des disques
- des ressources CPU et memoire
- du modele des interfaces reseau
- des contraintes de stockage du cluster cible
- de la strategie de migration la plus adaptee

Le projet s'inscrit dans cette problematique en cherchant a automatiser et fiabiliser le processus de migration, tout en gardant une approche pedagogique et explicable.

## 2. Objectifs du projet

L'objectif general du projet est de developper une plateforme capable de prendre en charge le cycle suivant :

1. decouverte d'une machine virtuelle source
2. analyse de sa compatibilite avec OpenShift Virtualization
3. generation d'un plan de conversion technique
4. recommandation d'une strategie de migration a l'aide d'un moteur intelligent
5. execution d'une migration reelle vers OpenShift
6. verification de la presence de la VM dans la console OpenShift

Deux categories de sources ont ete particulierement prises en compte :

- les VMs accessibles directement par le backend, par exemple `KVM/libvirt` ou `VMware Workstation` sur la machine d'execution du backend
- les VMs locales presentes sur le poste utilisateur, non visibles directement depuis le bastion

## 3. Architecture generale retenue

L'architecture de travail qui s'est imposee au fur et a mesure des essais est la suivante :

- un `frontend React` execute sur le poste local de l'utilisateur
- un `backend FastAPI` execute sur le bastion
- un cluster cible avec `OpenShift Virtualization`
- des VMs sources pouvant provenir de `VMware Workstation` ou de `KVM/libvirt`

Cette architecture repond a une contrainte importante observee pendant les tests : une VM locale sur le PC utilisateur n'est pas necessairement accessible depuis le bastion. Il a donc fallu distinguer les traitements qui peuvent etre effectues localement de ceux qui doivent etre delegues au bastion et au cluster.

## 4. Organisation du projet

Le projet est structure autour des composants suivants :

- `src/api/` : API REST FastAPI
- `src/discovery/` : modules de decouverte de VMs KVM et VMware Workstation
- `src/analysis/` : logique d'analyse de compatibilite OpenShift
- `src/conversion/` : plan de conversion de disques et d'interfaces
- `src/migration/` : orchestration et strategie de migration
- `src/openshift/` : appels aux outils OpenShift et KubeVirt
- `src/ml/` : moteur IA de recommandation
- `frontend/frontend-app/` : interface utilisateur React
- `k8s/openshift/` : manifests de deploiement
- `docs/` : documentation utilisateur et technique

## 5. Travaux realises

### 5.1 Mise en place de l'environnement d'execution

Plusieurs validations initiales ont ete effectuees avec succes :

- le bastion est accessible depuis le poste local
- le backend FastAPI peut etre lance sur le bastion
- le frontend React peut etre lance sur le PC local
- un tunnel SSH permet d'exposer l'API du bastion sur la machine locale
- l'acces au cluster OpenShift a ete configure a l'aide d'un `kubeconfig` valide
- `OpenShift Virtualization` est installe et les operateurs associes sont en etat `Running`

### 5.2 Verification des dependances critiques

Les outils suivants ont ete identifies comme indispensables au volet migration reelle :

- `oc`
- `virtctl`
- `qemu-img`
- `python3`

Leur presence a ete verifiee sur le bastion. Le backend a ensuite ete relance en mode migration reelle avec les variables d'environnement appropriees, notamment :

- `ENABLE_REAL_MIGRATION=true`
- `AUTH_MODE=jwt`
- `OPENSHIFT_UPLOADPROXY_URL=...`
- `KUBECONFIG=...`

### 5.3 Stabilisation de l'authentification entre frontend et backend

Un premier probleme fonctionnel a ete observe lors de l'utilisation du frontend : le message `Auth mode is not jwt` apparaissait au moment de l'inscription.

L'analyse a montre que le backend etait lance avec le mode d'authentification par defaut, alors que le frontend avait ete developpe pour fonctionner avec un schema JWT.

La solution mise en oeuvre a consiste a :

- activer `AUTH_MODE=jwt`
- definir `JWT_SECRET`
- relancer l'API dans le meme environnement
- tester les endpoints `register` et `login`

Cette correction a permis de rendre fonctionnel l'ensemble du parcours d'authentification depuis le frontend.

### 5.4 Evolution du frontend vers un vrai pipeline de migration

Le frontend a ete progressivement transforme pour ne plus etre une simple interface demonstrative, mais un veritable point de pilotage du workflow de migration.

Les ajouts principaux sont les suivants :

- affichage de l'etat de sante du backend
- decouverte des VMs cote backend
- lancement des etapes `Analyze` et `Plan`
- affichage des resultats de compatibilite et de strategie
- suivi de `job_id`
- formulaire de migration reelle vers OpenShift
- ajout d'un message de `Precheck`
- verrouillage du bouton de migration tant que la VM n'a pas passe l'etape de planification

Cette evolution constitue une avancee importante, car elle rapproche l'interface du comportement attendu d'une veritable plateforme de migration.

### 5.5 Prise en charge des VMs VMware locales

L'un des principaux problemes rencontres concernait les VMs locales VMware Workstation presentes uniquement sur le PC de l'utilisateur. Dans ce cas, le backend du bastion ne pouvait pas retrouver la VM, et l'etape `Analyze` echouait avec un message du type `VM 'devops' non trouvee`.

Ce comportement etait logique : l'analyse initiale reposait sur la decouverte cote backend, donc sur une VM visible depuis le bastion.

Pour corriger cette limite, un mecanisme de precheck local a ete introduit dans le frontend :

- lecture locale du fichier `.vmx`
- extraction des caracteristiques de la VM dans le navigateur
- reconstitution des informations utiles sur les disques et le reseau
- execution locale de l'analyse de compatibilite
- generation locale du plan de conversion
- recommandation locale d'une strategie heuristique lorsque la VM n'est pas accessible au backend

Cette solution a permis de traiter les VMs locales sans envoyer immediatement de gros volumes de donnees au bastion.

### 5.6 Support des disques VMware de type split VMDK

Les tests ont montre que plusieurs VMs VMware utilisaient un disque principal de type descripteur `*.vmdk` accompagne de segments `-s001.vmdk`, `-s002.vmdk`, etc.

Dans une premiere version, seul le fichier descripteur etait pris en compte, ce qui provoquait des echecs de conversion et d'analyse.

Des adaptations ont donc ete apportees :

- support de la selection multiple de fichiers
- prise en charge simultanee du `.vmx` et des segments `vmdk`
- logique permettant d'identifier le disque principal et ses morceaux associes

Cette amelioration a ete indispensable pour prendre en charge correctement les VMs VMware reelles.

## 6. Difficultes techniques rencontrees

### 6.1 Limites de l'upload navigateur pour les grandes VMs

Une tentative de migration d'une VM locale volumineuse a mis en evidence une faiblesse importante : l'upload de plusieurs dizaines de gigaoctets via le navigateur a provoque des erreurs de type `Failed to fetch`.

Cette difficulte a conduit a une conclusion importante :

- le navigateur est adapte au pilotage des etapes d'analyse et de planification
- il n'est pas adapte comme canal principal de transport pour de tres gros disques de VM

Cette observation a oriente le projet vers une separation plus nette entre :

- les traitements legers, effectues localement dans le frontend
- les traitements lourds, delegues au backend et au bastion

### 6.2 Problemes lies au stockage OpenShift

Une fois le pipeline logiciel en etat de fonctionnement, le blocage principal s'est deplace vers le cluster OpenShift.

Les constats successifs ont ete les suivants :

- absence totale de `StorageClass`
- PVC en etat `Pending`
- besoin de creer un `HostPathProvisioner`
- apparition d'un `StorageClass` par defaut
- necessite de remplacer le mode `WaitForFirstConsumer` par `Immediate`
- erreur de pool de stockage `legacy` non trouve

Ces observations ont montre que la logique applicative etait fonctionnelle, mais que le cluster n'etait pas encore totalement prepare pour accepter les volumes requis par `virtctl image-upload`.

### 6.3 Incoherence de configuration du HostPathProvisioner

Le provisioner de stockage attendait un pool nomme `legacy`, alors qu'un pool `local` avait ete defini initialement. Cette incoherence entrainait une erreur explicite lors du provisionnement :

`unable to locate path for storage pool legacy`

La configuration a donc ete corrigee de facon a declarer :

- `name: legacy`
- `path: /var/hpvolumes`

Apres cette correction, le `HostPathProvisioner` est passe en etat `Available=True` et les pods CSI associes ont ete recrées avec succes.

## 7. Campagne de validation

### 7.1 Cas de la VM `devops`

La VM `devops`, volumineuse et composee de plusieurs segments de disque, a servi de premier cas d'etude. Elle a permis de mettre en evidence plusieurs limites :

- impossibilite de decouverte depuis le bastion
- insuffisance du mode de precheck strictement backend
- fragilite de l'upload navigateur pour des tailles importantes

Ce cas a ete determinant pour orienter l'architecture vers un precheck local dans le navigateur.

### 7.2 Cas de la VM `test`

Une petite VM nommee `test` a ensuite ete creee afin de valider le pipeline de bout en bout dans un contexte plus simple.

Les fichiers suivants ont ete identifies :

- `test.vmx`
- `test.vmdk`
- `test-s001.vmdk`
- `test-s002.vmdk`
- `test-s003.vmdk`

Les resultats obtenus sont significatifs :

- `Analyze` fonctionne
- `Plan` fonctionne
- la soumission de migration vers OpenShift est acceptee
- les PVC necessaires a l'upload sont crees
- le pod `cdi-upload-test-disk` est planifie
- la ressource `VirtualMachine` nommee `test` est creee dans le namespace `vm-migration`
- la VM apparait dans la console OpenShift avec l'etat `Running`
- la `VirtualMachineInstance` associee obtient une adresse IP et un noeud d'execution
- la console texte `virtctl console` peut etre etablie

Ainsi, le projet a depasse la simple validation theorique et a atteint de veritables etapes d'execution sur OpenShift.

### 7.3 Resultat final du cas `test`

Le cas `test` a permis d'obtenir une validation tres importante pour le projet. En effet, la migration ne s'est pas arretee a la seule soumission du job : la VM a effectivement ete creee sur le cluster OpenShift, visible dans la console web et associee a une instance en cours d'execution.

Les verifications effectuees ont permis de confirmer :

- la presence de la ressource `VirtualMachine`
- l'etat `Running` et `Ready` de la VM dans OpenShift
- la presence d'une `VirtualMachineInstance`
- l'affectation d'une adresse IP au sein du cluster
- l'accessibilite de la console texte via `virtctl console`

Ce resultat permet d'affirmer que la chaine de migration vers OpenShift Virtualization est fonctionnelle du point de vue infrastructurel.

En revanche, l'etape de boot du systeme invite a revele une limite importante. Bien que la VM soit correctement creee et executee par OpenShift, le systeme invite affiche encore un message de type `No bootable device` ou `Failed to load Boot`. Cela signifie que la migration de l'infrastructure virtuelle est reussie, mais que le disque source ou son mode de boot n'est pas encore completement exploitable dans l'environnement cible.

Cette observation est essentielle d'un point de vue academique, car elle permet de distinguer clairement :

- la reussite de la migration au niveau plateforme OpenShift
- de la finalisation du demarrage du systeme d'exploitation invite

Le cas `test` valide donc la plus grande partie de la chaine fonctionnelle, tout en mettant en evidence un point restant a traiter sur la compatibilite de boot de l'OS migre.

## 8. Etat actuel du projet

### 8.1 Elements valides

Les points suivants peuvent etre consideres comme acquis a ce stade :

- le backend et le frontend demarrent correctement
- l'authentification JWT fonctionne
- le cluster OpenShift est accessible depuis le bastion
- `OpenShift Virtualization` est installe et operationnel
- la decouverte backend est fonctionnelle pour les cas visibles depuis le bastion
- les VMs VMware locales peuvent etre pre-analysees depuis le navigateur
- le plan de migration est genere
- la strategie de migration est calculee
- la soumission d'une migration reelle est fonctionnelle
- le stockage du cluster repond au pipeline CDI
- la ressource `VirtualMachine` peut etre creee sur OpenShift
- une petite VM de validation peut etre observee en etat `Running` dans la console OpenShift

### 8.2 Point de blocage residuel

Le principal point encore en cours de validation n'est plus l'apparition de la ressource `VirtualMachine` dans OpenShift, car cette etape a ete confirmee sur le cas `test`. Le point residuel concerne desormais la capacite du systeme d'exploitation invite a booter correctement apres import du disque dans l'environnement KubeVirt.

Autrement dit, le coeur logiciel du projet a largement progresse ; le travail restant se situe desormais au niveau de la compatibilite finale du disque importe, du chargeur de demarrage et du mode de boot de l'OS invite.

## 9. Place de l'intelligence artificielle dans le projet

Le projet integre un moteur de recommandation base sur un modele `Random Forest`. Son role est de proposer une strategie parmi les categories suivantes :

- `direct`
- `conversion`
- `alternative`

L'IA intervient comme aide a la decision dans le pipeline, en complement des regles de compatibilite et des contraintes techniques detectees.

Un avertissement de version `scikit-learn` a toutefois ete observe lors de l'execution sur le bastion, ce qui signifie que le modele persiste a ete entraine avec une version differente de celle presente dans l'environnement courant.

Par consequent :

- la brique IA est bien integree au projet
- elle est exploitable a des fins de demonstration
- un realignement ou re-entrainement du modele reste recommande pour garantir la robustesse scientifique des predictions

## 10. Apport des travaux realises

Les travaux realises jusqu'ici permettent de conclure que le projet a franchi plusieurs etapes structurantes :

- clarification de l'architecture cible
- transformation du frontend en veritable outil de pilotage
- prise en charge des VMs VMware locales
- ajout d'un precheck local adapte aux contraintes reelles
- distinction claire entre problemes applicatifs et problemes d'infrastructure
- progression jusqu'aux etapes concretes de provisionnement de volumes et d'upload vers OpenShift

Du point de vue academique, cette progression est importante car elle montre une demarche d'ingenierie iterative, basee sur l'observation, le diagnostic, l'ajustement de l'architecture et la validation experimentale.

## 11. Limites observees

A ce stade, plusieurs limites restent identifiees :

- l'upload de tres grosses VMs via le navigateur n'est pas suffisamment robuste
- la migration complete depend fortement de la bonne configuration du stockage OpenShift
- le boot de l'OS invite apres migration n'est pas encore garanti dans tous les cas
- certaines VMs de test peuvent etre migrees au niveau plateforme sans pour autant etre immediatement bootables
- le modele IA doit etre consolide du point de vue de la reproducibilite de l'environnement

## 12. Perspectives et travaux a poursuivre

Les perspectives les plus pertinentes pour la suite du projet sont les suivantes :

1. finaliser la correction du boot de l'OS invite apres migration
2. verifier la compatibilite du disque source avec les modes `BIOS` et `EFI`
3. mettre en place un mecanisme de transfert plus robuste pour les grosses VMs locales
4. etudier la mise en place d'un agent local sur le poste utilisateur pour completer le frontend
5. stabiliser l'environnement du modele IA et relancer l'entrainement si necessaire

## 13. Commandes utiles pour la reproduction

### Backend sur le bastion

```bash
source .venv/bin/activate
export KUBECONFIG=/root/ocp-install/auth/kubeconfig
export ENABLE_REAL_MIGRATION=true
export OPENSHIFT_NAMESPACE=vm-migration
export OPENSHIFT_UPLOADPROXY_URL=https://cdi-uploadproxy-openshift-cnv.apps.cluster.ocp.pfe.lan
export AUTH_MODE=jwt
export JWT_SECRET='pfe-migration-secret'
python src/main.py api
```

### Frontend sur le poste local

```powershell
ssh -L 8000:10.9.21.90:8000 root@10.9.21.90
cd frontend\frontend-app
npm install
$env:VITE_API_BASE="http://localhost:8000"
npm run dev
```

### Verification cote OpenShift

```bash
oc get pods -n openshift-cnv
oc get pvc -n vm-migration
oc get dv -n vm-migration
oc get vm -n vm-migration
oc get events -n vm-migration --sort-by=.metadata.creationTimestamp
```

### Consultation des jobs de migration

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"matricule":"test1","password":"123456"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl http://127.0.0.1:8000/api/v1/migration/jobs \
  -H "Authorization: Bearer $TOKEN"
```

## Conclusion generale

L'etat actuel du projet montre une progression solide et coherent avec les objectifs d'un PFE applique. Le travail deja realise ne se limite pas a une maquette superficielle : il a permis de construire une chaine fonctionnelle de pre-analyse, de planification et de soumission de migration, puis d'atteindre des etapes concretes d'integration avec OpenShift Virtualization.

Les difficultes rencontrees ont ete utiles pour faire evoluer l'architecture du projet dans une direction plus realiste, notamment en distinguant les traitements locaux, les traitements backend et les exigences d'infrastructure du cluster. La campagne de validation a permis d'obtenir un resultat majeur : une VM migree a bien ete creee, executee et observee dans la console OpenShift. La suite du travail portera principalement sur la stabilisation du demarrage du systeme invite apres migration, afin de transformer cette reussite infrastructurelle en une migration pleinement exploitable au niveau applicatif.
