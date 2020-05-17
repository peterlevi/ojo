# coding=utf-8
import io
import logging
import os
import random
import tempfile
import threading

import gi
from gi.repository import GdkPixbuf, Gio, GObject
from PIL import Image

from ojo import config
from ojo.exiftool import ExifTool
from ojo.metadata import metadata
from ojo.util import ext

gi.require_version("GdkPixbuf", "2.0")

# supported by PIL, as per http://infohost.nmt.edu/tcc/help/pubs/pil/formats.html:
NON_RAW_FORMATS = {
    ".bmp",
    ".dib",
    ".dcx",
    ".eps",
    ".ps",
    ".gif",
    ".im",
    ".jpg",
    ".jpe",
    ".jpeg",
    ".pcd",
    ".pcx",
    ".png",
    ".pbm",
    ".pgm",
    ".ppm",
    ".psd",
    ".tif",
    ".tiff",
    ".xbm",
    ".xpm",
}

# RAW formats, as per https://en.wikipedia.org/wiki/Raw_image_format#Annotated_list_of_file_extensions,
# we rely on pyexiv2 previews for these:
RAW_FORMATS = {
    ".3fr",
    ".ari",
    ".arw",
    ".bay",
    ".braw",
    ".crw",
    ".cr2",
    ".cr3",
    ".cap",
    ".data",
    ".dcs",
    ".dcr",
    ".dng",
    ".drf",
    ".eip",
    ".erf",
    ".fff",
    ".gpr",
    ".iiq",
    ".k25",
    ".kdc",
    ".mdc",
    ".mef",
    ".mos",
    ".mrw",
    ".nef",
    ".nrw",
    ".obm",
    ".orf",
    ".pef",
    ".ptx",
    ".pxn",
    ".r3d",
    ".raf",
    ".raw",
    ".rwl",
    ".rw2",
    ".rwz",
    ".sr2",
    ".srf",
    ".srw",
    ".tif",
    ".x3f",
}


exiftool = None
_lock = threading.Lock()


# ExifTool is not Thread-safe, so we start one for every subprocess that requires it
def start_exiftool_process(show_version=False):
    logging.debug('Starting exiftool in process %d', os.getpid())
    global exiftool
    global _lock
    with _lock:
        exiftool = ExifTool(executable=config.get_exiftool_path())
        exiftool.start(show_version)


def stop_exiftool_process():
    global exiftool
    global _lock
    with _lock:
        if exiftool:
            exiftool.terminate()
            exiftool = None


def get_optimal_preview(filename, to_folder, width=None, height=None):
    exiftool.extract_previews(filename, to_folder)

    # filter to just jpeg and png previews (tiffs are sometimes present too)
    previews = [
        {"path": os.path.join(to_folder, name)}
        for name in os.listdir(to_folder)
        if name.endswith((".jpg", ".jpeg", ".png"))
    ]

    for p in previews:
        w, h = get_size_via_pixbuf(p["path"])
        p["width"] = w
        p["height"] = h

    if width is None or height is None:
        # if no resizing required - use the biggest image
        preview = max(previews, key=lambda p: p["width"])
    else:
        # else use the smallest image that is bigger than the desired size
        bigger = [p for p in previews if p["width"] >= width and p["height"] >= height]
        if bigger:
            preview = min(bigger, key=lambda p: p["width"])
        else:
            preview = max(previews, key=lambda p: p["width"])

    return preview["path"]


def get_pil(filename, width=None, height=None, fallback_to_preview=False):
    meta = metadata.get(filename)
    orientation = meta["orientation"]

    try:
        pil_image = Image.open(filename)
    except IOError:
        if not fallback_to_preview:
            raise
        with tempfile.TemporaryDirectory(prefix="ojo") as to_folder:
            optimal_preview = get_optimal_preview(filename, to_folder, width, height)
            pil_image = Image.open(optimal_preview)

    if width is not None:
        # thumbnail, than auto-rotate (so we work rotate a smaller image), than re-thumbnail
        # because the rotation might chnage width/height
        pil_image.thumbnail((max(width, height), max(width, height)), Image.ANTIALIAS)
        pil_image = auto_rotate_pil(orientation, pil_image)
        if pil_image.size[0] > width or pil_image.size[1] > height:
            pil_image.thumbnail((width, height), Image.ANTIALIAS)
    else:
        pil_image = auto_rotate_pil(orientation, pil_image)

    return pil_image


def get_pixbuf(filename, width=None, height=None):
    meta = metadata.get(filename)
    orientation = meta["orientation"]
    image_width, image_height = meta["width"], meta["height"]

    def _from_preview():
        try:
            with tempfile.TemporaryDirectory(prefix="ojo") as to_folder:
                optimal_preview = get_optimal_preview(filename, to_folder, width, height)
                pixbuf = pixbuf_from_file(optimal_preview)
            pixbuf = auto_rotate_pixbuf(orientation, pixbuf)
            logging.debug("Loaded from preview")
            return pixbuf
        except Exception:
            return None  # below we'll use another method

    def _from_gdk_pixbuf():
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(filename)
            pixbuf = auto_rotate_pixbuf(orientation, pixbuf)
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
        raise Exception("Could not load %s" % filename)

    if width is not None and (width < image_width or height < image_height):
        # scale it
        if float(width) / height < float(image_width) / image_height:
            pixbuf = pixbuf.scale_simple(
                width, int(float(width) * image_height / image_width), GdkPixbuf.InterpType.BILINEAR
            )
        else:
            pixbuf = pixbuf.scale_simple(
                int(float(height) * image_width / image_height),
                height,
                GdkPixbuf.InterpType.BILINEAR,
            )

    return pixbuf


def thumbnail(filename, thumb_path, width, height):
    _, tmp_thumb_path = tempfile.mkstemp(prefix="ojo_thumbnail_")

    def use_pil():
        pil = get_pil(filename, width, height)
        try:
            pil.save(tmp_thumb_path, "JPEG")
        except Exception:
            logging.exception("Could not save thumbnail in format %s:" % format)

    def use_pixbuf():
        pixbuf = get_pixbuf(filename, width, height)
        pixbuf.savev(tmp_thumb_path, "png", [], [])

    cache_dir = os.path.dirname(thumb_path)
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    if ext(filename) in {".gif", ".png", ".svg", ".xpm"}.union(RAW_FORMATS):
        try:
            use_pixbuf()
        except Exception:
            use_pil()
    else:
        try:
            use_pil()
        except Exception:
            use_pixbuf()

    os.rename(tmp_thumb_path, thumb_path)

    return filename, thumb_path


def folder_thumb_height(thumb_height):
    return int(thumb_height / 4)


def folder_thumbnail(folder, thumb_path, width, height, kill_event):
    """
    Create the cache folder for the thumb
    :param folder: folder path
    :param thumb_path: thumb path to save thumb to
    :param width: max width of a single image thumbnail (standard non-folder one)
    :param height: height of a single image thumbnail (standard non-folder one, as set in options)
    :param kill_event: multiprocessing.Event that will be set when app is exiting
    :return: (folder, thumb path), or (folder, None) if folder contains no images
    """
    cache_dir = os.path.dirname(thumb_path)
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    images = list_images(folder)

    if not images:
        return folder, None

    from ojo.thumbs import Thumbs

    random.seed(1234)
    random.shuffle(images)

    MAX_WIDTH = 400
    MAX_IMAGES = 20
    THUMB_HEIGHT = folder_thumb_height(height)
    MARGIN = 8

    image = Image.new("RGBA", (MAX_WIDTH + 100, THUMB_HEIGHT))

    total_width = 0
    for f in images[:MAX_IMAGES]:
        if kill_event.is_set():
            return folder, None

        try:
            fthumb = Thumbs.get_cached_thumbnail_path(f, height)
            if not os.path.exists(fthumb):
                _, fthumb = thumbnail(f, fthumb, 3 * height, height)
            fthumb_image = get_pil(fthumb, MAX_WIDTH, THUMB_HEIGHT)
            w, h = fthumb_image.size
            if total_width + MARGIN + w > MAX_WIDTH + 100:
                break
            image.paste(fthumb_image, (total_width, 0, total_width + w, h))
            total_width += MARGIN + w
        except Exception:
            logging.exception("folder_thumbnail: Failed thumbing %s" % f)

    if total_width > 0:
        image = image.crop((0, 0, min(MAX_WIDTH, total_width), THUMB_HEIGHT))
        _, tmp_thumb_path = tempfile.mkstemp(prefix="ojo_folder_thumbnail_")
        image.save(tmp_thumb_path, "PNG")
        os.rename(tmp_thumb_path, thumb_path)

    return folder, thumb_path


def auto_rotate_pil(orientation, im):
    """
    From exiftool documentation

    1 = Horizontal (normal)
    2 = Mirror horizontal
    3 = Rotate 180
    4 = Mirror vertical
    5 = Mirror horizontal and rotate 270 CW
    6 = Rotate 90 CW
    7 = Mirror horizontal and rotate 90 CW
    8 = Rotate 270 CW
    """
    # We rotate regarding to the EXIF orientation information
    if orientation is None:
        result = im
    elif orientation in (1, "Horizontal (normal)"):
        result = im
    elif orientation in (2, "Mirror horizontal"):
        result = im.transpose(Image.FLIP_LEFT_RIGHT)
    elif orientation in (3, "Rotate 180"):
        result = im.transpose(Image.ROTATE_180)
    elif orientation in (4, "Mirror vertical"):
        result = im.transpose(Image.FLIP_TOP_BOTTOM)
    elif orientation in (5, "Mirror horizontal and rotate 270 CW"):
        result = im.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_90)
    elif orientation in (6, "Rotate 90 CW"):
        result = im.transpose(Image.ROTATE_270)
    elif orientation in (7, "Mirror horizontal and rotate 90 CW"):
        result = im.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_270)
    elif orientation in (8, "Rotate 270 CW"):
        result = im.transpose(Image.ROTATE_90)
    else:
        result = im

    return result


def auto_rotate_pixbuf(orientation, im):
    """
    From exiftool documentation

    1 = Horizontal (normal)
    2 = Mirror horizontal
    3 = Rotate 180
    4 = Mirror vertical
    5 = Mirror horizontal and rotate 270 CW
    6 = Rotate 90 CW
    7 = Mirror horizontal and rotate 90 CW
    8 = Rotate 270 CW
    """
    # prefer the orientation specified in the pixbuf, if any
    try:
        orientation = int(im.get_options()["orientation"])
    except:
        pass

    # We rotate regarding to the EXIF orientation information
    if orientation is None:
        result = im
    elif orientation in (1, "Horizontal (normal)"):
        result = im
    elif orientation in (2, "Mirror horizontal"):
        result = im.flip(True)
    elif orientation in (3, "Rotate 180"):
        result = im.rotate_simple(180)
    elif orientation in (4, "Mirror vertical"):
        result = im.flip(False)
    elif orientation in (5, "Mirror horizontal and rotate 270 CW"):
        result = im.flip(True).rotate_simple(90)
    elif orientation in (6, "Rotate 90 CW"):
        result = im.rotate_simple(270)
    elif orientation in (7, "Mirror horizontal and rotate 90 CW"):
        result = im.flip(True).rotate_simple(270)
    elif orientation in (8, "Rotate 270 CW"):
        result = im.rotate_simple(90)
    else:
        result = im

    return result


def pil_to_pixbuf(pil_image):
    if pil_image.mode != "RGB":  # Fix IOError: cannot write mode P as PPM
        pil_image = pil_image.convert("RGB")
    buff = io.StringIO()
    pil_image.save(buff, "ppm")
    contents = buff.getvalue()
    buff.close()
    loader = GdkPixbuf.PixbufLoader()
    loader.write(contents)
    pixbuf = loader.get_pixbuf()
    loader.close()
    return pixbuf


def pil_to_base64(pil_image):
    output = io.StringIO()
    pil_image.save(output, "PNG")
    contents = output.getvalue().encode("base64")
    output.close()
    return contents.replace("\n", "")


def pixbuf_from_data(data):
    input_str = Gio.MemoryInputStream.new_from_data(data, None)
    return GdkPixbuf.Pixbuf.new_from_stream(input_str, None)


def pixbuf_from_file(filename):
    return GdkPixbuf.Pixbuf.new_from_file(filename)


def pixbuf_to_b64(pixbuf):
    return pixbuf.save_to_bufferv("png", [], [])[1].encode("base64").replace("\n", "")


def get_supported_image_extensions():
    fn = get_supported_image_extensions
    if not hasattr(fn, "image_formats"):
        fn.image_formats = NON_RAW_FORMATS.union(RAW_FORMATS)

        # supported by GdkPixbuf:
        for l in [f.get_extensions() for f in GdkPixbuf.Pixbuf.get_formats()]:
            fn.image_formats = fn.image_formats.union(['.' + e.lower() for e in l])

    return fn.image_formats


def get_size_via_pixbuf(image):
    format, image_width, image_height = GdkPixbuf.Pixbuf.get_file_info(image)
    if format:
        return image_width, image_height
    else:
        try:
            im = Image.open(image)
            return im.size
        except:
            raise Exception("Not an image or unsupported image format")


def is_image(filename):
    """Decide if something might be a supported image based on extension"""
    try:
        return os.path.isfile(filename) and ext(filename) in get_supported_image_extensions()
    except Exception:
        return False


def list_images(folder):
    return list(filter(is_image, [os.path.join(folder, f) for f in os.listdir(folder)]))
