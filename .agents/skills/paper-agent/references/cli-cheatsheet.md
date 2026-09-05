# Advanced CLI operations

Routine search, fetch, review, citation, key and cache commands are indexed in [SKILL.md](../SKILL.md). Use the underlying CLI for operations beyond those wrappers.

Run `python -m pa_cli.cli --help` in the configured paper-agent environment, then inspect the chosen command's `--help`. Subcommand names and options depend on the installed version.

| Requested task | CLI command family to inspect |
| --- | --- |
| Zotero search, push or synchronization | `zotero` |
| Obsidian/project import and synchronization | `search-and-import`, `zotero-project` |
| Candidate selection, labeling and export | `sample-pool` |
| PRISMA flow diagram | `prisma` |
| MCP configuration | `mcp` |

Use actual screening counts for PRISMA diagrams. External synchronization, labeling and MCP installation change persistent state; perform only the requested operation.

Inspect command exit status and output rather than applying a universal exit-code or JSON schema: wrappers and CLI commands differ. Use `--quiet` only where the selected command supports it.
