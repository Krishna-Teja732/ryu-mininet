import requests
import requests.adapters
from ryu.topology.switches import Port, Switch, Link, Host


class KGEventHandler:

    def __init__(self, url_base="http://localhost:8080/ryu/openflow13"):
        adapter = requests.adapters.HTTPAdapter(pool_maxsize=1, pool_block=True)
        self.url_base = url_base
        self.session = requests.session()
        self.session.mount("http://", adapter)

    def send_switch_enter_event(self, dpid):
        print(f"Switch Enter: {dpid}")
        self.session.post(f"{self.url_base}/{dpid}")

    def send_switch_leave_event(self, dpid):
        print(f"Switch Leave: {dpid}")
        self.session.delete(f"{self.url_base}/{dpid}")

    def send_flow_add_event(self, dpid, table_id, request_body):
        print(f"Flow Add: {dpid}/{table_id} flowRule: {request_body}")
        self.session.post(
            f"{self.url_base}/{dpid}/{table_id}/flowrule", json=request_body
        )

    def send_flow_remove_event(self, dpid, table_id, request_body):
        print(f"Flow remove: {dpid}/{table_id} flowRule: {request_body}")
        self.session.delete(
            f"{self.url_base}/{dpid}/{table_id}/flowrule", json=request_body
        )

    def send_link_add_event(self, link: Link):
        src: Port = link.src
        dst: Port = link.dst
        request_body = dict()
        request_body = {
            "src": {"dpid": src.dpid, "port_no": src.port_no},
            "dst": {"dpid": dst.dpid, "port_no": dst.port_no},
        }
        print(f"Link Add: {request_body}")

        self.session.post(f"{self.url_base}/links", json=request_body)

    def send_link_delete_event(self, link: Link):
        src: Port = link.src
        dst: Port = link.dst
        request_body = dict()
        request_body = {
            "src": {"dpid": src.dpid, "port_no": src.port_no},
            "dst": {"dpid": dst.dpid, "port_no": dst.port_no},
        }
        print(f"Link Add: {request_body}")
        self.session.delete(f"{self.url_base}/links", json=request_body)

    def send_host_add_event(self, host: Host):
        request_body = {
            "mac": host.mac,
            "port": {"dpid": host.port.dpid, "port_no": host.port.port_no},
        }
        print(f"Host add: {request_body}")
        self.session.post(f"{self.url_base}/hosts", json=request_body)
