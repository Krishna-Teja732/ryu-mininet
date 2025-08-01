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

from ryu.base.app_manager import RyuApp
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3, ofproto_v1_3_parser
from ryu.lib import dpid as dpid_lib
from ryu.lib import stplib
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types


class STPControllerOPFV_1_3(RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {"stplib": stplib.Stp}

    def __init__(self, *args, **kwargs):
        super(STPControllerOPFV_1_3, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.stp = kwargs["stplib"]

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                buffer_id=buffer_id,
                priority=priority,
                match=match,
                instructions=inst,
                flags=ofproto_v1_3.OFPFF_SEND_FLOW_REM,
            )
        else:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                priority=priority,
                match=match,
                instructions=inst,
                flags=ofproto_v1_3.OFPFF_SEND_FLOW_REM,
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

        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)
        ]
        self.add_flow(datapath, 0, match, actions)

    @set_ev_cls(ofp_event.EventOFPFlowRemoved, MAIN_DISPATCHER)
    def flow_removed_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto

        if msg.reason == ofp.OFPRR_IDLE_TIMEOUT:
            reason = "IDLE TIMEOUT"
        elif msg.reason == ofp.OFPRR_HARD_TIMEOUT:
            reason = "HARD TIMEOUT"
        elif msg.reason == ofp.OFPRR_DELETE:
            reason = "DELETE"
        elif msg.reason == ofp.OFPRR_GROUP_DELETE:
            reason = "GROUP DELETE"
        else:
            reason = "unknown"

        self.logger.debug(
            "OFPFlowRemoved received: "
            "cookie=%d priority=%d reason=%s table_id=%d "
            "duration_sec=%d duration_nsec=%d "
            "idle_timeout=%d hard_timeout=%d "
            "packet_count=%d byte_count=%d match.fields=%s",
            msg.cookie,
            msg.priority,
            msg.reason,
            msg.table_id,
            msg.duration_sec,
            msg.duration_nsec,
            msg.idle_timeout,
            msg.hard_timeout,
            msg.packet_count,
            msg.byte_count,
            msg.match,
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
        dp = ev.dp
        dpid_str = dpid_lib.dpid_to_str(dp.id)
        msg = "Receive topology change event. Flush MAC table."
        self.logger.debug("[dpid=%s] %s", dpid_str, msg)

        if dp.id in self.mac_to_port:
            self.delete_flow(dp)
            del self.mac_to_port[dp.id]

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
