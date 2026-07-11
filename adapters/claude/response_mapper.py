"""Map solidworks-execution responses to compact MCP result strings."""
import json


def _compact_json(payload: dict) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def _parse_payload_item(item):
    if not isinstance(item, str):
        return item
    stripped = item.strip()
    if not stripped or stripped[0] not in "{[":
        return item
    try:
        return json.loads(stripped)
    except Exception:
        return item


def _features_payload(features, unwrap_single: bool = False):
    if not features:
        return None
    parsed = [_parse_payload_item(item) for item in features]
    if unwrap_single and len(parsed) == 1:
        return parsed[0]
    return parsed


def map_response(response: dict, tool_name: str = "") -> str:
    """Convert an ExecutionResponse dict into a compact MCP-compatible string."""
    status = response.get("status")

    if status == "COMPLETED":
        state = response.get("cadState") or {}
        payload = {
            "ok": True,
            "status": "COMPLETED",
            "tool": tool_name or None,
            "state_version": response.get("stateVersion"),
            "document": state.get("activeDocument"),
        }
        if state.get("activeSketch") is not None:
            payload["sketch"] = state.get("activeSketch")

        is_read_payload = tool_name.startswith("analyze_") or tool_name in {"get_selection", "verify_state"}
        features = _features_payload(state.get("features") or [], unwrap_single=is_read_payload)
        if features is not None:
            if is_read_payload:
                payload["data"] = features
            else:
                payload["features"] = features

        result_geometry = response.get("result_geometry")
        if result_geometry is not None:
            payload["result_geometry"] = result_geometry

        return _compact_json({k: v for k, v in payload.items() if v is not None})

    if status == "DUPLICATE":
        return _compact_json({
            "ok": True,
            "status": "DUPLICATE",
            "tool": tool_name or None,
            "last_known_state_version": response.get("last_known_state_version"),
        })

    if status == "FAILED":
        error = response.get("error") or {}
        raise RuntimeError(_compact_json({
            "ok": False,
            "status": "FAILED",
            "tool": tool_name or None,
            "code": error.get("code"),
            "message": error.get("message"),
        }))

    raise RuntimeError(f"Unknown execution response status: {status}")
