"""
Tests for tool2/relationships.py — read-only relationship analysis on top
of Tool 2's already-combined Pipeline. Phase 7.5 of BUILD_PLAN.md.

Covers: strict-equality shared-trigger detection (same structured fields +
same raw -> shared; same structured fields + different raw -> NOT shared),
`workflow_run` "follows" resolution against the one real fixture with a
genuine cross-file relationship (`tests/fixtures/multi/black`), the two
contrast fixtures with no relationships at all (`starlette`, `tox`), and
the Phase 7.5 Revision 1 dangling-dependency regression applied to the
relationship table's independent_job_count.
"""

import os

from ir.schema import Job, Pipeline, SourcePlatform, Trigger, TriggerType
from tool2.multi_pipeline import (
    _merge_pipelines,
    _origin_display_names,
    _repo_label,
    discover_workflow_files,
)
from tool2.relationships import (
    analyze_relationships,
    render_follows_diagram,
    render_relationship_table,
    render_shared_triggers_note,
)
from parsers.github_actions import GitHubActionsParser

FIXTURES_MULTI_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "multi")


def _analyze_real_repo(repo: str):
    repo_path = os.path.join(FIXTURES_MULTI_DIR, repo)
    files = discover_workflow_files(repo_path)
    pipelines = [GitHubActionsParser().parse(str(f)) for f in files]
    combined = _merge_pipelines(files, pipelines, _repo_label(repo_path), files[0].parent)
    origin_names = _origin_display_names(files, pipelines)
    return analyze_relationships(combined, origin_names), combined, origin_names


# ---------------------------------------------------------------------------
# black — the one real fixture with a genuine workflow_run relationship.
# ---------------------------------------------------------------------------

def test_black_follows_resolves_to_the_upstream_workflow():
    report, _, _ = _analyze_real_repo("black")
    assert len(report.follows) == 1
    f = report.follows[0]
    assert f.origin == "diff_shades_comment_yml"
    assert f.target_origin == "diff_shades_yml"
    assert f.target == "diff-shades"
    assert f.relationship == "triggered_by"


def test_black_relationship_table_shows_follows_not_independent():
    report, _, _ = _analyze_real_repo("black")
    rows_by_origin = {row.origin: row for row in report.rows}
    assert rows_by_origin["diff_shades_comment_yml"].relationship == "follows diff_shades_yml"
    assert rows_by_origin["diff_shades_yml"].relationship == "independent"
    assert rows_by_origin["lint_yml"].relationship == "independent"


def test_black_follows_diagram_has_correct_edge_direction():
    report, _, _ = _analyze_real_repo("black")
    diagram = render_follows_diagram(report)
    # target (upstream) --> origin (the one that follows/listens).
    assert "diff_shades_yml --> diff_shades_comment_yml" in diagram
    assert "diff_shades_comment_yml --> diff_shades_yml" not in diagram


def test_black_render_relationship_table_names_the_relationship():
    report, _, _ = _analyze_real_repo("black")
    table = render_relationship_table(report)
    assert "| diff_shades_comment_yml |" in table
    assert "follows diff_shades_yml" in table


# ---------------------------------------------------------------------------
# starlette / tox — contrast fixtures: no workflow_run relationships, but
# starlette/tox DO have real, verified-identical shared push triggers
# (confirmed against the raw YAML: starlette's main.yml/zizmor.yml both
# have exactly `push: {branches: [main]}`; tox's release.yaml/
# update-schemastore.yaml both have exactly `push: {tags: [*]}`).
# ---------------------------------------------------------------------------

def test_starlette_no_follows_relationships():
    report, _, _ = _analyze_real_repo("starlette")
    assert report.follows == []
    assert all(row.relationship == "independent" for row in report.rows)


def test_starlette_shared_trigger_detected_between_main_and_zizmor():
    report, _, _ = _analyze_real_repo("starlette")
    shared_origin_sets = [set(s.origins) for s in report.shared_triggers]
    assert {"main_yml", "zizmor_yml"} in shared_origin_sets


def test_starlette_shared_triggers_note_states_no_ordering():
    report, _, _ = _analyze_real_repo("starlette")
    note = render_shared_triggers_note(report)
    assert "no ordering" in note
    assert "main_yml, zizmor_yml" in note


def test_tox_no_follows_relationships():
    report, _, _ = _analyze_real_repo("tox")
    assert report.follows == []
    assert all(row.relationship == "independent" for row in report.rows)


def test_tox_shared_trigger_detected_between_release_and_update_schemastore():
    report, _, _ = _analyze_real_repo("tox")
    shared_origin_sets = [set(s.origins) for s in report.shared_triggers]
    assert {"release_yaml", "update_schemastore_yaml"} in shared_origin_sets


# ---------------------------------------------------------------------------
# Strict equality: structured fields match, raw text doesn't -> NOT shared.
# ---------------------------------------------------------------------------

def _pipeline(name, triggers=(), jobs=(), platform=SourcePlatform.GITHUB_ACTIONS, source_file="x.yml"):
    return Pipeline(name=name, source_platform=platform, source_file=source_file,
                     triggers=list(triggers), jobs=list(jobs))


def test_same_structured_fields_and_raw_are_shared():
    from pathlib import Path

    t1 = Trigger(type=TriggerType.PULL_REQUEST, raw="pull_request:\n  types: [opened]")
    t2 = Trigger(type=TriggerType.PULL_REQUEST, raw="pull_request:\n  types: [opened]")
    pipelines = [_pipeline("A", triggers=[t1]), _pipeline("B", triggers=[t2])]
    files = [Path("a.yml"), Path("b.yml")]
    combined = _merge_pipelines(files, pipelines, "repo", Path("."))
    report = analyze_relationships(combined, _origin_display_names(files, pipelines))
    assert len(report.shared_triggers) == 1
    assert set(report.shared_triggers[0].origins) == {"a_yml", "b_yml"}


def test_same_structured_fields_different_raw_are_not_shared():
    # Same TriggerType/branches/etc, but the `types:` activity filter (only
    # visible in `.raw`, not structurally modelled -- see LIMITATIONS.md)
    # differs. Must NOT be treated as the same shared trigger.
    from pathlib import Path

    t1 = Trigger(type=TriggerType.PULL_REQUEST, raw="pull_request:\n  types: [opened]")
    t2 = Trigger(type=TriggerType.PULL_REQUEST, raw="pull_request:\n  types: [closed]")
    pipelines = [_pipeline("A", triggers=[t1]), _pipeline("B", triggers=[t2])]
    files = [Path("a.yml"), Path("b.yml")]
    combined = _merge_pipelines(files, pipelines, "repo", Path("."))
    report = analyze_relationships(combined, _origin_display_names(files, pipelines))
    assert report.shared_triggers == []
    rows_by_origin = {row.origin: row for row in report.rows}
    assert rows_by_origin["a_yml"].relationship == "independent"
    assert rows_by_origin["b_yml"].relationship == "independent"


def test_raw_whitespace_differences_alone_still_count_as_shared():
    # Whitespace-only raw differences must not defeat the strict-equality
    # check -- only substantive differences (like the types: case above)
    # should.
    from pathlib import Path

    t1 = Trigger(type=TriggerType.PUSH, branches=["main"], raw="push:\n  branches: [main]")
    t2 = Trigger(type=TriggerType.PUSH, branches=["main"], raw="push:   branches: [main]  ")
    pipelines = [_pipeline("A", triggers=[t1]), _pipeline("B", triggers=[t2])]
    files = [Path("a.yml"), Path("b.yml")]
    combined = _merge_pipelines(files, pipelines, "repo", Path("."))
    report = analyze_relationships(combined, _origin_display_names(files, pipelines))
    assert len(report.shared_triggers) == 1


# ---------------------------------------------------------------------------
# Phase 7.5 Revision 1 — a dangling `needs:` reference must not inflate
# WorkflowRow.independent_job_count.
# ---------------------------------------------------------------------------

def test_dangling_dependency_not_counted_as_independent_in_relationship_table():
    from pathlib import Path

    jobs = [
        Job(name="A"),
        Job(name="B", dependencies=["does-not-exist"]),
    ]
    pipelines = [_pipeline("Repo", jobs=jobs)]
    files = [Path("a.yml")]
    combined = _merge_pipelines(files, pipelines, "repo", Path("."))
    report = analyze_relationships(combined, _origin_display_names(files, pipelines))
    row = report.rows[0]
    assert row.job_count == 2
    # Only A has no declared dependencies -- B's dangling `needs:` is a
    # real, declared (if unresolvable) dependency, not "independence".
    assert row.independent_job_count == 1
