# Daylight alternatives

The original ten-question UI remains in the root `cms-slice/` on **http://127.0.0.1:8890/**.
The separately editable chat-first UI is now in **[chat-first/](chat-first/README.md)** on **http://127.0.0.1:8891/**.
This consolidates source location only; it does not merge designs, profiles or services.

The separately implemented **[advisor-first UI](advisor-first/README.md)** runs on **http://127.0.0.1:8893/** under D86. It opens with a Medicare-specific life/context invitation, uses bounded LLM planning and inline forms, and retains its own cookie, guest store and launchd job. It shares the existing aggregate AI cap. Neither older interface is overwritten.

Edit :8891 only in `alternatives/chat-first/`. Its existing launchd runtime and saved guest information remain at `/Users/cep4u/daylight-chat-alternative-runtime`. Edit :8893 in `alternatives/advisor-first/`.
See its README for checking synchronization, running synthetic development checks, and rollback.
