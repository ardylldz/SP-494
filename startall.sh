#!/bin/bash

echo -e "\033[96m🚁 Koçovalı Mithat - 2 PX4 Drone başlatılıyor (Gazebo yok)...\033[0m"

# Grafik uyumluluğu için ortam değişkeni
export LIBGL_ALWAYS_SOFTWARE=1

# PX4 dizinine git
cd ~/PX4-Autopilot || { echo "❌ PX4-Autopilot dizini bulunamadı!"; exit 1; }

# QGroundControl'ü başlat
gnome-terminal -- bash -c "
cd ~/PX4-Autopilot || { echo 'PX4-Autopilot dizini bulunamadı!'; exit 1; }
export LIBGL_ALWAYS_SOFTWARE=1
./QGroundControl.AppImage
exec bash
"

# QGC otursun
sleep 10
# Drone 1 - PX4 başlat (pozisyon: 0,0)
gnome-terminal --title="Drone 1 - PX4 Simülasyonu" -- bash -c "
PX4_SYS_AUTOSTART=4001 \
PX4_SIM_MODEL=gz_x500_mono_cam \
PX4_GZ_MODEL_POSE='0,0,0,0,0,0' \
HEADLESS=1 \
./build/px4_sitl_default/bin/px4 -i 1
exec bash
"
sleep 10
# Drone 2 - PX4 başlat (pozisyon: 0,10)
gnome-terminal --title="Drone 2 - PX4 Simülasyonu" -- bash -c "
PX4_SYS_AUTOSTART=4001 \
PX4_SIM_MODEL=gz_x500_mono_cam \
PX4_GZ_MODEL_POSE='0,100,0,0,0,0' \
HEADLESS=1 \
./build/px4_sitl_default/bin/px4 -i 2
exec bash
"

# PX4 otursun
sleep 30

# Drone 1 - Python Kodları
gnome-terminal --title="Drone 1 - Python Kodları" -- bash -c "
python3 /home/arda/Masaüstü/Drone1_bayland.py
exec bash
"

# Drone 2 - Python Kodları
gnome-terminal --title="Drone 2 - Python Kodları" -- bash -c "
python3 /home/arda/Masaüstü/Drone2_bayland.py
exec bash
"



