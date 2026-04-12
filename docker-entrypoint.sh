#!/bin/sh
set -eu

DATA_DIR="${DISCORDCODEX_DATA_DIR:-/data}"
GIT_CREDENTIALS_FILE="${GIT_CREDENTIALS_FILE:-$DATA_DIR/git-credentials}"
GIT_CONFIG_FILE="${GIT_CONFIG_GLOBAL:-$DATA_DIR/gitconfig}"

if [ -n "${GITHUB_TOKEN:-}" ]; then
    GITHUB_USERNAME="${GITHUB_USERNAME:-x-access-token}"
    mkdir -p "$(dirname "$GIT_CREDENTIALS_FILE")" "$(dirname "$GIT_CONFIG_FILE")"
    umask 077
    printf 'https://%s:%s@github.com\n' "$GITHUB_USERNAME" "$GITHUB_TOKEN" > "$GIT_CREDENTIALS_FILE"
    cat > "$GIT_CONFIG_FILE" <<EOF
[credential]
	helper = store --file $GIT_CREDENTIALS_FILE
EOF
    export GIT_CONFIG_GLOBAL="$GIT_CONFIG_FILE"
fi

exec "$@"
