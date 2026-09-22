# Private repository access

This repository is intended to be private. Installation and update helpers authenticate with a GitHub fine-grained personal access token (PAT).

Create a fine-grained PAT with access to **SaulGoodman1337/community-scripts** and repository permission **Contents: Read-only**. No write or administration permission is required for installs.

Define this helper once in the shell where you want to run an installer:

```bash
csrun() {
  local target="${1:?repo-relative script path}"
  shift || true

  local token bootstrap
  printf 'GitHub token: ' >/dev/tty
  read -rs token </dev/tty
  printf '\n' >/dev/tty

  bootstrap="$(
    curl -fsSL \
      -H "Authorization: Bearer $token" \
      -H "Accept: application/vnd.github.raw+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "https://api.github.com/repos/SaulGoodman1337/community-scripts/contents/tools/private-run.sh?ref=main"
  )"

  COMMUNITY_SCRIPTS_GITHUB_TOKEN="$token" \
    bash -c "$bootstrap" -- "$target" "$@"

  unset token bootstrap
}
```

Then run any repository script by path, for example:

```bash
csrun ct/mindwtr.sh
```

The bootstrap downloads a temporary authenticated archive of the repository, sets `COMMUNITY_SCRIPTS_ROOT` to that checkout, executes the requested script, and removes the checkout afterwards. The token is not committed to the repository and is not stored permanently by the bootstrap.

LXC installations created with this flow install a private-aware `/usr/bin/update`. By default, `update` asks for the token when no saved token is available.

To store the read-only token persistently on the LXC, run:

```bash
update --save-token
```

The token is stored in `/etc/community-scripts-github-token` with mode `0600` and is used automatically by later updates. Remove it with:

```bash
update --forget-token
```

The token file is local to the LXC and is never committed to the repository.

For existing containers created before the repository became private, run their normal `update` command once while the repository is still public. That migrates `/usr/bin/update` to the private-aware wrapper before changing repository visibility.
