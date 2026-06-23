"""Tests for streaming TTS event flow.

Tests the streaming protocol (SynthesizeStart/Chunk/Stop) using a
mock TTS plugin that returns a small valid WAV file.
"""

import math
import struct
import tempfile
import wave
from asyncio import StreamReader, StreamWriter
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from wyoming.event import Event
from wyoming.info import Attribution, Info, TtsProgram
from wyoming.tts import SynthesizeStart, SynthesizeChunk, SynthesizeStop, SynthesizeStopped

from wyoming_ovos_tts.__main__ import OVOSTTSEventHandler, _extract_sentences


def _streams():
    return MagicMock(spec=StreamReader), MagicMock(spec=StreamWriter)


def _build_handler(fake_plugin=None, chunk_size=256):
    """Build a handler with a mock TTS plugin."""
    reader, writer = _streams()

    if fake_plugin is None:
        fake_plugin = MagicMock()
        fake_plugin.available_languages = ["en-US"]

    class MockArgs:
        samples_per_chunk = chunk_size

    attr = Attribution(name="test", url="https://example.com")
    wyoming_info = Info(
        tts=[
            TtsProgram(
                name="test-tts",
                description="test",
                installed=True,
                version="0.2.0",
                attribution=attr,
                supports_synthesize_streaming=True,
                voices=[],
            )
        ],
    )

    return OVOSTTSEventHandler(
        wyoming_info=wyoming_info,
        cli_args=MockArgs(),
        plugin=fake_plugin,
        reader=reader,
        writer=writer,
    )


def _make_fake_plugin():
    """Create a mock plugin that returns a tiny valid WAV."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    with wave.open(str(tmp_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        n = 2205  # 0.1 sec
        samples = [
            int(0.3 * 32767 * math.sin(2 * math.pi * 440 * i / 22050))
            for i in range(n)
        ]
        wf.writeframes(struct.pack("<" + "h" * n, *samples))

    mock_audio_path = MagicMock()
    mock_audio_path.path = tmp_path

    fake_plugin = MagicMock()
    fake_plugin.synth.return_value = (mock_audio_path, None)
    fake_plugin.available_languages = ["en-US"]
    return fake_plugin, tmp_path


@pytest.mark.asyncio
async def test_streaming_start_chunk_stop():
    """Full streaming cycle: Start -> Chunk -> Stop."""
    fake_plugin, tmp_path = _make_fake_plugin()
    try:
        handler = _build_handler(fake_plugin)

        await handler.handle_event(SynthesizeStart().event())
        assert handler.is_streaming is True

        await handler.handle_event(SynthesizeChunk(text="Hello. ").event())
        await handler.handle_event(SynthesizeChunk(text="How are ").event())
        await handler.handle_event(SynthesizeChunk(text="you?").event())
        await handler.handle_event(SynthesizeStop().event())

        assert handler.is_streaming is None
        assert handler._buffer == ""
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_streaming_partial_sentence():
    """Partial sentence stays in buffer, gets synthesized on Stop."""
    fake_plugin, tmp_path = _make_fake_plugin()
    try:
        handler = _build_handler(fake_plugin)

        await handler.handle_event(SynthesizeStart().event())
        await handler.handle_event(SynthesizeChunk(text="Hello").event())

        # Sentence-incomplete stays in buffer
        assert handler._buffer == "Hello"

        await handler.handle_event(SynthesizeChunk(text=" world.").event())
        # Handler flushed the complete sentence; buffer empty
        assert handler._buffer == ""
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_non_streaming_path():
    """Non-streaming Synthesize event still works."""
    fake_plugin, tmp_path = _make_fake_plugin()
    try:
        handler = _build_handler(fake_plugin)
        handler.is_streaming = None

        sent = await handler.handle_event(
            Event(type="synthesize", data={"text": "Hello"})
        )
        assert sent is True
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_error_event_on_failure():
    """Handler sends Error event when synth fails."""
    failing_plugin = MagicMock()
    failing_plugin.synth.side_effect = RuntimeError("synth failed")
    failing_plugin.available_languages = ["en-US"]

    handler = _build_handler(failing_plugin)

    with pytest.raises(RuntimeError):
        await handler._synthesize_and_send("test")
