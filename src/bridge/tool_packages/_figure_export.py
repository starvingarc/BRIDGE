from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from typing import Any


def figure_export_source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def render_figure_payloads(figure: Any) -> dict[str, tuple[str, bytes]]:
    from matplotlib import pyplot as plt

    outputs = {}
    try:
        for extension, media_type in (
            ("svg", "image/svg+xml"),
            ("png", "image/png"),
            ("pdf", "application/pdf"),
        ):
            buffer = BytesIO()
            metadata = {"Creator": "BRIDGE"}
            if extension == "svg":
                metadata["Date"] = None
                figure.savefig(buffer, format="svg", metadata=metadata)
            elif extension == "png":
                figure.savefig(
                    buffer,
                    format="png",
                    dpi=220,
                    metadata={"Software": "BRIDGE"},
                )
            else:
                metadata.update({"CreationDate": None, "ModDate": None})
                figure.savefig(buffer, format="pdf", metadata=metadata)
            outputs[extension] = (media_type, buffer.getvalue())
    finally:
        plt.close(figure)
    return outputs
