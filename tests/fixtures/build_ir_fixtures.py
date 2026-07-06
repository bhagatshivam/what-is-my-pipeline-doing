"""
tests/fixtures/build_ir_fixtures.py — hand-builds ground-truth Pipeline objects
(not via any parser) and writes them out as JSON fixtures via Pipeline.to_dict().

These are the ground truth Phase 3's parser output will eventually be compared
against. Re-run this script (`python -m tests.fixtures.build_ir_fixtures`) if
the IR schema changes and the fixtures need regenerating.
"""

from __future__ import annotations

import json
import os

from ir.schema import (
    Condition,
    EnvironmentVariable,
    Job,
    LinkedWorkflow,
    MatrixStrategy,
    Pipeline,
    Secret,
    SecretScope,
    SourcePlatform,
    Step,
    StepType,
    Trigger,
    TriggerType,
)

FIXTURES_DIR = os.path.dirname(__file__)


def build_simple_pipeline() -> Pipeline:
    """One job, one trigger, no matrix/secrets/conditions."""
    return Pipeline(
        name="Lint",
        source_platform=SourcePlatform.GITHUB_ACTIONS,
        source_file=".github/workflows/lint.yml",
        triggers=[
            Trigger(type=TriggerType.PUSH, branches=["main"], raw="push:\n  branches: [main]"),
        ],
        jobs=[
            Job(
                name="lint",
                runner="ubuntu-latest",
                steps=[
                    Step(name="checkout", type=StepType.ACTION, value="actions/checkout@v4"),
                    Step(name="run flake8", type=StepType.COMMAND, value="flake8 ."),
                ],
            ),
        ],
    )


def build_medium_pipeline() -> Pipeline:
    """build -> test -> deploy, a matrix on test, a condition on deploy, one secret, one env var."""
    return Pipeline(
        name="CI Pipeline",
        source_platform=SourcePlatform.GITHUB_ACTIONS,
        source_file=".github/workflows/ci.yml",
        triggers=[
            Trigger(type=TriggerType.PUSH, branches=["main"], raw="push:\n  branches: [main]"),
            Trigger(type=TriggerType.PULL_REQUEST, branches=["main"], raw="pull_request:\n  branches: [main]"),
        ],
        jobs=[
            Job(
                name="build",
                runner="ubuntu-latest",
                steps=[
                    Step(name="checkout", type=StepType.ACTION, value="actions/checkout@v4"),
                    Step(name="build", type=StepType.COMMAND, value="python setup.py build"),
                ],
            ),
            Job(
                name="test",
                runner="ubuntu-latest",
                dependencies=["build"],
                matrix=MatrixStrategy(axes={"python-version": ["3.10", "3.11", "3.12"]}, fail_fast=False),
                steps=[
                    Step(name="checkout", type=StepType.ACTION, value="actions/checkout@v4"),
                    Step(name="run tests", type=StepType.COMMAND, value="pytest"),
                ],
            ),
            Job(
                name="deploy",
                runner="ubuntu-latest",
                dependencies=["test"],
                condition=Condition(
                    expression="github.ref == 'refs/heads/main' && github.event_name == 'push'",
                    structured={"type": "branch_equals", "value": "main"},
                ),
                environment={"DEPLOY_ENV": "production"},
                steps=[
                    Step(
                        name="deploy to production",
                        type=StepType.SCRIPT,
                        value="./deploy.sh",
                        environment={"DEPLOY_API_KEY": "${{ secrets.DEPLOY_API_KEY }}"},
                    ),
                ],
            ),
        ],
        secrets=[Secret(name="DEPLOY_API_KEY", scope=SecretScope.PIPELINE)],
        environment_variables=[EnvironmentVariable(name="PYTHON_VERSION", value="3.11")],
    )


def build_complex_pipeline() -> Pipeline:
    """
    Multi-job needs-chain, matrix on one job, artifact passing between two jobs,
    a step-level condition, a linked (reusable) workflow, and a job-scoped secret.
    """
    return Pipeline(
        name="Build, Test & Release",
        source_platform=SourcePlatform.GITHUB_ACTIONS,
        source_file=".github/workflows/release.yml",
        triggers=[
            Trigger(type=TriggerType.PUSH, tags=["v*"], raw="push:\n  tags: ['v*']"),
            Trigger(
                type=TriggerType.WORKFLOW_CALL,
                inputs=[{"name": "release_tag", "required": True, "default": None, "type": "string"}],
                raw="workflow_call:\n  inputs:\n    release_tag: {required: true, type: string}",
            ),
        ],
        jobs=[
            Job(
                name="build",
                runner="ubuntu-latest",
                matrix=MatrixStrategy(
                    axes={"os": ["ubuntu-latest", "windows-latest", "macos-latest"]},
                    fail_fast=False,
                ),
                artifacts_produced=["dist/"],
                steps=[
                    Step(name="checkout", type=StepType.ACTION, value="actions/checkout@v4"),
                    Step(name="build wheel", type=StepType.COMMAND, value="python -m build"),
                    Step(
                        name="upload artifact",
                        type=StepType.ACTION,
                        value="actions/upload-artifact@v4",
                        with_args={"name": "dist", "path": "dist/"},
                    ),
                ],
            ),
            Job(
                name="test",
                runner="ubuntu-latest",
                dependencies=["build"],
                artifacts_consumed=["build"],
                steps=[
                    Step(
                        name="download artifact",
                        type=StepType.ACTION,
                        value="actions/download-artifact@v4",
                        with_args={"name": "dist"},
                    ),
                    Step(
                        name="run integration tests",
                        type=StepType.COMMAND,
                        value="pytest tests/integration",
                        condition=Condition(
                            expression="runner.os == 'Linux'",
                            structured={"type": "unparsed"},
                        ),
                    ),
                ],
            ),
            Job(
                name="release",
                runner="ubuntu-latest",
                dependencies=["test"],
                artifacts_consumed=["build"],
                environment={"RELEASE_ENV": "production"},
                steps=[
                    Step(
                        name="download artifact",
                        type=StepType.ACTION,
                        value="actions/download-artifact@v4",
                        with_args={"name": "dist"},
                    ),
                    Step(
                        name="publish to PyPI",
                        type=StepType.COMMAND,
                        value="twine upload dist/*",
                        environment={"TWINE_PASSWORD": "${{ secrets.PYPI_TOKEN }}"},
                    ),
                ],
            ),
        ],
        secrets=[Secret(name="PYPI_TOKEN", scope=SecretScope.JOB, scope_ref="release")],
        linked_workflows=[
            LinkedWorkflow(target="./.github/workflows/build.yml", relationship="calls"),
        ],
    )


def main() -> None:
    fixtures = {
        "simple_pipeline_ir.json": build_simple_pipeline(),
        "medium_pipeline_ir.json": build_medium_pipeline(),
        "complex_pipeline_ir.json": build_complex_pipeline(),
    }
    for filename, pipeline in fixtures.items():
        path = os.path.join(FIXTURES_DIR, filename)
        with open(path, "w") as f:
            json.dump(pipeline.to_dict(), f, indent=2)
            f.write("\n")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
