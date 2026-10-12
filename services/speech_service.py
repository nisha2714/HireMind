import os
import time

from openai import OpenAI

from config.settings import OPENAI_API_KEY, OPENAI_PRICING

TRANSCRIBE_MODEL = os.getenv("TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")


class SpeechService:
    """Speech-to-text via OpenAI. Accepts audio (wav/mp3/m4a) and video containers (webm/mp4)."""

    def __init__(self):
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in .env file")
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = TRANSCRIBE_MODEL

    def transcribe_bytes(self, data: bytes, filename: str = "answer.wav") -> str:
        """Transcribe raw media bytes; every call is logged with API-reported token usage."""
        if not data:
            raise ValueError("Empty recording")

        start = time.time()
        try:
            resp = self.client.audio.transcriptions.create(
                model=self.model, file=(filename, data), response_format="json"
            )
        except Exception as e:
            self._log(0, 0, start, "error", str(e))
            raise RuntimeError(f"Transcription failed: {e}")

        usage = getattr(resp, "usage", None)
        self._log(
            getattr(usage, "input_tokens", 0) or 0,
            getattr(usage, "output_tokens", 0) or 0,
            start, "success",
        )

        text = (getattr(resp, "text", "") or "").strip()
        if not text:
            raise ValueError("No speech detected in the recording. Please record again.")
        return text

    def transcribe_audio(self, audio_file) -> str:
        """Transcribe a Streamlit audio_input file."""
        return self.transcribe_bytes(audio_file.getvalue(), getattr(audio_file, "name", None) or "answer.wav")

    def transcribe_from_video(self, video_bytes: bytes, filename: str = "answer.webm") -> str:
        """Transcribe the audio track of a recorded video (webm/mp4 accepted directly)."""
        return self.transcribe_bytes(video_bytes, filename)

    def _log(self, in_tok, out_tok, start, status, error=None):
        try:
            from database.usage_logger import UsageLogger
            rates = OPENAI_PRICING.get(self.model, {})
            UsageLogger.log_usage(
                agent_name="SpeechService",
                model=self.model,
                input_tokens=in_tok,
                output_tokens=out_tok,
                latency_ms=int((time.time() - start) * 1000),
                cost_usd=in_tok * rates.get("input", 0) + out_tok * rates.get("output", 0),
                interview_id=os.getenv("CURRENT_INTERVIEW_ID") or None,
                user_id=os.getenv("CURRENT_USER_ID", "system"),
                status=status,
                error_message=error,
            )
        except Exception as e:
            print(f"Usage logging failed: {e}")
