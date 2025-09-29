import requests
from pprint import pprint

base_url = "http://localhost:8090"
flow_rule_base_url = f"{base_url}/stats/flow"
switch_url = f"{base_url}/v1.0/topology/switches"


def get_switches() -> list[int]:
    switches_response: list[dict] = requests.get(switch_url).json()
    dpids: list[int] = [int(switch["dpid"], base=16) for switch in switches_response]
    return dpids


def get_flow_rules(dpid: int) -> dict:
    retain_keys: set = {"actions", "match", "priority", "table_id"}

    response: dict = requests.get(f"{flow_rule_base_url}/{dpid}").json()
    formatted_flow_rules = list()
    for flow_rule in response[str(dpid)]:
        formatted_flow_rule: dict = {key: flow_rule[key] for key in retain_keys}
        formatted_flow_rules.append(formatted_flow_rule)

    return {str(dpid): list(formatted_flow_rules)}


if __name__ == "__main__":
    dpids = get_switches()
    for dpid in dpids:
        flow_rule = get_flow_rules(dpid)
        with open(f"./logs/flowrules/switch_{dpid}.log", "w") as file:
            pprint(flow_rule, stream=file)
