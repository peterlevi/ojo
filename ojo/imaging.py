# coding=utf-8
from gi.repository import GdkPixbuf
import logging


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


