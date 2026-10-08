# Build and test

Use a Windows x64 development machine with Python 3.14, Node.js, Rust/Cargo, Microsoft C++ build tools and Windows WebView2. The Tauri CLI is pinned through `package-lock.json`. These tools are needed to build; packaged users do not need Python or Node.

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt
npm ci
npm test
python -m unittest discover -s tests
cargo test --manifest-path app/desktop/src-tauri/Cargo.toml
cargo test --manifest-path app/launcher/src-tauri/Cargo.toml --bins
python scripts/build/workbench.py build
```

First-time Cargo dependency resolution may require network access. Subsequent cached builds can work offline. Do not assume a pre-existing private runtime folder or compiler cache exists in a fresh clone.

The verified build creates local root entry points and an immutable version slot. Open `Launch Workbench.exe`. Source and frozen-engine fingerprints must agree. Build outputs and local versions are ignored by Git.

For an isolated browser preview:

```powershell
python server.py --port 8766 --data-dir .local-preview
```

Open `http://127.0.0.1:8766/`. Stop the process when finished. Use synthetic data; this mode is for local development. See [release process](release-process.md) for candidate packaging and acceptance.
