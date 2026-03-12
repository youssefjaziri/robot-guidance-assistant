#!/bin/bash
# source this file before running any node in this workspace:
#   source ~/ros2-test/ros_env.sh

ROS_WS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source /opt/ros/jazzy/setup.bash
source "$ROS_WS/install/setup.bash"
export PYTHONPATH="$ROS_WS/venv/lib/python3.12/site-packages:$PYTHONPATH"

# Route audio through WSLg's built-in PulseAudio socket (Windows mic via RDP)
export PULSE_SERVER=unix:/mnt/wslg/runtime-dir/pulse/native

echo "ROS2 Jazzy + vad_component environment ready."
echo "  PYTHONPATH  : venv with torch + silero_vad"
echo "  PULSE_SERVER: WSLg socket → $(PULSE_SERVER=unix:/mnt/wslg/runtime-dir/pulse/native pactl info 2>/dev/null | awk '/Default Source/{print $3}' || echo 'unavailable')"
echo ""
echo "  Nodes:"
echo "    ros2 run vad_component mic_node        # live microphone"
echo "    ros2 run vad_component fake_mic_node   # WAV file playback"
echo "    ros2 run vad_component vad_node        # speech detection"
