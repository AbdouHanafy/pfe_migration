# Restitution 1 - Avancement Projet PFE Migration

## 1) Contexte
- **Projet**: Migration intelligente de machines virtuelles vers OpenShift Virtualization.
- **Stage**: NEXT STEP (Tunisie).
- **Objectif de la restitution 1**: faire valider l'etat d'avancement technique, partager les blocages, et aligner la suite des travaux.

## 2) Perimetre de la demonstration
- Decouverte des VMs (KVM / VMware Workstation selon contexte).
- Analyse de compatibilite OpenShift.
- Generation d'un plan de migration.
- Orchestration initiale de migration vers OpenShift.
- Interface frontend pour piloter le workflow.

## 3) Etat d'avancement (synthese)
- **Architecture globale**: faite.
- **Backend FastAPI**: fait (endpoints principaux disponibles).
- **Frontend React**: fait (pipeline utilisateur disponible).
- **Analyse + Planification**: fait (resultats exploitables).
- **Moteur de recommandation (IA/heuristique)**: partiellement fait (version hybride operationnelle).
- **Migration reelle OpenShift**: en cours (depend fortement du stockage cluster).
- **Industrialisation / robustesse**: en cours.

## 4) Realisations techniques deja faites
- Mise en place backend + frontend avec flux de travail coherents.
- Stabilisation de l'authentification JWT entre frontend et backend.
- Precheck local pour VMs VMware non visibles depuis le bastion.
- Support des disques VMware `split VMDK` (`-s001`, `-s002`, ...).
- Integration des outils `oc`, `virtctl`, `qemu-img` cote migration.
- Validation sur cas reel VM volumineuse + VM de test plus legere.

## 4.1) Focus IA/ML - moteur de recommandation
### Approche actuelle
- **Approche hybride**: couche 1 = regles heuristiques explicables (fallback garanti); couche 2 = modele supervise (classification) pour recommander une strategie.
- **Implementation**: module `src/ml/` (features + classifier + artefacts `model.pkl`/`scaler.pkl`) et integration dans le pipeline `Analyze -> Plan`.

### Algorithme / logique
- **Heuristique**: score de risque base sur des seuils techniques (CPU, RAM, disque, compatibilite).
- **ML supervise**: classifieur entraine sur des cas de migration (dataset interne) pour predire la strategie la plus adaptee.
- **Decision finale v1**: si confiance ML suffisante, on prend la prediction ML; sinon fallback heuristique.

### Criteres d'entree (features)
- Ressources VM: vCPU, RAM, taille disque totale.
- Profil disque: type/format, disque unique vs disque segmente.
- Compatibilite technique: niveau de compatibilite detecte pendant `Analyze`.
- Contexte d'execution: accessibilite locale/distante, contraintes de transfert.
- Signaux de risque: volumetrie elevee, conversion potentiellement couteuse, blocages infra identifies.

### Sorties du moteur (output)
- **Strategie recommandee** (exemple): migration assistee via pipeline standard, preparation prealable obligatoire, ou report technique.
- **Niveau de confiance** de la recommandation.
- **Justification resumee** (features dominantes/criteres declenchants).
- **Priorite de traitement** (faible, moyenne, haute) pour ordonnancer les VMs.

### Etat actuel du ML
- Pipeline d'extraction de features disponible.
- Modele initial entraine et utilisable dans le backend.
- Fallback heuristique actif pour garantir une reponse meme en cas de doute ML.
- Besoin d'augmenter le volume et la diversite des donnees pour fiabiliser la generalisation.

### Metriques et validation (restitution 1)
- **Deja mesurable**: taux de recommandations produites (couverture), temps moyen d'inference, concordance ML vs heuristique sur jeux de tests.
- **A consolider avant soutenance finale**: precision/recall/F1 sur dataset de validation, matrice de confusion par type de VM, taux d'acceptation expert de la recommandation.
- **A_COMPLETER**: inserer les valeurs chiffrees issues des derniers tests.

## 5) Difficultes rencontrees
### 5.1 Accessibilite des VMs locales
- **Probleme**: certaines VMs existent uniquement sur le poste utilisateur, pas sur le bastion.
- **Impact**: echec de l'analyse cote backend si decouverte distante uniquement.
- **Action**: ajout d'un precheck local (lecture `.vmx` + extraction infos utiles).

### 5.2 Upload de gros volumes via navigateur
- **Probleme**: erreurs type `Failed to fetch` sur tres gros disques VM.
- **Impact**: pipeline incomplet pour migration lourde via simple upload web.
- **Action**: separation claire entre etapes legeres (frontend) et lourdes (backend/bastion).

### 5.3 Configuration stockage OpenShift
- **Probleme**: absence/mauvaise configuration `StorageClass` / PVC `Pending` / HPP mal aligne.
- **Impact**: blocage `virtctl image-upload` meme si applicatif correct.
- **Action**: ajustements `HostPathProvisioner`, pool, mode de binding, verification CSI.

## 6) Analyse de l'avancement
### Points forts
- Base applicative stable et modulaire.
- Pipeline metier coherent: Discover -> Analyze -> Plan -> Migrate.
- Bonne capacite d'adaptation face aux contraintes terrain (VMs locales, disques split).
- Moteur IA explicable (ML + heuristique) deja integre au flux de decision.

### Points sensibles
- Dependance forte a l'etat du cluster OpenShift.
- Besoin de fiabiliser les transferts de gros disques.
- Besoin d'augmenter la couverture de tests bout-en-bout.

## 7) Ce qu'il reste a faire (plan de travail)
## Priorite 1 (court terme)
- Finaliser un scenario de migration reelle 100% valide de bout en bout.
- Stabiliser definitivement le stockage cluster pour supprimer les blocages PVC/upload.
- Ajouter des traces/observabilite pour diagnostiquer plus vite les echecs.

## Priorite 2 (moyen terme)
- Renforcer robustesse (gestion d'erreurs, retries, timeouts).
- Completer la strategie IA avec plus de cas etiquetes et calibration de seuil de confiance.
- Ajouter des tests d'integration et e2e representatifs.

## Priorite 3 (finalisation)
- Consolider les metriques (temps, taux de succes par etape, causes d'echec).
- Finaliser la documentation utilisateur/technique.
- Preparer la soutenance finale (demo + slides + preuves techniques).

## 8) Risques restants
- Variabilite de l'environnement OpenShift selon la configuration infra.
- Temps de transfert eleve pour disques volumineux.
- Complexite de certains cas VMware heterogenes.

## 9) Points a valider avec l'expert technique
- Architecture cible retenue pour migration lourde (canal de transfert recommande).
- Strategie de stockage OpenShift la plus fiable dans notre contexte.
- Niveau de profondeur attendu pour le moteur IA en phase PFE (prototype avance vs version quasi-industrielle).
- Priorisation finale: robustesse d'abord ou extension fonctionnelle d'abord.

## 10) Trame proposee de presentation (15-20 min)
1. Contexte + objectifs (2 min)
2. Architecture et choix techniques (3 min)
3. Demo de l'avancement actuel (5 min)
4. Difficultes majeures et resolutions (4 min)
5. Analyse + reste a faire + planning (4 min)
6. Questions ouvertes a l'expert (2 min)

## 11) Pieces a preparer avant la reunion
- Captures d'ecran du frontend (Analyze/Plan/Migrate).
- Logs backend sur un cas reussi et un cas en echec.
- Etat du cluster (`StorageClass`, PVC, HPP, pods CSI).
- Mini tableau d'indicateurs (nb tests, taux de succes, temps moyen).
- Tableau metriques IA (couverture, temps inference, precision/F1 si disponible).

---

### A completer avant envoi officiel
- Nom et prenom etudiant.
- Date exacte de la restitution 1.
- Version du projet / commit de reference.
- Valeurs chiffrees (taux de succes, durees, nombre de VMs testees).
