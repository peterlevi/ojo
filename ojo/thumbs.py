import logging
import os
import time

from config import options
from imaging import is_image, get_pil, get_pixbuf


class Thumbs:
    def __init__(self, ojo):
        self.ojo = ojo

    def reset_queues(self):
        with self.thumbs_queue_lock:
            self.thumbs_queue = []
            self.prepared_thumbs = set()

    def get_thumbs_cache_dir(self, height):
        return os.path.expanduser('~/.config/ojo/cache/%d' % height)

    def start_thumbnail_thread(self):
        import threading
        self.prepared_thumbs = set()
        self.thumbs_queue = []
        self.thumbs_queue_event = threading.Event()
        self.thumbs_queue_lock = threading.Lock()

        def _thumbs_thread():
            # delay the start to give the caching thread some time to prepare next images
            start_time = time.time()
            while self.ojo.mode == "image" and time.time() - start_time < 2:
                time.sleep(0.1)

            cache_dir = self.get_thumbs_cache_dir(options['thumb_height'])
            try:
                if not os.path.exists(cache_dir):
                    os.makedirs(cache_dir)
            except Exception:
                logging.exception("Could not create cache dir %s" % cache_dir)

            logging.info("Starting thumbs thread")
            while True:
                self.thumbs_queue_event.wait()
                while self.thumbs_queue:
                    # pause thumbnailing while the user is actively cycling images:
                    while time.time() - self.ojo.last_action_time < 2 and self.ojo.mode == "image":
                        time.sleep(0.2)
                    time.sleep(0.05)
                    try:
                        with self.thumbs_queue_lock:
                            if not self.thumbs_queue:
                                continue
                            img = self.thumbs_queue[0]
                            self.thumbs_queue.remove(img)
                        if not img in self.prepared_thumbs:
                            logging.debug("Thumbs thread loads file " + img)
                            self.ojo.add_thumb(img)
                    except Exception:
                        logging.exception("Exception in thumbs thread:")
                self.thumbs_queue_event.clear()

        thumbs_thread = threading.Thread(target=_thumbs_thread)
        thumbs_thread.daemon = True
        thumbs_thread.start()

    def priority_thumbs(self, files):
        logging.debug("Priority thumbs: " + str(files))
        new_thumbs_queue = [f for f in files if not f in self.prepared_thumbs] + \
                           [f for f in self.thumbs_queue if not f in files and not f in self.prepared_thumbs]
        new_thumbs_queue = filter(is_image, new_thumbs_queue)
        with self.thumbs_queue_lock:
            self.thumbs_queue = new_thumbs_queue
            self.thumbs_queue_event.set()

    def get_cached_thumbnail_path(self, filename, force_cache=False):
        # Use gifs directly - webkit will handle transparency, animation, etc.
        if not force_cache and os.path.splitext(filename)[1].lower() == '.gif':
            return filename

        import hashlib
        # we append modification time to ensure we're not using outdated cached images
        mtime = os.path.getmtime(filename)
        hash = hashlib.md5(filename + str(mtime)).hexdigest()
        folder = os.path.dirname(filename)
        if folder.startswith(os.sep):
            folder = folder[1:]
        return os.path.join(
            self.get_thumbs_cache_dir(options['thumb_height']),  # cache folder root
            folder,  # mirror the original directory structure
            os.path.basename(filename) + '_' + hash + '.jpg')  # filename + hash of the name & time

    def prepare_thumbnail(self, filename, width, height, on_done, on_error):
        cached = self.get_cached_thumbnail_path(filename)

        def use_pil():
            pil = get_pil(filename, width, height)
            format = {".gif": "GIF", ".png": "PNG", ".svg": "PNG"}.get(ext, 'JPEG')
            for format in (format, 'JPEG', 'GIF', 'PNG'):
                try:
                    pil.save(cached, format)
                    if os.path.getsize(cached):
                        self.prepared_thumbs.add(filename)
                        break
                except Exception, e:
                    logging.exception(
                        'Could not save thumbnail in format %s:' % format)

        def use_pixbuf():
            th = options['thumb_height']
            pixbuf = get_pixbuf(filename, 3*th, th)
            pixbuf.savev(cached, 'png', [], [])

        if not os.path.exists(cached):
            cache_dir = os.path.dirname(cached)
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
            ext = os.path.splitext(filename)[1].lower()
            if not ext in ('.gif', '.png', '.svg', '.xpm'):
                try:
                    use_pil()
                except Exception:
                    use_pixbuf()
            else:
                try:
                    use_pixbuf()
                except Exception:
                    use_pil()

        if not os.path.isfile(cached) or not os.path.getsize(cached):
            on_error('Could not create thumbnail')

        on_done(cached)

    def clear_thumbnails(self, folder):
        images = filter(
            is_image,
            map(lambda f: os.path.join(folder, f), os.listdir(folder)))
        for img in images:
            cached = self.get_cached_thumbnail_path(img, True)
            if os.path.isfile(cached) and \
                    cached.startswith(self.get_thumbs_cache_dir(options['thumb_height']) + os.sep):
                try:
                    os.unlink(cached)
                except IOError:
                    logging.exception("Could not delete %s" % cached)
