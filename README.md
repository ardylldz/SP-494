If tmux terminal is not installed, you can install it by typing apt-get install tmux In addition to this, I also add the mavsdk download commands

sudo apt-get update
sudo apt-get install build-essential cmake git
mkdir build
cd build
cmake -DBUILD_SHARED_LIBS=ON -DBUILD_MAVSDK_SERVER=ON ..
make mavsdk_server -j$(nproc)
ls -l src/mavsdk_server/mavsdk_server

cp ~/miniconda3/envs/sp494/lib/python3.13/site-packages/mavsdk/bin/mavsdk_server ~/mavsdk-server/mavsdk_server
chmod +x ~/mavsdk-server/mavsdk_server
