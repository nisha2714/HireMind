"""Browser video recorder (MediaRecorder) exposed as a Streamlit component."""
from pathlib import Path

import streamlit.components.v1 as components

_component = components.declare_component(
    "video_recorder",
    path=str(Path(__file__).resolve().parent.parent / "components" / "video_recorder"),
)


def video_recorder(key: str, max_seconds: int = 120):
    """Return None until the candidate records; then a dict with status 'recorded' or 'error'."""
    return _component(key=key, max_seconds=max_seconds, default=None)
