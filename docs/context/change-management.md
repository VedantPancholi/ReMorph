# Change Management

## Rule

Every code edit must have a matching documentation update in this repository.

## Required Updates Per Change

- Add a concise entry to `docs/changes/change-log.md`
- Add or extend the latest session note in `docs/journal/implementation-journal.md`
- Update the most relevant runbook, contract, or context file when behavior changes

## What To Record

- what changed
- why the change was made
- which files were touched
- any assumptions or follow-up risks

## Minimum Standard

A change is not considered complete until:

- the code is updated
- the run instructions still match reality
- handoff docs still match the current contract
- the change log and implementation journal reflect the new state

## Intent

This keeps the project auditable while we move fast, and it matches the
production mindset requested for the repository.
