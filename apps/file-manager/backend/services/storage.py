import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from backend.models.file import FileSummary, FileType, FileStatus
from backend.utils.config import DATA_DIR, ALLOWED_EXTENSIONS


def get_file_type(filename: str, mime_type: str = "") -> FileType:
    suffix = Path(filename).suffix.lower()
    for ftype, exts in ALLOWED_EXTENSIONS.items():
        if suffix in exts:
            return FileType(ftype)
    if mime_type.startswith("image/"):
        return FileType.image
    if mime_type.startswith("video/"):
        return FileType.video
    if mime_type.startswith("audio/"):
        return FileType.audio
    return FileType.other


def get_type_dir(file_type: FileType) -> str:
    return {
        FileType.image: "images",
        FileType.video: "videos",
        FileType.document: "documents",
        FileType.audio: "audios",
        FileType.link: "links",
        FileType.text: "texts",
        FileType.other: "others",
    }.get(file_type, "others")


def get_storage_path(date_str: str, file_type: FileType) -> Path:
    path = DATA_DIR / date_str / get_type_dir(file_type)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_file(content: bytes, original_filename: str, mime_type: str = "") -> FileSummary:
    file_id = str(uuid.uuid4())
    file_type = get_file_type(original_filename, mime_type)
    date_str = datetime.now().strftime("%Y-%m-%d")
    suffix = Path(original_filename).suffix
    stored_name = f"{file_id}{suffix}"
    dir_path = get_storage_path(date_str, file_type)
    file_path = dir_path / stored_name

    with open(file_path, "wb") as f:
        f.write(content)

    meta = FileSummary(
        id=file_id,
        filename=stored_name,
        original_filename=original_filename,
        type=file_type,
        file_path=str(file_path.relative_to(DATA_DIR)),
        file_size=len(content),
        mime_type=mime_type,
        status=FileStatus.pending,
    )
    save_meta(meta)
    return meta


def save_text(content: str) -> FileSummary:
    file_id = str(uuid.uuid4())
    date_str = datetime.now().strftime("%Y-%m-%d")
    dir_path = get_storage_path(date_str, FileType.text)
    txt_file = dir_path / f"{file_id}.txt"

    with open(txt_file, "w", encoding="utf-8") as f:
        f.write(content)

    meta = FileSummary(
        id=file_id,
        filename=f"{file_id}.txt",
        original_filename=content[:50] + ("…" if len(content) > 50 else ""),
        type=FileType.text,
        file_path=str(txt_file.relative_to(DATA_DIR)),
        file_size=len(content.encode("utf-8")),
        mime_type="text/plain",
        summary=content,
        status=FileStatus.ready,
    )
    save_meta(meta)
    return meta


def save_link(url: str) -> FileSummary:
    file_id = str(uuid.uuid4())
    date_str = datetime.now().strftime("%Y-%m-%d")
    dir_path = get_storage_path(date_str, FileType.link)
    link_file = dir_path / f"{file_id}_url.txt"

    with open(link_file, "w", encoding="utf-8") as f:
        f.write(url)

    meta = FileSummary(
        id=file_id,
        filename=f"{file_id}_url.txt",
        original_filename=url,
        type=FileType.link,
        url=url,
        file_path=str(link_file.relative_to(DATA_DIR)),
        status=FileStatus.pending,
    )
    save_meta(meta)
    return meta


def save_meta(meta: FileSummary):
    meta_path = _meta_path(meta)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta.model_dump(mode="json"), f, ensure_ascii=False, indent=2, default=str)


def _meta_path(meta: FileSummary) -> Path:
    if meta.file_path:
        file_abs = DATA_DIR / meta.file_path
        return file_abs.parent / f"{meta.id}_summary.json"
    date_str = meta.created_at.strftime("%Y-%m-%d")
    dir_path = get_storage_path(date_str, meta.type)
    return dir_path / f"{meta.id}_summary.json"


def load_meta(meta_path: Path) -> Optional[FileSummary]:
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return FileSummary(**data)
    except Exception:
        return None


def get_all_files(date_filter: Optional[str] = None, type_filter: Optional[str] = None) -> List[FileSummary]:
    results = []
    search_root = DATA_DIR
    if date_filter:
        search_root = DATA_DIR / date_filter
        if not search_root.exists():
            return []

    for meta_file in sorted(search_root.rglob("*_summary.json"), reverse=True):
        meta = load_meta(meta_file)
        if meta is None:
            continue
        if type_filter and meta.type.value != type_filter:
            continue
        results.append(meta)

    return results


def get_file_by_id(file_id: str) -> Optional[FileSummary]:
    for meta_file in DATA_DIR.rglob(f"{file_id}_summary.json"):
        return load_meta(meta_file)
    return None


def delete_file(file_id: str) -> bool:
    meta = get_file_by_id(file_id)
    if not meta:
        return False
    if meta.file_path:
        abs_path = DATA_DIR / meta.file_path
        if abs_path.exists():
            abs_path.unlink()
    meta_file = list(DATA_DIR.rglob(f"{file_id}_summary.json"))
    if meta_file:
        meta_file[0].unlink()
    return True


def get_file_absolute_path(meta: FileSummary) -> Optional[Path]:
    if meta.file_path:
        return DATA_DIR / meta.file_path
    return None
