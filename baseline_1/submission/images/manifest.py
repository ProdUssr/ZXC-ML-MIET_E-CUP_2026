"""Synchronous, non-blocking manifest: no file contents are opened in Phase 0."""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
VALID={".jpg",".jpeg",".png"}
def attach_images(items,root:Path,budget):
    if budget.max_images<=0:return list(items),{"scanned":0,"attached":0}
    output=[]; attached=0
    image_root=root/"images"
    for item in items:
        paths=[]
        try:
            for path in sorted(
                image_root.joinpath(item.id).iterdir(),
                key=lambda value: (value.name.lower(), value.name),
            ):
                if path.suffix.lower() in VALID:
                    paths.append(str(path));
                    if len(paths)>=budget.max_images: break
        except OSError: pass
        attached+=len(paths); output.append(replace(item,image_paths=tuple(paths)))
    return output,{"scanned":len(items),"attached":attached}
