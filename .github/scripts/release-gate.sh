#!/usr/bin/env bash
# 共同上線閘門：讀取 HUB_REPO 中標記 TRAIN_LABEL 的「上線協調」Issue，
# 只要相關 Issue 還有未打勾的模組，就讓這次發佈或這個 PR 的檢查失敗。
# 需要環境變數：GH_TOKEN、HUB_REPO、TRAIN_LABEL、THIS_REPO、EVENT_NAME；PR 事件另需 PR_TEXT。
set -euo pipefail

unchecked() { grep -E '^[[:space:]]*[-*][[:space:]]+\[ \]' || true; }

check_issue() { # $1 = issue number；印出未完成項目，全部完成時不印
  local json state body
  json=$(gh api "repos/$HUB_REPO/issues/$1")
  state=$(jq -r '.state' <<<"$json")
  if [[ "$state" != "open" ]]; then
    echo "協調 Issue #$1 已關閉，視為全部完成。" >&2
    return 0
  fi
  body=$(jq -r '.body // ""' <<<"$json" | tr -d '\r')
  unchecked <<<"$body"
}

blocked=0
if [[ "$EVENT_NAME" == "pull_request" ]]; then
  nums=$(grep -oiE 'release-train:?[[:space:]]*#[0-9]+' <<<"${PR_TEXT:-}" | grep -oE '[0-9]+' | sort -u || true)
  if [[ -z "$nums" ]]; then
    echo "這個 PR 沒有標註 Release-Train: #編號，不屬於共同上線，直接通過。"
    exit 0
  fi
  for n in $nums; do
    pending=$(check_issue "$n")
    if [[ -n "$pending" ]]; then
      echo "::error::協調 Issue $HUB_REPO#$n 還有模組未完成，這個 PR 先不要合併："
      echo "$pending"
      blocked=1
    else
      echo "協調 Issue #$n：所有模組都已完成。"
    fi
  done
else
  nums=$(gh api "repos/$HUB_REPO/issues?state=open&labels=$TRAIN_LABEL&per_page=100" \
    --jq '.[] | select(.pull_request == null) | .number')
  for n in $nums; do
    body=$(gh api "repos/$HUB_REPO/issues/$n" --jq '.body // ""' | tr -d '\r')
    grep -qiF "$THIS_REPO" <<<"$body" || continue
    pending=$(unchecked <<<"$body")
    if [[ -n "$pending" ]]; then
      echo "::error::$THIS_REPO 參與的協調 Issue $HUB_REPO#$n 還有模組未完成，現在不能上線："
      echo "$pending"
      blocked=1
    fi
  done
  [[ $blocked -eq 0 ]] && echo "沒有未完成的共同上線，可以發佈。"
fi
exit $blocked
