#!/usr/bin/env python3
"""
Point d'entrée principal du projet PFE Migration
"""

import sys
import os
import argparse

# Permet d'executer `python src/main.py` sans erreur d'import
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config import config

def run_discovery():
    """Exécute le module de découverte"""
    from src.discovery.kvm_discoverer import KVMDiscoverer
    
    print("🔍 Module de découverte KVM")
    print("=" * 40)
    
    discoverer = KVMDiscoverer()
    
    if discoverer.connect():
        vms = discoverer.list_vms()
        print(f"📊 {len(vms)} VM(s) trouvée(s):")
        
        for vm in vms:
            print(f"  • {vm['name']:20} [{vm['state']:10}]")
        
        if vms:
            print(f"\n💡 Pour les détails: python src/discovery/kvm_discoverer.py")
        
        discoverer.disconnect()
    else:
        print("❌ Impossible de se connecter à KVM")

def run_api():
    """Démarre l'API REST"""
    import uvicorn
    
    print("🚀 Démarrage de l'API Migration...")
    print(f"📡 http://{config.API_HOST}:{config.API_PORT}")
    print(f"📚 Documentation: http://{config.API_HOST}:{config.API_PORT}/docs")
    
    uvicorn.run(
        "src.api.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.API_DEBUG
    )

def run_tests():
    """Exécute les tests"""
    import pytest
    
    print("🧪 Exécution des tests...")
    result = pytest.main(["-v", "tests/"])
    
    if result == 0:
        print("✅ Tous les tests passent !")
    else:
        print("⚠️  Certains tests ont échoué")

def show_config():
    """Affiche la configuration"""
    config.display()

def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(
        description=config.APP_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  %(prog)s api          # Démarre l'API REST
  %(prog)s discovery    # Teste la découverte des VMs
  %(prog)s tests        # Exécute les tests
  %(prog)s config       # Affiche la configuration
        """
    )
    
    parser.add_argument(
        "command",
        choices=["api", "discovery", "tests", "config", "all"],
        help="Commande à exécuter"
    )
    
    args = parser.parse_args()
    
    print(f"🎓 {config.APP_NAME} v{config.APP_VERSION}")
    print()
    
    if args.command == "api":
        run_api()
    elif args.command == "discovery":
        run_discovery()
    elif args.command == "tests":
        run_tests()
    elif args.command == "config":
        show_config()
    elif args.command == "all":
        print("=== DÉMARRAGE COMPLET ===")
        run_tests()
        print()
        run_discovery()
        print()
        run_api()

if __name__ == "__main__":
    main()
