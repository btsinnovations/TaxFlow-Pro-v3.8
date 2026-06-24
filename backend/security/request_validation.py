"""Global request size limits for API hardening (TASK-031).

- ``TAXFLOW_MAX_BODY_SIZE_BYTES`` caps JSON/form bodies. Default: 10 MiB.
- Multipart uploads to ``/api/upload`` are governed by the upload-specific
  validator in ``backend.security.upload_validator`` and are exempt from this
  general body limit.
"""

from __future__ import annotations

import os

# 10 MiB default for general request bodies (JSON, form data, etc.)
MAX_BODY_SIZE_BYTES = int(
    os.environ.get("TAXFLOW_MAX_BODY_SIZE_BYTES", 10 * 1024 * 1024)
)


def human_size(num_bytes: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if abs(num_bytes) < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TiB"
