# Security policy

Thank you for helping keep Biodiversity Data Rescue Workbench and its users safer.

## Supported versions

Security fixes are focused on the latest public release and the current `main` branch. Older 0.x builds may not receive backported fixes.

## Report a vulnerability privately

Please **do not** post exploit details, credentials, private research data, precise sensitive locations, or other confidential material in a public issue.

Preferred reporting path:

1. Open the repository **Security** tab.
2. Use **Report a vulnerability** if GitHub private vulnerability reporting is available.
3. Include the affected version or commit, the security boundary involved, expected impact, and synthetic reproduction steps.
4. Use fictional or minimized data. Do not send a real confidential dataset just to demonstrate the issue.

If private vulnerability reporting is not available, open a minimal public issue asking for a private reporting channel. Do not include exploit details or sensitive attachments in that issue.

There is currently no dedicated security team or guaranteed response time. Reports will be handled as quickly as the maintainer can reasonably investigate them.

## Security boundaries worth reviewing

Useful reports may involve any real attacker-controlled path, including:

- local loopback session access and origin checks
- native IPC and Tauri capabilities
- imported files, archives, paths, filenames, spreadsheets, documents, and metadata
- extraction and parser behavior on malformed or hostile inputs
- immutable source preservation and integrity checks
- project revision checks, backup and restore behavior, and rollback boundaries
- export and support-package privacy boundaries
- executable and runtime selection
- accidental publication of secrets, private files, or machine-specific data
- dependency or build-chain compromise

A report does not need to fit one of these categories to be valid.

## Known limits

Working project storage is not encrypted. Anyone with access to the same operating-system account or project files may be able to read stored data.

Direct browser development mode has weaker same-machine isolation than the packaged desktop session.

Checksums detect changes relative to trusted checksum metadata. They do not authenticate the publisher of an unsigned binary by themselves.

Current public binaries are unsigned. Treat downloads as trusted only when obtained from the official repository release page and verify the published checksums when possible.

A saved project is not an independent backup. See [Data safety](docs/data-safety.md) for storage and sharing guidance.

## Public issue hygiene

For ordinary bugs, use fictional or minimized examples. Redact names, exact sensitive locations, contact information, access tokens, credentials, private file paths, and confidential dataset contents before posting screenshots or logs.

For implementation boundaries, see [Architecture](docs/architecture.md).
