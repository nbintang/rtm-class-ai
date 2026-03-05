from __future__ import annotations

from src.agent.runtime_helpers.parsing import try_parse_generated_payload


def test_try_parse_generated_payload_accepts_common_non_strict_json() -> None:
    reply = """
```json
{
  'summary': {
    'title': 'Ringkas',
    'overview': 'Materi inti.',
    'key_points': ['A',],
  },
}
```
"""
    parsed = try_parse_generated_payload(reply)
    assert parsed is not None
    assert parsed.summary is not None
    assert parsed.summary.title == "Ringkas"


def test_try_parse_generated_payload_handles_smart_quotes() -> None:
    reply = """
{
  “summary”: {
    “title”: “Ringkas”,
    “overview”: “Materi inti.”,
    “key_points”: [“A”, “B”]
  }
}
"""
    parsed = try_parse_generated_payload(reply)
    assert parsed is not None
    assert parsed.summary is not None
    assert parsed.summary.key_points == ["A", "B"]


def test_try_parse_generated_payload_maps_mcq_answer_label_to_option() -> None:
    reply = """
{
  "mcq_quiz": {
    "questions": [
      {
        "question": "Apa manfaat AI?",
        "options": [
          "A. Membantu otomatisasi",
          "B. Menghambat produktivitas",
          "C. Tidak berdampak",
          "D. Semua salah"
        ],
        "correct_answer": "A",
        "explanation": "AI membantu proses otomatisasi."
      }
    ]
  }
}
"""
    parsed = try_parse_generated_payload(reply)
    assert parsed is not None
    assert parsed.mcq_quiz is not None
    assert len(parsed.mcq_quiz.questions) == 1
    assert parsed.mcq_quiz.questions[0].correct_answer == "A. Membantu otomatisasi"


def test_try_parse_generated_payload_trims_mcq_options_to_four() -> None:
    reply = """
{
  "mcq_quiz": {
    "questions": [
      {
        "question": "Pilih jawaban benar.",
        "options": ["A", "B", "C", "D", "E"],
        "correct_answer": "E",
        "explanation": "Pilihan E semula benar."
      }
    ]
  }
}
"""
    parsed = try_parse_generated_payload(reply)
    assert parsed is not None
    assert parsed.mcq_quiz is not None
    assert len(parsed.mcq_quiz.questions[0].options) == 4
    assert parsed.mcq_quiz.questions[0].correct_answer in parsed.mcq_quiz.questions[0].options
