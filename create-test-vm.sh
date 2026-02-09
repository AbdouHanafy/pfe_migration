#!/bin/bash
echo "Création d'une VM de test pour le PFE..."

# Créer l'image de disque
sudo qemu-img create -f qcow2 /var/lib/libvirt/images/pfe-test-vm.qcow2 3G

# Créer la VM
sudo virt-install \
  --name pfe-test-vm \
  --ram 1024 \
  --disk path=/var/lib/libvirt/images/pfe-test-vm.qcow2,format=qcow2 \
  --vcpus 2 \
  --os-type linux \
  --os-variant ubuntu20.04 \
  --network network=default \
  --graphics none \
  --console pty,target_type=serial \
  --import \
  --noautoconsole

echo "VM créée : pfe-test-vm"
echo "Pour la démarrer : sudo virsh start pfe-test-vm"
