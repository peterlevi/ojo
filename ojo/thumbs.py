import hashlib
import logging
import multiprocessing
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from ojo import imaging
from ojo.config import options
from ojo.util import _bytes

POOL_SIZE = max(1, multiprocessing.cpu_count() - 1)


def _safe_thumbnail(filename, cached, width, height, kill_event):
    try:
        if kill_event.is_set():
            return filename, cached

        if os.path.exists(cached):
            return filename, cached

        if os.path.isfile(filename) and not imaging.is_image(filename):
            return filename, cached

        if os.path.isdir(filename):
            return imaging.folder_thumbnail(filename, cached, width, height, kill_event)
        else:
            return imaging.thumbnail(filename, cached, width, height)
    except:
        logging.exception("Error creating thumb for %s", filename)
        # caller will check whether the file was actually created
        return filename, cached


class Thumbs:
    def __init__(self, ojo):
        self.ojo = ojo
        self.pool = None
        self.killed = False
        self.lock = threading.Lock()

    @staticmethod
    def get_thumbs_cache_dir(height):
        return os.path.expanduser("~/.config/ojo/cache/%d" % height)

    @staticmethod
    def get_folderthumbs_cache_dir(height):
        return os.path.expanduser("~/.config/ojo/cache/folderthumbs_%d" % height)

    def reset_queues(self):
        self.queue = []

    def stop(self):
        self.killed = True
        with self.lock:
            self.queue = []
            self.kill_event.set()
            self.thumbs_event.set()
            if self.pool:
                logging.info("%s: Shutting down ThreaPoolExecutor...", self)
                self.pool.shutdown(wait=True)
                self.pool = None
                self.thread.join()
                logging.info("%s: Stopped", self)

    def init_pool(self):
        with self.lock:
            self.pool = ThreadPoolExecutor(max_workers=POOL_SIZE)

    def start(self, ojo):
        self.queue = []
        self.processing = set()
        self.pool = None
        self.kill_event = multiprocessing.Manager().Event()
        self.thumbs_event = threading.Event()

        def _thumbs_thread():
            # delay the start to give the caching thread some time to prepare next images
            start_time = time.time()
            while self.ojo.mode == "image" and time.time() - start_time < 2:
                if self.killed:
                    return
                time.sleep(0.1)

            self.init_pool()

            cache_dir = self.get_thumbs_cache_dir(options["thumb_height"])
            try:
                if not os.path.exists(cache_dir):
                    os.makedirs(cache_dir)
            except Exception:
                logging.exception("Could not create cache dir %s" % cache_dir)

            logging.info("Starting thumbs thread")

            while True:
                if self.killed:
                    return
                self.thumbs_event.wait(timeout=0.5)
                self.thumbs_event.clear()
                if self.killed:
                    return

                while self.queue:
                    if self.killed:
                        return

                    if len(self.processing) >= POOL_SIZE:
                        break

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

        from ojo.ojo import OjoThread

        self.thread = OjoThread(ojo=ojo, target=_thumbs_thread)
        if not self.killed:
            self.thread.start()

    def priority_thumbs(self, files):
        if self.killed:
            return
        pq = set(files)
        self.queue = files + [f for f in self.queue if f not in pq]
        self.thumbs_event.set()

    def enqueue(self, files):
        if self.killed:
            return
        self.queue = self.queue + [f for f in files if f not in self.queue]
        self.thumbs_event.set()

    @staticmethod
    def get_cached_thumbnail_path(filename, force_cache=False, thumb_height=None):
        # Use gifs directly - webkit will handle transparency, animation, etc.
        if not force_cache and os.path.splitext(filename)[1].lower() == ".gif":
            return filename

        if thumb_height is None:
            thumb_height = options["thumb_height"]

        # we append modification time to ensure we're not using outdated cached images
        mtime = os.path.getmtime(filename)
        hash = hashlib.md5(_bytes(filename + "{0:.2f}".format(mtime))).hexdigest()
        # we use .2 precision to keep the same behavior of getmtime as under Python 2
        folder = os.path.dirname(filename)
        if folder.startswith(os.sep):
            folder = folder[1:]
        return os.path.join(
            Thumbs.get_thumbs_cache_dir(thumb_height),  # cache folder root
            folder,  # mirror the original directory structure
            os.path.basename(filename) + "_" + hash + ".jpg",
        )  # filename + hash of the name & time

    @staticmethod
    def get_folder_thumbnail_path(folder):
        if not os.path.isdir(folder):
            raise Exception("Requested folder thumb for non-folder: " + folder)

        folder = os.path.abspath(folder)
        mtime = os.path.getmtime(folder)
        hash = hashlib.md5(_bytes(folder + "{0:.2f}".format(mtime))).hexdigest()

        parent = os.path.dirname(folder)
        if parent.startswith(os.sep):
            parent = parent[1:]

        return os.path.join(
            Thumbs.get_folderthumbs_cache_dir(
                options["thumb_height"]
            ),  # folderthumbs cache folder root
            parent,  # mirror the original directory structure
            os.path.basename(folder) + "_" + hash + ".png",
        )  # filename + hash of the name

    def on_thumb_ready(self, img, thumb_path):
        self.processing.remove(img)
        self.thumbs_event.set()
        if thumb_path:
            self.ojo.thumb_ready(img, thumb_path)

    def on_thumb_failed(self, img, thumb_path):
        self.processing.remove(img)
        self.thumbs_event.set()
        self.ojo.thumb_failed(img, thumb_path)

    def add_thumbnail(self, img):
        th = options["thumb_height"]
        self.prepare_thumbnail(img, 3 * th, th)

    def prepare_thumbnail(self, filename, width, height):
        self.processing.add(filename)

        is_folder = os.path.isdir(filename)
        cached = (
            self.get_folder_thumbnail_path(filename)
            if is_folder
            else self.get_cached_thumbnail_path(filename)
        )

        def _thumbnail_ready(future):
            filename, thumb_path = future.result()

            if thumb_path is None:
                # valid situation for folder thumbs
                self.on_thumb_ready(filename, None)
            elif not os.path.isfile(thumb_path) or not os.path.getsize(thumb_path):
                self.on_thumb_failed(filename, "Could not create thumbnail")
            else:
                self.on_thumb_ready(filename, thumb_path)

        if self.killed:
            return

        future = self.pool.submit(_safe_thumbnail, filename, cached, width, height, self.kill_event)
        future.add_done_callback(_thumbnail_ready)

    def clear_thumbnails(self, folder):
        for img in imaging.list_images(folder):
            if self.killed:
                return

            cached = self.get_cached_thumbnail_path(img, True)
            if os.path.isfile(cached) and cached.startswith(
                self.get_thumbs_cache_dir(options["thumb_height"]) + os.sep
            ):
                try:
                    os.unlink(cached)
                except IOError:
                    logging.exception("Could not delete %s" % cached)
