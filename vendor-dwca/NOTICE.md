# Pinned standards schemas

Original, unmodified XML schema bytes retrieved on 2026-10-04. The manifest records canonical and retrieved URLs, sizes and SHA-256 hashes. They are used offline; the application does not fetch schemas at runtime.

TDWG Darwin Core text descriptor and term/base schemas: [TDWG text guide](https://dwc.tdwg.org/text/), [TDWG source repository](https://github.com/tdwg/dwc). XML namespace schemas: [GBIF](https://rs.gbif.org/schema/xml.xsd) and [W3C](https://www.w3.org/2001/03/xml.xsd). Dublin Core schemas retain their original creator attribution and documentation; [DCMI XML schemas](https://www.dublincore.org/schemas/xmls/) are provided under the site's stated Creative Commons Attribution 3.0 terms. Original notices remain in each file.

The pinned `tdwg_dwcterms.xsd` refers to `chrono:chronometricAgeID` without a corresponding namespace import. The official descriptor therefore fails local lxml schema compilation. This is reported as unavailable validation, not a successful standards pass; original files are not edited to conceal that limitation. Local CSV/index/link checks are distinct from official schema or scientific validation.
