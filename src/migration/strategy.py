"""
Selection de strategie de migration
"""

from typing import Dict

def choose_strategy(analysis: Dict, conversion_plan: Dict) -> Dict:
    """Choisit la strategie de migration."""
    compatibility = analysis.get("compatibility", "non_compatible")
    actions = conversion_plan.get("actions", [])

    if compatibility == "non_compatible":
        return {
            "strategy": "alternative",
            "reason": "VM non compatible. Migration alternative requise."
        }
    if actions:
        return {
            "strategy": "conversion",
            "reason": "Conversion requise avant migration."
        }
    return {
        "strategy": "direct",
        "reason": "VM compatible. Migration directe possible."
    }
