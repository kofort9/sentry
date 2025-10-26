# Mermaid Diagrams

These Mermaid snippets mirror the diagrams rendered in the Streamlit dashboard and add a second view that drills into the TestSentry workflow. Open this file in Cursor (or any Markdown preview with Mermaid support) to see the diagrams rendered locally.

## CAMEL Architecture Overview

```mermaid
flowchart LR
    classDef trigger fill:#1f6feb,stroke:#0d408b,color:#ffffff,font-size:13px
    classDef agent fill:#f9d949,stroke:#b8860b,color:#111111,font-size:13px
    classDef service fill:#7c3aed,stroke:#4c1d95,color:#ffffff,font-size:13px
    classDef data fill:#3fb950,stroke:#238636,color:#111111,font-size:13px
    classDef status fill:#1b1f24,stroke:#30363d,color:#c9d1d9,font-size:13px

    Trigger[Pytest Failure Logs]:::trigger --> Coordinator{{CAMEL Coordinator}}:::service
    Coordinator --> Planner[[Planner Agent]]:::agent
    Planner --> Context[(Context Packs\n+ Target Files)]:::data
    Context --> Patcher[[Patcher Agent]]:::agent
    Patcher --> PatchEngine[[Patch Engine]]:::service
    PatchEngine --> RepoOps[(Git Ops + JSON patches)]:::data
    RepoOps --> Validator{{Validation Runner}}:::service
    Validator -->|pass| Success([Ready to Commit]):::status
    Validator -->|fail| Recovery[[Global Error Recovery]]:::service
    Recovery --> Coordinator
    Coordinator --> Telemetry[(LLM Logs, Metrics, History)]:::data
    Telemetry --> Dashboard[(Streamlit Dashboard)]:::service
```

## TestSentry Workflow

```mermaid
flowchart TD
    FailedTests[Pytest Failure Output] --> Parser[Test Failure Parser]
    Parser --> PlannerAgent[[Planner Agent]]
    PlannerAgent --> ContextPacks[(Context Packs\n+ Target Files)]
    ContextPacks --> PatcherAgent[[Patcher Agent]]
    PatcherAgent --> PatchEngine[[Patch Engine v2]]
    PatchEngine --> RepoChanges[(Patched Test Files\n+ Unified Diff)]
    RepoChanges --> Validator{{Validation Runner}}
    Validator -->|pass| CommitStage[Commit + Optional PR]
    Validator -->|fail| RecoveryLoop[[Error Recovery + Retry]]
    RecoveryLoop --> PlannerAgent
    Validator --> Observability[(Telemetry + Metrics)]
    Observability --> Dashboard[(Dashboard / Logs)]
```
