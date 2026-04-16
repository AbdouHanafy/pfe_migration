"""
Wrapper de prediction — charge le modele entraine et fournit
une interface simple pour predire la strategie de migration.
"""

import os
from typing import Dict, Tuple
import joblib
import numpy as np

from src.ml.features import extract_features, extract_features_from_analysis_only
from src.config import config

STRATEGY_MAP = {0: "direct", 1: "conversion", 2: "alternative"}

MODEL_DIR = os.path.abspath(os.path.dirname(__file__))
MODEL_PATH = os.path.join(MODEL_DIR, "model.pkl")
SCALER_PATH = os.path.join(MODEL_DIR, "scaler.pkl")


class MigrationClassifier:
    """
    Classeur de strategie de migration base sur un modele scikit-learn.

    Si le modele n'est pas disponible (pas d'entrainement),
    un fallback heuristique est utilise.
    """

    def __init__(self):
        self._model = None
        self._scaler = None
        self._model_available = False
        self._load_model()

    def _load_model(self) -> None:
        """Charge le modele et le scaler depuis les fichiers .pkl."""
        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            try:
                self._model = joblib.load(MODEL_PATH)
                self._scaler = joblib.load(SCALER_PATH)
                self._model_available = True
            except Exception as e:
                config._ml_error = f"Erreur chargement modele: {e}"
                self._model_available = False

    def predict(
        self,
        vm_details: Dict,
        analysis: Dict,
        conversion_plan: Dict
    ) -> Dict:
        """
        Predire la strategie de migration pour une VM.

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
                "confidence": float (0.0-1.0),
                "model_available": bool,
                "method": "ml" | "heuristic",
                "probabilities": {"direct": float, "conversion": float, "alternative": float}
            }
        """
        if self._model_available:
            return self._predict_ml(vm_details, analysis, conversion_plan)
        else:
            return self._predict_heuristic(analysis, conversion_plan)

    def _predict_ml(
        self,
        vm_details: Dict,
        analysis: Dict,
        conversion_plan: Dict
    ) -> Dict:
        """Prediction via le modele ML."""
        features = extract_features(vm_details, analysis, conversion_plan)
        features_scaled = self._scaler.transform(features)

        prediction = self._model.predict(features_scaled)[0]
        probabilities = self._model.predict_proba(features_scaled)[0]

        strategy = STRATEGY_MAP.get(int(prediction), "conversion")
        confidence = float(probabilities.max())

        prob_dict = {}
        for idx, prob in enumerate(probabilities):
            label = STRATEGY_MAP.get(idx, f"unknown_{idx}")
            prob_dict[label] = round(float(prob), 4)

        return {
            "strategy": strategy,
            "confidence": round(confidence, 4),
            "model_available": True,
            "method": "ml",
            "probabilities": prob_dict,
        }

    def _predict_heuristic(self, analysis: Dict, conversion_plan: Dict) -> Dict:
        """
        Fallback heuristique — utilise si le modele ML n'est pas disponible.

        Reproduit la logique des 3 if-statements originale mais avec
        des scores de confiance simules.
        """
        compatibility = analysis.get("compatibility", "non_compatible")
        actions = conversion_plan.get("actions", [])
        score = analysis.get("score", 50)
        issues = analysis.get("issues", [])
        blocker_count = sum(1 for i in issues if i.get("severity") == "blocker")

        if compatibility == "non_compatible" or blocker_count > 0:
            strategy = "alternative"
            confidence = 0.75
        elif len(actions) >= 3:
            strategy = "alternative"
            confidence = 0.60
        elif len(actions) >= 1:
            strategy = "conversion"
            confidence = min(0.9, 0.5 + len(actions) * 0.1)
        elif score >= 80:
            strategy = "direct"
            confidence = min(0.95, score / 100)
        else:
            strategy = "conversion"
            confidence = 0.50

        return {
            "strategy": strategy,
            "confidence": round(confidence, 4),
            "model_available": False,
            "method": "heuristic",
            "probabilities": {
                "direct": round(1 - confidence if strategy != "direct" else confidence, 4),
                "conversion": round(confidence if strategy == "conversion" else 0.2, 4),
                "alternative": round(confidence if strategy == "alternative" else 0.1, 4),
            },
        }

    @property
    def is_available(self) -> bool:
        return self._model_available


# Instance singleton partagee
classifier = MigrationClassifier()
