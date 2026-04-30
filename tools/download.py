from pathlib import Path
from typing import Union

import yt_dlp


def download_video(url: str, output_dir: Union[str, Path], dry_run: bool = False) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = output_dir / "%(id)s.%(ext)s"

    if dry_run:
        fake = output_dir / "dry_run_source.mp4"
        fake.write_bytes(b"dry-run")
        return fake

    ydl_opts = {
        "outtmpl": str(output_template),
        "format": "mp4/best",
        "quiet": True,
        "noprogress": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)
    return Path(path)

