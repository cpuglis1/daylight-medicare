#!/usr/bin/env python3
"""Idempotently seed the requested local Daylight Paperclip instance.

Uses only the loopback API. Existing matching records are preserved, not reset.
Does not start backlog tasks, attach external connectors, or store provider keys.
"""
import json
import urllib.error
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:3100/api"
ROOT = Path(__file__).resolve().parents[2]
PC = Path.home() / ".paperclip"
BASE = PC / "workspaces/daylight-source-20261105"


def api(method, route, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(API + route, data=data, method=method,
                                 headers={"Content-Type": "application/json", "Origin": "http://127.0.0.1:3100"})
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"{method} {route}: {error.code} {error.read().decode()[:1200]}") from error


def ensure(route, key, value, payload):
    found = next((x for x in api("GET", route) if x.get(key) == value), None)
    if route.endswith("/agents"):
        found = found or api("POST", route.removesuffix("/agents") + "/agent-hires", payload)["agent"]
        if found.get("status") == "pending_approval":
            found = api("POST", f"/agents/{found['id']}/approve", {})
        return found
    return found or api("POST", route, payload)


def main():
    api("PATCH", "/instance/settings/experimental", {"enableIsolatedWorkspaces": True, "enableIsolatedWorkspacesByDefault": True})
    company = ensure("/companies", "name", "Daylight", {
        "name": "Daylight", "description": "Your coverage, plain as day. Local development coordination for Chris: Codex + Claude, code and fictional test data, exact evidence and release boundaries.",
        "budgetMonthlyCents": 0,
    })
    cid = company["id"]
    api("PATCH", f"/companies/{cid}", {"requireBoardApprovalForNewAgents": True, "feedbackDataSharingEnabled": False})
    objective = ensure(f"/companies/{cid}/goals", "title", "One complete, supported Collier consumer journey", {
        "title": "One complete, supported Collier consumer journey", "level": "company", "status": "active",
        "description": "D91: build the 2026 controlled Collier journey from consequential profile questions through actual plan tradeoffs, resolvable checks and a useful next action. Source/method/purpose acceptance and material holds remain independent of implementation progress. The full L03 archive is a separate research track.",
    })
    instructions = (ROOT / "tools/paperclip/AGENT_INSTRUCTIONS.md").read_text()
    runpath = f"{PC}/runtime/bin:{Path.home()}/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    agents = {}
    for short, name, adapter, command in [
        ("codex", "Codex", "codex_local", str(Path.home()/".local/bin/codex")),
        ("claude", "Claude", "claude_local", str(PC/"runtime/bin/claude")),
    ]:
        config = {"command": command, "engine": "cli", "cwd": str(PC/f"workspaces/daylight-{short}"),
                  "timeoutSec": 900, "graceSec": 15,
                  "env": {"PATH": runpath, "PAPERCLIP_TELEMETRY_DISABLED": "1", "DO_NOT_TRACK": "1"}}
        if short == "codex":
            config.update({"model": "gpt-6.1-sol", "modelReasoningEffort": "medium", "dangerouslyBypassApprovalsAndSandbox": False,
                           "extraArgs": ["--sandbox", "workspace-write", "-c", "approval_policy=\"never\"", "-c", "sandbox_workspace_write.network_access=true", "-c", "forced_login_method=\"chatgpt\""]})
        else:
            config["env"]["CLAUDE_CONFIG_DIR"] = str(PC/"instances/daylight/claude-beacon")
            denied = [str(Path.home()/name) for name in ["daylight", ".aws", ".ssh", ".codex", "Downloads", "Documents", "Desktop"]]
            settings = {"forceLoginMethod": "claudeai", "sandbox": {"enabled": True, "failIfUnavailable": True, "autoAllowBashIfSandboxed": True, "allowUnsandboxedCommands": False,
                                    "network": {"allowedDomains": ["127.0.0.1:3100", "localhost:3100"]},
                                    "filesystem": {"denyRead": denied}},
                        "permissions": {"deny": [f"Read({p}/**)" for p in denied]}}
            config.update({"model": "sonnet", "dangerouslySkipPermissions": False, "maxTurnsPerRun": 60,
                           "extraArgs": ["--permission-mode", "acceptEdits", "--strict-mcp-config", "--settings", json.dumps(settings)]})
        agent = ensure(f"/companies/{cid}/agents", "name", name, {
            "name": name, "role": "engineer", "title": "Daylight engineer and reviewer",
            "capabilities": "Implement bounded development tasks or independently review another agent's actual artifacts. Use only the assigned development worktree and preserve Daylight requirements.",
            "adapterType": adapter, "adapterConfig": config,
            "instructionsBundle": {"entryFile": "AGENTS.md", "files": {"AGENTS.md": instructions}},
            "runtimeConfig": {"heartbeat": {"enabled": False, "intervalSec": 0, "wakeOnDemand": True, "maxConcurrentRuns": 1}},
            "budgetMonthlyCents": 0,
            "permissions": {"canCreateAgents": False, "canCreateSkills": False},
        })
        agents[short] = {"id": agent["id"], "name": name}
    project = ensure(f"/companies/{cid}/projects", "name", "Collier 2026 pilot", {
        "name": "Collier 2026 pilot", "description": "Current advisor development and evidence review. Start with the pinned local source snapshot. Customer stores, production credentials and full research evidence are not included. Review and integrate patches deliberately into the main workspace.",
        "status": "in_progress", "goalIds": [objective["id"]],
        "workspace": {"name": "Daylight source snapshot", "cwd": str(BASE), "sourceType": "local_path", "isPrimary": True, "repoRef": "main"},
        "executionWorkspacePolicy": {"enabled": True, "defaultMode": "isolated_workspace", "allowIssueOverride": False,
            "workspaceStrategy": {"type": "git_worktree", "baseRef": "main", "branchTemplate": "codex/{{issue.identifier}}-{{slug}}", "worktreeParentDir": str(PC/"workspaces/tasks")}},
    })
    descriptions = [
        ("Start here: working with Codex and Claude", "medium", "Use New task, choose this project, write a concrete deliverable and assign Codex or Claude. Move it to Todo to start it. Each project task receives an isolated Git worktree. Keep a single implementer; request review of the exact diff/artifact from the other agent. Existing backlog items are planning entries, not scheduled jobs.\n\nBoth agents use existing subscription logins. Timer heartbeats are off. Provider subscription limits apply; the owner explicitly removed Paperclip dollar hard stops and daily-run caps. One task runs at a time per agent.\n\nThe source snapshot has current selected code/docs, no live stores or production credentials, and no push remote. It is not the whole research archive. Return patches for review and integrate deliberately. Read PAPERCLIP_WORKSPACE.json and tools/paperclip/AGENT_INSTRUCTIONS.md.\n\nTrack plan coverage, field preparation, source/method/purpose acceptance and app access separately. Source data copied or tests passed does not mean consumer approval. The November 5 stack evaluation is future context, not blanket permission to buy or deploy its proposals."),
        ("P03: establish the reproducible advisor development baseline", "high", "Inspect the selected current source snapshot. Run tools/prepare_advisor.py and relevant offline checks. Report exact commit, missing dependencies and meaningful failures without accessing the original workspace or real stores. Produce a reviewable readiness report; do not silently substitute invented source evidence."),
        ("P06/P09: review the all-72 catalog's exact serving authority", "high", "Read docs/project/COLLIER_MVP.md and r9-r13 review documents. The 72-plan local research access milestone is delivered; do not repeat it. Identify precise remaining source-use, method and consumer-purpose decisions. Report plan coverage, field preparation, acceptance and app access independently. If an underlying retained source is missing from this development snapshot, identify the task-specific input needed; do not read the original private workspace."),
        ("P07/P10: prepare one complete synthetic consumer journey", "high", "Use the r6 consumer journey contract and existing advisor architecture. Prepare a bounded implementation and verification plan for eligibility, doctor, medicine and plan tradeoffs through a useful next action. Preserve consequential intake, end confirmation, correction invalidation, independence and material holds. No consumer activation or real-person data."),
        ("Evaluate the coordination trial before expanding the stack", "low", "Compare one bounded Paperclip task and independent artifact review with the existing manual workflow. Record founder interruptions, duplicated work, review defects, elapsed time and reported model cost. Keep production/customer data outside development tooling. The owner's stack evaluation favors low operating burden and named upgrade triggers; cloud/vendor choices remain separate decisions."),
    ]
    issues = []
    for title, priority, description in descriptions:
        issue = ensure(f"/companies/{cid}/issues", "title", title, {
            "title": title, "description": description, "status": "backlog", "priority": priority,
            "projectId": project["id"], "goalId": objective["id"], "reviewPolicy": "human_only",
        })
        issues.append({"id": issue["id"], "identifier": issue["identifier"], "title": title})
    result = {"companyId": cid, "projectId": project["id"], "goalId": objective["id"], "agents": agents, "issues": issues}
    receipt = PC / "instances/daylight/daylight-setup.json"
    receipt.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
