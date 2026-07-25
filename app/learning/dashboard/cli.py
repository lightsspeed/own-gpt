"""
Learning Dashboard — CLI display for telemetry counters.

Usage:
    python -m app.learning.dashboard.cli
"""

from __future__ import annotations

from ..storage.sqlite import LearningStore


def render_dashboard(store: LearningStore | None = None) -> str:
    store = store or LearningStore()
    records = store.count_records()
    events = store.count_events()
    by_type = store.count_events_by_type()
    by_intent = store.count_records_by_intent()

    thumbs_up = by_type.get("thumb_up", 0)
    thumbs_down = by_type.get("thumb_down", 0)
    total_thumbs = thumbs_up + thumbs_down
    thumb_rate = round(thumbs_up / total_thumbs * 100, 1) if total_thumbs else 0

    copies = by_type.get("copy", 0)
    regens = by_type.get("regenerate", 0)
    feedback = by_type.get("feedback", 0)

    lines = []
    lines.append("=" * 60)
    lines.append("  Learning Ledger Dashboard")
    lines.append("=" * 60)
    lines.append(f"  Learning Records                {records:>8d}")
    lines.append(f"  User Events                     {events:>8d}")
    lines.append(f"  Feedback                        {feedback:>8d}")
    lines.append("")
    lines.append(f"  Thumbs Up                       {thumbs_up:>8d}")
    lines.append(f"  Thumbs Down                     {thumbs_down:>8d}")
    lines.append(f"  Approval Rate                   {thumb_rate:>7.1f}%")
    lines.append(f"  Copies                          {copies:>8d}")
    lines.append(f"  Regenerations                   {regens:>8d}")
    lines.append("")
    lines.append("  By Intent:")
    for intent, count in sorted(by_intent.items(), key=lambda x: -x[1]):
        bar = "#" * min(count, 40)
        lines.append(f"    {intent:20s} {count:>5d}  {bar}")
    lines.append("")
    lines.append("  By Event Type:")
    for etype, count in sorted(by_type.items(), key=lambda x: -x[1]):
        bar = "#" * min(count, 40)
        lines.append(f"    {etype:25s} {count:>5d}  {bar}")
    lines.append("=" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    print(render_dashboard())
