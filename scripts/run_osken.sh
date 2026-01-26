#! /bin/bash
# Run this script using bash. Do not run it directly

# osken-manager ./controller/stp_controller.py --observe-links --ofp-tcp-listen-port 10001 
osken-manager ./controller/tree_controller.py --observe-links --ofp-tcp-listen-port 10001 
