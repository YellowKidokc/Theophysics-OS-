# Station Contract

Every station should be callable by a runner with the same basic contract.

## Inputs

- source path
- workflow name
- station name
- config path
- prompt path
- run id

## Outputs

- result status: `pass`, `review`, `fail`, `hold`
- output files
- log file
- optional signal
- optional next station

## Status Meanings

- `pass`: continue or route output
- `review`: place in REVIEW
- `fail`: place in ERROR
- `hold`: stop without destructive action

## Rules

- Never mutate original input in place.
- Write outputs to the packet's OUTPUT, REVIEW, ERROR, or ARCHIVE folders.
- Keep model weights and vector stores outside the repo.
- Use config examples in Git and private local configs outside Git.
