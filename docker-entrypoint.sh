#!/bin/sh
set -eu

DATA_DIR="${DISCORDCODEX_DATA_DIR:-/data}"
GIT_CREDENTIALS_FILE="${GIT_CREDENTIALS_FILE:-$DATA_DIR/git-credentials}"
GIT_CONFIG_FILE="${GIT_CONFIG_GLOBAL:-$DATA_DIR/gitconfig}"
CODEX_CONFIG_FILE="${DISCORDCODEX_CODEX_CONFIG:-$DATA_DIR/codex-home/shared/config.toml}"
LATEST_MODEL_URL="${DISCORDCODEX_LATEST_MODEL_URL:-https://developers.openai.com/api/docs/guides/latest-model.md}"

read_secret_file() {
    if [ ! -f "$1" ]; then
        printf 'Secret file not found: %s\n' "$1" >&2
        exit 1
    fi
    IFS= read -r value < "$1" || true
    printf '%s' "$value"
}

resolve_latest_codex_model() {
    curl -fsSL "$LATEST_MODEL_URL" 2>/dev/null \
        | sed -n 's/^[[:space:]]*model:[[:space:]]*\([^[:space:]]*\)[[:space:]]*$/\1/p' \
        | head -n 1
}

set_codex_model() {
    model="$1"
    config_file="$2"
    mkdir -p "$(dirname "$config_file")"
    if [ -f "$config_file" ] && grep -q '^[[:space:]]*model[[:space:]]*=' "$config_file"; then
        sed "s/^[[:space:]]*model[[:space:]]*=.*/model = \"$model\"/" "$config_file" > "$config_file.tmp"
        mv "$config_file.tmp" "$config_file"
    elif [ -f "$config_file" ]; then
        tmp_file="$config_file.tmp"
        {
            printf 'model = "%s"\n' "$model"
            cat "$config_file"
        } > "$tmp_file"
        mv "$tmp_file" "$config_file"
    else
        printf 'model = "%s"\n' "$model" > "$config_file"
    fi
}

configure_codex_model() {
    requested_model="${DISCORDCODEX_CODEX_MODEL:-}"
    if [ -z "$requested_model" ]; then
        return
    fi
    if [ "$requested_model" = "latest" ]; then
        resolved_model="$(resolve_latest_codex_model || true)"
        if [ -z "$resolved_model" ]; then
            printf 'Could not resolve latest Codex model; leaving %s unchanged.\n' "$CODEX_CONFIG_FILE" >&2
            return
        fi
        set_codex_model "$resolved_model" "$CODEX_CONFIG_FILE"
        printf 'Updated Codex model to %s in %s.\n' "$resolved_model" "$CODEX_CONFIG_FILE" >&2
        return
    fi
    set_codex_model "$requested_model" "$CODEX_CONFIG_FILE"
    printf 'Updated Codex model to %s in %s.\n' "$requested_model" "$CODEX_CONFIG_FILE" >&2
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

configure_codex_model

exec "$@"
