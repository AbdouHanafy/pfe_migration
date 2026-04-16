# Architecture Complete — Migration Intelligente vers OpenShift

> PFE 2024-2025 | Compact Cluster UPI Bare Metal | cluster.ocp.pfe.lan

---

## 1. Vue d'ensemble

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            UTILISATEUR                                     │
│                        Navigateur Web (Chrome/Firefox)                     │
│                      http://localhost:5173  (React + Vite)                 │
└─────────────────────────┬──────────────────────────────────────────────────┘
                          │  HTTP/JSON  (Bearer Token JWT)
                          ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         COUCHE PRESENTATION                                │
│                              Frontend (React 19)                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │Discovery │ │ Analyze  │ │  Plan    │ │ Migrate  │ │    Monitor       │ │
│  │   Page   │ │   Page   │ │  Page    │ │  Page    │ │    Page          │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────────┘ │
│                                                                          │
│  Composants: NavBar, Card, Button, Input, Pill, JsonBlock, FieldGrid     │
│  Services: api.js (fetch + auth), authService.js (login/register)        │
│  Store: AuthContext.jsx (localStorage + React Context)                   │
└─────────────────────────┬──────────────────────────────────────────────────┘
                          │  REST API  (FastAPI)
                          ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                       COUCHE APPLICATION (API)                             │
│                          Backend (FastAPI — Python 3.11)                   │
│                          http://10.9.21.90:8000                            │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                    src/api/main.py (FastAPI)                         │ │
│  │                                                                      │ │
│  │  Routes:                                                             │ │
│  │    GET    /health                                                    │ │
│  │    POST   /api/v1/auth/login                                         │ │
│  │    POST   /api/v1/auth/register                                      │ │
│  │    GET    /api/v1/discovery/kvm                                      │ │
│  │    GET    /api/v1/discovery/vmware-workstation                       │ │
│  │    POST   /api/v1/migration/analyze/{vm_name}                        │ │
│  │    POST   /api/v1/migration/plan/{vm_name}                           │ │
│  │    POST   /api/v1/migration/start/{vm_name}                          │ │
│  │    GET    /api/v1/migration/status/{job_id}                          │ │
│  │    GET    /api/v1/migration/report/{job_id}                          │ │
│  │    POST   /api/v1/migration/openshift/{vm_name}                      │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  Middleware: CORS, Auth (JWT / API Key / None)                           │
│  Base de donnees: SQLite (via SQLAlchemy)                                │
└─────────────────────────┬──────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  COUCHE      │ │  COUCHE      │ │  COUCHE      │
│  DECOUVERTE  │ │  ANALYSE     │ │  IA / ML     │
│  (Module 1)  │ │  (Module 2)  │ │  (Module 4)  │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  COUCHE      │ │  COUCHE      │ │  COUCHE      │
│  CONVERSION  │ │ORCHESTRATION │ │  OPENSHIFT   │
│  (Module 3)  │ │  (Module 5)  │ │   CLIENT     │
└──────────────┘ └──────────────┘ └──────────────┘
```

---

## 2. Communication entre les couches

### 2.1 Flux de donnees complet

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│Utilis.  │────►│Frontend │────►│  API    │────►│Modules  │────►│OpenShift│
│         │◄────│         │◄────│(FastAPI)│◄────│Backend  │◄────│  CLI    │
└─────────┘     └─────────┘     └─────────┘     └─────────┘     └─────────┘
  HTTP/JSON     React/Vite     REST API       Python libs     oc/virtctl
  Browser       localhost:5173 localhost:8000  In-process      CLI tools
```

### 2.2 Detail des appels par etape

#### Etape 1 — Decouverte des VMs

```
Frontend                    Backend                      Hyperviseur
   │                           │                             │
   │  GET /api/v1/discovery/   │                             │
   │  vmware-workstation       │                             │
   ├──────────────────────────►│                             │
   │                           │  Parser .vmx files          │
   │                           ├────────────────────────────►│
   │                           │  Lire: OS, RAM, CPU, disks  │
   │                           │◄────────────────────────────┤
   │  Liste de VMs (JSON)      │                             │
   │◄──────────────────────────┤                             │
```

#### Etape 2 — Analyse de compatibilite

```
Frontend                    Backend                      Regles d'analyse
   │                           │                             │
   │  POST /api/v1/migration/  │                             │
   │  analyze/{vm_name}        │                             │
   ├──────────────────────────►│                             │
   │                           │  analyze_vm(vm_details)     │
   │                           ├────────────────────────────►│
   │                           │  20 regles de compatibilite │
   │                           │  Scoring 0-100              │
   │                           │  Blockers + Warnings        │
   │                           │◄────────────────────────────┤
   │  Rapport JSON             │                             │
   │  {compatibility, score,   │                             │
   │   issues, recommendations}│                             │
   │◄──────────────────────────┤                             │
```

#### Etape 3 — Plan de conversion

```
Frontend                    Backend                      Modules
   │                           │                             │
   │  POST /api/v1/migration/  │                             │
   │  plan/{vm_name}           │                             │
   ├──────────────────────────►│                             │
   │                           │  build_conversion_plan()    │
   │                           ├───────┐                     │
   │                           │       │ Format VMDK→raw     │
   │                           │       │ Bus SCSI→VirtIO     │
   │                           │       │ Net e1000→VirtIO    │
   │                           │◄──────┘                     │
   │                           │                             │
   │                           │  choose_strategy()          │
   │                           ├───────┐                     │
   │                           │       │ IA: 20 features     │
   │                           │       │ RF: prediction      │
   │                           │       │ Confiance + Probas  │
   │                           │◄──────┘                     │
   │                           │                             │
   │  Plan complet (JSON)      │                             │
   │  {analysis, plan,         │                             │
   │   strategy, confidence,   │                             │
   │   probabilities, reason}  │                             │
   │◄──────────────────────────┤                             │
```

#### Etape 4 — Migration simulee

```
Frontend                    Backend                      Job Store
   │                           │                             │
   │  POST /api/v1/migration/  │                             │
   │  start/{vm_name}          │                             │
   ├──────────────────────────►│                             │
   │                           │  create_job()               │
   │                           ├────────────────────────────►│
   │                           │  Thread: etapes simulees    │
   │                           │  discovery→analysis→conv→   │
   │                           │  transfer→verify            │
   │                           │                             │
   │  Job info (JSON)          │                             │
   │  {job_id, vm_name,        │                             │
   │   status, plan, steps}    │                             │
   │◄──────────────────────────┤                             │
   │                           │                             │
   │  GET /status/{job_id}     │                             │
   ├──────────────────────────►│                             │
   │                           │  get_job()                  │
   │                           ├────────────────────────────►│
   │  Status (JSON)            │                             │
   │◄──────────────────────────┤                             │
```

#### Etape 5 — Migration reelle (OpenShift)

```
Frontend                    Backend                      OpenShift CLI
   │                           │                             │
   │  POST /api/v1/migration/  │                             │
   │  openshift/{vm_name}      │                             │
   │  {disk_path, format,      │                             │
   │   target_name, pvc_size}  │                             │
   ├──────────────────────────►│                             │
   │                           │  ensure_namespace()         │
   │                           ├──── oc new-project ─────────►│
   │                           │◄────────────────────────────┤
   │                           │                             │
   │                           │  convert_disk_if_needed()   │
   │                           ├─ qemu-img convert ──────────►│
   │                           │◄────────────────────────────┤
   │                           │                             │
   │                           │  upload_disk()              │
   │                           ├─ virtctl image-upload ──────►│
   │                           │  (CDI DataVolume)           │
   │                           │◄────────────────────────────┤
   │                           │                             │
   │                           │  build_vm_manifest()        │
   │                           │  apply_manifest()           │
   │                           ├─ oc apply -f - ────────────►│
   │                           │  (VirtualMachine CRD)       │
   │                           │◄────────────────────────────┤
   │  Result (JSON)            │                             │
   │  {vm_name, namespace,     │                             │
   │   pvc, status: submitted} │                             │
   │◄──────────────────────────┤                             │
```

---

## 3. Position du module IA dans l'architecture

### Le module IA est une COUCHE INTERNE (pas separee)

```
┌──────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                             │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  src/api/main.py  (API REST — point d'entree)              │  │
│  │                                                            │  │
│  │  POST /plan/{vm_name}                                      │  │
│  │    ↓                                                       │  │
│  │    1. discovery.get_vm_details()     ──┐                   │  │
│  │    2. analyze_vm(vm_details)           │                   │  │
│  │    3. build_conversion_plan()          │  Meme processus   │  │
│  │    4. choose_strategy() ──────────────►┤  (meme thread,    │  │
│  │         ↓                              │   meme espace      │  │
│  │    ┌────────────────────────────┐     │   memoire)          │  │
│  │    │ src/ml/classifier.py       │     │                     │  │
│  │    │   ↓                        │     │                     │  │
│  │    │   predict(vm, analysis,    │     │                     │  │
│  │    │           conversion_plan) │     │                     │  │
│  │    │     ↓                      │     │                     │  │
│  │    │   model.predict_proba()    │     │                     │  │
│  │    │   (scikit-learn, in-process)     │                     │  │
│  │    └────────────────────────────┘     │                     │  │
│  │         ↓                             │                     │  │
│  │    {strategy, confidence,             │                     │  │
│  │     probabilities, reason}            │                     │  │
│  └───────────────────────────────────────┼─────────────────────┘  │
└──────────────────────────────────────────┼────────────────────────┘
                                           │
                                    Appelle en
                                    direct (fonction)
                                    PAS de reseau,
                                    PAS de service
                                    separe
```

### Pourquoi interne et pas separee ?

| Aspect | Couche Interne (notre choix) | Service Separe (microservice) |
|---|---|---|
| **Communication** | Appel de fonction Python | HTTP/gRPC entre services |
| **Latence** | ~0ms (in-process) | ~10-50ms (reseau) |
| **Deploiement** | 1 seul container | 2 containers minimum |
| **Complexite** | Simple | Orchestration supplementaire |
| **Scalabilite** | Liee a l'API | Independante |
| **Pour un PFE** | ✅ Suffisant | ❌ Overkill |

### Si tu devais le separer (architecture production) :

```
┌─────────────┐     HTTP/JSON      ┌─────────────────┐
│   API       │ ──────────────────►│  ML Service     │
│  Backend    │  POST /predict     │  (scikit-learn) │
│  (FastAPI)  │◄────────────────── │  Port 8001      │
│  Port 8000  │  {strategy,        │                 │
│             │   confidence}      │  model.pkl      │
└─────────────┘                    └─────────────────┘
```

**Mais pour ton PFE, l'approche interne est parfaitement justifiable.**
Le jury comprendra que pour un prototype, un microservice IA serait excessif.

---

## 4. Vue d'infrastructure complete

```
┌──────────────────────────────────────────────────────────────────┐
│                    PC Developpeur (ton desktop)                  │
│                                                                  │
│  ┌─────────────────────────────┐    ┌────────────────────────┐  │
│  │  Navigateur                 │    │  Terminal              │  │
│  │  http://localhost:5173      │    │  SSH → bastion         │  │
│  │  (React Frontend)           │    │  (VPN + port forward)  │  │
│  └────────────┬────────────────┘    └────────────────────────┘  │
│               │                                                  │
└───────────────┼──────────────────────────────────────────────────┘
                │
                │ VPN (reseau 10.9.21.0/24)
                ▼
┌──────────────────────────────────────────────────────────────────┐
│                    BASTION (10.9.21.90)                          │
│  RHEL 9.6 — 2 vCPU / 4 GB RAM / 50 GB disk                      │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Services Infrastructure                                   │  │
│  │  ┌──────────┐ ┌──────────┐ ┌───────┐ ┌──────────┐        │  │
│  │  │ BIND9    │ │ HAProxy  │ │nginx  │ │ Chrony   │        │  │
│  │  │ DNS :53  │ │ LB :6443 │ │HTTP   │ │ NTP :123 │        │  │
│  │  │          │ │ :22623   │ │:8080  │ │          │        │  │
│  │  │          │ │ :80/:443 │ │       │ │          │        │  │
│  │  └──────────┘ └──────────┘ └───────┘ └──────────┘        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Application Backend (FastAPI)                             │  │
│  │  Port 8000                                                 │  │
│  │                                                            │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐ │  │
│  │  │Discovery │ │ Analysis │ │ IA/ML    │ │Orchestration │ │  │
│  │  │Module    │ │ Module   │ │ Module   │ │  Module      │ │  │
│  │  │          │ │          │ │          │ │              │ │  │
│  │  │ • libvirt│ │ • 20     │ │ • 20     │ │ • Job store  │ │  │
│  │  │ • .vmx   │ │   regles │ │   feat.  │ │ • Steps      │ │  │
│  │  │ • pyvmomi│ │ • Score  │ │ • RF     │ │ • Reports    │ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘ │  │
│  │                           ▲                                │  │
│  │                           │ in-process                     │  │
│  │                    ┌──────┴──────┐                         │  │
│  │                    │ model.pkl   │                         │  │
│  │                    │ scaler.pkl  │                         │  │
│  │                    │ (scikit)    │                         │  │
│  │                    └─────────────┘                         │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Donnees locales                                           │  │
│  │  SQLite: migration.db                                      │  │
│  │  IA: training_data.csv (20 000 VMs)                        │  │
│  │  Modele: model.pkl, scaler.pkl                             │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           │ oc / virtctl (CLI)
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│              OPENSHIFT CLUSTER (cluster.ocp.pfe.lan)             │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  master-1    │  │  master-2    │  │  master-3    │          │
│  │  10.9.21.91  │  │  10.9.21.92  │  │  10.9.21.93  │          │
│  │  CP + Worker │  │  CP + Worker │  │  CP + Worker │          │
│  │  RHCOS 4.18  │  │  RHCOS 4.18  │  │  RHCOS 4.18  │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                    │
│         └─────────────────┴─────────────────┘                    │
│                           │                                      │
│              OVN-Kubernetes (SDN)                                │
│                           │                                      │
│         ┌─────────────────┴─────────────────┐                   │
│         ▼                                   ▼                    │
│  ┌─────────────────┐              ┌──────────────────┐          │
│  │ CDI             │              │ KubeVirt         │          │
│  │ (DataImporter)  │              │ (Virtualization) │          │
│  │                 │              │                  │          │
│  │ PVC import      │─────────────►│ VirtualMachine   │          │
│  │ qcow2 upload    │              │ CRD              │          │
│  └─────────────────┘              └──────────────────┘          │
│                                                                  │
│  Namespace: vm-migration                                         │
│  VMs migrees: running + console VNC + monitoring                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. Matrice des communications

| Source | Destination | Protocole | Port | Contenu |
|---|---|---|---|---|
| Browser → Frontend | HTTP | 5173 | React SPA (Vite dev) |
| Frontend → Backend | HTTP/REST + Bearer Token | 8000 | JSON API calls |
| Backend → Hyperviseur | SSH / libvirt XML / .vmx files | — | VM metadata extraction |
| Backend → Module IA | In-process (appel fonction Python) | — | 20 features → prediction |
| Backend → SQLite | SQLAlchemy ORM | — | User auth, session |
| Backend → OpenShift | CLI (`oc`, `virtctl`) | 6443 | Namespace, PVC, VM CRD |
| Bastion → Masters | HAProxy (TCP passthrough) | 6443, 22623, 80, 443 | API, MCS, Ingress |
| Bastion → Masters | nginx (HTTP) | 8080 | Fichiers Ignition |
| Bastion → Masters | DNS (BIND9) | 53 | Resolution noms |
| Bastion → Masters | NTP (Chrony) | 123 (UDP) | Synchronisation temps |
| Developer → Bastion | SSH (VPN) | 22 | Administration + port forwarding |

---

## 6. Couche IA — Detail technique

### Architecture du module IA (interne au backend)

```
┌─────────────────────────────────────────────────────────────────┐
│  src/ml/  (Module IA — Interne au backend)                      │
│                                                                 │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐   │
│  │  features.py  │    │  train.py     │    │ classifier.py │   │
│  │               │    │               │    │               │   │
│  │ • 20 features │    │ • 16 profils  │    │ • Load model  │   │
│  │ • Extraction  │    │   VM realistes│    │ • predict()   │   │
│  │ • Vectoriser  │    │ • 20k samples │    │ • Fallback    │   │
│  │   les donnees │    │ • RF 200      │    │   heuristique │   │
│  └───────┬───────┘    │   arbres      │    │               │   │
│          │            │ • Accuracy    │    └───────┬───────┘   │
│          │            │   99.90%      │            │           │
│          │            └───────────────┘            │           │
│          │                                         │           │
│          │            ┌───────────────┐            │           │
│          │            │  model.pkl    │            │           │
│          │            │  scaler.pkl   │            │           │
│          │            │  (charges au  │            │           │
│          │            │   demarrage)  │            │           │
│          │            └───────────────┘            │           │
│          │                                         │           │
│          └─────────────────────────────────────────┘           │
│                              │                                 │
│                              ▼                                 │
│                    strategy.py (wrapper)                       │
│                    choose_strategy()                           │
│                    → {strategy, confidence,                    │
│                       probabilities, reason}                   │
└─────────────────────────────────────────────────────────────────┘
```

### Justification pour le jury

> **Question possible du jury** : *"Pourquoi l'IA n'est pas un microservice separe ?"*
>
> **Reponse** : *"Dans une architecture de production a grande echelle, on pourrait
> isoler le module IA dans un microservice dedie avec sa propre API et sa propre
> scalabilite. Cependant, pour ce PFE, l'IA est integree directement dans le backend
> car :*
>
> 1. *Les predictions sont instantanees (~1ms) — pas de besoin de scalabilite independante*
> 2. *Le modele est charge en memoire au demarrage — pas de latence reseau*
> 3. *L'IA est appelee uniquement pendant la phase de planification — pas en temps reel*
> 4. *Un seul container suffit pour le prototype — simplifie le deploiement*
>
> *Cette approche est standard pour les applications ML de taille moyenne. Des
> entreprises comme Netflix et Spotify utilisent des modeles in-process dans leurs
> services pour les memes raisons."*

---

*PFE 2024-2025 — Migration Intelligente de VMs vers OpenShift*
*Compact Cluster UPI Bare Metal — cluster.ocp.pfe.lan*
