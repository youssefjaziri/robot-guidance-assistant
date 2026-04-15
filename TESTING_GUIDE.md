# Testing Guide - Orlock API Integration

## 1. Prerequisites Check

Before testing, ensure:
- Orlock server is running on `http://localhost:8000`
- ROS2 environment is set up
- Dependencies installed: `pip install -r requirements.txt`

## 2. Test 1: Check API Endpoint

```bash
curl -X POST http://localhost:8000/api/v1/userAudio \
  -F "user_id=test" \
  -F "audio=@test_audio.wav" \
  -F "temperature=0.2"
```

Expected response:
```json
{
  "user_id": "test",
  "user_text": "[TRANSCRIPTION_PLACEHOLDER] file saved at ...",
  "llm_response": "AI response here"
}
```

## 3. Test 2: Test API Client Directly

```bash
cd /path/to/ros2-VAD-module
python test_orlock_client.py
```

Output should show:
```
Testing OrlockAPIClient...
  Audio: 16000 samples at 16000 Hz
  Duration: 1.00s

Response:
  ✓ Success! Status: 200
  LLM Response: ...
```

## 4. Test 3: Test with ROS2 Nodes

### Terminal 1 - Start Orlock Server
```bash
cd /path/to/ORLOCK-SERVER
python -m uvicorn src.orlock.main:app --host 0.0.0.0 --port 8000
```

### Terminal 2 - Start Fake Mic (for testing)
```bash
cd /path/to/ros2-VAD-module
source ros_env.sh
ros2 run vad_component fake_mic_node --ros-args -p audio_file:='test.wav'
```

### Terminal 3 - Start VAD Node
```bash
source ros_env.sh
ros2 run vad_component vad_node
```

### Terminal 4 - Start Speech Segmentation WITH API
```bash
source ros_env.sh
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p enable_api:=true \
  -p api_url:='http://localhost:8000' \
  -p api_user_id:='test_user' \
  -p output_dir:=./audio_chunks \
  -p verbose:=true
```

## 5. Expected Output

When speech is detected and ends, you should see:

```
[INFO] [speech_segmentation_node]: [SEGMENTATION] Speech started
[INFO] [speech_segmentation_node]: [SEGMENTATION] Speech ended
  Saved chunk_1.wav
  Duration: 2.45s
  Samples: 39200
[INFO] [speech_segmentation_node]: [API] Sent audio - Status: 200
```

## 6. Verify Results

Check files created:
```bash
ls -la audio_chunks/
# Should see: chunk_1.wav, chunk_1.txt (transcription)
```

Check logs for API call:
```bash
# Terminal 4 should show: [API] Sent audio - Status: 200
```

Check Orlock logs:
```bash
# Terminal 1 should show the POST request received
```

## 7. Troubleshooting

| Issue | Solution |
|-------|----------|
| `[API] Failed - Could not connect` | Orlock server not running on localhost:8000 |
| `ModuleNotFoundError: orlock_api_client` | Did you source ros_env.sh? |
| `requests` not found | `pip install requests` |
| No API calls in logs | Check `enable_api:=true` is set |
| Local files save but no API call | Check if Orlock is reachable |

## 8. Quick Smoke Test

If you want to test just the Python import:

```bash
cd ros2-VAD-module
python -c "from vad_component.orlock_api_client import OrlockAPIClient; print('✓ Import OK')"
```

Expected output:
```
✓ Import OK
```
