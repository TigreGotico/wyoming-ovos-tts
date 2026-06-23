# Configuration

The bridge itself is configured with CLI flags; the **TTS plugin** is configured
through `mycroft.conf` (the standard OVOS config stack), read at startup.

## CLI

| Argument | Required | Default | Meaning |
| --- | --- | --- | --- |
| `--plugin-name` | Yes | — | OVOS TTS plugin module name (e.g. `ovos-tts-plugin-server`) |
| `--uri` | No | `stdio://` | `tcp://HOST:PORT`, `unix:///path`, or `stdio://` |
| `--samples-per-chunk` | No | `1024` | audio samples per Wyoming `AudioChunk` |
| `--no-streaming` | No | `False` | disable the streaming protocol (only `Synthesize`) |
| `--debug` | No | `False` | DEBUG-level logging |
| `--log-format` | No | `%(levelname)s:%(name)s:%(message)s` | Python log format |
| `--version` | No | — | print version and exit |

`--no-streaming` also advertises `supports_synthesize_streaming=False` in `Info`,
so clients fall back to the one-shot `Synthesize` flow.

## Plugin configuration

Plugin settings are read from `mycroft.conf` under `tts.<plugin-name>`. The
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

The language advertised in `Info` is taken from `tts.<plugin-name>.lang` if set,
otherwise from the top-level `lang`.

## Supported plugins

Any plugin implementing `TTS` from `ovos_plugin_manager.templates.tts`, e.g.
`ovos-tts-plugin-server`, `ovos-tts-plugin-piper`, `ovos-tts-plugin-mimic3`,
`ovos-tts-plugin-azure`. Install the plugin alongside the bridge — it is not
pulled in automatically.
