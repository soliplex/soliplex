Manage GitHub pull requests - create, review, update, and merge PRs.

## Arguments

- (none) - Auto-detect: show PR status or offer to create
- `create` - Create a new PR from current branch
- `create --draft` - Create a draft PR
- `review [number]` - Review a PR (defaults to current branch's PR if no number)
- `status` - Show current branch's PR status
- `list` - List open PRs
- `update` - Update current branch's PR title/body
- `merge [number]` - Merge a PR (defaults to current branch's PR)
- `close [number]` - Close PR without merging

## Content Guidelines

IMPORTANT: All PR content (titles, descriptions, review comments) must NOT include any AI-generated branding, watermarks, or attribution text.

## Instructions

### Setup (run for all modes)

1. Get repo info: Parse owner/repo from `git remote get-url origin`
2. Get current branch: `git branch --show-current`
3. Detect default branch: `git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'`
4. Get authenticated user: `mcp__github__get_me`

### Mode: Auto-Detect (no argument)

1. Search for open PR from current branch using `mcp__github__search_pull_requests`
2. If PR exists: Show status (title, state, checks, reviews)
3. If no PR: Ask if user wants to create one

### Mode: Create

Prerequisites:
- Current branch is not the default branch (main/master)
- Branch is pushed to remote (check with `git rev-parse --abbrev-ref @{upstream}`)

Steps:
1. Check if PR already exists for this branch
2. Get commits since default branch: `git log <default>..HEAD --oneline`
3. Get diff stats: `git diff <default> --stat`
4. Check for PR template (in order):
   - `.github/PULL_REQUEST_TEMPLATE.md`
   - `.github/pull_request_template.md`
   - `PULL_REQUEST_TEMPLATE.md`
   - `docs/PULL_REQUEST_TEMPLATE.md`
5. **Auto-detect issue from branch name** using patterns:
   - `123-description` → #123
   - `feature/123-description` → #123
   - `issue-123-description` → #123
   - `fix/123` → #123
6. **Ask user for issues to link** via `AskUserQuestion`:
   - "Which GitHub issue(s) should this PR close? (space-separated, e.g., '123 456', or 'none')"
   - Pre-fill suggestion if auto-detected
7. **Fetch issue details** for each issue number:
   - Use `mcp__github__issue_read` (method: get) to get title
   - Skip and warn if issue not found
8. Draft PR title and body:
   - Title: Primary commit message or branch name (cleaned up)
   - Body: Use template if found, populate with:
     - Summary from commit messages
     - **Related Issues section** with `Closes #X - {title}` for each linked issue
9. Present draft to user for review/edits
10. After user confirms, create PR with `mcp__github__create_pull_request`
    - Use `draft: true` if `--draft` flag was passed
11. Return PR URL

### Mode: Review

Steps:
1. If no PR number provided, find PR for current branch
2. Get PR details: `mcp__github__pull_request_read` (method: get)
3. Get PR diff: `mcp__github__pull_request_read` (method: get_diff)
4. Get existing comments: `mcp__github__pull_request_read` (method: get_review_comments)
5. Analyze changes for:
   - Code quality issues
   - Missing tests
   - Documentation gaps
   - Security concerns
6. Present findings to user with suggested review action (APPROVE, REQUEST_CHANGES, COMMENT)
7. If user approves, submit review with `mcp__github__pull_request_review_write`

### Mode: Status

1. Find PR for current branch using `mcp__github__search_pull_requests`
2. Get PR status: `mcp__github__pull_request_read` (method: get_status)
3. Display: title, state, CI checks, requested reviewers, review status, comment count

### Mode: List

1. Use `mcp__github__list_pull_requests` with state: open
2. Display table: number, title, author, created date, review status

### Mode: Update

1. Find PR for current branch
2. Get current PR details
3. Present current title/body to user
4. Get updated title/body from user
5. Update with `mcp__github__update_pull_request`

### Mode: Merge

1. If no PR number, find PR for current branch
2. Get PR status and check if mergeable
3. Show merge options: merge commit, squash, or rebase
4. After user confirms method, merge with `mcp__github__merge_pull_request`

### Mode: Close

1. If no PR number, find PR for current branch
2. Confirm with user
3. Close with `mcp__github__update_pull_request` (state: closed)