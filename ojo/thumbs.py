import logging
import os
import time

from config import options
from imaging import is_image, thumbnail


def _safe_thumbnail(filename, cached, width, height):
    try:
        return thumbnail(filename, cached, width, height)
    except Exception:
        # caller will check whether the file was actually created
        return cached


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
        import multiprocessing
        import psutil
        self.prepared_thumbs = set()
        self.thumbs_queue = []
        self.thumbs_queue_event = threading.Event()
        self.thumbs_queue_lock = threading.Lock()

        self.pool = multiprocessing.Pool(processes=multiprocessing.cpu_count() - 1)

        # nice the thumbnailing pool as idle priority
        parent = psutil.Process()
        for child in parent.children():
            child.nice(10)  # lower than normal priority
            child.ionice(psutil.IOPRIO_CLASS_IDLE)

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
                        if img not in self.prepared_thumbs:
                            logging.debug("Thumbs thread loads file " + img)
                            self.add_thumb(img)
                    except Exception:
                        logging.exception("Exception in thumbs thread:")
                self.thumbs_queue_event.clear()

        thumbs_thread = threading.Thread(target=_thumbs_thread)
        thumbs_thread.daemon = True
        thumbs_thread.start()

    def priority_thumbs(self, files):
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

    def add_thumb(self, img):
        th = options['thumb_height']
        self.prepare_thumbnail(img, 3 * th, th,
                               on_done=self.ojo.thumb_ready,
                               on_error=self.ojo.thumb_failed)

    def prepare_thumbnail(self, filename, width, height, on_done, on_error):
        cached = self.get_cached_thumbnail_path(filename)

        def _thumbnail_ready(thumb_path):
            if not os.path.isfile(thumb_path) or not os.path.getsize(thumb_path):
                on_error(filename, 'Could not create thumbnail')
            else:
                self.prepared_thumbs.add(filename)
                on_done(filename, thumb_path)

        if not os.path.exists(cached):
            self.pool.apply_async(
                _safe_thumbnail,
                args=(filename, cached, width, height),
                callback=_thumbnail_ready)
        else:
            _thumbnail_ready(cached)

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
