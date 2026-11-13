import pandas as pd
from src.data_validation import validate_schemas

def test_validate_schemas_reports_missing_tables():
    problems = validate_schemas({})
    assert any("Missing loaded table" in item for item in problems)
