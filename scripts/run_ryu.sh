#! /bin/bash

# Run this script using bash. Do not run it directly


# ryu-manager ./controller/tree_controller.py ryu.app.rest_topology ryu.app.ofctl_rest --wsapi-host=127.0.0.1 --wsapi-port=8090 --observe-links --ofp-tcp-listen-port 10001 
ryu-manager ./controller/tree_controller.py --observe-links --ofp-tcp-listen-port 10001 
