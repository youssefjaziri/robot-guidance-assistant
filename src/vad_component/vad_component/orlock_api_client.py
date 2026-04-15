"""
orlock_api_client.py
--------------------
Simple HTTP client to send audio to Orlock server.
"""

import io
import requests
import numpy as np
import soundfile as sf
from typing import Optional


class OrlockAPIClient:
    """Send audio to Orlock server's /api/v1/userAudio endpoint."""

    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.endpoint = f"{server_url}/api/v1/userAudio"

    def send_audio(
        self,
        audio_data: np.ndarray,
        user_id: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
        sample_rate: int = 16000,
    ) -> dict:
        """
        Send audio buffer to Orlock server.

        Args:
            audio_data: numpy array of audio samples (float32 normalized to [-1, 1])
            user_id: user identifier
            system: optional system prompt
            temperature: LLM temperature (default 0.2)
            sample_rate: sample rate (default 16000 Hz)

        Returns:
            dict with response from server, or error info
        """
        try:
            # Convert numpy array to WAV bytes
            wav_buffer = io.BytesIO()
            sf.write(wav_buffer, audio_data, sample_rate, format='WAV')
            wav_buffer.seek(0)

            # Prepare form data
            files = {'audio': ('segment.wav', wav_buffer, 'audio/wav')}
            data = {
                'user_id': user_id,
                'temperature': temperature,
            }
            if system:
                data['system'] = system

            # Send to Orlock API
            response = requests.post(
                self.endpoint,
                files=files,
                data=data,
                timeout=30,
            )
            response.raise_for_status()

            return {
                'success': True,
                'status_code': response.status_code,
                'response': response.json(),
            }

        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': f'Could not connect to {self.endpoint}',
            }
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Request timeout',
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
