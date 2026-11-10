#!/usr/bin/env bash
set -Eeuo pipefail

# Merge a reviewed pull request into the protected default branch.
# Default behavior is check-only. A real merge requires CONFIRM_MERGE=YES.

REPO="${REPO:-ahmadassayyaaf/polyester-testnet-trading-engine}"
HEAD_BRANCH="${HEAD_BRANCH:-feature/production-reliability-upgrade}"
BASE_BRANCH="${BASE_BRANCH:-main}"
MERGE_METHOD="${MERGE_METHOD:-squash}"
POLL_SECONDS="${POLL_SECONDS:-30}"
WAIT_SECONDS="${WAIT_SECONDS:-0}"
CONFIRM_MERGE="${CONFIRM_MERGE:-NO}"
CHECK_ONLY="${CHECK_ONLY:-NO}"

usage() {
  cat <<'USAGE'
Usage:
  scripts/merge-after-review.sh

The script locates the open PR from HEAD_BRANCH to BASE_BRANCH, then requires:
  - a clean local working tree;
  - the PR head to match origin/HEAD_BRANCH;
  - a non-draft PR with reviewDecision=APPROVED;
  - required checks to pass;
  - mergeStateStatus=CLEAN;
  - CONFIRM_MERGE=YES for the actual GitHub merge.

Environment variables:
  REPO=OWNER/REPO                         GitHub repository
  HEAD_BRANCH=feature/...                 reviewed source branch
  BASE_BRANCH=main                        destination branch
  MERGE_METHOD=squash|merge|rebase       merge strategy (default: squash)
  WAIT_SECONDS=0                          total polling window; 0 checks once
  POLL_SECONDS=30                         delay between polling attempts
  CONFIRM_MERGE=YES                      required for a real merge
  CHECK_ONLY=YES                         never merge, even with confirmation

Examples:
  CHECK_ONLY=YES scripts/merge-after-review.sh
  WAIT_SECONDS=3600 POLL_SECONDS=60 CONFIRM_MERGE=YES scripts/merge-after-review.sh
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "ERROR: required command not found: $1" >&2; exit 2; }
}

need_cmd git
need_cmd gh

if [[ "$MERGE_METHOD" != "squash" && "$MERGE_METHOD" != "merge" && "$MERGE_METHOD" != "rebase" ]]; then
  echo "ERROR: MERGE_METHOD must be squash, merge, or rebase" >&2
  exit 2
fi
if ! [[ "$WAIT_SECONDS" =~ ^[0-9]+$ && "$POLL_SECONDS" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: WAIT_SECONDS must be >= 0 and POLL_SECONDS must be a positive integer" >&2
  exit 2
fi

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: working tree is not clean; commit or stash changes before merging" >&2
  exit 3
fi

current_branch=$(git branch --show-current)
if [[ "$current_branch" != "$HEAD_BRANCH" ]]; then
  echo "ERROR: run this script from branch '$HEAD_BRANCH'; current branch is '$current_branch'" >&2
  exit 3
fi

echo "Fetching origin/$HEAD_BRANCH and origin/$BASE_BRANCH..."
git fetch --prune origin "$HEAD_BRANCH" "$BASE_BRANCH" >/dev/null

pr_count=$(gh pr list --repo "$REPO" --head "$HEAD_BRANCH" --base "$BASE_BRANCH" --state open --json number --jq 'length')
if [[ "$pr_count" != "1" ]]; then
  echo "ERROR: expected exactly one open PR from '$HEAD_BRANCH' to '$BASE_BRANCH'; found $pr_count" >&2
  exit 4
fi

pr_number=$(gh pr list --repo "$REPO" --head "$HEAD_BRANCH" --base "$BASE_BRANCH" --state open --json number --jq '.[0].number')
pr_url=$(gh pr view "$pr_number" --repo "$REPO" --json url --jq '.url')

check_pr() {
  local state draft review merge_state head_oid remote_oid checks_json checks_rc

  state=$(gh pr view "$pr_number" --repo "$REPO" --json state --jq '.state')
  draft=$(gh pr view "$pr_number" --repo "$REPO" --json isDraft --jq '.isDraft')
  review=$(gh pr view "$pr_number" --repo "$REPO" --json reviewDecision --jq '.reviewDecision // ""')
  merge_state=$(gh pr view "$pr_number" --repo "$REPO" --json mergeStateStatus --jq '.mergeStateStatus // ""')
  head_oid=$(gh pr view "$pr_number" --repo "$REPO" --json headRefOid --jq '.headRefOid')
  remote_oid=$(git rev-parse "origin/$HEAD_BRANCH")

  if [[ "$state" != "OPEN" ]]; then
    echo "ERROR: PR #$pr_number is not open: $state" >&2
    return 1
  fi
  if [[ "$draft" == "true" ]]; then
    echo "WAIT: PR #$pr_number is still a draft"
    return 1
  fi
  if [[ "$head_oid" != "$remote_oid" ]]; then
    echo "WAIT: PR head $head_oid does not match origin/$HEAD_BRANCH $remote_oid"
    return 1
  fi
  if [[ "$review" != "APPROVED" ]]; then
    echo "WAIT: review decision is '$review'; required: APPROVED"
    return 1
  fi

  set +e
  checks_json=$(gh pr checks "$pr_number" --repo "$REPO" --required --json name,bucket 2>&1)
  checks_rc=$?
  set -e
  # gh pr checks exit 0 means all displayed required checks passed; exit 8 means pending.
  if [[ "$checks_rc" -ne 0 ]]; then
    if [[ "$checks_rc" -eq 8 ]]; then
      echo "WAIT: required checks are still pending"
    else
      echo "WAIT/FAIL: required checks are not passing: $checks_json" >&2
    fi
    return 1
  fi

  if [[ "$merge_state" != "CLEAN" ]]; then
    echo "WAIT: merge state is '$merge_state'; required: CLEAN"
    return 1
  fi

  echo "READY: PR #$pr_number ($pr_url) is approved, checks pass, head is current, and merge state is CLEAN"
  return 0
}

start_epoch=$(date +%s)
while true; do
  if check_pr; then
    break
  fi
  if [[ "$WAIT_SECONDS" == "0" ]]; then
    echo "No merge performed. Re-run with WAIT_SECONDS>0 to poll, or review the conditions above." >&2
    exit 5
  fi
  now_epoch=$(date +%s)
  elapsed=$((now_epoch - start_epoch))
  if (( elapsed >= WAIT_SECONDS )); then
    echo "ERROR: review/check wait timeout after ${elapsed}s" >&2
    exit 6
  fi
  sleep_for=$POLL_SECONDS
  remaining=$((WAIT_SECONDS - elapsed))
  (( sleep_for > remaining )) && sleep_for=$remaining
  echo "Polling again in ${sleep_for}s..."
  sleep "$sleep_for"
done

if [[ "$CHECK_ONLY" == "YES" || "$CONFIRM_MERGE" != "YES" ]]; then
  echo "CHECK ONLY: no merge was performed."
  echo "To merge this exact reviewed PR, rerun with CONFIRM_MERGE=YES."
  exit 0
fi

echo "Merging PR #$pr_number into '$BASE_BRANCH' with method '$MERGE_METHOD'..."
gh pr merge "$pr_number" --repo "$REPO" "--$MERGE_METHOD" --delete-branch=false

echo "Merge command completed. Verify the resulting main commit with:"
echo "  git fetch origin && git log -1 --oneline origin/$BASE_BRANCH"
