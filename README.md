# Switch

Ethernet `Switch` that uses **VLAN segmentation** for network efficiency, **Spanning Tree Protocol (STP)** for loop prevention, and **MAC address** learning for fast frame forwarding. By  managing **VLAN membership**, **preventing loops**, and **learning MAC addresses**, the implementation ensures reliable communication and facilitates network segmentation for enhanced performance.

<p align="center">
    <img src="./images/topo.png" alt="TOPO" width="65%">
</p>

## Frame Forwarding Process

- **Frame Arrival:** An Ethernet frame arrives at a switch through one of its ports.
- **Destination MAC Address:** The switch examines the destination MAC address (dst) in the header frame.
- **MAC Address Table Lookup:** The switch checks its MAC address table to find the port associated with the destination MAC address. If found, the frame is forwarded out of the corresponding port.
- **Unknown Destination MAC Address:** If the MAC address is unknown, the switch floods the frame to all ports except the incoming one to ensure connectivity.
- **Broadcast and Multicast:**
  - `Broadcast` frames are forwarded to **all** ports except the receiving one, all devices receive the broadcast.
  - `Multicast` frames are forwarded **only** to ports interested in the multicast group.

## VLAN

`VLANs` (`Virtual Local Area Networks`) segment a single physical LAN into multiple broadcast domains. The VLANs introduce the concept of `VLAN tagging` and forwards frames based on VLAN membership, facilitating efficient network segmentation and traffic management.

<p align="center">
    <img src="./images/ethernet_802.png" alt="ETHERNET_802" width="75%">
</p>

### VLAN Forwarding Process

- **Frame Reception:** When a switch receives a frame with an *unknown destination or broadcast*, it forwards it to all ports within the same VLAN, including trunks.
- **IEEE 802.1Q VLAN Tagging:** VLAN tagging is introduced using `IEEE 802.1Q`, adding **4** bytes to the frame. The `VID field` (**12 bits**) represents the **VLAN identifier**.

**Switch Behavior:**

- If on an **access port**:
  - Forwards **with** `802.1Q` header on trunk interfaces.
  - Forwards **without** header if VLAN ID matches that of the incoming interface.
- If on a **trunk port**:
  - Removes **VLAN tag** and forwards:
    - **With** `802.1Q header` (including tag) on trunk interfaces.
    - **Without** header if VLAN ID matches that of the received frame on access interfaces.

1. **Linux VLAN Filtering:** `TPID` value of `0x8200` is used instead of `0x8100`. `PCP` and `DEI` are set to `0`.
2. **Trunk Links:** Links between switches operate in **trunk mode**, allowing passage of all VLANs.
3. **Configuration:** VLANs and trunk configurations are set via a `configuration file` specified in the API section.

<p align="center">
    <img src="./images/tag_format.png" alt="TAG" width="50%">
</p>

## STP (Spanning Tree Protocol)

`STP` (`Spanning Tree Protocol`) is a protocol used to prevent loops in network topologies by creating a loop-free logical topology. This implementation provides a simplified version of STP to avoid LAN loops.

- Each switch initially considers itself as the `root bridge` and starts with all ports in the `Listening state`.
- `BPDUs` are exchanged between switches to elect the `root bridge` and determine the `designated ports`.
- `Trunk` ports are crucial for loop prevention, and `STP` operates **only on these ports** *to avoid potential loops*.

### Structure of BPDU Frames

`BPDU frames` utilize encapsulation with the `802.2 Logical Link Control (LLC) header`. The following article briefly outlines their structure:
The `Bridge Protocol Data Units (BPDUs)` utilize the encapsulation of the 802.2 Logical Link Control (LLC) header. The structure of a BPDU is as follows:

-------------------------------------------------

1. **Destination MAC** (`DST_MAC`): `6` bytes
2. **Source MAC** (`SRC_MAC`): `6` bytes
3. **LLC Length** (`LLC_LENGTH`): `2` bytes, indicating the total size of the frame including the BPDU.
4. **LLC Header** (`LLC_HEADER`): `3` bytes, comprising the **DSAP** (*Destination Service Access Point*), **SSAP** (*Source Service Access Point*), and **Control** fields.
   - `DSAP`: `1` byte, typically set to `0x42` to identify the STP protocol.
   - `SSAP`: `1` byte, also set to `0x42` to identify the STP protocol.
   - `Control`: `1` byte, often set to `0x03` for control purposes.
5. **BPDU Header** (`BPDU_HEADER`): `4` bytes, containing control information specific to STP.
6. **BPDU Configuration** (`BPDU_CONFIG`): `31` bytes, encompassing various parameters such as **flags**, **root bridge ID**, **root path cost**, **sender bridge ID**, **port ID**, **message age**, **max age**, **hello time**, and **forward delay**.

-------------------------------------------------

### STP Forwarding Process

- **Initialization:** `Trunk ports` start in the `Blocking state` to prevent loops. Switches consider themselves as `root bridges`, with all ports in the `Listening state`. If a switch it's the `root bridge`, it sets all ports to the `Designated state`.
- **BPDU Exchange:** Switches exchange `BPDUs` to elect the `root bridge` and determine designated ports. `BPDUs` contain **root bridge ID**, **sender bridge ID**, and **root path cost**, sent regularly on **trunk ports**.
- **Root Bridge Election:** Upon receiving a `BPDU`, switches compare `root bridge IDs`. If received **ID is lower**, the switch **updates** its information and **forwards** the BPDU.
  - Switches **continuously update root bridge** information.
- **Port States:** Ports can be `Blocking`, `Listening`, `Learning`, or `Forwarding`.
  - `Blocking` prevents loops,
  - `Listening` prepares for Learning state,
  - `Learning populates` MAC address tables, and
  - `Forwarding` fully operates.
- **Loop Prevention:** STP operates on trunk ports to prevent loops. `BPDUs` determine best paths to **root bridge and block redundant links**.
- **Frame Forwarding:** Forward frames based on established spanning tree topology, ensuring a loop-free network.

## Usage

To simulate a virtual network use `Mininet`. Mininet is a network simulator that utilizes real kernel, switch, and application code implementations. Mininet can be used on both Linux and WSL2.

```bash
sudo apt update
sudo apt install mininet openvswitch-testcontroller tshark python3-click python3-scapy xterm python3-pip
sudo pip3 install mininet
```

After installing Mininet use the following command to increase the font size in the terminals we open.

```bash
echo "xterm*font: *-fixed-*-*-*-18-*" >> ~/.Xresources
xrdb -merge ~/.Xresources
```

When running the simulation, you may encounter the following error: `Exception: Please shut down the controller which is running on port 6653:`. To resolve the issue, you will need to run `pkill ovs-test`.
