#!/usr/bin/env python3

import socket
import json

# Renk kodları
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
ENDC = "\033[0m"

LISTEN_PORT = 1881  # Hangi portu dinleyeceksen buraya yaz

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", LISTEN_PORT))

    print(f"{CYAN}Listener başlatıldı: 0.0.0.0:{LISTEN_PORT}{ENDC}\n")

    while True:
        data, addr = sock.recvfrom(4096)  # DOĞRU: 2 değişken alıyoruz
        try:
            message = data.decode()
            telemetry = json.loads(message)

            drone_id = telemetry.get("drone_id", "Unknown")
            udp_port = telemetry.get("udp_port", "Unknown")
            telem = telemetry.get("telemetry", {})

            print(f"\n{BLUE}--- Listener: Drone ID: {drone_id} | UDP Port: {udp_port} ---{ENDC}")
            print(f"{GREEN}Latitude:{ENDC} {telem.get('latitude', 'N/A')}")
            print(f"{GREEN}Longitude:{ENDC} {telem.get('longitude', 'N/A')}")
            print(f"{BLUE}Absolute Altitude:{ENDC} {telem.get('absolute_altitude', 'N/A')} m")
            print(f"{BLUE}Relative Altitude:{ENDC} {telem.get('relative_altitude', 'N/A')} m")
            print(f"{YELLOW}Speed:{ENDC} {telem.get('speed', 'N/A')} m/s")
            print(f"{YELLOW}Roll:{ENDC} {telem.get('roll', 'N/A')}°")
            print(f"{YELLOW}Pitch:{ENDC} {telem.get('pitch', 'N/A')}°")
            print(f"{YELLOW}Yaw:{ENDC} {telem.get('yaw', 'N/A')}°")
            print(f"{RED}Flight Mode:{ENDC} {telem.get('flight_mode', 'N/A')}")
            print(f"{GREEN}Battery:{ENDC} {telem.get('battery_percent', 'N/A')}%")
            print(f"{GREEN}Voltage:{ENDC} {telem.get('battery_voltage', 'N/A')}V")
            print(f"{CYAN}Satellites:{ENDC} {telem.get('satellites_visible', 'N/A')}")
            print(f"{CYAN}Fix Type:{ENDC} {telem.get('fix_type', 'N/A')}")
            print(f"{BLUE}Uptime:{ENDC} {telem.get('uptime', 'N/A')}")
            print(f"{CYAN}-----------------------------{ENDC}")

        except Exception as e:
            print(f"{RED}UDP Veri Okuma Hatası:{ENDC} {e}")

if __name__ == "__main__":
    main()

