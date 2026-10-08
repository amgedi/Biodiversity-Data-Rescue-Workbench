# Architecture

Bio has three main layers: a Python scientific engine, browser presentation code, and Windows Rust/Tauri desktop and launcher applications. The engine owns ingestion, source preservation, project storage, reviewed transformation and export. Presentation code does not become a new scientific authority.

The desktop starts a bundled engine on an ephemeral loopback port. Configuration and readiness travel through anonymous pipes. A fresh session token protects desktop requests; bootstrap creates a local cookie. Host and Origin validation constrain browser requests. Native IPC is limited to declared windows and commands. Direct browser development mode binds to loopback and checks Host/Origin but has no desktop session token.

PDF, legacy Excel and Word readers use bounded workers and pinned vendored resources. Original bytes remain distinct from extracted working data. Import bounds and unsupported content must remain visible rather than being silently repaired.

The launcher reads an explicit `versions/CURRENT.json`, verifies the selected runtime identity and executable hash, and observes an engine identity handshake. Previous builds remain local for rollback. User projects are stored separately from binaries. Integrity checks use local metadata and are not code signing.

Source builds generate frontend assets, run regressions, freeze the engine and compile native applications. Distribution packaging must include the launcher, its explicit runtime selection, complete engine resources, licenses and checksums. It must not copy local data or private diagnostic/history trees.
