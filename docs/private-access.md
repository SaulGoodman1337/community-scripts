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
csrun ct/optolink-splitter.sh
```

The bootstrap downloads a temporary authenticated archive of the repository, sets `COMMUNITY_SCRIPTS_ROOT` to that checkout, executes the requested script, and removes the checkout afterwards. The token is not committed to the repository and is not stored permanently by the bootstrap.

LXC installations created with this flow install a private-aware `/usr/bin/update`. Running `update` asks for the token again and does not store it on disk.

For existing containers created before the repository became private, run their normal `update` command once while the repository is still public. That migrates `/usr/bin/update` to the private-aware wrapper before changing repository visibility.
