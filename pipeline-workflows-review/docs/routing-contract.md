# Routing Contract

Route stations decide where finished products go.

Common routes:

- `vault_drop`
- `r2_publish`
- `substack_queue`
- `pg_warehouse`
- `nas_archive`

Routing should be explicit and logged.

Each route station should support:

- dry run
- destination check
- write/copy
- manifest update
- rollback note
