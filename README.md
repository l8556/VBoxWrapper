# VBoxWrapper

[![Python Version](https://img.shields.io/badge/python-3.7%20%7C%203.8%20%7C%203.9%20%7C%203.10%20%7C%203.11-blue)](https://www.python.org/)

VBoxWrapper is a Python library that provides a high-level,
object-oriented interface for managing Oracle VirtualBox virtual machines.
It simplifies common VM management tasks such as starting, stopping,
snapshot management,
and network configuration through an intuitive Python API.

## Features

- **VM Management**: Start, stop, pause, and resume virtual machines
- **Snapshot Management**: Create, restore, and manage VM snapshots
- **Network Configuration**: Configure VM network settings programmatically
- **Group Operations**: Manage VMs in groups for batch operations


## Installation

VBoxWrapper requires Python 3.7 or higher and VirtualBox to be installed on your system.

### Using pip

```bash
pip install git+https://github.com/l8556/VBoxWrapper.git
```

### From source

```bash
git clone https://github.com/l8556/VBoxWrapper.git
cd VBoxWrapper
pip install .
```

## Quick Start

```python
from vboxwrapper import VirtualMachine, Vbox

# Create a Vbox instance
vbox = Vbox()

# List all VMs
vms = vbox.vm_list()
print("Available VMs:", vms)

# Get a VM instance
vm = VirtualMachine("your-vm-name")

# Start the VM
vm.start()

# Take a snapshot
vm.snapshot.create("before-update")
# ... perform some operations ...

# Revert to snapshot
vm.snapshot.restore("before-update")


# Configure network
vm.network.set_nat_network(1, "NatNetwork")
# Shutdown the VM
vm.shutdown()
```

## Documentation

### Vbox Class

The `Vbox` class provides methods to interact with the VirtualBox environment:

- `vm_list(group_name=None)`: List all VMs, optionally filtered by group
- `check_vm_names(vm_names)`: Verify if VMs exist
- `get_vm_names(group_name=None)`: Get names of all VMs
- `get_vm_uuids(group_name=None)`: Get UUIDs of all VMs

### VirtualMachine Class

The `VirtualMachine` class represents a single VM and provides methods to control it:

#### Basic Operations
- `start()`: Start the VM
- `shutdown()`: Send ACPI power button event to shutdown the VM
- `power_off()`: Force power off the VM
- `pause()`: Pause the VM
- `resume()`: Resume a paused VM
- `reset()`: Reset the VM

#### Snapshot Management
- `snapshot.create(name, description="")`: Create a new snapshot
- `snapshot.restore(name)`: Restore to a specific snapshot
- `snapshot.delete(name)`: Delete a snapshot
- `snapshot.list()`: List all snapshots

#### Network Configuration
- `network.set_nat_network(adapter, network_name)`: Configure NAT network
- `network.set_bridged_adapter(adapter, interface=None)`: Configure bridged networking
- `network.set_host_only_adapter(adapter, interface)`: Configure host-only networking
- `network.get_mac_address(adapter)`: Get MAC address of a network adapter

## Examples

### List all VMs in a specific group

```python
from vboxwrapper import Vbox

vbox = Vbox()
group_vms = vbox.vm_list("development")
print(f"Development VMs: {group_vms}")
```

### Take and manage snapshots

```python
from vboxwrapper import VirtualMachine

vm = VirtualMachine("my-vm")

# Take a snapshot
vm.snapshot.take("Fresh OS installation")

# List snapshots
snapshots = vm.snapshot.list()
print(f"Available snapshots: {snapshots}")

# Restore snapshot
vm.snapshot.restore("clean-install")
```

### Configure network settings

```python
from vboxwrapper import VirtualMachine

vm = VirtualMachine("my-vm")

# Configure NAT network
vm.network.set_adapter(
    turn=True,
    adapter_number=1,
    connect_type='bridged',
    adapter_name="MyNetwork"
)

```
