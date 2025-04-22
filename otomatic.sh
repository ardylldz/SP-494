#!/bin/bash

# ~/PX4-Autopilot dizinine git
cd ~/PX4-Autopilot || { echo "Directory does not exist"; exit 1; }

# QGroundControl'u aç
gnome-terminal -- bash -c "./QGroundControl.AppImage; exec bash"

# Drone 1 PX4 başlat
gnome-terminal -- bash -c "PX4_SYS_AUTOSTART=4002 PX4_SIM_MODEL=gz_x500 ./build/px4_sitl_default/bin/px4 -i 1; exec bash"

# 15 saniye bekle (Drone1 otursun)
sleep 15

# Drone 2 PX4 başlat
gnome-terminal -- bash -c "PX4_SYS_AUTOSTART=4002 PX4_GZ_MODEL_POSE='0,100' PX4_SIM_MODEL=gz_x500 ./build/px4_sitl_default/bin/px4 -i 2; exec bash"

# 10 saniye daha bekle (Drone2 otursun)
sleep 10

# Ucak1.py başlat (Python scripti)
gnome-terminal -- bash -c "sleep 3; python3 ~/Masaüstü/ucak1.py; exec bash"

# Ucak2.py başlat (Python scripti)
gnome-terminal -- bash -c "sleep 3; python3 ~/Masaüstü/ucak2.py; exec bash"

