# Quick Testing Checklist

## ✅ Verification Status

- ✓ **orlock_api_client.py** - Created and contains OrlockAPIClient class
- ✓ **speech_segmentation_node.py** - Modified with API parameters and _send_to_api() method
- ✓ **requirements.txt** - Added requests>=2.31.0
- ✓ **setup.py** - Added requests to install_requires
- ✓ **Documentation** - Created guides and summaries

## 🚀 Next Steps to Test

### Step 1: Install Dependencies
```bash
cd /path/to/ros2-VAD-module
pip install -r requirements.txt
```

### Step 2: Make Sure Orlock Server is Running
```bash
# In one terminal
cd /path/to/ORLOCK-SERVER
python -m uvicorn src.orlock.main:app --reload --port 8000
```

### Step 3: Set Up ROS2 Environment
```bash
cd /path/to/ros2-VAD-module
source ros_env.sh
```

### Step 4: Build the Package
```bash
colcon build --packages-select vad_component
source install/setup.bash
```

### Step 5: Run the Pipeline with API Enabled

**Terminal 1 - Mic:**
```bash
ros2 run vad_component mic_node --ros-args -p device:=pulse
```

**Terminal 2 - VAD:**
```bash
ros2 run vad_component vad_node
```

**Terminal 3 - Speech Segmentation with API:**
```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p enable_api:=true \
  -p api_url:='http://localhost:8000' \
  -p api_user_id:='test_user' \
  -p verbose:=true
```

### Step 6: Speak into Microphone
- Say something (speech will be detected)
- Stop speaking (silence threshold triggers save)
- Check logs for:
  ```
  [API] Sent audio - Status: 200
  ```

### Step 7: Verify Results
```bash
# Check local files saved
ls -la audio_chunks/

# Check Orlock logs
# Should see POST request from ROS2 node
```

## ⚡ Quick Test (Without ROS2)

If you just want to test the API client:

```python
import numpy as np
from vad_component.orlock_api_client import OrlockAPIClient

# Create dummy audio
audio = np.sin(np.linspace(0, 1, 16000)) * 0.3

# Send to Orlock
client = OrlockAPIClient('http://localhost:8000')
response = client.send_audio(
    audio_data=audio,
    user_id='test',
    sample_rate=16000
)

print(response)
```

## 📊 What to Look For

| Component | Success Indicator |
|-----------|-------------------|
| API Client | No import errors |
| Dependencies | `pip install` completes |
| Orlock Server | Returns `200 OK` responses |
| ROS2 Nodes | All nodes start without errors |
| API Integration | `[API] Sent audio - Status: 200` in logs |
| Fallback | Local files still save if API fails |

## 🐛 Common Issues

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError` | Did you `source ros_env.sh`? |
| `Connection refused` | Orlock server not running |
| `requests not found` | `pip install requests` |
| `enable_api parameter not found` | Did you rebuild? `colcon build` |

## ✨ Ready!

The implementation is complete and ready to test. Follow the steps above to verify everything works!
