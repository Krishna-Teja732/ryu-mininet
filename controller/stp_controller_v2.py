# Copyright (C) 2016 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Modified from source: https://github.com/faucetsdn/ryu/blob/master/ryu/app/simple_switch_stp_13.py

from os_ken.base.app_manager import OSKenApp
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from os_ken.controller.handler import set_ev_cls
from os_ken.controller.controller import Datapath
from os_ken.ofproto import ofproto_v1_3, ofproto_v1_3_parser
from os_ken.lib import dpid as dpid_lib
from os_ken.lib import stplib
from os_ken.lib.packet import packet
from os_ken.lib.packet import ethernet
from os_ken.lib.packet import ether_types
from os_ken.topology import event as topology_events
from os_ken.topology.switches import Port, Switch, Link, Host
from multiprocessing import Process, Queue

from kgevents import KGEventHandler as kg_events


def send_kg_events(queue: Queue):
    while True:
        fun, args = queue.get()
        fun(**args)


kg_event_queue = Queue()
# TODO: Fix
Process(target=send_kg_events, args=(kg_event_queue,)).start()


class STPControllerOFPV_1_3(OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {"stplib": stplib.Stp}

    def __init__(self, *args, **kwargs):
        super(STPControllerOFPV_1_3, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.stp = kwargs["stplib"]

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id:
            mod: ofproto_v1_3_parser.OFPFlowMod = parser.OFPFlowMod(
                datapath=datapath,
                buffer_id=buffer_id,
                priority=priority,
                match=match,
                instructions=inst,
                flags=ofproto_v1_3.OFPFF_SEND_FLOW_REM,
            )
        else:
            mod: ofproto_v1_3_parser.OFPFlowMod = parser.OFPFlowMod(
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

        kg_event_queue.put(
            (
                kg_events.send_flow_add_event,
                {
                    "dpid": datapath.id,
                    "table_id": mod.table_id,
                    "request_body": {
                        "priority": mod.priority,
                        "oxm_fields": formatted_match,
                        "instructions": formatted_inst,
                    },
                },
            )
        )

        datapath.send_msg(mod)

    def delete_flow(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        for dst in self.mac_to_port[datapath.id].keys():
            match = parser.OFPMatch(eth_dst=dst)
            mod = parser.OFPFlowMod(
                datapath,
                command=ofproto.OFPFC_DELETE,
                out_port=ofproto.OFPP_ANY,
                out_group=ofproto.OFPG_ANY,
                priority=1,
                match=match,
            )
            datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        kg_event_queue.put((kg_events.send_switch_enter_event, {"dpid": datapath.id}))

        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)
        ]
        self.add_flow(datapath, 0, match, actions)

    @set_ev_cls(ofp_event.EventOFPFlowRemoved, MAIN_DISPATCHER)
    def flow_removed_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofp = datapath.ofproto

        formatted_match = dict()
        for _, match_headers in msg.match.stringify_attrs():
            formatted_match.update(match_headers)

        kg_event_queue.put(
            (
                kg_events.send_flow_remove_event,
                {
                    "dpid": datapath.id,
                    "table_id": msg.table_id,
                    "request_body": {
                        "priority": msg.priority,
                        "oxm_fields": formatted_match,
                    },
                },
            )
        )

    @set_ev_cls(stplib.EventPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            return

        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            self.add_flow(datapath, 1, match, actions)

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)

    @set_ev_cls(stplib.EventTopologyChange, MAIN_DISPATCHER)
    def _topology_change_handler(self, ev):
        datapath: Datapath = ev.dp
        dpid_str = dpid_lib.dpid_to_str(datapath.id)
        msg = "Receive topology change event. Flush MAC table."
        self.logger.debug("[dpid=%s] %s", dpid_str, msg)

        if datapath.id in self.mac_to_port:
            self.delete_flow(datapath)
            del self.mac_to_port[datapath.id]

    @set_ev_cls(stplib.EventPortStateChange, MAIN_DISPATCHER)
    def _port_state_change_handler(self, ev):
        dpid_str = dpid_lib.dpid_to_str(ev.dp.id)
        of_state = {
            stplib.PORT_STATE_DISABLE: "DISABLE",
            stplib.PORT_STATE_BLOCK: "BLOCK",
            stplib.PORT_STATE_LISTEN: "LISTEN",
            stplib.PORT_STATE_LEARN: "LEARN",
            stplib.PORT_STATE_FORWARD: "FORWARD",
        }
        self.logger.debug(
            "[dpid=%s][port=%d] state=%s", dpid_str, ev.port_no, of_state[ev.port_state]
        )

    @set_ev_cls(topology_events.EventSwitchLeave, MAIN_DISPATCHER)
    def _switch_leave_handler(self, ev):
        datapath = ev.switch.dp
        kg_event_queue.put((kg_events.send_switch_leave_event, {"dpid": datapath.id}))

    @set_ev_cls(topology_events.EventHostAdd, MAIN_DISPATCHER)
    def _host_add_handler(self, ev):
        host: Host = ev.host
        kg_event_queue.put(
            (
                kg_events.send_host_add_event,
                {
                    "request_body": {
                        "mac": host.mac,
                        "port": {"dpid": host.port.dpid, "port_no": host.port.port_no},
                    }
                },
            )
        )

    @set_ev_cls(topology_events.EventHostMove, MAIN_DISPATCHER)
    def _host_move_handler(self, ev):
        host: Host = ev.host
        self.logger.info(f"Host Move: {host}")

    @set_ev_cls(topology_events.EventLinkAdd, MAIN_DISPATCHER)
    def _link_add_handler(self, ev):
        link: Link = ev.link
        kg_event_queue.put(
            (
                kg_events.send_link_add_event,
                {
                    "request_body": {
                        "src": {"dpid": link.src.dpid, "port_no": link.src.port_no},
                        "dst": {"dpid": link.dst.dpid, "port_no": link.dst.port_no},
                    }
                },
            )
        )

    @set_ev_cls(topology_events.EventLinkDelete, MAIN_DISPATCHER)
    def _link_delete_handler(self, ev):
        link: Link = ev.link
        kg_event_queue.put(
            (
                kg_events.send_link_delete_event,
                {
                    "request_body": {
                        "src": {"dpid": link.src.dpid, "port_no": link.src.port_no},
                        "dst": {"dpid": link.dst.dpid, "port_no": link.dst.port_no},
                    }
                },
            )
        )
