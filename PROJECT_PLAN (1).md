# CI Pipeline Documentation Tool — Project Plan

## Project Overview

**Title:** What is my CI Pipeline Doing? — Automated Documentation  
**Student:** Shivam Balasaheb Bhagat  
**Supervisor:** Professor Suzanne Embury, University of Manchester  
**Degree:** MSc Computer Science  
**Open Source:** Yes — Suzanne will be credited as project supervisor  

---

## The Problem Being Solved

CI/CD pipelines are sets of automated tasks that run whenever a developer pushes code to a repository. They are defined in YAML configuration files and handle things like running tests, checking code style, deploying to servers, and scanning for security issues.

The problem is that these YAML files are hard to understand — especially for new developers joining a project. A real project can have multiple pipeline files, hundreds of lines each, with complex job dependencies, conditional logic, secrets, and cross-file relationships. There is currently no tool that reads these files and automatically generates clear human-readable documentation explaining what the pipeline actually does.

This project builds that tool.

**Key motivation from literature:**  
Bajpai & Lewis (2022) showed that undocumented CI/CD pipelines are not just inconvenient — they lead to real security vulnerabilities because developers cannot fully understand what their own pipelines are doing.

---

## What the Project Builds

### Tool 1 — Single Pipeline Documentation
Takes one CI pipeline YAML file as input and generates:
- A plain English explanation of what the pipeline does
- What triggers it (push, pull request, schedule, manual etc)
- What jobs exist and what order they run in
- What each step in each job does
- What secrets and environment variables are needed
- A Mermaid diagram showing the job flow visually

### Tool 2 — Multi-Pipeline Documentation
Takes an entire repository folder containing multiple pipeline YAML files and generates:
- A unified understanding of the complete CI setup
- Which pipelines run in which situations
- How pipelines relate to or depend on each other
- A combined picture of what happens for any given developer action (push, PR etc)
- Unified Mermaid diagrams showing the full flow

---

## Architecture — Four Layers

The tool is built in four clearly separated layers. This is critical — each layer is independent so new platforms, new LLMs, and new output types can be added later without restructuring anything.

```
Layer 1 — Parsers        (platform specific — one per CI platform)
Layer 2 — Intermediate   (platform agnostic — common format)
Layer 3 — Generators     (documentation, diagrams — works on any platform)
Layer 4 — LLM Layer      (beautification — swappable between providers)
```

---

### Layer 1 — Platform-Specific Parsers

Each supported CI platform gets its own parser. The parser reads the raw YAML file and converts it into the Intermediate Representation (Layer 2). Nothing else in the system touches platform-specific syntax.

**Platforms planned:**
- GitHub Actions — full support (primary, built first)
- GitLab CI — full support (added in extra time if available)
- Jenkins — partial support if time allows (uses Groovy not YAML, more complex)
- CircleCI — partial support if time allows

**Adding a new platform later = writing one new parser. Nothing else changes.**

---

### Layer 2 — Intermediate Representation (IR)

This is the heart of the platform-agnostic design. Every parser converts its platform-specific YAML into a common Python dictionary structure — the IR. All downstream processing works only with this IR, never with raw YAML.

**Field names are deliberately generic — not tied to any platform:**

| GitHub Actions term | GitLab CI term | IR field name |
|--------------------|----------------|---------------|
| `runs-on` | `image` | `runner` |
| `steps` | `script` | `steps` |
| `needs` | `needs` | `dependencies` |
| `on` | `only/rules` | `triggers` |
| `env` | `variables` | `environment` |
| `uses` | `include` | `action` |

**Example IR structure:**
```python
pipeline = {
    "name": "CI Pipeline",
    "source_platform": "github_actions",
    "source_file": "ci.yml",
    "triggers": [
        {"type": "push", "branches": ["main"]},
        {"type": "pull_request", "branches": ["main"]}
    ],
    "jobs": [
        {
            "name": "lint",
            "runner": "ubuntu-latest",
            "dependencies": [],
            "steps": [
                {"name": "checkout", "action": "actions/checkout@v3"},
                {"name": "run linter", "command": "flake8 ."}
            ],
            "conditions": []
        },
        {
            "name": "test",
            "runner": "ubuntu-latest",
            "dependencies": ["lint"],
            "steps": [
                {"name": "checkout", "action": "actions/checkout@v3"},
                {"name": "run tests", "command": "pytest"}
            ],
            "conditions": []
        },
        {
            "name": "deploy",
            "runner": "ubuntu-latest",
            "dependencies": ["test"],
            "steps": [
                {"name": "deploy to production", "command": "./deploy.sh"}
            ],
            "conditions": [
                {"type": "branch", "value": "main"},
                {"type": "event", "value": "push_only"}
            ]
        }
    ],
    "secrets": ["DEPLOY_API_KEY"],
    "environment_variables": []
}
```

---

### Layer 3 — Generators

These take the IR as input and produce output. They never touch raw YAML or platform-specific code.

**3a — Structured Text Generator (pure Python)**  
Reads the IR and produces a structured plain text summary. No LLM involved. Completely private, works offline.

Example output:
```
Pipeline: CI Pipeline
Source: ci.yml (GitHub Actions)

TRIGGERS
- Runs on every push to main branch
- Runs on every pull request targeting main branch

JOBS (in order)
1. lint — checks code style using flake8
2. test — runs pytest (only if lint passes)
3. deploy — deploys to production (only if test passes, only on push not pull request)

SECRETS REQUIRED
- DEPLOY_API_KEY
```

**3b — Mermaid Diagram Generator (pure Python)**  
Reads the IR job structure and builds Mermaid diagram syntax as a string. No LLM involved.

Example output:
```
flowchart LR
    push([Push to main]) --> lint
    lint["lint: check code style"] --> test
    test["test: run pytest"] --> deploy
    deploy["deploy: production only"]
```

This renders as an actual visual flowchart in any Markdown viewer.

---

### Layer 4 — LLM Layer

Takes the structured text output from Layer 3 and converts it into natural, readable prose. The LLM is doing a simple task here — rewriting structured bullet points into flowing sentences. It is not doing analysis. Python already did the analysis.

**This layer is swappable — the rest of the system does not care which LLM is used.**

**Mode 1 — Local LLM (default, private)**
- Uses Ollama running locally on the user's machine
- Nothing leaves the user's system
- Suitable for companies with private repositories
- Slightly less polished output but factually accurate (Python verified the facts)
- Models: Llama 3.1 8B or Mistral 7B

**Mode 2 — Gemini API (enhanced, optional)**
- User explicitly opts in knowing data leaves their system
- Better natural language quality
- Used for more complex diagram generation if needed
- Free tier via Google AI Studio

**Adding a new LLM provider later = adding one new option in this layer. Nothing else changes.**

---

## Why This Is Not Just "Ask Claude/Gemini to Read the YAML"

This is an important distinction. If the tool just sent raw YAML to an LLM and asked for an explanation:

1. Any developer could do that themselves — no tool needed
2. The LLM might hallucinate or misinterpret complex conditions
3. Output would be inconsistent every time
4. Would not work across multiple files together
5. Company's private pipeline details sent to external API with no choice

This tool's value is in the Python extraction layer — systematic, reliable, consistent, private by default. The LLM only handles natural language beautification from already-verified structured data. That is a fundamentally different and more valuable product.

---

## Evaluation Plan

### Tool 1 Evaluation — Two Methods

**Method 1 — Correctness check (inspired by student's own idea)**  
- Pick 5-10 real open source repositories with clear GitHub Actions workflows
- Trigger their actual pipelines with a test push or pull request
- GitHub's UI shows exactly which jobs ran and passed
- Compare this against what the tool documented
- Did the tool correctly describe what actually happened?

**Method 2 — Human quality evaluation (based on Hu et al. 2022)**  
Hu et al. (2022) showed that automated scoring methods like BLEU and ROUGE do not reliably measure documentation quality. Human judgment is what actually matters.  
- Take the same real repositories
- Find existing human-written documentation for their pipelines (if any exists) or ask developers to write brief descriptions
- Ask human evaluators (fellow students, developers) to rate tool output against human-written output on a rubric
- Rubric criteria: accuracy, clarity, completeness, usefulness

### Tool 2 Evaluation
- Human evaluation only (correctness checking across multiple files is too complex to automate reliably)
- Focus on whether the unified documentation genuinely helps someone understand the full CI setup of a repository

---

## What Is Cut From Scope (Deliberately)

These are good ideas but cut to keep the project achievable in 3 months:

- **Full multi-platform support from day one** — GitHub Actions first, GitLab CI if time allows. Architecture supports extension but full implementation is not required
- **Full local LLM implementation** — Mentioned as a design decision and future work in the report. Gemini used as primary LLM
- **Animation/step-through feature** — Marked as "if time allows" in project description. Treat as genuine stretch goal only
- **Automated pipeline execution for evaluation** — Used as manual spot check only, not automated end-to-end
- **Web interface or GUI** — Command line tool is sufficient for dissertation purposes

---

## Academic Framing

**Project type:** Hybrid — primarily development-driven with evaluation methodology as the research contribution  

**Key literature:**
- Bajpai & Lewis (2022) — motivation: undocumented CI/CD pipelines cause security vulnerabilities
- Hu et al. (2022) — evaluation methodology: human judgment over automated metrics
- GLITCH framework — architectural precedent for intermediate representation approach in CI/IaC tooling
- Decan et al. — empirical study on GitHub Actions usage across real repositories
- Rahman et al. — IaC smells literature, relevant to understanding CI configuration quality
- Schwarz et al. — code smells in IaC, supports platform-agnostic design rationale

**Architectural precedent:**  
The GLITCH framework (Ferreira et al.) built a platform-agnostic security smell detector for IaC scripts using an intermediate representation — converting Ansible, Chef, and Puppet scripts into a common format before analysis. This project applies the same architectural pattern to documentation generation.

---

## Open Questions to Resolve With Suzanne

- How to handle dynamic YAML values like `${{ matrix.python-version }}` in documentation
- Whether to include a small survey as part of human evaluation or keep it informal
- How many repositories to use in evaluation — enough to be meaningful, not so many it becomes unmanageable
- Whether partial GitLab CI support counts toward the "platform-agnostic" claim or needs to be more complete

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python |
| YAML parsing | PyYAML |
| Diagram generation | Pure Python string building → Mermaid syntax |
| Primary LLM | Gemini API (Google AI Studio free tier) |
| Optional local LLM | Ollama (Llama 3.1 8B or Mistral 7B) |
| Output format | Markdown (.md files with embedded Mermaid) |
| IDE | VS Code with GitHub Copilot |
| Version control | GitHub (project will be open sourced on completion) |

---

## Extensibility Summary

Because of the layered architecture, future additions require no restructuring:

| Feature | How to add later |
|---------|-----------------|
| New CI platform (e.g. GitLab) | Write one new parser in Layer 1 |
| New LLM provider | Add one new option in Layer 4 |
| Local LLM support | Add Ollama option in Layer 4 |
| Animation feature | Add new generator in Layer 3 |
| New output format | Add new generator in Layer 3 |
| Web interface | Build on top of existing Layer 3 output |

---

*This document is a living reference — update as the project evolves.*  
*Last updated: June 2026*
