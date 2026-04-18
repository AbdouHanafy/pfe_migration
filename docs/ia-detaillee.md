# IA detaillee

## 1. Place de l'IA dans le projet

Dans ce projet, l'IA n'est pas chargee d'executer la migration elle-meme. Son role est plus precis et plus utile d'un point de vue decisionnel : recommander la strategie de migration la plus adaptee pour une VM donnee.

Les strategies possibles sont :

- `direct`
- `conversion`
- `alternative`

Ce choix est pertinent, car la vraie difficulte n'est pas seulement de migrer une VM, mais de savoir quelle approche est la plus raisonnable avant de lancer des actions couteuses.

## 2. Pourquoi ajouter une couche IA

Une logique purement statique a base de quelques `if` suffit pour des cas tres simples, mais elle devient vite limitee quand plusieurs facteurs s'accumulent :

- architecture de la VM
- RAM
- CPU
- nombre de disques
- format des disques
- bus des disques
- modele reseau
- score de compatibilite
- nombre de warnings
- nombre de blockers
- complexite globale du plan de conversion

L'IA a donc ete ajoutee pour obtenir une recommandation plus flexible qu'une simple regle binaire.

## 3. Pipeline IA complet

Le pipeline IA du projet suit plusieurs etapes.

### 3.1 Etape 1 : collecte des donnees techniques de la VM

Avant toute prediction, le systeme collecte les informations VM via les modules de decouverte :

- specs CPU / RAM / OS
- liste des disques
- formats des disques
- bus utilises
- interfaces reseau

Pourquoi cette etape :

- l'IA doit partir d'une representation concrete de la VM
- elle ne travaille pas sur du texte libre mais sur des attributs techniques objectifs

### 3.2 Etape 2 : analyse de compatibilite

Le module `analysis` produit :

- un score sur 100
- des warnings
- des blockers
- une classe de compatibilite

Pourquoi faire cette etape avant l'IA :

- cela transforme deja une partie des donnees brutes en signal metier interpretable
- le modele n'a pas a redecouvrir seul des regles evidentes

### 3.3 Etape 3 : generation du plan de conversion

Le module `conversion` calcule les actions necessaires.

Exemples :

- convertir un disque `vmdk` vers `raw`
- changer un bus `ide` vers `virtio`
- changer un modele reseau non optimal

Pourquoi integrer cette etape dans l'IA :

- le nombre et le type d'actions sont un bon indicateur de complexite
- une VM qui demande beaucoup d'actions n'appelle pas la meme strategie qu'une VM deja presque compatible

### 3.4 Etape 4 : extraction des features

Le fichier `src/ml/features.py` construit un vecteur numerique de 20 features.

Les families de features sont :

- architecture
- ressources machine
- structure disque
- compatibilite du stockage
- compatibilite reseau
- score et severite des problemes
- type d'OS
- estimation de taille disque
- niveau de complexite global

Pourquoi 20 features :

- c'est assez riche pour decrire la VM sans rendre le modele trop lourd
- elles melangent informations brutes et informations derivees

Exemples de features importantes :

- `is_x86_64`
- `memory_mb`
- `cpu_count`
- `disk_count`
- `needs_disk_conversion`
- `needs_bus_change`
- `needs_net_change`
- `compatibility_score`
- `blocker_count`
- `conversion_action_count`
- `total_disk_size_gb_est`

### 3.5 Etape 5 : creation du dataset d'entrainement

Le projet ne depend pas d'un grand dataset reel externe. Il genere un dataset synthetique dans `src/ml/train.py`.

Le generateur cree des profils de VMs representant differents cas :

- Linux simple
- Linux complexe
- Windows Server
- systeme legacy
- base de donnees multi-disques
- noeud Kubernetes
- VDI
- SAP / ERP
- Oracle DB
- etc.

Pourquoi un dataset synthetique :

- un PFE ne dispose pas toujours d'un grand historique de migrations reelles etiquetees
- cela permet de couvrir de nombreux cas de figure
- cela donne une base reproductible pour l'entrainement

### 3.6 Etape 6 : attribution des labels

Chaque profil synthetique recoit un label :

- `0 = direct`
- `1 = conversion`
- `2 = alternative`

Les labels sont affectes par des regles metier dans `_assign_label`.

Exemples de logique :

- presence de blockers -> `alternative`
- conversion disque importante -> `conversion`
- VM trop complexe ou trop grosse -> `alternative`
- VM tres compatible sans action -> `direct`

Pourquoi cette approche :

- il fallait une verite terrain initiale pour entrainer le modele
- ces regles encapsulent l'expertise metier du projet

## 4. Algorithme choisi : Random Forest

Le modele choisi est un `RandomForestClassifier`.

### 4.1 Pourquoi Random Forest

Cet algorithme a ete retenu car il est :

- robuste sur des donnees tabulaires
- facile a entrainer
- peu sensible au bruit
- capable de capter des relations non lineaires
- interpretable a un niveau raisonnable
- bien adapte a un prototype avec peu de maintenance

Pour ce projet, il est plus pertinent qu'un modele tres lourd ou qu'un reseau de neurones, car les donnees d'entree sont structurees et de taille modeste.

### 4.2 Pourquoi pas un algorithme plus complexe

Un modele plus complexe n'aurait pas forcement apporte de gain reel ici, parce que :

- le volume de donnees reelles est limite
- les features sont deja bien structurees
- la priorite du projet est la fiabilite et l'explicabilite, pas la sophistication maximale

### 4.3 Pourquoi pas uniquement des heuristiques

Les heuristiques seules existent deja en fallback, mais elles deviennent rapidement rigides. Le Random Forest apporte une decision plus souple lorsqu'il faut combiner plusieurs signaux simultanement.

## 5. Standardisation et pipeline d'apprentissage

Le pipeline d'entrainement applique aussi un `StandardScaler`, puis sauvegarde :

- `model.pkl`
- `scaler.pkl`
- `training_data.csv`

Le scaler n'est pas strictement indispensable pour un Random Forest, mais dans l'etat actuel du code il normalise le pipeline et facilite un futur remplacement du modele par un autre algorithme si necessaire.

## 6. Etapes d'entrainement

L'entrainement suit globalement ce schema :

1. generation du dataset synthetique
2. separation train/test
3. standardisation
4. entrainement du Random Forest
5. evaluation
6. sauvegarde du modele et du scaler

Pourquoi ce pipeline :

- il est simple
- il est reproductible
- il est suffisant pour un classifieur de strategie

## 7. Etapes d'inference en production

Quand l'API appelle `choose_strategy`, il se passe ceci :

1. extraction des features a partir de `vm_details`, `analysis` et `conversion_plan`
2. transformation par le scaler
3. prediction de classe
4. calcul des probabilites
5. calcul d'un score de confiance
6. generation d'une raison textuelle

Le systeme retourne :

- la strategie retenue
- la confiance
- les probabilites par classe
- l'indication `method = ml`
- une explication `reason`

Pourquoi cette sortie est utile :

- elle est plus exploitable qu'une simple etiquette
- elle aide l'utilisateur a comprendre la decision
- elle s'integre bien dans un rapport de migration

## 8. Fallback heuristique

Si `model.pkl` ou `scaler.pkl` ne sont pas disponibles, le projet bascule automatiquement vers une heuristique.

Pourquoi ce fallback est important :

- le backend continue a fonctionner meme sans modele charge
- la fonctionnalite IA ne bloque pas tout le pipeline
- cela rend le systeme plus robuste en demo et en developpement

La logique heuristique reste coherente avec les classes du projet :

- `non_compatible` -> `alternative`
- plusieurs actions -> `conversion` ou `alternative`
- tres bonne compatibilite sans action -> `direct`

## 9. Pourquoi cette IA est adaptee au projet

Le choix global est pertinent pour plusieurs raisons :

1. le probleme est un probleme de classification, pas de generation
2. les donnees sont tabulaires et bien structurees
3. le projet a besoin d'un modele simple a expliquer en soutenance
4. la prediction doit etre rapide et embarquee directement dans le backend
5. il faut une solution robuste meme avec un dataset reel limite

## 10. Limites actuelles de la couche IA

Les limites principales sont :

- le dataset est synthetique et non issu d'un grand historique reel
- le modele recommande une strategie, mais ne garantit pas la bootabilite finale
- certaines variables externes importantes, comme l'etat reel du cluster ou les specificites fines de l'OS invite, ne sont pas encore integrees comme features

Ces limites sont normales pour un PFE, et elles n'annulent pas la valeur de la couche IA. Au contraire, elles montrent clairement ce que fait le modele et ce qu'il ne fait pas.

## 11. Conclusion

La couche IA du projet a ete construite de maniere pragmatique : features techniques bien choisies, dataset synthetique base sur des regles metier, Random Forest pour la classification, probabilites de sortie, et fallback heuristique en cas d'absence du modele. Ce n'est pas une IA "decorative" ; c'est un module de recommandation concret, integre au pipeline de migration et suffisamment explicable pour un cadre academique.
