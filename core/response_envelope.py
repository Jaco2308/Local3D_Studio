"""
Local3D Studio Standardized Response & Error Contracts (Inspired by REA Tool Contracts)
Wraps tool outputs and exceptions into predictable, typed JSON envelopes with actionable remediations.
"""

import sys
import json
import time
from typing import Dict, Any, Optional
from core.hardware_backend import HardwareManager


def format_success(
    result: Any,
    operation: str,
    duration_ms: Optional[float] = None,
    limitations: Optional[list] = None
) -> str:
    """Creates a standardized success envelope compatible with MCP agents."""
    hw = HardwareManager.get_instance()
    envelope = {
        "status": "success",
        "operation": operation,
        "normalized_result": result if isinstance(result, (dict, list)) else {"value": result},
        "telemetry": {
            "tier": hw.tier_config.name,
            "badge": hw.get_hardware_badge(),
            "blender_path": hw.blender_path or "NOT_FOUND",
            "duration_ms": round(duration_ms, 2) if duration_ms is not None else None
        },
        "limitations": limitations or []
    }
    return json.dumps(envelope, indent=2, ensure_ascii=False)


def format_error(
    code: str,
    message: str,
    remediation: str,
    details: Optional[Dict[str, Any]] = None
) -> str:
    """Creates a standardized canonical error envelope with explicit remediation instructions."""
    envelope = {
        "status": "error",
        "isError": True,
        "error": {
            "code": code,
            "message": message,
            "remediation": remediation,
            "details": details or {}
        }
    }
    return json.dumps(envelope, indent=2, ensure_ascii=False)
