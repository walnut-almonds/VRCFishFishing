# VRC Fish Fishing
## 概要

這是一個透過 python 實現的 VRC Fish 地圖自動化釣魚程式，
流程為 拋勾->等待咬勾(咬勾提示音)->拉力計階段(附圖1)->回收魚

## Agent Memory (`MEMORY.md`)

Use `MEMORY.md` as the shared, persistent memory index for AI agents in this repository.

### Purpose
- Store stable project knowledge that should persist across sessions
- Reduce repeated rediscovery of commands, architecture notes, and known pitfalls
- Keep instructions in `AGENTS.md`; keep learned project facts in `MEMORY.md`

### Location and Scope
- Main file: repository root `MEMORY.md`
- Optional detail files: `memory/*.md` (topic-specific notes such as `memory/debugging.md`)
- `MEMORY.md` should remain a concise index and link/point to topic files for long details

### Required Structure (recommended)
- `## Quick Facts` - high-value facts and constraints
- `## Commands` - verified run/test/build commands
- `## Architecture Notes` - key module relationships and responsibilities
- `## Pitfalls` - recurring issues and fixes
- `## Decisions` - important trade-offs and rationale
- `## Last Updated` - date + short summary of latest meaningful change

### Maintenance Rules for Agents
- Read `MEMORY.md` at task start before making major changes
- Update memory only when information is reusable and likely to matter again
- Prefer concise bullets; move long explanations to `memory/*.md` and reference them
- Keep the most important items near the top of `MEMORY.md`
- Remove or revise outdated entries instead of only appending new text
- Never store secrets, tokens, personal data, or machine-specific private paths

### When to Update
- Add/update entries after discovering:
  - new validated project workflow or command
  - non-obvious debugging insight that saved time
  - architecture constraint that affects future changes
  - recurring failure mode and reliable mitigation

### Quality Bar
- Be specific, actionable, and repository-scoped
- Avoid task diary logs or one-off temporary notes
- Keep wording implementation-oriented so future agents can execute directly