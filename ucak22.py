#!/usr/bin/env python3

import asyncio
import configparser
import multiprocessing.shared_memory as shm
import json
from mavsdk import System
from mavsdk.offboard import VelocityNedYaw
import os
import math
from datetime import datetime

GREEN, YELLOW, RED, BLUE, CYAN, ENDC = "\033[92m", "\033[93m", "\033[91m", "\033[94m", "\033[96m", "\033[0m"
SHM_NAME = "telemetry_shared"
SHM_SIZE = 4096

async def telemetry_collector(drone, drone_id, telemetry_shm):
    """
    Tüm telemetry streamlerini paralel takip eder, shared memory'ye yazar.
    """
    last = {}
    lock = asyncio.Lock()

    async def update_position():
        async for pos in drone.telemetry.position():
            async with lock:
                last['latitude'] = pos.latitude_deg
                last['longitude'] = pos.longitude_deg
                last['absolute_altitude'] = pos.absolute_altitude_m

    async def update_velocity():
        async for vel in drone.telemetry.position_velocity_ned():
            async with lock:
                last['speed'] = math.hypot(vel.velocity.north_m_s, vel.velocity.east_m_s)

    async def update_attitude():
        async for att in drone.telemetry.attitude_euler():
            async with lock:
                last['roll'] = att.roll_deg
                last['pitch'] = att.pitch_deg
                last['yaw'] = att.yaw_deg

    async def update_flight_mode():
        async for fm in drone.telemetry.flight_mode():
            async with lock:
                last['flight_mode'] = str(fm)

    async def update_battery():
        async for bat in drone.telemetry.battery():
            async with lock:
                last['battery_percent'] = bat.remaining_percent * 100

    async def update_gps():
        async for gps in drone.telemetry.raw_gps():
            async with lock:
                last['satellites_visible'] = getattr(gps, "satellites_visible", "N/A")

    # SHM'ye güvenli yazıcı
    async def publisher():
        while True:
            async with lock:
                try:
                    raw = bytes(telemetry_shm.buf[:]).split(b'\x00', 1)[0]
                    # --- JSON bozuksa temizle ---
                    try:
                        current = json.loads(raw.decode("utf-8")) if raw else {}
                    except Exception:
                        current = {}
                except Exception:
                    current = {}

                current[drone_id] = last.copy()
                encoded = json.dumps(current).encode("utf-8")
                if len(encoded) < SHM_SIZE:
                    telemetry_shm.buf[:len(encoded)] = encoded
                    telemetry_shm.buf[len(encoded):] = b'\x00' * (SHM_SIZE - len(encoded))
                else:
                    print(f"{RED}[SHM] Veri büyük!{ENDC}")
            await asyncio.sleep(0.01)

    await asyncio.gather(
        update_position(),
        update_velocity(),
        update_attitude(),
        update_flight_mode(),
        update_battery(),
        update_gps(),
        publisher()
    )

async def flocking_controller(drone_id, drone, telemetry_shm):
    ESCAPE_DISTANCE = 10
    ESCAPE_SPEED = 3.5   # Daha hızlı kaçınma
    FLOCK_SPEED = 1.2    # Flocking sırasında biraz daha hızlı
    NORMAL_SPEED = 0.8
    while True:
        try:
            # SHM'den okuma işlemi
            for _ in range(3):  # 3 denemeye kadar retry
                try:
                    raw = bytes(telemetry_shm.buf[:]).split(b'\x00', 1)[0]
                    all_data = json.loads(raw.decode("utf-8")) if raw else {}
                    break
                except Exception as e:
                    all_data = {}
                    await asyncio.sleep(0.01)
            else:
                print(f"{RED}[Flocking SHM Hatası]: JSON okunamıyor!{ENDC}")
                await asyncio.sleep(0.02)
                continue

            my = all_data.get(drone_id)
            if not my:
                await asyncio.sleep(0.02)
                continue

            my_lat, my_lon, my_yaw = my.get("latitude"), my.get("longitude"), my.get("yaw")

            others = [d for oid, d in all_data.items() if oid != drone_id and "latitude" in d]
            if not others:
                await drone.offboard.set_velocity_ned(VelocityNedYaw(NORMAL_SPEED, 0.0, 0.0, my_yaw or 0))
                await asyncio.sleep(0.02)
                continue

            nearest = min(
                others,
                key=lambda o: calculate_distance(my_lat, my_lon, o["latitude"], o["longitude"])
            )
            dist = calculate_distance(my_lat, my_lon, nearest["latitude"], nearest["longitude"])

            if dist < ESCAPE_DISTANCE:
                print(f"{RED}🚨 Kaçınma: {dist:.1f}m{ENDC}")
                # Kaçınma vektörü ile hızlı çekilme
                angle = math.atan2(my_lon - nearest["longitude"], my_lat - nearest["latitude"])
                vx = ESCAPE_SPEED * math.cos(angle)
                vy = ESCAPE_SPEED * math.sin(angle)
                await drone.offboard.set_velocity_ned(VelocityNedYaw(vx, vy, 0.0, my_yaw or 0))
                await asyncio.sleep(0.4)
            elif ESCAPE_DISTANCE <= dist <= 30:
                print(f"{CYAN}🔄 Flocking Aktif: {dist:.1f}m{ENDC}")
                sep_angle = math.atan2(my_lon - nearest["longitude"], my_lat - nearest["latitude"])
                ali_angle = math.radians(nearest.get("yaw", 0))
                coh_angle = math.atan2(nearest["longitude"] - my_lon, nearest["latitude"] - my_lat)

                vx = 2 * math.cos(sep_angle) + 1 * math.cos(ali_angle) + 1 * math.cos(coh_angle)
                vy = 2 * math.sin(sep_angle) + 1 * math.sin(ali_angle) + 1 * math.sin(coh_angle)
                final_yaw = math.degrees(math.atan2(vy, vx))
                await drone.offboard.set_velocity_ned(VelocityNedYaw(FLOCK_SPEED, 0.0, 0.0, final_yaw))
                await asyncio.sleep(0.15)
            else:
                print(f"{YELLOW}🟢 Serbest uçuş: {dist:.1f}m{ENDC}")
                await drone.offboard.set_velocity_ned(VelocityNedYaw(NORMAL_SPEED, 0.0, 0.0, my_yaw or 0))
                await asyncio.sleep(0.25)
        except Exception as e:
            print(f"{RED}[Flocking Controller Hatası]: {e}{ENDC}")
            await asyncio.sleep(0.05)

def calculate_distance(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return 1e9
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

async def run():
    config = configparser.ConfigParser()
    config.read(os.path.expanduser("~/Masaüstü/drone2_config.ini"))
    drone_id = config.get("swarm", "ID").strip()
    connection_string = config.get("swarm", "Connection").strip()

    print(f"{CYAN}[Drone{drone_id}] Config Okundu: {connection_string}{ENDC}")
    drone = System(port=50052)
    await drone.connect(system_address=connection_string)

    # SHM aç
    try:
        telemetry_shm = shm.SharedMemory(name=SHM_NAME, create=True, size=SHM_SIZE)
        telemetry_shm.buf[:2] = b'{}'
        telemetry_shm.buf[2:] = b'\x00' * (SHM_SIZE - 2)
        print(f"{GREEN}[SHM] Yeni oluşturuldu ve boş JSON yazıldı.{ENDC}")
    except FileExistsError:
        telemetry_shm = shm.SharedMemory(name=SHM_NAME)
        print(f"{YELLOW}[SHM] Mevcut alana bağlandı.{ENDC}")

    print(f"{BLUE}[Drone{drone_id}] Arming ve Offboard başlatılıyor...{ENDC}")
    await drone.action.arm()
    await drone.offboard.set_velocity_ned(VelocityNedYaw(0.0, 0.0, 0.0, 0.0))
    await drone.offboard.start()

    await asyncio.gather(
        telemetry_collector(drone, drone_id, telemetry_shm),
        flocking_controller(drone_id, drone, telemetry_shm)
    )

if __name__ == "__main__":
    asyncio.run(run())

