# Security Policy

## Supported version

Security fixes are applied to the latest commit on this fork's `main` branch. Older commits and
upstream releases are not separately supported here.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting for this repository when it is available. Include:

- the affected commit and component;
- reproduction steps or a minimal proof of concept;
- the expected impact;
- whether SolidWorks, the execution server, or an MCP client must already be running; and
- any suggested mitigation.

Do not publish exploit details, credentials, proprietary CAD data, or customer file paths in a
public issue. If private vulnerability reporting is unavailable, open a public issue containing no
sensitive details and ask the maintainer for a private contact channel.

You should receive an acknowledgment within seven days. Disclosure timing will be coordinated
after the issue is reproduced and a fix or mitigation is available.

## Deployment guidance

SolidPilot gives an MCP client the ability to create, open, modify, export, and capture local CAD
documents through SolidWorks. Treat the MCP client and all prompts or retrieved content as code
with access to those files.

- Keep `EXECUTION_BASE_URL` bound to loopback. The local execution HTTP service has no remote-user
  authentication and must not be exposed to a LAN or the internet.
- Run SolidPilot as a non-administrator and restrict access to sensitive CAD directories.
- Use versioned backups or source control before allowing automated edits to production models.
- Review paths supplied to open, save, export, analysis, and capture tools.
- Never place secrets in `.env`, prompts, tool logs, screenshots, or sample CAD files. This project
  does not require API keys for its local SolidWorks connection.
- Review dependency-lock updates and CI results before merging them.

## Scope

Reports about this fork's Python adapter, C# execution service, compiler, contracts, or unsafe file
handling are in scope. Vulnerabilities in SolidWorks itself, an MCP host, Windows, or an upstream
dependency should also be reported to the relevant vendor or upstream maintainer.
