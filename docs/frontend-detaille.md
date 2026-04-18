# Frontend detaille

## 1. Role du frontend

Le frontend est l'interface de pilotage du projet. Il ne sert pas seulement a afficher des boutons ; il joue un role important dans la chaine de migration, surtout quand la VM source se trouve sur le poste local de l'utilisateur.

Le frontend permet :

- la connexion utilisateur
- la decouverte des VMs visibles cote backend
- l'analyse de compatibilite
- la generation du plan
- le lancement d'une migration simulee
- le lancement d'une migration reelle vers OpenShift
- le precheck local d'une VM VMware non visible depuis le bastion

## 2. Technologies choisies

Le frontend utilise :

- `React 19`
- `React Router`
- `Vite`

Pourquoi ce choix :

- React facilite la construction d'une interface modulaire
- React Router structure la navigation simplement
- Vite donne un demarrage rapide et une configuration legere

Pour un projet PFE, ce choix est pertinent car il permet d'aller vite sans sacrifier la lisibilite du code.

## 3. Decoupage du frontend

Le frontend est organise de maniere classique mais propre.

### 3.1 `src/pages/`

Ce dossier contient les pages principales :

- `HomePage.jsx`
- `LoginPage.jsx`
- `RegisterPage.jsx`
- `AboutPage.jsx`
- `NotFoundPage.jsx`

Pourquoi ce decoupage :

- chaque page represente une intention utilisateur claire
- la logique d'ecran reste separee des composants reutilisables

### 3.2 `src/components/`

Ce dossier contient les briques reutilisables :

- `NavBar`
- `ProtectedRoute`
- `Card`
- `Button`
- `Input`
- `Pill`
- `JsonBlock`
- `FieldGrid`

Pourquoi ce choix :

- eviter de dupliquer le code UI
- garder une interface coherente
- rendre `HomePage` plus lisible malgre la richesse fonctionnelle

### 3.3 `src/services/`

Ce dossier contient l'acces reseau :

- `api.js`
- `authService.js`

Pourquoi separer les services :

- les appels HTTP ne doivent pas etre melanges avec le rendu React
- cela facilite l'ajout des headers d'authentification
- la gestion des erreurs reste centralisee

### 3.4 `src/store/`

Ce dossier contient `AuthContext.jsx`.

Role :

- stocker le token JWT
- le partager dans l'application
- le persister dans `localStorage`

Pourquoi ce choix :

- l'authentification est un etat transverse
- React Context est suffisant ici, sans ajouter Redux ou une autre couche plus lourde

### 3.5 `src/hooks/`

On trouve notamment :

- `useAuth`
- `useLogger`

Pourquoi ces hooks :

- simplifier l'acces au contexte d'auth
- gerer proprement le journal d'activite de l'interface

### 3.6 `src/utils/`

Ce dossier contient les utilitaires, notamment `localVmware.js`.

Pourquoi ce dossier est important :

- il porte la logique locale de lecture `.vmx`
- il reproduit dans le navigateur une partie de l'analyse backend
- il permet de traiter des VMs locales sans dependre immediatement du bastion

## 4. Structure fonctionnelle de l'interface

### 4.1 `App.jsx`

`App.jsx` assemble :

- le `BrowserRouter`
- le `AuthProvider`
- la `NavBar`
- les routes

Pourquoi cette structure :

- elle place la navigation et l'auth au niveau global
- toutes les pages beneficient du meme contexte

### 4.2 Routage

La route `/` est protegee par `ProtectedRoute`.

Pourquoi :

- la page principale pilote des operations sensibles
- on ne veut pas exposer le tableau de controle sans authentification quand le backend est en mode JWT

### 4.3 `HomePage.jsx`

`HomePage` est la page la plus importante. Elle joue le role de "control room".

Elle regroupe les zones :

- `Discovery`
- `Analyze And Plan`
- `Migration`
- `OpenShift Real Migration`
- `Activity Log`

Pourquoi tout rassembler ici :

- le workflow de migration est sequentiel
- l'utilisateur doit voir l'etat de chaque etape au meme endroit
- cela reduit les changements de page inutiles pendant les tests

## 5. Pourquoi le frontend fait aussi du precheck local

C'est le point architectural le plus important du frontend.

### 5.1 Probleme initial

Certaines VMs VMware sont locales au poste utilisateur. Le backend sur bastion ne peut pas les voir. Si le frontend envoyait uniquement un nom de VM au backend, celui-ci repondait que la VM etait introuvable.

### 5.2 Solution retenue

Le frontend lit localement :

- le fichier `.vmx`
- les noms des fichiers de disques
- les informations CPU, RAM, OS, reseau

Il reconstruit ensuite :

- `details`
- `analysis`
- `conversion_plan`
- `strategy`

### 5.3 Pourquoi ce choix est bon

- il respecte la realite d'une VM locale
- il permet un diagnostic immediat
- il evite d'uploader de gros fichiers juste pour savoir si la VM est compatible
- il donne une experience plus fluide a l'utilisateur

Autrement dit, le frontend ne fait pas "trop de logique" par erreur ; il fait volontairement une logique locale parce que le contexte technique l'impose.

## 6. Gestion des fichiers locaux VMware

Le frontend accepte :

- `.vmx`
- `.vmdk`
- `.qcow2`
- `.img`
- `.raw`

Il gere aussi le cas des disques VMware split.

Pourquoi :

- une VM VMware reelle n'est pas toujours un seul gros fichier
- il faut souvent selectionner le descripteur et tous les segments

Le frontend essaye aussi d'inferer :

- le nom de VM
- le format disque
- le nom cible OpenShift

Pourquoi :

- cela reduit les erreurs de saisie
- cela rend l'outil plus pratique en demonstration

## 7. Communication avec le backend

Le frontend utilise `fetch` via `createApi`.

Principes :

- base URL configurable
- ajout automatique du header `Authorization`
- gestion simple des erreurs

Pourquoi un wrapper minimal :

- le projet n'a pas besoin d'une grosse couche reseau type Axios + interceptors complexes
- un petit service suffit et reste facile a relire

## 8. Choix UX et organisation de l'etat

Le frontend maintient dans `HomePage` :

- l'etat de la VM selectionnee
- l'etat d'analyse
- l'etat du job
- l'etat OpenShift
- les erreurs
- les indicateurs de chargement

Pourquoi cet etat local a la page :

- ce workflow est principalement concentre dans un seul ecran
- remonter tout cela dans un store global serait inutilement lourd

Le frontend ajoute aussi :

- un verrou de migration reelle apres planification
- un message `Precheck`
- un polling de statut de job

Pourquoi :

- il faut guider l'utilisateur
- la migration reelle ne doit pas etre declenchee trop tot
- l'utilisateur doit comprendre pourquoi une action est bloquee

## 9. Choix d'architecture frontend

### 9.1 Pourquoi React et pas une interface statique

- l'application manipule beaucoup d'etats
- plusieurs cartes doivent se mettre a jour apres les appels API
- il faut maintenir une experience interactive sur tout le workflow

### 9.2 Pourquoi une interface "control room"

- le projet est centre sur un pipeline technique
- il est plus efficace de montrer les etapes cote a cote
- cela convient bien a une soutenance ou a une demonstration

### 9.3 Pourquoi un frontend leger

Le frontend ne depend pas d'une grosse bibliotheque UI.

Pourquoi :

- garder le controle de l'interface
- reduire les dependances
- rester simple a maintenir

## 10. Limites actuelles

Les limites principales du frontend sont :

- `HomePage` concentre beaucoup de responsabilites et pourrait etre encore scindee
- l'upload de tres gros disques via navigateur reste limite
- le precheck local utilise une heuristique plus simple que le vrai modele backend

Ces limites sont normales dans l'etat actuel du projet, mais elles sont deja contournees de maniere raisonnable.

## 11. Conclusion

Le frontend a ete divise selon une logique claire : pages, composants, services, store, hooks et utilitaires. Le choix le plus important est d'avoir laisse au navigateur une partie de l'intelligence locale pour les VMs VMware presentes sur le poste utilisateur. Ce choix n'est pas un detail de confort ; c'est une reponse directe a la contrainte reelle du projet.
