# Speech Segmentation Node - Usage Guide

## Overview

The `SpeechSegmentationNode` is a ROS2 node that:
- Subscribes to VAD (Voice Activity Detection) results
- Subscribes to raw audio frames
- Implements a state machine to detect speech segments
- Buffers audio during speech
- Saves audio chunks as .wav files when speech ends

## Architecture

The node maintains a 3-state finite state machine:

```
        speech detected
        ↓
    IDLE ──────→ RECORDING
         ↑           │
         │           │ no speech detected
         │           ↓
         └─── STOPPING ──→ silence threshold exceeded → back to IDLE
              ↑
              └─ speech resumed → back to RECORDING
```

### State Descriptions

- **IDLE**: Waiting for speech to be detected
- **RECORDING**: Speech detected, buffering audio frames
- **STOPPING**: Silence detected, waiting for silence threshold to be exceeded

## Dependencies

```bash
python3 -m pip install -r requirements.txt
```

## Setup on Another PC (Recommended)

### 1) Install system prerequisites

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip ffmpeg libsndfile1 portaudio19-dev
```

### 2) Clone and enter workspace

```bash
git clone <your-repo-url>
cd ros2-VAD-module
```

### 3) Create and activate virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4) Build the ROS package

```bash
colcon build --packages-select vad_component
```

### 5) Prepare terminal environment before running nodes

```bash
source ros_env.sh
```

`ros_env.sh` now auto-detects both `venv` and `.venv` and adds the virtualenv site-packages path dynamically.

## Topic Subscriptions

| Topic | Type | Description |
|-------|------|-------------|
| `/speech_detected` | `std_msgs/Bool` | VAD output (from vad_node) |
| `/audio/raw` | `std_msgs/Int16MultiArray` | Raw PCM audio frames (from mic_node) |

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `output_dir` | string | `./audio_chunks` | Directory to save audio chunks |
| `silence_threshold` | double | `0.5` | Silence duration before stopping recording (seconds) |
| `min_duration` | double | `0.3` | Minimum segment duration to save (seconds) |
| `verbose` | bool | `False` | Enable detailed logging of state transitions and frame stats |

## File Output

Audio chunks are saved as:
- `chunk_1.wav`
- `chunk_2.wav`
- `chunk_N.wav`

With properties:
- **Sample Rate**: 16,000 Hz
- **Format**: 16-bit PCM (float32 normalized to [-1, 1])
- **Channels**: Mono

## Running the Node

### Build the package
```bash
cd /home/youssef/PFE/ros2-VAD-module
colcon build --packages-select vad_component
source ros_env.sh
```

### Run the full pipeline
```bash
# Terminal 1: Start the microphone node
ros2 run vad_component mic_node --ros-args -p device:=pulse

# Terminal 2: Start the VAD node
ros2 run vad_component vad_node

# Terminal 3: Start the speech segmentation node
ros2 run vad_component speech_segmentation_node --ros-args -p output_dir:=./audio_chunks -p verbose:=true
```

### With custom parameters
```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p output_dir:=/tmp/speech_chunks \
  -p silence_threshold:=0.8 \
  -p min_duration:=0.5 \
  -p verbose:=true
```

## Logging Output

The node prints informative messages:

```
[INFO] [speech_segmentation_node]: SpeechSegmentationNode ready
  output_dir=/home/user/audio_chunks
  silence_threshold=0.5s
  min_duration=0.3s
  verbose=False

[INFO] [speech_segmentation_node]: [SEGMENTATION] Speech started

[INFO] [speech_segmentation_node]: [SEGMENTATION] Speech ended
  Saved chunk_1.wav
  Duration: 2.45s
  Samples: 39200
```

## Processing Flow Example

1. User speaks "Hello world"
   - `speech_detected` → true
   - State: IDLE → RECORDING
   - Logs: "Speech started"
   - Audio frames buffered

2. User stops speaking
   - `speech_detected` → false
   - State: RECORDING → STOPPING
   - Waits 0.5s for silence threshold

3. Silence threshold exceeded
   - Audio buffer saved as `chunk_1.wav`
   - State: STOPPING → IDLE
   - Logs: "Speech ended" + duration info

## Edge Cases Handled

- **Short segments**: Segments shorter than `min_duration` are skipped with a warning
- **Speech resumption**: If speech resumes during STOPPING state, it transitions back to RECORDING
- **Empty buffer**: Safeguard against saving empty audio
- **File I/O errors**: Exceptions are caught and logged

## Integration with APIs

The node is designed to be easily extended. To send audio to an API:

1. Replace the `_save_segment()` method to:
   - Keep the buffering logic as-is
   - Add API call instead of (or in addition to) file saving
   - Example:
     ```python
     def _save_segment(self) -> None:
         audio_data = np.concatenate(self._audio_buffer)
         # ... validation ...

         # Save locally AND send to API
         filepath = self._save_to_file(audio_data)
         self._send_to_api(audio_data)  # Add this method
     ```

## Performance Notes

- **Latency**: Minimal (~32ms per frame at 16kHz with 512-sample chunks)
- **Memory**: Scales with segment length (e.g., 2-second segment ≈ 128KB)
- **CPU**: Low overhead (just concatenation and file writing)

## Troubleshooting

**No chunks being saved:**
- Check `/speech_detected` topic: `ros2 topic echo /speech_detected`
- Check `/audio/raw` topic: `ros2 topic echo /audio/raw`
- Ensure VAD threshold is appropriate
- Check output directory permissions

**Files not being saved:**
- Verify `output_dir` exists and is writable
- Enable `verbose=true` to see detailed logs
- Check disk space

**Sample rate mismatches:**
- Ensure all nodes use the same sample rate (16,000 Hz)
- Check with: `ros2 topic list -v`
