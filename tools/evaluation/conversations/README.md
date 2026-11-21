# Simulated conversation cases (D155 Q7, Q8)

Fictional visitors for `tools/evaluation/sim_conversations.py`. Each case is
played against a running local advisor, then judged once per check in
`alternatives/advisor-first/config/conversation-checks.json` and once per
`must_cover` / `must_not_claim` item. Hand-run twins of these scripts are in
`docs/evaluations/hand-tests-2026-11-21/HAND_TESTS.md`.

All people, ZIPs and numbers are fictional. Never put a real or fake SSN,
Medicare number or bank number in a case.

## Running

Start the advisor (traces are on by default locally), then:

```bash
python3 tools/evaluation/sim_conversations.py --dry-run
```

```bash
python3 tools/evaluation/sim_conversations.py --base http://127.0.0.1:8893 --allow-unmetered
```

- No `--case` runs the default subset: the fewest cases that together probe
  every check. `--case <key>` (repeatable) picks cases; `--all` runs all 20.
- `--trials N` repeats each case to measure consistency.
- `--probes-only` judges only the checks a case lists in `probes`.
- Results land in `cms-slice/var/sim-runs/<time>/` (`results.json`,
  `report.md`), which is gitignored. Each turn's ID opens in the dev Turns panel
  or with `python3 tools/show_turn.py <id>`.
- Exit code: 0 all checks pass or have no data, 1 a check failed or the budget
  stopped the run, 2 a setup error.

## Cost rules

- The simulated person and the judges run through `claude -p` on Charlie's
  subscription (default models: person `sonnet`, judges `haiku,sonnet`; the
  second judge decides when the first is under 0.7 confidence).
- Daylight's own model calls are metered by the server's `/api/status`
  budget. The run stops before a turn that could push this run's spend past
  `--cap-usd` (default and maximum $10; above $10 only with `--all`).
- A fixture server has no meter, so it needs `--allow-unmetered`. Running
  against a live server spends real money: only when Charlie asks. The full
  set (about $30) runs only on request.
- The advisor allows 8 turns per visitor per minute; the runner waits out a
  429 instead of failing the turn.

## Case schema

One YAML file per case; the file name (without `.yaml`) must equal `key`.

| Field | Required | Meaning |
|---|---|---|
| `key` | yes | Same as the file stem, for example `c11-switch-self-to-mom`. |
| `title` | yes | One line saying what the case tests. |
| `probes` | yes | Check ids this case is built to exercise; each must exist in the checks file. |
| `typist` | yes | `self` or `someone`: who is typing relative to the person on Medicare. |
| `persona` | one of these | An id from `docs/evaluations/medicare-personas-2026-11-08/personas.json`; its opening and response script are used. |
| `person_brief` | one of these | Inline brief for the simulated person when there is no persona. |
| `opening` | if no persona | First message; overrides the persona's opening. |
| `replies` | no | `{if_asked_about, reply}` pairs the simulated person should use; added before the persona's script. |
| `events` | no | `{at, say}`: at message number `at`, send `say` verbatim (for example a subject switch). |
| `max_messages` | no | Messages the visitor sends before the run stops (default 8). |
| `stop_early_after` | no | The visitor leaves after this many messages (tests early exits). |
| `must_cover` | no | Things Daylight must do or say; each is judged separately. |
| `must_not_claim` | no | Things Daylight must not do or say; each is judged separately. |

Unknown fields, unknown probes or personas, and a key that does not match the
file name stop the run before any conversation starts.
