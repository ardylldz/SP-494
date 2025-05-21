#!/usr/bin/env python3

import asyncio
import configparser
import multiprocessing.shared_memory as shm
import json
from mavsdk import System
from mavsdk.offboard import VelocityNedYaw
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

    try:
        telemetry_shm = shm.SharedMemory(name=SHM_NAME, create=True, size=SHM_SIZE)
        telemetry_shm.buf[:2] = b'{}'
        telemetry_shm.buf[2:] = b'\x00' * (SHM_SIZE - 2)
        print(f"{GREEN}[SHM] Yeni oluşturuldu ve boş JSON yazıldı.{ENDC}")
    except FileExistsError:
        telemetry_shm = shm.SharedMemory(name=SHM_NAME)
        print(f"{YELLOW}[SHM] Mevcut alana bağlandı.{ENDC}")

    subprocess.Popen(["python3", "/home/arda/Masaüstü/listener2.py", drone_id])
    await asyncio.sleep(1)

    print(f"{BLUE}[Drone{drone_id}] Arming ve Offboard başlatılıyor...{ENDC}")
    await drone.action.arm()
    await drone.offboard.set_velocity_ned(VelocityNedYaw(0.0, 0.0, 0.0, 0.0))
    await drone.offboard.start()

    position = await drone.telemetry.position().__anext__()
    asyncio.create_task(test_maneuver(drone, position, angle_deg=135))
    await send_telemetry_forever(drone, drone_id, telemetry_shm)

async def test_maneuver(drone, current_position, angle_deg=135):
    await asyncio.sleep(30)
    print(f"{YELLOW}[TEST] 30sn sonra GOTO testi başlatılıyor...{ENDC}")
    angle_rad = math.radians(angle_deg)
    d = 20 / 6371000  # Dünya yarıçapı

    lat = current_position.latitude_deg
    lon = current_position.longitude_deg
    target_lat = math.degrees(math.radians(lat) + d * math.cos(angle_rad))
    target_lon = math.degrees(math.radians(lon) + d * math.sin(angle_rad) / math.cos(math.radians(lat)))

    try:
        await drone.action.goto_location(target_lat, target_lon, current_position.absolute_altitude_m, angle_deg)
        print(f"{CYAN}[TEST] GOTO gönderildi: {target_lat:.6f}, {target_lon:.6f}{ENDC}")
    except Exception as e:
        print(f"{RED}[TEST HATA] {e}{ENDC}")

async def send_telemetry_forever(drone, drone_id, telemetry_shm):
    start_time = datetime.now()
    while True:
        try:
            pos = await drone.telemetry.position().__anext__()
            vel = await drone.telemetry.position_velocity_ned().__anext__()
            att = await drone.telemetry.attitude_euler().__anext__()
            fm = await drone.telemetry.flight_mode().__anext__()
            bat = await drone.telemetry.battery().__anext__()
            gps = await drone.telemetry.raw_gps().__anext__()

            data = {
                "latitude": pos.latitude_deg, "longitude": pos.longitude_deg,
                "absolute_altitude": pos.absolute_altitude_m, "relative_altitude": pos.relative_altitude_m,
                "speed": math.hypot(vel.velocity.north_m_s, vel.velocity.east_m_s),
                "roll": att.roll_deg, "pitch": att.pitch_deg, "yaw": att.yaw_deg,
                "flight_mode": str(fm), "battery_percent": bat.remaining_percent * 100,
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
                print(f"{RED}[SHM] Veri çok büyük!{ENDC}")

            await apply_flocking_and_avoidance(drone_id, data, current, drone)
            await asyncio.sleep(0.2)
        except Exception as e:
            print(f"{RED}Hata: {e}{ENDC}")
            await asyncio.sleep(0.2)

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

async def apply_flocking_and_avoidance(drone_id, my, all_data, drone):
    for other_id, other in all_data.items():
        if other_id == drone_id:
            continue
        dist = calculate_distance(my["latitude"], my["longitude"], other["latitude"], other["longitude"])
        bearing = math.atan2(other["longitude"] - my["longitude"], other["latitude"] - my["latitude"])

        if dist < 10:
            print(f"{RED}🚨 Yakın! Drone{other_id} ({dist:.1f}m) → Kaçınılıyor...{ENDC}")
            angle = (bearing + math.pi) % (2 * math.pi)
            d = 10 / 6371000
            lat = math.degrees(math.radians(my["latitude"]) + d * math.cos(angle))
            lon = math.degrees(math.radians(my["longitude"]) + d * math.sin(angle) / math.cos(math.radians(my["latitude"])))
            try:
                await drone.action.goto_location(lat, lon, 10.0, math.degrees(angle))
                await asyncio.sleep(5)
            except:
                await drone.offboard.set_velocity_ned(VelocityNedYaw(math.cos(angle), math.sin(angle), 0.0, my["yaw"]))
        elif dist < 50:
            await drone.offboard.set_velocity_ned(VelocityNedYaw(0.5, 0.0, 0.0, my["yaw"]))
        else:
            await drone.offboard.set_velocity_ned(VelocityNedYaw(1.0, 0.0, 0.0, my["yaw"]))

if __name__ == "__main__":
    asyncio.run(run())

