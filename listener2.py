#!/usr/bin/env python3

import time
import multiprocessing.shared_memory as shm
import json
import sys
import threading

# Renk Kodları
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
ENDC = "\033[0m"

SHM_NAME = "telemetry_shared"
SHM_SIZE = 4096

# Shared Memory okuma fonksiyonu
def read_shared_memory(shm_name):
    try:
        memory = shm.SharedMemory(name=shm_name)
        raw_bytes = bytes(memory.buf[:])
        # JSON verisinin doğrudan okunması
        decoded = raw_bytes.decode('utf-8').split('\x00')[0]
        telemetry = json.loads(decoded)
        return telemetry
    except FileNotFoundError:
        print(f"{RED}[Listener] {shm_name} bulunamadı!{ENDC}")
        return None
    except json.JSONDecodeError:
        print(f"{RED}[Listener] JSON Decode hatası!{ENDC}")
        return None

# Telemetri verilerinin hızlıca işlenmesi
def print_telemetry(telem):
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

# Ana işlem fonksiyonu
def main(my_id):
    print(f"{YELLOW}[ListenerDrone] Drone{my_id} ➔ {SHM_NAME} shared memory dinliyor...{ENDC}")

    # Shared Memory kontrolü ve açılması
    try:
        shm.SharedMemory(name=SHM_NAME)
    except FileNotFoundError as e:
        print(f"{RED}Shared Memory açma hatası: {e}{ENDC}")
        return

    # Hızlı veri okuma işlemi
    while True:
        telemetry_all = read_shared_memory(SHM_NAME)

        if telemetry_all:
            if my_id not in telemetry_all:
                print(f"{RED}[Uyarı] Drone{my_id} verisi shared memory içinde yok.{ENDC}")

            # Diğer drone'ların verilerini hızlıca ekrana basma
            for drone_id, telem in telemetry_all.items():
                if drone_id != my_id:
                    print(f"\n{CYAN}--- Gelen Telemetri (Drone {drone_id}) ---{ENDC}")
                    print_telemetry(telem)

        # Veri okuma sıklığını artırmak için 0.1 saniye
        time.sleep(0.1)

# Ana fonksiyonun çalışması
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"{RED}Kullanım: python3 listener2.py <my_drone_id>{ENDC}")
        sys.exit(1)

    my_id = sys.argv[1]
    # Ana fonksiyonu çalıştırmak için ayrı bir thread oluşturuluyor
    listener_thread = threading.Thread(target=main, args=(my_id,))
    listener_thread.daemon = True
    listener_thread.start()

    # Thread'in devam etmesini sağlamak
    listener_thread.join()
