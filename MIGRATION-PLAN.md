# Repository Migration Plan

## Overview

| Repository | Current State | Target State |
|------------|--------------|--------------|
| `soliplex/soliplex` | Monorepo with backend, frontend, docs | Backend only (keep new_frontend branch) |
| `soliplex/flutter` | Empty | Flutter frontend with full history |
| `soliplex/docs` | Empty, public | MkDocs documentation site |
| `soliplex/ingester` | No branch protection | Protected main, CI enabled |
| `soliplex/whitelabel` | Empty, public | Customer appshell template, best practices enabled |

## Configuration Decisions

- **PR Approvals:** 0 required (status checks only)
- **PR Merge Strategy:** Squash and merge (default)
- **Flutter Git History:** Preserved via git-filter-repo
- **new_frontend branch:** Keep as-is (not archived)
- **Flutter CI:** Full (analyze, format, test)

### Repo Settings Template (apply to flutter, docs, ingester, whitelabel)
```bash
# Set squash merge as default (disable merge commit and rebase)
gh repo edit soliplex/{repo} \
  --enable-squash-merge \
  --disable-merge-commit \
  --disable-rebase-merge \
  --delete-branch-on-merge
```

---

## Milestone 1: Prepare Infrastructure & Secrets

**Goal:** Set up shared secrets and validate tooling

### Tasks

1. **Verify SLACK_NOTIFY_URL secret exists in soliplex/soliplex**
   ```bash
   gh secret list --repo soliplex/soliplex
   ```

2. **Add SLACK_NOTIFY_URL secret to target repos**
   ```bash
   # Get the value from your Slack webhook configuration
   gh secret set SLACK_NOTIFY_URL --repo soliplex/flutter
   gh secret set SLACK_NOTIFY_URL --repo soliplex/docs
   gh secret set SLACK_NOTIFY_URL --repo soliplex/ingester
   gh secret set SLACK_NOTIFY_URL --repo soliplex/whitelabel
   ```

3. **Verify git-filter-repo is installed**
   ```bash
   git-filter-repo --version
   # If not installed:
   brew install git-filter-repo  # macOS
   # or: pip install git-filter-repo
   ```

4. **Enable GitHub Pages on soliplex/docs**
   ```bash
   gh repo edit soliplex/docs --enable-pages
   ```

5. **Configure squash-merge as default for all target repos**
   ```bash
   for repo in flutter docs ingester whitelabel; do
     gh repo edit soliplex/$repo \
       --enable-squash-merge \
       --disable-merge-commit \
       --disable-rebase-merge \
       --delete-branch-on-merge
   done
   ```

6. **Enable Secret Scanning on all repos**
   ```bash
   # Note: Secret scanning may require GitHub Advanced Security for private repos
   for repo in flutter docs ingester whitelabel; do
     gh api repos/soliplex/$repo -X PATCH \
       -f security_and_analysis='{"secret_scanning":{"status":"enabled"},"secret_scanning_push_protection":{"status":"enabled"}}'
   done
   ```

7. **Enable Dependabot for all repos**

   Create `.github/dependabot.yml` in each repo:
   ```yaml
   version: 2
   updates:
     # For Flutter repo
     - package-ecosystem: "pub"
       directory: "/"
       schedule:
         interval: "weekly"
       commit-message:
         prefix: "chore(deps)"

     # For Python repos (ingester, soliplex)
     - package-ecosystem: "pip"
       directory: "/"
       schedule:
         interval: "weekly"
       commit-message:
         prefix: "chore(deps)"

     # GitHub Actions (all repos)
     - package-ecosystem: "github-actions"
       directory: "/"
       schedule:
         interval: "weekly"
       commit-message:
         prefix: "chore(ci)"
   ```

8. **Create CODEOWNERS files**

   Create `.github/CODEOWNERS` in each repo:
   ```
   # Default owners for everything
   * @soliplex/core-team

   # CI/CD changes require additional review
   .github/ @soliplex/devops
   ```

### Verification
- [ ] Secrets visible in all three target repos
- [ ] git-filter-repo command available
- [ ] GitHub Pages settings accessible for docs repo
- [ ] Secret scanning enabled
- [ ] Dependabot configured
- [ ] CODEOWNERS files created

### Gate Criteria (ALL must pass before proceeding)

| Gate | Command | Expected Result |
|------|---------|-----------------|
| Secret in flutter | `gh secret list --repo soliplex/flutter \| grep SLACK` | SLACK_NOTIFY_URL listed |
| Secret in docs | `gh secret list --repo soliplex/docs \| grep SLACK` | SLACK_NOTIFY_URL listed |
| Secret in ingester | `gh secret list --repo soliplex/ingester \| grep SLACK` | SLACK_NOTIFY_URL listed |
| Secret in whitelabel | `gh secret list --repo soliplex/whitelabel \| grep SLACK` | SLACK_NOTIFY_URL listed |
| git-filter-repo | `git-filter-repo --version` | Version number printed |
| Squash merge (flutter) | `gh repo view soliplex/flutter --json squashMergeAllowed --jq '.squashMergeAllowed'` | `true` |
| Squash merge (docs) | `gh repo view soliplex/docs --json squashMergeAllowed --jq '.squashMergeAllowed'` | `true` |
| Squash merge (ingester) | `gh repo view soliplex/ingester --json squashMergeAllowed --jq '.squashMergeAllowed'` | `true` |
| Squash merge (whitelabel) | `gh repo view soliplex/whitelabel --json squashMergeAllowed --jq '.squashMergeAllowed'` | `true` |
| Merge commit disabled | `gh repo view soliplex/flutter --json mergeCommitAllowed --jq '.mergeCommitAllowed'` | `false` |
| Secret scanning | `gh api repos/soliplex/flutter --jq '.security_and_analysis.secret_scanning.status'` | `enabled` |
| Dependabot (flutter) | `gh api repos/soliplex/flutter/contents/.github/dependabot.yml --jq '.name'` | `dependabot.yml` |

**STOP:** Do not proceed to Milestone 2 until all gates pass.

---

## Milestone 2: Migrate Flutter to Dedicated Repository

**Goal:** Move `src/frontend/` to `soliplex/flutter` with full git history

### Tasks

1. **Create fresh clone for filtering**
   ```bash
   cd /tmp
   git clone git@github.com:soliplex/soliplex.git flutter-migration
   cd flutter-migration
   git checkout new_frontend
   ```

2. **Extract src/frontend subdirectory with full history**
   ```bash
   git filter-repo \
     --subdirectory-filter src/frontend \
     --force
   ```
   This rewrites history so `src/frontend/` becomes the repo root.

3. **Push to soliplex/flutter**
   ```bash
   git remote add flutter git@github.com:soliplex/flutter.git
   git branch -M main
   git push -u flutter main
   ```

4. **Create Flutter CI workflow**

   Create `.github/workflows/flutter.yaml`:
   ```yaml
   name: Flutter CI

   on:
     push:
       branches: [main]
     pull_request:
       branches: [main]
     workflow_dispatch:

   jobs:
     analyze-and-test:
       runs-on: ubuntu-latest
       timeout-minutes: 15
       steps:
         - uses: actions/checkout@v4

         - name: Setup Flutter
           uses: subosito/flutter-action@v2
           with:
             channel: stable
             cache: true

         - name: Install dependencies
           run: flutter pub get

         - name: Check formatting
           run: dart format --set-exit-if-changed .

         - name: Analyze code
           run: flutter analyze --fatal-infos

         - name: Run tests
           run: flutter test --coverage

         - name: Notify Slack on failure
           if: failure()
           env:
             SLACK_NOTIFY_URL: ${{ secrets.SLACK_NOTIFY_URL }}
           run: |
             curl -X POST \
               --data-urlencode \
               "payload={\"channel\": \"#soliplex\", \"username\": \"flutter-ci\", \"text\": \":x: Flutter CI failed on ${{ github.ref }}:\n${{ github.event.head_commit.message }}\nhttps://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }}\", \"icon_emoji\": \":flutter:\"}" \
               "$SLACK_NOTIFY_URL"
   ```

5. **Add branch protection**
   ```bash
   gh api repos/soliplex/flutter/branches/main/protection -X PUT \
     --input - <<EOF
   {
     "required_status_checks": {
       "strict": true,
       "contexts": ["analyze-and-test"]
     },
     "enforce_admins": false,
     "required_pull_request_reviews": null,
     "restrictions": null,
     "required_linear_history": true,
     "allow_force_pushes": false,
     "allow_deletions": false
   }
   EOF
   ```

### Verification
- [ ] Flutter repo has commit history preserved
- [ ] CI runs on push to main
- [ ] CI runs on PRs
- [ ] Slack notification fires on failure
- [ ] Direct push to main is blocked

### Gate Criteria (ALL must pass before proceeding)

| Gate | Command | Expected Result |
|------|---------|-----------------|
| Repo not empty | `gh repo view soliplex/flutter --json isEmpty` | `"isEmpty": false` |
| Has commits | `gh api repos/soliplex/flutter/commits --jq '.[0].sha'` | Returns commit SHA |
| CI workflow exists | `gh workflow list --repo soliplex/flutter` | flutter.yaml listed |
| CI passes | `gh run list --repo soliplex/flutter --limit 1 --json conclusion` | `"conclusion": "success"` |
| Branch protected | `gh api repos/soliplex/flutter/branches/main/protection --jq '.required_linear_history.enabled'` | `true` |
| PR required | Create test branch, attempt push to main | Push rejected |

**Gate Test:** Create a test PR with intentional lint error, verify CI fails and Slack notification fires.

**STOP:** Do not proceed to Milestone 3 until all gates pass.

---

## Milestone 3: Migrate Documentation to Dedicated Repository

**Goal:** Move `docs/` and `mkdocs.yml` to `soliplex/docs`

### Tasks

1. **Create fresh clone for docs filtering**
   ```bash
   cd /tmp
   git clone git@github.com:soliplex/soliplex.git docs-migration
   cd docs-migration
   ```

2. **Extract docs with history**
   ```bash
   git filter-repo \
     --path docs/ \
     --path mkdocs.yml \
     --force
   ```

3. **Push to soliplex/docs**
   ```bash
   git remote add docs git@github.com:soliplex/docs.git
   git branch -M main
   git push -u docs main
   ```

4. **Update mkdocs.yml** to point to new repo
   ```yaml
   repo_url: https://github.com/soliplex/docs
   repo_name: soliplex/docs
   ```

5. **Create docs build/deploy workflow**

   Create `.github/workflows/build-docs.yml`:
   ```yaml
   name: Build and Deploy Docs

   on:
     push:
       branches: [main]
     workflow_dispatch:

   permissions:
     contents: write
     pages: write
     id-token: write

   jobs:
     deploy:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4

         - name: Configure Git
           run: |
             git config user.name github-actions[bot]
             git config user.email 41898282+github-actions[bot]@users.noreply.github.com

         - uses: actions/setup-python@v5
           with:
             python-version: '3.x'

         - name: Cache MkDocs
           uses: actions/cache@v4
           with:
             key: mkdocs-material-${{ github.run_id }}
             path: .cache
             restore-keys: mkdocs-material-

         - name: Install dependencies
           run: pip install mkdocs-material

         - name: Deploy to GitHub Pages
           run: mkdocs gh-deploy --force

         - name: Notify Slack on failure
           if: failure()
           env:
             SLACK_NOTIFY_URL: ${{ secrets.SLACK_NOTIFY_URL }}
           run: |
             curl -X POST \
               --data-urlencode \
               "payload={\"channel\": \"#soliplex\", \"username\": \"docs-ci\", \"text\": \":x: Docs deployment failed\nhttps://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }}\", \"icon_emoji\": \":books:\"}" \
               "$SLACK_NOTIFY_URL"
   ```

6. **Create PR validation workflow**

   Create `.github/workflows/docs-pr.yml`:
   ```yaml
   name: Validate Docs PR

   on:
     pull_request:
       branches: [main]

   jobs:
     validate:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4

         - uses: actions/setup-python@v5
           with:
             python-version: '3.x'

         - name: Install dependencies
           run: pip install mkdocs-material

         - name: Build docs (validation)
           run: mkdocs build --strict

         - name: Notify Slack on failure
           if: failure()
           env:
             SLACK_NOTIFY_URL: ${{ secrets.SLACK_NOTIFY_URL }}
           run: |
             curl -X POST \
               --data-urlencode \
               "payload={\"channel\": \"#soliplex\", \"username\": \"docs-ci\", \"text\": \":x: Docs PR validation failed\nhttps://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }}\", \"icon_emoji\": \":books:\"}" \
               "$SLACK_NOTIFY_URL"
   ```

7. **Add branch protection**
   ```bash
   gh api repos/soliplex/docs/branches/main/protection -X PUT \
     --input - <<EOF
   {
     "required_status_checks": {
       "strict": true,
       "contexts": ["validate"]
     },
     "enforce_admins": false,
     "required_pull_request_reviews": null,
     "restrictions": null,
     "required_linear_history": true,
     "allow_force_pushes": false,
     "allow_deletions": false
   }
   EOF
   ```

### Verification
- [ ] Docs repo has commit history
- [ ] mkdocs build succeeds
- [ ] GitHub Pages serves docs at soliplex.github.io/docs
- [ ] PR validation workflow runs
- [ ] Branch protection active

### Gate Criteria (ALL must pass before proceeding)

| Gate | Command | Expected Result |
|------|---------|-----------------|
| Repo not empty | `gh repo view soliplex/docs --json isEmpty` | `"isEmpty": false` |
| Has mkdocs.yml | `gh api repos/soliplex/docs/contents/mkdocs.yml --jq '.name'` | `mkdocs.yml` |
| Has docs/ | `gh api repos/soliplex/docs/contents/docs --jq '.[0].name'` | Returns file name |
| Deploy workflow | `gh workflow list --repo soliplex/docs` | build-docs.yml listed |
| Deploy succeeds | `gh run list --repo soliplex/docs --workflow build-docs.yml --limit 1 --json conclusion` | `"conclusion": "success"` |
| PR validation | `gh workflow list --repo soliplex/docs \| grep docs-pr` | docs-pr.yml listed |
| Branch protected | `gh api repos/soliplex/docs/branches/main/protection --jq '.required_linear_history.enabled'` | `true` |
| Pages live | `curl -s -o /dev/null -w "%{http_code}" https://soliplex.github.io/docs/` | `200` |

**Gate Test:** Create PR with broken markdown link, verify validation fails.

**STOP:** Do not proceed to Milestone 4 until all gates pass.

---

## Milestone 4: Configure Ingester Repository

**Goal:** Add CI and branch protection to existing ingester repo

### Tasks

1. **Clone and analyze ingester structure**
   ```bash
   gh repo clone soliplex/ingester /tmp/ingester-check
   cd /tmp/ingester-check
   ls -la
   cat pyproject.toml  # or package.json, Cargo.toml, etc.
   ```

2. **Create appropriate CI workflow** based on language

   (Workflow will depend on ingester's tech stack - Python, Node, etc.)

3. **Add Slack notification on failure** (same pattern as above)

4. **Add branch protection**
   ```bash
   gh api repos/soliplex/ingester/branches/main/protection -X PUT \
     --input - <<EOF
   {
     "required_status_checks": {
       "strict": true,
       "contexts": ["<ci-job-name>"]
     },
     "enforce_admins": false,
     "required_pull_request_reviews": null,
     "restrictions": null,
     "required_linear_history": true,
     "allow_force_pushes": false,
     "allow_deletions": false
   }
   EOF
   ```

### Verification
- [ ] CI runs on push/PR
- [ ] Slack notifications work
- [ ] Branch protection active

### Gate Criteria (ALL must pass before proceeding)

| Gate | Command | Expected Result |
|------|---------|-----------------|
| CI workflow exists | `gh workflow list --repo soliplex/ingester` | CI workflow listed |
| CI passes | `gh run list --repo soliplex/ingester --limit 1 --json conclusion` | `"conclusion": "success"` |
| Branch protected | `gh api repos/soliplex/ingester/branches/main/protection --jq '.required_linear_history.enabled'` | `true` |
| Direct push blocked | Attempt `git push origin main` from test branch | Push rejected |

**Gate Test:** Create PR with intentional test failure, verify CI fails and Slack notification fires.

**STOP:** Do not proceed to Milestone 5 until all gates pass.

---

## Milestone 5: Cleanup soliplex/soliplex

**Goal:** Remove redundant CI and update references

### Tasks

1. **Remove docs CI from soliplex/soliplex**
   ```bash
   git rm .github/workflows/build-docs.yml
   git commit -m "chore: remove docs CI (moved to soliplex/docs)"
   ```

2. **Update README.md** with links to new repos
   ```markdown
   ## Related Repositories

   - **Flutter Frontend:** [soliplex/flutter](https://github.com/soliplex/flutter)
   - **Documentation:** [soliplex/docs](https://github.com/soliplex/docs)
   - **Ingester:** [soliplex/ingester](https://github.com/soliplex/ingester)
   ```

3. **Keep new_frontend branch** as-is for reference

### Verification
- [ ] build-docs.yml removed from main
- [ ] README updated
- [ ] new_frontend branch unchanged

### Gate Criteria (ALL must pass before proceeding)

| Gate | Command | Expected Result |
|------|---------|-----------------|
| build-docs.yml removed | `gh api repos/soliplex/soliplex/contents/.github/workflows/build-docs.yml` | 404 Not Found |
| README updated | `gh api repos/soliplex/soliplex/contents/README.md --jq '.content' \| base64 -d \| grep 'soliplex/flutter'` | Match found |
| new_frontend exists | `gh api repos/soliplex/soliplex/branches/new_frontend --jq '.name'` | `new_frontend` |
| Main still works | `gh run list --repo soliplex/soliplex --branch main --limit 1 --json conclusion` | `"conclusion": "success"` |

**STOP:** Do not proceed to Milestone 6 until all gates pass.

---

## Milestone 6: Validation & Documentation

**Goal:** End-to-end testing and documentation

### Tasks

1. **Test Flutter repo**
   - Create test branch
   - Open PR
   - Verify CI runs
   - Verify merge blocked without passing CI
   - Force failure to test Slack notification

2. **Test Docs repo**
   - Create test branch with intentional mkdocs error
   - Verify PR validation fails
   - Fix and verify deployment works

3. **Test Ingester repo**
   - Similar PR workflow test

4. **Add PR and Issue templates to all repos**

   Create `.github/ISSUE_TEMPLATE/bug_report.md`:
   ```markdown
   ---
   name: Bug Report
   about: Report a bug or unexpected behavior
   labels: bug
   ---

   ## Description
   A clear description of the bug.

   ## Steps to Reproduce
   1.
   2.
   3.

   ## Expected Behavior
   What you expected to happen.

   ## Actual Behavior
   What actually happened.

   ## Environment
   - OS:
   - Version:
   ```

   Create `.github/ISSUE_TEMPLATE/feature_request.md`:
   ```markdown
   ---
   name: Feature Request
   about: Suggest a new feature
   labels: enhancement
   ---

   ## Problem
   What problem does this solve?

   ## Proposed Solution
   How should this work?

   ## Alternatives Considered
   Other approaches you've thought about.
   ```

   Create `.github/PULL_REQUEST_TEMPLATE.md`:
   ```markdown
   ## Summary
   Brief description of changes.

   ## Changes
   -

   ## Test Plan
   - [ ] Tests pass locally
   - [ ] Manual testing completed

   ## Related Issues
   Fixes #
   ```

5. **Add status badges to README files**

   For Flutter repo:
   ```markdown
   # Soliplex Flutter

   [![Flutter CI](https://github.com/soliplex/flutter/actions/workflows/flutter.yaml/badge.svg)](https://github.com/soliplex/flutter/actions/workflows/flutter.yaml)
   ```

   For Docs repo:
   ```markdown
   # Soliplex Documentation

   [![Deploy Docs](https://github.com/soliplex/docs/actions/workflows/build-docs.yml/badge.svg)](https://github.com/soliplex/docs/actions/workflows/build-docs.yml)
   ```

   For Ingester repo:
   ```markdown
   # Soliplex Ingester

   [![CI](https://github.com/soliplex/ingester/actions/workflows/ci.yaml/badge.svg)](https://github.com/soliplex/ingester/actions/workflows/ci.yaml)
   ```

   For Whitelabel repo:
   ```markdown
   # Soliplex Whitelabel

   Customer appshell template for white-label Flutter applications.

   [![CI](https://github.com/soliplex/whitelabel/actions/workflows/flutter.yaml/badge.svg)](https://github.com/soliplex/whitelabel/actions/workflows/flutter.yaml)
   ```

6. **Update organization-level documentation**
   - Document new repo structure
   - Update any onboarding docs

7. **Announce changes to team**

### Final Checklist
- [ ] All repos have CI running on push and PR
- [ ] All repos have branch protection on main
- [ ] Slack notifications fire on CI failures
- [ ] Documentation publishes from soliplex/docs
- [ ] Flutter frontend builds from soliplex/flutter
- [ ] Secret scanning enabled on all repos
- [ ] Dependabot configured on all repos
- [ ] CODEOWNERS files in all repos
- [ ] PR/Issue templates in all repos
- [ ] Status badges in all READMEs
- [ ] Team notified of changes

### Gate Criteria (Migration Complete)

| Gate | Check | Expected Result |
|------|-------|-----------------|
| Flutter CI on PR | Open PR in soliplex/flutter | CI runs automatically |
| Flutter CI blocks merge | PR with failing tests | Cannot merge |
| Docs CI on PR | Open PR in soliplex/docs | Validation runs |
| Docs deploy on merge | Merge to main | Pages updated |
| Ingester CI on PR | Open PR in soliplex/ingester | CI runs automatically |
| Whitelabel configured | `gh repo view soliplex/whitelabel --json squashMergeAllowed` | squashMergeAllowed: true |
| Slack on failure | Force CI failure in any repo | Slack #soliplex notified |
| Main repo unchanged | soliplex/soliplex main | Python CI still works |
| new_frontend preserved | soliplex/soliplex branches | new_frontend exists |
| PR templates | Open PR in any repo | Template auto-populates |
| Issue templates | Create issue in any repo | Template chooser appears |
| Status badges | View README in each repo | Badge shows CI status |

**Complete Gate Script:**
```bash
#!/bin/bash
# Run this to verify all gates pass

check_repo() {
  local repo=$1
  echo "=== Checking $repo ==="
  gh api repos/soliplex/$repo/branches/main/protection --jq '.required_linear_history.enabled' 2>/dev/null && echo "  Protected: OK" || echo "  Protected: SKIP (no main branch yet)"
  gh workflow list --repo soliplex/$repo 2>/dev/null && echo "  Workflows: OK" || echo "  Workflows: NONE"
  gh repo view soliplex/$repo --json squashMergeAllowed --jq '.squashMergeAllowed' && echo "  Squash merge: OK"
  gh api repos/soliplex/$repo --jq '.security_and_analysis.secret_scanning.status' 2>/dev/null && echo "  Secret scanning: OK" || echo "  Secret scanning: N/A"
  gh api repos/soliplex/$repo/contents/.github/dependabot.yml --jq '.name' 2>/dev/null && echo "  Dependabot: OK" || echo "  Dependabot: MISSING"
  gh api repos/soliplex/$repo/contents/.github/CODEOWNERS --jq '.name' 2>/dev/null && echo "  CODEOWNERS: OK" || echo "  CODEOWNERS: MISSING"
  gh api repos/soliplex/$repo/contents/.github/PULL_REQUEST_TEMPLATE.md --jq '.name' 2>/dev/null && echo "  PR template: OK" || echo "  PR template: MISSING"
}

check_repo flutter
check_repo docs
check_repo ingester
check_repo whitelabel

echo "=== Checking Docs Pages ==="
curl -s -o /dev/null -w "Pages HTTP: %{http_code}\n" https://soliplex.github.io/docs/

echo "=== Checking Main Repo ==="
gh api repos/soliplex/soliplex/branches/new_frontend --jq '.name' && echo "new_frontend: OK"

echo "=== All checks complete ==="
```

**MIGRATION COMPLETE** when all gates pass and team has been notified.

---

## Rollback Plan

If issues arise:

1. **Flutter repo issues:** Frontend still exists in soliplex/soliplex on new_frontend branch
2. **Docs repo issues:** Re-enable build-docs.yml in soliplex/soliplex
3. **Branch protection issues:** Remove via `gh api ... -X DELETE`

---

## Commands Reference

### Check branch protection
```bash
gh api repos/soliplex/{repo}/branches/main/protection
```

### Remove branch protection
```bash
gh api repos/soliplex/{repo}/branches/main/protection -X DELETE
```

### List secrets
```bash
gh secret list --repo soliplex/{repo}
```

### Check workflow runs
```bash
gh run list --repo soliplex/{repo}
```
