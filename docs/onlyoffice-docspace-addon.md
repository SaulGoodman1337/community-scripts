# ONLYOFFICE DocSpace add-on for an existing ONLYOFFICE Docs LXC

This installer adds **ONLYOFFICE DocSpace Community** to an existing native ONLYOFFICE Docs installation created with the Proxmox VE Community Scripts ONLYOFFICE LXC.

The existing Document Server is reused. DocSpace is installed with native DEB packages and listens on a separate port.

## Default layout

```text
ONLYOFFICE Docs:     http://LXC-IP:80
ONLYOFFICE DocSpace: http://LXC-IP:8088
```

For VyOS HAProxy, use two hostnames:

```text
office.example.internal -> LXC-IP:8088
docs.example.internal   -> LXC-IP:80
```

TLS can terminate on VyOS.

## Requirements

- Debian-based LXC
- amd64
- existing `onlyoffice-documentserver` package
- `/etc/onlyoffice/documentserver/local.json`
- root privileges
- TCP port 8088 free by default (DocSpace uses 8080 internally for identity authorization)

DocSpace is much heavier than ONLYOFFICE Docs alone. Current upstream guidance is roughly 4 CPU cores, 8 GB RAM, and 40 GB free disk space for a basic installation.

DocSpace uses OpenSearch. In an unprivileged Proxmox LXC, set this on the **Proxmox host**:

```bash
echo 'vm.max_map_count=262144' > /etc/sysctl.d/99-opensearch.conf
sysctl --system
```

The installer checks this before modifying the container.

## One-command install

Run this **inside the existing ONLYOFFICE LXC**:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/install/onlyoffice-docspace-addon.sh)"
```

Defaults:

- DocSpace port: `8088`
- existing ONLYOFFICE Docs is reused
- JWT secret/header are read locally from `local.json`
- no JWT secret is stored in GitHub
- upstream hardware checks stay enabled
- swap-file creation is disabled; configure swap in Proxmox instead
- Fluent Bit / OpenSearch Dashboards are disabled by default

## Install with the final Docs URL

```bash
DOCS_PUBLIC_URL="https://docs.example.internal" \
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/install/onlyoffice-docspace-addon.sh)"
```

Recommended final routing:

```text
https://office.example.internal -> LXC-IP:8088
https://docs.example.internal   -> LXC-IP:80
```

Use HTTPS for both hostnames to avoid mixed-content problems.

## Options

Different DocSpace port:

```bash
DOCSPACE_PORT=8180 bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/install/onlyoffice-docspace-addon.sh)"
```

Skip upstream hardware checks (not recommended):

```bash
DOCSPACE_SKIP_HARDWARE_CHECK=true bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/install/onlyoffice-docspace-addon.sh)"
```

Enable Fluent Bit / OpenSearch Dashboards:

```bash
DOCSPACE_INSTALL_FLUENTBIT=true bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/install/onlyoffice-docspace-addon.sh)"
```

## Safety behavior

Before installation, the script verifies the existing Docs package, checks the port and `vm.max_map_count`, reads JWT configuration, creates a backup under `/root/onlyoffice-docspace-preinstall-*`, and logs to `/var/log/onlyoffice-docspace-addon.log`.

The installer intentionally refuses to run when DocSpace is already installed.

## After installation

Open:

```text
http://LXC-IP:8088/
```

and finish the DocSpace setup wizard. Once HAProxy is active, ensure DocSpace uses the HTTPS Document Service address, for example `https://docs.example.internal/`.

## Local accounts and email activation

DocSpace expects normal local accounts, including the initial owner, to confirm their
email address. Current upstream documentation exposes **Disable email verification**
for SSO and LDAP users, but not as a documented global switch for ordinary local
accounts.

For a trusted internal/home-lab installation without SMTP, use the helper below to
mark a specific local account as activated after creating it in the wizard:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/tools/docspace-activate-user.sh)" -- user@example.com
```

The helper only changes the matching user's `activation_status` from its current
value to `1` (Activated) in DocSpace's MySQL database. It prints the row before and
after the update and refuses to continue if the email is ambiguous or missing.


## Automatic activation for local users

For a trusted internal/home-lab installation, email verification for normal local
accounts can be bypassed automatically.

Install the automation once on an existing DocSpace installation:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/tools/docspace-auto-activate-users.sh)" -- install
```

Behavior:

- active local users with a non-empty email address are automatically changed from
  activation status `NotActivated (0)` or `Pending (2)` to `Activated (1)`
- LDAP users (`sid` set) are excluded
- SSO users (`sso_name_id` set) are excluded
- removed users are excluded
- `AutoGenerated (4)` accounts are excluded
- invitation accounts with `EmployeeStatus.Pending` remain in their registration/password
  flow and are not force-activated prematurely
- when such an invitation later becomes an active local account, the UPDATE trigger
  automatically removes the email-verification requirement
- already active local accounts waiting for email verification are activated once when
  the automation is installed

Check status:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/tools/docspace-auto-activate-users.sh)" -- status
```

Remove the automation:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/tools/docspace-auto-activate-users.sh)" -- remove
```

Removing the triggers does not revert users that were already activated.

For a fresh one-command DocSpace installation, enable this behavior directly:

```bash
DOCSPACE_AUTO_ACTIVATE_USERS=true \
DOCSPACE_SKIP_HARDWARE_CHECK=true \
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/install/onlyoffice-docspace-addon.sh)"
```

This automation deliberately bypasses an identity-verification control. Use it only on
a trusted internal deployment where accounts are created by an administrator.
