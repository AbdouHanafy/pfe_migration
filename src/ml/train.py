"""
Pipeline d'entrainement du modele de classification.

Genere un dataset synthetique de VMs avec des profils realistes,
entraine un Random Forest Classifier, et sauvegarde le modele.

Usage:
    python -m src.ml.train
    # ou
    python train_model.py
"""

import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
import joblib

from src.ml.features import FEATURE_NAMES

# Labels: 0 = direct, 1 = conversion, 2 = alternative
STRATEGY_LABELS = {0: "direct", 1: "conversion", 2: "alternative"}
RANDOM_STATE = 42
N_SAMPLES = 20000  # Big dataset — 20k VM profiles


def generate_synthetic_dataset(n_samples: int = N_SAMPLES) -> pd.DataFrame:
    """
    Genere un dataset synthetique de VMs avec des labels de strategie.

    Le dataset simule des VMs d'entreprise avec des caracteristiques
    variees et des labels attribues selon des regles metier realistes.

    Returns
    -------
    pandas.DataFrame
        Dataset avec 20 features + 1 label.
    """
    np.random.seed(RANDOM_STATE)

    data = []
    for _ in range(n_samples):
        row = _generate_single_vm_profile()
        data.append(row)

    df = pd.DataFrame(data, columns=FEATURE_NAMES + ["label"])
    return df


def _generate_single_vm_profile() -> list:
    """Genere un profil VM unique avec son label de strategie."""
    # --- Distribution des types de VM (16 types — plus realiste) ---
    vm_type = np.random.choice(
        ["simple_linux", "complex_linux", "windows_server", "legacy_system",
         "high_perf", "multi_disk_db", "old_workstation", "minimal",
         "web_server", "domain_controller", "exchange_server", "sap_erp",
         "kubernetes_node", "ci_cd_runner", "desktop_vdi", "oracle_db"],
        p=[0.10, 0.08, 0.10, 0.06, 0.06, 0.05, 0.06, 0.05,
           0.08, 0.05, 0.04, 0.04, 0.05, 0.04, 0.07, 0.07]
    )

    profile = _VM_PROFILES[vm_type]()
    label = _assign_label(profile)
    return profile + [label]


_VM_PROFILES = {
    "simple_linux": lambda: _profile(
        is_x86_64=1, memory_mb=np.random.uniform(512, 4096),
        cpu_count=np.random.uniform(1, 4), disk_count=1,
        has_raw_disk=0.7, has_qcow2_disk=0.3, needs_disk_conversion=0,
        has_virtio_bus=0.8, needs_bus_change=0, has_virtio_net=0.8,
        needs_net_change=0, compatibility_score=np.random.uniform(80, 100),
        issue_count=np.random.choice([0, 1, 2], p=[0.7, 0.2, 0.1]),
        blocker_count=0, warning_count=np.random.choice([0, 1, 2], p=[0.5, 0.3, 0.2]),
        conversion_action_count=0, has_windows_os=0, has_linux_os=1,
        total_disk_size_gb_est=np.random.uniform(10, 40), is_multi_disk=0
    ),
    "complex_linux": lambda: _profile(
        is_x86_64=1, memory_mb=np.random.uniform(2048, 16384),
        cpu_count=np.random.uniform(2, 8), disk_count=np.random.choice([2, 3, 4]),
        has_raw_disk=0.3, has_qcow2_disk=0.2, needs_disk_conversion=np.random.uniform(0.3, 0.8),
        has_virtio_bus=0.5, needs_bus_change=np.random.uniform(0, 0.5), has_virtio_net=0.4,
        needs_net_change=np.random.uniform(0, 0.4), compatibility_score=np.random.uniform(50, 85),
        issue_count=np.random.choice([1, 2, 3, 4], p=[0.2, 0.3, 0.3, 0.2]),
        blocker_count=0, warning_count=np.random.choice([1, 2, 3, 4]),
        conversion_action_count=np.random.choice([1, 2, 3, 4]), has_windows_os=0, has_linux_os=1,
        total_disk_size_gb_est=np.random.uniform(40, 200), is_multi_disk=1
    ),
    "windows_server": lambda: _profile(
        is_x86_64=1, memory_mb=np.random.uniform(4096, 32768),
        cpu_count=np.random.uniform(2, 16), disk_count=np.random.choice([1, 2, 3]),
        has_raw_disk=0, has_qcow2_disk=0, needs_disk_conversion=np.random.uniform(0.7, 1.0),
        has_virtio_bus=0.2, needs_bus_change=np.random.uniform(0.3, 0.8), has_virtio_net=0.1,
        needs_net_change=np.random.uniform(0.2, 0.6), compatibility_score=np.random.uniform(35, 70),
        issue_count=np.random.choice([2, 3, 4, 5], p=[0.2, 0.3, 0.3, 0.2]),
        blocker_count=0, warning_count=np.random.choice([2, 3, 4, 5]),
        conversion_action_count=np.random.choice([2, 3, 4, 5]), has_windows_os=1, has_linux_os=0,
        total_disk_size_gb_est=np.random.uniform(40, 500), is_multi_disk=np.random.choice([0, 1], p=[0.3, 0.7])
    ),
    "legacy_system": lambda: _profile(
        is_x86_64=np.random.choice([0, 1], p=[0.3, 0.7]), memory_mb=np.random.uniform(128, 1024),
        cpu_count=np.random.uniform(1, 2), disk_count=np.random.choice([1, 2]),
        has_raw_disk=0, has_qcow2_disk=0, needs_disk_conversion=1.0,
        has_virtio_bus=0, needs_bus_change=np.random.uniform(0.5, 1.0), has_virtio_net=0,
        needs_net_change=np.random.uniform(0.5, 1.0), compatibility_score=np.random.uniform(10, 50),
        issue_count=np.random.choice([3, 4, 5, 6], p=[0.2, 0.3, 0.3, 0.2]),
        blocker_count=np.random.choice([0, 1], p=[0.5, 0.5]), warning_count=np.random.choice([2, 3, 4, 5]),
        conversion_action_count=np.random.choice([3, 4, 5, 6]), has_windows_os=np.random.choice([0, 1]), has_linux_os=np.random.choice([0, 1]),
        total_disk_size_gb_est=np.random.uniform(5, 30), is_multi_disk=np.random.choice([0, 1])
    ),
    "high_perf": lambda: _profile(
        is_x86_64=1, memory_mb=np.random.uniform(8192, 65536),
        cpu_count=np.random.uniform(4, 32), disk_count=np.random.choice([3, 4, 5, 6]),
        has_raw_disk=0.3, has_qcow2_disk=0.1, needs_disk_conversion=np.random.uniform(0.5, 1.0),
        has_virtio_bus=0.3, needs_bus_change=np.random.uniform(0.2, 0.7), has_virtio_net=0.2,
        needs_net_change=np.random.uniform(0.1, 0.5), compatibility_score=np.random.uniform(30, 70),
        issue_count=np.random.choice([2, 3, 4, 5]),
        blocker_count=np.random.choice([0, 1], p=[0.6, 0.4]), warning_count=np.random.choice([2, 3, 4]),
        conversion_action_count=np.random.choice([2, 3, 4, 5]), has_windows_os=np.random.choice([0, 1]), has_linux_os=np.random.choice([0, 1]),
        total_disk_size_gb_est=np.random.uniform(200, 2000), is_multi_disk=1
    ),
    "multi_disk_db": lambda: _profile(
        is_x86_64=1, memory_mb=np.random.uniform(8192, 32768),
        cpu_count=np.random.uniform(4, 16), disk_count=np.random.choice([3, 4, 5]),
        has_raw_disk=0.2, has_qcow2_disk=0.2, needs_disk_conversion=np.random.uniform(0.4, 0.8),
        has_virtio_bus=0.4, needs_bus_change=np.random.uniform(0.1, 0.5), has_virtio_net=0.5,
        needs_net_change=np.random.uniform(0, 0.3), compatibility_score=np.random.uniform(50, 80),
        issue_count=np.random.choice([1, 2, 3, 4]),
        blocker_count=0, warning_count=np.random.choice([1, 2, 3, 4]),
        conversion_action_count=np.random.choice([1, 2, 3, 4]), has_windows_os=0, has_linux_os=1,
        total_disk_size_gb_est=np.random.uniform(100, 1000), is_multi_disk=1
    ),
    "old_workstation": lambda: _profile(
        is_x86_64=np.random.choice([0, 1], p=[0.4, 0.6]), memory_mb=np.random.uniform(256, 2048),
        cpu_count=np.random.uniform(1, 4), disk_count=1,
        has_raw_disk=0.3, has_qcow2_disk=0.1, needs_disk_conversion=np.random.uniform(0.5, 1.0),
        has_virtio_bus=0.2, needs_bus_change=np.random.uniform(0.3, 0.7), has_virtio_net=0.1,
        needs_net_change=np.random.uniform(0.3, 0.7), compatibility_score=np.random.uniform(25, 65),
        issue_count=np.random.choice([1, 2, 3, 4]),
        blocker_count=np.random.choice([0, 1], p=[0.7, 0.3]), warning_count=np.random.choice([1, 2, 3]),
        conversion_action_count=np.random.choice([1, 2, 3]), has_windows_os=np.random.choice([0, 1], p=[0.5, 0.5]), has_linux_os=np.random.choice([0, 1], p=[0.5, 0.5]),
        total_disk_size_gb_est=np.random.uniform(10, 60), is_multi_disk=0
    ),
    "minimal": lambda: _profile(
        is_x86_64=1, memory_mb=np.random.uniform(128, 512),
        cpu_count=1, disk_count=1,
        has_raw_disk=0.5, has_qcow2_disk=0.3, needs_disk_conversion=0.0,
        has_virtio_bus=0.9, needs_bus_change=0, has_virtio_net=0.9,
        needs_net_change=0, compatibility_score=np.random.uniform(85, 100),
        issue_count=np.random.choice([0, 1], p=[0.8, 0.2]),
        blocker_count=0, warning_count=np.random.choice([0, 1]),
        conversion_action_count=0, has_windows_os=0, has_linux_os=1,
        total_disk_size_gb_est=np.random.uniform(5, 20), is_multi_disk=0
    ),
    # --- 8 nouveaux profils ---
    "web_server": lambda: _profile(
        is_x86_64=1, memory_mb=np.random.uniform(2048, 8192),
        cpu_count=np.random.uniform(2, 8), disk_count=np.random.choice([1, 2]),
        has_raw_disk=0.6, has_qcow2_disk=0.2, needs_disk_conversion=0,
        has_virtio_bus=0.9, needs_bus_change=0, has_virtio_net=0.9,
        needs_net_change=0, compatibility_score=np.random.uniform(75, 95),
        issue_count=np.random.choice([0, 1, 2], p=[0.6, 0.3, 0.1]),
        blocker_count=0, warning_count=np.random.choice([0, 1, 2], p=[0.5, 0.3, 0.2]),
        conversion_action_count=0, has_windows_os=0, has_linux_os=1,
        total_disk_size_gb_est=np.random.uniform(20, 60), is_multi_disk=np.random.choice([0, 1], p=[0.5, 0.5])
    ),
    "domain_controller": lambda: _profile(
        is_x86_64=1, memory_mb=np.random.uniform(2048, 4096),
        cpu_count=np.random.uniform(2, 4), disk_count=1,
        has_raw_disk=0, has_qcow2_disk=0, needs_disk_conversion=np.random.uniform(0.8, 1.0),
        has_virtio_bus=0.1, needs_bus_change=np.random.uniform(0.5, 0.9), has_virtio_net=0.1,
        needs_net_change=np.random.uniform(0.3, 0.7), compatibility_score=np.random.uniform(30, 55),
        issue_count=np.random.choice([2, 3, 4], p=[0.3, 0.4, 0.3]),
        blocker_count=0, warning_count=np.random.choice([2, 3, 4]),
        conversion_action_count=np.random.choice([2, 3, 4]), has_windows_os=1, has_linux_os=0,
        total_disk_size_gb_est=np.random.uniform(30, 60), is_multi_disk=0
    ),
    "exchange_server": lambda: _profile(
        is_x86_64=1, memory_mb=np.random.uniform(16384, 65536),
        cpu_count=np.random.uniform(4, 16), disk_count=np.random.choice([4, 5, 6]),
        has_raw_disk=0, has_qcow2_disk=0, needs_disk_conversion=1.0,
        has_virtio_bus=0, needs_bus_change=np.random.uniform(0.6, 1.0), has_virtio_net=0,
        needs_net_change=np.random.uniform(0.4, 0.8), compatibility_score=np.random.uniform(20, 45),
        issue_count=np.random.choice([3, 4, 5, 6]),
        blocker_count=np.random.choice([0, 1], p=[0.4, 0.6]), warning_count=np.random.choice([3, 4, 5]),
        conversion_action_count=np.random.choice([4, 5, 6]), has_windows_os=1, has_linux_os=0,
        total_disk_size_gb_est=np.random.uniform(500, 5000), is_multi_disk=1
    ),
    "sap_erp": lambda: _profile(
        is_x86_64=1, memory_mb=np.random.uniform(32768, 131072),
        cpu_count=np.random.uniform(8, 64), disk_count=np.random.choice([4, 5, 6, 8]),
        has_raw_disk=0.3, has_qcow2_disk=0, needs_disk_conversion=np.random.uniform(0.6, 1.0),
        has_virtio_bus=0.2, needs_bus_change=np.random.uniform(0.3, 0.7), has_virtio_net=0.3,
        needs_net_change=np.random.uniform(0.1, 0.5), compatibility_score=np.random.uniform(15, 40),
        issue_count=np.random.choice([3, 4, 5, 6]),
        blocker_count=np.random.choice([0, 1], p=[0.3, 0.7]), warning_count=np.random.choice([3, 4, 5]),
        conversion_action_count=np.random.choice([3, 4, 5, 6]), has_windows_os=np.random.choice([0, 1], p=[0.3, 0.7]), has_linux_os=np.random.choice([0, 1], p=[0.7, 0.3]),
        total_disk_size_gb_est=np.random.uniform(500, 10000), is_multi_disk=1
    ),
    "kubernetes_node": lambda: _profile(
        is_x86_64=1, memory_mb=np.random.uniform(4096, 32768),
        cpu_count=np.random.uniform(4, 16), disk_count=np.random.choice([1, 2, 3]),
        has_raw_disk=0.8, has_qcow2_disk=0.1, needs_disk_conversion=0,
        has_virtio_bus=0.95, needs_bus_change=0, has_virtio_net=0.95,
        needs_net_change=0, compatibility_score=np.random.uniform(85, 100),
        issue_count=np.random.choice([0, 1], p=[0.9, 0.1]),
        blocker_count=0, warning_count=np.random.choice([0, 1]),
        conversion_action_count=0, has_windows_os=0, has_linux_os=1,
        total_disk_size_gb_est=np.random.uniform(30, 100), is_multi_disk=np.random.choice([0, 1], p=[0.3, 0.7])
    ),
    "ci_cd_runner": lambda: _profile(
        is_x86_64=1, memory_mb=np.random.uniform(4096, 16384),
        cpu_count=np.random.uniform(4, 16), disk_count=np.random.choice([1, 2]),
        has_raw_disk=0.7, has_qcow2_disk=0.2, needs_disk_conversion=0,
        has_virtio_bus=0.9, needs_bus_change=0, has_virtio_net=0.9,
        needs_net_change=0, compatibility_score=np.random.uniform(80, 98),
        issue_count=np.random.choice([0, 1], p=[0.8, 0.2]),
        blocker_count=0, warning_count=np.random.choice([0, 1]),
        conversion_action_count=0, has_windows_os=0, has_linux_os=1,
        total_disk_size_gb_est=np.random.uniform(30, 80), is_multi_disk=np.random.choice([0, 1], p=[0.5, 0.5])
    ),
    "desktop_vdi": lambda: _profile(
        is_x86_64=1, memory_mb=np.random.uniform(2048, 8192),
        cpu_count=np.random.uniform(1, 4), disk_count=1,
        has_raw_disk=0, has_qcow2_disk=0, needs_disk_conversion=np.random.uniform(0.7, 1.0),
        has_virtio_bus=0.1, needs_bus_change=np.random.uniform(0.4, 0.8), has_virtio_net=0.2,
        needs_net_change=np.random.uniform(0.2, 0.5), compatibility_score=np.random.uniform(40, 70),
        issue_count=np.random.choice([1, 2, 3], p=[0.3, 0.4, 0.3]),
        blocker_count=0, warning_count=np.random.choice([1, 2, 3]),
        conversion_action_count=np.random.choice([1, 2, 3]), has_windows_os=np.random.choice([0, 1], p=[0.7, 0.3]), has_linux_os=np.random.choice([0, 1], p=[0.3, 0.7]),
        total_disk_size_gb_est=np.random.uniform(20, 60), is_multi_disk=0
    ),
    "oracle_db": lambda: _profile(
        is_x86_64=1, memory_mb=np.random.uniform(16384, 131072),
        cpu_count=np.random.uniform(4, 32), disk_count=np.random.choice([3, 4, 5, 6]),
        has_raw_disk=0.4, has_qcow2_disk=0.1, needs_disk_conversion=np.random.uniform(0.5, 0.9),
        has_virtio_bus=0.3, needs_bus_change=np.random.uniform(0.2, 0.6), has_virtio_net=0.4,
        needs_net_change=np.random.uniform(0.1, 0.4), compatibility_score=np.random.uniform(30, 65),
        issue_count=np.random.choice([2, 3, 4, 5]),
        blocker_count=np.random.choice([0, 1], p=[0.5, 0.5]), warning_count=np.random.choice([2, 3, 4]),
        conversion_action_count=np.random.choice([2, 3, 4, 5]), has_windows_os=np.random.choice([0, 1], p=[0.3, 0.7]), has_linux_os=np.random.choice([0, 1], p=[0.7, 0.3]),
        total_disk_size_gb_est=np.random.uniform(200, 5000), is_multi_disk=1
    ),
}


def _profile(**kwargs) -> list:
    """Helper pour convertir des kwargs en liste ordonnee."""
    keys = [
        "is_x86_64", "memory_mb", "cpu_count", "disk_count",
        "has_raw_disk", "has_qcow2_disk", "needs_disk_conversion",
        "has_virtio_bus", "needs_bus_change", "has_virtio_net",
        "needs_net_change", "compatibility_score", "issue_count",
        "blocker_count", "warning_count", "conversion_action_count",
        "has_windows_os", "has_linux_os", "total_disk_size_gb_est",
        "is_multi_disk"
    ]
    return [kwargs[k] for k in keys]


def _assign_label(features: list) -> int:
    """
    Attribue un label de strategie selon des regles metier.

    0 = direct (lift-and-shift)       : VM compatible, peu/no actions
    1 = conversion (re-platforming)   : VM necessite conversion/drivers
    2 = alternative (refactor)        : VM non-compatible ou trop complexe
    """
    (is_x86_64, memory_mb, cpu_count, disk_count,
     has_raw, has_qcow2, needs_disk_conv,
     has_virtio_bus, needs_bus_change, has_virtio_net,
     needs_net_change, score, issue_count,
     blocker_count, warning_count, conversion_actions,
     has_windows, has_linux, disk_gb, is_multi) = features

    # Regles de labelisation (pour generer le dataset d'entrainement)
    if blocker_count > 0 or score < 30:
        return 2  # alternative

    if needs_disk_conv > 0.5 or (has_windows and needs_disk_conv > 0.3):
        return 1  # conversion

    if conversion_actions >= 3 or (disk_gb > 500 and needs_disk_conv > 0.3):
        return 2  # alternative — trop complexe

    if conversion_actions >= 1 or needs_bus_change > 0.3 or needs_net_change > 0.3:
        return 1  # conversion

    if score >= 80 and conversion_actions == 0:
        return 0  # direct

    if score >= 60 and needs_disk_conv < 0.5:
        return 0  # direct

    # Cas intermediaire
    if score < 60 and conversion_actions >= 2:
        return 1  # conversion

    if is_x86_64 == 0:
        return 2  # alternative

    return 1  # conversion par defaut


def train_and_save_model(
    output_dir: str = "src/ml",
    n_samples: int = N_SAMPLES,
    random_state: int = RANDOM_STATE
) -> tuple:
    """
    Genere le dataset, entraine le modele, et sauvegarde.

    Parameters
    ----------
    output_dir : str
        Dossier ou sauvegarder le modele et le dataset.
    n_samples : int
        Nombre d'echantillons a generer.
    random_state : int
        Seed pour la reproductibilite.

    Returns
    -------
    tuple
        (classifier, scaler, X_train, X_test, y_train, y_test)
    """
    print("=" * 60)
    print("  ENTRAINEMENT DU MODELE DE CLASSIFICATION")
    print("=" * 60)

    # 1. Generer le dataset
    print(f"\n[1/5] Generation de {n_samples} VMs synthetiques...")
    df = generate_synthetic_dataset(n_samples)

    # Sauvegarder le dataset
    dataset_path = os.path.join(output_dir, "training_data.csv")
    df.to_csv(dataset_path, index=False)
    print(f"  Dataset sauvegarde: {dataset_path}")
    print(f"  Distribution des labels:")
    for label, name in STRATEGY_LABELS.items():
        count = (df["label"] == label).sum()
        pct = count / len(df) * 100
        print(f"    {name:12s}: {count:5d} ({pct:5.1f}%)")

    # 2. Preparer les donnees
    print("\n[2/5] Preparation des donnees...")
    X = df[FEATURE_NAMES].values
    y = df["label"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=random_state, stratify=y
    )
    print(f"  Train: {len(X_train)} echantillons")
    print(f"  Test:  {len(X_test)} echantillons")

    # 3. Scaler
    print("\n[3/5] Standardisation des features...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # 4. Entrainement
    print("\n[4/5] Entrainement du Random Forest...")
    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=random_state,
        n_jobs=-1
    )
    clf.fit(X_train_scaled, y_train)

    # Validation croisee
    cv_scores = cross_val_score(clf, X_train_scaled, y_train, cv=5, scoring="accuracy")
    print(f"  Cross-validation (5 folds): {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")

    # 5. Evaluation
    print("\n[5/5] Evaluation sur le test set...")
    train_acc = clf.score(X_train_scaled, y_train)
    test_acc = clf.score(X_test_scaled, y_test)
    print(f"  Train accuracy: {train_acc:.4f}")
    print(f"  Test  accuracy: {test_acc:.4f}")

    y_pred = clf.predict(X_test_scaled)
    print("\n  Classification Report:")
    print(classification_report(y_test, y_pred, target_names=list(STRATEGY_LABELS.values())))

    print("\n  Confusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(cm)

    # Feature importance
    print("\n  Feature Importance:")
    importances = clf.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    for idx in sorted_idx:
        print(f"    {FEATURE_NAMES[idx]:30s}: {importances[idx]:.4f}")

    # 6. Sauvegarde
    model_path = os.path.join(output_dir, "model.pkl")
    scaler_path = os.path.join(output_dir, "scaler.pkl")
    joblib.dump(clf, model_path)
    joblib.dump(scaler, scaler_path)
    print(f"\n  Modele sauvegarde: {model_path}")
    print(f"  Scaler sauvegarde: {scaler_path}")

    print("\n" + "=" * 60)
    print("  ENTRAINEMENT TERMINE")
    print("=" * 60)

    return clf, scaler, X_train, X_test, y_train, y_test


if __name__ == "__main__":
    train_and_save_model()
