"""Tests for streaming TTS event flow.

Exercises the streaming protocol (SynthesizeStart/Chunk/Stop). Sentence
segmentation is delegated to ``sentence_stream.SentenceBoundaryDetector``,
so these tests assert the per-sentence synthesis the handler drives from it.
"""

import math
import struct
import tempfile
import wave
from asyncio import StreamReader, StreamWriter
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from wyoming.info import Attribution, Info, TtsProgram
from wyoming.tts import SynthesizeStart, SynthesizeChunk, SynthesizeStop

from wyoming_ovos_tts.__main__ import OVOSTTSEventHandler


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


def _capture_sentences(handler):
    """Replace _synthesize_and_send with a collector of requested sentences."""
    sent = []

    async def fake_send(text):
        sent.append(text)
        return True

    handler._synthesize_and_send = fake_send
    return sent


def _capture_events(handler):
    captured = []

    async def capture(event):
        captured.append(event)

    handler.write_event = capture
    return captured


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
    """Full streaming cycle: sentences emitted incrementally, tail on stop."""
    handler = _build_handler()
    sent = _capture_sentences(handler)
    captured = _capture_events(handler)

    await handler.handle_event(SynthesizeStart().event())
    assert handler.is_streaming is True

    await handler.handle_event(SynthesizeChunk(text="Hello. ").event())
    await handler.handle_event(SynthesizeChunk(text="How are ").event())
    await handler.handle_event(SynthesizeChunk(text="you?").event())
    # "Hello." flushes once "How" (a new capitalized sentence) arrives;
    # "How are you?" has no following sentence so it waits for the tail.
    assert sent == ["Hello."]

    await handler.handle_event(SynthesizeStop().event())
    assert handler.is_streaming is None
    assert sent == ["Hello.", "How are you?"]
    assert any(e.type == "synthesize-stopped" for e in captured)


@pytest.mark.asyncio
async def test_streaming_partial_flushed_on_stop():
    """A single unterminated sentence is held, then flushed on stop."""
    handler = _build_handler()
    sent = _capture_sentences(handler)
    _capture_events(handler)

    await handler.handle_event(SynthesizeStart().event())
    await handler.handle_event(SynthesizeChunk(text="Hello").event())
    assert sent == []
    await handler.handle_event(SynthesizeChunk(text=" world.").event())
    # No following capitalized sentence yet -> still buffered.
    assert sent == []
    await handler.handle_event(SynthesizeStop().event())
    assert sent == ["Hello world."]


@pytest.mark.asyncio
async def test_streaming_does_not_split_abbreviation():
    """Abbreviations (Dr.) are not treated as sentence boundaries."""
    handler = _build_handler()
    sent = _capture_sentences(handler)
    _capture_events(handler)

    await handler.handle_event(SynthesizeStart().event())
    await handler.handle_event(
        SynthesizeChunk(text="Dr. Smith went home. Next up. ").event()
    )
    assert sent == ["Dr. Smith went home."]
    await handler.handle_event(SynthesizeStop().event())
    assert sent == ["Dr. Smith went home.", "Next up."]


@pytest.mark.asyncio
async def test_streaming_does_not_split_decimal():
    """Decimal points (3.14) are not treated as sentence boundaries."""
    handler = _build_handler()
    sent = _capture_sentences(handler)
    _capture_events(handler)

    await handler.handle_event(SynthesizeStart().event())
    await handler.handle_event(
        SynthesizeChunk(text="The value is 3.14 today. Done. ").event()
    )
    assert sent == ["The value is 3.14 today."]


@pytest.mark.asyncio
async def test_stop_without_chunks_sends_stopped():
    """SynthesizeStop with no buffered text still terminates the stream."""
    handler = _build_handler()
    sent = _capture_sentences(handler)
    captured = _capture_events(handler)

    await handler.handle_event(SynthesizeStart().event())
    await handler.handle_event(SynthesizeStop().event())
    assert sent == []
    assert any(e.type == "synthesize-stopped" for e in captured)
    assert handler.is_streaming is None


@pytest.mark.asyncio
async def test_real_synth_path_frames_audio_per_sentence():
    """Each synthesized sentence emits its own AudioStart..AudioStop group."""
    fake_plugin, tmp_path = _make_fake_plugin()
    try:
        handler = _build_handler(fake_plugin)
        captured = _capture_events(handler)

        await handler.handle_event(SynthesizeStart().event())
        await handler.handle_event(
            SynthesizeChunk(text="Hello world. Goodbye now. ").event()
        )
        await handler.handle_event(SynthesizeStop().event())

        starts = [e for e in captured if e.type == "audio-start"]
        stops = [e for e in captured if e.type == "audio-stop"]
        # First sentence flushes on the chunk, second on finish -> 2 groups.
        assert len(starts) == 2
        assert len(stops) == 2
        assert any(e.type == "synthesize-stopped" for e in captured)
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_error_event_on_failure():
    """A synth failure sends exactly one Error event and returns False."""
    failing_plugin = MagicMock()
    failing_plugin.synth.side_effect = RuntimeError("synth failed")
    failing_plugin.available_languages = ["en-US"]

    handler = _build_handler(failing_plugin)
    captured = _capture_events(handler)

    result = await handler._synthesize_and_send("test")
    assert result is False
    errors = [e for e in captured if e.type == "error"]
    assert len(errors) == 1
