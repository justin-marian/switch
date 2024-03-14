#!/usr/bin/python3

import sys
import struct
import wrapper
import threading
import time

from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name

# Global Variables
CAM_TABLE = {}
PORT_STATE = {}
ROOT_PORT = None
OWN_BRIDGE_ID = None
ROOT_BRIDGE_ID = None
ROOT_PATH_COST = 0
TRUNK_PORTS = []
ACCESS_PORTS = []
INTERFACES = []
SWITCH_ID = None

STP_MULTICAST_MAC = b'\x01\x80\xc2\x00\x00\x00'


def is_unicast(mac):
    return mac[0] & 0x01 == 0


def parse_eth_header(data):
    dest_mac = data[0:6]
    src_mac = data[6:12]
    ether_type = (data[12] << 8) + data[13]

    vlan_id = -1
    # If the frame has a VLAN tag
    if ether_type == 0x8200:
        # Extract the VLAN tag and the new EtherType
        vlan_tci = int.from_bytes(data[14:16], byteorder='big')
        vlan_id = vlan_tci & 0x0FFF
        ether_type = (data[16] << 8) + data[17]

    return dest_mac, src_mac, ether_type, vlan_id


def create_vlan_tag(vlan_id):
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)


def send_bdpu():
    global TRUNK_PORTS, OWN_BRIDGE_ID

    while True:
        for i in TRUNK_PORTS:
            bpdu = struct.pack('!6sqqq', STP_MULTICAST_MAC,
                               OWN_BRIDGE_ID, OWN_BRIDGE_ID, 0)
            # Send the BPDU to the trunk port
            send_to_link(i, bpdu, len(bpdu))
        time.sleep(1)


def handle_stp(interface, data):
    global ROOT_BRIDGE_ID, ROOT_PATH_COST, ROOT_PORT, PORT_STATE, OWN_BRIDGE_ID

    were_root_bridge = OWN_BRIDGE_ID == ROOT_BRIDGE_ID
    # Extract information from the received BPDU
    bpdu_root_bridge_id, bpdu_sender_bridge_id, bpdu_sender_path_cost = [
        int.from_bytes(data[i : i + 8], byteorder='big') for i in range(6, 30, 8)
    ]

    # Update STP parameters based on the received BPDU
    if bpdu_root_bridge_id < ROOT_BRIDGE_ID:
        ROOT_BRIDGE_ID = bpdu_root_bridge_id
        ROOT_PATH_COST = bpdu_sender_path_cost + 10
        ROOT_PORT = interface

        if PORT_STATE[ROOT_PORT] == "blocking":
            PORT_STATE[ROOT_PORT] = "listening"

        if were_root_bridge:
            # If the switch was the root bridge and now it's not, block non-root trunk ports
            for i in TRUNK_PORTS:
                if i != ROOT_PORT:
                    PORT_STATE[i] = "blocking"

        # Construct a new BPDU with updated information and send it to trunk ports
        new_bpdu = struct.pack('!6sqqq', STP_MULTICAST_MAC, 
                               ROOT_BRIDGE_ID, OWN_BRIDGE_ID, ROOT_PATH_COST)

        for i in TRUNK_PORTS:
            if PORT_STATE[i] == "listening":
                send_to_link(i, new_bpdu, len(new_bpdu))

    elif bpdu_root_bridge_id == ROOT_BRIDGE_ID:
        # If the received BPDU has the same root bridge ID as the switch
        if interface == ROOT_PORT and bpdu_sender_path_cost + 10 < ROOT_PATH_COST:
            ROOT_PATH_COST = bpdu_sender_path_cost + 10

    elif bpdu_sender_bridge_id == OWN_BRIDGE_ID:
        # If the received BPDU is from the same bridge as this switch, block the interface
        PORT_STATE[interface] = "blocking"

    # If this switch is the root bridge, set all trunk ports to listening state
    if OWN_BRIDGE_ID == ROOT_BRIDGE_ID:
        for i in TRUNK_PORTS:
            PORT_STATE[i] = "listening"

    return ROOT_BRIDGE_ID, ROOT_PATH_COST, ROOT_PORT, PORT_STATE


def handle_vlan(interface, data, length, dest_mac, src_mac, vlan_id):
    global CAM_TABLE, PORT_STATE

    # Learning MAC src address from comming interface
    if src_mac not in CAM_TABLE or CAM_TABLE[src_mac] != interface:
        CAM_TABLE[src_mac] = interface
        src_mac_str = ':'.join(f'{b:02x}' for b in src_mac)
        print(f"Learned MAC {src_mac_str} on interface {interface}.")

    if PORT_STATE[interface] == "blocking":
        return

    if interface in TRUNK_PORTS:
        handle_from_trunk(interface, data, length, dest_mac, vlan_id)
    else:
        handle_from_access(interface, data, length, dest_mac, vlan_id)


def handle_from_trunk(interface, data, length, dest_mac, vlan_id):
    global CAM_TABLE, PORT_STATE

    if is_unicast(dest_mac):
        # If the destination MAC is in the MAC table
        if dest_mac in CAM_TABLE:
            target_interface = CAM_TABLE[dest_mac]
            # If the target interface is a trunk port, forward the traffic
            if target_interface in TRUNK_PORTS:
                send_to_link(target_interface, data, length)
            # If the target interface is an access port, check VLAN membership and forward accordingly
            else:
                if vlan_id == ACCESS_PORTS[target_interface][1]:
                    data_without_vlan = data[0:12] + data[16:]  # Remove VLAN tag
                    send_to_link(target_interface, data_without_vlan, length - 4)
        # If the destination MAC is not in the MAC table, flood the frame to all trunk ports
        else:
            flood_frame(interface, data, length, vlan_id, is_trunk=True)
    else:
        flood_frame(interface, data, length, vlan_id, is_trunk=True)


def handle_from_access(interface, data, length, dest_mac, _):
    global CAM_TABLE, PORT_STATE

    access_vlan_id = ACCESS_PORTS[interface][1]
    if is_unicast(dest_mac):
        # If the destination MAC is in the MAC table
        if dest_mac in CAM_TABLE:
            target_interface = CAM_TABLE[dest_mac]
            # If the target interface is a trunk port, add VLAN tag and forward the traffic
            if target_interface in TRUNK_PORTS:
                tagged_frame = data[0:12] + create_vlan_tag(access_vlan_id) + data[12:]
                send_to_link(target_interface, tagged_frame, length + 4)
            # If the target interface is an access port, check VLAN membership and forward accordingly
            else:
                if ACCESS_PORTS[target_interface][1] == access_vlan_id:
                    send_to_link(target_interface, data, length)
        # If the destination MAC is not in the MAC table, flood the frame to all access ports in the same VLAN
        else:
            flood_frame(interface, data, length, access_vlan_id, is_trunk=False)
    else:
        flood_frame(interface, data, length, access_vlan_id, is_trunk=False)


def flood_frame(source_interface, data, length, vlan_id, is_trunk):
    global INTERFACES, PORT_STATE, TRUNK_PORTS, ACCESS_PORTS

    for intf in INTERFACES:
        # If the interface is not the source and it's in listening state
        if intf != source_interface and PORT_STATE[intf] == "listening":
            # If the interface is a trunk port, forward the traffic
            if intf in TRUNK_PORTS:
                if is_trunk:
                    send_to_link(intf, data, length)
                else:
                    tagged_frame = data[0:12] + create_vlan_tag(vlan_id) + data[12:]
                    send_to_link(intf, tagged_frame, length + 4)
            # If the interface is an access port, check VLAN membership and forward accordingly
            else:
                if ACCESS_PORTS[intf][1] == vlan_id:
                    if is_trunk:
                        data_without_vlan = data[0:12] + data[16:]
                        send_to_link(intf, data_without_vlan, length - 4)
                    else:
                        send_to_link(intf, data, length)


def switch_config_init():
    global PORT_STATE, TRUNK_PORTS, ACCESS_PORTS, OWN_BRIDGE_ID, ROOT_BRIDGE_ID

    # Extract switch ID from command-line arguments
    SWITCH_ID = sys.argv[1]

    # Initialize switch interfaces
    num_interfaces = wrapper.init(sys.argv[2:])
    INTERFACES = range(num_interfaces)

    print("# Starting switch with id {}".format(SWITCH_ID), flush=True)
    print("[INFO] Switch MAC", ':'.join(f'{b:02x}' for b in get_switch_mac()))

    # Print the name of each interface
    for i in INTERFACES:
        print(get_interface_name(i))
    
    # Read switch configuration file
    path = f"configs/switch{SWITCH_ID}.cfg"
    file = open(path, "r")
    priority = file.readline()

    # Parse each line of the configuration file
    for i in INTERFACES:
        line = file.readline()
        parts = line.split(" ")
        port_index = i

        # Determine if the port is a trunk or access port
        port_type = parts[1].strip()
        if port_type == "T":
            TRUNK_PORTS.append(port_index)
        else:
            vlan_id = int(parts[1].strip())
            ACCESS_PORTS.append((port_index, vlan_id))

    file.close()

    # Set initial port states based on port types
    for i in INTERFACES:
        if i in TRUNK_PORTS:
            PORT_STATE[i] = "blocking"
        else:
            PORT_STATE[i] = "listening"

    OWN_BRIDGE_ID = int(priority)
    ROOT_BRIDGE_ID = OWN_BRIDGE_ID

    # If this switch is the root bridge, set all trunk ports to listening state
    if OWN_BRIDGE_ID == ROOT_BRIDGE_ID:
        for i in TRUNK_PORTS:
            PORT_STATE[i] = "listening"

    # Start a thread to send Bridge Protocol Data Units (BPDUs)
    t = threading.Thread(target=send_bdpu)
    t.start()

    return SWITCH_ID, INTERFACES


def main():
    global SWITCH_ID, CAM_TABLE, INTERFACES, TRUNK_PORTS, ACCESS_PORTS
    global PORT_STATE, ROOT_PORT, ROOT_PATH_COST, ROOT_BRIDGE_ID, OWN_BRIDGE_ID

    SWITCH_ID, INTERFACES = switch_config_init()

    while True:
        interface, data, length = recv_from_any_link()
        dest_mac, src_mac, ethertype, vlan_id = parse_eth_header(data)
        dest_mac_str = ':'.join(f'{b:02x}' for b in dest_mac)
        src_mac_str = ':'.join(f'{b:02x}' for b in src_mac)

        print(f'Destination MAC: {dest_mac_str}')
        print(f'Source MAC: {src_mac_str}')
        print(f'EtherType: {ethertype}')
        print("Received frame of size {} on interface {}".format(length, interface), flush=True)

        if dest_mac == STP_MULTICAST_MAC:
            ROOT_BRIDGE_ID, ROOT_PATH_COST, ROOT_PORT, PORT_STATE = handle_stp(interface, data)
        else:
            handle_vlan(interface, data, length, dest_mac, src_mac, vlan_id)


if __name__ == "__main__":
    main()
