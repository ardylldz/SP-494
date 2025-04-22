#!/usr/bin/env python3

import sys
import socket
import json
import configparser
import os

if len(sys.argv) != 2:
    print("Usage: sender.py <telemetry_json>")
    sys.exit(1)

telemetry_json = sys.argv[1]

# Config dosyasını oku
config = configparser.ConfigParser()
config.read(os.path.expanduser("~/Masaüstü/drone2_config.ini"))  # Drone2 ini dosyası

udp_ip = config.get("UDP", "IP").strip()
udp_port = config.getint("UDP", "Port")

# UDP bağlantısı oluştur ve veriyi gönder
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(telemetry_json.encode(), (udp_ip, udp_port))

print(f"Telemetry verisi UDP ile gönderildi: {udp_ip}:{udp_port}")

