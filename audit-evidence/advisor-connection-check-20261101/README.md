# Local connection check · November 1, 2026

Owner reported `NetworkError when attempting to fetch resource. Your input is preserved.` after local launch.

The local job was running and listening on 127.0.0.1:8893. The error log had no new November 1 failure; the displayed browser tab contained the landing page, with no matching console warning/error. Two retained tabs were connection-error pages. This establishes an earlier/local browser connection failure, but does not identify the exact failed request or prove a particular timeout/root cause.

Verification went beyond the homepage:

- `/api/status` reported the configured AI service available under the existing $5 shared policy.
- A fresh test session completed `/api/conversation/initial` and a no-AI `POST /api/conversation/turn` with HTTP 200 and zero AI calls. No supplied user message was replayed.
- A separate agent-created browser tab used the real :8893 Send path with the fictional request “I’m new to Medicare and want to understand the basics.” It received a sourced generated explanation, cleared the submitted draft after success and displayed no network/status error. [Actual capture](send-verified.png). Browser error/warning logs were empty afterward.

The user's original tab/draft was not refreshed, edited or resent. The test tab was closed. No application code, styling, permissions, model choice or source gates changed, and no automatic retry or ledger reset was performed. The test used the existing bounded two-stage model path; there was no broader paid matrix. If the original transport error recurs, capture that specific request rather than attributing it to model prompting or treating homepage availability as proof of Send reliability.
