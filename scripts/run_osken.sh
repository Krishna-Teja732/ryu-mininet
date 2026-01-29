#! /bin/bash
# Run this script using bash. Do not run it directly

# osken-manager ./controller/stp_controller.py --observe-links --ofp-tcp-listen-port 10001 
# osken-manager --log-file debug.log ./controller/tree_controller.py --observe-links --ofp-tcp-listen-port 10001 
# osken-manager --log-file debug.log ./controller/tree_controller_v2.py --observe-links --ofp-tcp-listen-port 10001 
osken-manager --log-file debug.log ./controller/tree_controller_v3.py --ofp-tcp-listen-port 10001 
