# PFE Migration Intelligente de VMs vers OpenShift

Projet de fin d'études visant à automatiser la migration de machines virtuelles depuis des environnements VMware Workstation et KVM/libvirt vers **OpenShift Virtualization** (KubeVirt + CDI).

## Objectif

Fournir une plateforme complète pour :
- découvrir et analyser des VMs existantes
- évaluer la compatibilité avec OpenShift
- générer un plan de conversion technique
- proposer une stratégie de migration avec un moteur IA
- orchestrer une migration simulée et préparer le déploiement réel sur OpenShift

## Structure du projet

- `src/` : backend Python
  - `src/api/` : API FastAPI
  - `src/discovery/` : découverte de VMs KVM et VMware Workstation
  - `src/analysis/` : règles de compatibilité et scoring OpenShift
  - `src/conversion/` : génération de plan de conversion de disques et bus
  - `src/ml/` : génération de dataset, entraînement et classification IA
  - `src/migration/` : choix de stratégie et orchestration de jobs
  - `src/monitoring/` : stockage et suivi des jobs
  - `src/openshift/` : intégration basique avec OpenShift via CLI
  - `src/database/` : modèles SQLAlchemy et sessions
  - `src/config.py` : configuration globale
  - `src/main.py` : point d'entrée CLI
- `frontend/frontend-app/` : application React + Vite
- `k8s/openshift/` : manifests OpenShift (namespace, PVC, deployment, service, route)
- `docs/` : documentation, architecture et configuration VPN/SSH
- `tests/` : tests unitaires et d'intégration
- `train_model.py` : script d'entraînement IA
- `test_real_vm.py` : script de test sur VM réelle
- `Dockerfile` : image backend Python
- `requirements.txt` : dépendances Python

## Fonctionnalités principales

- Découverte de VMs KVM et VMware Workstation
- Analyse de compatibilité OpenShift avec scoring et règles métier
- Plan de conversion de disques et bus réseau
- Moteur IA local (Random Forest) pour recommander la stratégie de migration
- Orchestration de jobs de migration simulée
- API REST avec authenticaton et documentation Swagger
- Frontend React pour interface utilisateur
- Manifests OpenShift prêts à déployer

## Installation backend

1. Créer un environnement virtuel Python 3.11+ :
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Installer les dépendances :
   ```powershell
   pip install -r requirements.txt
   ```

## Lancer le backend

```powershell
python src/main.py api
```

API disponible sur `http://localhost:8000`
Docs Swagger : `http://localhost:8000/docs`

## Lancer le frontend

```powershell
cd frontend/frontend-app
npm install
npm run dev
```

Interface frontend : `http://localhost:5173`

## Utilisation rapide

- `python src/main.py discovery` : tester la découverte KVM
- `python src/main.py tests` : exécuter les tests Python
- `python train_model.py` : entraîner le modèle IA
- `python test_real_vm.py` : tester le workflow avec une VM réelle

## API disponibles

- `GET /` : informations de service
- `GET /health` : état de santé
- `POST /api/v1/auth/register` : créer un compte
- `POST /api/v1/auth/login` : authentifier un utilisateur
- `GET /api/v1/discovery/kvm` : lister les VMs KVM
- `GET /api/v1/discovery/kvm/{vm}` : détail VM KVM
- `GET /api/v1/discovery/vmware-workstation` : lister les VMs VMware Workstation
- `GET /api/v1/discovery/vmware-workstation/{vm}` : détail VM VMware
- `POST /api/v1/migration/analyze/{vm}` : analyser une VM
- `POST /api/v1/migration/plan/{vm}` : générer le plan de migration
- `POST /api/v1/migration/start/{vm}` : démarrer une migration simulée
- `GET /api/v1/migration/status/{job}` : statut d'un job
- `GET /api/v1/migration/jobs` : liste des jobs
- `GET /api/v1/migration/report/{job}` : rapport d'un job
- `POST /api/v1/migration/openshift/{vm}` : lancer la migration OpenShift

## IA et machine learning

- Dataset synthétique de 20 000 profils de VMs
- 20 features extraites pour chaque VM
- Random Forest Classifier entraîné
- Stratégies produites : `direct`, `conversion`, `alternative`
- Modèle intégré directement dans le backend (pas de service séparé)

## Déploiement OpenShift

1. Appliquer les manifests :
   ```powershell
   oc apply -f k8s/openshift/namespace.yaml
   oc apply -f k8s/openshift/configmap.yaml
   oc apply -f k8s/openshift/pvc.yaml
   oc apply -f k8s/openshift/deployment.yaml
   oc apply -f k8s/openshift/service.yaml
   oc apply -f k8s/openshift/route.yaml
   ```
2. Vérifier les ressources :
   ```powershell
   oc get pods -n migration-pfe
   oc get routes -n migration-pfe
   ```

## Dépendances principales

- `fastapi`, `uvicorn`, `pydantic`
- `scikit-learn`, `pandas`, `numpy`, `joblib`
- `sqlalchemy`, `PyJWT`, `passlib`
- `react`, `react-router-dom`, `vite`

## Tests

```powershell
python -m pytest tests/ -v
```

## Notes

- L'API supporte plusieurs modes d'authentification via `src/config.py`
- Le module OpenShift utilise les commandes CLI `oc` et `virtctl`
- Le frontend est dans `frontend/frontend-app`
- La documentation utilisateur et technique est disponible dans `docs/`

## Prochaines étapes

- Compléter l'intégration `virt-v2v` pour les conversions réelles
- Ajouter une orchestration asynchrone et WebSocket
- Migrer la persistance vers PostgreSQL
- Finaliser le frontend avec dashboards et rapports
- Renforcer le support VMware/vCenter
