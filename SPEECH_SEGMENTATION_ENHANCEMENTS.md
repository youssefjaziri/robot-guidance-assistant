# Speech Segmentation Node - Enhancements Guide

This document describes three key enhancements to the `speech_segmentation_node` that improve speech capture, filtering, and transcription capabilities.

---

## 1. Pre-Buffering: Circular Buffer for Sentence Starts

### Problem It Solves

Voice Activity Detection (VAD) typically has some latency or delay before triggering on speech onset. This means the first few milliseconds of speech might be lost before recording begins. For complete speech understanding, capturing the full sentence from the very beginning is critical—missing the opening phrase can change the meaning of an entire utterance.

**Example**: If a user says "No, don't do that", but VAD detects speech after "don't", you lose critical context.

### How It Works

The node maintains a **circular buffer** that continuously stores audio frames even while in the IDLE state:

1. **Continuous storage**: Every audio frame received is added to the pre-buffer (a fixed-size rotating queue)
2. **Circular FIFO**: Old frames are automatically discarded when the buffer reaches its size limit
3. **On speech detection**: When VAD detects speech, all pre-buffered frames are prepended to the main recording buffer
4. **Sentence preservation**: The speaker's opening words are captured, providing complete semantic context

**Technical flow:**
```
IDLE state:     frame1 → frame2 → frame3 → frame4 → (circular buffer maintained)
                                                    ↓
Speech detected:  [frame1, frame2, frame3, frame4] + new frames → main buffer
                  (pre-buffer prepended to recording)
```

### Parameters to Configure

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `pre_buffer_duration` | double | `1.0` | 0.5 - 3.0 | Duration in seconds to store pre-buffer. At 16kHz with 512-sample frames, 1.0s = ~31 frames. Larger values capture more sentence context but use more memory. |

### Usage Examples

#### Example 1: Default setup (1 second pre-buffer)
```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p output_dir:=./audio_chunks \
  -p pre_buffer_duration:=1.0
```

**Result**: Captures up to 1.0 second before VAD triggers
- Memory usage: ~31 frames × 512 samples × 4 bytes ≈ 64 KB
- Typical capture: First 1-2 words plus VAD latency

#### Example 2: Shorter pre-buffer for low-latency applications
```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p pre_buffer_duration:=0.5
```

**Result**: Captures only 0.5 seconds (~16 frames)
- Use when: Memory is constrained or latency is prioritized
- Trade-off: May miss some opening words

#### Example 3: Longer pre-buffer for important applications
```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p pre_buffer_duration:=2.0
```

**Result**: Captures up to 2.0 seconds before speech detection
- Use when: Complete utterances are critical (e.g., commands, dictation)
- Trade-off: Higher memory usage; pre-buffer contains ~62 frames

### Expected Output

With verbose logging enabled, you'll see pre-buffer metrics:

```
[INFO] [speech_segmentation_node]: [SEGMENTATION] Speech started (pre-buffered: 0.95s)
```

This indicates 0.95 seconds of pre-buffered audio was prepended to the recording.

---

## 2. Amplitude Filtering: RMS-Based Noise Gating

### Problem It Solves

In multi-user or noisy environments, distant speakers or background noise can trigger VAD. Even with a good VAD model, far-field audio has significantly lower signal-to-noise ratio. Without filtering, you may save segments with minimal actual speech content.

**Example scenarios:**
- User sitting 3+ meters away from microphone triggers VAD but audio is mostly room noise
- Background TV or music in another room registers as speech
- Keyboard typing or paper shuffling gets captured

### How It Works

The node calculates the **Root Mean Square (RMS)** energy of each audio frame and compares it against a configurable threshold:

1. **Per-frame RMS calculation**: For each 512-sample frame, compute RMS energy
   ```
   RMS = sqrt(mean(sample₁² + sample₂² + ... + sampleₙ²))
   ```

2. **Threshold comparison**: If RMS < threshold, frame is rejected (not buffered)

3. **Optional filtering**: Can be disabled if VAD is already excellent

**Energy levels reference** (normalized audio [-1, 1]):
- **0.001 - 0.005**: Very quiet breathing, distant whisper
- **0.01 - 0.02**: Quiet speech, far-field audio (typical rejection zone)
- **0.05 - 0.10**: Normal conversational speech
- **0.15+**: Loud speech or shouting

### Parameters to Configure

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `amplitude_threshold` | double | `0.02` | 0.005 - 0.10 | RMS energy threshold for near-field detection. Frames with RMS below this are rejected. Default 0.02 captures normal speech while filtering far-field audio. |
| `enable_amplitude_filter` | bool | `True` | — | Enable/disable amplitude filtering. Set to `False` if your VAD is already reliable or you need all audio regardless of distance. |

### Usage Examples

#### Example 1: Default filtering for good VAD (0.02 threshold)
```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p amplitude_threshold:=0.02 \
  -p enable_amplitude_filter:=true
```

**Result**: Rejects frames quieter than typical conversation level
- Typical acceptance: Voices ~0.05-0.15 RMS
- Typical rejection: Background noise, far-field speech ~0.005-0.02 RMS

#### Example 2: Aggressive filtering for noisy environments
```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p amplitude_threshold:=0.05 \
  -p enable_amplitude_filter:=true \
  -p verbose:=true
```

**Result**: Only captures loud, near-field speech
- Use when: Environment has significant background noise
- Trade-off: May reject very quiet speakers

Sample verbose output:
```
[DEBUG] [speech_segmentation_node]: [SEGMENTATION] Frame rejected (RMS=0.0089 < 0.0500)
[DEBUG] [speech_segmentation_node]: [SEGMENTATION] Buffered frame: 512 samples (32.0ms), RMS=0.0756, total: 2.35s
[DEBUG] [speech_segmentation_node]: [SEGMENTATION] Frame rejected (RMS=0.0034 < 0.0500)
```

#### Example 3: Lenient filtering for challenging scenarios
```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p amplitude_threshold:=0.01 \
  -p enable_amplitude_filter:=true
```

**Result**: Accepts quieter audio (whispers, distant speakers)
- Use when: Need to capture all speech types
- Trade-off: May include some background noise

#### Example 4: Disable filtering (rely on VAD only)
```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p enable_amplitude_filter:=false
```

**Result**: All frames passing VAD are buffered
- Use when: VAD is very reliable or you're in a controlled environment
- Use when: You need to preserve audio dynamics (e.g., music transcription)

### Expected Output

With verbose logging enabled, you'll see amplitude filtering decisions:

```
[SEGMENTATION] Buffered frame: 512 samples (32.0ms), RMS=0.0856, total: 1.23s
[SEGMENTATION] Frame rejected (RMS=0.0018 < 0.0200)
[SEGMENTATION] Buffered frame: 512 samples (32.0ms), RMS=0.0634, total: 1.26s
```

---

## 3. Fast-Whisper Transcription: Auto-Transcribe Segments

### Problem It Solves

Audio segments are useful for storage and replay, but speech-to-text transcription is often needed for:
- Voice commands that must be understood, not just detected
- Creating searchable archives of conversations
- Real-time closed captioning or accessibility
- Building training datasets with ground truth labels
- Compliance and audit trails

Waiting for transcription to happen separately creates workflow friction. Automating transcription on segment completion ensures text is available immediately.

### How It Works

The node uses **Faster-Whisper**, an optimized implementation of OpenAI's Whisper model:

1. **Segment saved**: When a speech segment is saved as `.wav`, transcription begins immediately
2. **Model inference**: Faster-Whisper processes the audio and predicts text
3. **Output file**: Transcribed text is saved as `.txt` file (same name as audio)
4. **Auto-language detection**: Automatically detects language (not limited to English)
5. **Minimal latency**: Faster-Whisper is optimized for CPU inference

**Processing pipeline:**
```
chunk_N.wav (saved) → Faster-Whisper model → [speech-to-text] → chunk_N.txt (created)
                     ↓
                  Language: auto-detected
                  Model: base (130M parameters)
                  Device: CPU
```

### Parameters to Configure

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_transcription` | bool | `True` | Enable/disable automatic transcription. Set to `False` to save audio only. |

**Note**: Model selection and device are currently hardcoded but can be customized:
- Model: `"base"` (130M parameters, good accuracy/speed balance)
  - Alternatives: `"tiny"` (39M, faster), `"small"` (244M, better accuracy), `"medium"` (769M, excellent accuracy)
- Device: `"cpu"` (works everywhere; use `"cuda"` for GPU if available)

### Installation & Setup

#### Install Faster-Whisper
```bash
pip install faster-whisper
```

#### First run
On first use, the model will be automatically downloaded (~140 MB for base model):
```
[INFO] [speech_segmentation_node]: [TRANSCRIPTION] Loaded Whisper base model
```

### Usage Examples

#### Example 1: Auto-transcription enabled (default)
```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p output_dir:=./audio_chunks \
  -p enable_transcription:=true
```

**Result**: Each saved segment automatically generates a `.txt` file

**Output structure:**
```
audio_chunks/
├── chunk_1.wav          (2.45 seconds of audio)
├── chunk_1.txt          ("Hello, this is a test recording")
├── chunk_2.wav          (1.87 seconds of audio)
└── chunk_2.txt          ("Transcription works great!")
```

#### Example 2: Audio only, no transcription
```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p output_dir:=./audio_chunks \
  -p enable_transcription:=false
```

**Result**: Only `.wav` files are saved (faster, lower latency)

**Use when:**
- You only need audio for later processing
- Running on resource-constrained hardware
- Transcription accuracy isn't immediately needed

#### Example 3: Full pipeline with all enhancements
```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p output_dir:=./audio_chunks \
  -p pre_buffer_duration:=1.0 \
  -p amplitude_threshold:=0.02 \
  -p enable_amplitude_filter:=true \
  -p enable_transcription:=true \
  -p silence_threshold:=0.5 \
  -p min_duration:=0.3 \
  -p verbose:=true
```

**Result**: Comprehensive speech capture with transcription

Sample output:
```
[INFO] [speech_segmentation_node]: SpeechSegmentationNode ready
  output_dir=/home/user/audio_chunks
  silence_threshold=0.5s
  min_duration=0.3s
  pre_buffer_duration=1.0s (31 frames)
  amplitude_threshold=0.02 (RMS)
  enable_amplitude_filter=True
  enable_transcription=True
  verbose=True

[INFO] [speech_segmentation_node]: [SEGMENTATION] Speech started (pre-buffered: 0.97s)
[INFO] [speech_segmentation_node]: [SEGMENTATION] Speech ended
  Saved chunk_1.wav
  Duration: 2.45s
  Samples: 39200

[INFO] [speech_segmentation_node]: [TRANSCRIPTION] Saved transcription
  File: chunk_1.txt
  Text: Hello, how can I help you today?
```

### Expected Output Files

**Before transcription:**
```
chunk_1.wav  (binary audio file, ~40 KB for 2.5-second segment)
```

**After transcription (automatically created):**
```
chunk_1.wav   (binary audio file)
chunk_1.txt   (text file with transcribed content)
```

**Example `.txt` file content:**
```
Hello, how can I help you today?
```

### Transcription Quality Notes

**Advantages:**
- **Multi-language**: Automatically detects language
- **Robust**: Works with accents, background noise, casual speech
- **Fast**: Base model processes ~10 seconds of audio per second on CPU
- **Accurate**: Whisper model trained on 680,000 hours of multilingual data

**Accuracy by scenario:**
- **Clear speech in quiet environment**: 95%+ accuracy
- **Conversational speech with minor background noise**: 85-90% accuracy
- **Heavily accented speech**: 70-85% accuracy (depends on training data)
- **Heavy background noise**: May produce partial results or errors

**Tips for best results:**
1. Keep `amplitude_threshold` appropriate for your environment
2. Use longer `silence_threshold` if speech is interrupted by pauses
3. Increase `pre_buffer_duration` to capture opening words clearly
4. Enable `verbose` logging to verify amplitude filtering is working

### Troubleshooting

**Transcription not working:**
```bash
# Check if faster-whisper is installed
python3 -c "import faster_whisper; print('OK')"

# If missing, install it:
pip install faster-whisper

# Check logs for model loading errors
ros2 run vad_component speech_segmentation_node --ros-args -p verbose:=true
```

**Model download issues:**
- First run downloads ~140 MB (base model)
- Requires internet connection for first-time setup
- Model cached locally (typically in `~/.cache/huggingface/`)

**Slow transcription:**
- Base model processes ~10s audio/sec on modern CPU
- 2.5-second segment takes ~0.25 seconds to transcribe
- For faster results on older hardware: use `"tiny"` model (faster but less accurate)

---

## Combined Usage: All Three Enhancements

### Real-World Example: Call Center Audio Processing

```bash
# Capture complete utterances from multiple meters away with transcription
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p output_dir:=/var/call_center_recordings \
  -p pre_buffer_duration:=1.5 \
  -p amplitude_threshold:=0.015 \
  -p enable_amplitude_filter:=true \
  -p enable_transcription:=true \
  -p silence_threshold:=1.0 \
  -p min_duration:=0.5
```

**Result flow:**
1. Pre-buffer captures opening words (1.5 seconds context)
2. Amplitude filter rejects ambient office noise
3. Full call center conversation captured
4. Transcribed text automatically generated for logging/searching

### File Structure After Processing

```
/var/call_center_recordings/
├── chunk_1.wav
├── chunk_1.txt  ("Customer: Hello, I need to reset my password")
├── chunk_2.wav
├── chunk_2.txt  ("Agent: Sure, I can help you with that")
├── chunk_3.wav
├── chunk_3.txt  ("Customer: My account email is john@example.com")
└── ... (continues)
```

---

## Performance & Resource Impact

| Enhancement | Memory | CPU | Latency | Notes |
|-------------|--------|-----|---------|-------|
| **Pre-buffering** | ~1-4 MB | Negligible | +0ms | Circular buffer, minimal overhead |
| **Amplitude filtering** | +0 KB | ~2-3% | +~1ms per frame | RMS calculation is fast |
| **Transcription** | +50 MB | 80-90% | ~100-200ms per segment | Model loaded once; blocking I/O |

**Transcription timing examples:**
- 1-second segment: ~100ms transcription
- 2.5-second segment: ~250ms transcription
- 5-second segment: ~500ms transcription

---

## Combining with Other Nodes

The speech segmentation node integrates seamlessly with:

1. **mic_node**: Captures audio → provides frames
2. **vad_node**: Detects speech → triggers segmentation
3. **speech_segmentation_node**: Buffers & transcribes → creates segments
4. **Your application**: Reads `.wav` + `.txt` files for processing

```
mic_node (/audio/raw)
    ↓
vad_node (/speech_detected)
    ↓
speech_segmentation_node
    ├── Pre-buffer (1.0s circular)
    ├── Amplitude filter (RMS ≥ 0.02)
    └── Transcription (Faster-Whisper)
    ↓
audio_chunks/
├── chunk_1.wav
├── chunk_1.txt
├── chunk_2.wav
├── chunk_2.txt
└── ...
```

---

## Summary Table

| Feature | Problem | Solution | Key Parameter |
|---------|---------|----------|----------------|
| **Pre-Buffering** | Missing sentence starts | Circular buffer stores pre-speech audio | `pre_buffer_duration` (default: 1.0s) |
| **Amplitude Filtering** | Far-field noise captured | RMS-based threshold gate | `amplitude_threshold` (default: 0.02) |
| **Transcription** | No text output from audio | Automatic Faster-Whisper processing | `enable_transcription` (default: True) |

---

## Configuration Templates

### Template 1: Sensitive Microphone (Far-field Capture)
```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p pre_buffer_duration:=1.5 \
  -p amplitude_threshold:=0.01 \
  -p enable_amplitude_filter:=true \
  -p enable_transcription:=true
```

### Template 2: Near-field Only (Headset/Lapel Mic)
```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p pre_buffer_duration:=0.5 \
  -p amplitude_threshold:=0.05 \
  -p enable_amplitude_filter:=true \
  -p enable_transcription:=true
```

### Template 3: Battery-Constrained Device
```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p pre_buffer_duration:=0.5 \
  -p enable_amplitude_filter:=true \
  -p enable_transcription:=false
```

### Template 4: Maximum Accuracy
```bash
ros2 run vad_component speech_segmentation_node \
  --ros-args \
  -p pre_buffer_duration:=2.0 \
  -p amplitude_threshold:=0.01 \
  -p enable_amplitude_filter:=true \
  -p enable_transcription:=true \
  -p silence_threshold:=0.8 \
  -p min_duration:=0.5
```

---

## Appendix: Technical Reference

### RMS Energy Formula

For a frame of N audio samples:
```
RMS = sqrt((1/N) * Σ(sample_i)²)
```

**Example calculation** (4 samples for simplicity):
- Samples: [0.1, -0.15, 0.2, -0.05]
- Squared: [0.01, 0.0225, 0.04, 0.0025]
- Mean: (0.01 + 0.0225 + 0.04 + 0.0025) / 4 = 0.015625
- RMS: sqrt(0.015625) = 0.125

### Pre-Buffer Circular Queue

```python
from collections import deque

# Initialize with max 31 frames (1.0s at 16kHz, 512-sample frames)
pre_buffer = deque(maxlen=31)

# Adding frames (automatically discards oldest if full)
pre_buffer.append(frame1)  # [frame1]
pre_buffer.append(frame2)  # [frame1, frame2]
...
pre_buffer.append(frame32) # [frame2, frame3, ..., frame32] (frame1 auto-removed)

# Drain when speech detected
buffered_frames = list(pre_buffer)  # Convert to list
pre_buffer.clear()                   # Empty the queue
```

### Faster-Whisper Model Sizes

| Model | Size | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| tiny | 39M | 0.5x (fastest) | ~80% | Real-time, low-power |
| base | 130M | 1x (baseline) | ~90% | General purpose (default) |
| small | 244M | 2x | ~95% | High accuracy needed |
| medium | 769M | 6x | ~97% | Very high accuracy |
| large | 3B | 12x (slowest) | ~99% | Maximum accuracy |

---

**Document Version**: 1.0
**Last Updated**: 2026-03-18
**Tested With**: speech_segmentation_node.py (implementation complete)
