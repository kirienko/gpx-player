---
name: review-pr-comments
description: Review unresolved bot comments (e.g. @coderabbitai) on a GitHub PR of the gpx-player repo, fix legitimate issues, reply with commit links, and dismiss non-applicable ones with a reason.
user_invocable: true
---

# Review PR Comments (gpx-player)

Triage and address unresolved review comments from automated bots on a PR of
`kirienko/gpx-player`. This project is Python-only with a single test suite.

## Arguments

- First argument (optional): PR number or URL. If omitted, detect the PR for
  the current branch.
- `--bot <name>`: Bot username to filter (default: `coderabbitai[bot]`).
- `--dry-run`: Assess comments without making changes.

## Tools

- GitHub is accessed **exclusively via the `mcp__github__*` MCP tools**. The
  `gh` CLI is not available in this environment.
- Tests run with `python -m pytest tests/ -q` from the repo root.
- If `requirements.txt` or `pyproject.toml` changes, also run
  `pip-audit -r requirements.txt` (if `pip-audit` is installed; skip otherwise
  and note it).

## Workflow

1. **Identify the PR.**
   - Prefer the argument. Otherwise use `mcp__github__list_pull_requests` with
     `head=<current-branch>` on `kirienko/gpx-player` and pick the open PR.

2. **Fetch review threads.** Use `mcp__github__pull_request_read` with
   `method=get_review_comments` to list all review comments, and
   `method=get_reviews` plus `get_comments` as needed. There is no direct
   GraphQL for thread-resolution state via this MCP server, so derive
   resolution as follows:
   - Treat a thread's top-level review comment as "unresolved" if the MCP tool
     `mcp__github__pull_request_read` with `method=get_review_comments`
     returns it **and** it has no sibling reply whose body contains a resolution
     marker such as "Addressed in" or a collaborator's acknowledgement.
   - When in doubt, fall back to `mcp__github__pull_request_read` to fetch
     full comment threads and inspect replies.
   - Use `mcp__github__resolve_review_thread` to mark threads resolved after
     posting the reply, so subsequent runs skip them.

3. **Filter by bot.** Keep only threads whose top-level comment is authored by
   the target bot (default `coderabbitai[bot]`). Ignore replies from humans or
   other bots when deciding authorship.

4. **Read each comment.** For every candidate thread extract:
   - File path and line number (`path`, `line` / `original_line`).
   - Severity tag (Critical / Major / Minor) if present in the body.
   - The concrete suggested fix or the "Prompt for AI Agents" block.

5. **Evaluate against current code.** Open the referenced file with the
   `Read` tool and decide:
   - `fix` — legitimate, will address.
   - `dismiss` — not applicable, wrong, or the tradeoff is intentional.
   - `skip` — already fixed in a later commit (verify by reading the file).

6. **For comments classified as `fix`:**
   - Implement the change using `Edit` / `Write`.
   - **Run tests BEFORE committing:** `python -m pytest tests/ -q`.
   - If `requirements.txt` or `pyproject.toml` changed, also run
     `pip-audit -r requirements.txt` when available.
   - **If any test fails:** do NOT stage or commit. Record the failure for
     the summary table and move on — do not attempt repeated fixes in the
     same run.
   - **If tests pass:** `git add <changed files>` and create one commit per
     comment. Commit message format:
     `fix: <short summary> (PR #<num> review)`
     Do NOT push yet.

7. **For comments classified as `dismiss`:** draft a one-paragraph reply that
   explains why the finding does not apply. Cite file/line if relevant.

8. **After processing all comments:**
   - Push only if every attempted fix's test run passed:
     `git push origin <branch>`.
   - Reply to each addressed comment via
     `mcp__github__add_reply_to_pull_request_comment` with the form:
     `Addressed in <short-sha>: <brief description>`
     (include a link of the form
     `https://github.com/kirienko/gpx-player/commit/<sha>`).
   - Reply to each dismissed comment via the same tool with the reasoning.
   - After posting the reply, call `mcp__github__resolve_review_thread` on
     the thread so the next run skips it.
   - For any fix that failed tests, do NOT reply; surface the failure in the
     summary so the user can decide.

9. **Print a summary table** at the end:

   | # | File:Line | Issue | Action | Commit |
   |---|-----------|-------|--------|--------|

## Rules

- Always read the referenced file before deciding; the code may have moved
  since the comment was posted.
- One commit per addressed comment. Keep each commit focused.
- Tests must pass before committing **any** fix.
- Push all commits together (single `git push`) to keep CI runs to one.
- Only interact with `kirienko/gpx-player` — the MCP scope is restricted to
  that repo anyway.
- When replying, thread replies correctly via
  `mcp__github__add_reply_to_pull_request_comment` using the top-level
  comment's id.
- Do not modify files unrelated to the comment being addressed.
- If a comment references a "Prompt for AI Agents" block, treat it as
  guidance but verify against the current code first.
- Validate YAML / TOML / JSON syntax after editing config files
  (`python -c "import tomllib; tomllib.loads(open('pyproject.toml').read())"`
  for TOML on Python 3.11+, or `python -m json.tool` for JSON).
- If `--dry-run`, print the assessment table only and make no changes.
