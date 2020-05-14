import logging
import os
from datetime import datetime

from . import imaging


def needs_rotation(meta):
    orientation = meta.get("Orientation", "")
    return "otate 90" in orientation or "otate 270" in orientation


class Metadata:
    def __init__(self):
        self.cache = {}

    def clear_cache(self):
        self.cache.clear()

    def get(self, filename):
        # check cache
        meta = self.cache.get(filename)
        if meta:
            return meta

        # try to read actual metadata
        meta = self.read(filename)
        if meta:
            self.cache[filename] = meta
            return meta

        # no metadata, fallback to simplest default case
        w, h = imaging.get_size_simple(filename)
        stat = os.stat(filename)
        meta = {
            "filename": os.path.basename(filename),
            "needs_rotation": False,
            "width": w,
            "height": h,
            "orientation": None,
            "file_date": stat.st_mtime,
            "file_size": stat.st_size,
            "exif": {},
        }

        self.cache[filename] = meta
        return meta

    def get_cached(self, filename):
        return self.cache.get(filename, None)

    def read(self, filename):
        try:
            if imaging.exiftool is None or not imaging.exiftool.running:
                return None

            meta = imaging.exiftool.get_metadata(filename)

            date_key = "DateTimeOriginal"
            if date_key in meta:
                meta[date_key] = datetime.strptime(meta[date_key], "%Y:%m:%d %H:%M:%S")

            # also cache the most important part
            needs_rot = needs_rotation(meta)
            stat = os.stat(filename)
            return {
                "filename": os.path.basename(filename),
                "needs_rotation": needs_rot,
                "width": meta["ImageWidth" if not needs_rot else "ImageHeight"],
                "height": meta["ImageHeight" if not needs_rot else "ImageWidth"],
                "orientation": meta.get("Orientation", None),
                "file_date": stat.st_mtime,
                "file_size": stat.st_size,
                "exif": meta,
            }
        except Exception:
            logging.exception("Could not parse meta-info for %s" % filename)
            return None


metadata = Metadata()
