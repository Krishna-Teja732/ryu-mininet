### 1. Initialize virtual env 
- Install dependencies(required only once)
```sh
pipenv install
```

### 2. Run Ryu application
- Use virtual env shell 
```sh
pipenv shell
```
- To run an ryu application, the ryu-manager command is used. 
```sh
ryu-manager ./controller/ryu_stp_controller.py ryu.app.rest_topology ryu.app.ofctl_rest --wsapi-host=127.0.0.1 --wsapi-port=8080 --observe-links --ofp-tcp-listen-port 10001
```
- We are running three applications
    - ./controller/ryu_stp_controller.py: STP application, prevents loops in the network
    - ryu.app.rest_topology: Enables /v1.0/topology REST APIs([Source code](https://github.com/faucetsdn/ryu/blob/master/ryu/app/rest_topology.py))
    - ryu.app.ofctl_rest: Enables /stats/ REST APIs([RYU OFCTL Application](https://ryu.readthedocs.io/en/latest/app/ofctl_rest.html#get-table-features))
- The APIs are accessible through localhost:8080 

### 3. Run mininet topology
- Use the following command to create a topology
```sh
sudo mn --mac --switch ovs,protocol=OpenFlow13 --controller remote,ip=127.0.0.1,port=10001 --custom ./topology/topos.py --topo TriangleTopo
```
