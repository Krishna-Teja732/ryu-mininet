from pprint import pprint
from typing import Literal
from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, set_ev_cls
from ryu.lib.packet import ether_types
from ryu.lib.packet.packet import Packet
from ryu.lib.packet.ethernet import ethernet

FORWARD_TABLE_ID = 0
FLOOD_TABLE_ID = 1


class TreeController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TreeController, self).__init__(*args, **kwargs)
        self.dst_mac_address_to_port = dict()
        self.branch_factor = 6

    def __init_forward_table(self, datapath, ofp, ofp_parser):
        # TODO: Send to controller to instead of sending to flood table
        broadcast_pkt_instructions = [
            ofp_parser.OFPInstructionGotoTable(FLOOD_TABLE_ID)
        ]
        go_to_flood_table = ofp_parser.OFPFlowMod(
            datapath=datapath,
            table_id=FORWARD_TABLE_ID,
            match=ofp_parser.OFPMatch(),
            priority=0,
            instructions=broadcast_pkt_instructions,
        )
        datapath.send_msg(go_to_flood_table)

    def __init_flood_table(self, datapath, ofp, ofp_parser):
        # Broadcast to ports from range [k/2 + 1, k] to prevent broadcast storming
        partial_flood_actions = [
            ofp_parser.OFPActionOutput(port)
            for port in range(self.branch_factor // 2 + 1, self.branch_factor + 1)
        ]
        partial_flood_instruction = [
            ofp_parser.OFPInstructionActions(
                ofp.OFPIT_APPLY_ACTIONS, partial_flood_actions
            )
        ]
        for in_port in range(1, self.branch_factor // 2 + 1):
            partial_flood_flow_mod = ofp_parser.OFPFlowMod(
                datapath=datapath,
                table_id=FLOOD_TABLE_ID,
                match=ofp_parser.OFPMatch(in_port=in_port),
                priority=0,
                instructions=partial_flood_instruction,
            )
            datapath.send_msg(partial_flood_flow_mod)

        # Default action: flood. Because of the previous match condition, packets with in_port in range
        # [branch_factor/2, branch_factor] will be matched. This will not cause broadcast storming
        flood_action = [ofp_parser.OFPActionOutput(ofp.OFPP_FLOOD)]
        flood_instruction = [
            ofp_parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, flood_action)
        ]
        table_miss_flow_rule = ofp_parser.OFPFlowMod(
            datapath=datapath,
            table_id=FLOOD_TABLE_ID,
            match=ofp_parser.OFPMatch(),
            priority=0,
            instructions=flood_instruction,
        )
        datapath.send_msg(table_miss_flow_rule)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features_handler(self, ev):
        datapath = ev.msg.datapath
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        self.__init_forward_table(datapath, ofp, ofp_parser)
        self.__init_flood_table(datapath, ofp, ofp_parser)

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
        # If the packet is an LLDP packet, the peer on the port is a switch
        if eth_headers.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        # learning switch implementation
        if datapath.id not in self.dst_mac_address_to_port.keys():
            self.dst_mac_address_to_port[datapath.id] = dict()

        self.dst_mac_address_to_port[datapath.id][eth_headers.src] = in_port

        if eth_headers.dst in self.dst_mac_address_to_port[datapath.id].keys():
            output_port = self.dst_mac_address_to_port[datapath.id][eth_headers.dst]
            actions = [ofp_parser.OFPActionOutput(output_port)]

            # if the peer is a host, strip the vlan before forwarding
            if self.datapath_ports[datapath.id][output_port]["peer_type"] == "host":
                actions.insert(0, ofp_parser.OFPActionPopVlan())

            pkt_forward_instruction = [
                ofp_parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)
            ]
            forward_pkt = ofp_parser.OFPFlowMod(
                datapath=datapath,
                table_id=FORWARD_TABLE_ID,
                match=ofp_parser.OFPMatch(eth_dst=eth_headers.dst),
                priority=1,
                instructions=pkt_forward_instruction,
            )
            datapath.send_msg(forward_pkt)
