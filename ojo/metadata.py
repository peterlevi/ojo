from . import imaging
import os


# https://lazka.github.io/pgi-docs/#GExiv2-0.10/enums.html#GExiv2.Orientation
def needs_orientation(meta):
    return 'Exif.Image.Orientation' in meta and \
           int(meta.get_orientation()) not in (0, 1)


def needs_rotation(meta):
    return 'Exif.Image.Orientation' in meta and \
           int(meta.get_orientation()) in (5, 6, 7, 8)


class Metadata:
    EXIF_KEYS = [
        'Exif.Image.Model',
        'Exif.Photo.DateTimeOriginal',
        'Exif.Photo.ExposureTime',
        'Exif.Photo.FNumber',
        'Exif.Photo.ISOSpeedRatings',
        'Exif.Photo.FocalLength',
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
            from datetime import datetime
            from gi.repository import GExiv2
            meta = GExiv2.Metadata(path=filename)

            exif = {}
            for key in Metadata.EXIF_KEYS:
                v = meta.get_tag_interpreted_string(key)
                if v is not None:
                    if key == 'Exif.Photo.DateTimeOriginal':
                        v = datetime.strptime(v, '%Y:%m:%d %H:%M:%S')
                    exif[key] = v

            # also cache the most important part
            needs_rot = needs_rotation(meta)
            stat = os.stat(filename)
            self.cache[filename] = {
                'filename': os.path.basename(filename),
                'needs_orientation': needs_orientation(meta),
                'needs_rotation': needs_rot,
                'width': meta.get_pixel_width() if not needs_rot else meta.get_pixel_height(),
                'height': meta.get_pixel_height() if not needs_rot else meta.get_pixel_width(),
                'orientation': int(meta.get_orientation()) if 'Exif.Image.Orientation' in meta else None,
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
