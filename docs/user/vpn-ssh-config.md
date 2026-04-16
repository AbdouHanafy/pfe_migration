# Configuration VPN/SSH — Acces distant au cluster

## Contexte

Tu accedes au cluster via **VPN + SSH** vers le bastion. Le cluster n'est pas encore up.
Voici comment configurer l'acces pour developper et tester depuis ton PC local.

---

## 1. Acces SSH vers le bastion

```
PC Local (ton desktop)
       │
       │ VPN connecte
       ▼
   Bastion (10.9.21.90)
       │
       ├── DNS (BIND9)
       ├── HAProxy (6443, 22623, 80, 443)
       ├── nginx (8080 — fichiers Ignition)
       ├── FastAPI (8000 — backend)
       └── SSH (22)
```

---

## 2. Tunnel SSH — Exposer le backend sur ton PC local

Puisque tu es derriere un VPN, le backend FastAPI (port 8000) sur le bastion
n'est pas accessible directement. Tu dois creer un **tunnel SSH**.

### Sur ton PC Windows :

```powershell
# Tunnel SSH : localhost:8000 → bastion:8000
ssh -L 8000:10.9.21.90:8000 root@<VPN_IP_DU_BASTION>

# Exemple si le bastion est accessible a 10.9.21.90 via VPN :
ssh -L 8000:10.9.21.90:8000 root@10.9.21.90
```

### Si tu es sur le meme reseau VPN (pas besoin de tunnel) :

Si ton PC est sur le **meme reseau VPN** que le bastion (`10.9.21.0/24`),
tu peux acceder directement :

```
Frontend → http://10.9.21.90:8000
```

Dans ce cas, configure le frontend :

```env
# frontend/frontend-app/.env.local
VITE_API_BASE=http://10.9.21.90:8000
```

---

## 3. Lancer le backend sur le bastion

```bash
# SSH vers le bastion
ssh root@<bastion_ip>

# Installer les dependances
cd /root/pfe_migration  # ou ou est le projet
pip install -r requirements.txt

# Lancer l'API (ecoute sur 0.0.0.0)
python src/main.py api
```

> ⚠️ Le backend doit ecouter sur `0.0.0.0:8000`, pas `127.0.0.1`.
> C'est deja le cas dans `config.py` (`API_HOST = "0.0.0.0"`).

---

## 4. Lancer le frontend sur ton PC

```powershell
cd C:\Users\abdou\Desktop\PFE\dev\pfe_migration\frontend\frontend-app

# Si tunnel SSH :
npm run dev
# → Frontend sur http://localhost:5173
# → API via http://localhost:8000 (tunnel)

# Si acces direct VPN :
$env:VITE_API_BASE="http://10.9.21.90:8000"
npm run dev
# → Frontend sur http://localhost:5173
# → API via http://10.9.21.90:8000
```

---

## 5. Firewall du bastion

Verifie que le port 8000 est ouvert sur le bastion :

```bash
# Sur le bastion
firewall-cmd --list-ports | grep 8000

# Si non ouvert :
firewall-cmd --permanent --add-port=8000/tcp
firewall-cmd --reload
```

---

## 6. Resumé des scenarios

| Scenario | Config | URL Frontend | URL Backend |
|---|---|---|---|
| **Tunnel SSH** (recommande) | `ssh -L 8000:10.9.21.90:8000` | `http://localhost:5173` | `http://localhost:8000` |
| **Acces direct VPN** | `.env.local: VITE_API_BASE=http://10.9.21.90:8000` | `http://localhost:5173` | `http://10.9.21.90:8000` |
| **Dev local complet** | Tout sur le bastion | `http://10.9.21.90:5173` | `http://10.9.21.90:8000` |

### Recommandation : **Tunnel SSH**

```powershell
# Terminal 1 — Tunnel SSH
ssh -L 8000:10.9.21.90:8000 root@10.9.21.90

# Terminal 2 — Backend (sur le bastion)
ssh root@10.9.21.90
python /chemin/vers/pfe_migration/src/main.py api

# Terminal 3 — Frontend (sur ton PC)
cd C:\Users\abdou\Desktop\PFE\dev\pfe_migration\frontend\frontend-app
npm run dev
```

---

## 7. Quand le cluster sera up

Une fois le cluster OpenShift actif, tu auras besoin de ces tunnels supplementaires :

```bash
# API Kubernetes (6443)
ssh -L 6443:10.9.21.94:6443 root@10.9.21.90

# Ingress HTTP/HTTPS (80/443)
ssh -L 80:10.9.21.91:80 -L 443:10.9.21.91:443 root@10.9.21.90

# Console web OpenShift
ssh -L 443:console-openshift-console.apps.cluster.ocp.pfe.lan:443 root@10.9.21.90
```

---

## 8. Tester la connectivite

```powershell
# Depuis ton PC, verifier si le bastion est accessible
ping 10.9.21.90

# Verifier si le port 8000 est ouvert
Test-NetConnection -ComputerName 10.9.21.90 -Port 8000

# Verifier le backend
curl http://10.9.21.90:8000/health

# Ou via tunnel
curl http://localhost:8000/health
```

---

*PFE 2024-2025 — Migration Intelligente de VMs vers OpenShift*
