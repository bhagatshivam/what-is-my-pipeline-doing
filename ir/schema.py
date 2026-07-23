"""
ir/schema.py — Platform-agnostic Intermediate Representation (IR) for CI pipelines.

This is the common data structure that every platform-specific parser (Layer 1)
converts into, and every generator (Layer 3) and LLM prompt (Layer 4) consumes.
No downstream code should ever see raw YAML — only these structures.

Design principles (see PROJECT_PLAN.md for full rationale):
- Field names are platform-agnostic, never tied to GitHub Actions / GitLab / etc.
  terminology specifically.
- Every field that could plausibly not exist on some platform is Optional with a
  sensible default, rather than forcing every parser to fabricate a value.
- `raw_extras` escape hatches exist on Pipeline/Job/Step so parsers can preserve
  information the schema doesn't yet model, instead of silently dropping it.
  Dropped information is a correctness bug; an unmapped-but-preserved field is
  just a known limitation (write it up honestly in the report instead).
- Anything platforms structure differently (branch conditions, artifact passing)
  gets both a raw form (always present, always trustworthy) and a structured
  form (best-effort parse, may be None) — never structured-only, since a failed
  structured parse must not mean silently losing the fact entirely.

Migration note (from the original flat-dict schema in PROJECT_PLAN.md):
This version is a superset. If Phase 3 parser code already exists against the
old shape, the fields that changed are: `steps` (unified `type`/`value` instead
of separate `action`/`command` keys), `dependencies` (now execution-order only —
artifact passing is separate), and `conditions` (now a structured Condition
object per job/step, not a bare list). Everything else is additive.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any, Union


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SourcePlatform(str, Enum):
    GITHUB_ACTIONS = "github_actions"
    GITLAB_CI = "gitlab_ci"
    CIRCLECI = "circleci"
    JENKINS = "jenkins"


class TriggerType(str, Enum):
    PUSH = "push"
    PULL_REQUEST = "pull_request"
    SCHEDULE = "schedule"
    MANUAL = "manual"
    RELEASE = "release"
    WORKFLOW_CALL = "workflow_call"
    WORKFLOW_RUN = "workflow_run"
    OTHER = "other"


class StepType(str, Enum):
    ACTION = "action"      # a reusable action/orb/plugin, e.g. actions/checkout@v3
    COMMAND = "command"    # a shell command run inline
    SCRIPT = "script"      # a reference to an external script file


class SecretScope(str, Enum):
    PIPELINE = "pipeline"
    JOB = "job"
    STEP = "step"


# ---------------------------------------------------------------------------
# Shared sub-structures
# ---------------------------------------------------------------------------

@dataclass
class Condition:
    """
    Represents a conditional gate on a job or step (GH Actions `if:`, GitLab
    `rules:`, Jenkins `when {}`, etc).

    `expression` is the raw, original-syntax condition string and MUST always
    be populated whenever a Condition exists — it is the ground truth. `structured`
    is a best-effort parse into a common shape and may be None if the expression
    is too complex/dynamic to parse reliably. Generators and LLM prompts should
    prefer `structured` when present but must fall back to `expression` — never
    silently drop a condition because it couldn't be structured.
    """
    expression: str
    structured: Optional[Dict[str, Any]] = None
    # e.g. {"type": "branch_equals", "value": "main"}
    #      {"type": "event_equals", "value": "push"}
    #      {"type": "unparsed"}  -- explicit marker meaning "raw only, don't guess"


@dataclass
class MatrixStrategy:
    """
    Represents a build matrix (GH Actions `strategy.matrix` and equivalents).
    `axes` keys are axis names, values are the list of values for that axis, e.g.
    {"python-version": ["3.10", "3.11"], "os": ["ubuntu-latest", "windows-latest"]}
    """
    axes: Dict[str, List[str]] = field(default_factory=dict)
    include: List[Dict[str, Any]] = field(default_factory=list)  # extra explicit combinations
    exclude: List[Dict[str, Any]] = field(default_factory=list)  # excluded combinations
    fail_fast: Optional[bool] = None


@dataclass
class Trigger:
    type: TriggerType
    branches: List[str] = field(default_factory=list)
    branches_ignore: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    tags_ignore: List[str] = field(default_factory=list)
    paths: List[str] = field(default_factory=list)
    paths_ignore: List[str] = field(default_factory=list)
    schedule: Optional[str] = None           # cron string; only meaningful when type == SCHEDULE
    inputs: List[Dict[str, Any]] = field(default_factory=list)
    # each input dict: {"name": ..., "required": bool, "default": ..., "type": ...}
    source_workflow: Optional[str] = None    # for WORKFLOW_RUN: name/path of the upstream workflow
    raw: str = ""                            # original trigger fragment, for traceability/debugging
    origin: Optional[str] = None
    # Set only by tool2's merge layer (see tool2/multi_pipeline.py) to scope
    # unified-diagram trigger wiring to the workflow file this trigger came
    # from. Always None for a single-file Tool 1 parse.


@dataclass
class Step:
    name: str
    type: StepType
    value: str                                # the action ref, the command string, or the script path
    with_args: Dict[str, Any] = field(default_factory=dict)   # named with_args, not `with` (avoid confusion)
    condition: Optional[Condition] = None
    environment: Dict[str, str] = field(default_factory=dict)
    continue_on_error: bool = False
    raw_extras: Dict[str, Any] = field(default_factory=dict)  # unmapped step-level fields, preserved


@dataclass
class Job:
    name: str
    stage: Optional[str] = None              # populated for platforms with explicit named stages (GitLab/Jenkins)
    runner: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)         # execution-order only: "runs after"
    artifacts_produced: List[str] = field(default_factory=list)   # paths/names this job outputs
    artifacts_consumed: List[str] = field(default_factory=list)   # job names whose artifacts this job pulls in
    matrix: Optional[MatrixStrategy] = None
    allow_failure: bool = False
    condition: Optional[Condition] = None
    environment: Dict[str, str] = field(default_factory=dict)     # job-level env vars
    steps: List[Step] = field(default_factory=list)
    timeout_minutes: Optional[int] = None
    permissions: Optional[Union[Dict[str, str], str]] = None
    concurrency: Optional[Dict[str, Any]] = None
    deployment_environment: Optional[str] = None
    # GH Actions' job-level `environment:` (protection-rules concept) —
    # distinct from Job.environment (env VARS, from `env:`). Typed only for
    # the string/dynamic-${{ }}-expression form, the only one seen in real
    # data. The extended `{name, url}` mapping form is valid GH Actions
    # syntax but untested here — falls back to
    # raw_extras["deployment_environment"] (see parser).
    origin: Optional[str] = None
    # Same meaning as Trigger.origin: set only by tool2's merge layer,
    # always None for a single-file Tool 1 parse.
    raw_extras: Dict[str, Any] = field(default_factory=dict)      # unmapped job-level fields, preserved


@dataclass
class Secret:
    name: str
    scope: SecretScope = SecretScope.PIPELINE
    scope_ref: Optional[str] = None   # job name (or "job.step") when scope is JOB/STEP; None when PIPELINE


@dataclass
class EnvironmentVariable:
    name: str
    value: Optional[str] = None       # None if the value is itself a secret/dynamic reference, not a literal
    scope: SecretScope = SecretScope.PIPELINE
    scope_ref: Optional[str] = None


@dataclass
class LinkedWorkflow:
    """
    An explicit relationship between this pipeline file and another one, e.g.
    `workflow_call` reuse, `workflow_run` chaining, or GitLab `include:`.
    Tool 2 needs this to be explicit in the IR rather than inferred at merge time.
    """
    target: str                       # name or path of the other workflow file
    relationship: str                 # "calls" | "triggered_by" | "includes"


# ---------------------------------------------------------------------------
# Top-level Pipeline structure
# ---------------------------------------------------------------------------

@dataclass
class Pipeline:
    name: str
    source_platform: SourcePlatform
    source_file: str
    triggers: List[Trigger] = field(default_factory=list)
    jobs: List[Job] = field(default_factory=list)
    secrets: List[Secret] = field(default_factory=list)
    environment_variables: List[EnvironmentVariable] = field(default_factory=list)
    linked_workflows: List[LinkedWorkflow] = field(default_factory=list)
    permissions: Optional[Union[Dict[str, str], str]] = None
    # GH Actions' `permissions:` — either a mapping of scope name -> "read"/
    # "write"/"none" (its fixed permission-level vocabulary, unlike the
    # free-form Job.environment dict) or a bare shorthand string like
    # "read-all". Both are fully-structured facts once you know which shape
    # you have — no raw/structured duality the way Condition has, so no
    # wrapper dataclass.
    concurrency: Optional[Dict[str, Any]] = None
    # GH Actions' `concurrency:` — always a mapping (`group` + usually
    # `cancel-in-progress`) in every real fixture. GH also allows a bare
    # `concurrency: group-name` shorthand string, but no fixture exercises
    # it, so it's untyped here — falls back to raw_extras (see parser).
    raw_extras: Dict[str, Any] = field(default_factory=dict)   # unmapped pipeline-level fields, preserved

    # -- Serialization helpers ------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to a plain, JSON-serializable dict — for handing to generators,
        LLM prompts, or writing out as a debug artifact. Enum values become their
        `.value` strings automatically since all enums here subclass `str`.
        """
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Pipeline":
        """
        Reconstruct a Pipeline from a plain dict (e.g. a hand-written JSON
        fixture used as ground truth in Phase 2 tests, or a round-tripped
        to_dict() output). Does NOT validate — call ir.validate.validate_pipeline()
        separately on the result.
        """

        def _condition(d: Optional[Dict[str, Any]]) -> Optional[Condition]:
            return Condition(**d) if d else None

        def _matrix(d: Optional[Dict[str, Any]]) -> Optional[MatrixStrategy]:
            return MatrixStrategy(**d) if d else None

        triggers = [
            Trigger(**{**t, "type": TriggerType(t["type"])})
            for t in data.get("triggers", [])
        ]

        jobs: List[Job] = []
        for j in data.get("jobs", []):
            j = dict(j)
            j["condition"] = _condition(j.get("condition"))
            j["matrix"] = _matrix(j.get("matrix"))
            steps: List[Step] = []
            for s in j.get("steps", []):
                s = dict(s)
                s["type"] = StepType(s["type"])
                s["condition"] = _condition(s.get("condition"))
                steps.append(Step(**s))
            j["steps"] = steps
            jobs.append(Job(**j))

        secrets = [
            Secret(**{**s, "scope": SecretScope(s.get("scope", "pipeline"))})
            for s in data.get("secrets", [])
        ]
        env_vars = [
            EnvironmentVariable(**{**e, "scope": SecretScope(e.get("scope", "pipeline"))})
            for e in data.get("environment_variables", [])
        ]
        linked = [LinkedWorkflow(**lw) for lw in data.get("linked_workflows", [])]

        return Pipeline(
            name=data["name"],
            source_platform=SourcePlatform(data["source_platform"]),
            source_file=data["source_file"],
            triggers=triggers,
            jobs=jobs,
            secrets=secrets,
            environment_variables=env_vars,
            linked_workflows=linked,
            permissions=data.get("permissions"),
            concurrency=data.get("concurrency"),
            raw_extras=data.get("raw_extras", {}),
        )
