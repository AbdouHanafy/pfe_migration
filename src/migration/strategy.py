"""
Selection de strategie de migration

Utilise un modele de classification scikit-learn (Random Forest) entraine
sur des profils de VMs synthetiques pour predire la meilleure strategie.

Fallback heuristique si le modele ML n'est pas disponible.
"""

from typing import Dict

from src.ml.classifier import classifier as ml_classifier


def choose_strategy(vm_details: Dict, analysis: Dict, conversion_plan: Dict) -> Dict:
    """
    Choisit la strategie de migration via le modele ML.

    Parameters
    ----------
    vm_details : dict
        Details bruts de la VM (disks, network, specs).
    analysis : dict
        Resultat de l'analyse de compatibilite.
    conversion_plan : dict
        Plan de conversion avec actions.

    Returns
    -------
    dict
        {
            "strategy": "direct" | "conversion" | "alternative",
            "confidence": float,
            "model_available": bool,
            "method": "ml" | "heuristic",
            "probabilities": dict,
            "reason": str
        }
    """
    prediction = ml_classifier.predict(vm_details, analysis, conversion_plan)

    # Construire la raison explicative
    strategy = prediction["strategy"]
    reasons = _build_reason(strategy, analysis, conversion_plan)

    return {
        "strategy": strategy,
        "confidence": prediction["confidence"],
        "model_available": prediction["model_available"],
        "method": prediction["method"],
        "probabilities": prediction["probabilities"],
        "reason": reasons
    }


def _build_reason(strategy: str, analysis: Dict, conversion_plan: Dict) -> str:
    """Construit une explication textuelle de la strategie choisie."""
    compatibility = analysis.get("compatibility", "unknown")
    score = analysis.get("score", 0)
    issues = analysis.get("issues", [])
    actions = conversion_plan.get("actions", [])
    blocker_count = sum(1 for i in issues if i.get("severity") == "blocker")

    if strategy == "direct":
        return (
            f"VM {compatibility} (score: {score}/100). "
            f"Aucune conversion majeure requise. "
            f"Migration lift-and-shift possible."
        )
    elif strategy == "conversion":
        action_types = [a.get("type", "unknown") for a in actions]
        return (
            f"VM {compatibility} (score: {score}/100). "
            f"{len(actions)} action(s) de conversion requises: "
            f"{', '.join(set(action_types))}. "
            f"Re-platforming recommande."
        )
    else:  # alternative
        if blocker_count > 0:
            blockers = [i.get("message", "blocker inconnu") for i in issues if i.get("severity") == "blocker"]
            return (
                f"VM non compatible. {blocker_count} blocker(s): "
                f"{'; '.join(blockers)}. "
                f"Migration alternative ou refactoring requis."
            )
        return (
            f"VM {compatibility} (score: {score}/100). "
            f"Complexite trop elevee ({len(actions)} actions). "
            f"Migration alternative recommandee."
        )
