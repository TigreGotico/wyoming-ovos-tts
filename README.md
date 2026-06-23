# Wyoming OVOS TTS Bridge

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](pyproject.toml)
[![Wyoming](https://img.shields.io/badge/wyoming-1.9+-blueviolet.svg)](https://github.com/OHF-voice/wyoming)
[![OVOS](https://img.shields.io/badge/OVOS-plugin--manager-ff69b4.svg)](https://github.com/OpenVoiceOS/ovos-plugin-manager)

Expose any [OpenVoiceOS](https://openvoiceos.org) TTS plugin as a [Wyoming protocol](https://github.com/OHF-voice/wyoming) server for use with Home Assistant, Rhasspy, and other Wyoming-compatible voice pipelines.

```
                         ┌──────────────────────────────────────┐
  Wyoming client         │         wyoming-ovos-tts              │
  (Home Assistant,       │                                      │
   Rhasspy, etc.)        │  ┌────────────────────────────────┐  │
                         │  │   OVOSTTSEventHandler          │  │
  Synthesize ───────────►│  │                                │  │
  AudioStart ◄───────────│  │  asyncio.to_thread() ──────────►│  OVOSTTSFactory
  AudioChunk* ◄──────────│  │  TTS.synth(text)               │  └──> TTS plugin
  AudioStop  ◄───────────│  │                                │
                         │  └────────────────────────────────┘  │
  Describe ─────────────►│  Info(tts=[TtsProgram(...)])         │
  Info ◄─────────────────│                                      │
                         └──────────────────────────────────────┘
```

## Features

- **Non-streaming TTS** — Single `Synthesize` event returns complete audio
- **Streaming TTS** (Wyoming v1.7+) — `SynthesizeStart`/`SynthesizeChunk`/`SynthesizeStop` with sentence-boundary-aware audio streaming (via [`sentence-stream`](https://github.com/rhasspy/sentence-stream), the same segmenter used by `wyoming-piper`) for lower latency
- **Multi-language** — Advertises the plugin's `available_languages` in the Wyoming `Info` response
- **Thread-safe** — Blocking `tts.synth()` is offloaded via `asyncio.to_thread()` so the event loop stays responsive
- **Error reporting** — Failures are sent back as Wyoming `Error` events
- **Signal handling** — Graceful shutdown on SIGINT/SIGTERM

## Installation

### From PyPI

```bash
pip install wyoming-ovos-tts
```

You also need to install the OVOS TTS plugin you intend to bridge, e.g.:

```bash
pip install ovos-tts-plugin-server
pip install ovos-tts-plugin-piper
```

### From source

```bash
git clone https://github.com/OpenVoiceOS/wyoming-ovos-tts.git
cd wyoming-ovos-tts
pip install -e .
```

## Configuration

Plugin configuration is read from `mycroft.conf` under `tts.<plugin-name>`:

```json
{
  "lang": "en-US",
  "tts": {
    "ovos-tts-plugin-server": {
      "host": "https://pipertts.ziggyai.online"
    },
    "ovos-tts-plugin-piper": {
      "voice": "en_US-lessac-medium"
    },
    "ovos-tts-plugin-espeak": {
      "voice": "en+f3"
    }
  }
}
```

The language is taken from `tts.<plugin-name>.lang` if set, otherwise from `lang` at the root level. Each plugin's config section must match the value passed to `--plugin-name`.

## Usage

```bash
# TCP server using public OVOS TTS servers
wyoming-ovos-tts --uri tcp://0.0.0.0:7892 \
                 --plugin-name ovos-tts-plugin-server \
                 --debug

# With streaming disabled (requires wyoming info)
wyoming-ovos-tts --uri tcp://0.0.0.0:7892 \
                 --plugin-name ovos-tts-plugin-piper \
                 --no-streaming

# Unix socket
wyoming-ovos-tts --uri unix:///run/wyoming-tts.sock \
                 --plugin-name ovos-tts-plugin-server

# Over stdio (for subprocess usage)
wyoming-ovos-tts --plugin-name ovos-tts-plugin-server
```

## CLI Reference

| Argument | Required | Default | Description |
|---|---|---|---|
| `--plugin-name` | Yes | — | OVOS TTS plugin module name (e.g. `ovos-tts-plugin-server`) |
| `--uri` | No | `stdio://` | `tcp://HOST:PORT`, `unix:///path`, or `stdio://` |
| `--samples-per-chunk` | No | `1024` | Audio samples per Wyoming `AudioChunk` event |
| `--no-streaming` | No | `False` | Disable streaming TTS protocol (only `Synthesize`) |
| `--debug` | No | `False` | Enable DEBUG-level logging |
| `--log-format` | No | `%(levelname)s:%(name)s:%(message)s` | Python log format string |
| `--version` | No | — | Print version and exit |

## Wyoming Protocol

### Non-streaming flow

```
Client → Describe
Server → Info(tts=[TtsProgram(supports_synthesize_streaming=True, ...)])

Client → Synthesize(text="Hello world", voice=VoiceSettings(...))
Server → AudioStart(rate=22050, width=2, channels=1)
       → AudioChunk (1024 samples of PCM)
       → AudioChunk ...
       → AudioStop
```

### Streaming flow (v1.7+)

```
Client → SynthesizeStart
Client → SynthesizeChunk(text="Hello. ")
Server → AudioStart → AudioChunk+ → AudioStop   (sentence "Hello.")
Client → SynthesizeChunk(text="How are you? I'm ")
Server → AudioStart → AudioChunk+ → AudioStop   (sentence "How are you?")
Client → SynthesizeChunk(text="fine.")
Client → SynthesizeStop
Server → AudioStart → AudioChunk+ → AudioStop   (sentence "I'm fine.")
Server → SynthesizeStopped
```

When `--no-streaming` is not set, incoming text is segmented into complete sentences by [`sentence-stream`](https://github.com/rhasspy/sentence-stream) — which correctly handles abbreviations (`Dr.`), decimals (`3.14`), ellipses and non-Latin scripts — and each sentence is synthesized and streamed as its own `AudioStart`→`AudioChunk`→`AudioStop` group as soon as it is complete. This lowers time-to-first-audio compared to the non-streaming path. A trailing partial sentence is flushed when `SynthesizeStop` arrives, followed by a single `SynthesizeStopped`.

## Supported Plugin Types

Any OVOS STT plugin implementing `TTS` from `ovos_plugin_manager.templates.tts`:

- `ovos-tts-plugin-server` — proxy to remote TTS servers
- `ovos-tts-plugin-piper` — local Piper TTS
- `ovos-tts-plugin-espeak` — eSpeak NG synthesizer
- `ovos-tts-plugin-mimic` — Mycroft Mimic
- `ovos-tts-plugin-google-tx` — Google Translate TTS
- `ovos-tts-plugin-nos` — NOS TTS
- `ovos-tts-plugin-sam` — Software Automatic Mouth
- `ovos-tts-plugin-azure` — Microsoft Azure Cognitive Services
- `ovos-tts-plugin-ibm` — IBM Watson TTS
- `ovos-tts-plugin-amazon` — Amazon Polly TTS

## Credits

Developed by [TigreGótico](https://tigregotico.pt) for [OpenVoiceOS](https://openvoiceos.org).

[![NGI0 Commons Fund](./ngi.png)](https://nlnet.nl/project/OpenVoiceOS)

This project was funded through the [NGI0 Commons Fund](https://nlnet.nl/commonsfund),
a fund established by [NLnet](https://nlnet.nl) with financial support from the
European Commission's [Next Generation Internet](https://ngi.eu) programme, under
the aegis of [DG Communications Networks, Content and Technology](https://commission.europa.eu/about-european-commission/departments-and-executive-agencies/communications-networks-content-and-technology_en)
under grant agreement No [101135429](https://cordis.europa.eu/project/id/101135429).
