from . import imaging
import os


class Metadata:
    EXIF_KEYS = [
        ('Exif.Image.Model', 'human_value'),
        ('Exif.Photo.DateTimeOriginal', 'value'),
        ('Exif.Photo.ExposureTime', 'human_value'),
        ('Exif.Photo.FNumber', 'human_value'),
        ('Exif.Photo.ISOSpeedRatings', 'human_value'),
        ('Exif.Photo.FocalLength', 'human_value'),
    ]  # Add additional keys we'd like to show

    def __init__(self):
        self.cache = {}

    def clear_cache(self):
        self.cache.clear()

    def get(self, filename):
        meta = self.cache.get(filename)

        # check cache
        if meta:
            return meta

        # try to read actual metadata
        full_meta = self.get_full(filename)
        if full_meta:
            return dict(self.cache.get(filename), full_meta=full_meta)

        # no metadata, fallback to simplest default case
        w, h = imaging.get_size(filename)
        stat = os.stat(filename)
        meta = {
            'filename': os.path.basename(filename),
            'needs_orientation': False,
            'needs_rotation': False,
            'width': w,
            'height': h,
            'orientation': None,
            'file_date': stat.st_mtime,
            'file_size': stat.st_size,
            'exif': {},
        }

        self.cache[filename] = meta
        return meta

    def get_cached(self, filename):
        return self.cache.get(filename, None)

    def get_full(self, filename):
        try:
            from pyexiv2 import ImageMetadata
            meta = ImageMetadata(filename)
            meta.read()

            exif = {}
            for key, accessor in Metadata.EXIF_KEYS:
                v = meta.get(key, None)
                if v:
                    exif[key] = getattr(v, accessor)

            # also cache the most important part
            needs_rotation = imaging.needs_rotation(meta)
            stat = os.stat(filename)
            self.cache[filename] = {
                'filename': os.path.basename(filename),
                'needs_orientation': imaging.needs_orientation(meta),
                'needs_rotation': needs_rotation,
                'width': meta.dimensions[0 if not needs_rotation else 1],
                'height': meta.dimensions[1 if not needs_rotation else 0],
                'orientation': meta['Exif.Image.Orientation'].value if 'Exif.Image.Orientation' in meta else None,
                'file_date': stat.st_mtime,
                'file_size': stat.st_size,
                'exif': exif,
            }

            return meta
        except Exception:
            import logging
            logging.warning("Could not parse meta-info for %s" % filename)
            return None


metadata = Metadata()
