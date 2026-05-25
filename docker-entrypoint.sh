#!/bin/sh
set -eu

DATA_DIR="${DISCORDCODEX_DATA_DIR:-/data}"
GIT_CREDENTIALS_FILE="${GIT_CREDENTIALS_FILE:-$DATA_DIR/git-credentials}"
GIT_CONFIG_FILE="${GIT_CONFIG_GLOBAL:-$DATA_DIR/gitconfig}"

read_secret_file() {
    if [ ! -f "$1" ]; then
        printf 'Secret file not found: %s\n' "$1" >&2
        exit 1
    fi
    IFS= read -r value < "$1" || true
    printf '%s' "$value"
}

GITHUB_TOKEN_VALUE="${DISCORDCODEX_GITHUB_TOKEN:-}"
if [ -z "$GITHUB_TOKEN_VALUE" ] && [ -n "${DISCORDCODEX_GITHUB_TOKEN_FILE:-}" ]; then
    GITHUB_TOKEN_VALUE="$(read_secret_file "$DISCORDCODEX_GITHUB_TOKEN_FILE")"
fi

GIT_TOKEN="${GITHUB_TOKEN_VALUE:-${DISCORDCODEX_GIT_CREDENTIAL_TOKEN:-${GITHUB_TOKEN:-}}}"
if [ -z "$GIT_TOKEN" ] && [ -n "${DISCORDCODEX_GIT_CREDENTIAL_TOKEN_FILE:-}" ]; then
    GIT_TOKEN="$(read_secret_file "$DISCORDCODEX_GIT_CREDENTIAL_TOKEN_FILE")"
fi

if [ -n "$GIT_TOKEN" ]; then
    GITHUB_USERNAME="${DISCORDCODEX_GIT_USERNAME:-${GITHUB_USERNAME:-x-access-token}}"
    mkdir -p "$(dirname "$GIT_CREDENTIALS_FILE")" "$(dirname "$GIT_CONFIG_FILE")"
    umask 077
    printf 'https://%s:%s@github.com\n' "$GITHUB_USERNAME" "$GIT_TOKEN" > "$GIT_CREDENTIALS_FILE"
    cat > "$GIT_CONFIG_FILE" <<EOF
[credential]
	helper = store --file $GIT_CREDENTIALS_FILE
EOF
    export GIT_CONFIG_GLOBAL="$GIT_CONFIG_FILE"
    unset DISCORDCODEX_GITHUB_TOKEN
    unset DISCORDCODEX_GITHUB_TOKEN_FILE
    unset DISCORDCODEX_GIT_CREDENTIAL_TOKEN
    unset DISCORDCODEX_GIT_CREDENTIAL_TOKEN_FILE
    unset GITHUB_TOKEN
fi

API_TOKEN="${GITHUB_TOKEN_VALUE:-${DISCORDCODEX_GITHUB_API_TOKEN:-}}"
if [ -z "$API_TOKEN" ] && [ -n "${DISCORDCODEX_GITHUB_API_TOKEN_FILE:-}" ]; then
    API_TOKEN="$(read_secret_file "$DISCORDCODEX_GITHUB_API_TOKEN_FILE")"
fi

if [ -n "$API_TOKEN" ] && [ -z "${GH_TOKEN:-}" ]; then
    export GH_TOKEN="$API_TOKEN"
fi
unset DISCORDCODEX_GITHUB_TOKEN
unset DISCORDCODEX_GITHUB_TOKEN_FILE
unset DISCORDCODEX_GITHUB_API_TOKEN
unset DISCORDCODEX_GITHUB_API_TOKEN_FILE

exec "$@"
