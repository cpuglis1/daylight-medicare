# Diagnostic calibration cases

Each JSONL file contains 80 fictional, single-scored-turn cases for one diagnostic judge. Each judge has 16 scenario families with five variations in phrasing or visit context per family. A seeded random draw (20261124) selected six complete families for the held-out split, leaving ten for training. The assignments are stored in the case files and should stay fixed while instructions are tuned. Across the files, 432 cases are self-service and 48 involve someone helping a relative.

`context` summarizes the fictional state immediately before the turn. `user_prompt` is the only user utterance in that turn. `sample_reply` and `tool_trace` are authored fixture observations. They do not record a live conversation or integration run. `expected_behavior` describes what the selected diagnostic should check. Judge requests must keep `reference_label` and `reference_reason` out of the prompt. The held-out cases belong in final scoring after the instructions have been frozen, with their labels used only to compare outputs.

Evidence entries reference exact statement text in the repository's owner-accepted `pilot-rules.json`. These entries cover general education within the 2026 Collier pilot scope. Fictional outcomes for directories, plan catalogs, handoffs and tool failures live in the fixture context or trace. Their tool names describe mocked actions where applicable and do not assert a deployed interface. An empty evidence list can be intentional, including when a current-turn lookup is missing.

Agent-authored reference labels apply to the named judge only. The five related cases in a family share their underlying scenario and often share sample replies. Interpret agreement as calibration on these fixtures. Replaying a case through a running advisor would require separate setup of the visit, applicable data, and tools. The state summary is for offline evaluation and must stay out of the visitor message.

Run `python evals/diagnostics/validate_cases.py` from the repository root to check the stored split, case schema, evidence text and corpus counts without network or model calls.

For a tuning worker, use `python3 evals/diagnostics/export_training.py /absolute/path/to/new-package` from the owner environment. Grant the worker access only to that training package in an isolated session. Full-repository access includes the operator's validation data.

From the repository root, `python3 tools/evaluation/calibrate_turns.py --suite tool_use --split training --trials 3 --reason "Review tool-use rubric" --output-dir /private/tmp/daylight-calibration` prints the selection and upper call count. This uses the D155 Python environment with PyYAML installed. An owner-requested subscription run additionally takes `--run`. Output files contain fictional judge inputs and responses; keep them in private local storage.
