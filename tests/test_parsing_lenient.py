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
