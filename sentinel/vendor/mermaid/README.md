# Vendored mermaid

Third-party code, vendored for IMP-273 (`/view --artifact diagrams`). The views' CSP admits inline
scripts only, so `sentinel/diagrams.py` inlines this file into the diagrams page. It is never fetched
at run time.

| Field | Value |
|---|---|
| Package | `mermaid` (npm) |
| Version | `11.17.2`, the latest of branch 11 at download time |
| File | `dist/mermaid.min.js` from `https://registry.npmjs.org/mermaid/-/mermaid-11.17.2.tgz` |
| Tarball integrity | verified against the registry's `sha512` before extraction |
| `mermaid.min.js` sha256 | `581ed7d74bd9048d0e3a91363927d72ef22942d7722546b27f7cc29e35390eb8` |
| `LICENSE` sha256 | `ec9fb67dcb25eccc416ed56e1aab819222c805a2a4bfe4cb19e7556bf2ffde80` |
| License | MIT (`LICENSE`, embedded in the page as the library's leading comment) |

`/doctor` (check `vendored mermaid`) fails when either file does not match its pinned sha256. The
pins live in `sentinel/diagrams.py` (`MERMAID_SHA256`, `MERMAID_LICENSE_SHA256`). `.gitattributes`
keeps these bytes untouched (`-text`).

To update: download a fixed version once, verify the tarball integrity, replace both files, update
the pins and this table, and run the diagrams tests and `/doctor`. The minimal `.pyz`
(`sentinel/build.py`) leaves this folder out.
