#!/usr/bin/env python3

import asyncio
import json
import math
import multiprocessing.shared_memory as shm
from mavsdk import System

SHM_NAME = "telemetry_shared"
SHM_SIZE = 4096
SEE_RADIUS = 30
COHESION_WEIGHT = 0.4
SEPARATION_WEIGHT = 1.2

MY_ID = "2"
GPRC_PORT = 50052

def meter_distance(lat1, lon1, lat2, lon2):
    dx = (lon2 - lon1) * 111320 * math.cos(math.radians(lat1))
    dy = (lat2 - lat1) * 110540
    return math.hypot(dx, dy), dx, dy

async def flock():
    drone = System(port=GPRC_PORT)
    await drone.connect(system_address=f"udp://:{14540 + int(MY_ID)}")
    print(f"[Flocking2] Drone{MY_ID} bağlandı.")

    memory = shm.SharedMemory(name=SHM_NAME)

    while True:
        try:
            raw = bytes(memory.buf[:]).split(b'\x00', 1)[0]
            data_all = json.loads(raw.decode('utf-8'))

            if MY_ID not in data_all or "1" not in data_all:
                await asyncio.sleep(0.2)
                continue

            me = data_all[MY_ID]
            other = data_all["1"]

            dist, dx, dy = meter_distance(
                me["latitude"], me["longitude"],
                other["latitude"], other["longitude"]
            )

            if dist > SEE_RADIUS:
                await asyncio.sleep(1)
                continue

            sep_x, sep_y = -dx, -dy
            coh_x = (other["longitude"] - me["longitude"]) * 111320
            coh_y = (other["latitude"] - me["latitude"]) * 110540

            total_dx = SEPARATION_WEIGHT * sep_x + COHESION_WEIGHT * coh_x
            total_dy = SEPARATION_WEIGHT * sep_y + COHESION_WEIGHT * coh_y

            target_lon = me["longitude"] + total_dx / 111320
            target_lat = me["latitude"] + total_dy / 110540

            await drone.action.goto_location(
                target_lat, target_lon, me["absolute_altitude"], 0
            )

            print(f"[Flocking2] Drone2 yönlendirildi ➤ {target_lat:.6f}, {target_lon:.6f}")

        except Exception as e:
            print(f"[Flocking2] Hata: {e}")
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(flock())
