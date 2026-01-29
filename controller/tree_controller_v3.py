from os_ken.base.app_manager import OSKenApp
from os_ken.controller import ofp_event
from os_ken.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3

from os_ken.lib.packet import ether_types
from os_ken.lib.packet.packet import Packet
from os_ken.lib.packet.ethernet import ethernet
from os_ken.topology.switches import LLDPPacket

from kgevents import KGEventHandler as kg_events

import resource
from enum import Enum
from typing import cast
from dataclasses import dataclass, field


soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
print(f"Resource Limits for open files(soft, hard): {resource.getrlimit(resource.RLIMIT_NOFILE)}")


class PeerType(Enum):
    HOST = 0
    SWITCH = 1


@dataclass
class SwitchPort:
    mac: str
    number: int
    datapath_id: int
    peer_type: PeerType = field(default=PeerType.HOST)
    flow_count: int = 0 

    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, SwitchPort):
            return False

        port = cast(SwitchPort, value)
        if port.mac != self.mac:
            return False 
        return True


class TreeControllerV3(OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]


    def __init__(self, *args, **kwargs):
        super(TreeControllerV3, self).__init__(*args, **kwargs)
        self.branch_factor = 10

        # Format
        # [<dpid>] : {
        #       [<dst_addr>]: [
        #           [<port_num>], 
        #           [<port_num>], 
        #       ],
        #} 
        self.dpid_mac_dst_ports: dict[int, dict[str, list[SwitchPort]]]= dict()

        # Format
        # [<dpid>] : {
        #       [<port_number>]: OutputPort,
        #       [<port_number>]: OutputPort,
        #} 
        self.port_num_to_obj_map: dict[int, dict[int, SwitchPort]]= dict()

        # Format
        # dpid : {"eth_src:eth_dst": "output_port",  ...  "eth_src:eth_dst": "output_port"} 
        self.dpid_flows: dict[int, dict[str, SwitchPort]] = dict()

        # All mac address of hosts
        self.host_mac_set: set[str] = set()

        # Set of all dpid that are initialized
        self.dpid_initialized: set[int] = set()


    def __add_flow(self, datapath, priority, match, actions) -> bool:
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
            flags=ofproto_v1_3.OFPFF_SEND_FLOW_REM,
        )

        # os_ken.controller.controller.Datapath.send_msg(msg)
        # Returns true if the message was added to the send queue, else it returns false
        message_queued = datapath.send_msg(mod)

        # Send flow add only if the message was queued
        if message_queued:
            formatted_match = dict()
            for _, match_headers in mod.match.stringify_attrs():
                formatted_match.update(match_headers)

            formatted_inst = list()
            for instruction in mod.instructions:
                formatted_inst.append(instruction.to_jsondict())
            body = {
                    "dpid": datapath.id,
                    "table_id": mod.table_id,
                    "request_body": {
                        "priority": mod.priority,
                        "oxm_fields": formatted_match,
                        "instructions": formatted_inst,
                    }
                }
            kg_events.send_flow_add_event(**body)

        return message_queued 


    def __init_default_flow_rules(self, datapath, ofp, ofp_parser):
        match = ofp_parser.OFPMatch()
        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_CONTROLLER)]
        self.__add_flow(datapath, 0, match, actions)

        match = ofp_parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IPV6)
        self.__add_flow(datapath, 65535, match, [])

        match = ofp_parser.OFPMatch(eth_type=ether_types.ETH_TYPE_LLDP)
        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self.__add_flow(datapath, 65535, match, actions)


    def __init_flood_flow_rules(self, datapath, ofp, ofp_parser):
        is_core_switch = datapath.id <= (self.branch_factor // 2)**2
        min_port = self.branch_factor // 2 + 1
        if is_core_switch:
            min_port = 1 
        # Packets in in_port [(K//2) + 1, K] are from lower layers, flood these packets
        action = [ofp_parser.OFPActionOutput(ofp.OFPP_FLOOD), ofp_parser.OFPActionOutput(ofp.OFPP_CONTROLLER)]
        for in_port in range(min_port, self.branch_factor + 1):
            match=ofp_parser.OFPMatch(in_port=in_port, eth_dst="FF:FF:FF:FF:FF:FF")
            self.__add_flow(datapath, 1000, match, action)

        if not is_core_switch:
            # Packets received through first K ports are from uppler layer, send it only downwards
            partial_flood_actions = [ofp_parser.OFPActionOutput(port) 
                                     for port in range(self.branch_factor // 2 + 1, self.branch_factor + 1)]
            partial_flood_actions.append(ofp_parser.OFPActionOutput(ofp.OFPP_CONTROLLER))
            for in_port in range(1, (self.branch_factor // 2) + 1):
                match=ofp_parser.OFPMatch(in_port=in_port, eth_dst="FF:FF:FF:FF:FF:FF")
                self.__add_flow(datapath, 1000, match, partial_flood_actions)


    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features_handler(self, ev):
        datapath = ev.msg.datapath
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        # Add only if the datapath is not already present i.e. case where the switch reconnects.
        # From what I've observed, the mininet switches do not discard the flow rules
        # even if the controller goes offline. All the initialization steps need not be repeated
        # TODO: Check if datapath disconnects when a flow rule is added
        # TODO: Add event handler for error messages from the switch
        if datapath.id in self.dpid_initialized:
            return

        self.dpid_mac_dst_ports[datapath.id] = dict()
        self.port_num_to_obj_map[datapath.id] = dict()
        self.dpid_flows[datapath.id] = dict()

        body = {"dpid": datapath.id}
        kg_events.send_switch_enter_event(**body)

        self.__init_default_flow_rules(datapath, ofp, ofp_parser)
        self.__init_flood_flow_rules(datapath, ofp, ofp_parser)


    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, CONFIG_DISPATCHER)
    def store_port_desc_stats(self, ev):
        datapath = ev.msg.datapath
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        # The ofp_handler.py sends a port description request when switch connects,
        # If the switch is already initialized, do not send LLDP 
        # packets through them
        if datapath.id in self.dpid_initialized:
            return

        # Send an LLDP packet on each port of the switch
        for port in ev.msg.body:
            # Skip the controller port
            if port.port_no == (ofp.OFPP_CONTROLLER + 1) or port.port_no == ofp.OFPP_CONTROLLER:
                continue

            self.port_num_to_obj_map[datapath.id][port.port_no] = SwitchPort(port.hw_addr, port.port_no, datapath.id)

            lldp_packet = LLDPPacket.lldp_packet(datapath.id, port.port_no, port.hw_addr, 0)
            actions = [ofp_parser.OFPActionOutput(port.port_no)]
            out = ofp_parser.OFPPacketOut(
                datapath=datapath, in_port=ofp.OFPP_CONTROLLER,
                buffer_id=ofp.OFP_NO_BUFFER, actions=actions,
                data=lldp_packet)
            datapath.send_msg(out)

        self.dpid_initialized.add(datapath.id)


    @set_ev_cls(ofp_event.EventOFPFlowRemoved, MAIN_DISPATCHER)
    def flow_removed_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath

        formatted_match = dict()
        for _, match_headers in msg.match.stringify_attrs():
            formatted_match.update(match_headers)

        body ={
                "dpid": datapath.id,
                "table_id": msg.table_id,
                "request_body": {
                    "priority": msg.priority,
                    "oxm_fields": formatted_match,
                },
            }
        kg_events.send_flow_remove_event(**body)


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        switch_in_port = self.port_num_to_obj_map[datapath.id][msg.match["in_port"]]
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
            data = msg.data

        eth_headers = Packet(msg.data).get_protocol(ethernet)
        if eth_headers.ethertype == ether_types.ETH_TYPE_LLDP:
            src_dpid, src_port = LLDPPacket.lldp_parse(msg.data)
            self._link_add_handler(src_dpid, src_port, datapath.id, switch_in_port.number)
            switch_in_port.peer_type = PeerType.SWITCH
            return

        eth_src = eth_headers.src
        eth_dst = eth_headers.dst

        forward_table = self.dpid_mac_dst_ports.get(datapath.id)
        if forward_table is None:
            self.logger.warning("WARN: switch datastructures not initialized")
            return
        if eth_src not in forward_table:
            forward_table[eth_src] = list()
        if switch_in_port not in forward_table[eth_src]:
            forward_table[eth_src].append(switch_in_port)
            self.logger.debug(f"{eth_src} reachable through switch {datapath.id} port {switch_in_port}")

        if switch_in_port.peer_type == PeerType.HOST and eth_src not in self.host_mac_set:
            self.host_mac_set.add(eth_src)
            self._host_add_handler(eth_src, datapath.id, switch_in_port.number)

        # No action is performed for broadcast packets. 
        # Flow rules for broadcast packets are already installed
        # These packets are used to only learn the port of src_ip
        if eth_dst == "ff:ff:ff:ff:ff:ff":
            return

        if eth_dst not in forward_table or len(forward_table[eth_dst]) == 0:
            self.logger.warning(f"WARN: {eth_dst} not reachable through switch {datapath.id}")
            return


        flow = f"{eth_src}:{eth_dst}"
        if flow not in self.dpid_flows[datapath.id]:
            # Select port (Using data structures like priority queue does not 
            # work because updating the key of an object inside the priority 
            # queue does not reorder the queue)
            output_port = forward_table[eth_dst][0]
            for port in forward_table[eth_dst]:
                if port.flow_count < output_port.flow_count:
                    output_port = port

            actions = [ofp_parser.OFPActionOutput(output_port.number)]
            match = ofp_parser.OFPMatch(eth_src=eth_src,eth_dst=eth_dst)

            # Increment the counters and store flow in controller 
            # only if we successfully add the flow mod to the queue
            # TODO: Even if the message was added to the queue, a error can occur 
            # during socket.send(). In this case, all the messages in the queue are discarded. 
            # There are no events or exceptions raised when this happens. Figure out how to handle this 
            # Refer os_ken.controller.controller.Datapath._send_loop()
            if self.__add_flow(datapath, 5000, match, actions):
                # Store flow 
                self.dpid_flows[datapath.id][flow] = output_port

                # Increment number flows for in_port and out_port
                switch_in_port.flow_count += 1
                output_port.flow_count = output_port.flow_count + 1

        else: 
            output_port = self.dpid_flows[datapath.id][flow]

        actions = [ofp_parser.OFPActionOutput(output_port.number)]

        # Need to send the data packet back to switch
        # Switch does not buffer the data packets
        out = ofp_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=switch_in_port.number,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)


    def _link_add_handler(self, src_dpid, src_port, dst_dpid, dst_port):
        body = {
                    "request_body": {
                        "src": {"dpid": src_dpid, "port_no": src_port},
                        "dst": {"dpid": dst_dpid, "port_no": dst_port},
                    }
                }
        kg_events.send_link_add_event(**body)


    def _host_add_handler(self, host_mac, datapath_id, datapath_port):
        body = {
                    "request_body": {
                        "mac": host_mac,
                        "port": {"dpid": datapath_id, "port_no": datapath_port},
                    }
                }
        kg_events.send_host_add_event(**body)
