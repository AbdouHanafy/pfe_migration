# pfe_migration

Plateforme PFE pour l'analyse de compatibilite, la planification et l'orchestration (simulation) de migration de VMs vers OpenShift Virtualization.

## Fonctionnalites

- Decouverte des VMs (KVM/libvirt) et extraction des metadonnees.
- Analyse de compatibilite avec score et recommandations.
- Plan de conversion (formats disque, bus, reseau).
- Selection de strategie de migration (directe, conversion, alternative).
- Orchestration et suivi de jobs (simulation) + reporting via API.
- API REST (FastAPI) + frontend React.

## Architecture technique (resume)

Composants principaux (voir `docs/technical/architecture.md`) :
- `src/discovery` : decouverte des VMs (KVM/libvirt).
- `src/analysis` : regles de compatibilite + scoring.
- `src/conversion` : generation du plan de conversion.
- `src/migration` : selection de strategie + orchestration.
- `src/monitoring` : suivi de jobs et reporting.
- `src/api` : API REST (FastAPI).

Flux de donnees (haut niveau) :
1. Decouverte des VMs.
2. Analyse de compatibilite.
3. Plan de conversion.
4. Choix de strategie.
5. Orchestration et suivi.
6. Rapport final.

## Stack & versions

Backend (Python) :
- Python 3.11 (Dockerfile)
- fastapi 0.104.0, uvicorn 0.24.0, pydantic 2.5.0
- sqlalchemy 2.0.0, alembic 1.12.0, psycopg2-binary 2.9.9
- kubernetes 28.1.0, pyvmomi 8.0.3.0.1

Frontend :
- react ^19.2.0, react-dom ^19.2.0, react-router-dom ^7.13.0
- vite ^7.2.4, eslint ^9.39.1

Infra / deploy :
- Docker (image Python 3.11)
- Manifests OpenShift dans `k8s/openshift/`

## Structure du projet

- `src/` : code backend
- `frontend/frontend-app/` : frontend React
- `docs/` : documentation (architecture, API, usage, avancement)
- `k8s/openshift/` : manifests OpenShift
- `tests/` : tests unitaires / integration

## Demarrage rapide (API)

```bash
pip install -r requirements.txt
python src/main.py api
```

Documentation interactive : `http://localhost:8000/docs`

Voir `docs/user/usage.md` pour un flux complet.

## Frontend

```bash
cd frontend/frontend-app
npm install
npm run dev
```

## API (extrait)

- `GET /health`
- `GET /api/v1/discovery/kvm`
- `POST /api/v1/migration/analyze/{vm_name}`
- `POST /api/v1/migration/plan/{vm_name}`
- `POST /api/v1/migration/start/{vm_name}`
- `GET /api/v1/migration/status/{job_id}`
- `GET /api/v1/migration/report/{job_id}`

Details : `docs/api/README.md`

## Etat du projet (au 2026-02-03)

- Avancement global estime : 65-70% (voir `docs/progress.md`)
- Migration reelle vers OpenShift Virtualization non integree (simulation)
- IA non integree (regles heuristiques uniquement)
