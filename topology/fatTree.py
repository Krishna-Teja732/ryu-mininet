from time import sleep
from mininet.node import RemoteController
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.cli import CLI


# Fat tree topology reference: https://www.cs.cornell.edu/courses/cs5413/2014fa/lectures/08-fattree.pdf
# Switches are added to the topology such that for each
# Aggregate switch:
#   - Ports from [1, k/2] is connected to core switch
#   - Ports from [k/2 + 1, k] is connected to edge switch
# Edge Switch:
#   - Ports from [1, k/2] is connected to aggregate switch
#   - Ports from [k/2 + 1, k] is connected to host
class FatTreeTopo(Topo):
    "Fat-tree topology"
    def __init__(self, k, *args, **params):
        self.k = k
        super().__init__(*args, **params)

    def build(self):
        k = self.k 
        num_core_switches = (k // 2) ** 2
        core_switches = []
        switch_id = 1
        host_id = 1
        # Core switches
        for _ in range(num_core_switches):
            core_switches.append(self.addSwitch(f"c{switch_id}"))
            switch_id += 1

        # Pods
        for _ in range(k):
            pod_agg_switches = []
            # Each Pod has k/2 agg switches
            for ind in range(k // 2):
                agg_switch = self.addSwitch(f"a{switch_id}")
                pod_agg_switches.append(agg_switch)
                switch_id += 1

                for core_sw_ind in range(ind, num_core_switches, k // 2):
                    self.addLink(agg_switch, core_switches[core_sw_ind])

            # Add edge switches and hosts
            for _ in range(k // 2):
                edge_switch = self.addSwitch(f"e{switch_id}")
                switch_id += 1

                # Connect to all the pod's agg switches to the edge switch
                for agg_switch in pod_agg_switches:
                    self.addLink(edge_switch, agg_switch)

                # Add hosts for each edge switch
                for _ in range(k // 2):
                    host = self.addHost(f"h{host_id}")
                    host_id = host_id + 1
                    self.addLink(host, edge_switch)


topos = {"FatTreeTopo": (lambda: FatTreeTopo(4))}


if __name__ == "__main__":
    net = Mininet(topo=FatTreeTopo(10), waitConnected=True, autoSetMacs=True ,controller=RemoteController('c1', port=10001))
    net.start()
    print(f"Added {len(net.switches)} Switches")
    print(f"Added {len(net.hosts)} Hosts")
    print(f"Added {len(net.links)} Links")
    print(f"Press any key to start Arping")
    input()

    print("Sending gratuitous arp for each host")
    for host in net.hosts:
        print(host.cmd(f"arping -U -c 1 -I {host.defaultIntf().name} {host.IP()}"))
        sleep(0.2)

    CLI(net)
    net.stop()
