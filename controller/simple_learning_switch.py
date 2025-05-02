from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_0

# Get the ethernet header from packet
from ryu.lib.packet.ethernet import ethernet
from ryu.lib.packet import ether_types

## Convert bytes to object of protos in the bytes(used for decoding the bytes)
from ryu.lib.packet.packet import Packet


class L2LearningSwitch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(L2LearningSwitch, self).__init__(*args, **kwargs)
        self.dst_mac_to_port_dict = dict()

    ## Set the default flow rule to send packet to controller when none of the existing rules match
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # When packet does not match any flow rule at switch, send it to the controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER)]

        # Create the flow rule
        mod = parser.OFPFlowMod(
            datapath=datapath, match=match, priority=0, actions=actions
        )

        # Send the flow rule to switch
        datapath.send_msg(mod)

    # Here ev is the event that the function handles
    # In this case the ev is an instance of EventOFPPacketIn
    # Here the second arg of set_ev_cls specifies in which phase this handler is called,
    #
    # MAIN_DISPATCHER is the phase after the switch is configured
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        # Here msg is of the type ryu.ofproto.ofproto_<<version>>_parser.OFPPacketIn
        msg = ev.msg

        # Here the data path is the switch
        dp = msg.datapath

        # The ofp version and parser used by the switch
        ofp = dp.ofproto
        ofp_parser: ofproto_v1_0_parser = dp.ofproto_parser

        # What action should the switch perform
        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_FLOOD)]

        # If data path id does not exist, create new entry in dict
        if dp.id not in self.dst_mac_to_port_dict.keys():
            self.dst_mac_to_port_dict[dp.id] = dict()

        data = None
        # If the message is not buffered at the swtich the buffer id is set to ofp.OfP_NO_BUFFER
        # Set the data at the controller before sending to the switch if the switch did not buffer the packet
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
            data = msg.data

        # decode data and get ethernet frame
        eth_frame = Packet(msg.data).get_protocol(ethernet)

        # Get the incomming port
        in_port = msg.in_port
        # Get the src and destination mac address from the frame
        src_mac = eth_frame.src
        dst_mac = eth_frame.dst

        # Learn the port for the mac address
        self.dst_mac_to_port_dict[dp.id][src_mac] = in_port

        # If the port for the address is know, forward instead of flood, set the flow rule
        if dst_mac in self.dst_mac_to_port_dict[dp.id].keys():
            # change acition to forward instead of flood
            actions = [
                ofp_parser.OFPActionOutput(self.dst_mac_to_port_dict[dp.id][dst_mac])
            ]

            # set flow rule
            match = ofp_parser.OFPMatch(dl_dst=dst_mac, in_port=in_port)
            # Create the flow rule
            mod = ofp_parser.OFPFlowMod(
                datapath=dp, match=match, priority=1, actions=actions
            )

            # Send the flow rule to switch
            dp.send_msg(mod)

        # Create the ofp_packet to send to the switch
        # if the swtich buffered the packet, the data can be left as None
        # Here the action is not the same as setting a flow rule, this specifies is the action for this particular packet
        out = ofp_parser.OFPPacketOut(
            datapath=dp,
            buffer_id=msg.buffer_id,
            in_port=msg.in_port,
            actions=actions,
            data=data,
        )

        # Send the ofp packet to the swtich
        dp.send_msg(out)
