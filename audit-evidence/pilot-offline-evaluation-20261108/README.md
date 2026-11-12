# Pilot offline evaluation · November 8, 2026

## VE-01 baseline

All five evaluation suites passed on Python 3.12.9 and again on Python 3.14.7 with the packaged network profile. Both runs used pytest 8.4.2. All 14 fictional scenarios passed all 1,244 assertions. The runs started with a clean environment, used injected provider replies, and allowed HTTP only to disposable loopback fixtures. The macOS sandbox blocked external networking and writes to the checkout. There were zero external API calls and zero model spend.

- [Python 3.12 harness report](harness-report.json), [Python 3.14 repeat](harness-report-python314.json) and [persona summary](persona-summary.json)
- [Build receipt](build-receipt.json) and [scoped input file hashes](input-manifest.json)
- [Broader advisor result and targeted diagnostics](advisor-summary.json)

This is a working-tree baseline. The checkout is based on `7d15873e98875dca7940d07903c141d19d5da333` and contains uncommitted advisor and harness inputs. The scoped manifest matched before and after the run. The receipt verifies the engine lock and records the configured model IDs and policy hash. Actual provider-resolved model versions were unobserved because model replies were injected. Neither local Git copy contained a confirmed exact merged P03 Milestone A build. The November 7 PR #4 receipt is for repository controls and the pilot rehearsal code is tracked separately. VE-01 remains open for the exact build. [P03 acceptance](../../docs/project/COLLIER_MVP.md#actionable-backlog) · [PR #4 scope](../pilot-p0-security-20261107/README.md)

The broader advisor command ran 1,077 tests and reported 12 failures and nine errors. It explicitly excludes the accepted-reference replay module. All seven tests in the model module passed when rerun with the locally installed `jsonschema` 4.25.1. The older comparison fixture failed at setup because it expects an archived profile capture hash. The original comparison verifier replayed all six historical result cells in a temporary root with the exact archived file. The current advisor comparison HTTP suite remains open. Remaining failures include education and timing expectations, visit ambiguity state and historical task replay. The targeted results do not replace the broader run.

## Repeat the offline run on the exact merged build

Use a clean copy of the P03 build and verify that it contains the full harness and the exact permitted fixtures. Use Python 3.11 or newer and Node, and provide `pytest` in an isolated environment. The broader advisor command also uses `jsonschema`. The local setup reused installed packages and performed no network installs. An existing local wheel directory can also be used with `pip --no-index --find-links` when available.

The commands below are for macOS. Run from the root of the clean checkout. Set `daylight_packet` to the absolute path to this packet and `daylight_python` to the absolute path to the isolated Python interpreter. Copy the Python loopback guard into that environment, then run the harness with the network profile. The test environment drops the original environment variables, and the report is written outside the repo.

```sh
daylight_site=$("$daylight_python" -B -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
cp "$daylight_packet/daylight_loopback_guard.py" "$daylight_site/"
printf 'import daylight_loopback_guard\n' > "$daylight_site/daylight_loopback_guard.pth"

daylight_output=$(mktemp -d /private/tmp/daylight-evaluation.XXXXXX)
daylight_path="$PATH"
env -i PATH="$daylight_path" PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  TMPDIR="$daylight_output" /usr/bin/sandbox-exec -D "DAYLIGHT_REPO=$PWD" \
  -f "$daylight_packet/loopback-only.sb" "$daylight_python" -B \
  tools/evaluation/run_suites.py --out "$daylight_output/harness"
```

For the broader advisor command, use the same guarded invocation with `tools/run_advisor_checks.py` in place of `tools/evaluation/run_suites.py --out ...`. Archive the report and record the full merged commit, engine lock hash, model policy hash, configured model IDs, Python version and exact permitted evidence inputs. Distinguish offline results from P03 founder review, source acceptance and pilot launch approval.

## VE-03 reviewer handoff

The [independent review packet](REVIEWER.md) uses the existing 10 personas and four variants. The input file contains the reported actions and no test assertions or outputs. The reviewer authors the expected decisions, binds them to exact sources, methods and build, then signs the exact P0 samples. The reviewer assignment, source selection and approval, answer key and sample sign-off remain open under DQ-02, DQ-25 and VE-03.
