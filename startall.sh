#!/bin/bash

echo "🚀 Tüm drone sistemleri başlatılıyor..."

cd ~/PX4-Autopilot || { echo "Directory does not exist"; exit 1; }

gnome-terminal -- bash -c "./QGroundControl.AppImage; exec bash"

# Drone 1 için yeni terminal aç ve tmux başlat
gnome-terminal --title="Drone 1" -- bash -c "~/Masaüstü/start_drone1.sh; exec bash"
sleep 15
# Drone 2 için yeni terminal aç ve tmux başlat
gnome-terminal --title="Drone 2" -- bash -c "~/Masaüstü/start_drone2.sh; exec bash"

