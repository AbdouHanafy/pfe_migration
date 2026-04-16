"""
Module d'intelligence artificielle — Classification de strategie de migration.

Utilise scikit-learn pour predire la meilleure strategie de migration
(direct, conversion, alternative) a partir des caracteristiques d'une VM.
"""

from src.ml.classifier import MigrationClassifier
from src.ml.train import train_and_save_model

__all__ = ["MigrationClassifier", "train_and_save_model"]
