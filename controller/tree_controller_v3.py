from os_ken.base.app_manager import OSKenApp
from os_ken.controller import ofp_event
from os_ken.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import ether_types
from os_ken.lib.packet.packet import Packet
from os_ken.lib.packet.ethernet import ethernet
from kgevents import KGEventHandler as kg_events
from dataclasses import dataclass, field
import resource


soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
print(f"Resource Limits for open files(soft, hard): {resource.getrlimit(resource.RLIMIT_NOFILE)}")


class TreeControllerV2(OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    @dataclass(order=True)
    class OutputPort:
        flow_count: int
        number: int = field(compare=False)

    def __init__(self, *args, **kwargs):
        super(TreeControllerV2, self).__init__(*args, **kwargs)
        self.branch_factor = 10
        # Format
        # [<dpid>] : {
        #       [<dst_addr>]: [
        #           [<port_num>], 
        #           [<port_num>], 
        #       ],
        #} 
        self.all_switch_mac_table: dict[int, dict[str, list[TreeControllerV2.OutputPort]]]= dict()
        # Format
        # [<dpid>] : {
        #       [<dst_addr>]: {
        #           [<port_num>], 
        #           [<port_num>], 
        #       }, 
        #} 
        self.all_switch_ports: dict[int, dict[str, set[int]]]= dict()

        # Format
        # [<dpid>] : {
        #       [<port_number>]: OutputPort,
        #       [<port_number>]: OutputPort,
        #} 
        self.port_to_obj: dict[int, dict[int, TreeControllerV2.OutputPort]]= dict()

        # Format
        # dpid : {"eth_src:eth_dst": "output_port",  ...  "eth_src:eth_dst": "output_port"} 
        self.dpid_flows: dict[int, dict[str, TreeControllerV2.OutputPort]] = dict()


    def __add_flow(self, datapath, priority, match, actions):
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

        body = {"dpid": datapath.id}

        # Add only if the datapath is not already present i.e. case where the switch reconnects
        if datapath.id not in self.all_switch_mac_table:
            self.all_switch_mac_table[datapath.id] = dict()
            self.all_switch_ports[datapath.id] = dict()
            self.port_to_obj[datapath.id] = dict()
            for port_num in range(1, self.branch_factor + 1):
                self.port_to_obj[datapath.id][port_num] = TreeControllerV2.OutputPort(0, port_num)
            self.dpid_flows[datapath.id] = dict()
            kg_events.send_switch_enter_event(**body)

        self.__init_default_flow_rule(datapath, ofp, ofp_parser)
        self.__init_flood_flow_rules(datapath, ofp, ofp_parser)


    @set_ev_cls(ofp_event.EventOFPFlowRemoved, MAIN_DISPATCHER)
    def flow_removed_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofp = datapath.ofproto

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
            forward_table[eth_src] = list()
            port_table[eth_src] = set()
        if in_port not in port_table[eth_src]:
            port_table[eth_src].add(in_port)
            forward_table[eth_src].append(self.port_to_obj[datapath.id][in_port])
            print(f"{eth_src} reachable through switch {datapath.id} port {in_port}")

        # No action is performed for broadcast packets. 
        # Flow rules for broadcast packets are already installed
        # These packets are used to only learn the port of src_ip
        if eth_headers.dst == "ff:ff:ff:ff:ff:ff":
            return

        if eth_dst not in forward_table or len(forward_table[eth_dst]) == 0:
            print(f"WARN: {eth_dst} not reachable through switch {datapath.id}")
            return


        flow = f"{eth_src}:{eth_dst}"
        if flow not in self.dpid_flows[datapath.id]:
            # Select port (Using something like a priority queue does not 
            # work because updating the key of an object inside the priority 
            # queue does not reorder the queue)
            output_port = forward_table[eth_dst][0]
            for port in forward_table[eth_dst]:
                if port.flow_count < output_port.flow_count:
                    output_port = port

            # Increment number flows for in_port and out_port
            self.port_to_obj[datapath.id][in_port].flow_count += 1
            output_port.flow_count = output_port.flow_count + 1

            self.dpid_flows[datapath.id][flow] = output_port

            actions = [ofp_parser.OFPActionOutput(output_port.number)]
            match = ofp_parser.OFPMatch(eth_src=eth_src,eth_dst=eth_dst)
            self.__add_flow(datapath, 5000, match, actions)
        else: 
            output_port = self.dpid_flows[datapath.id][flow]

        actions = [ofp_parser.OFPActionOutput(output_port.number)]

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


    # @set_ev_cls(topology_events.EventSwitchLeave, MAIN_DISPATCHER)
    # def _switch_leave_handler(self, ev):
    #     datapath = ev.switch.dp
    #     body = {"dpid": datapath.id}
    #     kg_events.send_switch_leave_event(**body)
    #
    #
    # @set_ev_cls(topology_events.EventHostAdd, MAIN_DISPATCHER)
    # def _host_add_handler(self, ev):
    #     host: Host = ev.host
    #     body = {
    #                 "request_body": {
    #                     "mac": host.mac,
    #                     "port": {"dpid": host.port.dpid, "port_no": host.port.port_no},
    #                 }
    #             }
    #     kg_events.send_host_add_event(**body)
    #
    #
    # @set_ev_cls(topology_events.EventHostMove, MAIN_DISPATCHER)
    # def _host_move_handler(self, ev):
    #     host: Host = ev.host
    #     self.logger.info(f"Host Move: {host}")
    #
    #
    # @set_ev_cls(topology_events.EventLinkAdd, MAIN_DISPATCHER)
    # def _link_add_handler(self, ev):
    #     link: Link = ev.link
    #     body = {
    #                 "request_body": {
    #                     "src": {"dpid": link.src.dpid, "port_no": link.src.port_no},
    #                     "dst": {"dpid": link.dst.dpid, "port_no": link.dst.port_no},
    #                 }
    #             }
    #     kg_events.send_link_add_event(**body)
    #
    #
    # @set_ev_cls(topology_events.EventLinkDelete, MAIN_DISPATCHER)
    # def _link_delete_handler(self, ev):
    #     link: Link = ev.link
    #     body = {
    #                 "request_body": {
    #                     "src": {"dpid": link.src.dpid, "port_no": link.src.port_no},
    #                     "dst": {"dpid": link.dst.dpid, "port_no": link.dst.port_no},
    #                 }
    #             }
    #     kg_events.send_link_delete_event(**body)
