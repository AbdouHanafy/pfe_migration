#!/usr/bin/env python3
"""
Script d'entrainement du modele IA de classification de strategie.

Usage:
    python train_model.py
    python train_model.py --samples 10000
    python train_model.py --output models/
"""

import sys
import os
import argparse

# Ajouter le repertoire parent au path pour les imports
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ml.train import train_and_save_model


def main():
    parser = argparse.ArgumentParser(
        description="Entrainement du modele de classification de strategie de migration"
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=5000,
        help="Nombre d'echantillons a generer (defaut: 5000)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="src/ml",
        help="Dossier de sortie pour le modele (defaut: src/ml)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed aleatoire pour reproductibilite (defaut: 42)"
    )

    args = parser.parse_args()

    # Creer le dossier de sortie si necessaire
    os.makedirs(args.output, exist_ok=True)

    clf, scaler, X_train, X_test, y_train, y_test = train_and_save_model(
        output_dir=args.output,
        n_samples=args.samples,
        random_state=args.seed
    )

    print(f"\n🎯 Modele entraine et sauvegarde dans: {args.output}/model.pkl")
    print(f"📊 Precision test set: {clf.score(scaler.transform(X_test), y_test):.2%}")
    print(f"🔧 Features: 20")
    print(f"📁 Dataset: {args.output}/training_data.csv")


if __name__ == "__main__":
    main()
