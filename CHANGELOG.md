# Changelog

This file records changes made by the independently maintained fork after upstream commit
`a7348f0`. Upstream history remains available in Git.

## 2026-07-11 — Fork improvement pass

### Added

- `add_sketch_text`, providing native SolidWorks sketch-text creation with anchor, height,
  rotation, font, bold, and italic controls.
- `capture_view`, providing named-view, zoom-fit PNG capture returned directly as MCP image content.
- Hash-pinned Windows/Python 3.12 runtime and development dependency lock files.
- Windows CI for contract checks, offline compiler tests, and Python compilation.
- Public fork attribution, DCO contribution terms, environment template, and security guidance.

### Changed

- Increased the MCP surface from 37 to 39 tools.
- Replaced verbose pipe-delimited adapter results with compact JSON responses.
- Preserved additional mass-property precision so small feature volume changes remain visible.
- Targeted .NET Framework 4.8.1 in the execution project.

### Fixed

- Retried boss creation with all sketch regions selected, allowing disjoint profiles such as
  dissolved TrueType glyphs to produce one joined boss.
- Passed SolidWorks sketch-text width and spacing as percentage integers, preventing collapsed,
  self-intersecting glyphs.
- Added actionable diagnostics for blind cuts whose reference plane is coincident with a model
  face.
- Verified Right Plane blind cuts as single-direction: the default cuts toward positive X and
  `reverse=true` flips the direction.

### Verification

- Live verification was performed against SolidWorks 2026 for raised sketch text, direct PNG
  capture, multi-region boss creation, cut direction, and the offset-plane blind-cut workaround.

## Fork base — 2026-07-11

- Forked from `eyfel/mcp-server-solidworks` at commit `a7348f0`.
- Fork modifications maintained by Benny Cohen beginning 2026-07-11.
