# Contributing Guide

Thanks for contributing to SolidPilot. This document summarizes how to set up the development environment, the architectural rules, and the flow for adding a new capability.

SolidPilot is an AI-driven CAD automation system for SolidWorks that runs as an MCP server. For an overview, see [README.md](README.md).

This repository is Benny Cohen's independently maintained AGPL-3.0 fork of
`eyfel/mcp-server-solidworks`, based on upstream commit `a7348f0`. Contributions submitted here
target this fork; they are not submissions to, or endorsements by, the upstream maintainer.

---

## Architecture and invariants

The system has four layers, and preserving these boundaries is the foundation of the project:

| Layer | Directory | Responsibility |
|---|---|---|
| `cad-planner` | `cad-planner/` | Intent -> CAD-neutral Feature Graph IR. Does not touch COM, does not emit raw tool calls. |
| `solidworks-compiler` | `solidworks-compiler/` | IR -> tool calls + reference resolution. Deterministic; contains no LLM and no MCP. |
| `solidworks-execution` | `solidworks-execution/` | The only layer that touches SolidWorks COM (C#, .NET 4.8.1). |
| `adapters/claude` | `adapters/claude/` | MCP protocol bridge (Python, FastMCP). |

Rules that must never be violated:

- The AI works at the **feature level**; only the compiler knows tools; only `SolidWorksService.cs` touches COM.
- **MCP is the top boundary** (between the client and the IR), not an internal transport. The compiler reaches the execution layer over plain REST.
- The IR is **CAD-neutral**; SolidWorks-specific details live only in the compiler and execution layers.
- The execution and planner layers have no knowledge of which client is calling them.
- Adding a new CAD backend means adding a new compiler and execution layer; the IR and `cad-planner` stay unchanged.
- The adapter layer is provider-specific. Supporting a new AI client (OpenClaw, OpenAI, a local LLM, etc.) means only adding a new adapter that reuses the shared bridge core.

---

## Development environment

### Requirements

- Windows and **SolidWorks 2026** (development happens against a local SolidWorks install).
- **.NET Framework 4.8.1 Developer Pack** and MSBuild (available with Visual Studio 2022).
- **Python 3.12** for the checked-in Windows lock files and CI parity.

### Building and running the execution layer

Build:

```
& "C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe" solidworks-execution\SolidworksExecution.sln /t:Build /p:Configuration=Debug
```

Restart (headless, `http://localhost:5000`):

```
Get-Process SolidworksExecution -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Process solidworks-execution\SolidworksExecution\bin\Debug\SolidworksExecution.exe -WindowStyle Hidden
```

The server runs headless and must be running while SolidWorks is open (the COM connection is established lazily, on the first tool call). C#-side errors and per-request traces are written to `solidworks-execution\SolidworksExecution\bin\Debug\execution.log`.

### Running the adapter

From the repository root:

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
Copy-Item adapters\claude\.env.example adapters\claude\.env
& .\.venv\Scripts\python.exe .\adapters\claude\server.py
```

**Important:** the Python MCP adapter does not hot-reload while running. When you change `server.py` (for example, adding a new parameter), the MCP server must be reconnected. Reconnecting also resets the adapter's local `state_version` to 0. (The C# execution server, by contrast, can be restarted.)

### Dependency files

- `requirements.txt` and `adapters/claude/requirements.txt` define runtime dependency ranges.
- `adapters/claude/requirements-dev.txt` adds development and test dependencies.
- `requirements.lock` and `requirements-dev.lock` are hash-pinned for Windows and Python 3.12.
  End users should install `requirements.lock`; contributors and CI should install
  `requirements-dev.lock` with `--require-hashes`.

When a dependency range changes, regenerate and commit both applicable lock files with `uv`:

```powershell
uv pip compile requirements.txt --output-file requirements.lock --python-version 3.12 --python-platform windows --generate-hashes
uv pip compile adapters\claude\requirements-dev.txt --output-file requirements-dev.lock --python-version 3.12 --python-platform windows --generate-hashes
```

---

## Adding a new capability

### A new low-level tool (execution surface)

1. **Contract** — add the tool to `solidworks-execution/contracts/tool-schemas.json`.
2. **Execution** — add a `case "tool_name":` in `ToolController.cs` and implement it in `SolidWorksService.cs`. **Verify any SolidWorks COM API signature by reflecting the interop assembly first — never invent a method name or argument list.** The real API frequently differs from what looks plausible (for example, the model-item insertion API lives on `IDrawingDoc`, not `IView`; `GetLines3` returns empty while `GetPolylines7` is the working geometry getter). Decode unknown return shapes empirically against a live document before writing the parser.
3. **Adapter** — register the MCP tool in `adapters/claude/server.py`. Model-facing guidance lives here (the client never sees `tool-schemas.json`): use `Literal` enums for discriminators, Pydantic `Field` constraints for units and ranges, and real required parameters.
4. **Verify** — run the contract test (see below), then validate against live SolidWorks.

### A new feature (IR level — the strategic direction)

1. Add the feature type to `cad-planner/contracts/feature-graph.schema.json` (this also registers the capability).
2. Add its lowering rule and any required reference resolution in `solidworks-compiler`.
3. It reuses existing low-level tools; usually no new execution tool is needed.

> **Forward IR status:** the direct `submit_feature_graph` entry point is development scaffolding and
> is currently commented out, so it is not part of the MCP surface. Exercise the supported compiler
> path through `rebuild_from_ir`. Re-enabling the forward entry point requires a deliberate code and
> contract change, followed by the normal contract and live SolidWorks checks.

---

## Conventions

- **Units:** all lengths are in meters (SolidWorks internal units). Angles are taken in degrees at the adapter boundary.
- **HTTP semantics:** all CAD results return HTTP 200; `FAILED` and `DUPLICATE` are domain states, not transport errors. HTTP 400 is only for malformed requests or unknown tool names.
- **state_version:** every request is checked with strict equality; a mismatch returns `FAILED` with `INVALID_STATE_VERSION`. The adapter increments its local value only on a `COMPLETED` response.
- **Variable-length array parameters** must be passed as a JSON string at the MCP boundary (e.g. `points: str = "[]"`), not as a `list`/`List` type. The MCP client stringifies list-typed arguments, which makes a list-typed parameter uncallable; parse the string in the adapter (`json.loads`) or in C#.
- **C# JSON:** parameters are deserialized as a `JObject`; use `p.Value<T>("key")`. Serialization is camelCase and null values are omitted.
- **swconst enums:** must be used as inlined constants, never as runtime types (the relevant DLL is not copied into `bin/Debug`; using one as a type causes a runtime load failure).

---

## Testing

- **Contract test:** catches any tool or parameter drift across the 39-tool adapter surface and
  `tool-schemas.json`.

  ```powershell
  & .\.venv\Scripts\python.exe .\adapters\claude\tests\test_schema_contract.py
  ```

- **Offline compiler tests:**

  ```powershell
  & .\.venv\Scripts\python.exe .\solidworks-compiler\pycompiler\tests\test_compiler.py
  ```

- **Syntax check:**

  ```powershell
  & .\.venv\Scripts\python.exe -m compileall -q adapters\claude solidworks-compiler scripts
  ```

The Windows GitHub Actions workflow in `.github/workflows/ci.yml` installs
`requirements-dev.lock` with hash verification and runs all three offline checks for pushes to
`main` and pull requests.

- **Live testing (manual by design):** tools are verified against live SolidWorks, with the GUI open, case by case. A cohesive batch of tools is chosen together and tested as a batch. When a tool fails, inspect `execution.log` and report the expected result, the API response, and a hypothesis. For part-model changes, use `capture_view` for fast top/isometric/side visual checks. For drawing-only content, an exported PDF remains the ground truth because some interop counters under-report inserted annotations and center marks.

Live SolidWorks behavior remains manually verified; the automated suite covers the MCP contract,
the deterministic compiler, and Python source compilation without requiring a SolidWorks license.

---

## Contribution terms (AGPL-3.0 + DCO)

This fork does **not** ask contributors to grant proprietary relicensing rights. Contributions
are accepted under the same [GNU AGPL-3.0](LICENSE) terms used for the fork, with a
Developer Certificate of Origin (DCO) sign-off. This is an inbound-equals-outbound policy, not a
copyright assignment.

Sign every commit with:

```powershell
git commit -s
```

The resulting `Signed-off-by: Name <email>` line certifies that you have the right to submit the
work under the project's license. The complete policy and DCO text are in [CLA.md](CLA.md). The
filename is retained for compatibility with upstream links; this fork does not use the upstream
commercial-relicensing CLA.

---

## Commits and Pull Requests

- Write meaningful, focused commits; do not mix several unrelated changes in one commit.
- If you change the behavior of a tool or feature, keep the relevant contract and tests up to date.
- In the Pull Request description, state what you changed, why, and how you verified it.
- Sign off every commit under the DCO (see [Contribution terms](#contribution-terms-agpl-30--dco)).

For questions and discussions, feel free to open an issue.
