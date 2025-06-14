#!/usr/bin/env python3

import asyncio
import configparser
import multiprocessing.shared_memory as shm
import json
from mavsdk import System
from datetime import datetime
import os
import subprocess
import math

# Renkler
GREEN, YELLOW, RED, BLUE, CYAN, ENDC = "\033[92m", "\033[93m", "\033[91m", "\033[94m", "\033[96m", "\033[0m"
SHM_NAME = "telemetry_shared"
SHM_SIZE = 4096

async def run():
    config = configparser.ConfigParser()
    config.read(os.path.expanduser("~/Masaüstü/drone2_config.ini"))
    drone_id = config.get("swarm", "ID").strip()
    connection_string = config.get("swarm", "Connection").strip()

    print(f"{CYAN}[Drone{drone_id}] Config Okundu: {connection_string}{ENDC}")
    drone = System(port=50052)
    await drone.connect(system_address=connection_string)

    # SHM oluştur veya bağlan
    try:
        telemetry_shm = shm.SharedMemory(name=SHM_NAME, create=True, size=SHM_SIZE)
        telemetry_shm.buf[:2] = b'{}'
        telemetry_shm.buf[2:] = b'\x00' * (SHM_SIZE - 2)
        print(f"{GREEN}[SHM] Yeni oluşturuldu ve boş JSON yazıldı.{ENDC}")
    except FileExistsError:
        telemetry_shm = shm.SharedMemory(name=SHM_NAME)
        print(f"{YELLOW}[SHM] Mevcut alana bağlandı.{ENDC}")

    # Listener başlat
    subprocess.Popen(["python3", "/home/arda/Masaüstü/listener2.py", drone_id])

    # Flocking2 subprocess başlat
    subprocess.Popen(["python3", "/home/arda/Masaüstü/flocking2.py"])

    await asyncio.sleep(1)
    await send_telemetry_forever(drone, drone_id, telemetry_shm)

async def send_telemetry_forever(drone, drone_id, telemetry_shm):
    start_time = datetime.now()

    while True:
        try:
            pos = await drone.telemetry.position().__anext__()
            vel = await drone.telemetry.position_velocity_ned().__anext__()
            att = await drone.telemetry.attitude_euler().__anext__()
            fm  = await drone.telemetry.flight_mode().__anext__()
            bat = await drone.telemetry.battery().__anext__()
            gps = await drone.telemetry.raw_gps().__anext__()

            data = {
                "latitude": pos.latitude_deg,
                "longitude": pos.longitude_deg,
                "absolute_altitude": pos.absolute_altitude_m,
                "relative_altitude": pos.relative_altitude_m,
                "speed": math.hypot(vel.velocity.north_m_s, vel.velocity.east_m_s),
                "roll": att.roll_deg,
                "pitch": att.pitch_deg,
                "yaw": att.yaw_deg,
                "flight_mode": str(fm),
                "battery_percent": bat.remaining_percent * 100,
                "battery_voltage": bat.voltage_v,
                "satellites_visible": getattr(gps, "satellites_visible", "N/A"),
                "fix_type": getattr(gps, "fix_type", "N/A"),
                "uptime": f"{(datetime.now()-start_time).seconds//60:02}:{(datetime.now()-start_time).seconds%60:02}"
            }

            try:
                raw = bytes(telemetry_shm.buf[:]).split(b'\x00', 1)[0]
                current = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception as e:
                print(f"{RED}[SHM] JSON okuma hatası: {e}{ENDC}")
                current = {}

            current[drone_id] = data
            encoded = json.dumps(current).encode("utf-8")

            if len(encoded) <= SHM_SIZE:
                telemetry_shm.buf[:len(encoded)] = encoded
                telemetry_shm.buf[len(encoded):] = b'\x00' * (SHM_SIZE - len(encoded))
                print(f"{CYAN}[Drone{drone_id}] Telemetri paylaşıldı.{ENDC}")
            else:
                print(f"{RED}[SHM] Veri çok büyük! Yazılamadı.{ENDC}")

            await asyncio.sleep(0.05)

        except Exception as e:
            print(f"{RED}Hata: {e}{ENDC}")
            await asyncio.sleep(0.05)

if __name__ == "__main__":
    asyncio.run(run())

