# Slides Restitution 1 - Expert Technique

Ce fichier est un **deck markdown decoupe slide par slide**.
Tu peux l'utiliser tel quel pour preparer PowerPoint/Canva/Google Slides.

---

## Slide 1 - Titre
**Restitution 1 - PFE Migration Intelligente de VMs vers OpenShift Virtualization**
- Etudiant: `Abderrhamen Hanafi`
- Entreprise: `NEXT STEP Tunisie`
- Encadrants: `Bilel Charfi`
- Date: `30/01/2026`

**Speaker notes**
- Objectif de cette restitution: montrer l'avancement reel, les blocages techniques et le plan pour finaliser.

---

## Slide 2 - Contexte et enjeu
- La migration VM -> OpenShift Virtualization n'est pas une simple copie disque.
- Il faut traiter: compatibilite, conversion, stockage, orchestration et validation.
- Le projet vise une chaine complete: `Discover -> Analyze -> Plan -> Migrate -> Monitor`.

**Speaker notes**
- Insister sur la difference entre prototype UI et plateforme de migration exploitable.

---

## Slide 3 - Objectifs de la restitution 1
- Valider l'architecture technique retenue.
- Montrer ce qui est operationnel aujourd'hui.
- Exposer les difficultes reelles rencontrees.
- Aligner les priorites de la phase suivante avec l'expert.

---

## Slide 4 - Choix d'architecture: pourquoi UPI Bare Metal
### Pourquoi **UPI** (User-Provisioned Infrastructure)
- Environnement on-prem/lab avec controle reseau infra.
- Besoin de maitriser DNS, LB, ignition, stockage.
- Permet d'apprendre et justifier toute la chaine infra du PFE.

### Pourquoi **Bare Metal / VM bare-metal-like** (hors IPI cloud)
- Pas de dependance aux APIs cloud provider.
- Comportement proche des environnements entreprise on-prem.
- Plus representatif des contraintes reelles de migration infra legacy.

### Pourquoi pas IPI ici
- IPI simplifie le provisioning mais masque des decisions infra critiques.
- Le PFE doit demontrer la comprehension bout-en-bout (reseau, boot, services, stockage).

**Speaker notes**
- Message cle: le choix est pedagogique et technique, pas de complexite gratuite.

---

## Slide 5 - Topologie retenue
- **Poste utilisateur**: frontend React, precheck local VMware.
- **Bastion (10.9.21.90)**: FastAPI + services infra UPI + outils de migration.
- **Cluster OpenShift**: 3 masters (`10.9.21.91/92/93`) en mode compact.
- Domaine cible: `cluster.ocp.pfe.lan`.

---

## Slide 6 - Composants infra sur le bastion
- `BIND9` (DNS)
- `HAProxy` (API/Ingress/MCS: 6443, 22623, 80, 443)
- `nginx` (serveur ignition: 8080)
- `Chrony` (NTP)
- `FastAPI` (backend: 8000)
- outils: `oc`, `virtctl`, `qemu-img`

**Ports critiques**
- API Kubernetes: `6443`
- Machine Config Server: `22623`
- Ingress: `80/443`
- Ignition: `8080`
- Backend API projet: `8000`

---

## Slide 7 - Ressources VM: minimal vs ideal (projet)
> Base pratique pour ton contexte PFE (a valider selon charge finale et version OCP).

| Noeud | Minimal labo | Ideal projet migration | Commentaire |
|---|---:|---:|---|
| Bastion | 2 vCPU, 4 Go RAM, 50 Go disk | 4 vCPU, 8-16 Go RAM, 100+ Go disk | 2/4/50 deja observe dans ton architecture; ideal pour logs/outils |
| Bootstrap (temporaire) | 4 vCPU, 16 Go RAM, 120 Go disk | 8 vCPU, 16-32 Go RAM, 120+ Go disk | Utilise uniquement pendant installation |
| Master-1 | 4 vCPU, 16 Go RAM, 120 Go disk | 8 vCPU, 32 Go RAM, 200+ Go disk | En compact, master porte aussi workload |
| Master-2 | 4 vCPU, 16 Go RAM, 120 Go disk | 8 vCPU, 32 Go RAM, 200+ Go disk | idem |
| Master-3 | 4 vCPU, 16 Go RAM, 120 Go disk | 8 vCPU, 32 Go RAM, 200+ Go disk | idem |

**Speaker notes**
- Expliquer que l'"ideal" vise une meilleure marge pour OpenShift Virtualization et CDI.

---

## Slide 8 - Prerequis avant installation cluster
- Synchronisation temps correcte (Chrony).
- Resolution DNS complete (`api`, `api-int`, `*.apps`, masters, bootstrap).
- HAProxy pret pour API/MCS/Ingress.
- nginx pret pour servir les fichiers ignition.
- Acces SSH/KVM/iLO/console pour lancer `coreos-installer`.
- Fichiers install OCP disponibles (`openshift-install`, pull-secret, ssh key).

Checklist rapide
- `dig api.cluster.ocp.pfe.lan`
- `curl http://<bastion>:8080/master.ign`
- test ports `6443/22623/80/443` depuis le reseau cluster

---

## Slide 9 - Sequence UPI: generation des artefacts
1. Preparer `install-config.yaml` (domain, network, pull-secret, ssh key).
2. `openshift-install create manifests`
3. (mode compact) verifier `mastersSchedulable: true` si aucun worker dedie.
4. `openshift-install create ignition-configs`
5. Copier `bootstrap.ign`, `master.ign`, `worker.ign` sur nginx bastion.

---

## Slide 10 - Sequence UPI: boot des noeuds
1. Installer RHCOS sur bootstrap via `coreos-installer` + `bootstrap.ign`.
2. Installer RHCOS sur `master-1/2/3` via `master.ign`.
3. Demarrer bootstrap puis masters.
4. Lancer `openshift-install wait-for bootstrap-complete`.
5. Retirer bootstrap du load-balancer apres completion.
6. Lancer `openshift-install wait-for install-complete`.

**Speaker notes**
- Mentionner que cette etape a ete le principal facteur de temps projet.

---

## Slide 11 - Post-install cluster (obligatoire)
- Configurer `kubeconfig` sur bastion.
- Verifier etat:
  - `oc get nodes`
  - `oc get co`
- Approuver CSRs si necessaire:
  - `oc get csr`
  - `oc adm certificate approve <csr>`
- Verifier acces console et route apps.

Critere de succes
- 3 masters en `Ready`
- Operators principaux en `Available=True`

---

## Slide 12 - Installation des composants sur les noeuds
### Sur bastion
- Paquets/services infra: DNS, HAProxy, nginx, Chrony.
- Outils projet: Python deps, `oc`, `virtctl`, `qemu-img`.
- Backend FastAPI + auth JWT + variables env migration.

### Sur masters (RHCOS)
- Pas d'installation manuelle lourde conseillee.
- Laisser OpenShift Operator-driven.
- Valider uniquement prerequis reseau/stockage/temps.

### Dans le cluster
- Installer OpenShift Virtualization (CNV).
- Verifier CDI et uploadproxy.
- Mettre en place un stockage fonctionnel (`StorageClass`, PVC binding, HPP si lab).

---

## Slide 13 - Pourquoi le stockage est critique
Blocages observes:
- absence de `StorageClass`
- PVC `Pending`
- incoherence pool HPP (`legacy`)

Impact:
- `virtctl image-upload` bloque meme si API/migration code est correcte.

Actions:
- corriger `HostPathProvisioner`
- aligner pool/path
- verifier CSI pods + mode binding

---

## Slide 14 - Architecture applicative projet
- Frontend React (pilotage workflow)
- Backend FastAPI modulaire:
  - `discovery`
  - `analysis`
  - `conversion`
  - `migration/orchestration`
  - `openshift client`
  - `ml`

Flux principal
- `Analyze` -> rapport compatibilite
- `Plan` -> plan conversion + strategie recommandee
- `Migrate` -> conversion + upload + VM manifest

---

## Slide 15 - Focus ML (IA)
- Approche hybride: heuristiques + modele supervise.
- Features: CPU, RAM, disque, compatibilite, profil risque.
- Sorties: strategie, confiance, justification, priorite.
- Integration in-process dans backend (pas microservice dedie au stade PFE).

Valeur
- Aide decision explicable avant action de migration.

---

## Slide 16 - Avancement actuel (factuel)
- Backend + frontend operationnels.
- Pipeline `Discover/Analyze/Plan` valide.
- Precheck local VMware (VM locale non visible bastion) implemente.
- Support split VMDK implemente.
- Migration reelle codee mais dependante de la stabilite cluster/stockage.

---

## Slide 17 - Difficultes majeures et resolutions
1. VM locale non visible par bastion -> precheck local frontend.
2. Upload navigateur gros disques -> separation controle leger vs transfert lourd.
3. Blocage stockage OpenShift -> correction HPP/StorageClass/PVC.
4. Incoherence auth frontend/backend -> alignement JWT.

---

## Slide 18 - Demonstration proposee (live)
1. Health backend + auth.
2. Discovery VM.
3. Analyze + lecture du score/issues.
4. Plan + recommandation strategie (ML/heuristique).
5. (si cluster stable) migration OpenShift et verification VM.
6. (fallback) mode simulation + logs techniques.

---

## Slide 19 - Ce qu'il reste a faire
### Priorite P1
- Finaliser 1 migration reelle bout-en-bout prouvee.
- Stabiliser definitivement stockage cluster.
- Ajouter observabilite et logs exploitables.

### Priorite P2
- Renforcer robustesse (timeouts/retry/erreurs).
- Ameliorer calibration ML (plus de cas etiquetes).
- Ajouter tests integration/e2e.

### Priorite P3
- Consolider metriques finales + documentation soutenance.

---

## Slide 20 - Metriques a presenter a l'expert
- Taux de succes par etape (`Analyze`, `Plan`, `Migrate`).
- Temps moyen par etape.
- Nb VMs testees (petites vs volumineuses).
- IA: couverture, temps d'inference, concordance heuristique vs ML.
- Incidents infra et temps de resolution.

---

## Slide 21 - Risques restants
- Variabilite infra OpenShift (selon config stockage/reseau).
- Performance transfert disques volumineux.
- Cas VMware heterogenes (format/segment/driver).

Plan de mitigation
- scenario de demo fallback
- checklist pre-demo cluster
- preuves logs/screenshots precollectees

---

## Slide 22 - Questions a valider avec l'expert
- Niveau attendu pour la partie IA (prototype robuste vs quasi production).
- Strategie cible pour migration gros disques (streaming, upload, staging bastion).
- Sizing final cluster pour soutenance.
- Priorisation finale: stabilite migration vs enrichissement fonctionnel.

---

## Slide 23 - Annexes techniques (optionnelles)
- Ports et flux reseau complets.
- Commandes de verification cluster.
- Variables d'environnement migration reelle.
- Exemples payload API / reponses JSON.

---

## Slide 24 - Backup demo (si cluster indisponible)
- Montrer pipeline simulation complet avec preuves.
- Montrer code migration reelle (`oc/virtctl/qemu-img`) et checklists preflight.
- Expliquer blocage exact infra + actions correctives deja appliquees.
- Donner plan date par date pour validation finale migration reelle.

---

## Annexe A - Commandes utiles (operateur)
```bash
# Verification cluster
oc get nodes
oc get co
oc get sc
oc get pvc -A
oc get pods -A | grep -E "cdi|kubevirt|csi"

# CSR
oc get csr
oc adm certificate approve <csr_name>

# Backend (bastion)
python src/main.py api

# Health API
curl http://10.9.21.90:8000/health
```

---

## Annexe B - Variables backend migration reelle
```bash
export ENABLE_REAL_MIGRATION=true
export AUTH_MODE=jwt
export JWT_SECRET="A_COMPLETER_SECRET"
export KUBECONFIG=/chemin/vers/kubeconfig
export OPENSHIFT_UPLOADPROXY_URL=https://cdi-uploadproxy-openshift-cnv.apps.cluster.ocp.pfe.lan
```

---

## Annexe C - Template "etat d'avancement" (a remplir avant passage)
- Date: `A_COMPLETER`
- Commit: `A_COMPLETER`
- Cluster:
  - Nodes Ready: `x/3`
  - Operators Available: `x/y`
  - StorageClass par defaut: `Oui/Non`
- Migration:
  - Nb tests: `A_COMPLETER`
  - Reussites: `A_COMPLETER`
  - Echecs: `A_COMPLETER`
  - Cause principale: `A_COMPLETER`
- IA:
  - Couverture recommandations: `A_COMPLETER`
  - Latence inference moyenne: `A_COMPLETER`
  - Concordance ML/heuristique: `A_COMPLETER`

---

## Annexe D - Runbook detaille UPI (checklist execution)
1. Preparer machine bastion et services reseau.
2. Generer artefacts d'installation OpenShift.
3. Publier les fichiers ignition.
4. Installer bootstrap + masters avec `coreos-installer`.
5. Finaliser installation, valider operateurs, puis installer CNV/CDI.

### 1) Bastion - preparation
```bash
# Services infra
sudo dnf install -y bind bind-utils haproxy nginx chrony
sudo systemctl enable --now named haproxy nginx chronyd

# Outils OpenShift/migration (selon methode interne)
oc version || true
virtctl version || true
qemu-img --version || true
```

### 2) Generation manifests + ignition
```bash
# Dossier d'installation
mkdir -p ~/ocp-install && cd ~/ocp-install

# Copier install-config.yaml ici
openshift-install create manifests

# Compact cluster: verifier masters schedulables si pas de workers dedies
# (adapter dans manifests/cluster-scheduler-02-config.yml si necessaire)

openshift-install create ignition-configs
ls -lh *.ign
```

### 3) Publication ignition via nginx (bastion:8080)
```bash
sudo mkdir -p /var/www/html/ignition
sudo cp bootstrap.ign master.ign worker.ign /var/www/html/ignition/
sudo restorecon -Rv /var/www/html/ignition || true
curl http://10.9.21.90:8080/ignition/master.ign
```

### 4) Installation RHCOS sur bootstrap/masters
```bash
# Sur chaque noeud (depuis ISO live RHCOS), exemple:
sudo coreos-installer install /dev/sda \
  --ignition-url http://10.9.21.90:8080/ignition/bootstrap.ign \
  --insecure-ignition
sudo reboot

# Pour masters, utiliser master.ign
```

### 5) Finalisation installation
```bash
# Sur bastion
openshift-install wait-for bootstrap-complete --log-level=info
openshift-install wait-for install-complete --log-level=info

export KUBECONFIG=~/ocp-install/auth/kubeconfig
oc get nodes
oc get co
```

---

## Annexe E - Installations par couche (qui installe quoi)
### Bastion (obligatoire)
- DNS (`bind`), LB (`haproxy`), ignition HTTP (`nginx`), NTP (`chrony`).
- Backend FastAPI + dependances Python.
- Outils `oc`, `virtctl`, `qemu-img`.

### Bootstrap (temporaire)
- Aucune personnalisation applicative.
- Seulement RHCOS + `bootstrap.ign`.
- Retire du flux apres `bootstrap-complete`.

### Masters (persistants)
- RHCOS + `master.ign`.
- Pas d'installation applicative manuelle recommandee.
- Les composants Kubernetes/OpenShift sont geres par Operators.

### Cluster (post-install)
- OpenShift Virtualization operator.
- CDI (DataVolumes / upload).
- StorageClass fonctionnelle + HPP (si environnement lab).

---

## Annexe F - Decision UPI vs IPI (argumentaire jury)
| Critere | UPI (choisi) | IPI |
|---|---|---|
| Controle reseau | Tres eleve (DNS/LB/NTP/ignition) | Plus automatise |
| Effort installation | Plus eleve | Plus faible |
| Valeur pedagogique PFE infra | Excellente | Moyenne |
| Dependance cloud provider | Faible | Souvent plus forte |
| Alignement avec ton contexte | Fort (lab/on-prem) | Moins adapte |

Conclusion:
- UPI a ete choisi pour maitriser les couches critiques qui impactent directement la migration VM.
- Ce choix explique la complexite, mais aussi la valeur technique de la restitution.

