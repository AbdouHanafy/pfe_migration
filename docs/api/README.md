# API Reference

## Endpoints

- `GET /health`
- `GET /api/v1/discovery/kvm`
- `GET /api/v1/discovery/kvm/{vm_name}`
- `POST /api/v1/migration/analyze/{vm_name}`
- `POST /api/v1/migration/plan/{vm_name}`
- `POST /api/v1/migration/start/{vm_name}`
- `GET /api/v1/migration/status/{job_id}`
- `GET /api/v1/migration/jobs`
- `GET /api/v1/migration/report/{job_id}`

## Exemple de reponse: analyse

```json
{
  "vm_name": "ubuntu-vm",
  "analysis": {
    "compatibility": "partiellement_compatible",
    "score": 85,
    "issues": [
      {
        "code": "disk_format",
        "severity": "warning",
        "message": "Format disque non optimal: vmdk"
      }
    ],
    "recommendations": [
      "Convertir le disque en format raw (actuel: vmdk)."
    ],
    "detected": {
      "os_arch": "x86_64",
      "memory_mb": 1024,
      "cpu_count": 2,
      "disks_count": 1,
      "network_count": 1
    }
  }
}
```
