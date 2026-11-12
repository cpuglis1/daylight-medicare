# C13 — Medicare.gov policy review

Completed October 20, 2026. Exact [robots.txt](medicare-robots.txt), raw privacy/using-this-site pages and the CMS linking policy are preserved with URL, UTC time and SHA-256 in [sources.json](sources.json). [The policy decision](c13-site-policy.json) records every Allow/Disallow directive and the C16 boundaries. C12 remains complete on the owner's reported legal approval.

The saved robots file does not deny `/plan-compare/`, `/medigap-supplemental-insurance-plans/` or `/care-compare/`; all three are linked in the saved Medicare.gov navigation. These entry URLs are eligible for bounded synthetic public-page observations under G9. This does not automatically approve subroutes, API/back-end requests or other hosts. C16 must enumerate and review its actual request manifest before collection.

Robots denies `/core/` and `/profiles/` except specified CSS/JS/image patterns, and denies admin, comment/reply, filter/tips, node, Spanish node, app-static-content, search, medicare-search and user register/password/login/logout paths, plus the listed `/index.php/` equivalents. `/README.txt` and `/web.config` are denied. The exact list, including wildcard/end-marker exceptions, is retained in the JSON. `/app-static-content/` must stay blocked even if a public app depends on it. No account/member/login route is in scope.

Privacy and using-this-site explain privacy/security, accessibility, external links and reporting security issues. They do not supply a blanket automated reuse permission in the captured text. Non-denial by robots is not a legal license. This review implements the existing approved G9 boundary and does not reopen C12.

C16 retains: fixed synthetic sets, off-peak Eastern, at least five seconds between all outgoing requests, at most 2,000 requests/run, identified User-Agent, query cache, complete observation receipts, dry-run/kill switch, and stop on 403/429/CAPTCHA/block/schema change. Browser subresources must also obey the request policy. No proxies/IP rotation/login bypass and no real-user queries (H09). If required app traffic falls outside reviewed paths, stop and review that engineering dependency rather than silently allowing it. Refresh the robots/policy review after its 24-hour window; existing release freshness deadlines do not change.

Only three Medicare.gov policy GETs were made in this research, at least five seconds apart. No collector or Plan Finder scenarios were run. C16 remains open.
