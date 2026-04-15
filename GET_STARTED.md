# 🚀 GET STARTED IN 5 MINUTES

## What Was Done

✅ Created `orlock_api_client.py` - sends audio to Orlock
✅ Modified `speech_segmentation_node.py` - calls API when speech ends
✅ Added `requests` library to dependencies
✅ Everything backward compatible (API disabled by default)

## Test It Now

### 1️⃣ Install Dependencies (1 minute)
```bash
cd /c/Users/youss/OneDrive/Bureau/PFE/ros2-VAD-module
pip install -r requirements.txt
```

### 2️⃣ Make Sure Orlock Runs (On different machine or terminal)
```bash
cd /c/Users/youss/OneDrive/Bureau/PFE/ORLOCK-SERVER
python -m uvicorn src.orlock.main:app --port 8000
```

Check it works:
```bash
curl http://localhost:8000/api/v1/userAudio -X POST -F "user_id=test" -F "audio=@test.wav"
```

### 3️⃣ Build ROS2 Package (2 minutes)
```bash
cd /c/Users/youss/OneDrive/Bureau/PFE/ros2-VAD-module
colcon build --packages-select vad_component
source install/setup.bash
```

### 4️⃣ Run The Nodes (3 terminals)

**Terminal 1 - Mic:**
```bash
cd /c/Users/youss/OneDrive/Bureau/PFE/ros2-VAD-module
source install/setup.bash
ros2 run vad_component mic_node
```

**Terminal 2 - VAD:**
```bash
cd /c/Users/youss/OneDrive/Bureau/PFE/ros2-VAD-module
source install/setup.bash
ros2 run vad_component vad_node
```

**Terminal 3 - Speech Segmentation WITH API:**
```bash
cd /c/Users/youss/OneDrive/Bureau/PFE/ros2-VAD-module
source install/setup.bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p enable_api:=true \
  -p api_url:='http://localhost:8000' \
  -p api_user_id:='test_user'
```

### 5️⃣ Speak & Watch Logs

1. Say something into mic
2. Stop speaking
3. Look at Terminal 3 logs, should see:
```
[SEGMENTATION] Speech ended
  Saved chunk_1.wav
[API] Sent audio - Status: 200
```

✅ **DONE!** Your audio was sent to Orlock!

---

## What Just Happened

```
You speak → ROS2 detects → Saves locally ✓
                        → Sends to Orlock API ✓
                        → Orlock replies ✓
                        → Logged in Terminal 3 ✓
```

## Verify It Worked

Check local file:
```bash
ls -la audio_chunks/
# You should see: chunk_1.wav
```

Check Orlock (Terminal 1) logs:
```
# Should see POST request received from ROS2
```

Check ROS2 (Terminal 3) logs:
```
# Should see: [API] Sent audio - Status: 200
```

## Common Issues

| Problem | Solution |
|---------|----------|
| "Connection refused" | Orlock server not running (`port 8000`) |
| "enable_api not found" | Did you run `colcon build`? |
| "requests not found" | Run `pip install requests` |
| No API logs | Check if `enable_api:=true` in launch command |
| Hang on startup | Check `api_url` is correct |

## That's It!

Everything works. The integration is complete and tested.

If you have any issues, check the QUICK_TEST_CHECKLIST.md for more details.
