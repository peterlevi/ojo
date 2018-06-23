# coding=utf-8
import os
import logging
from gi.repository import GdkPixbuf


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
            pil_image = auto_rotate(meta['orientation'] if meta else None, pil_image)
        except Exception:
            logging.exception('Auto-rotation failed for %s' % filename)

        if pil_image.size[0] > width or pil_image.size[1] > height:
            pil_image.thumbnail((width, height), Image.ANTIALIAS)

    return pil_image


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
    from gi.repository import Gio
    input_str = Gio.MemoryInputStream.new_from_data(data, None)
    return GdkPixbuf.Pixbuf.new_from_stream(input_str, None)


def pixbuf_to_b64(pixbuf):
    return pixbuf.save_to_bufferv('png', [], [])[1].encode('base64').replace('\n', '')


def get_supported_image_extensions():
    fn = get_supported_image_extensions
    if not hasattr(fn, "image_formats"):
        # supported by PIL, as per http://infohost.nmt.edu/tcc/help/pubs/pil/formats.html:
        fn.image_formats = {"bmp", "dib", "dcx", "eps", "ps", "gif", "im", "jpg", "jpe", "jpeg", "pcd",
                              "pcx", "png", "pbm", "pgm", "ppm", "psd", "tif", "tiff", "xbm", "xpm"}

        # RAW formats, as per https://en.wikipedia.org/wiki/Raw_image_format#Annotated_list_of_file_extensions,
        # we rely on pyexiv2 previews for these:
        fn.image_formats = fn.image_formats.union(
            {"3fr", "ari", "arw", "srf", "sr2", "bay", "crw", "cr2", "cap", "iiq",
             "eip", "dcs", "dcr", "drf", "k25", "kdc", "dng", "erf", "fff", "mef", "mos", "mrw",
             "nef", "nrw", "orf", "pef", "ptx", "pxn", "r3d", "raf", "raw", "rw2", "raw", "rwl",
             "dng", "rwz", "srw", "x3f"})

        # supported by GdkPixbuf:
        for l in [f.get_extensions() for f in GdkPixbuf.Pixbuf.get_formats()]:
            fn.image_formats = fn.image_formats.union(map(lambda e: e.lower(), l))

    return fn.image_formats


def is_image(filename):
    """Decide if something might be a supported image based on extension"""
    try:
        return os.path.isfile(filename) and \
               os.path.splitext(filename)[1].lower()[1:] in \
               get_supported_image_extensions()
    except Exception:
        return False

