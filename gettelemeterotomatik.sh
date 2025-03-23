#!/bin/bash

# Run the first Python script in the current terminal
python_file="/home/arda/Masaüstü/class.py"

gnome-terminal -- bash -c "python3 '$python_file'; exec bash" & 

# Open a new terminal window and run the second Python script
python_file2="/home/arda/Masaüstü/class2.py"
gnome-terminal -- bash -c "python3 '$python_file2'; exec bash"  

