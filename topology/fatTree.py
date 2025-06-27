from mininet.topo import Topo


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

    def build(self):
        k = 6

        num_core_switches = (k // 2) ** 2
        core_switches = []
        switch_id = 1
        host_id = 1
        # Core switches
        for core_ind in range(num_core_switches):
            core_switches.append(self.addSwitch(f"c{switch_id}"))
            switch_id += 1

        # Pods
        for pod_ind in range(k):
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


topos = {"FatTreeTopo": (lambda: FatTreeTopo())}
