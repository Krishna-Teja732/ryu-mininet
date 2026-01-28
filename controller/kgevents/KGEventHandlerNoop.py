import requests
import requests.adapters
from os_ken.topology.switches import Port, Switch, Link, Host


def send_switch_enter_event(dpid):
    pass

def send_switch_leave_event(dpid):
    pass

def send_flow_add_event(dpid, table_id, request_body):
    pass


def send_flow_remove_event(dpid, table_id, request_body):
    pass 


def send_link_add_event(request_body: dict):
    pass

def send_link_delete_event(request_body: dict):
    pass


def send_host_add_event(request_body: dict):
    pass

