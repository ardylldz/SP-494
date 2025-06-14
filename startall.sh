#!/bin/bash

# Başsız grafik ortamı (zorunlu değil ama uyumsuzlukları önler)
export LIBGL_ALWAYS_SOFTWARE=1

# PX4 dizinine git
cd ~/PX4-Autopilot || { echo "PX4-Autopilot dizini bulunamadı!"; exit 1; }

# QGroundControl'ü başlat (isteğe bağlı)
gnome-terminal --title="QGroundControl" -- bash -c "
cd ~/PX4-Autopilot || exit 1
export LIBGL_ALWAYS_SOFTWARE=1
./QGroundControl.AppImage
exec bash
"

sleep 5

# Drone 2 - Gazebo OLMADAN başlat
gnome-terminal --title="Drone 2 - PX4 (Headless)" -- bash -c "
HEADLESS=1 PX4_SYS_AUTOSTART=4001 PX4_SIM_MODEL=gz_x500_mono_cam ./build/px4_sitl_default/bin/px4 -i 2
exec bash
"

sleep 5

# Drone 1 - Gazebo OLMADAN başlat
gnome-terminal --title="Drone 1 - PX4 (Headless)" -- bash -c "
HEADLESS=1 PX4_SYS_AUTOSTART=4001 PX4_SIM_MODEL=gz_x500_mono_cam ./build/px4_sitl_default/bin/px4 -i 1
exec bash
"

sleep 15

# Python scriptleri başlat
gnome-terminal --title="Drone 1 - Python Kodları" -- bash -c "
python3 /home/arda/Masaüstü/Drone1_bayland.py
exec bash
"

gnome-terminal --title="Drone 2 - Python Kodları" -- bash -c "
python3 /home/arda/Masaüstü/Drone2_bayland.py
exec bash
"

