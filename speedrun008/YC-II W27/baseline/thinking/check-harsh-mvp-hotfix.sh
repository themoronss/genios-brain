#!/usr/bin/env bash
# The production hotfix for Claude Sonnet 5's default thinking (STEP-18 M50.C5.L-integration.V0.U18,
# the 13 Oct audit's s5t-F3): proves `harsh-mvp-r2-thinking-off.diff` applies to `origin/harsh/mvp`
# and that harsh/mvp's own client tests pass with it — on an EXTRACT of the branch (`git archive`),
# never a checkout of it, and nothing is pushed.
#
#   bash 'speedrun008/YC-II W27/baseline/thinking/check-harsh-mvp-hotfix.sh'      # exit 0 = applies + green
#
# Harsh applies it on harsh/mvp with `git apply '<this folder>/harsh-mvp-r2-thinking-off.diff'`.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIFF="$HERE/harsh-mvp-r2-thinking-off.diff"
REPO="$(git -C "$HERE" rev-parse --show-toplevel)"
COMMON="$(cd "$REPO" && cd "$(git rev-parse --git-common-dir)/.." && pwd)"
PY="${PYTHON:-}"
for candidate in "$REPO/.venv/bin/python" "$COMMON/.venv/bin/python"; do
  [ -z "$PY" ] && [ -x "$candidate" ] && PY="$candidate"
done
[ -n "$PY" ] || { echo "no python: set PYTHON" >&2; exit 3; }
REF="${HARSH_MVP_REF:-origin/harsh/mvp}"
X="$(mktemp -d "${TMPDIR:-/tmp}/harsh-mvp-hotfix.XXXXXX")"
trap 'rm -rf "$X"' EXIT

echo "extract $REF @ $(git -C "$REPO" rev-parse --short "$REF") → $X"
git -C "$REPO" archive "$REF" | tar -x -C "$X"
cd "$X"
# No database: harsh/mvp's schema is not this checkout's, so its database tests skip.
TESTS="tests/context/test_sampling_is_omitted_where_it_is_refused.py tests/context/test_a_truncated_call_is_not_bad_json.py"

echo "before: harsh/mvp's own client tests"
env -u GENIOS_TEST_DATABASE_URL PYTHONDONTWRITEBYTECODE=1 "$PY" -m pytest -q -p no:cacheprovider $TESTS | tail -1

git apply --check "$DIFF"
git apply "$DIFF"
echo "applied: $(git apply --numstat "$DIFF" 2>/dev/null | wc -l | tr -d ' ') files — reverse-checks clean: $(git apply -R --check "$DIFF" && echo yes)"

echo "after: the same tests, with the hotfix's own"
env -u GENIOS_TEST_DATABASE_URL PYTHONDONTWRITEBYTECODE=1 "$PY" -m pytest -q -p no:cacheprovider $TESTS | tail -1
echo "after: harsh/mvp's tests/context and its R-site gate and narrator tests"
env -u GENIOS_TEST_DATABASE_URL PYTHONDONTWRITEBYTECODE=1 "$PY" -m pytest -q -p no:cacheprovider tests/context \
  tests/reason/test_bundle_gauntlet.py tests/reason/test_bundle_doctrine.py | tail -1
echo "OK: the hotfix applies to $REF and its tests pass"
