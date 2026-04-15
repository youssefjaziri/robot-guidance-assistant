"""
speech_segmentation_node.py
-----------------------------
Subscribes to /speech_detected and /audio/raw, implements a state machine
to detect speech segments, buffers audio, and saves chunks as .wav files.
Includes pre-buffering for sentence start capture, amplitude filtering for
near-field audio detection, and automatic transcription with fast-whisper.

Topics subscribed:
    /speech_detected    (std_msgs/msg/Bool)      – VAD output
    /audio/raw          (std_msgs/msg/Int16MultiArray) – PCM audio

Dependencies (install in your ROS2 environment):
    pip install soundfile numpy faster-whisper
"""

from collections import deque
from enum import Enum
import time
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Int16MultiArray

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

from vad_component.orlock_api_client import OrlockAPIClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SAMPLE_RATE = 16_000          # Hz – must match mic_node
SILENCE_THRESHOLD = 0.5       # seconds – how long to wait for silence
MIN_SEGMENT_DURATION = 0.3    # seconds – ignore very short segments
INT16_MAX = 32768.0           # used to normalise int16 ↔ float32


class VadState(Enum):
    """State machine states for speech detection."""
    IDLE = "IDLE"
    RECORDING = "RECORDING"
    STOPPING = "STOPPING"


class SpeechSegmentationNode(Node):
    """
    Buffers audio frames during detected speech and saves segments to .wav files.
    Includes pre-buffering to capture sentence starts, amplitude filtering for
    near-field audio, and automatic transcription with fast-whisper.

    Parameters (ROS2 params):
        output_dir (str): Directory to save audio chunks. Default: "./audio_chunks"
        silence_threshold (double): Silence duration before stopping recording (sec).
                                    Default: 0.5
        min_duration (double): Minimum segment duration to save (seconds).
                              Default: 0.3
        pre_buffer_duration (double): Duration of pre-buffer to capture sentence starts (sec).
                                      Default: 1.0
        amplitude_threshold (double): RMS energy threshold for near-field detection.
                                      Default: 0.02
        enable_transcription (bool): Enable fast-whisper transcription of segments.
                                     Default: True
        enable_amplitude_filter (bool): Enable amplitude-based filtering to exclude far-field audio.
                                        Default: True
        verbose (bool): If True, log all state transitions and frame stats.
                        Default: False
    """

    def __init__(self) -> None:
        super().__init__('speech_segmentation_node')

        # --- declare & read parameters ----------------------------------------
        self.declare_parameter('output_dir', './audio_chunks')
        self.declare_parameter('silence_threshold', SILENCE_THRESHOLD)
        self.declare_parameter('min_duration', MIN_SEGMENT_DURATION)
        self.declare_parameter('verbose', False)
        self.declare_parameter('pre_buffer_duration', 1.0)
        self.declare_parameter('amplitude_threshold', 0.02)
        self.declare_parameter('enable_transcription', True)
        self.declare_parameter('enable_amplitude_filter', True)
        # --- API parameters ----
        self.declare_parameter('enable_api', False)
        self.declare_parameter('api_url', 'http://localhost:8000')
        self.declare_parameter('api_user_id', 'default_user')
        self.declare_parameter('api_system_prompt', None)

        self._output_dir: str = (
            self.get_parameter('output_dir').get_parameter_value().string_value
        )
        self._silence_threshold: float = (
            self.get_parameter('silence_threshold').get_parameter_value().double_value
        )
        self._min_duration: float = (
            self.get_parameter('min_duration').get_parameter_value().double_value
        )
        self._verbose: bool = (
            self.get_parameter('verbose').get_parameter_value().bool_value
        )
        self._pre_buffer_duration: float = (
            self.get_parameter('pre_buffer_duration').get_parameter_value().double_value
        )
        self._amplitude_threshold: float = (
            self.get_parameter('amplitude_threshold').get_parameter_value().double_value
        )
        self._enable_transcription: bool = (
            self.get_parameter('enable_transcription').get_parameter_value().bool_value
        )
        self._enable_amplitude_filter: bool = (
            self.get_parameter('enable_amplitude_filter').get_parameter_value().bool_value
        )
        # --- API parameters ----
        self._enable_api: bool = (
            self.get_parameter('enable_api').get_parameter_value().bool_value
        )
        self._api_url: str = (
            self.get_parameter('api_url').get_parameter_value().string_value
        )
        self._api_user_id: str = (
            self.get_parameter('api_user_id').get_parameter_value().string_value
        )
        api_system_param = self.get_parameter('api_system_prompt').get_parameter_value()
        self._api_system_prompt: Optional[str] = (
            api_system_param.string_value if api_system_param.type != 0 else None
        )

        # Initialize API client if enabled
        self._api_client = None
        if self._enable_api:
            self._api_client = OrlockAPIClient(self._api_url)
            self.get_logger().info(f'[API] Enabled - {self._api_url}')

        # Create output directory if it doesn't exist
        output_path = Path(self._output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        self._output_dir = str(output_path.resolve())

        # --- state machine  ---------------------------------------------------
        self._state: VadState = VadState.IDLE
        self._audio_buffer: list[np.ndarray] = []
        self._chunk_counter: int = 0
        self._silence_start_time: Optional[float] = None
        self._recording_start_time: Optional[float] = None

        # --- pre-buffering for capturing sentence starts ----------------------
        self._pre_buffer_max_frames: int = max(1, int(self._pre_buffer_duration * SAMPLE_RATE / 512))
        self._pre_buffer: deque[np.ndarray] = deque(maxlen=self._pre_buffer_max_frames)

        # --- transcription model initialization --------------------------------
        self._whisper_model = None
        if self._enable_transcription and WhisperModel is not None:
            try:
                self._whisper_model = WhisperModel("base", device="cpu")
                self.get_logger().info('[TRANSCRIPTION] Loaded Whisper base model')
            except Exception as exc:
                self.get_logger().warn(
                    f'[TRANSCRIPTION] Failed to load Whisper model: {exc}\n'
                    f'  Transcription will be disabled.'
                )
                self._enable_transcription = False
        elif self._enable_transcription and WhisperModel is None:
            self.get_logger().warn(
                '[TRANSCRIPTION] faster-whisper not installed. '
                'Transcription disabled. Install with: pip install faster-whisper'
            )
            self._enable_transcription = False

        # --- subscribers & publishers -----------------------------------------
        self._sub_speech = self.create_subscription(
            Bool,
            '/speech_detected',
            self._speech_detected_callback,
            10,
        )
        self._sub_audio = self.create_subscription(
            Int16MultiArray,
            '/audio/raw',
            self._audio_callback,
            10,
        )

        self.get_logger().info(
            f'SpeechSegmentationNode ready\n'
            f'  output_dir={self._output_dir}\n'
            f'  silence_threshold={self._silence_threshold}s\n'
            f'  min_duration={self._min_duration}s\n'
            f'  pre_buffer_duration={self._pre_buffer_duration}s ({self._pre_buffer_max_frames} frames)\n'
            f'  amplitude_threshold={self._amplitude_threshold} (RMS)\n'
            f'  enable_amplitude_filter={self._enable_amplitude_filter}\n'
            f'  enable_transcription={self._enable_transcription}\n'
            f'  enable_api={self._enable_api}\n'
            f'  api_url={self._api_url if self._enable_api else "N/A"}\n'
            f'  verbose={self._verbose}'
        )

    # ------------------------------------------------------------------
    def _speech_detected_callback(self, msg: Bool) -> None:
        """Handle speech detection state changes."""
        speech_detected = msg.data

        if speech_detected and self._state == VadState.IDLE:
            # --- IDLE → RECORDING: Start recording ----
            self._state = VadState.RECORDING
            self._audio_buffer.clear()

            # --- Prepend pre-buffered frames to capture sentence start ----
            pre_buffered_frames = self._drain_pre_buffer()
            self._audio_buffer.extend(pre_buffered_frames)

            self._recording_start_time = time.time()
            self._silence_start_time = None

            pre_buffer_duration = len(pre_buffered_frames) * 512 / SAMPLE_RATE
            self.get_logger().info(
                f'[SEGMENTATION] Speech started (pre-buffered: {pre_buffer_duration:.2f}s)'
            )

        elif not speech_detected and self._state == VadState.RECORDING:
            # --- RECORDING → STOPPING: Silence detected, start timer ----
            self._state = VadState.STOPPING
            self._silence_start_time = time.time()

            if self._verbose:
                self.get_logger().debug('[SEGMENTATION] Silence detected, waiting for threshold...')

        elif speech_detected and self._state == VadState.STOPPING:
            # --- STOPPING → RECORDING: Speech resumed before silence threshold ----
            self._state = VadState.RECORDING
            self._silence_start_time = None

            if self._verbose:
                self.get_logger().debug('[SEGMENTATION] Speech resumed, continuing recording')

    # ------------------------------------------------------------------
    def _audio_callback(self, msg: Int16MultiArray) -> None:
        """Buffer audio frames during RECORDING state, maintain pre-buffer during IDLE."""
        if not msg.data:
            return

        # Convert int16 PCM to float32 normalized to [-1, 1]
        audio_np = np.array(msg.data, dtype=np.int16).astype(np.float32) / INT16_MAX
        frame_duration = len(audio_np) / SAMPLE_RATE

        # --- IDLE: Maintain pre-buffer for sentence start capture ----
        if self._state == VadState.IDLE:
            self._update_pre_buffer(audio_np)

        # --- RECORDING: Accumulate frames with optional amplitude filtering ----
        elif self._state == VadState.RECORDING:
            # Calculate RMS energy for this frame
            rms_energy = self._get_frame_rms(audio_np)

            # Check amplitude threshold if filtering is enabled
            if self._enable_amplitude_filter and rms_energy < self._amplitude_threshold:
                if self._verbose:
                    self.get_logger().debug(
                        f'[SEGMENTATION] Frame rejected (RMS={rms_energy:.4f} < {self._amplitude_threshold})'
                    )
            else:
                # Frame passes filter or filtering disabled – buffer it
                self._audio_buffer.append(audio_np)
                self._update_pre_buffer(audio_np)  # Maintain for continuity

                if self._verbose:
                    self.get_logger().debug(
                        f'[SEGMENTATION] Buffered frame: {len(audio_np)} samples '
                        f'({frame_duration*1000:.1f}ms), RMS={rms_energy:.4f}, total: {self._get_buffer_duration():.2f}s'
                    )

        # --- STOPPING: Check if silence threshold exceeded ----
        elif self._state == VadState.STOPPING and self._silence_start_time is not None:
            silence_duration = time.time() - self._silence_start_time

            if silence_duration >= self._silence_threshold:
                # Silence threshold reached – save segment and return to IDLE
                self._save_segment()
                self._state = VadState.IDLE
                self._audio_buffer.clear()
                self._pre_buffer.clear()  # Clear pre-buffer on segment end
                self._silence_start_time = None

    # ------------------------------------------------------------------
    def _get_buffer_duration(self) -> float:
        """Calculate total duration of buffered audio in seconds."""
        if not self._audio_buffer:
            return 0.0
        total_samples = sum(len(frame) for frame in self._audio_buffer)
        return total_samples / SAMPLE_RATE

    # ------------------------------------------------------------------
    def _update_pre_buffer(self, audio_frame: np.ndarray) -> None:
        """Add audio frame to circular pre-buffer for sentence start capture."""
        self._pre_buffer.append(audio_frame)

    # ------------------------------------------------------------------
    def _drain_pre_buffer(self) -> list[np.ndarray]:
        """Extract all frames from pre-buffer in order and clear it."""
        frames = list(self._pre_buffer)
        self._pre_buffer.clear()
        return frames

    # ------------------------------------------------------------------
    def _get_frame_rms(self, audio_frame: np.ndarray) -> float:
        """Calculate RMS (root mean square) energy of an audio frame."""
        if len(audio_frame) == 0:
            return 0.0
        return float(np.sqrt(np.mean(audio_frame ** 2)))

    # ------------------------------------------------------------------
    def _transcribe_segment(self, filepath: Path) -> None:
        """Transcribe saved audio file using fast-whisper."""
        if not self._enable_transcription or self._whisper_model is None:
            return

        try:
            # Transcribe audio file
            segments = list(self._whisper_model.transcribe(str(filepath), language="en"))

            # Combine all segments into single text
            full_text = ' '.join([
                segment.text.strip() if hasattr(segment, 'text') else str(segment).strip()
                for segment in segments
            ])

            if not full_text.strip():
                self.get_logger().info('[TRANSCRIPTION] Segment contains no speech')
                return

            # Save transcription as .txt file
            txt_filepath = filepath.with_suffix('.txt')
            with open(txt_filepath, 'w', encoding='utf-8') as f:
                f.write(full_text.strip())

            self.get_logger().info(
                f'[TRANSCRIPTION] Saved transcription\n'
                f'  File: {txt_filepath.name}\n'
                f'  Text: {full_text[:100]}...' if len(full_text) > 100 else f'  Text: {full_text}'
            )

        except Exception as exc:
            self.get_logger().error(
                f'[TRANSCRIPTION] Failed to transcribe {filepath.name}: {exc}'
            )

    # ------------------------------------------------------------------
    def _send_to_api(self, audio_data: np.ndarray) -> None:
        """Send audio to Orlock API."""
        if not self._api_client:
            return

        try:
            response = self._api_client.send_audio(
                audio_data=audio_data,
                user_id=self._api_user_id,
                system=self._api_system_prompt,
                sample_rate=SAMPLE_RATE,
            )

            if response['success']:
                self.get_logger().info(
                    f'[API] Sent audio - Status: {response["status_code"]}'
                )
            else:
                self.get_logger().warn(
                    f'[API] Failed - {response["error"]}'
                )

        except Exception as exc:
            self.get_logger().error(
                f'[API] Error sending audio: {exc}'
            )

    # ------------------------------------------------------------------
    def _save_segment(self) -> None:
        """Concatenate buffered frames, validate, and save as .wav file."""
        if not self._audio_buffer:
            self.get_logger().warn('[SEGMENTATION] Attempted to save empty buffer')
            return

        # Concatenate all frames
        audio_data = np.concatenate(self._audio_buffer)
        duration = len(audio_data) / SAMPLE_RATE

        # Validate minimum duration
        if duration < self._min_duration:
            self.get_logger().info(
                f'[SEGMENTATION] Segment too short ({duration:.2f}s < {self._min_duration}s), skipping'
            )
            return

        # Generate filename and save
        self._chunk_counter += 1
        filename = f'chunk_{self._chunk_counter}.wav'
        filepath = Path(self._output_dir) / filename

        try:
            # Save as .wav file at 16kHz
            sf.write(str(filepath), audio_data, SAMPLE_RATE)

            self.get_logger().info(
                f'[SEGMENTATION] Speech ended\n'
                f'  Saved {filename}\n'
                f'  Duration: {duration:.2f}s\n'
                f'  Samples: {len(audio_data)}'
            )

            # --- Send to Orlock API if enabled ----
            if self._enable_api and self._api_client:
                self._send_to_api(audio_data)

            # --- Transcribe segment if enabled ----
            self._transcribe_segment(filepath)

        except Exception as exc:
            self.get_logger().error(
                f'[SEGMENTATION] Failed to save {filename}: {exc}'
            )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SpeechSegmentationNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
