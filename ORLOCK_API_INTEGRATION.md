# Orlock API Integration Guide

## Quick Start

The speech segmentation node can now send audio directly to the Orlock server.

### Enable API Sending

Run the node with API enabled:

```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p enable_api:=true \
  -p api_url:='http://localhost:8000' \
  -p api_user_id:='test_user' \
  -p output_dir:=./audio_chunks
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_api` | bool | `false` | Enable sending to Orlock API |
| `api_url` | string | `http://localhost:8000` | Orlock server URL |
| `api_user_id` | string | `default_user` | User ID for API requests |
| `api_system_prompt` | string | `null` | Optional system prompt for LLM |

### What Happens

When speech ends:
1. Audio is saved locally to `output_dir`
2. Same audio is sent to `/api/v1/userAudio` endpoint
3. Orlock server transcribes and sends to LLM
4. Response is logged

If API fails, local saving continues (no blocking).

### Error Handling

- Connection timeout: Logged as warning, continues normal operation
- Server error: Logged as warning, does not affect local saving
- Malformed data: Caught and logged

### Example Setup

**Terminal 1 - Microphone:**
```bash
ros2 run vad_component mic_node --ros-args -p device:=pulse
```

**Terminal 2 - VAD:**
```bash
ros2 run vad_component vad_node
```

**Terminal 3 - Speech + API (NEW):**
```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p enable_api:=true \
  -p api_url:='http://localhost:8000' \
  -p api_user_id:='alice' \
  -p output_dir:=./audio_chunks \
  -p verbose:=true
```

## How It Works

```python
# In _save_segment():
audio_data = np.concatenate(self._audio_buffer)
sf.write(str(filepath), audio_data, SAMPLE_RATE)  # Save locally

if self._enable_api and self._api_client:
    self._send_to_api(audio_data)  # Send to Orlock
```

The `OrlockAPIClient` converts numpy arrays to WAV bytes and POSTs to the server with multipart form-data.

## Troubleshooting

**No API calls being made:**
- Check `enable_api:=true` is set
- Verify Orlock server is running on correct URL
- Check logs for connection errors

**API errors in logs:**
- Ensure Orlock server is accessible
- Check `/api/v1/userAudio` endpoint exists
- Verify `api_user_id` is valid

**Local files not saving with API enabled:**
- API failures don't block local saving
- Check `output_dir` permissions
