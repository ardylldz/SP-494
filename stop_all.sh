#!/bin/bash

echo "🛑 Tüm drone süreçleri kapatılıyor..."

# Tüm tmux oturumlarını sonlandır
tmux kill-server 2>/dev/null
echo "✅ Tüm tmux oturumları sonlandırıldı."

# MAVSDK server süreçlerini kapat
pkill -f mavsdk_server
echo "✅ MAVSDK server kapatıldı."

# PX4 SITL süreçlerini kapat
pkill -f px4
echo "✅ PX4 süreçleri kapatıldı."

# Python logger scriptlerini kapat
pkill -f drone_logger.py
echo "✅ drone_logger.py kapatıldı."

# QGroundControl (isteğe bağlı)
pkill -f QGroundControl.AppImage && echo "✅ QGroundControl kapatıldı."

echo "🚨 Tüm sistem durduruldu."
