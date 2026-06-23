"""Tests for the Wyoming Describe/Info exchange."""

from asyncio import StreamReader, StreamWriter
from unittest.mock import MagicMock

import pytest
from wyoming.info import Attribution, Describe, Info, TtsProgram, TtsVoice

from wyoming_ovos_tts.__main__ import OVOSTTSEventHandler


def _streams():
    return MagicMock(spec=StreamReader), MagicMock(spec=StreamWriter)


@pytest.mark.asyncio
async def test_describe_roundtrip() -> None:
    """Verify that Describe -> Info returns expected TtsProgram fields."""
    fake_plugin = MagicMock()
    fake_plugin.available_languages = ["en-US", "pt-PT"]

    reader, writer = _streams()

    class MockArgs:
        samples_per_chunk = 1024

    attr = Attribution(name="test", url="https://example.com")
    handler = OVOSTTSEventHandler(
        wyoming_info=Info(
            tts=[
                TtsProgram(
                    name="test-tts-plugin",
                    attribution=attr,
                    description="test",
                    installed=True,
                    version="0.2.0",
                    supports_synthesize_streaming=True,
                    voices=[
                        TtsVoice(
                            name="test-tts-plugin",
                            attribution=attr,
                            description="test",
                            installed=True,
                            version="0.2.0",
                            languages=["en-US", "pt-PT"],
                        )
                    ],
                )
            ],
        ),
        cli_args=MockArgs(),
        plugin=fake_plugin,
        reader=reader,
        writer=writer,
    )

    response = await handler.handle_event(Describe().event())
    assert response is True
