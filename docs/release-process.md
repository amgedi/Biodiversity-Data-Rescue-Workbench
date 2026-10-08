# Release process

Keep the repository private until source, history, privacy, license, dependency and native acceptance reviews are complete. Preserve full project and source/Git backups before sanitation or history changes. Never publish local research, runtime history, diagnostic captures or credentials.

Build and test from a new local clone using only tracked source and documented dependencies. Package useful Windows installer and portable assets, verify complete launcher/runtime resources, generate SHA-256 checksums and read archives back. Exercise launcher/version handshake, import, Help, search, tutorials, window controls and rollback with fictional data.

Only after acceptance passes, align application, launcher, installer and release metadata to the target version. Tag the exact release commit, publish assets and checksums, then make visibility public as the final step. Download the uploaded assets and repeat checksum/launch smoke tests. Preserve a private source snapshot of the exact shipped commit.

Update detection must use the configured official GitHub release source. A successful current-version comparison may say Up to date; network, feed or metadata failure must say Unable to check. Automatic installation is not implied by a check button; when unavailable, direct users to verified release downloads.

Unsigned packages and format/scientific limits must be disclosed. Passing test counts alone do not establish release readiness.
