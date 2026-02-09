# Guide Utilisateur

## Demarrage rapide

1. Installer les dependances

```bash
pip install -r requirements.txt
```

2. Lancer l'API

```bash
python src/main.py api
```

3. Acceder a la documentation interactive

- `http://localhost:8000/docs`

## Exemple de flux

1. Decouvrir les VMs KVM
   - `GET /api/v1/discovery/kvm`
2. Analyser une VM
   - `POST /api/v1/migration/analyze/{vm_name}`
3. Generer un plan
   - `POST /api/v1/migration/plan/{vm_name}`
4. Demarrer une migration (simulee)
   - `POST /api/v1/migration/start/{vm_name}`
5. Suivre le statut
   - `GET /api/v1/migration/status/{job_id}`
6. Generer un rapport
   - `GET /api/v1/migration/report/{job_id}`
