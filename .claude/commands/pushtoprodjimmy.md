---
description: Commit, push to main, deploy Jimmy MCP to prod on Vercel — one command, never leave chat
---

# Push to Prod Jimmy

Ship the current state of the Jimmy MCP server to production. One command. Never leave chat.

## The Flow

### Step 1: Pre-flight
- Run `git status` to see what's changed
- Run `git diff --stat` to summarize the scope of changes
- If there are no changes, stop and say so — nothing to push

### Step 2: Confirm scope
Show Ethan:
- Files changed (focused on `mcp_servers/ghl/` and `api/mcp.py`)
- Brief summary of what's new or different
- Any non-MCP files that are also staged (flag these — might be unintentional)

### Step 3: Commit
- Stage the relevant files (prefer specific files over `git add -A`)
- Write a clear commit message describing what changed in the MCP server
- Commit

### Step 4: Push
- Push to `main` (or current branch if working on a PR)
- Vercel auto-deploys on push to main — no manual deploy needed

### Step 5: Verify deployment
- Wait ~30 seconds for Vercel to pick up the push
- Run `curl -s -o /dev/null -w "%{http_code}" https://jimmy-sooty.vercel.app/api/mcp` to confirm the endpoint is responding
- If the deploy is still building, check with `npx vercel ls` or just hit the URL again in a moment
- Report: deployed, endpoint live, Andrej's next message will use the new version

### Step 6: Summary
Tell Ethan:
- What was shipped
- That it's live
- What Andrej will experience differently (new tools, improved responses, etc.)

## Rules
- Never force push
- Never push secrets, `.env` files, or tokens
- If there are merge conflicts, stop and resolve them first
- If the deploy fails, diagnose from the conversation — don't tell Ethan to go check Vercel dashboard
- Always end with confirmation that the endpoint is live
