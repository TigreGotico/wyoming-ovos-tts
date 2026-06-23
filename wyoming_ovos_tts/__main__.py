#!/usr/bin/env python3
import argparse
import asyncio
import io
import logging
import signal
import time
import wave
from functools import partial
from pathlib import Path
from typing import Optional

from ovos_config import Configuration
from ovos_plugin_manager.templates.tts import TTS
from ovos_plugin_manager.tts import OVOSTTSFactory
from sentence_stream import SentenceBoundaryDetector
from wyoming.audio import wav_to_chunks
from wyoming.error import Error
from wyoming.event import Event
from wyoming.info import Attribution, Describe, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncEventHandler, AsyncServer
from wyoming.tts import (
    Synthesize,
    SynthesizeStart,
    SynthesizeChunk,
    SynthesizeStop,
    SynthesizeStopped,
)

from wyoming_ovos_tts.version import __version__

_LOGGER = logging.getLogger()
_DIR = Path(__file__).parent

_SAMPLES_PER_CHUNK = 1024


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin-name", required=True,
                        help="OVOS TTS plugin to load (matches 'module' in mycroft.conf)")
    parser.add_argument("--uri", default="stdio://",
                        help="unix:// or tcp:// (default: stdio://)")
    parser.add_argument("--samples-per-chunk", type=int, default=_SAMPLES_PER_CHUNK,
                        help="Audio samples per Wyoming chunk (default: 1024)")
    parser.add_argument("--no-streaming", action="store_true",
                        help="Disable streaming TTS (SynthesizeStart/Chunk/Stop)")
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    parser.add_argument("--log-format", default=logging.BASIC_FORMAT,
                        help="Format for log messages")
    parser.add_argument("--version", action="version", version=__version__,
                        help="Print version and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format=args.log_format)
    _LOGGER.debug(args)

    cfg = Configuration().get("tts", {}).get(args.plugin_name, {})
    lang = cfg.get("lang") or Configuration().get("lang")
    tts = OVOSTTSFactory.create({"module": args.plugin_name,
                                 args.plugin_name: cfg})
    languages = list(tts.available_languages or [lang])

    supports_streaming = not args.no_streaming

    wyoming_info = Info(
        tts=[
            TtsProgram(
                name=args.plugin_name,
                description="TTS via OpenVoiceOS plugins",
                attribution=Attribution(
                    name="OpenVoiceOS",
                    url="https://github.com/OpenVoiceOS/ovos-plugin-manager",
                ),
                installed=True,
                version=__version__,
                supports_synthesize_streaming=supports_streaming,
                voices=[
                    TtsVoice(
                        name=args.plugin_name,
                        description=f"OVOS TTS Plugin: {args.plugin_name}",
                        attribution=Attribution(
                            name="OpenVoiceOS",
                            url="https://github.com/OpenVoiceOS/ovos-plugin-manager",
                        ),
                        installed=True,
                        languages=languages,
                    )
                ],
            )
        ],
    )

    _LOGGER.info("Ready")

    server = AsyncServer.from_uri(args.uri)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.ensure_future(server.stop()))

    try:
        await server.run(
            partial(OVOSTTSEventHandler, wyoming_info, args, tts)
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


# -----------------------------------------------------------------------------


class OVOSTTSEventHandler(AsyncEventHandler):
    """Wyoming event handler for TTS.

    Supports both non-streaming (Synthesize) and streaming
    (SynthesizeStart/SynthesizeChunk/SynthesizeStop) protocols.
    """

    def __init__(
            self,
            wyoming_info: Info,
            cli_args: argparse.Namespace,
            plugin: TTS,
            *args,
            **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.cli_args = cli_args
        self.wyoming_info_event = wyoming_info.event()
        self.client_id = str(time.monotonic_ns())
        self.tts = plugin
        self.is_streaming: Optional[bool] = None
        self._sbd = SentenceBoundaryDetector()
        self._samples_per_chunk = cli_args.samples_per_chunk

        _LOGGER.debug("Client connected: %s", self.client_id)

    async def _synthesize_and_send(self, text: str) -> bool:
        """Synthesize text and stream audio chunks back to client.

        Runs the blocking ``tts.synth()`` in a thread to avoid stalling
        the event loop. On failure an ``Error`` event is sent and
        ``False`` is returned; the connection is left open so the rest
        of a streaming request can continue.
        """
        try:
            audio_path, _ = await asyncio.to_thread(self.tts.synth, text)
            with open(str(audio_path.path), "rb") as audio_file:
                wav_bytes = audio_file.read()
            _LOGGER.debug("Got %s byte(s) of WAV data", len(wav_bytes))
            with io.BytesIO(wav_bytes) as wav_io:
                wav_file: wave.Wave_read = wave.open(wav_io, "rb")
                for wav_event in wav_to_chunks(
                        wav_file,
                        samples_per_chunk=self._samples_per_chunk,
                        start_event=True,
                        stop_event=True,
                ):
                    await self.write_event(wav_event.event())
            return True
        except Exception as err:
            _LOGGER.exception("Synthesis failed for text: %r", text[:80])
            await self.write_event(
                Error(text=str(err), code=err.__class__.__name__).event()
            )
            return False

    async def handle_event(self, event: Event) -> bool:
        try:
            if Describe.is_type(event.type):
                await self.write_event(self.wyoming_info_event)
                _LOGGER.debug("Sent info to client: %s", self.client_id)
                return True

            # -- Non-streaming path -------------------------------------------

            if Synthesize.is_type(event.type) and not self.is_streaming:
                synth = Synthesize.from_event(event)
                _LOGGER.debug(synth)
                if synth.text:
                    await self._synthesize_and_send(synth.text)
                return True

            # -- Streaming path -----------------------------------------------

            if SynthesizeStart.is_type(event.type):
                self.is_streaming = True
                self._sbd = SentenceBoundaryDetector()
                _LOGGER.debug("Streaming started")
                return True

            if SynthesizeChunk.is_type(event.type):
                chunk = SynthesizeChunk.from_event(event)
                for sentence in self._sbd.add_chunk(chunk.text):
                    await self._synthesize_and_send(sentence)
                return True

            if SynthesizeStop.is_type(event.type):
                remaining = self._sbd.finish().strip()
                if remaining:
                    await self._synthesize_and_send(remaining)
                self.is_streaming = None
                await self.write_event(SynthesizeStopped().event())
                _LOGGER.debug("Streaming finished")
                return True

            _LOGGER.debug("Unexpected event: type=%s, data=%s",
                          event.type, event.data)
            return True

        except Exception as err:
            await self.write_event(
                Error(text=str(err), code=err.__class__.__name__).event()
            )
            return False

    async def disconnect(self) -> None:
        _LOGGER.debug("Client disconnected: %s", self.client_id)


# -----------------------------------------------------------------------------


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
