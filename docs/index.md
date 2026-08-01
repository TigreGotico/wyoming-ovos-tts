# wyoming-ovos-tts documentation

This bridge exposes any [OpenVoiceOS](https://openvoiceos.org) TTS plugin as a
[Wyoming protocol](https://github.com/OHF-voice/wyoming) server, for use with
Home Assistant, Rhasspy, and other Wyoming-compatible voice pipelines.

The bridge loads one OVOS `TTS` plugin (selected with `--plugin-name`), runs the
plugin's blocking `synth()` off the event loop, and streams the resulting audio
back as Wyoming `AudioChunk`s. It supports both the one-shot `Synthesize` flow and
the incremental `SynthesizeStart`/`Chunk`/`Stop` streaming flow.

## Pages

- **[Configuration](configuration.md)**: selecting a plugin, its `mycroft.conf`
  settings, and the streaming CLI flags.
- **[Home Assistant](home_assistant.md)**: adding the bridge as a Wyoming TTS
  service.
- **[Wyoming protocol](protocol.md)**: the non-streaming and streaming flows,
  and how sentences are segmented for low-latency streaming.

## Quickstart

```bash
pip install wyoming-ovos-tts ovos-tts-plugin-server

wyoming-ovos-tts --uri tcp://0.0.0.0:7892 \
                 --plugin-name ovos-tts-plugin-server
```

Point Home Assistant's Wyoming integration at `host:7892`. See
[Home Assistant](home_assistant.md).

## Docker

```bash
docker build -t wyoming-ovos-tts .
docker run --rm -p 7892:7892 wyoming-ovos-tts \
    --uri tcp://0.0.0.0:7892 --plugin-name ovos-tts-plugin-server
```

The image installs the package (and its dependencies) from `pyproject.toml`. Add
any extra TTS plugin you intend to load to the image, or mount its config.
