"""Transparent, deterministic revision scheduler (no database access, easy to test).

The Transformer only *estimates* how likely the student is to answer correctly. This module
decides what to revise using those estimates plus plain rules.

Priority score for a topic on a given day (all components are in [0, 1]):

    score = 0.30 * weakness       1 - P(correct)   (model estimate; falls back to recent accuracy, else 0.5)
          + 0.20 * recent_error   1 - accuracy over the last 5 answers on the topic (0.5 if none)
          + 0.15 * overdue        days since last revision / 7, capped at 1 (never revised = 1)
          + 0.10 * failures       wrong answers among the last 5, / 5
          + 0.20 * urgency        1 - days_to_exam / 30, capped (no exam = 0.1)
          + 0.05 * difficulty     (topic difficulty - 1) / 4
          + 0.10 * missed_bonus   0.5 per missed session in the last 14 days, capped at 1

The weights are hand-chosen, documented heuristics, not learned. Scores are estimates.

Constraints (hard rules, never delegated to the model):
  * a day's sessions never exceed the daily study minutes (including already-booked sessions)
  * sessions never overlap (each is placed in the first free gap)
  * a topic appears at most once per day, never on/after its subject's exam day
  * a repeat-penalty and a same-subject-per-day penalty stop one topic or subject starving the rest
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

WEIGHTS = {
    "weakness": 0.30, "recent_error": 0.20, "overdue": 0.15,
    "failures": 0.10, "urgency": 0.20, "difficulty": 0.05, "missed": 0.10,
}
MIN_SESSION = 10
TOPIC_REPEAT_PENALTY = 0.6
SUBJECT_DAY_PENALTY = 0.15


@dataclass
class TopicState:
    topic_id: int
    subject_id: int
    name: str
    subject_name: str
    difficulty: int = 3
    estimated_minutes: int = 30
    predicted_p: float | None = None
    model_version: str | None = None
    recent_accuracy: float | None = None   # over last 5 answers on this topic
    recent_wrong: int = 0                  # wrong answers among last 5
    n_events: int = 0
    days_since_revision: int | None = None  # as of `today`; None = never revised
    missed_count: int = 0
    exam_date: date | None = None


@dataclass
class Booked:
    scheduled_date: date
    start_minute: int
    duration_minutes: int


@dataclass
class PlannedSession:
    topic_id: int
    subject_id: int
    scheduled_date: date
    start_minute: int
    duration_minutes: int
    priority_score: float
    reason: str
    predicted_p: float | None
    model_version: str | None


def score_topic(t: TopicState, day: date, today: date) -> tuple[float, dict, str]:
    if t.predicted_p is not None:
        p = t.predicted_p
    elif t.recent_accuracy is not None:
        p = t.recent_accuracy
    else:
        p = 0.5
    weakness = 1 - p
    recent_error = 0.5 if t.recent_accuracy is None else 1 - t.recent_accuracy
    if t.days_since_revision is None:
        overdue, since = 1.0, None
    else:
        since = t.days_since_revision + (day - today).days
        overdue = min(since / 7, 1.0)
    failures = min(t.recent_wrong / 5, 1.0)
    days_left = (t.exam_date - day).days if t.exam_date else None
    urgency = 0.1 if days_left is None else 1 - min(max(days_left, 0), 30) / 30
    difficulty = (t.difficulty - 1) / 4
    missed = min(t.missed_count * 0.5, 1.0)

    comps = {
        "weakness": weakness, "recent_error": recent_error, "overdue": overdue,
        "failures": failures, "urgency": urgency, "difficulty": difficulty, "missed": missed,
    }
    score = sum(WEIGHTS[k] * v for k, v in comps.items())

    parts = []
    if days_left is not None:
        parts.append(f"exam in {days_left} day{'s' if days_left != 1 else ''}")
    if t.predicted_p is not None:
        parts.append(f"model estimates a {t.predicted_p:.0%} chance of answering correctly (an estimate, not a measurement)")
    else:
        parts.append("no model estimate available" + (" (using recent accuracy)" if t.recent_accuracy is not None else " (no quiz data yet)"))
    if t.recent_accuracy is not None:
        parts.append(f"recent answers {round(t.recent_accuracy * min(5, t.n_events))}/{min(5, t.n_events)} correct")
    parts.append("never revised" if since is None else f"last revised {since} day{'s' if since != 1 else ''} ago")
    if t.missed_count:
        parts.append(f"{t.missed_count} recently missed session{'s' if t.missed_count != 1 else ''}")
    if t.difficulty >= 4:
        parts.append(f"difficulty {t.difficulty}/5")
    return score, comps, f"Priority {score:.2f}: " + "; ".join(parts) + "."


def first_free(intervals: list[tuple[int, int]], duration: int, limit: int) -> int | None:
    """Start minute of the first gap of `duration` minutes that ends within `limit`; else None."""
    cursor = 0
    for start, end in sorted(intervals):
        if start - cursor >= duration:
            return cursor
        cursor = max(cursor, end)
    return cursor if cursor + duration <= limit else None


def build_plan(
    topics: list[TopicState],
    booked: list[Booked],
    today: date,
    horizon_days: int,
    daily_minutes: int,
    session_minutes: int,
) -> list[PlannedSession]:
    plan: list[PlannedSession] = []
    repeats: dict[int, int] = {}

    for offset in range(horizon_days):
        day = today + timedelta(days=offset)
        intervals = [(b.start_minute, b.start_minute + b.duration_minutes)
                     for b in booked if b.scheduled_date == day]
        used = sum(b.duration_minutes for b in booked if b.scheduled_date == day)
        remaining = daily_minutes - used
        subject_today: dict[int, int] = {}
        done_today: set[int] = set()

        while remaining >= MIN_SESSION:
            best = None
            for t in topics:
                if t.topic_id in done_today:
                    continue
                if t.exam_date is not None and t.exam_date <= day:
                    continue  # exam already happening / over
                score, _, reason = score_topic(t, day, today)
                eff = (score / (1 + TOPIC_REPEAT_PENALTY * repeats.get(t.topic_id, 0))
                       * (1 - SUBJECT_DAY_PENALTY * subject_today.get(t.subject_id, 0)))
                if best is None or eff > best[0]:
                    best = (eff, t, score, reason)
            if best is None:
                break
            _, t, score, reason = best
            duration = max(MIN_SESSION, min(t.estimated_minutes, session_minutes))
            duration = min(duration, remaining)
            if duration < MIN_SESSION:
                break
            start = first_free(intervals, duration, daily_minutes)
            if start is None:
                break
            intervals.append((start, start + duration))
            remaining -= duration
            done_today.add(t.topic_id)
            subject_today[t.subject_id] = subject_today.get(t.subject_id, 0) + 1
            repeats[t.topic_id] = repeats.get(t.topic_id, 0) + 1
            plan.append(PlannedSession(
                topic_id=t.topic_id, subject_id=t.subject_id, scheduled_date=day,
                start_minute=start, duration_minutes=duration,
                priority_score=round(score, 4), reason=reason,
                predicted_p=t.predicted_p, model_version=t.model_version,
            ))
    return plan
