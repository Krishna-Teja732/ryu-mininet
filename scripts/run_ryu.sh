#! /bin/bash

# Run this script using bash. Do not run it directly


ryu-manager ./controller/ryu_stp_controller_v2.py ryu.app.rest_topology ryu.app.ofctl_rest --wsapi-host=127.0.0.1 --wsapi-port=8090 --observe-links --ofp-tcp-listen-port 10001 
