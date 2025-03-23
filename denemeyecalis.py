import asyncio
from mavsdk import System
from datetime import datetime

# Drone bağlantıları için adres listesi
drone_addresses = ["udp://:14542", "udp://:14543"]  # Farklı portlar kullanarak birden fazla drone

async def get_telemetry(drone_id, system_address, filename):
    drone = System()
    await drone.connect(system_address=system_address)

    print(f"{drone_id} - Bağlantı kuruluyor...")
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print(f"{drone_id} - Bağlantı başarılı!")
            break

    # Dosya yazma işlemi için açık tutma
    with open(filename, "w") as file:
        # Sonsuz döngü ile sürekli veri çekme
        while True:
            # Konum bilgisi
            async for position in drone.telemetry.position():
                altitude = position.relative_altitude_m  # İrtifa (m)
                latitude = position.latitude_deg
                longitude = position.longitude_deg
                file.write(f"{drone_id} - İrtifa: {altitude} m, Konum: {latitude}, {longitude}\n")
                break

            # Hız bilgisi
            async for velocity in drone.telemetry.velocity_ned():
                speed = (velocity.north_m_s**2 + velocity.east_m_s**2)**0.5  # Yatay hız (m/s)
                file.write(f"{drone_id} - Hız: {speed:.2f} m/s\n")
                break

            # Uçuş modunu kontrol etme
            async for flight_mode in drone.telemetry.flight_mode():
                file.write(f"{drone_id} - Uçuş Modu: {flight_mode}\n")
                break

            # Batarya bilgisini al
            async for battery in drone.telemetry.battery():
                battery_percentage = battery.remaining_percent  # Batarya yüzdesi
                battery_voltage = battery.voltage_v  # Batarya voltajı
                file.write(f"{drone_id} - Batarya: %{battery_percentage}\n")
                break
            
            # Saat bilgisi ekleme
            current_time = datetime.now().strftime("%H:%M:%S")  
            file.write(f"{drone_id} - Zaman: {current_time}\n")
            file.write("\n")  # Veriler arasında boşluk bırakmak için

            # Döngüde biraz bekleme eklemek verimli olacaktır (örneğin, 1 saniye)
            await asyncio.sleep(1)  # Veriyi her saniye güncelle

async def main():
    # Birden fazla drone'ı başlatmak için görevler oluştur
    tasks = []
    for i, address in enumerate(drone_addresses, start=1):
        drone_id = f"Drone-{i}"
        filename = f"droneinfo{i}.txt"  # Her drone için farklı dosya ismi
        tasks.append(get_telemetry(drone_id, address, filename))

    # Tüm görevleri eşzamanlı olarak çalıştır
    await asyncio.gather(*tasks)

# Bu fonksiyonu çalıştır
asyncio.run(main())
