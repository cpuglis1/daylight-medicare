---
name: daylight-verify-feature
description: "Map a Daylight feature change to observable checks, original requirements, evidence and release limits."
---

# Daylight Verify Feature

Inspired by Lauren Tan's project-local feature-verification map. Use `daylight_obsidian/02 Product/Feature map.md`, then the original capability/requirement documents and scoped AGENTS.md. Older capability cards are dated snapshots; CURRENT_STATE and newer exact evidence govern.

For the touched feature, identify its entry points, expected behavior, meaningful failure/correction/unknown states, data persistence boundary and release gates. Choose offline fictional checks that can disprove the claimed behavior. Record the exact command, environment/revision, actual result and important untested paths. Do not infer success from a test count.

For app interface changes follow the repository's desktop/tablet/phone inspection requirements. No agent-run live conversation tests or paid probes. Consumer acceptance, source acceptance and domain review remain separate. If a test needs unavailable evidence or a forbidden source route, record that gap without substituting invented evidence.

Update the affected feature note and link the evidence packet in the same task. Keep implemented, technically verified, domain-reviewed, accepted-for-purpose and user-proven states separate.
