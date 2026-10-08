# Biodiversity Data Rescue Workbench

A local-first Windows workbench for preserving, investigating, repairing, validating and packaging messy biodiversity and scientific datasets.

Bio is for researchers, collection managers and data stewards working with legacy files, incomplete documentation and uncertain meanings. It preserves original bytes, keeps interpretations separate from observations, and makes reviewed changes traceable. Structural validation does not certify scientific truth.

## Current status

The current source is **0.7.0-dev.0**, preparing for the first public 0.7.0 release. A public release is not available until repository, privacy, licensing, clean-build, packaging and native acceptance checks pass. Builds are unsigned.

## Capabilities

- Preserve original files and inspect extraction before committing working tables.
- Review data quality, evidence, uncertainty, transformations and provenance.
- Work with delimited tables, spreadsheet and document evidence, relational sources and bounded large-data investigations.
- Prepare standards-oriented exports and preservation packages with explicit limitations.
- Use guided tutorials, a searchable Help Center and the offline Bio Buddy field guide.
- Open verified native builds through the launcher and retain previous local builds for rollback.

Some advanced scientific workflows use the retained interface. Reader, schema and export limitations remain visible; inferred meanings require human review.

## Install and start

When a release is available, download the Windows x64 installer or portable archive from [Releases](https://github.com/amgedi/Biodiversity-Data-Rescue-Workbench/releases). Verify its SHA-256 checksum. Extract the entire portable archive before opening **Launch Workbench.exe**. Keep its folders together. Windows WebView2 is required; packaged use does not require Python or Node.

Open the launcher, choose **Open Workbench**, then **Add sources**. Select files, inspect extraction, and preserve the source. Record unresolved meaning as Unknown instead of guessing. Explore Help and Learn & practice with fictional data before using research material.

## Privacy and data safety

Research stays on the local machine. Bio Buddy uses curated local resources, without a remote model or telemetry. Manually checking for updates contacts GitHub and does not send project content. Network failure must be reported as an inability to check, not as Up to date.

Desktop projects normally live under `%LOCALAPPDATA%\Biodiversity Data Rescue Workbench\projects-data`. Saved projects are not independent backups. Working storage is not encrypted. Preservation packages and support details can contain original files, precise locations, contacts and private history; review them before sharing. See [data safety](docs/data-safety.md).

## Development

See [build and test instructions](docs/build.md), [architecture](docs/architecture.md), and [contributing](CONTRIBUTING.md). The canonical source includes Python, Rust/Tauri and browser presentation code. Local runtime binaries and build history are deliberately excluded from Git.

## Feedback and security

Use [Issues](https://github.com/amgedi/Biodiversity-Data-Rescue-Workbench/issues) for bugs and scientific interpretation concerns. Reproduce with fictional or minimized data. **Do not attach confidential datasets, credentials, support bundles or unredacted paths to public issues.** See [SECURITY.md](SECURITY.md) for vulnerability reporting.

## License

Original project code is licensed under **GNU Affero General Public License version 3 only (AGPL-3.0-only)**. See [LICENSE](LICENSE). Third-party code, schemas and fixture-derived material retain their own licenses and notices; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
