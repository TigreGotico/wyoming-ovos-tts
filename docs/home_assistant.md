# Home Assistant integration

The bridge speaks the Wyoming protocol, so Home Assistant talks to it through the
[Wyoming integration](https://www.home-assistant.io/integrations/wyoming/).

## Add the service

1. Run the bridge on a TCP URI reachable from Home Assistant:

   ```bash
   wyoming-ovos-tts --uri tcp://0.0.0.0:7892 \
                    --plugin-name ovos-tts-plugin-server
   ```

2. In Home Assistant, go to **Settings → Devices & Services → Add Integration →
   Wyoming Protocol**, and enter the bridge host and port (`7892` above).

3. The new entry exposes a text-to-speech engine. Select it in your
   [Assist pipeline](https://www.home-assistant.io/voice_control/), under
   **Text-to-speech**.

## Streaming

When the client and `Info` both support it, Home Assistant streams text to the
bridge (`SynthesizeStart` → `SynthesizeChunk`* → `SynthesizeStop`). The bridge
synthesizes each complete sentence as it arrives, lowering time-to-first-audio.
This is most noticeable with LLM-driven responses. Pass `--no-streaming` to
disable it and force the one-shot path. See [protocol](protocol.md) for details.

## Notes

- Run one bridge process per TTS plugin/port if you want to offer several voices
  or engines.
- The plugin produces a WAV. The bridge re-chunks it into `AudioChunk`s of
  `--samples-per-chunk` samples.

---
[← Configuration](configuration.md) · [Home](index.md) · [Wyoming protocol →](protocol.md)
