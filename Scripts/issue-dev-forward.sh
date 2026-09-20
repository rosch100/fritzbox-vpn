#!/usr/bin/env bash
# GitHub Actions → Issue-Dev Grok-Wake (Bearer + Envelope).
# Copy to `Scripts/issue-dev-forward.sh` in each githubRepos consumer.
# Secrets niemals loggen. Kein set -x.
set -euo pipefail
set +x

EVENT_NAME="${GITHUB_EVENT_NAME:-}"
EVENT_PATH="${GITHUB_EVENT_PATH:-}"
if [[ -z "$EVENT_NAME" || -z "$EVENT_PATH" || ! -f "$EVENT_PATH" ]]; then
  echo "GITHUB_EVENT_NAME/PATH fehlt" >&2
  exit 1
fi

python3 - "$EVENT_NAME" "$EVENT_PATH" <<'PY'
import hashlib, hmac, json, os, pathlib, sys, urllib.error, urllib.request

def is_issue_dev_wake_label(label_name):
    if not isinstance(label_name, str) or not label_name:
        return False
    if label_name in ("kind/error", "kind/feature", "kind/feedback"):
        return True
    return label_name.startswith("issue-dev/")

event_name, event_path = sys.argv[1], sys.argv[2]
payload = pathlib.Path(event_path).read_text(encoding="utf-8")
secret = os.environ.get("ISSUE_DEV_WEBHOOK_SECRET", "").strip()
sig = os.environ.get("ISSUE_DEV_RECEIVED_SIGNATURE", "").strip()
if secret:
    if not sig.startswith("sha256="):
        print("missing signature", file=sys.stderr)
        sys.exit(1)
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig[7:], digest):
        print("bad signature", file=sys.stderr)
        sys.exit(1)

data = json.loads(payload)
repo = data.get("repository") or {}
full = repo.get("full_name")
if not isinstance(full, str) or "/" not in full:
    print("repository.full_name fehlt", file=sys.stderr)
    sys.exit(1)
owner, name = full.split("/", 1)
issue = data.get("issue") or {}
pull = data.get("pull_request") or {}
comment = data.get("comment") or {}
labels = []
for lab in (issue.get("labels") or pull.get("labels") or []):
    if isinstance(lab, dict) and lab.get("name"):
        labels.append(lab["name"])
kind = "manual_wake"
action = data.get("action")
if event_name == "issues":
    if action in ("labeled", "unlabeled"):
        triggering = (data.get("label") or {}).get("name")
        if not is_issue_dev_wake_label(triggering):
            print(json.dumps({"skipped": True, "reason": "unrelated-label"}))
            sys.exit(0)
        kind = "issue_labeled"
    else:
        kind = "issue_opened"
elif event_name == "issue_comment":
    kind = "issue_comment"
elif event_name == "pull_request":
    kind = "pull_request"
elif event_name == "workflow_run":
    kind = "ci_completed"
elif event_name == "repository_dispatch":
    kind = "manual_wake"

run_id = os.environ.get("GITHUB_RUN_ID", "")
attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
if not run_id:
    print("GITHUB_RUN_ID fehlt", file=sys.stderr)
    sys.exit(1)
if not attempt:
    print("GITHUB_RUN_ATTEMPT fehlt", file=sys.stderr)
    sys.exit(1)
pr_number = pull.get("number")
if pr_number is None and isinstance(issue.get("pull_request"), dict):
    pr_number = issue.get("number")

delivery_id = f"github/{owner}/{name}/{kind}/{run_id}-{attempt}"
envelope = {
    "deliveryId": delivery_id,
    "host": "github",
    "owner": owner,
    "repo": name,
    "kind": kind,
    "issueNumber": issue.get("number"),
    "prNumber": pr_number,
    "commentBody": comment.get("body"),
    "labels": labels,
    "skillHint": (
        "bugfix" if "kind/error" in labels else
        "feature-dev" if "kind/feature" in labels else None
    ),
    "htmlUrl": issue.get("html_url") or pull.get("html_url"),
}

url = os.environ.get("ISSUE_DEV_GROK_WEBHOOK_URL", "").strip()
key = os.environ.get("ISSUE_DEV_GROK_WEBHOOK_KEY", "").strip()
if key.lower().startswith("bearer "):
    key = key[7:].strip()
if not url:
    print("ISSUE_DEV_GROK_WEBHOOK_URL fehlt", file=sys.stderr)
    sys.exit(1)
if not key:
    print("ISSUE_DEV_GROK_WEBHOOK_KEY fehlt", file=sys.stderr)
    sys.exit(1)

body = json.dumps({
    "deliveryId": delivery_id,
    "envelope": envelope,
    "path": "",
}).encode()
req = urllib.request.Request(
    url,
    data=body,
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    },
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()
except urllib.error.HTTPError as exc:
    print(f"grok wake HTTP {exc.code}", file=sys.stderr)
    sys.exit(1)
except Exception as exc:
    print(f"grok wake failed: {type(exc).__name__}", file=sys.stderr)
    sys.exit(1)

print(json.dumps({"skipped": False, "deliveryId": delivery_id, "wokeGrok": True}))
PY
