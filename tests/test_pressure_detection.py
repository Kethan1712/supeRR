import pandas as pd
import pytest

from src.pressure_detection import add_pressure_flags, pressure_audit


def _context(rows, *, revised_first=None, revised_second=None, innings=1):
    return pd.DataFrame(
        {
            "match_id": [101] * len(rows),
            "innings": [innings] * len(rows),
            "overid": [row[0] for row in rows],
            "wickets_before": [row[1] for row in rows],
            "wickets_after": [row[2] for row in rows],
            "is_regular_innings": [innings in (1, 2)] * len(rows),
            "match_format": ["T20"] * len(rows),
            "first_inn_revised_overs": [revised_first] * len(rows),
            "second_inn_revised_overs": [revised_second] * len(rows),
        }
    )


def test_early_collapse_flag_starts_after_fifth_wicket_and_persists():
    # Fifth wicket falls in over 10. That delivery has only four wickets
    # before it and is not pressure under the early-collapse rule.
    rows = [(10, 4, 5), (10, 5, 5), (11, 5, 5), (12, 5, 5)]
    result = add_pressure_flags(_context(rows))
    assert result["is_early_collapse_pressure"].tolist() == [False, True, True, True]


def test_fifth_wicket_after_threshold_does_not_trigger_early_collapse():
    rows = [(11, 4, 5), (12, 5, 5)]
    result = add_pressure_flags(_context(rows))
    assert not result["early_collapse_triggered"].any()
    assert not result["is_early_collapse_pressure"].any()


def test_death_phase_standard_t20_starts_in_over_16_without_wicket_condition():
    rows = [(15, 0, 0), (16, 0, 0), (20, 2, 2)]
    result = add_pressure_flags(_context(rows))
    assert result["is_death_over_pressure"].tolist() == [False, True, True]


def test_reduced_15_over_innings_scales_death_and_collapse_boundaries():
    rows = [(7, 4, 5), (8, 5, 5), (11, 5, 5), (12, 0, 0), (15, 0, 0)]
    result = add_pressure_flags(_context(rows, revised_first=90))
    assert result["early_collapse_threshold_over"].eq(8).all()
    assert result["death_phase_start_over"].eq(12).all()
    assert result["is_early_collapse_pressure"].tolist() == [False, True, True, False, False]
    assert result["is_death_over_pressure"].tolist() == [False, False, False, True, True]


def test_second_innings_inherits_first_revised_allocation_when_own_value_missing():
    rows = [(5, 0, 0), (6, 4, 5), (7, 5, 5)]
    result = add_pressure_flags(
        _context(rows, revised_first=66, revised_second=None, innings=2)
    )
    assert result["allocation_balls"].eq(66).all()
    assert result["allocation_source"].eq(
        "inherited_first_innings_revised_allocation"
    ).all()
    assert result["early_collapse_threshold_over"].eq(6).all()
    assert result["death_phase_start_over"].eq(9).all()


def test_additional_innings_are_retained_but_not_pressure_classified():
    rows = [(19, 5, 5)]
    result = add_pressure_flags(_context(rows, innings=3))
    assert len(result) == 1
    assert not result["is_pressure"].any()
    assert result.loc[0, "pressure_category"] == "additional_innings_not_classified"
    assert pd.isna(result.loc[0, "allocation_balls"])


def test_revised_allocation_must_be_positive_multiple_of_six():
    rows = [(1, 0, 0)]
    with pytest.raises(ValueError, match="positive multiples of six"):
        add_pressure_flags(_context(rows, revised_first=91))


def test_pressure_audit_does_not_double_count_overlap():
    rows = [(10, 4, 5), (16, 5, 5)]
    result = add_pressure_flags(_context(rows))
    audit = pressure_audit(result)
    assert audit["early_collapse_pressure_records"] == 1
    assert audit["death_phase_pressure_records"] == 1
    assert audit["overlapping_pressure_records"] == 1
    assert audit["combined_pressure_records_without_double_counting"] == 1


def test_second_innings_inheritance_can_be_disabled_for_sensitivity():
    rows = [(5, 0, 0), (6, 4, 5), (7, 5, 5)]
    result = add_pressure_flags(
        _context(rows, revised_first=66, revised_second=None, innings=2),
        inherit_missing_second_innings_revision=False,
    )
    assert result["allocation_balls"].eq(120).all()
    assert result["allocation_source"].eq("standard_20_over_default").all()


def test_pressure_threshold_sensitivity_accepts_no_inheritance_option():
    from src.pressure_detection import pressure_threshold_sensitivity

    context = _context(
        [(5, 0, 0), (6, 4, 5), (7, 5, 5)],
        revised_first=66,
        revised_second=None,
        innings=2,
    )
    result = pressure_threshold_sensitivity(
        context,
        fractions=(0.5,),
        inherit_missing_second_innings_revision=False,
    )
    assert len(result) == 1
    assert result[0]["inherit_missing_second_innings_revision"] is False
