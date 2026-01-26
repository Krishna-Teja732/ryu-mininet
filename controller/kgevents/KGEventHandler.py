import requests
import requests.adapters
from multiprocessing.pool import ThreadPool
from os_ken.topology.switches import Port, Switch, Link, Host

adapter = requests.adapters.HTTPAdapter(pool_maxsize=1, pool_block=True)
url_base = "http://localhost:8080/ryu/openflow13"
session = requests.session()
session.mount("http://", adapter)
thread_pool = ThreadPool(1)


def send_switch_enter_event(dpid):
    print(f"Switch Enter: {dpid}")
    with open("event.txt", "a") as file:
        file.write(f"post,{url_base}/{dpid}\n")
    print_response(session.post(f"{url_base}/{dpid}"))


def send_switch_leave_event(dpid):
    print(f"Switch Leave: {dpid}")
    with open("event.txt", "a") as file:
        file.write(f"delete,{url_base}/{dpid}\n")
    print_response(session.delete(f"{url_base}/{dpid}"))


def send_flow_add_event(dpid, table_id, request_body):
    print(f"Flow Add: {dpid}/{table_id} flowRule: {request_body}")
    with open("event.txt", "a") as file:
        file.write(f"post,{url_base}/{dpid}/{table_id}/flowrule,{request_body}\n")
    print_response(
        session.post(url=f"{url_base}/{dpid}/{table_id}/flowrule", json=request_body)
    )


def send_flow_remove_event(dpid, table_id, request_body):
    print(f"Flow remove: {dpid}/{table_id} flowRule: {request_body}")
    with open("event.txt", "a") as file:
        file.write(f"delete,{url_base}/{dpid}/{table_id}/flowrule,{request_body}\n")
    print_response(
        session.delete(url=f"{url_base}/{dpid}/{table_id}/flowrule", json=request_body)
    )


def send_link_add_event(request_body: dict):
    print(f"Link Add: {request_body}")
    with open("event.txt", "a") as file:
        file.write(f"post,{url_base}/links,{request_body}\n")
    print_response(session.post(url=f"{url_base}/links", json=request_body))


def send_link_delete_event(request_body: dict):
    print(f"Link Delete: {request_body}")
    with open("event.txt", "a") as file:
        file.write(f"delete,{url_base}/links,{request_body}\n")
    print_response(session.delete(url=f"{url_base}/links", json=request_body))


def send_host_add_event(request_body: dict):
    print(f"Host add: {request_body}")
    with open("event.txt", "a") as file:
        file.write(f"post,{url_base}/hosts,{request_body}\n")
    print_response(session.post(url=f"{url_base}/hosts", json=request_body))


def print_response(res: requests.Response):
    print(res.request.method, res.url, res.status_code, res.request.body)
