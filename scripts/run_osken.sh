#! /bin/bash
# Run this script using bash. Do not run it directly

# osken-manager ./controller/stp_controller.py --observe-links --ofp-tcp-listen-port 10001 
# osken-manager --verbose --log-file debug.log ./controller/tree_controller_v2.py --observe-links --ofp-tcp-listen-port 10001 

# Python free threaded build
/home/teja/.local/share/virtualenvs/os-ken-P5uQCxPJ/bin/osken-manager --verbose --log-file debug.log ./controller/tree_controller_v2.py --observe-links --ofp-tcp-listen-port 10001 
