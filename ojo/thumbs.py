import logging
import os
import time

from .config import options
from .imaging import is_image, thumbnail


def _safe_thumbnail(filename, cached, width, height):
    try:
        if os.path.exists(cached) or not is_image(filename):
            return cached
        return thumbnail(filename, cached, width, height)
    except:
        # caller will check whether the file was actually created
        return cached


class Thumbs:
    def __init__(self, ojo):
        self.ojo = ojo

    def get_thumbs_cache_dir(self, height):
        return os.path.expanduser('~/.config/ojo/cache/%d' % height)

    def reset_queues(self):
        self.queue = []

    def stop(self):
        self.killed = True
        self.thumbs_event.set()
        self.pool.close()
        self.pool.join()
        self.thread.join()

    def start(self):
        import threading
        import multiprocessing
        self.pool = multiprocessing.Pool(processes=max(1, multiprocessing.cpu_count() - 1))

        self.killed = False
        self.thumbs_event = threading.Event()
        self.reset_queues()

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
                self.thumbs_event.wait()
                self.thumbs_event.clear()
                if self.killed:
                    return

                while self.queue:
                    if self.killed:
                        return

                    # pause thumbnailing while the user is actively cycling images:
                    while time.time() - self.ojo.last_action_time < 1 and self.ojo.mode == "image":
                        if self.killed:
                            return
                        time.sleep(0.2)

                    # make the cycle less tight
                    time.sleep(0.05)

                    try:
                        img = self.queue.pop(0)
                        self.add_thumbnail(img)
                    except IndexError:
                        # caused by queue being modified, ignore
                        pass
                    except Exception:
                        logging.exception("Exception in thumbs thread:")

        self.thread = threading.Thread(target=_thumbs_thread)
        self.thread.daemon = True
        self.thread.start()

    def priority_thumbs(self, files):
        pq = set(files)
        self.queue = files + [f for f in self.queue if f not in pq]
        self.thumbs_event.set()

    def get_cached_thumbnail_path(self, filename, force_cache=False):
        # Use gifs directly - webkit will handle transparency, animation, etc.
        if not force_cache and os.path.splitext(filename)[1].lower() == '.gif':
            return filename

        import hashlib
        from .util import _bytes
        # we append modification time to ensure we're not using outdated cached images
        mtime = os.path.getmtime(filename)
        hash = hashlib.md5(_bytes(filename + '{0:.2f}'.format(mtime))).hexdigest()
        # we use .2 precision to keep the same behavior of getmtime as under Python 2
        folder = os.path.dirname(filename)
        if folder.startswith(os.sep):
            folder = folder[1:]
        return os.path.join(
            self.get_thumbs_cache_dir(options['thumb_height']),  # cache folder root
            folder,  # mirror the original directory structure
            os.path.basename(filename) + '_' + hash + '.jpg')  # filename + hash of the name & time

    def add_thumbnail(self, img):
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
                on_done(filename, thumb_path)

        if self.killed:
            return

        self.pool.apply_async(
            _safe_thumbnail,
            args=(filename, cached, width, height),
            callback=_thumbnail_ready)

    def clear_thumbnails(self, folder):
        images = list(filter(
            is_image,
            [os.path.join(folder, f) for f in os.listdir(folder)]))

        for img in images:

            if self.killed:
                return

            cached = self.get_cached_thumbnail_path(img, True)
            if os.path.isfile(cached) and \
                    cached.startswith(self.get_thumbs_cache_dir(options['thumb_height']) + os.sep):
                try:
                    os.unlink(cached)
                except IOError:
                    logging.exception("Could not delete %s" % cached)
