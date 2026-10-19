"""Shared utility functions for TTS services."""

from typing import Tuple


def media_type_for(audio_format: str) -> Tuple[str, str]:
    """Return (Content-Type, file_extension) for the given audio format.

    Case-insensitive. Supports MP3, WAV, FLAC.
    Defaults to application/octet-stream for unknown formats.
    """
    value = audio_format.strip().upper()
    if value == "MP3":
        return "audio/mpeg", "mp3"
    if value == "WAV":
        return "audio/wav", "wav"
    if value == "FLAC":
        return "audio/flac", "flac"
    return "application/octet-stream", value.lower() or "bin"


def pitch_to_ssml(value: float) -> str:
    """Convert pitch multiplier to SSML pitch string (Hz).

    1.0 → '+0Hz', 1.2 → '+20Hz', 0.8 → '-20Hz'
    """
    hz = round((value - 1.0) * 100)
    if hz >= 0:
        return f"+{hz}Hz"
    return f"{hz}Hz"


def volume_to_ssml(value: float) -> str:
    """Convert volume multiplier to SSML volume string.

    1.0 → '+0%', 1.2 → '+20%', 0.8 → '-20%'
    """
    pct = round((value - 1.0) * 100)
    if pct >= 0:
        return f"+{pct}%"
    return f"{pct}%"


def speed_to_rate(speed: float) -> str:
    """Convert speed multiplier (0.5-2.0) to SSML rate string.

    1.0 → '+0%', 1.2 → '+20%', 0.8 → '-20%'
    """
    pct = round((speed - 1.0) * 100)
    if pct >= 0:
        return f"+{pct}%"
    return f"{pct}%"
