"""Writing a file so a reader never sees it half-written.

Extracted from ``gridlab.scripts.build_atlas``, which needed it first and now shares it with
the daily recorder. Both write an artifact that something else reads while the writer is
still running, and both must leave the previous good artifact intact when a run dies partway.
"""

from __future__ import annotations

import os
from pathlib import Path


def write_atomic(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` without ever exposing a partial file.

    ``Path.write_text`` truncates before it writes, which opens a window where the file on
    disk is a prefix of valid JSON. That is not theoretical: the atlas sweep takes half a
    minute, ``/api/v1/atlas`` reads the same file, and a truncated `atlas.json` makes the
    endpoint return **500 Atlas file unreadable** rather than the previous good sweep. A run
    interrupted partway leaves the same wreckage permanently.

    Writing beside the target and renaming closes it. ``os.replace`` is atomic on POSIX and
    on Windows, so a reader sees either the old file or the new one and never a mixture. The
    temporary file is created in the destination directory because a rename across
    filesystems is not atomic — and both ``data/`` and ``recordings/`` are bind mounts, so a
    system temp directory would be exactly that.
    """
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except BaseException:
        # Including KeyboardInterrupt: an interrupted run should leave no debris, and the
        # previous artifact stays valid because it was never opened for writing.
        tmp.unlink(missing_ok=True)
        raise
