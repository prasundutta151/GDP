#!/bin/sh
set -eu

usage() {
  cat <<'USAGE'
Usage:
  ./push_to_git.sh "commit message"
  ./push_to_git.sh -m "commit message"
  sh push_to_git.sh "commit message"

What it does:
  - Runs from the GDP repository root.
  - Stages tracked edits and normal untracked repo files.
  - Force-adds the current version tar, gdp-$(cat VERSION).tar, if present.
  - Leaves ignored runtime/local files alone, such as rundir/.
  - Commits if there are staged changes.
  - Pushes the current branch to origin.
USAGE
}

message=""
if [ "$#" -eq 0 ]; then
  usage
  exit 2
fi

while [ "$#" -gt 0 ]; do
  case "$1" in
    -m|--message)
      shift
      if [ "$#" -eq 0 ]; then
        echo "Missing commit message after -m/--message" >&2
        exit 2
      fi
      message="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [ -n "$message" ]; then
        echo "Commit message was provided more than once" >&2
        exit 2
      fi
      message="$1"
      ;;
  esac
  shift
done

if [ -z "$(printf '%s' "$message" | tr -d '[:space:]')" ]; then
  echo "Commit message cannot be empty" >&2
  exit 2
fi

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$repo_root"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not inside a git repository: $repo_root" >&2
  exit 1
fi

branch="$(git branch --show-current)"
if [ -z "$branch" ]; then
  echo "Cannot push from detached HEAD" >&2
  exit 1
fi

echo "Repository: $repo_root"
echo "Branch:     $branch"
echo

echo "Status before staging:"
git status --short
echo

git add -u

git ls-files --others --exclude-standard | while IFS= read -r new_file; do
  [ -n "$new_file" ] || continue
  git add -- "$new_file"
done

version="$(tr -d '[:space:]' < VERSION)"
tar_file="gdp-${version}.tar"
if [ -f "$tar_file" ]; then
  git add -f "$tar_file"
else
  echo "Warning: $tar_file not found; no release tar staged" >&2
fi

echo "Staged changes:"
git diff --cached --stat || true
echo

if git diff --cached --quiet; then
  echo "No staged changes to commit."
else
  git commit -m "$message"
fi

git push origin "$branch"
echo "Pushed $branch to origin."
