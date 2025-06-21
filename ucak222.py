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
    TARGET_DISTANCE = 15   # Sabit mesafe hedefi (kohezyon)
    COHESION_SPEED = 1.2   # Kohezyon/sabit mesafe yaklaşma hızı
    ESCAPE_SPEED = 3.5     # Kaçınma hızı
    NORMAL_SPEED = 0.8     # Serbest uçuş hızı

    while True:
        try:
            # SHM'den oku
            for _ in range(3):
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
                await asyncio.sleep(0.05)
                continue

            # En yakın drone
            nearest = min(
                others,
                key=lambda o: calculate_distance(my_lat, my_lon, o["latitude"], o["longitude"])
            )
            dist = calculate_distance(my_lat, my_lon, nearest["latitude"], nearest["longitude"])
            yaw_to_other = math.degrees(math.atan2(nearest["longitude"] - my_lon, nearest["latitude"] - my_lat))

            if dist < ESCAPE_DISTANCE:
                print(f"{RED}🚨 Kaçınma: {dist:.1f}m{ENDC}")
                # Kaçınma vektörü
                angle = math.atan2(my_lon - nearest["longitude"], my_lat - nearest["latitude"])
                vx = ESCAPE_SPEED * math.cos(angle)
                vy = ESCAPE_SPEED * math.sin(angle)
                await drone.offboard.set_velocity_ned(VelocityNedYaw(vx, vy, 0.0, my_yaw or 0))
                await asyncio.sleep(0.2)

            elif ESCAPE_DISTANCE <= dist < (TARGET_DISTANCE - 1):
                # 10-14m: Uzaklaş (kohezyon - sabit mesafeye çekil)
                print(f"{CYAN}⬅️ Kohezyon (Uzaklaş): {dist:.1f}m{ENDC}")
                angle = math.atan2(my_lon - nearest["longitude"], my_lat - nearest["latitude"])
                vx = COHESION_SPEED * math.cos(angle)
                vy = COHESION_SPEED * math.sin(angle)
                await drone.offboard.set_velocity_ned(VelocityNedYaw(vx, vy, 0.0, yaw_to_other))
                await asyncio.sleep(0.15)

            elif (TARGET_DISTANCE - 1) <= dist <= (TARGET_DISTANCE + 1):
                # 14-16m: Sabit tut
                print(f"{GREEN}✅ Mesafe Sabit: {dist:.1f}m{ENDC}")
                await drone.offboard.set_velocity_ned(VelocityNedYaw(0.0, 0.0, 0.0, my_yaw or 0))
                await asyncio.sleep(0.15)

            elif dist > (TARGET_DISTANCE + 1):
                # 16m üstü: yaklaş (kohezyon)
                print(f"{BLUE}➡️ Kohezyon (Yaklaş): {dist:.1f}m{ENDC}")
                angle = math.atan2(nearest["longitude"] - my_lon, nearest["latitude"] - my_lat)
                vx = COHESION_SPEED * math.cos(angle)
                vy = COHESION_SPEED * math.sin(angle)
                await drone.offboard.set_velocity_ned(VelocityNedYaw(vx, vy, 0.0, yaw_to_other))
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
    created_new_shm = False
    try:
        telemetry_shm = shm.SharedMemory(name=SHM_NAME, create=True, size=SHM_SIZE)
        created_new_shm = True
        telemetry_shm.buf[:2] = b'{}'
        telemetry_shm.buf[2:] = b'\x00' * (SHM_SIZE - 2)
        print(f"{GREEN}[SHM] Yeni oluşturuldu ve boş JSON yazıldı.{ENDC}")
    except FileExistsError:
        telemetry_shm = shm.SharedMemory(name=SHM_NAME)
        print(f"{YELLOW}[SHM] Mevcut alana bağlandı.{ENDC}")

    try:
        print(f"{BLUE}[Drone{drone_id}] Arming başlatılıyor...{ENDC}")
        await asyncio.sleep(4)
        await drone.action.arm()
        await asyncio.sleep(4)  # Arming sonrası kısa bekleme

        print(f"{BLUE}[Drone{drone_id}] Takeoff başlatılıyor...{ENDC}")
        await drone.action.takeoff()
        await asyncio.sleep(22)  # Takeoff sonrası drone havalansın

        print(f"{BLUE}[Drone{drone_id}] Offboard başlatılıyor...{ENDC}")
        await drone.offboard.set_velocity_ned(VelocityNedYaw(0.0, 0.0, 0.0, 0.0))
        await drone.offboard.start()

        await asyncio.gather(
            telemetry_collector(drone, drone_id, telemetry_shm),
            flocking_controller(drone_id, drone, telemetry_shm)
        )
    finally:
        print(f"{CYAN}[SHM] Temizleniyor...{ENDC}")
        telemetry_shm.close()
        if created_new_shm:
            try:
                telemetry_shm.unlink()
            except FileNotFoundError:
                pass
        print(f"{GREEN}[SHM] Kapandı ve silindi.{ENDC}")

if __name__ == "__main__":
    asyncio.run(run())

