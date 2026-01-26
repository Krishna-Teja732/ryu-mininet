### 1. Initialize virtual env 
- Install dependencies(required only once)
```sh
pipenv install
```

### 2. Run osken application
- Use virtual env shell 
```sh
pipenv shell
```
- To run an osken application, the osken-manager command is used. 
```sh
osken-manager ./controller/stp_controller.py --observe-links --ofp-tcp-listen-port 10001
```
- We are running three applications
    - ./controller/stp_controller.py: STP application, prevents loops in the network

### 3. Run mininet topology
- Use the following command to create a topology
```sh
sudo mn --mac --switch ovs,protocol=OpenFlow13 --controller remote,ip=127.0.0.1,port=10001 --custom ./topology/topos.py --topo TriangleTopo
```

### 4. Commands used for event drivent KG build
- Run osken controller
```sh
osken-manager ./controller/stp_controller_v2.py --observe-links --ofp-tcp-listen-port 10001
```
- Run mininet
```sh
sudo mn --mac --switch ovs,protocol=OpenFlow13 --controller remote,ip=127.0.0.1,port=10001 --custom ./topology/topos.py --topo TriangleTopo
```
