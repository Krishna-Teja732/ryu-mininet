import requests
import requests.adapters
from multiprocessing.pool import ThreadPool
from ryu.topology.switches import Port, Switch, Link, Host


class KGEventHandler:

    def __init__(self, url_base="http://localhost:8080/ryu/openflow13"):
        adapter = requests.adapters.HTTPAdapter(pool_maxsize=1, pool_block=True)
        self.url_base = url_base
        self.session = requests.session()
        self.session.mount("http://", adapter)
        self.thread_pool = ThreadPool(1)

    def send_switch_enter_event(self, dpid):
        print(f"Switch Enter: {dpid}")
        self.thread_pool.apply_async(
            self.session.post,
            args=(f"{self.url_base}/{dpid}",),
            callback=success_callback,
            error_callback=error_callback,
        )

    def send_switch_leave_event(self, dpid):
        print(f"Switch Leave: {dpid}")
        self.thread_pool.apply_async(
            self.session.delete,
            args=(f"{self.url_base}/{dpid}",),
            callback=success_callback,
            error_callback=error_callback,
        )

    def send_flow_add_event(self, dpid, table_id, request_body):
        print(f"Flow Add: {dpid}/{table_id} flowRule: {request_body}")
        self.thread_pool.apply_async(
            self.session.post,
            kwds={
                "url": f"{self.url_base}/{dpid}/{table_id}/flowrule",
                "json": request_body,
            },
            callback=success_callback,
            error_callback=error_callback,
        )

    def send_flow_remove_event(self, dpid, table_id, request_body):
        print(f"Flow remove: {dpid}/{table_id} flowRule: {request_body}")
        self.thread_pool.apply_async(
            self.session.delete,
            kwds={
                "url": f"{self.url_base}/{dpid}/{table_id}/flowrule",
                "json": request_body,
            },
            callback=success_callback,
            error_callback=error_callback,
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
        self.thread_pool.apply_async(
            self.session.post,
            kwds={
                "url": f"{self.url_base}/links",
                "json": request_body,
            },
            callback=success_callback,
            error_callback=error_callback,
        )

    def send_link_delete_event(self, link: Link):
        src: Port = link.src
        dst: Port = link.dst
        request_body = dict()
        request_body = {
            "src": {"dpid": src.dpid, "port_no": src.port_no},
            "dst": {"dpid": dst.dpid, "port_no": dst.port_no},
        }
        print(f"Link Add: {request_body}")
        self.thread_pool.apply_async(
            self.session.delete,
            kwds={
                "url": f"{self.url_base}/links",
                "json": request_body,
            },
            callback=success_callback,
            error_callback=error_callback,
        )

    def send_host_add_event(self, host: Host):
        request_body = {
            "mac": host.mac,
            "port": {"dpid": host.port.dpid, "port_no": host.port.port_no},
        }
        print(f"Host add: {request_body}")
        self.thread_pool.apply_async(
            self.session.post,
            kwds={
                "url": f"{self.url_base}/hosts",
                "json": request_body,
            },
            callback=success_callback,
            error_callback=error_callback,
        )


def success_callback(res: requests.Response):
    print(res.request.method, res.url, res.status_code, res.request.body)


def error_callback(err: BaseException):
    print("Error: ", err)
