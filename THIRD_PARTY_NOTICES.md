# Bundled offline readers

xlrd 2.0.2 is bundled unmodified for passive legacy `.xls` recovery. Its BSD license is retained in [vendor-xls/LICENSE-xlrd.txt](vendor-xls/LICENSE-xlrd.txt); [vendor-xls/manifest.json](vendor-xls/manifest.json) records the pinned distribution hash and every source hash/length. Runtime verifies the inventory before the bounded worker starts. The development-only xlwt fixture generator is not bundled. The application reads cached values; it does not recover formula text, run macros, recalculate formulas, or faithfully reconstruct workbooks. [Official xlrd documentation](https://xlrd.readthedocs.io/en/stable/) records these limitations.

## PDF reader

pypdf 6.10.0, BSD-3-Clause, bundled unmodified from its pinned upstream distribution. Full copyright, conditions and disclaimer are retained in [vendor/PYPDF_LICENSE.txt](vendor/PYPDF_LICENSE.txt). [vendor/pypdf-manifest.json](vendor/pypdf-manifest.json) records every source hash and byte length. No runtime installation or cloud service is needed.

[Official PDF extraction documentation](https://pypdf.readthedocs.io/en/6.10.0/user/extract-text.html) describes text-order/OCR and memory limitations. The Workbench adds a separately bounded process and explicitly reviewed evidence; it does not assert faithful visual/table reconstruction.

Windows memory bounds use [Job Object process limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information). POSIX uses process address-space limits; these are different measurements and do not certify total Workbench RSS.

## Legacy Word container and fictional formatting fixture

Legacy DOC reuses the unmodified pinned BSD xlrd 2.0.2 container module already listed above. Word text policy is original application code based on Microsoft’s public MS-DOC specification. Fictional legacy-notes.doc derives formatting streams from [Apache POI simple.doc](https://github.com/apache/poi/blob/trunk/test-data/document/simple.doc): the entire main story is replaced with fictional text and all other OLE streams are removed. Apache Software Foundation attribution, full upstream license and notice are retained in examples/APACHE_POI_FIXTURE_LICENSE.txt and examples/APACHE_POI_FIXTURE_NOTICE.txt. Other DOC fixtures are original explicitly synthetic parser boundaries. No Apache POI runtime/JAR is bundled or needed.

## Public scientific fixtures

The official Camtrap DP example archive is an upstream public example, not a user research project. Its embedded datapackage declares CC0-1.0 for data and CC-BY-4.0 for media; preserve those declarations and contributor attribution. Darwin Core and Camtrap schemas retain their upstream metadata and licenses. Synthetic practice and parser-boundary fixtures are labeled in their source or accompanying descriptions.
