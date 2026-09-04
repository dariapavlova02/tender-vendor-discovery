"""Isolated storage for document uploads."""
from pathlib import Path
from uuid import uuid4


def save_uploads(uploaded_files, root: Path) -> list[Path]:
    directory = root / uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    paths = []
    for uploaded in uploaded_files:
        name = Path(uploaded.name.replace("\\", "/")).name
        if name in {"", ".", ".."}:
            raise ValueError("Upload needs a filename")
        path = directory / name
        with path.open("xb") as target:
            target.write(uploaded.getbuffer())
        paths.append(path)
    return paths
