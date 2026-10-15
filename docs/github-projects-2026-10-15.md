# Similar-name GitHub projects: lessons for paper-agent

Reviewed 2026-10-15. These are independent projects with similar names, not our
affiliates. Primary repository files were read at the commits linked below;
their code/dependencies were not executed or installed. This is a scoped design
comparison, not an endorsement, benchmark or claim of production reliability.

| Project / inspected commit | Concrete observation | Fit for our project |
| --- | --- | --- |
| [galleonli/paper-agent](https://github.com/galleonli/paper-agent/tree/2552cb66758755f36f04166cf3ee82709c6633bc) | `paper_agent/export/bibtex_ris.py` writes BibTeX/RIS; `pipeline.py` connects selected papers to local notes, exports and digests. | Adopt the portable export idea, not scheduled discovery. Add RIS beside existing export formats; no provider or corpus required. |
| [whut09/paper_agent](https://github.com/whut09/paper_agent/tree/1f4e47980b457f9b305d5baa683e4f4eef8d22eb) | `agents/contracts.py` declares stage inputs/outputs/failures. `harness/executor.py` restores checkpoints in dependency order and records restored-stage artifacts/status. The `harness/trace.py` file itself is only a facade. | Adapt stage contracts to a local run report. Reuse our journal/jobs/evidence boundaries; avoid introducing another graph/agent framework. Existing PR #16 still needs snapshot/identity fixes. |
| [happyTonakai/PaperAgent](https://github.com/happyTonakai/PaperAgent/tree/d3eb328e71eaf628bd4efdd92dcd82bb36989cae) | `internal/export/export.go` exports session metadata/Q&A to local Obsidian Markdown and supports a configurable template. | Useful later for local report presentation. Existing Obsidian support means a second sync subsystem would duplicate work. |
| [MassEast/paper-agent](https://github.com/MassEast/paper-agent/tree/2a5c96c99a322a14c455ab59deec06213e6f96a8) | `app/models.py` separates Paper from ProjectPaper; project associations carry notes/tags/relevance reasons and enforce a project-paper uniqueness constraint. | Borrow separation of bibliographic identity from project-specific reading state. No automatic labels/crawlers; a reading queue remains deferred. |
| [bingdongni/PaperAgent](https://github.com/bingdongni/PaperAgent/tree/1fb7f313e02b6646bf876861e6b97db9216b55e3) | `paperagent/cli.py` exposes separate service, web, worker and health commands, including optional database/Redis/LLM checks. | Keep the lesson of explicit operation boundaries. Do not adopt its service/worker stack under the personal-hobbyist budget; our offline doctor already covers basic discovery. |

## Decisions and relationship to the existing Roadmap

1. **Implement `[P3-43]` RIS export now**, as a subtask of the existing `[P0-16]`
   structured export capability. Missing today: an offline standard reference
   interchange file. Preserve Unicode, authors, real DOI/arXiv distinction,
   container metadata and optional fields. Use independent implementation;
   external source is an idea reference, not copied code.
2. **Propose `[P3-44]` local run report**, refining historical M4 in
   `docs/roadmap-skill-reliability-2026-09.md`. Join explicit existing result
   files/statuses, version/schema and artifact references without rerunning any
   stage. Do not claim hashes establish scientific correctness. Snapshot/identity
   correctness of PR #16 remains a prerequisite for its evidence-specific part.
3. **Defer reading queues/templates** under existing project/Obsidian surfaces;
   avoid another database or competing identity system until a concrete workflow
   warrants it. Collection, human labels, rankings and all dependent scientific
   evaluation remain indefinitely suspended.

The expected benefit of RIS is simpler file interchange; actual import behavior
in a particular Zotero/EndNote/Mendeley version needs an operator check. Fixture
tests establish exported structure and metadata preservation, not all-client
compatibility. No notifications, account linking, hosted services, model training
or paid calls are included. Sources are separate codebases, not independent
scientific validation of these design choices.
