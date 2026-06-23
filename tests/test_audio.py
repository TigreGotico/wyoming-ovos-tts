"""Tests for audio generation and streaming behaviour."""

from asyncio import StreamReader, StreamWriter
from unittest.mock import MagicMock, patch

import pytest
from wyoming.event import Event
from wyoming.info import Attribution, Info, TtsProgram
from wyoming.tts import Synthesize, SynthesizeStart, SynthesizeChunk, SynthesizeStop

from wyoming_ovos_tts.__main__ import OVOSTTSEventHandler


def _streams():
    return MagicMock(spec=StreamReader), MagicMock(spec=StreamWriter)


def _handler(plugin=None):
    reader, writer = _streams()
    if plugin is None:
        plugin = MagicMock()
        plugin.available_languages = ["en-US"]
    attr = Attribution(name="test", url="https://example.com")

    class MockArgs:
        samples_per_chunk = 256

    wyoming_info = Info(tts=[
        TtsProgram(name="test", attribution=attr, description="test",
                   installed=True, version="1.0",
                   supports_synthesize_streaming=True, voices=[])
    ])
    return OVOSTTSEventHandler(wyoming_info, MockArgs(), plugin,
                                reader=reader, writer=writer)


@pytest.mark.asyncio
async def test_synthesize_stop_without_start():
    """SynthesizeStop without a preceding Start does not crash."""
    handler = _handler()
    handler.is_streaming = None
    result = await handler.handle_event(SynthesizeStop().event())
    assert result is True


@pytest.mark.asyncio
async def test_streaming_chunk_before_start():
    """SynthesizeChunk without a preceding Start does not crash."""
    handler = _handler()
    handler.is_streaming = None
    result = await handler.handle_event(SynthesizeChunk(text="hello").event())
    assert result is True


@pytest.mark.asyncio
async def test_synthesize_while_streaming():
    """Non-streaming Synthesize during streaming still works."""
    handler = _handler()
    handler.is_streaming = True
    result = await handler.handle_event(
        Event(type="synthesize", data={"text": "hello"})
    )
    assert result is True


@pytest.mark.asyncio
async def test_multiple_sentence_chunks():
    """A chunk with multiple complete sentences synthesizes each one."""
    handler = _handler()
    sent = []

    async def fake_send(text):
        sent.append(text)
        return True

    handler._synthesize_and_send = fake_send

    await handler.handle_event(SynthesizeStart().event())
    # Trailing capitalized sentence makes both prior boundaries flush.
    await handler.handle_event(
        SynthesizeChunk(text="First. Second! Third? Go.").event()
    )
    assert sent == ["First.", "Second!", "Third?"]


@pytest.mark.asyncio
async def test_synthesize_empty_text():
    """Empty Synthesize text does not crash."""
    handler = _handler()
    handler.is_streaming = None
    result = await handler.handle_event(
        Event(type="synthesize", data={"text": ""})
    )
    assert result is True


@pytest.mark.asyncio
async def test_handler_accepts_describe_always():
    """Describe event is always accepted regardless of state."""
    handler = _handler()
    for streaming_state in (None, True, False):
        handler.is_streaming = streaming_state
        result = await handler.handle_event(
            Event(type="describe")
        )
        assert result is True
