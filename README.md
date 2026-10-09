<div align="center">

<img src="web/branding/biodiversity-full-logo.png" width="240" alt="Biodiversity Data Rescue Workbench logo" />

# Biodiversity Data Rescue Workbench

**Give messy biodiversity data a careful second life.**

Bio is a local-first Windows workbench for preserving original files, investigating messy or uncertain data, reviewing repairs, and keeping a clear record of what changed and what is still unknown.

[![Download Latest](https://img.shields.io/badge/Download-Latest_Release-355E49?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/amgedi/Biodiversity-Data-Rescue-Workbench/releases/latest)
[![Read the Docs](https://img.shields.io/badge/Docs-Start_Here-58704F?style=for-the-badge&logo=readthedocs&logoColor=white)](docs/README.md)
[![Report a Bug](https://img.shields.io/badge/Report-Bug-876B52?style=for-the-badge&logo=github&logoColor=white)](https://github.com/amgedi/Biodiversity-Data-Rescue-Workbench/issues/new?template=bug.md)
[![Request a Feature](https://img.shields.io/badge/Request-Feature-6F875F?style=for-the-badge&logo=github&logoColor=white)](https://github.com/amgedi/Biodiversity-Data-Rescue-Workbench/issues/new?template=feature.md)

<br/>

[![Release](https://img.shields.io/github/v/release/amgedi/Biodiversity-Data-Rescue-Workbench?style=flat-square&color=6F875F)](https://github.com/amgedi/Biodiversity-Data-Rescue-Workbench/releases/latest)
[![CI](https://img.shields.io/github/actions/workflow/status/amgedi/Biodiversity-Data-Rescue-Workbench/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/amgedi/Biodiversity-Data-Rescue-Workbench/actions/workflows/ci.yml)
[![CodeQL](https://img.shields.io/github/actions/workflow/status/amgedi/Biodiversity-Data-Rescue-Workbench/codeql.yml?branch=main&style=flat-square&label=CodeQL)](https://github.com/amgedi/Biodiversity-Data-Rescue-Workbench/actions/workflows/codeql.yml)
[![License](https://img.shields.io/badge/License-AGPL--3.0--only-A18463?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/Windows-x64-507B68?style=flat-square&logo=windows&logoColor=white)](https://github.com/amgedi/Biodiversity-Data-Rescue-Workbench/releases/latest)

[**Getting started**](#getting-started) · [**Screenshots**](#screenshots) · [**Data safety**](docs/data-safety.md) · [**Contributing**](CONTRIBUTING.md) · [**Security**](SECURITY.md) · [**Changelog**](CHANGELOG.md)

</div>

## What is Bio?

I built Bio around a pretty simple idea: **messy data is not the same thing as bad data**.

Old biodiversity datasets can come with weird spreadsheets, undocumented codes, missing field notes, broken exports, conflicting values, and files from software nobody uses anymore. The dangerous part is trying to make all of that look clean by quietly guessing what it meant.

Bio gives you a place to preserve the source, inspect what is actually there, record what you know, keep uncertainty visible, and make repairs that another person can review later.

> **Preserve the evidence. Investigate the mess. Rescue the data.**

## What Bio can do

| Your task | What Bio helps with |
| --- | --- |
| **Preserve** | Keep original source bytes separate from working data and inspect extraction before accepting it. |
| **Investigate** | Explore literal values, evidence, relationships, missingness, conflicts, and unresolved questions. |
| **Repair** | Preview changes before applying them and keep reviewable history where the workflow supports it. |
| **Validate** | Run local structural checks and standards-oriented validation without pretending that structure proves scientific truth. |
| **Package** | Prepare reviewed exports and preservation packages with provenance and supporting evidence. |
| **Learn** | Use guided lessons, the searchable Help Center, and Bio Buddy for local workflow guidance. |

Some advanced workflows still use the retained interface. Validation can check structure and documented constraints, but it cannot certify that a scientific interpretation is correct.

## The rules I do not want Bio to forget

```text
preserve originals
unknown != no
missing != zero
inferred != observed
repairs should be reviewable
provenance should travel with the data
```

Those rules are the reason Bio keeps originals, working values, evidence, uncertainty, and repair history separate instead of trying to flatten everything into one "clean" table.

## Screenshots

All screenshots use fictional practice data.

<table>
<tr>
<td width="50%" valign="top"><img src="docs/images/workbench-home.jpg" alt="Biodiversity Data Rescue Workbench home screen with fictional practice projects" /></td>
<td width="50%" valign="top"><img src="docs/images/help-center.jpg" alt="Biodiversity Data Rescue Workbench searchable Help Center" /></td>
</tr>
<tr>
<td align="center"><b>Workbench home</b><br/><sub>Start, resume, and inspect local rescue projects.</sub></td>
<td align="center"><b>Help Center</b><br/><sub>Searchable guidance when you are not sure what a field or workflow means.</sub></td>
</tr>
<tr>
<td colspan="2" align="center"><img src="docs/images/launcher.jpg" width="72%" alt="Biodiversity Data Rescue Workbench native launcher preview" /></td>
</tr>
<tr>
<td colspan="2" align="center"><b>Native launcher</b><br/><sub>Open the workbench and keep the packaged runtime together.</sub></td>
</tr>
</table>

These are browser-rendered V7 previews. Final live Windows visual acceptance is still pending. The launcher preview uses fictional installation status.

## Getting started

<div align="center">

[![Latest Release](https://img.shields.io/badge/Open-Latest_Release-355E49?style=for-the-badge&logo=github&logoColor=white)](https://github.com/amgedi/Biodiversity-Data-Rescue-Workbench/releases/latest)
[![Portable ZIP](https://img.shields.io/badge/Download-v0.7.0_Portable-58704F?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/amgedi/Biodiversity-Data-Rescue-Workbench/releases/download/v0.7.0/Biodiversity-Data-Rescue-Workbench-0.7.0-Portable.zip)
[![Checksums](https://img.shields.io/badge/Verify-SHA--256-A18463?style=for-the-badge&logo=shieldsdotio&logoColor=white)](https://github.com/amgedi/Biodiversity-Data-Rescue-Workbench/releases/download/v0.7.0/SHA256SUMS.txt)

</div>

The first public release is portable. There is no installer yet.

1. Download the complete portable ZIP and the SHA-256 checksum file.
2. Verify the download, then extract the full archive into a writable folder.
3. Open **Launch Workbench.exe**, then choose **Open Workbench**.
4. Start with **Learn & practice** and a fictional project.
5. Add sources, inspect the extraction, and preserve the source before making repairs.

Want to build it yourself instead? See [build and test](docs/build.md).

## A typical rescue

**Preserve → Inspect → Repair → Validate → Export**

Keep the source and its context. Look at the literal values before deciding what they mean. Preview repairs before applying them. Record why an interpretation was made. Validate what can actually be validated, then export enough evidence for the next person to understand the decisions.

## Major capabilities

### Sources and evidence

Delimited tables, spreadsheet and document evidence, original-file integrity checks, and retained supporting material. Reader fidelity varies, so originals still matter.

### Review and repair

Working tables, relationship-aware investigation, explicit uncertainty, reviewed transformations, undo and recovery where supported, and project history that does not quietly erase earlier states.

### Validation and packaging

Local checks, standards-oriented mapping and export tools, preservation packages, and bounded large-data investigations. Bio does not make an unlimited-size claim and does not treat structural validation as scientific validation.

### Help and learning

Guided tutorials, a searchable Help Center, and **Bio Buddy**, a local learning and workflow assistant based on curated guidance. Bio Buddy does not automatically interpret scientific evidence for you.

## Privacy and data safety

Bio does not silently upload projects. Optional external analysis providers in retained tools require explicit consent, and you should review the provider and payload before sending anything. Bio Buddy works locally.

Manual update checks contact GitHub. Opening a support page contacts that external service. Neither action sends project content.

Working project storage is **not encrypted**. Projects normally live under `%LOCALAPPDATA%\Biodiversity Data Rescue Workbench\projects-data`. Packages and support details may contain original files, exact locations, contact information, and project history, so review them before sharing.

A saved project is not an independent backup. Read [Data safety](docs/data-safety.md) before using Bio with anything important.

## Project status

Current release: **0.7.0**.

Bio is early 0.x research software and I am still actively testing it against real-world messiness. Windows x64 and WebView2 are required. Current binaries are unsigned. Packaged use does not require Python or Node, while source builds use the documented development toolchain.

The portable distribution includes the launcher and selected runtime, so keep its folders together. Manual native visual acceptance was deferred by the maintainer. Automated checks, native unit tests, and headless browser checks passed for the release.

For the implementation details, see [Architecture](docs/architecture.md). For development setup, see [Build instructions](docs/build.md).

## Contributing and feedback

Bug reports, accessibility feedback, documentation improvements, scientific concerns, and carefully scoped fixes are welcome. Please use fictional or minimized examples and do not upload private datasets.

<div align="center">

[![Bug Report](https://img.shields.io/badge/Open-Bug_Report-876B52?style=for-the-badge&logo=github&logoColor=white)](https://github.com/amgedi/Biodiversity-Data-Rescue-Workbench/issues/new?template=bug.md)
[![Feature Request](https://img.shields.io/badge/Open-Feature_Request-6F875F?style=for-the-badge&logo=github&logoColor=white)](https://github.com/amgedi/Biodiversity-Data-Rescue-Workbench/issues/new?template=feature.md)
[![Scientific Concern](https://img.shields.io/badge/Open-Scientific_Concern-507B68?style=for-the-badge&logo=github&logoColor=white)](https://github.com/amgedi/Biodiversity-Data-Rescue-Workbench/issues/new?template=scientific-concern.md)
[![Contributing Guide](https://img.shields.io/badge/Read-Contributing-A18463?style=for-the-badge&logo=git&logoColor=white)](CONTRIBUTING.md)

</div>

Cite the software using [CITATION.cff](CITATION.cff).

## Security

Please do not post credentials, confidential research, private datasets, or exploit details in public issues. Use the reporting steps in [SECURITY.md](SECURITY.md).

<div align="center">

[![Security Policy](https://img.shields.io/badge/Security-Reporting-6F875F?style=for-the-badge&logo=github&logoColor=white)](SECURITY.md)
[![Data Safety](https://img.shields.io/badge/Data-Safety_Notes-725D45?style=for-the-badge&logo=shield&logoColor=white)](docs/data-safety.md)

</div>

## Support the project

Biodiversity Data Rescue Workbench is free and open source. If it saves you time or helps rescue a dataset, optional support helps with development, testing, documentation, accessibility, and future research-software work.

<div align="center">

[![GitHub Sponsors](https://img.shields.io/badge/GitHub_Sponsors-Support-876B52?style=for-the-badge&logo=githubsponsors&logoColor=white)](https://github.com/sponsors/amgedi)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support-6D7F58?style=for-the-badge&logo=kofi&logoColor=white)](https://ko-fi.com/openfhs)

</div>

Every feature stays free. Support reminders can be disabled in **Settings → About**.

## License

Original project code is licensed under **AGPL-3.0-only**. See [LICENSE](LICENSE). Third-party components keep their own licenses and attribution; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
