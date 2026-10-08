# Security

Do not disclose exploit details, credentials or private research in a public issue. If GitHub's **Report a vulnerability** action is available under the repository Security tab, use it for a private report. Otherwise open a minimal issue requesting a private reporting channel, without exploit details or sensitive attachments, and wait for a maintainer response.

The current development branch receives security fixes. There is no institutional security certification or guaranteed response time.

Important boundaries include loopback-session access, native IPC capabilities, passive bounded import, archive/path handling, immutable originals, revision checks and executable selection. Working storage is not encrypted. Direct browser development mode has weaker same-machine isolation than the desktop session. Checksums detect changes relative to trusted metadata; they do not authenticate the publisher of unsigned binaries.

See [data safety](docs/data-safety.md) for user responsibilities and [architecture](docs/architecture.md) for implementation boundaries.
