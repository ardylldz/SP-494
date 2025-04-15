#!/bin/bash

SESSION="drone2"
MAVSDK_SERVER=~/mavsdk-server/mavsdk_server
LOGGER_SCRIPT=~/Masaüstü/drone_logger.py
PX4_DIR=~/PX4-Autopilot

DRONE_ID=2
SYS_AUTOSTART=4002
POSE_Y=100
PX4_UDP_PORT=14540
MAVSDK_GRPC_PORT=50052
MAVSDK_REMOTE_PORT=14601

# Var olan oturumu kapat (varsa)
tmux kill-session -t $SESSION 2>/dev/null

# Yeni oturumu başlat
tmux new-session -d -s $SESSION -n main

# Panel 0: PX4
tmux send-keys -t $SESSION:0.0 "cd $PX4_DIR" C-m
tmux send-keys -t $SESSION:0.0 "PX4_SIM_MODEL=gz_x500 PX4_GZ_MODEL_POSE='0,$POSE_Y,0' PX4_SYS_AUTOSTART=$SYS_AUTOSTART PX4_SIM_INSTANCE=$DRONE_ID ./build/px4_sitl_default/bin/px4 -i $DRONE_ID" C-m

# Panel 1: MAVSDK Server (aşağıya böl)
tmux split-window -v -t $SESSION
tmux send-keys -t $SESSION:0.1 "sleep 6; $MAVSDK_SERVER -p $MAVSDK_GRPC_PORT udpin://0.0.0.0:$MAVSDK_REMOTE_PORT" C-m

# Panel 2: Logger (sağ alt)
tmux split-window -h -t $SESSION:0.1
tmux send-keys -t $SESSION:0.2 "sleep 11; python3 $LOGGER_SCRIPT drone$DRONE_ID 127.0.0.1:$MAVSDK_GRPC_PORT" C-m

# Oturumu kullanıcıya bağla
tmux attach -t $SESSION

