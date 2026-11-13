import pandas as pd

from src.match_context import build_match_context, context_audit


def _fixtures():
    # Deliberately out of order to test explicit delivery ordering.
    ball_by_ball = pd.DataFrame(
        {
            "match_id": [10, 10, 10, 10],
            "innings": [1, 1, 1, 1],
            "innings_ball_num": [3, 1, 2, 4],
            "overid": [1, 1, 1, 1],
            "is_wicket": [False, False, True, False],
            "striker_id": [3, 1, 2, 4],
        }
    )
    matches = pd.DataFrame({"match_id": [10], "comp_id": [7]})
    competitions = pd.DataFrame(
        {"comp_id": [7], "comp_name": ["Example T20"], "match_format": ["T20"]}
    )
    return ball_by_ball, matches, competitions


def test_wickets_before_excludes_current_delivery_wicket():
    ball_by_ball, matches, competitions = _fixtures()
    context = build_match_context(ball_by_ball, matches, competitions)

    assert context["innings_ball_num"].tolist() == [1, 2, 3, 4]
    assert context["wickets_before"].tolist() == [0, 0, 1, 1]
    assert context["wickets_after"].tolist() == [0, 1, 1, 1]
    assert context["is_regular_innings"].all()
    assert context["comp_name"].eq("Example T20").all()


def test_context_does_not_mutate_source_delivery_data():
    ball_by_ball, matches, competitions = _fixtures()
    original_columns = list(ball_by_ball.columns)
    original_order = ball_by_ball["innings_ball_num"].tolist()

    build_match_context(ball_by_ball, matches, competitions)

    assert list(ball_by_ball.columns) == original_columns
    assert ball_by_ball["innings_ball_num"].tolist() == original_order


def test_context_audit_reports_contiguous_sequence():
    ball_by_ball, matches, competitions = _fixtures()
    context = build_match_context(ball_by_ball, matches, competitions)
    audit = context_audit(context)

    assert audit["delivery_records"] == 4
    assert audit["innings_groups"] == 1
    assert audit["duplicate_delivery_numbers"] == 0
    assert audit["innings_groups_not_starting_at_ball_1"] == 0
    assert audit["innings_groups_with_sequence_gaps"] == 0
    assert audit["wicket_state_monotonic"] is True
