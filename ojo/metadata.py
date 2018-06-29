import imaging


class Metadata:
    def __init__(self):
        self.cache = {}

    def clear_cache(self):
        self.cache.clear()

    def get(self, filename):
        meta = self.cache.get(filename)
        if meta:
            return meta

        full_meta = self.get_full(filename)
        if full_meta:
            return dict(self.cache.get(filename), full_meta=full_meta)

        return None

    def get_cached(self, filename):
        return self.cache.get(filename, None)

    def get_full(self, filename):
        try:
            from pyexiv2 import ImageMetadata
            meta = ImageMetadata(filename)
            meta.read()

            # also cache the most important part
            self.cache[filename] = {
                'needs_orientation': imaging.needs_orientation(meta),
                'needs_rotation': imaging.needs_rotation(meta),
                'width': meta.dimensions[0],
                'height': meta.dimensions[1],
                'orientation': meta['Exif.Image.Orientation'].value if 'Exif.Image.Orientation' in meta else None
            }

            return meta
        except Exception:
            import logging
            logging.exception("Could not parse meta-info for %s" % filename)
            return None


metadata = Metadata()
