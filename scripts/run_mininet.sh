sudo systemctl start ovs-vswitchd
sudo mn --mac --switch ovs,protocol=OpenFlow13 --controller remote,ip=127.0.0.1,port=10001 --custom ./topology/fatTree.py --topo FatTreeTopo
