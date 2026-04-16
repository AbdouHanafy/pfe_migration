#!/usr/bin/env python3
"""
Test du pipeline complet sur la VM reelle: devops (VMware Workstation)
"""

import sys
import os
import json

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.discovery.vmware_workstation_discoverer import VMwareWorkstationDiscoverer
from src.analysis.compatibility import analyze_vm
from src.conversion.converter import build_conversion_plan
from src.migration.strategy import choose_strategy

# Chemin vers le dossier de la VM
VM_PATH = r"C:\Users\abdou\Documents\Virtual Machines\devops"

print("=" * 70)
print("  TEST PFE MIGRATION — VM REELLE: devops")
print("=" * 70)

# ============================================================
# 1. DISCOVERY
# ============================================================
print("\n[1/4] DISCOVERY — VMware Workstation")
print("-" * 50)

discoverer = VMwareWorkstationDiscoverer(search_paths=[VM_PATH])

vms = discoverer.list_vms()
print(f"  VMs trouvees: {len(vms)}")

if not vms:
    print("  ❌ Aucune VM trouvee. Verifier le chemin:")
    print(f"     {VM_PATH}")
    sys.exit(1)

for vm in vms:
    print(f"  📦 {vm['name']} (hypervisor: {vm['hypervisor']})")

# Get details for "devops"
vm_name = "devops"
details = discoverer.get_vm_details(vm_name)

if details is None:
    print(f"\n  ❌ Impossible d'obtenir les details de '{vm_name}'")
    sys.exit(1)

print(f"\n  Details de '{vm_name}':")
print(f"    Hypervisor : {details.get('hypervisor')}")
print(f"    VMX Path   : {details.get('vmx_path')}")
print(f"    UUID       : {details.get('uuid')}")
print(f"    State      : {details.get('state')}")

specs = details.get("specs", {})
print(f"\n  Specs:")
print(f"    OS         : {specs.get('os_type', 'unknown')}")
print(f"    Arch       : {specs.get('os_arch', 'unknown')}")
print(f"    RAM        : {specs.get('memory_mb', 0)} MB")
print(f"    CPUs       : {specs.get('cpus', 0)}")

disks = details.get("disks", [])
print(f"\n  Disks ({len(disks)}):")
for d in disks:
    print(f"    • {d.get('path', '?')}  format={d.get('format')}  bus={d.get('bus')}")

networks = details.get("network", [])
print(f"\n  Network ({len(networks)}):")
for n in networks:
    print(f"    • model={n.get('model')}  network={n.get('network')}  mac={n.get('mac_address')}")

# ============================================================
# 2. ANALYSIS
# ============================================================
print("\n[2/4] ANALYSIS — Compatibilite OpenShift")
print("-" * 50)

analysis = analyze_vm(details)
print(f"  Compatibilite    : {analysis['compatibility']}")
print(f"  Score            : {analysis['score']}/100")
print(f"  Issues ({len(analysis['issues'])}):")
for issue in analysis['issues']:
    sev = issue['severity']
    icon = "❌" if sev == "blocker" else "⚠️"
    print(f"    {icon} [{sev}] {issue['message']}")

print(f"  Recommendations ({len(analysis['recommendations'])}):")
for rec in analysis['recommendations']:
    print(f"    → {rec}")

# ============================================================
# 3. CONVERSION PLAN
# ============================================================
print("\n[3/4] CONVERSION PLAN")
print("-" * 50)

conversion_plan = build_conversion_plan(details, analysis)
print(f"  Convertible      : {conversion_plan['can_convert']}")
print(f"  Actions ({len(conversion_plan['actions'])}):")
for action in conversion_plan['actions']:
    print(f"    • {action['type']}: {action.get('from', '?')} → {action.get('to', '?')}")

print(f"  Warnings:")
for w in conversion_plan['warnings']:
    print(f"    ⚠️  {w}")

# ============================================================
# 4. STRATEGY (IA)
# ============================================================
print("\n[4/4] STRATEGY — IA Prediction")
print("-" * 50)

strategy = choose_strategy(details, analysis, conversion_plan)
print(f"  Strategie        : {strategy['strategy']}")
print(f"  Confiance        : {strategy['confidence']:.1%}")
print(f"  Methode          : {strategy['method']}")
print(f"  Model disponible : {strategy['model_available']}")
print(f"  Raison           : {strategy['reason']}")

print(f"\n  Probabilites:")
for strat, prob in strategy['probabilities'].items():
    bar = "█" * int(prob * 30)
    print(f"    {strat:15s}: {prob:5.1%} {bar}")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 70)
print("  RESUME")
print("=" * 70)
print(f"  VM           : {vm_name}")
print(f"  OS           : {specs.get('os_type', 'unknown')}")
print(f"  RAM/CPU      : {specs.get('memory_mb', 0)} MB / {specs.get('cpus', 0)} vCPU")
print(f"  Disks        : {len(disks)}x ({', '.join(set(d.get('format', '?') for d in disks))})")
print(f"  Network      : {', '.join(n.get('model', '?') for n in networks)}")
print(f"  Compatibilite: {analysis['compatibility']} ({analysis['score']}/100)")
print(f"  Strategie IA : {strategy['strategy']} ({strategy['confidence']:.1%})")
print("=" * 70)
