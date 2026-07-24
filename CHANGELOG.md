# Changelog

## Unreleased

- Added `search_solidworks_references` for short, page-cited retrieval from locally owned SolidWorks PDFs.
- Added `scripts/build_reference_index.py`; PDFs stay external and generated page indexes remain under the gitignored `.solidpilot/` directory.
- Added eight SolidWorks Simulation tools: create/list/delete static and topology studies, add fixed
  fixtures and normal forces, mesh and solve, extract stress/displacement/factor-of-safety results,
  and configure topology goals, mass reduction, preserved faces, and minimum thickness.
- Added strict adapter-side validation for model-space face-coordinate arrays and a dedicated
  `SIMULATION_TIMEOUT` (600 seconds by default) for synchronous meshing and solves.
- Corrected Simulation COM interop for dispatch-array face selections, mesh length units and quality,
  result-array ordering/units, material-free user-yield FoS fallback, and topology edit transactions.

This file records changes made by the independently maintained fork after upstream commit
`a7348f0`. Upstream history remains available in Git.

## 2026-07-12 — Reference-modeling pass (design photos + user input)

### Added

- `load_reference_image` — normalize a design photo/drawing from disk (png/jpg/bmp/gif/tiff)
  and SEE it: optional normalized crop box to zoom into details/dimensions, long-edge cap,
  returned as MCP image content. Backed by a new pure-image `prepare_reference_image`
  execution handler (no COM, no state change).
- `capture_view_set(reference_image_path=...)` and `inspect_model(reference_image_path=...)` —
  compose the design photo as a labelled row ABOVE the live model views in one PNG: the
  compare-and-iterate loop for modeling from a reference, one image per check.
- `solidworks_help("reference_modeling")` — the photo-to-part protocol (decompose first, crop
  for details, one stated scale assumption, feature-tree plan, per-feature volume checks,
  reference-vs-model visual compare after every major feature).

### Changed

- 47 → 48 tools while the always-loaded schema SHRANK (~32.6k → ~31.4k chars): concise
  schema descriptions for auto_center_marks, open_document, add_hole_callout, ensure_ready,
  export_document, and set_part_material (full guidance stays in source docstrings and
  on-demand help).

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
