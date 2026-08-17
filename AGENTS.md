# Project delivery instructions

## Publish completed changes

For every completed application change or repair in this repository:

1. Preserve unrelated user changes and stage only files that belong to the task.
2. Run the relevant backend, frontend, build, export, and regression checks in proportion to the change.
3. Do not publish a change while a required check is failing. Fix the failure and rerun the check.
4. Commit the completed task on a `codex/` branch and push that branch to `origin`.
5. Merge the verified branch into `main`, push `main`, and allow the configured production deployments to run.
6. Monitor CI, Vercel, Render, and the production smoke workflow until they reach a terminal result.
7. If deployment or smoke verification fails, diagnose it, implement the in-scope repair, and repeat the verified publish flow.
8. Report the commit, pushed branch, merge result, deployment status, tests, and any remaining risk.

The standing authorization above applies to normal code publication and deployment for completed changes and repairs. It does not authorize destructive data operations, secret changes, paid external actions, or unrelated modifications. Stop and ask for direction when one of those is required.

## Release invariants

- Never weaken fact, source, teacher-approval, privacy, or export gates merely to make a test pass.
- Unverified content must not be released as approved material.
- Every asynchronous generation job must terminate as completed, review-required, failed, or cancelled.
- Do not merge unrelated or obsolete branches only because they exist; compare their effective changes with `main` first.
