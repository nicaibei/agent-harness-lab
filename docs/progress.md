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
- Implemented Recovery Middleware v1 for transient retries, terminal-error classification, and repeated-call detection.
- Added Agent-graph integration coverage for a timeout followed by a successful retry.
- Added model-facing recovery tests for corrected tool arguments and injected test failures.
- Added Checkpoint/Replay v1 with LangGraph `InMemorySaver`, tool-boundary interruption and resume, checkpoint artifacts, and side-effect-free event replay.
- Added an offline evaluation report that separates model/setup failures from Agent task outcomes and keeps latest-valid per-task summaries.
- Added deterministic fault-injection cases for transient retry, changed tool arguments, and test failure followed by a file-changing fix.
- Added a real DeepSeek hidden-evaluator recovery fixture, an enforced baseline-test gate, and a second-run success trace after an initial hidden-test failure.
- Fixed Recovery classification for raw JSON string tool results and immediate hidden-test event recording.
- Added two more real hidden-evaluator tasks (`fractional-tax`, `parse-percent`) and a recovery matrix report: 3/3 forced-failure runs recovered successfully.
- Added a baseline-test-gate ablation run: without the gate, DeepSeek edited before the first test; with the gate, the run produced a first-test failure followed by a successful repair.
- Extended the gate ablation to `fractional-tax` and `parse-percent`; both tasks showed the same no-gate/edit-first versus gate/fail-then-repair pattern.
- Added an offline cross-file Recovery fixture where `order_parser.py` and `order_total.py` must be fixed together; the hidden evaluator fails initially and passes after both files are repaired (`43 passed`).
- Completed one authorized DeepSeek cross-file recovery run: the baseline gate forced `2 failed`, DeepSeek modified both production files, and the second hidden test run passed (`20261107T052728Z-a1313c18`).

## Next

- Preserve the 10-task Baseline matrix as the comparison set for the first enhanced Harness version.
- Evaluate whether cross-process checkpoint persistence is needed before adding a database dependency.
- Compare Baseline, Policy, Recovery, and Checkpoint/Replay metrics on the preserved 10-task matrix.
- Add controlled fault-injection tasks that produce test failures and parameter errors for Recovery evaluation.
- Add negative fault-injection cases where the model changes its action but still fails, and compare failure traces across Harness versions.
- Add two more real hidden-evaluator tasks and compare prompt-only ordering with the Harness-enforced baseline-test gate.
- Compare a fixed task with and without the Harness-enforced baseline-test gate, keeping model and fixture constant.
- Repeat the gate ablation across more than one fixture before making a recovery-rate claim.
- Add a cross-file recovery fixture to test whether the same order guarantee holds when the model changes multiple production files.
- Repeat cross-file recovery with a different business fixture before making a general cross-file recovery-rate claim.
