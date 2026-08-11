# Plan Lifecycle

Complex changes use one branch-scoped plan under `plans/`. The plan path is the stable identity for that task and appears only once in `PLANS.md`; an existing plan is resumed or handed off rather than overwritten.

Each plan records motivation, scope, non-goals, frozen interfaces, tasks, validation, decisions and unresolved risks. Stable facts belong in `docs/`; plans must not claim that proposed work is already implemented.

A Draft PR may keep an `in_progress` plan when real-data or human-review gates remain open. Before a PR becomes ready to merge, record final evidence and either complete the plan or split every remaining item into an explicit follow-up plan. Completed plans are removed from `PLANS.md`; their implementation and verification history remains in Git.
