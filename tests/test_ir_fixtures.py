"""Round-trips the hand-written ground-truth IR fixtures and checks they validate."""

import json
import os

import pytest

from ir.schema import Pipeline
from ir.validate import is_valid, validate_pipeline

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

FIXTURE_FILES = [
    "simple_pipeline_ir.json",
    "medium_pipeline_ir.json",
    "complex_pipeline_ir.json",
]


@pytest.mark.parametrize("filename", FIXTURE_FILES)
def test_ground_truth_fixture_is_valid(filename):
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path) as f:
        data = json.load(f)

    pipeline = Pipeline.from_dict(data)

    issues = validate_pipeline(pipeline)
    errors = [i for i in issues if i.severity == "error"]
    assert is_valid(pipeline), f"{filename} failed validation: {errors}"
