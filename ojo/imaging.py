# coding=utf-8
from gi.repository import GdkPixbuf


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


