"""Tests for sentence-boundary extraction utility."""

from wyoming_ovos_tts.__main__ import _extract_sentences


def test_empty_buffer() -> None:
    assert _extract_sentences("") == ([], "")


def test_single_complete_sentence() -> None:
    sentences, rest = _extract_sentences("Hello world.")
    assert sentences == ["Hello world."]
    assert rest == ""


def test_single_incomplete() -> None:
    sentences, rest = _extract_sentences("Hello world")
    assert sentences == []
    assert rest == "Hello world"


def test_two_complete() -> None:
    sentences, rest = _extract_sentences("Hi there. How are you?")
    assert sentences == ["Hi there.", "How are you?"]
    assert rest == ""


def test_complete_then_partial() -> None:
    sentences, rest = _extract_sentences("First sentence. Second is not")
    assert sentences == ["First sentence."]
    assert rest == "Second is not"


def test_multiple_sentences_various_punctuation() -> None:
    sentences, rest = _extract_sentences("Stop! No way. Really? Maybe")
    assert sentences == ["Stop!", "No way.", "Really?"]
    assert rest == "Maybe"


def test_exclamation_and_question() -> None:
    sentences, rest = _extract_sentences("Wow! What now? Done.")
    assert sentences == ["Wow!", "What now?", "Done."]
    assert rest == ""


def test_buffer_with_only_partial_words() -> None:
    sentences, rest = _extract_sentences("He")
    assert sentences == []
    assert rest == "He"


def test_whitespace_handling() -> None:
    sentences, rest = _extract_sentences("  Hello.   World!   ")
    assert sentences == ["Hello.", "World!"]
    assert rest == ""
