"""Run one private loopback service; deployment configuration stays server-side."""
import json
import os
from pathlib import Path

import uvicorn

from .app import Settings, create_app


def main():
    pins = json.loads(os.environ.get("BRIDGE_WEB_TRUSTED_ANCESTORS", "{}"))
    if pins:
        from bridge.storage.private_paths import configure_trusted_ancestors
        configure_trusted_ancestors({Path(path): tuple(identity) for path, identity in pins.items()})
    settings = Settings(
        storage_root=Path(os.environ["BRIDGE_WEB_STORAGE"]),
        token=os.environ["BRIDGE_WEB_TOKEN"],
        model_base_url=os.environ["BRIDGE_WEB_MODEL_BASE_URL"],
        model=os.environ["BRIDGE_WEB_MODEL"],
        model_api_key=os.environ["BRIDGE_WEB_MODEL_API_KEY"],
        origin=os.environ.get("BRIDGE_WEB_ORIGIN", "http://127.0.0.1:8765"),
        cell_state_measurement_spec_ref=os.environ.get("BRIDGE_WEB_CELL_STATE_MEASUREMENT_SPEC_REF") or None,
        static_dir=Path(os.environ["BRIDGE_WEB_STATIC_DIR"]) if os.environ.get("BRIDGE_WEB_STATIC_DIR") else None,
    )
    uvicorn.run(create_app(settings), host="127.0.0.1", port=int(os.environ.get("BRIDGE_WEB_PORT", "8765")),
                access_log=False, proxy_headers=False)


if __name__ == "__main__":
    main()
