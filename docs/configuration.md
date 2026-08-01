# Configuration

CLI flags configure the bridge itself. The **TTS plugin** is configured
through `mycroft.conf` (the standard OVOS config stack), read at startup.

## CLI

| Argument | Required | Default | Meaning |
| --- | --- | --- | --- |
| `--plugin-name` | Yes | none | OVOS TTS plugin module name (e.g. `ovos-tts-plugin-server`) |
| `--uri` | No | `stdio://` | `tcp://HOST:PORT`, `unix:///path`, or `stdio://` |
| `--samples-per-chunk` | No | `1024` | audio samples per Wyoming `AudioChunk` |
| `--no-streaming` | No | `False` | disable the streaming protocol (only `Synthesize`) |
| `--debug` | No | `False` | DEBUG-level logging |
| `--log-format` | No | `%(levelname)s:%(name)s:%(message)s` | Python log format |
| `--version` | No | none | print version and exit |

`--no-streaming` also advertises `supports_synthesize_streaming=False` in `Info`.
Clients then fall back to the one-shot `Synthesize` flow.

## Plugin configuration

The bridge reads plugin settings from `mycroft.conf`, under `tts.<plugin-name>`. The
section key must match the value passed to `--plugin-name`:

```json
{
  "lang": "en-US",
  "tts": {
    "ovos-tts-plugin-server": {
      "host": "https://pipertts.ziggyai.online"
    },
    "ovos-tts-plugin-piper": {
      "voice": "en_US-lessac-medium"
    }
  }
}
```

The language advertised in `Info` comes from `tts.<plugin-name>.lang` if set,
otherwise from the top-level `lang`.

## Supported plugins

The bridge supports any plugin implementing `TTS` from
`ovos_plugin_manager.templates.tts`, for example `ovos-tts-plugin-server`,
`ovos-tts-plugin-piper`, and `ovos-tts-plugin-mimic3`. Install the plugin
alongside the bridge. It is not pulled in automatically.

---
[Home](index.md) · [Home Assistant →](home_assistant.md)
