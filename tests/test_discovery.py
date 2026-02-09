"""
Tests pour le module de découverte
"""

import pytest
from unittest.mock import Mock, patch
from src.discovery.kvm_discoverer import KVMDiscoverer

def test_kvm_discoverer_initialization():
    """Test l'initialisation du découvreur KVM"""
    discoverer = KVMDiscoverer()
    assert discoverer.connection_uri == 'qemu:///system'
    assert discoverer.conn is None

@patch('libvirt.open')
def test_connect_success(mock_libvirt_open):
    """Test une connexion réussie"""
    mock_conn = Mock()
    mock_libvirt_open.return_value = mock_conn
    
    discoverer = KVMDiscoverer()
    result = discoverer.connect()
    
    assert result is True
    assert discoverer.conn == mock_conn

@patch('libvirt.open')
def test_connect_failure(mock_libvirt_open):
    """Test un échec de connexion"""
    mock_libvirt_open.return_value = None
    
    discoverer = KVMDiscoverer()
    result = discoverer.connect()
    
    assert result is False
    assert discoverer.conn is None

def test_disconnect():
    """Test la déconnexion"""
    discoverer = KVMDiscoverer()
    discoverer.conn = Mock()
    discoverer.disconnect()
    
    assert discoverer.conn is None

@patch('libvirt.open')
def test_list_vms_empty(mock_libvirt_open):
    """Test la liste des VMs quand il n'y en a pas"""
    mock_conn = Mock()
    mock_conn.listAllDomains.return_value = []
    mock_libvirt_open.return_value = mock_conn
    
    discoverer = KVMDiscoverer()
    discoverer.connect()
    vms = discoverer.list_vms()
    
    assert len(vms) == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
