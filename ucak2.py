#!/usr/bin/env python3

import asyncio
import configparser
from mavsdk import System
from datetime import datetime
import os
import socket
import json
import subprocess

# Renk Kodları
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
ENDC = "\033[0m"

async def run():
    config = configparser.ConfigParser()
    config.read(os.path.expanduser("~/Masaüstü/drone2_config.ini"))  # Drone2 için config dosyası

    drone_id = config.get("swarm", "ID").strip()
    connection_string = config.get("swarm", "Connection").strip()

    print(f"{CYAN}[Drone{drone_id}] Config Okundu -> Connection: {connection_string}{ENDC}")

    drone = System()
    await drone.connect(system_address=connection_string)

    # UDP dinleme portunu configten oku
    udp_ip = config.get("UDP", "IP").strip()
    udp_port = config.getint("UDP", "Port")

    # Listener görevini başlat
    asyncio.create_task(listen_udp(udp_port))

    # Küçük bir bekleme (listener hazır olsun)
    await asyncio.sleep(1)

    # Sürekli telemetry verisi gönder
    await send_telemetry_forever(drone, udp_ip, udp_port, drone_id)

async def send_telemetry_forever(drone, udp_ip, udp_port, drone_id):
    start_time = datetime.now()

    while True:
        current_time = datetime.now()

        try:
            position = await drone.telemetry.position().__anext__()
            latitude = position.latitude_deg
            longitude = position.longitude_deg
            abs_altitude = position.absolute_altitude_m
            rel_altitude = position.relative_altitude_m

            pos_vel = await drone.telemetry.position_velocity_ned().__anext__()
            velocity = pos_vel.velocity
            speed = (velocity.north_m_s**2 + velocity.east_m_s**2)**0.5

            attitude = await drone.telemetry.attitude_euler().__anext__()
            roll = attitude.roll_deg
            pitch = attitude.pitch_deg
            yaw = attitude.yaw_deg

            flight_mode = await drone.telemetry.flight_mode().__anext__()
            flight_mode_str = str(flight_mode)

            battery = await drone.telemetry.battery().__anext__()
            battery_percentage = battery.remaining_percent * 100
            battery_voltage = battery.voltage_v

            gps = await drone.telemetry.raw_gps().__anext__()
            satellites = getattr(gps, "satellites_visible", "N/A")
            fix_type = getattr(gps, "fix_type", "N/A")

            uptime = current_time - start_time
            minutes, seconds = divmod(uptime.seconds, 60)

            telemetry_data = {
                "drone_id": drone_id,
                "udp_port": udp_port,
                "telemetry": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "absolute_altitude": abs_altitude,
                    "relative_altitude": rel_altitude,
                    "speed": speed,
                    "roll": roll,
                    "pitch": pitch,
                    "yaw": yaw,
                    "flight_mode": flight_mode_str,
                    "battery_percent": battery_percentage,
                    "battery_voltage": battery_voltage,
                    "satellites_visible": satellites,
                    "fix_type": fix_type,
                    "uptime": f"{minutes:02}:{seconds:02}"
                }
            }

            telemetry_json = json.dumps(telemetry_data)

            # Telemetry'yi subprocess ile gönder
            subprocess.Popen(["python3", "/home/arda/Masaüstü/sender.py", telemetry_json])

            await asyncio.sleep(1.5)  # 1.5 saniyede bir yeni telemetry verisi gönder

        except Exception as e:
            print(f"{RED}Telemetry Gönderim Hatası:{ENDC} {e}")
            await asyncio.sleep(1.5)

async def listen_udp(listen_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", listen_port))

    print(f"{YELLOW}[Listener] Başlatıldı: 0.0.0.0:{listen_port}{ENDC}\n")

    while True:
        data, addr = await asyncio.get_event_loop().run_in_executor(None, lambda: sock.recvfrom(4096))
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
    asyncio.run(run())

