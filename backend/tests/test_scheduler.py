from datetime import date, timedelta

from app.services.scheduler import Booked, TopicState, build_plan, first_free, score_topic

TODAY = date(2030, 1, 1)


def topic(i, subject=1, **kw):
    return TopicState(topic_id=i, subject_id=subject, name=f"T{i}", subject_name=f"S{subject}", **kw)


def test_first_free_finds_gap_and_respects_limit():
    assert first_free([], 30, 120) == 0
    assert first_free([(0, 30), (60, 90)], 30, 120) == 30
    assert first_free([(0, 100)], 30, 120) is None


def test_daily_budget_and_no_overlap():
    topics = [topic(i, subject=1 + i % 3, estimated_minutes=40) for i in range(10)]
    booked = [Booked(TODAY, 0, 30)]
    plan = build_plan(topics, booked, TODAY, 5, daily_minutes=100, session_minutes=40)
    for d in {p.scheduled_date for p in plan}:
        day = sorted([(p.start_minute, p.start_minute + p.duration_minutes) for p in plan if p.scheduled_date == d]
                     + ([(0, 30)] if d == TODAY else []))
        assert sum(e - s for s, e in day) <= 100
        assert all(day[i][1] <= day[i + 1][0] for i in range(len(day) - 1))


def test_weak_urgent_topic_ranked_above_strong_topic():
    weak = topic(1, predicted_p=0.2, recent_accuracy=0.2, recent_wrong=4, exam_date=TODAY + timedelta(days=3))
    strong = topic(2, predicted_p=0.95, recent_accuracy=1.0, days_since_revision=0)
    assert score_topic(weak, TODAY, TODAY)[0] > score_topic(strong, TODAY, TODAY)[0]
    plan = build_plan([strong, weak], [], TODAY, 1, 30, 30)
    assert plan[0].topic_id == 1 and "exam in 3 days" in plan[0].reason


def test_no_sessions_on_or_after_exam_day():
    t = topic(1, exam_date=TODAY + timedelta(days=2))
    plan = build_plan([t], [], TODAY, 7, 60, 30)
    assert plan and all(p.scheduled_date < TODAY + timedelta(days=2) for p in plan)


def test_each_topic_at_most_once_per_day_and_subjects_not_starved():
    topics = [topic(1, 1, predicted_p=0.1), topic(2, 1, predicted_p=0.1), topic(3, 2, predicted_p=0.6)]
    plan = build_plan(topics, [], TODAY, 1, 90, 30)
    assert len({p.topic_id for p in plan}) == len(plan)
    assert {p.subject_id for p in plan} == {1, 2}


def test_missed_sessions_raise_priority():
    a, b = topic(1, days_since_revision=2), topic(2, days_since_revision=2, missed_count=2)
    assert score_topic(b, TODAY, TODAY)[0] > score_topic(a, TODAY, TODAY)[0]


def test_reason_labels_prediction_as_estimate_or_missing():
    assert "estimate" in score_topic(topic(1, predicted_p=0.4), TODAY, TODAY)[2]
    assert "no model estimate" in score_topic(topic(1), TODAY, TODAY)[2]
