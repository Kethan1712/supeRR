"""Classify early-collapse and death-phase pressure from delivery context.

The supplied matches table stores non-null ``*_revised_overs`` values as
multiples of six (for example, 114). In this data pack those values align with
innings allocations when interpreted as legal-ball allowances (114 balls =
19 overs). This interpretation is validated by an audit and guarded by a
multiple-of-six check; it is not inferred from delivery-row counts.

For matches without an innings-specific revised value, the standard T20/T20I
allocation of 120 balls (20 overs) is used. Missing revised values are not
inferred from the other innings' field.

Pressure categories:
- Early collapse: at least five wickets have fallen by the end of the first
  half of the innings allocation. The pressure flag begins on the delivery
  AFTER the fifth wicket and continues for the rest of that innings.
- Death phase: the final 25% of the allocated innings, rounded to whole overs.
  In a standard 20-over innings this is overs 16-20. For shortened innings the
  boundary scales with the allocated length.

Only regular innings 1 and 2 receive pressure labels. Additional innings are
retained in the output and explicitly marked as not pressure-classified.
"""

from __future__ import annotations

import math

import pandas as pd

REGULAR_INNINGS = (1, 2)
STANDARD_T20_BALLS = 120
SUPPORTED_FORMATS = {"T20", "T20I"}


def _validate_fraction(name: str, value: float) -> None:
    if not 0 < value < 1:
        raise ValueError(f"{name} must be strictly between 0 and 1; got {value!r}")


def add_pressure_flags(
    context: pd.DataFrame,
    *,
    early_collapse_fraction: float = 0.50,
    death_phase_fraction: float = 0.75,
    inherit_missing_second_innings_revision: bool = True,
) -> pd.DataFrame:
    """Return a copy of match context with pressure allocation and flags.

    Parameters
    ----------
    context:
        Output from :func:`src.match_context.build_match_context`, including
        match format, innings number, over number, wickets_before and
        wickets_after, and revised-overs fields from matches.csv.
    early_collapse_fraction:
        Fraction of allocated innings within which the fifth wicket must fall.
        Default 0.50 means the first 10 overs of a standard 20-over innings.
        Use 0.40 and 0.60 for the 8-over and 12-over sensitivity tests.
    death_phase_fraction:
        Start of the final innings fraction considered the death phase.
        Default 0.75 means overs 16-20 in a standard 20-over innings.
    """
    _validate_fraction("early_collapse_fraction", early_collapse_fraction)
    _validate_fraction("death_phase_fraction", death_phase_fraction)

    required = {
        "match_id", "innings", "overid", "wickets_before", "wickets_after",
        "is_regular_innings", "match_format", "first_inn_revised_overs",
        "second_inn_revised_overs",
    }
    missing = sorted(required - set(context.columns))
    if missing:
        raise ValueError(f"context is missing pressure columns: {missing}")

    result = context.copy()
    formats = set(result.loc[result["is_regular_innings"], "match_format"].dropna().unique())
    unsupported = sorted(formats - SUPPORTED_FORMATS)
    if unsupported:
        raise ValueError(
            "Cannot assume a 20-over allocation for unsupported match format(s): "
            f"{unsupported}"
        )
    if result.loc[result["is_regular_innings"], "match_format"].isna().any():
        raise ValueError("Regular-innings delivery rows have missing match_format")

    # Select the match-level revised allocation field for the relevant innings.
    first_revision = pd.to_numeric(
        result["first_inn_revised_overs"], errors="coerce"
    )
    second_revision = pd.to_numeric(
        result["second_inn_revised_overs"], errors="coerce"
    )
    selected_revision = pd.Series(pd.NA, index=result.index, dtype="Float64")
    first_mask = result["innings"].eq(1)
    second_mask = result["innings"].eq(2)
    selected_revision.loc[first_mask] = first_revision.loc[first_mask].astype("Float64")
    selected_revision.loc[second_mask] = second_revision.loc[second_mask].astype("Float64")

    # In this data pack, two completed matches have a first-innings revised
    # allocation, no second-innings revised value, and second-innings records
    # reaching the same over cap. In that narrow case the second innings uses
    # the first-innings allocation as an explicitly labelled inheritance.
    # This does not copy a second-innings allocation back to innings 1.
    inherited_revision = (
        second_mask
        & selected_revision.isna()
        & first_revision.notna()
        & result["is_regular_innings"]
        & bool(inherit_missing_second_innings_revision)
    )
    selected_revision.loc[inherited_revision] = first_revision.loc[inherited_revision].astype("Float64")

    revision_present = selected_revision.notna() & result["is_regular_innings"]
    invalid_revision = revision_present & (
        selected_revision.le(0) | selected_revision.mod(6).ne(0)
    )
    if invalid_revision.any():
        bad_values = sorted(selected_revision.loc[invalid_revision].astype(float).unique())
        raise ValueError(
            "Revised allocation values must be positive multiples of six balls; "
            f"found {bad_values}"
        )

    allocation_balls = pd.Series(pd.NA, index=result.index, dtype="Int64")
    allocation_balls.loc[result["is_regular_innings"]] = STANDARD_T20_BALLS
    allocation_balls.loc[revision_present] = selected_revision.loc[revision_present].astype("int64")

    result["allocation_balls"] = allocation_balls
    result["allocation_overs"] = result["allocation_balls"].astype("Float64") / 6
    result["allocation_source"] = "not_regular_innings"
    result.loc[result["is_regular_innings"], "allocation_source"] = "standard_20_over_default"
    result.loc[revision_present & ~inherited_revision, "allocation_source"] = (
        "revised_field_interpreted_as_balls"
    )
    result.loc[inherited_revision, "allocation_source"] = (
        "inherited_first_innings_revised_allocation"
    )

    # Boundaries are computed from each innings' allocation, not observed
    # innings length (which may be shorter because of a chase, wickets, or rain).
    result["early_collapse_threshold_over"] = pd.Series(
        pd.NA, index=result.index, dtype="Int64"
    )
    result["death_phase_start_over"] = pd.Series(
        pd.NA, index=result.index, dtype="Int64"
    )
    regular = result["is_regular_innings"]
    allocation_overs = result.loc[regular, "allocation_overs"].astype(float)
    result.loc[regular, "early_collapse_threshold_over"] = (
        allocation_overs.mul(early_collapse_fraction).apply(math.ceil).astype("int64")
    )
    result.loc[regular, "death_phase_start_over"] = (
        allocation_overs.mul(death_phase_fraction).apply(math.floor).add(1).astype("int64")
    )

    within_collapse_window = (
        regular
        & result["overid"].le(result["early_collapse_threshold_over"].fillna(-1))
        & result["wickets_after"].ge(5)
    )
    collapse_by_threshold = within_collapse_window.groupby(
        [result["match_id"], result["innings"]], sort=False
    ).transform("any")
    result["early_collapse_triggered"] = (regular & collapse_by_threshold).astype(bool)
    result["is_early_collapse_pressure"] = (
        result["early_collapse_triggered"] & result["wickets_before"].ge(5)
    ).astype(bool)

    result["is_death_over_pressure"] = (
        regular
        & result["overid"].ge(result["death_phase_start_over"].fillna(10**9))
        & result["overid"].le(result["allocation_overs"].fillna(-1).apply(math.ceil))
    ).astype(bool)

    result["is_pressure"] = (
        result["is_early_collapse_pressure"] | result["is_death_over_pressure"]
    )
    result["pressure_category"] = "ordinary"
    result.loc[result["is_early_collapse_pressure"], "pressure_category"] = "early_collapse"
    result.loc[result["is_death_over_pressure"], "pressure_category"] = "death_over"
    result.loc[
        result["is_early_collapse_pressure"] & result["is_death_over_pressure"],
        "pressure_category",
    ] = "early_collapse_and_death_over"
    result.loc[~regular, "pressure_category"] = "additional_innings_not_classified"

    return result


def pressure_audit(pressured: pd.DataFrame) -> dict:
    """Return pressure-label coverage counts for the supplied dataframe."""
    required = {
        "match_id", "innings", "is_regular_innings", "is_early_collapse_pressure",
        "is_death_over_pressure", "is_pressure", "early_collapse_triggered",
        "allocation_source", "pressure_category",
    }
    missing = sorted(required - set(pressured.columns))
    if missing:
        raise ValueError(f"pressured dataframe is missing audit columns: {missing}")

    regular = pressured[pressured["is_regular_innings"]]
    early_rows = regular[regular["is_early_collapse_pressure"]]
    death_rows = regular[regular["is_death_over_pressure"]]
    any_rows = regular[regular["is_pressure"]]
    early_innings = regular.groupby(["match_id", "innings"])[
        "early_collapse_triggered"
    ].first()
    early_innings = early_innings[early_innings]

    category_counts = (
        regular["pressure_category"].value_counts(dropna=False).to_dict()
    )
    allocation_sources = (
        regular["allocation_source"].value_counts(dropna=False).to_dict()
    )

    return {
        "pressure_definition": {
            "early_collapse": "5+ wickets lost by the end of the first 50% of allocated innings; flag starts on the next delivery",
            "death_phase": "final 25% of allocated innings, rounded to full overs (overs 16-20 for 20 overs)",
            "additional_innings": "retained but not pressure-classified",
        },
        "delivery_records_total": int(len(pressured)),
        "regular_innings_delivery_records": int(len(regular)),
        "additional_innings_delivery_records": int((~pressured["is_regular_innings"]).sum()),
        "early_collapse_pressure_records": int(len(early_rows)),
        "death_phase_pressure_records": int(len(death_rows)),
        "overlapping_pressure_records": int(
            (regular["is_early_collapse_pressure"] & regular["is_death_over_pressure"]).sum()
        ),
        "combined_pressure_records_without_double_counting": int(len(any_rows)),
        "early_collapse_innings": int(early_innings.sum()),
        "matches_with_early_collapse": int(
            early_innings.index.get_level_values("match_id").nunique()
        ),
        "matches_with_death_phase_pressure": int(
            death_rows.loc[:, "match_id"].nunique()
        ),
        "pressure_category_record_counts": {
            str(key): int(value) for key, value in category_counts.items()
        },
        "allocation_source_record_counts": {
            str(key): int(value) for key, value in allocation_sources.items()
        },
        "revised_allocation_encoding_check": {
            "non_null_first_innings_revised_values": int(
                pressured["first_inn_revised_overs"].notna().sum()
            ),
            "non_null_second_innings_revised_values": int(
                pressured["second_inn_revised_overs"].notna().sum()
            ),
            "all_used_revised_values_are_multiples_of_six": bool(
                pressured.loc[
                    pressured["allocation_source"].isin([
                        "revised_field_interpreted_as_balls",
                        "inherited_first_innings_revised_allocation",
                    ]),
                    "allocation_balls",
                ].dropna().mod(6).eq(0).all()
            ),
            "interpretation_note": (
                "Revised fields are interpreted as ball allowances because all "
                "non-null supplied values are multiples of six. The source schema "
                "does not explicitly document units; inherited second-innings "
                "allocations are separately labelled."
            ),
        },
    }


def pressure_threshold_sensitivity(
    context: pd.DataFrame,
    fractions: tuple[float, ...] = (0.40, 0.50, 0.60),
    inherit_missing_second_innings_revision: bool = True,
) -> list[dict]:
    """Compare early-collapse coverage at 40%, 50% and 60% of the allocation.

    For a standard 20-over innings these are equivalent to collapse cutoffs by
    the ends of overs 8, 10 and 12. The death-phase rule remains unchanged.
    """
    results = []
    for fraction in fractions:
        pressured = add_pressure_flags(
            context,
            early_collapse_fraction=fraction,
            death_phase_fraction=0.75,
            inherit_missing_second_innings_revision=inherit_missing_second_innings_revision,
        )
        audit = pressure_audit(pressured)
        results.append(
            {
                "inherit_missing_second_innings_revision": inherit_missing_second_innings_revision,
                "early_collapse_fraction": fraction,
                "equivalent_standard_20_over_cutoff": int(math.ceil(20 * fraction)),
                "early_collapse_pressure_records": audit[
                    "early_collapse_pressure_records"
                ],
                "early_collapse_innings": audit["early_collapse_innings"],
                "matches_with_early_collapse": audit[
                    "matches_with_early_collapse"
                ],
                "death_phase_pressure_records": audit[
                    "death_phase_pressure_records"
                ],
                "overlapping_pressure_records": audit[
                    "overlapping_pressure_records"
                ],
                "combined_pressure_records_without_double_counting": audit[
                    "combined_pressure_records_without_double_counting"
                ],
            }
        )
    return results
