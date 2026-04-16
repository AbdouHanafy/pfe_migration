"""
Tests pour le module IA — features, entrainement et prediction.
"""

import os
import numpy as np
import pytest

from src.ml.features import (
    extract_features,
    extract_features_from_analysis_only,
    FEATURE_NAMES,
)
from src.ml.train import generate_synthetic_dataset, _assign_label
from src.ml.classifier import MigrationClassifier, STRATEGY_MAP
from src.analysis.compatibility import analyze_vm
from src.conversion.converter import build_conversion_plan


# ============================================================
# FEATURES
# ============================================================

def test_feature_names_count():
    """Verifie qu'il y a exactement 20 features."""
    assert len(FEATURE_NAMES) == 20


def test_extract_features_shape():
    """Verifie que le vecteur de features a la bonne forme."""
    vm_details = {
        "specs": {"os_arch": "x86_64", "memory_mb": 2048, "cpus": 2, "os_type": "linux"},
        "disks": [
            {"format": "raw", "bus": "virtio", "path": "/tmp/disk.raw"},
            {"format": "vmdk", "bus": "ide", "path": "/tmp/disk2.vmdk"},
        ],
        "network": [{"model": "virtio"}],
    }
    analysis = {
        "compatibility": "partiellement_compatible",
        "score": 70,
        "issues": [
            {"severity": "warning", "message": "Format disque non optimal"},
        ],
    }
    conversion_plan = {
        "can_convert": True,
        "actions": [
            {"type": "disk_format_conversion", "from": "vmdk", "to": "raw"},
            {"type": "disk_bus_change", "from": "ide", "to": "virtio"},
        ],
    }

    features = extract_features(vm_details, analysis, conversion_plan)
    assert features.shape == (1, 20)


def test_extract_features_x86_64():
    """Verifie que l'architecture x86_64 est bien detectee."""
    vm_details = {
        "specs": {"os_arch": "x86_64", "memory_mb": 1024, "cpus": 1},
        "disks": [{"format": "raw", "bus": "virtio", "path": "/tmp/disk.raw"}],
        "network": [{"model": "virtio"}],
    }
    analysis = {"score": 100, "issues": [], "compatibility": "compatible"}
    conversion_plan = {"actions": []}

    features = extract_features(vm_details, analysis, conversion_plan)
    assert features[0, 0] == 1.0  # is_x86_64


def test_extract_features_non_x86_64():
    """Verifie que l'architecture non supportee est detectee."""
    vm_details = {
        "specs": {"os_arch": "arm64", "memory_mb": 1024, "cpus": 1},
        "disks": [{"format": "raw", "bus": "virtio", "path": "/tmp/disk.raw"}],
        "network": [{"model": "virtio"}],
    }
    analysis = {"score": 60, "issues": [], "compatibility": "partiellement_compatible"}
    conversion_plan = {"actions": []}

    features = extract_features(vm_details, analysis, conversion_plan)
    assert features[0, 0] == 0.0  # is_x86_64


def test_extract_features_vmdk_conversion_needed():
    """Verifie que les disques VMDK sont marques pour conversion."""
    vm_details = {
        "specs": {"os_arch": "x86_64", "memory_mb": 2048, "cpus": 2},
        "disks": [{"format": "vmdk", "bus": "virtio", "path": "/tmp/disk.vmdk"}],
        "network": [{"model": "virtio"}],
    }
    analysis = {"score": 80, "issues": [], "compatibility": "compatible"}
    conversion_plan = {"actions": [{"type": "disk_format_conversion"}]}

    features = extract_features(vm_details, analysis, conversion_plan)
    assert features[0, 6] > 0  # needs_disk_conversion > 0


def test_extract_features_from_analysis_only():
    """Verifie la version simplifiee."""
    analysis = {
        "compatibility": "compatible",
        "score": 85,
        "issues": [{"severity": "warning", "message": "test"}],
        "detected": {"memory_mb": 2048, "cpu_count": 2, "disks_count": 1},
    }
    conversion_plan = {"actions": [{"type": "disk_format_conversion"}]}

    features = extract_features_from_analysis_only(analysis, conversion_plan)
    assert features.shape == (1, 20)
    assert features[0, 11] == 85.0  # compatibility_score


# ============================================================
# TRAINING DATA
# ============================================================

def test_generate_dataset():
    """Verifie que le dataset synthetique est genere correctement."""
    df = generate_synthetic_dataset(n_samples=100)
    assert len(df) == 100
    assert set(FEATURE_NAMES).issubset(set(df.columns))
    assert "label" in df.columns
    assert set(df["label"].unique()).issubset({0, 1, 2})


def test_dataset_has_all_labels():
    """Verifie que le dataset contient les 3 classes."""
    df = generate_synthetic_dataset(n_samples=500)
    labels = set(df["label"].unique())
    assert 0 in labels, "Missing 'direct' class"
    assert 1 in labels, "Missing 'conversion' class"
    assert 2 in labels, "Missing 'alternative' class"


def test_blocker_implies_alternative():
    """Verifie qu'un VM avec un blocker est labelise 'alternative' (2)."""
    features = [1, 1024, 2, 1, 1, 0, 0, 1, 0, 1, 0, 50, 3, 1, 2, 0, 0, 1, 20, 0]
    label = _assign_label(features)
    assert label == 2  # alternative


def test_no_actions_implies_direct():
    """Verifie qu'une VM sans action est labelisee 'direct' (0)."""
    features = [1, 2048, 2, 1, 1, 0, 0, 1, 0, 1, 0, 90, 0, 0, 0, 0, 0, 1, 20, 0]
    label = _assign_label(features)
    assert label == 0  # direct


# ============================================================
# CLASSIFIER
# ============================================================

def test_classifier_instantiation():
    """Verifie que le classeur s'instancie sans erreur."""
    clf = MigrationClassifier()
    assert clf is not None


def test_predict_returns_required_keys():
    """Verifie que predict retourne toutes les cles attendues."""
    clf = MigrationClassifier()
    analysis = {
        "compatibility": "partiellement_compatible",
        "score": 70,
        "issues": [{"severity": "warning", "message": "test"}],
        "detected": {"memory_mb": 2048, "cpu_count": 2, "disks_count": 1},
    }
    conversion_plan = {
        "can_convert": True,
        "actions": [{"type": "disk_format_conversion", "from": "vmdk", "to": "raw"}],
    }
    vm_details = {
        "specs": {"os_arch": "x86_64", "memory_mb": 2048, "cpus": 2},
        "disks": [{"format": "vmdk", "bus": "virtio", "path": "/tmp/disk.vmdk"}],
        "network": [{"model": "virtio"}],
    }

    result = clf.predict(vm_details, analysis, conversion_plan)

    assert "strategy" in result
    assert "confidence" in result
    assert "model_available" in result
    assert "method" in result
    assert "probabilities" in result


def test_strategy_wrapper_returns_reason():
    """Verifie que choose_strategy (strategy.py) retourne 'reason'."""
    from src.migration.strategy import choose_strategy

    vm_details = {
        "specs": {"os_arch": "x86_64", "memory_mb": 2048, "cpus": 2},
        "disks": [{"format": "raw", "bus": "virtio", "path": "/tmp/disk.raw"}],
        "network": [{"model": "virtio"}],
    }
    analysis = analyze_vm(vm_details)
    conversion_plan = build_conversion_plan(vm_details, analysis)
    result = choose_strategy(vm_details, analysis, conversion_plan)

    assert "reason" in result
    assert "strategy" in result
    assert "confidence" in result
    assert "probabilities" in result


def test_strategy_is_valid_string():
    """Verifie que la strategie retournee est une valeur valide."""
    clf = MigrationClassifier()
    analysis = {
        "compatibility": "compatible",
        "score": 90,
        "issues": [],
        "detected": {"memory_mb": 4096, "cpu_count": 4, "disks_count": 1},
    }
    conversion_plan = {"can_convert": True, "actions": []}
    vm_details = {
        "specs": {"os_arch": "x86_64", "memory_mb": 4096, "cpus": 4},
        "disks": [{"format": "raw", "bus": "virtio", "path": "/tmp/disk.raw"}],
        "network": [{"model": "virtio"}],
    }

    result = clf.predict(vm_details, analysis, conversion_plan)
    assert result["strategy"] in ("direct", "conversion", "alternative")


def test_non_compatible_vm_is_alternative():
    """Verifie qu'une VM non compatible obtient 'alternative' via heuristique."""
    clf = MigrationClassifier()
    analysis = {
        "compatibility": "non_compatible",
        "score": 20,
        "issues": [
            {"severity": "blocker", "message": "Architecture non supportee: arm64"},
            {"severity": "blocker", "message": "Aucun disque detecte"},
        ],
        "detected": {"memory_mb": 1024, "cpu_count": 2, "disks_count": 0},
    }
    conversion_plan = {"can_convert": False, "actions": []}
    vm_details = {
        "specs": {"os_arch": "arm64", "memory_mb": 1024, "cpus": 2},
        "disks": [],
        "network": [],
    }

    result = clf.predict(vm_details, analysis, conversion_plan)

    # Model ou heuristique — alternative doit etre la strategie dominante
    # ou avoir la plus haute probabilite
    if clf.is_available:
        # Verifier que la probabilite d'alternative est significative
        alt_prob = result["probabilities"].get("alternative", 0)
        assert alt_prob > 0.3, f"Alternative prob too low: {alt_prob}"
    else:
        assert result["strategy"] == "alternative"


def test_confidence_is_between_0_and_1():
    """Verifie que la confiance est dans [0, 1]."""
    clf = MigrationClassifier()
    analysis = {
        "compatibility": "partiellement_compatible",
        "score": 60,
        "issues": [{"severity": "warning", "message": "test"}],
        "detected": {"memory_mb": 2048, "cpu_count": 2, "disks_count": 1},
    }
    conversion_plan = {"can_convert": True, "actions": [{"type": "disk_format_conversion"}]}
    vm_details = {
        "specs": {"os_arch": "x86_64", "memory_mb": 2048, "cpus": 2},
        "disks": [{"format": "vmdk", "bus": "virtio", "path": "/tmp/disk.vmdk"}],
        "network": [{"model": "virtio"}],
    }

    result = clf.predict(vm_details, analysis, conversion_plan)
    assert 0.0 <= result["confidence"] <= 1.0
