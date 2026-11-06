# Progress

## 2026-11-05

- Created the personal agent-harness-lab repository.
- Added the model-free Backend experiment and report.
- Added the initial project layout and README.
- Implemented the first model-backed coding baseline and a three-task starter set.
- Added offline tests for diff generation.
- Adapted the baseline to Qwen through DashScope's OpenAI-compatible API.
- Expanded the starter set to 10 baseline tasks covering boundary tests and small implementation changes.
- Recorded the first baseline failure analysis, including model connection, local setup permission, and quota failures.
- Switched the active provider to DeepSeek and completed the latest valid run for all 10 baseline tasks.
- Added timestamped lifecycle events to new `run.json` artifacts and validated them on seven DeepSeek runs.
- Implemented Policy Middleware v1 for tool allowlists, path traversal and sensitive-file rejection, delete blocking, and call budgets.
- Added policy unit tests and completed one DeepSeek regression run with policy decision events.
- Added offline Agent-graph integration tests for path traversal, sensitive files, delete, and tool-budget denial.
- Added Policy v2 command risk classification and an approval callback contract, with offline graph integration tests.

## Next

- Preserve the 10-task Baseline matrix as the comparison set for the first enhanced Harness version.
- Add structured setup-error reporting before testing recovery and replay behavior.
- Begin Recovery Middleware experiments with injected test and tool failures.
