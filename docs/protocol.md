# Wyoming protocol

The bridge handles both the one-shot and the streaming synthesis flows.

## Non-streaming flow

```
Client → Describe
Server → Info(tts=[TtsProgram(supports_synthesize_streaming=True, ...)])

Client → Synthesize(text="Hello world", voice=VoiceSettings(...))
Server → AudioStart(rate=22050, width=2, channels=1)
       → AudioChunk (PCM)
       → AudioChunk ...
       → AudioStop
```

## Streaming flow (Wyoming v1.7+)

```
Client → SynthesizeStart
Client → SynthesizeChunk(text="Hello. ")
Client → SynthesizeChunk(text="How are you? I'm ")
Client → SynthesizeChunk(text="fine.")
Client → SynthesizeStop
Server → AudioStart → AudioChunk+ → AudioStop   (per complete sentence)
       → ...
       → SynthesizeStopped
```

Each **complete sentence** is synthesized and streamed as its own
`AudioStart` → `AudioChunk`* → `AudioStop` group as soon as it is available. A
single `SynthesizeStopped` terminates the stream. Any trailing partial sentence
still buffered when `SynthesizeStop` arrives is flushed first.

## Sentence segmentation

The [`sentence-stream`](https://github.com/rhasspy/sentence-stream) package
detects sentence boundaries. It is the same segmenter used by upstream
`wyoming-piper`. It correctly keeps abbreviations (`Dr.`), decimals (`3.14`),
ellipses, quotes, and non-Latin scripts intact, instead of splitting on every
`.`/`!`/`?`. A boundary is only emitted once the start of the next sentence is
seen, so the bridge never speaks a fragment early.

## Threading and errors

`TTS.synth()` is blocking, so it runs via `asyncio.to_thread()`. A failure while
synthesizing one sentence comes back as a Wyoming `Error(text, code)` event, and
the rest of the stream continues. The connection is not torn down.

---
[← Home Assistant](home_assistant.md) · [Home](index.md)
