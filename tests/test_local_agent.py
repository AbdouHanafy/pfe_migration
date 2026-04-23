from src.local_agent.hyperv_discoverer import HyperVDiscoverer


def test_hyperv_guess_disk_format():
    discoverer = HyperVDiscoverer()
    assert discoverer._guess_disk_format("C:\\VMs\\disk.vhdx") == "vhdx"
    assert discoverer._guess_disk_format("C:\\VMs\\disk.vhd") == "vhd"
    assert discoverer._guess_disk_format("C:\\VMs\\disk.img") == "raw"


def test_hyperv_ensure_list():
    discoverer = HyperVDiscoverer()
    assert discoverer._ensure_list(None) == []
    assert discoverer._ensure_list({"name": "vm1"}) == [{"name": "vm1"}]
    assert discoverer._ensure_list([{"name": "vm1"}]) == [{"name": "vm1"}]
