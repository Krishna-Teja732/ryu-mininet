import requests
import requests.adapters
from os_ken.topology.switches import Port, Switch, Link, Host

url_base = "http://localhost:8080/openflow13"


def send_switch_enter_event(dpid):
    print(f"Switch Enter: {dpid}")
    with open("event.txt", "a") as file:
        file.write(f"post,{url_base}/{dpid}\n")


def send_switch_leave_event(dpid):
    print(f"Switch Leave: {dpid}")
    with open("event.txt", "a") as file:
        file.write(f"delete,{url_base}/{dpid}\n")


def send_flow_add_event(dpid, table_id, request_body):
    print(f"Flow Add: {dpid}/{table_id} flowRule: {request_body}")
    with open("event.txt", "a") as file:
        file.write(f"post,{url_base}/{dpid}/flowrule,{request_body}\n")


def send_flow_remove_event(dpid, table_id, request_body):
    print(f"Flow remove: {dpid}/{table_id} flowRule: {request_body}")
    with open("event.txt", "a") as file:
        file.write(f"delete,{url_base}/{dpid}/flowrule,{request_body}\n")


def send_link_add_event(request_body: dict):
    print(f"Link Add: {request_body}")
    with open("event.txt", "a") as file:
        file.write(f"post,{url_base}/links,{request_body}\n")


def send_link_delete_event(request_body: dict):
    print(f"Link Delete: {request_body}")
    with open("event.txt", "a") as file:
        file.write(f"delete,{url_base}/links,{request_body}\n")


def send_host_add_event(request_body: dict):
    print(f"Host add: {request_body}")
    with open("event.txt", "a") as file:
        file.write(f"post,{url_base}/hosts,{request_body}\n")


def print_response(res: requests.Response):
    print(res.request.method, res.url, res.status_code, res.request.body)
