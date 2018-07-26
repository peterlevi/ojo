# coding=utf-8
import os
import logging
from gi.repository import Gio, GdkPixbuf, GObject

# supported by PIL, as per http://infohost.nmt.edu/tcc/help/pubs/pil/formats.html:
NON_RAW_FORMATS = {
    "bmp", "dib", "dcx", "eps", "ps", "gif", "im", "jpg", "jpe", "jpeg", "pcd", "pcx", "png", "pbm", "pgm", "ppm",
    "psd", "tif", "tiff", "xbm", "xpm"}

# RAW formats, as per https://en.wikipedia.org/wiki/Raw_image_format#Annotated_list_of_file_extensions,
# we rely on pyexiv2 previews for these:
RAW_FORMATS = {
    "3fr", "ari", "arw", "srf", "sr2", "bay", "crw", "cr2", "cap", "iiq", "eip", "dcs", "dcr", "drf", "k25",
    "kdc", "dng", "erf", "fff", "mef", "mos", "mrw", "nef", "nrw", "orf", "pef", "ptx", "pxn", "r3d", "raf",
    "raw", "rw2", "raw", "rwl", "dng", "rwz", "srw", "x3f"}


def get_pil(filename, width=None, height=None):
    from PIL import Image
    from metadata import metadata

    try:
        pil_image = Image.open(filename)
    except IOError:
        import cStringIO
        full_meta = metadata.get_full(filename)
        pil_image = Image.open(
            cStringIO.StringIO(full_meta.previews[-1].data))

    if width is not None:
        meta = metadata.get(filename)

        pil_image.thumbnail(
            (max(width, height), max(width, height)), Image.ANTIALIAS)

        try:
            pil_image = auto_rotate(meta['orientation'], pil_image)
        except Exception:
            logging.exception('Auto-rotation failed for %s' % filename)

        if pil_image.size[0] > width or pil_image.size[1] > height:
            pil_image.thumbnail((width, height), Image.ANTIALIAS)

    return pil_image


def get_pixbuf(filename, width=None, height=None):
    from metadata import metadata

    meta = metadata.get(filename)
    orientation = meta['orientation']
    image_width, image_height = meta['width'], meta['height']

    def _from_preview():
        try:
            full_meta = meta.get('full_meta',
                                 metadata.get_full(filename))
            preview = max(full_meta.previews, key=lambda p: p.dimensions[0]).data
            pixbuf = pixbuf_from_data(preview)
            logging.debug("Loaded from preview")
            return pixbuf
        except Exception, e:
            return None  # below we'll use another method

    def _from_gdk_pixbuf():
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(filename)
            logging.debug("Loaded directly")
            return pixbuf
        except GObject.GError:
            return None  # below we'll use another method

    def _from_pil():
        try:
            pixbuf = pil_to_pixbuf(get_pil(filename))
            logging.debug("Loaded with PIL")
            return pixbuf
        except:
            return None

    if ext(filename) in RAW_FORMATS:
        # raw file, prefer preview with max size
        pixbuf = _from_preview()
        if not pixbuf:
            pixbuf = _from_gdk_pixbuf()
    else:
        # ordinary image, prefer loading with GdkPixbuf directly
        # (previews here might be present, but wrong)
        pixbuf = _from_gdk_pixbuf()
        if not pixbuf:
            pixbuf = _from_preview()

    if not pixbuf:
        pixbuf = _from_pil()

    if not pixbuf:
        raise Exception('Could not load %s' % filename)

    pixbuf = auto_rotate_pixbuf(orientation, pixbuf)

    if width is not None and (width < image_width or height < image_height):
        # scale it
        if float(width) / height < float(image_width) / image_height:
            pixbuf = pixbuf.scale_simple(
                width,
                int(float(width) * image_height / image_width),
                GdkPixbuf.InterpType.BILINEAR)
        else:
            pixbuf = pixbuf.scale_simple(
                int(float(height) * image_width / image_height),
                height,
                GdkPixbuf.InterpType.BILINEAR)

    return pixbuf


def thumbnail(filename, thumb_path, width, height):
    def use_pil():
        pil = get_pil(filename, width, height)
        try:
            pil.save(thumb_path, 'JPEG')
        except Exception, e:
            logging.exception(
                'Could not save thumbnail in format %s:' % format)

    def use_pixbuf():
        pixbuf = get_pixbuf(filename, width, height)
        pixbuf.savev(thumb_path, 'png', [], [])

    cache_dir = os.path.dirname(thumb_path)
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ('.gif', '.png', '.svg', '.xpm'):
        try:
            use_pil()
        except Exception:
            use_pixbuf()
    else:
        try:
            use_pixbuf()
        except Exception:
            use_pil()

    return thumb_path


def needs_orientation(meta):
    return 'Exif.Image.Orientation' in meta.keys() and meta['Exif.Image.Orientation'].value != 1


def needs_rotation(meta):
    return 'Exif.Image.Orientation' in meta.keys() and meta['Exif.Image.Orientation'].value in (5, 6, 7, 8)


def auto_rotate(orientation, im):
    from PIL import Image
    # We rotate regarding to the EXIF orientation information
    if orientation is None:
        result = im
    elif orientation == 1:
        # Nothing
        result = im
    elif orientation == 2:
        # Vertical Mirror
        result = im.transpose(Image.FLIP_LEFT_RIGHT)
    elif orientation == 3:
        # Rotation 180°
        result = im.transpose(Image.ROTATE_180)
    elif orientation == 4:
        # Horizontal Mirror
        result = im.transpose(Image.FLIP_TOP_BOTTOM)
    elif orientation == 5:
        # Horizontal Mirror + Rotation 270°
        result = im.transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.ROTATE_270)
    elif orientation == 6:
        # Rotation 270°
        result = im.transpose(Image.ROTATE_270)
    elif orientation == 7:
        # Vertical Mirror + Rotation 270°
        result = im.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_270)
    elif orientation == 8:
        # Rotation 90°
        result = im.transpose(Image.ROTATE_90)
    else:
        result = im

    return result


def auto_rotate_pixbuf(orientation, im):
    # prefer the orientation specified in the pixbuf, if any
    try:
        orientation = int(im.get_options()['orientation'])
    except:
        pass

    # We rotate regarding to the EXIF orientation information
    if orientation is None:
        result = im
    elif orientation == 1:
        # Nothing
        result = im
    elif orientation == 2:
        # Vertical Mirror
        result = im.flip(True)
    elif orientation == 3:
        # Rotation 180°
        result = im.rotate_simple(180)
    elif orientation == 4:
        # Horizontal Mirror
        result = im.flip(False)
    elif orientation == 5:
        # Horizontal Mirror + Rotation 270°
        result = im.flip(False).rotate_simple(270)
    elif orientation == 6:
        # Rotation 270°
        result = im.rotate_simple(270)
    elif orientation == 7:
        # Vertical Mirror + Rotation 270°
        result = im.flip(True).rotate_simple(270)
    elif orientation == 8:
        # Rotation 90°
        result = im.rotate_simple(90)
    else:
        result = im

    return result

def pil_to_pixbuf(pil_image):
    import cStringIO
    if pil_image.mode != 'RGB':  # Fix IOError: cannot write mode P as PPM
        pil_image = pil_image.convert('RGB')
    buff = cStringIO.StringIO()
    pil_image.save(buff, 'ppm')
    contents = buff.getvalue()
    buff.close()
    loader = GdkPixbuf.PixbufLoader()
    loader.write(contents)
    pixbuf = loader.get_pixbuf()
    loader.close()
    return pixbuf


def pil_to_base64(pil_image):
    import cStringIO
    output = cStringIO.StringIO()
    pil_image.save(output, "PNG")
    contents = output.getvalue().encode("base64")
    output.close()
    return contents.replace('\n', '')


def pixbuf_from_data(data):
    input_str = Gio.MemoryInputStream.new_from_data(data, None)
    return GdkPixbuf.Pixbuf.new_from_stream(input_str, None)


def pixbuf_to_b64(pixbuf):
    return pixbuf.save_to_bufferv('png', [], [])[1].encode('base64').replace('\n', '')


def get_supported_image_extensions():
    fn = get_supported_image_extensions
    if not hasattr(fn, "image_formats"):
        fn.image_formats = NON_RAW_FORMATS.union(RAW_FORMATS)

        # supported by GdkPixbuf:
        for l in [f.get_extensions() for f in GdkPixbuf.Pixbuf.get_formats()]:
            fn.image_formats = fn.image_formats.union(map(lambda e: e.lower(), l))

    return fn.image_formats


def get_size(image):
    format, image_width, image_height = GdkPixbuf.Pixbuf.get_file_info(image)
    if format:
        return image_width, image_height
    else:
        try:
            from PIL import Image
            im = Image.open(image)
            return im.size
        except:
            raise Exception('Not an image or unsupported image format')


def ext(filename):
    return os.path.splitext(filename)[1].lower()[1:]


def is_image(filename):
    """Decide if something might be a supported image based on extension"""
    try:
        return os.path.isfile(filename) and ext(filename) in get_supported_image_extensions()
    except Exception:
        return False

