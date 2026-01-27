from collections import deque
from os_ken.base.app_manager import OSKenApp
from os_ken.controller import ofp_event
from os_ken.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3, ofproto_v1_3_parser
from os_ken.lib.packet import ether_types
from os_ken.lib.packet.packet import Packet
from os_ken.lib.packet.ethernet import ethernet

class TreeController(OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TreeController, self).__init__(*args, **kwargs)
        self.branch_factor = 4
        # Format
        # [<dpid>] : {
        #       [<dst_addr>]: [
        #           [<port_num>], 
        #           [<port_num>], 
        #       ],
        #} 
        self.all_switch_mac_table: dict[int, dict[str, deque[int]]]= dict()
        # Format
        # [<dpid>] : {
        #       [<dst_addr>]: {
        #           [<port_num>], 
        #           [<port_num>], 
        #       }, 
        #} 
        self.all_switch_ports: dict[int, dict[str, set[int]]]= dict()

    def __add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod: ofproto_v1_3_parser.OFPFlowMod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
            flags=ofproto_v1_3.OFPFF_SEND_FLOW_REM,
        )
        datapath.send_msg(mod)


    def __init_default_flow_rule(self, datapath, ofp, ofp_parser):
        match = ofp_parser.OFPMatch()
        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_CONTROLLER)]
        self.__add_flow(datapath, 0, match, actions)

        match = ofp_parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IPV6)
        self.__add_flow(datapath, 65535, match, [])


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
        self.all_switch_mac_table[datapath.id] = dict()
        self.all_switch_ports[datapath.id] = dict()

        self.__init_default_flow_rule(datapath, ofp, ofp_parser)
        self.__init_flood_flow_rules(datapath, ofp, ofp_parser)


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        in_port = msg.match["in_port"]
        datapath = msg.datapath
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
            data = msg.data

        eth_headers = Packet(msg.data).get_protocol(ethernet)
        if eth_headers.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        eth_src = eth_headers.src
        eth_dst = eth_headers.dst

        forward_table = self.all_switch_mac_table.get(datapath.id)
        port_table = self.all_switch_ports.get(datapath.id)
        if forward_table is None or port_table is None:
            print("WARN: switch not initialized")
            return
        if eth_src not in forward_table:
            forward_table[eth_src] = deque()
            port_table[eth_src] = set()
        if in_port not in port_table[eth_src]:
            port_table[eth_src].add(in_port)
            forward_table[eth_src].append(in_port)
            print(f"{eth_src} reachable through switch {datapath.id} port {in_port}")

        pprint(self.all_switch_mac_table)

        # No action is performed for broadcast packets. 
        # Flow rules for broadcast packets are already installed
        # These packets are used to only learn the port of src_ip
        if eth_headers.dst == "ff:ff:ff:ff:ff:ff":
            return

        if eth_dst not in forward_table or len(forward_table[eth_dst]) == 0:
            print(f"WARN: {eth_dst} not reachable through switch {datapath.id}")
            return

        port_number = forward_table[eth_dst][0]
        forward_table[eth_dst].rotate()

        actions = [ofp_parser.OFPActionOutput(port_number)]
        match = ofp_parser.OFPMatch(eth_dst=eth_dst)
        self.__add_flow(datapath, 5000, match, actions)

        # Need to send the data packet back to switch
        # Switch does not buffer the data packets
        out = ofp_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)

        del ev
        del datapath
