# Template Presentation Pro (15 Slides) - Projet Infrastructure & Migration IA/ML

Ce template est en francais et suit strictement ton style (flat design, codes couleurs, structure 15 pages).

## 0) Charte visuelle globale (a appliquer a toutes les slides)

### Palette
- Fond principal: `#042C53`
- Fond contenu: `#F8F9FC`
- Accent bleu: `#378ADD`
- Succes / termine: `#1D9E75`
- Avertissement / partiel: `#BA7517`
- Erreur / bloquant: `#D85A30`
- Texte principal: `#2C2C2A`
- Texte discret: `#888780`

### Typographie
- Titres: `Trebuchet MS` (ou sans-serif geometrique gras), `36-44 pt`
- Sous-titres: meme famille, `18-24 pt`, medium
- Corps: `14-16 pt`, regulier
- Tech/code/ports/commandes: `Courier New`, `9-11 pt`

### Regles de style
- Flat design uniquement: pas de degrade, pas d'ombre
- Bordures fines `0.5 px`
- Badges tech en pilule arrondie
- Cartes probleme/solution avec bordure gauche coloree
- Header sur slides de contenu: fond `#042C53`, texte blanc + numero
- Espaces blancs larges, pas de surcharge visuelle

---

## Slide 1 - Couverture
Mise en page:
- Fond plein `#042C53`
- Badge haut gauche: `RESTITUTION 1`
- Titre central (blanc, 40-44 pt):
  `Migration intelligente de machines virtuelles vers OpenShift Virtualization`
- Sous-titre:
  `Projet Infrastructure, DevOps et IA/ML`
- Bas de page (meta):
  - Etudiant: `Abderrhamen Hanafi`
  - Entreprise: `NEXT STEP Tunisie`
  - Encadrant: `Bilel Charfi`
  - Date: `30/01/2026`

---

## Slide 2 - Contexte et Pipeline
Header:
- `02 | Contexte et pipeline`

Corps:
- Ligne de flux horizontal (4 etapes):
  `Decouverte -> Analyse -> Planification -> Migration`
- Pour chaque etape, un bloc avec:
  - icone simple
  - description 1 ligne

Texte de support:
- "Le pipeline couvre le cycle complet de la migration VM, de l'inventaire initial jusqu'au deploiement cible OpenShift."

---

## Slide 3 - Objectifs
Header:
- `03 | Objectifs de la restitution`

Corps:
- Grille 2x2 de cartes numerotees:
  - Carte 1 (`#378ADD`): Valider l'architecture technique
  - Carte 2 (`#1D9E75`): Montrer l'avancement reel
  - Carte 3 (`#BA7517`): Exposer les blocages
  - Carte 4 (`#D85A30`): Aligner les prochaines priorites

---

## Slide 4 - Diagramme d'Architecture
Header:
- `04 | Architecture cible`

Corps:
- Topologie en 3 zones:
  1. Utilisateur (frontend React)
  2. Bastion (FastAPI + outils + services infra)
  3. Cluster OpenShift (masters + CNV/CDI)
- Fleches de communication (HTTP/SSH/oc/virtctl)
- Badges tech: `KVM`, `VMware`, `FastAPI`, `OpenShift`, `CDI`, `KubeVirt`

---

## Slide 5 - Tableau Infrastructure
Header:
- `05 | Capacite infrastructure`

Corps:
- Tableau comparatif `Minimal vs Ideal`:
  - Bastion
  - Bootstrap
  - Master-1
  - Master-2
  - Master-3
- Codes couleur:
  - Minimal: ambre `#BA7517`
  - Ideal: sarcelle `#1D9E75`

Note:
- "Valeurs de reference pour contexte PFE, a valider selon charge CNV et version OpenShift."

---

## Slide 6 - Composants Techniques
Header:
- `06 | Composants et configuration`

Corps (2 colonnes):
- Gauche (pilules services):
  `BIND9`, `HAProxy`, `nginx`, `Chrony`, `FastAPI`, `oc`, `virtctl`, `qemu-img`
- Droite (ports/config):
  - `6443` API
  - `22623` MCS
  - `80/443` Ingress
  - `8080` Ignition
  - `8000` Backend

---

## Slide 7 - Sequence d'Installation
Header:
- `07 | Sequence d'installation UPI`

Corps:
- Timeline verticale numerotee (6 etapes):
  1. Preparation `install-config.yaml`
  2. `openshift-install create manifests`
  3. `openshift-install create ignition-configs`
  4. Installation bootstrap (`coreos-installer`)
  5. Installation masters
  6. `wait-for bootstrap-complete` puis `install-complete`

Bloc code monospace (petit):
```bash
openshift-install create manifests
openshift-install create ignition-configs
openshift-install wait-for install-complete
```

---

## Slide 8 - Etat d'Avancement
Header:
- `08 | Etat d'avancement`

Corps:
- Grille 2x3 cartes statut (point couleur + %):
  - Architecture: termine (`#1D9E75`)
  - Backend: termine (`#1D9E75`)
  - Frontend: termine (`#1D9E75`)
  - IA/ML: partiel (`#BA7517`)
  - Migration reelle: partiel/bloque (`#D85A30`)
  - Industrialisation: partiel (`#BA7517`)

---

## Slide 9 - Moteur IA/ML
Header:
- `09 | Moteur IA/ML - architecture`

Corps:
- Diagramme 2 couches:
  - Couche 1: heuristique explicable
  - Couche 2: ML supervise
- Regle de decision:
  - prediction ML si confiance >= seuil
  - sinon fallback heuristique
- Badges output:
  `strategie`, `confiance`, `justification`, `priorite`

---

## Slide 10 - Fonctionnalites et Pipeline ML
Header:
- `10 | Entrees et sorties du modele`

Corps en 3 blocs:
- Gauche: features d'entree
  - CPU, RAM, taille disque, format disque, compatibilite
- Centre: fleche de traitement
  - `feature extraction -> scoring -> prediction`
- Droite: resultats
  - strategie recommandee
  - niveau de confiance
  - raison resumee

---

## Slide 11 - Difficultes et Resolutions
Header:
- `11 | Difficultes majeures et resolutions`

Corps:
- 3 a 4 cartes avec bordure gauche corail (`#D85A30`):
  1. VM locale non visible bastion
  2. Upload gros disques via navigateur
  3. Stockage OpenShift (PVC Pending / HPP)
  4. Alignement auth JWT
- Dans chaque carte:
  - probleme (1 ligne)
  - solution appliquee (1 ligne en sarcelle `#1D9E75`)

---

## Slide 12 - Feuille de Route et Priorites
Header:
- `12 | Roadmap de finalisation`

Corps (3 blocs empiles):
- P1 `#D85A30`:
  - migration end-to-end validee
  - stabilisation stockage cluster
- P2 `#BA7517`:
  - robustesse (retry/timeouts)
  - amelioration ML
- P3 `#1D9E75`:
  - metriques finales
  - documentation + soutenance

---

## Slide 13 - Tableau de Bord des Metriques
Header:
- `13 | Metriques techniques`

Corps (2 colonnes):
- Colonne gauche (pipeline):
  - taux succes Analyze
  - taux succes Plan
  - taux succes Migrate
  - temps moyen par etape
- Colonne droite (IA):
  - couverture recommandations
  - latence inference
  - concordance ML vs heuristique

Note:
- Integrer des chiffres reels (meme partiels) avant presentation.

---

## Slide 14 - Evaluation des Risques
Header:
- `14 | Risques et mitigation`

Corps:
- 3 lignes de risques avec badge:
  - `ELEVE` / `MOYEN`
- Exemple:
  1. Stockage cluster instable - `ELEVE`
  2. Transfert gros disques - `MOYEN`
  3. Heterogeneite VMware - `MOYEN`
- Bloc mitigation en dessous:
  - checklist pre-demo
  - scenario fallback
  - preuves logs/captures

---

## Slide 15 - Questions & Validation Expert
Header:
- `15 | Questions a valider avec l'expert`

Corps:
- 4 blocs question avec badge `Q` bleu (`#378ADD`):
  1. Canal cible pour gros transferts
  2. Strategie stockage la plus fiable
  3. Niveau attendu pour la partie IA
  4. Priorisation finale (robustesse vs extension)

Cloture (bas slide):
- "Validation attendue aujourd'hui: architecture, stockage et priorites de finalisation."

---

## Bonus - Conseils execution presentation (optionnel)
- Duree cible: 15-18 minutes
- 1 minute max par slide
- Garder annexes en backup uniquement
- Toujours montrer au moins 2 preuves visuelles reelles (capture `oc get nodes` + capture `Analyze/Plan`)
