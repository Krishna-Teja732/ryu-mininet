from mininet.topo import Topo
from mininet.link import TCLink
import random


class LinearTopo(Topo):

    def build(self):
        s1 = self.addSwitch("s1")
        s2 = self.addSwitch("s2")

        h1 = self.addHost("h1")
        h2 = self.addHost("h2")

        self.addLink(s1, s2, cls=TCLink, delay="100ms", loss=5)
        self.addLink(s1, h1, cls=TCLink, delay="10ms", loss=0)
        self.addLink(s2, h2, cls=TCLink, delay="20ms", loss=0)


class TriangleTopo(Topo):

    def build(self):
        s1 = self.addSwitch("s1")
        s2 = self.addSwitch("s2")
        s3 = self.addSwitch("s3")

        h1 = self.addHost("h1")
        h2 = self.addHost("h2")
        h3 = self.addHost("h3")

        self.addLink(s1, s2)
        self.addLink(s1, s3)
        self.addLink(s3, s2)

        self.addLink(s1, h1)
        self.addLink(s2, h2)
        self.addLink(s3, h3)


class MeshTopo(Topo):
    def build(self):
        number_of_nodes = 15
        switches = []
        hosts = []

        for index in range(1, number_of_nodes + 1):
            switches.append(self.addSwitch(f"s{index}"))
            hosts.append(self.addHost(f"h{index}"))
            self.addLink(hosts[index - 1], switches[index - 1])

        for x in range(number_of_nodes):
            for y in range(x + 1, number_of_nodes):
                self.addLink(switches[x], switches[y])


class TreeTopo(Topo):
    def build(self):
        number_of_nodes = 15
        switches = []
        hosts = []

        for index in range(1, number_of_nodes + 1):
            switches.append(self.addSwitch(f"s{index}"))
            hosts.append(self.addHost(f"h{index}"))
            self.addLink(hosts[index - 1], switches[index - 1])

        connectivity_set = []
        for x in range(number_of_nodes):
            connectivity_set.append(set())
            connectivity_set[x].add(switches[x])

        rand_gen = random.Random()
        while len(connectivity_set) > 1:
            midInd = int(len(connectivity_set) / 2)
            ind1 = rand_gen.randrange(0, midInd)
            ind2 = rand_gen.randrange(midInd, len(connectivity_set))

            s1 = connectivity_set[ind1].pop()
            s2 = connectivity_set[ind2].pop()
            self.addLink(s1, s2)
            connectivity_set[ind1] = connectivity_set[ind1].union(
                connectivity_set[ind2]
            )
            connectivity_set[ind1].add(s1)
            connectivity_set[ind1].add(s2)
            del connectivity_set[ind2]


class GraphTopo(Topo):
    def build(self):
        number_of_nodes = 15
        switches = []
        hosts = []

        for index in range(1, number_of_nodes + 1):
            switches.append(self.addSwitch(f"s{index}"))
            hosts.append(self.addHost(f"h{index}"))
            self.addLink(hosts[index - 1], switches[index - 1])

        connectivity_set = []
        for x in range(number_of_nodes):
            connectivity_set.append(set())
            connectivity_set[x].add(switches[x])

        rand_gen = random.Random()
        while len(connectivity_set) > 1:
            midInd = int(len(connectivity_set) / 2)
            ind1 = rand_gen.randrange(0, midInd)
            ind2 = rand_gen.randrange(midInd, len(connectivity_set))

            s1 = connectivity_set[ind1].pop()
            s2 = connectivity_set[ind2].pop()
            self.addLink(s1, s2)
            connectivity_set[ind1] = connectivity_set[ind1].union(
                connectivity_set[ind2]
            )
            connectivity_set[ind1].add(s1)
            connectivity_set[ind1].add(s2)
            del connectivity_set[ind2]

        while number_of_nodes > -1:
            ind1 = rand_gen.randrange(0, len(switches))
            ind2 = rand_gen.randrange(0, len(switches))
            if ind1 == ind2:
                continue

            self.addLink(switches[ind1], switches[ind2])
            number_of_nodes -= 1


class BoxTopo(Topo):
    def build(self):
        s1 = self.addSwitch("s1")
        s2 = self.addSwitch("s2")
        s3 = self.addSwitch("s3")
        s4 = self.addSwitch("s4")

        h1 = self.addHost("h1")
        h2 = self.addHost("h2")
        h3 = self.addHost("h3")
        h4 = self.addHost("h4")

        self.addLink(s1, s2)
        self.addLink(s2, s3)
        self.addLink(s3, s4)
        self.addLink(s4, s1)

        self.addLink(s1, h1)
        self.addLink(s2, h2)
        self.addLink(s3, h3)
        self.addLink(s4, h4)


class LinearTopoV2(Topo):

    def build(self):
        s1 = self.addSwitch("s1")
        h1 = self.addHost("h1")
        h2 = self.addHost("h2")

        s2 = self.addSwitch("s2")
        h3 = self.addHost("h3")
        h4 = self.addHost("h4")

        self.addLink(s1, s2)
        self.addLink(s1, h1)
        self.addLink(s1, h2)
        self.addLink(s2, h3)
        self.addLink(s2, h4)


topos = {
    "LinearTopo": (lambda: LinearTopo()),
    "TriangleTopo": (lambda: TriangleTopo()),
    "MeshTopo": (lambda: MeshTopo()),
    "TreeTopo": (lambda: TreeTopo()),
    "GraphTopo": (lambda: GraphTopo()),
    "BoxTopo": (lambda: BoxTopo()),
    "LinearTopoV2": (lambda: LinearTopoV2()),
}
