# Changelog

This file records changes made by the independently maintained fork after upstream commit
`a7348f0`. Upstream history remains available in Git.

## 2026-07-12 — Native assembly pass (first slice)

### Added

- `open_new_assembly`, creating a blank assembly from the default (or a given) template.
- `insert_component`, inserting saved parts/assemblies with verified rename, verified
  configuration, and tri-state `fixed` (omitted preserves SolidWorks' first-component grounding).
  XYZ placement is documented as approximate (bounding-box centre).
- `add_assembly_mate` — coincident / concentric / distance mates through the selection-free
  `IAssemblyDoc.CreateMateData`/`CreateMate` path. Faces are addressed by Base64 persistent
  references (cross-call safe) or component + same-call face index (top-level only; a lightweight
  component involved via the index path is resolved individually, never the whole assembly).
- `analyze_assembly` — read-only structure: components with suppression/fixed/configuration/
  position, per-face persistent `ref` handles (`include_faces=true`), and mates read from the
  MateGroup subfeatures (feature name, type, alignment, suppression, dimension value).
- `inspect_model` now detects assemblies: component/mate structure plus mass instead of
  part-only geometry/features analysis; montage capture unchanged.

### Changed

- Increased the MCP surface from 43 to 47 tools.
- Every response now reports the live document type (PART/ASSEMBLY/DRAWING) instead of a
  hardcoded PART.

## 2026-07-12 — Performance and visual-assignment pass

### Added

- `execute_batch`, running up to 100 ordered execution-layer operations in one MCP call with
  compact results and references to earlier outputs.
- `capture_view_set`, returning a labelled 1–4 view PNG montage.
- `inspect_model`, combining compact topology, mass, feature-tree summary, and a multi-view image.
- `solidworks_help`, moving detailed workflow guidance behind on-demand topics.
- Native `extrude_feature(feature_type="revolve_cut")` support.

### Changed

- Increased the MCP surface from 39 to 43 tools.
- Reused persistent localhost HTTP connections instead of creating one client per CAD operation.
- Reduced the always-loaded MCP schema from about 54,243 to under 30,000 characters while retaining
  detailed source docstrings and on-demand help.
- Documented a measurement-first screenshot-to-CAD workflow using synchronized orthographic views.

### Verification

- Added adapter orchestration tests, contract coverage for all 43 tools, live montage inspection,
  live revolved-cut verification, and before/after latency and schema-size measurements.

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
