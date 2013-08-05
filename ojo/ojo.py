#!/usr/bin/python
# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
### BEGIN LICENSE
# Copyright (C) 2013 Peter Levi <peterlevi@peterlevi.com>
# This program is free software: you can redistribute it and/or modify it 
# under the terms of the GNU General Public License version 3, as published 
# by the Free Software Foundation.
# 
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranties of 
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR 
# PURPOSE.  See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along 
# with this program.  If not, see <http://www.gnu.org/licenses/>.
### END LICENSE


# We import here only the things necessary to start and show an image.
# The rest are imported lazily so they do not slow startup
from gi.repository import Gtk, Gdk, GdkPixbuf, GObject
import os
import sys
import time
import util
import logging
import ojoconfig
import optparse

import gettext
from gettext import gettext as _
gettext.textdomain('ojo')

LEVELS = (logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG)


killed = False
def kill(*args):
    global killed
    killed = True


class Ojo():
    def parse_command_line(self):
        # Support for command line options.
        parser = optparse.OptionParser(version="%%prog %s" % ojoconfig.__version__, usage=(_("ojo [options]")))
        parser.add_option('-d', '--debug', dest='debug_mode', action='store_true',
                          help=_('Print the maximum debugging info (implies -vv)'))
        parser.add_option('-v', '--verbose', dest='logging_level', action='count',
                          help=_('set error_level output to warning, info, and then debug'))
        parser.set_defaults(logging_level=0)
        (self.command_options, self.command_args) = parser.parse_args()

    def setup_logging(self):
        # set the verbosity
        if self.command_options.debug_mode:
            self.command_options.logging_level = 3
        logging.basicConfig(level=LEVELS[self.command_options.logging_level],
                            format='%(asctime)s %(levelname)s %(message)s')

    def __init__(self):
        self.parse_command_line()
        self.setup_logging()

        if len(self.command_args) >= 1 and os.path.exists(self.command_args[0]):
            path = os.path.realpath(self.command_args[0])
        else:
            path = os.path.expanduser('~/Pictures')
        logging.info("Started with: " + path)

        self.window = Gtk.Window(Gtk.WindowType.TOPLEVEL)

        self.window.set_position(Gtk.WindowPosition.CENTER)

        self.visual = self.window.get_screen().get_rgba_visual()
        if self.visual and self.window.get_screen().is_composited():
            self.window.set_visual(self.visual)

        self.scroll_window = Gtk.ScrolledWindow()
        self.image = Gtk.Image()
        self.image.set_visible(True)
        self.scroll_window.add_with_viewport(self.image)
        self.make_transparent(self.scroll_window)
        self.make_transparent(self.scroll_window.get_child())
        self.scroll_window.set_visible(True)

        self.box = Gtk.VBox()
        self.box.set_visible(True)
        self.box.add(self.scroll_window)
        self.window.add(self.box)

        self.window.set_events(
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.SCROLL_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK)

        self.mousedown_zoomed = False
        self.mousedown_panning = False

        self.load_options()

        self.window.set_decorated(self.options['decorated'])
        if self.options['maximized']:
            self.window.maximize()

        self.meta_cache = {}
        self.pix_cache = {False: {}, True: {}} # keyed by "zoomed" property
        self.current_preparing = None
        self.manually_resized = False

        self.set_zoom(False, 0.5, 0.5)
        self.mode = 'image' if os.path.isfile(path) else 'folder'
        self.last_action_time = 0
        self.last_folder_change_time = time.time()
        self.shown = None
        self.toggle_fullscreen(self.options['fullscreen'], first_run=True)
        if self.options['fullscreen']:
            self.window.resize(*self.get_recommended_size())

        if os.path.isfile(path):
            self.last_automatic_resize = time.time()
            self.show(path, quick=True)
            GObject.timeout_add(500, self.after_quick_start)
        else:
            if not path.endswith('/'):
                path += '/'
            self.selected = path
            self.after_quick_start()
            self.set_mode('folder')
            self.selected = self.images[0] if self.images else path
            self.last_automatic_resize = time.time()
            self.window.resize(*self.get_recommended_size())

        self.window.set_visible(True)

        GObject.threads_init()
        Gdk.threads_init()
        Gdk.threads_enter()
        Gtk.main()
        Gdk.threads_leave()

    def js(self, command):
        logging.debug('js(%s)' % command)
        if hasattr(self, "web_view_loaded"):
            GObject.idle_add(lambda: self.web_view.execute_script(command))
        else:
            GObject.timeout_add(100, lambda: self.js(command))

    def select_in_browser(self, path):
        self.js("select('%s')" % (path if self.is_command(path) else util.path2url(path)))

    def update_zoom_scrolling(self):
        if self.zoom:
            if not self.zoom_x_percent is None:
                ha = self.scroll_window.get_hadjustment()
                ha.set_value(self.zoom_x_percent * (ha.get_upper() - ha.get_page_size() - ha.get_lower()))
                self.zoom_x_percent = None
            if not self.zoom_y_percent is None:
                va = self.scroll_window.get_vadjustment()
                va.set_value(self.zoom_y_percent * (va.get_upper() - va.get_page_size() - va.get_lower()))
                self.zoom_y_percent = None
            self.scroll_h = self.scroll_window.get_hadjustment().get_value()
            self.scroll_v = self.scroll_window.get_vadjustment().get_value()

    def show(self, filename=None, quick=False):
        filename = filename or self.selected
        logging.info("Showing " + filename)

        if not quick and self.is_command(filename):
            self.on_command(self.selected[self.selected.index(':') + 1:])
        elif os.path.isdir(filename):
            self.change_to_folder(filename)
        else:
            self.register_action()
            self.shown = filename
            self.selected = self.shown
            self.window.set_title(self.shown)
            self.refresh_image()

            if not quick:
                self.update_cursor()
                self.select_in_browser(self.shown)
                self.cache_around()

    def refresh_image(self):
        if self.shown:
            self.pixbuf = self.get_pixbuf(self.shown)
            self.increase_size()
            if os.path.splitext(self.shown)[1].lower() in ('.gif', '.mng', '.png'):
                anim = GdkPixbuf.PixbufAnimation.new_from_file(self.shown)
                if anim.is_static_image():
                    self.image.set_from_pixbuf(self.pixbuf)
                else:
                    self.image.set_from_animation(anim)
            else:
                self.image.set_from_pixbuf(self.pixbuf)
            self.box.set_visible(True)

    def get_supported_image_extensions(self):
        if not hasattr(self, "image_formats"):
            # supported by PIL, as per http://infohost.nmt.edu/tcc/help/pubs/pil/formats.html:
            self.image_formats = {"bmp", "dib", "dcx", "eps", "ps", "gif", "im", "jpg", "jpe", "jpeg", "pcd",
                                  "pcx", "png", "pbm", "pgm", "ppm", "psd", "tif", "tiff", "xbm", "xpm"}

            # RAW formats, as per https://en.wikipedia.org/wiki/Raw_image_format#Annotated_list_of_file_extensions,
            # we rely on pyexiv2 previews for these:
            self.image_formats = self.image_formats.union(
                    {"3fr", "ari", "arw", "srf", "sr2", "bay", "crw", "cr2", "cap", "iiq",
                     "eip", "dcs", "dcr", "drf", "k25", "kdc", "dng", "erf", "fff", "mef", "mos", "mrw",
                     "nef", "nrw", "orf", "pef", "ptx", "pxn", "r3d", "raf", "raw", "rw2", "raw", "rwl",
                     "dng", "rwz", "srw", "x3f"})

            # supported by GdkPixbuf:
            for l in [f.get_extensions() for f in GdkPixbuf.Pixbuf.get_formats()]:
                self.image_formats = self.image_formats.union(map(lambda e: e.lower(), l))

        return self.image_formats

    def is_image(self, filename):
        """Decide if something might be a supported image based on extension"""
        try:
            return os.path.isfile(filename) and \
                   os.path.splitext(filename)[1].lower()[1:] in self.get_supported_image_extensions()
        except Exception:
            return False

    def get_image_list(self):
        images = filter(self.is_image, map(lambda f: os.path.join(self.folder, f), os.listdir(self.folder)))
        if not self.options['show_hidden']:
            images = filter(lambda f: not os.path.basename(f).startswith('.'), images)

        if self.options['sort_by'] == 'name':
            key = lambda f: os.path.basename(f).lower()
        elif self.options['sort_by'] == 'date':
            key = lambda f: os.stat(f).st_mtime
        elif self.options['sort_by'] == 'size':
            key = lambda f: os.stat(f).st_size
        else:
            key = lambda f: f
        images = sorted(images, key=key)
        if self.options['sort_order'] == 'desc':
            images = list(reversed(images))
        return images

    def show_hidden(self, key):
        self.options['show_hidden'] = key == 'true'
        self.save_options()
        self.change_to_folder(self.folder, self.folder_history_position)

    def sort(self, key):
        if key in ('asc', 'desc'):
            self.options['sort_order'] = key
        else:
            self.options['sort_by'] = key
            m = {'name': 'asc', 'date': 'asc', 'size': 'desc'}
            self.options['sort_order'] = m[key]
        self.save_options()
        self.change_to_folder(self.folder, self.folder_history_position)

    def set_folder(self, path, modify_history_position=None):
        path = os.path.realpath(path)
        logging.info("Setting folder %s" % path)
        same = path == getattr(self, "folder", None)
        self.folder = path
        if modify_history_position is None:
            if not same:
                self.folder_history = self.folder_history[self.folder_history_position:]
                self.folder_history.insert(0, self.folder)
                self.folder_history_position = 0
        else:
            self.folder_history_position = modify_history_position
        self.search_text = ""
        self.images = self.get_image_list()

    def get_back_folder(self):
        i = self.folder_history_position
        if i < len(self.folder_history) - 1:
            return self.folder_history[i + 1]
        else:
            return None

    def folder_history_back(self):
        if self.folder_history_position < len(self.folder_history) - 1:
            self.change_to_folder(self.get_back_folder(), modify_history_position=self.folder_history_position + 1)

    def get_forward_folder(self):
        i = self.folder_history_position
        if i > 0:
            return self.folder_history[i - 1]
        else:
            return None

    def folder_history_forward(self):
        if self.folder_history_position > 0:
            self.change_to_folder(self.get_forward_folder(), modify_history_position=self.folder_history_position - 1)

    def get_parent_folder(self):
        return util.get_parent(self.folder)

    def folder_parent(self):
        if self.get_parent_folder():
            self.change_to_folder(self.get_parent_folder())

    def change_to_folder(self, path, modify_history_position=None):
        import gc

        with self.thumbs_queue_lock:
            self.thumbs_queue = []
            self.prepared_thumbs = set()
        self.pix_cache[False].clear()
        self.pix_cache[True].clear()
        self.meta_cache.clear()

        collected = gc.collect()
        logging.debug("GC collected: %d" % collected)

        old_folder = self.folder
        self.set_folder(path, modify_history_position)
        self.selected = old_folder if self.folder == util.get_parent(old_folder) else \
            self.images[0] if self.images else 'command:back'
        self.set_mode("folder")
        self.last_folder_change_time = time.time()
        self.render_folder_view()

    def check_kill(self):
        global killed
        if killed:
            logging.info('Killed, quitting...')
            GObject.idle_add(Gtk.main_quit)
        else:
            GObject.timeout_add(500, self.check_kill)

    def resized(self, widget, event):
        last_width = getattr(self, "last_width", 0)
        last_height = getattr(self, "last_height", 0)
        last_x = getattr(self, "last_x", 0)
        last_y = getattr(self, "last_y", 0)

        if (event.width, event.height, event.x, event.y) != (last_width, last_height, last_x, last_y):
            GObject.idle_add(self.refresh_image)
            if time.time() - self.last_automatic_resize > 0.5:
                logging.info("Manually resized, stop automatic resizing")
                self.manually_resized = True

        self.last_width = event.width
        self.last_height = event.height
        self.last_x = event.x
        self.last_y = event.y

    def window_state_changed(self, widget, event):
        self.options['maximized'] = event.new_window_state & Gdk.WindowState.MAXIMIZED != 0
        self.save_options()

    def after_quick_start(self):
        import signal
        signal.signal(signal.SIGINT, kill)
        signal.signal(signal.SIGTERM, kill)
        signal.signal(signal.SIGQUIT, kill)

        self.check_kill()
        self.folder_history = []
        self.folder_history_position = 0

        self.set_folder(os.path.dirname(self.selected))

        self.update_cursor()
        self.from_browser_time = 0

        self.browser = Gtk.ScrolledWindow()
        self.browser.set_visible(False)
        self.make_transparent(self.browser)
        self.box.add(self.browser)

        self.window.connect("delete-event", Gtk.main_quit)
        self.window.connect("key-press-event", self.process_key)
        if "--quit-on-focus-out" in sys.argv:
            self.window.connect("focus-out-event", Gtk.main_quit)
        self.window.connect("button-press-event", self.mousedown)
        self.last_mouseup_time = 0
        self.window.connect("button-release-event", self.mouseup)
        self.window.connect("scroll-event", self.scrolled)
        self.window.connect('motion-notify-event', self.mouse_motion)

        self.window.connect('configure-event', self.resized)
        self.window.connect('window-state-event', self.window_state_changed)

        self.load_bookmarks()

        GObject.idle_add(self.render_browser)

        self.start_cache_thread()
        if self.mode == "image":
            self.cache_around()
        self.start_thumbnail_thread()

    def load_options(self):
        self.options = self.load_json('options.json', {})
        defaults = {
            'decorated': True,
            'maximized': False,
            'fullscreen': False,

            'enlarge_smaller': False,

            'sort_by': 'name',
            'sort_order': 'asc',
            'show_hidden': False
        }
        for k, v in defaults.items():
            if not k in self.options:
                self.options[k] = v

    def filter_hidden(self, files):
        return files if self.options['show_hidden'] else filter(
            lambda f: not os.path.basename(f).startswith('.'), files)

    def save_options(self):
        self.save_json('options.json', self.options)

    def load_bookmarks(self):
        self.bookmarks = self.load_json('bookmarks.json', [util.get_xdg_pictures_folder()])

    def save_bookmarks(self):
        self.save_json('bookmarks.json', self.bookmarks)

    def load_json(self, filename, default_data):
        import json
        try:
            with open(self.get_config_file(filename)) as f:
                return json.load(f)
        except Exception:
            self.save_json(filename, default_data)
            return default_data

    def save_json(self, filename, data):
        import json
        with open(self.get_config_file(filename), 'w') as f:
            json.dump(data, f)

    def make_transparent(self, widget, color='rgba(0, 0, 0, 0)'):
        rgba = Gdk.RGBA()
        rgba.parse(color)
        widget.override_background_color(Gtk.StateFlags.NORMAL, rgba)

    def update_selected_info(self, filename):
        if self.selected != filename or not os.path.isfile(filename):
            return
        if not filename in self.meta_cache:
            self.get_meta(filename)
        if filename in self.meta_cache:    # get_meta() might have failed
            meta = self.meta_cache[filename]
            rok = not meta[1]
            self.js("set_dimensions('%s', '%s', '%d x %d')" % (
                util.path2url(filename), os.path.basename(filename), meta[2 if rok else 3], meta[3 if rok else 2]))

    def is_command(self, s):
        return s.startswith('command:')

    def on_js_action(self, action, argument):
        import json

        if action in ('ojo', 'ojo-select'):
            path = argument if self.is_command(argument) else util.url2path(argument)
            self.selected = path
            GObject.idle_add(lambda: self.update_selected_info(self.selected))
            if action == 'ojo':
                def _do():
                    self.from_browser_time = time.time()
                    self.show()
                    if os.path.isfile(path):
                        self.set_mode('image')
                GObject.idle_add(_do)
        elif action == 'ojo-priority':
            files = json.loads(argument)
            self.priority_thumbs(map(lambda f: util.url2path(f.encode('utf-8')), files))
        elif action == 'ojo-handle-key':
            self.process_key(key=argument, skip_browser=True)
        elif action == "ojo-search":
            self.search_text = argument

    def render_browser(self):
        from gi.repository import WebKit

        with open(ojoconfig.get_data_file('browse.html')) as f:
            html = f.read()

        self.web_view = WebKit.WebView()
        self.web_view.set_transparent(True)
        self.web_view.set_can_focus(True)

        def nav(wv, command):
            logging.info('Received command: ' + command)
            if command:
                command = command[command.index('|') + 1:]
                index = command.index(':')
                action = command[:index]
                argument = command[index + 1:]
                self.on_js_action(action, argument)
        self.web_view.connect("status-bar-text-changed", nav)

        self.web_view.connect('document-load-finished', lambda wf, data: self.render_folder_view())
        self.web_view.load_string(html, "text/html", "UTF-8", util.path2url(ojoconfig.get_data_path()) + '/')

        self.make_transparent(self.web_view)
        self.web_view.set_visible(True)
        self.browser.add(self.web_view)
        self.web_view.grab_focus()

    def get_folder_item(self, path):
        return {
            'label': os.path.basename(path) or path,
            'path': util.path2url(path),
            'filename': os.path.basename(path) or path,
            'icon': util.path2url(util.get_folder_icon(path, 24))
        }

    def get_command_item(self, command, path, icon, label = ''):
        icon_url = None
        if icon:
            try:
                icon_url = util.path2url(util.get_icon_path(icon, 24))
            except Exception:
                logging.exception('Could not get icon %s' % icon)
                icon_url = None
        return {
            'label': label,
            'path': command,
            'filename': os.path.basename(path) if path else label,
            'icon': icon_url
        }

    def get_navigation_folder(self, key):
        m = {'back': self.get_back_folder, 'forward': self.get_forward_folder, 'up': self.get_parent_folder}
        return m[key]()

    def on_command(self, command):
        parts = command.split(':')
        m = {
            'back': self.folder_history_back,
            'forward': self.folder_history_forward,
            'up': self.folder_parent,
            'add-bookmark': self.add_bookmark,
            'remove-bookmark': self.remove_bookmark,
            'sort': self.sort,
            'hidden': self.show_hidden,
        }
        m[parts[0]](*parts[1:])

    def get_crumbs(self):
        folder = self.folder
        crumbs = []
        while folder:
            crumbs.insert(0, {"path": util.path2url(folder), "name": os.path.basename(folder) or '/'})
            folder = util.get_parent(folder)
        return crumbs

    def add_bookmark(self):
        if not self.folder in self.bookmarks:
            self.bookmarks.append(self.folder)
            self.save_bookmarks()
            self.refresh_category(self.build_bookmarks_category())
            self.selected = 'command:remove-bookmark'
            self.select_in_browser(self.selected)

    def remove_bookmark(self):
        if self.folder in self.bookmarks:
            self.bookmarks.remove(self.folder)
            self.save_bookmarks()
            self.refresh_category(self.build_bookmarks_category())
            self.selected = 'command:add-bookmark'
            self.select_in_browser(self.selected)

    def build_bookmarks_category(self):
        bookmark_items = [self.get_folder_item(b) for b in
                          sorted(self.bookmarks, key=lambda p: os.path.basename(p).lower()) if os.path.isdir(b)]
        if self.folder in self.bookmarks:
            bookmark_items.append(
                self.get_command_item('command:remove-bookmark', None, 'remove', 'Remove current'))
        else:
            bookmark_items.append(self.get_command_item('command:add-bookmark', None, 'add', 'Add current'))
        bookmarks_category = {'label': 'Bookmarks', 'items': bookmark_items}
        return bookmarks_category

    def build_options_category(self):
        items = []

        by = self.options['sort_by']
        order = self.options['sort_order']
        mapby = {'name': 'name', 'date': 'date', 'size': 'file size'}
        mapord = {
            "desc": {'name': 'Z to A', 'date': 'newest at top', 'size': 'big at top'},
            "asc":  {'name': 'A to Z', 'date': 'oldest at top', 'size': 'small at top'}}
        items.append(self.get_command_item(None, None, None, 'Sorted by %s, %s' % (mapby[by], mapord[order][by])))
        for sort in ('name', 'date', 'size'):
            if sort != by:
                items.append(self.get_command_item('command:sort:' + sort, None, None, 'Sort by ' + mapby[sort]))
        if order == 'asc':
            m = {'name': 'Z to A', 'date': 'Newest at top', 'size': 'Big at top'}
            items.append(self.get_command_item('command:sort:desc', None, None, m[by]))
        else:
            m = {'name': 'A to Z', 'date': 'Oldest at top', 'size': 'Small at top'}
            items.append(self.get_command_item('command:sort:asc', None, None, m[by]))

        if self.options['show_hidden']:
            items.append(self.get_command_item('command:hidden:false', None, None, 'Hide hidden files'))
        else:
            items.append(self.get_command_item('command:hidden:true', None, None, 'Show hidden files'))

        return {'label': 'Options', 'items': items}

    def refresh_category(self, category):
        import json
        self.js('refresh_category(%s)' % json.dumps(category))

    def render_folder_view(self):
        self.web_view_loaded = True
        self.loading_folder = True
        thread_change_time = self.last_folder_change_time
        thread_folder = self.folder
        self.js("change_folder('%s')" % util.path2url(self.folder))

        import threading
        import json

        def _thread():
            parent_folder = self.get_parent_folder()

            nav_items = [
                self.get_command_item('command:back' if self.get_back_folder() else None, self.get_back_folder(), 'back'),
                self.get_command_item('command:forward' if self.get_forward_folder() else None, self.get_forward_folder(), 'forward'),
                self.get_command_item('command:up' if parent_folder else None, parent_folder, 'up')
            ]

            categories = [{'label': 'Navigate', 'no_labels': True, 'items': nav_items}]

            # Siblings
            if parent_folder:
                siblings = self.filter_hidden([os.path.join(parent_folder, f) for f in sorted(os.listdir(parent_folder))
                            if os.path.isdir(os.path.join(parent_folder, f))])
                pos = siblings.index(self.folder)
                if pos + 1 < len(siblings):
                    categories .append({'label': 'Next sibling', 'items': [self.get_folder_item(siblings[pos + 1])]})

            # Subfolders
            subfolders = self.filter_hidden([os.path.join(self.folder, f) for f in sorted(os.listdir(self.folder))
                          if os.path.isdir(os.path.join(self.folder, f))])
            if subfolders:
                categories.append({'label': 'Subfolders', 'items': [self.get_folder_item(sub) for sub in subfolders]})

            # Bookmarks
            categories.append(self.build_bookmarks_category())

            # Options
            categories.append(self.build_options_category())

            folder_info = {"crumbs": self.get_crumbs(), "categories": categories}

            if self.last_folder_change_time != thread_change_time or thread_folder != self.folder:
                return
            self.js("render_folders(%s)" % json.dumps(folder_info))
            self.select_in_browser(self.selected)

            pos = self.images.index(self.selected) if self.selected in self.images else 0
            self.priority_thumbs([x[1] for x in sorted(enumerate(self.images), key=lambda (i,f): abs(i - pos))])

            for img in self.images:
                if self.last_folder_change_time != thread_change_time or thread_folder != self.folder:
                    return
                self.js("add_image_div('%s', '%s', %s, %d)" % (
                    util.path2url(img), os.path.basename(img), 'true' if img==self.selected else 'false', 180))
                time.sleep(0.001)
                cached = self.get_cached_thumbnail_path(img)
                if os.path.exists(cached):
                    self.add_thumb(img, use_cached=cached)
                else:
                    try:
                        meta = self.get_meta(img)
                        w, h = meta.dimensions
                        rok = not self.needs_rotation(meta)
                        thumb_width = round(w * 120 / h) if rok else round(h * 120 / w)
                        if w and h:
                            self.js("set_dimensions('%s', '%s', '%d x %d', %d)" % (
                                util.path2url(img), os.path.basename(img), w if rok else h, h if rok else w, thumb_width))
                    except Exception:
                        pass

            self.select_in_browser(self.selected)

            self.loading_folder = False

        prepare_thread = threading.Thread(target=_thread)
        prepare_thread.daemon = True
        prepare_thread.start()

    def cache_around(self):
        if not hasattr(self, "images") or not self.images:
            return
        pos = self.images.index(self.selected) if self.selected in self.images else 0
        for i in [1, -1]:
            if pos + i < 0 or pos + i >= len(self.images):
                continue
            f = self.images[pos + i]
            if not f in self.pix_cache[self.zoom]:
                logging.info("Caching around: file %s, zoomed %s" % (f, self.zoom))
                self.cache_queue.put((f, self.zoom))

    def start_cache_thread(self):
        import threading
        import Queue
        self.cache_queue = Queue.Queue()
        self.preparing_event = threading.Event()

        def _queue_thread():
            logging.info("Starting cache thread")
            while True:
                if len(self.pix_cache[False]) > 20:   # TODO: Do we want a proper LRU policy, or this is good enough?
                    self.pix_cache[False] = {}
                if len(self.pix_cache[True]) > 20:
                    self.pix_cache[True] = {}

                path, zoom = self.cache_queue.get()

                try:
                    if not path in self.pix_cache[zoom]:
                        logging.debug("Cache thread loads file %s, zoomed %s" % (path, zoom))
                        self.current_preparing = path, zoom
                        try:
                            self.get_pixbuf(path, force=True, zoom=zoom)
                        except Exception:
                            logging.exception("Could not cache file " + path)
                        finally:
                            self.current_preparing = None
                            self.preparing_event.set()
                except Exception:
                    logging.exception("Exception in cache thread:")
        cache_thread = threading.Thread(target=_queue_thread)
        cache_thread.daemon = True
        cache_thread.start()

    def get_thumbs_cache_dir(self, height):
        return os.path.expanduser('~/.config/ojo/cache/%d' % height)

    def get_config_dir(self):
        return util.makedirs(os.path.expanduser('~/.config/ojo/config/'))

    def get_config_file(self, filename):
        return os.path.join(self.get_config_dir(), filename)

    def start_thumbnail_thread(self):
        import threading
        self.prepared_thumbs = set()
        self.thumbs_queue = []
        self.thumbs_queue_event = threading.Event()
        self.thumbs_queue_lock = threading.Lock()

        def _thumbs_thread():
            # delay the start to give the caching thread some time to prepare next images
            start_time = time.time()
            while self.mode == "image" and time.time() - start_time < 2:
                time.sleep(0.1)

            cache_dir = self.get_thumbs_cache_dir(120)
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
                    while time.time() - self.last_action_time < 2 and self.mode == "image":
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
                            self.add_thumb(img)
                    except Exception:
                        logging.exception("Exception in thumbs thread:")
                self.thumbs_queue_event.clear()
        thumbs_thread = threading.Thread(target=_thumbs_thread)
        thumbs_thread.daemon = True
        thumbs_thread.start()

    def add_thumb(self, img, use_cached=None):
        try:
            thumb_path = use_cached or self.prepare_thumbnail(img, 360, 120)
            self.js("add_image('%s', '%s')" % (util.path2url(img), util.path2url(thumb_path)))
            if img == self.selected:
                self.select_in_browser(img)
            self.prepared_thumbs.add(img)
        except Exception:
            self.js("remove_image_div('%s')" % util.path2url(img))
            logging.warning("Could not add thumb for " + img)

    def priority_thumbs(self, files):
        logging.debug("Priority thumbs: " + str(files))
        new_thumbs_queue = [f for f in files if not f in self.prepared_thumbs] + \
                           [f for f in self.thumbs_queue if not f in files and not f in self.prepared_thumbs]
        new_thumbs_queue = filter(self.is_image, new_thumbs_queue)
        with self.thumbs_queue_lock:
            self.thumbs_queue = new_thumbs_queue
            self.thumbs_queue_event.set()

    def get_meta(self, filename):
        try:
            from pyexiv2 import ImageMetadata
            meta = ImageMetadata(filename)
            meta.read()
            self.meta_cache[filename] = self.needs_orientation(meta), self.needs_rotation(meta), meta.dimensions[0], meta.dimensions[1]
            return meta
        except Exception:
            logging.exception("Could not parse meta-info for %s" % filename)
            return None

    def set_margins(self, margin):
        self.margin = margin
        def _f():
            self.box.set_margin_right(margin)
            self.box.set_margin_left(margin)
            self.box.set_margin_bottom(margin)
            self.box.set_margin_top(margin)
        GObject.idle_add(_f)

    def get_recommended_size(self):
        screen = self.window.get_screen()
        width = screen.get_width() - 150
        height = screen.get_height() - 150
        if width > 1.5 * height:
            width = int(1.5 * height)
        else:
            height = int(width / 1.5)
        return min(width, screen.get_width() - 150), min(height, screen.get_height() - 150)

    def get_max_image_width(self):
        if self.options['fullscreen']:
            return self.window.get_screen().get_width()
        elif self.manually_resized:
            self.last_windowed_image_width = self.window.get_window().get_width() - 2 * self.margin
            return self.last_windowed_image_width
        elif self.options['maximized']:
            if self.window.get_window():
                return self.window.get_window().get_width() - 2 * self.margin
            else:
                return self.window.get_screen().get_width() - 40 - 2 * self.margin
        else:
            self.last_windowed_image_width = self.get_recommended_size()[0] - 2 * self.margin
            return self.last_windowed_image_width

    def get_max_image_height(self):
        if self.options['fullscreen']:
            return self.window.get_screen().get_height()
        elif self.manually_resized:
            self.last_windowed_image_height = self.window.get_window().get_height() - 2 * self.margin
            return self.last_windowed_image_height
        elif self.options['maximized']:
            if self.window.get_window():
                return self.window.get_window().get_height() - 2 * self.margin
            else:
                return self.window.get_screen().get_height() - 40 - 2 * self.margin
        else:
            self.last_windowed_image_height = self.get_recommended_size()[1] - 2 * self.margin
            return self.last_windowed_image_height

    def increase_size(self):
        if self.manually_resized or self.zoom or self.options['fullscreen']:
            return

        new_width = max(400, self.pixbuf.get_width() + 2 * self.margin, self.get_width())
        new_height = max(300, self.pixbuf.get_height() + 2 * self.margin, self.get_height())
        if new_width > self.get_width() or new_height > self.get_height():
            self.last_automatic_resize = time.time()
            self.resize_and_center(new_width, new_height)

    def resize_and_center(self, new_width, new_height):
        self.window.resize(new_width, new_height)
        self.window.move(
            (self.window.get_screen().get_width() - new_width) // 2,
            (self.window.get_screen().get_height() - new_height) // 2)

    def go(self, direction, start_position=None):
        search = getattr(self, "search_text", "")
        applicable = self.images if not search else \
            [f for f in self.images if os.path.basename(f).lower().find(search) >= 0]
        filename = None
        position = start_position - direction if start_position is not None else applicable.index(self.selected)
        position = (position + direction + len(applicable)) % len(applicable)
        filename = applicable[position]

        def _f():
            try:
                self.show(filename)
            except Exception:
                logging.exception("go: Could not show %s" % filename)
                GObject.idle_add(lambda: self.go(direction))
        GObject.idle_add(_f)

    def toggle_fullscreen(self, full=None, first_run=False):
        if full is None:
            full = not self.options['fullscreen']
        self.options['fullscreen'] = full
        self.save_options()

        self.pix_cache[False] = {}

        if not first_run and self.shown:
            width = height = None
            if not self.options['fullscreen']:
                width = getattr(self, "last_windowed_image_width", None)
                height = getattr(self, "last_windowed_image_height", None)
            self.get_pixbuf(self.shown, force=True, width=width, height=height) # caches the new image before we start changing sizes
            self.box.set_visible(False)

        self.update_margins()
        if self.options['fullscreen']:
            self.window.fullscreen()
        elif not first_run:
            self.window.unfullscreen()
        self.last_automatic_resize = time.time()

        self.update_cursor()
        self.js('setTimeout(scroll_to_selected, 100)')

    def update_margins(self):
        if self.options['fullscreen']:
            self.make_transparent(self.window, color='rgba(77, 75, 69, 1)' if self.mode == 'folder' else 'rgba(0, 0, 0, 1)')
            self.set_margins(0)
        else:
            self.make_transparent(self.window, color='rgba(77, 75, 69, 0.9)')
            self.set_margins(30)

    def update_cursor(self):
        if self.mousedown_zoomed:
            self.set_cursor(Gdk.CursorType.HAND1)
        elif self.mousedown_panning:
            self.set_cursor(Gdk.CursorType.HAND1)
        elif self.options['fullscreen'] and self.mode == 'image':
            self.set_cursor(Gdk.CursorType.BLANK_CURSOR)
        else:
            self.set_cursor(Gdk.CursorType.ARROW)

    def set_cursor(self, cursor):
        if self.window.get_window() and (
            not self.window.get_window().get_cursor() or cursor != self.window.get_window().get_cursor().get_cursor_type()):
            self.window.get_window().set_cursor(Gdk.Cursor.new_for_display(Gdk.Display.get_default(), cursor))

    def set_mode(self, mode):
        self.mode = mode
        if self.mode == "image" and self.selected != self.shown:
            self.show(self.selected)
        elif self.mode == "folder":
            self.shown = None
            self.window.set_title(self.folder)

        self.update_cursor()
        self.scroll_window.set_visible(self.mode == 'image')
        self.image.set_visible(self.mode == 'image')
        self.browser.set_visible(self.mode == 'folder')
        self.update_margins()
        self.js("set_mode('%s')" % self.mode)

        if self.mode == 'folder' and not self.manually_resized:
            self.resize_and_center(*self.get_recommended_size())

    def clear_thumbnails(self, folder):
        images = filter(self.is_image, map(lambda f: os.path.join(folder, f), os.listdir(folder)))
        for img in images:
            cached = self.get_cached_thumbnail_path(img, True)
            if os.path.isfile(cached) and os.path.split(cached)[0] == self.get_thumbs_cache_dir(120):
                try:
                    os.unlink(cached)
                except IOError:
                    logging.exception("Could not delete %s" % cached)

    def process_key(self, widget=None, event=None, key=None, skip_browser=False):
        key = key or Gdk.keyval_name(event.keyval)
        if key == 'Escape' and (self.mode == 'image' or skip_browser):
            Gtk.main_quit()
        elif key in ("F11",) or (self.mode == 'image' and key in ('f', 'F')):
            self.toggle_fullscreen()
        elif key == 'F5':
            if event and event.state & Gdk.ModifierType.CONTROL_MASK and self.mode == "folder":
                self.clear_thumbnails(self.folder)
            self.show(self.selected if self.mode == 'image' else self.folder)
        elif key == 'Return':
            if self.mode == 'image':
                self.set_mode('folder')
            else:
                prev = self.selected    # save selected from before the action, as it might change it
                self.show()
                if os.path.isfile(prev):
                    self.set_mode('image')
        elif self.mode == 'folder':
            if hasattr(self, 'web_view'):
                self.web_view.grab_focus()
            if key == 'Left' and event and (event.state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK)):
                self.folder_history_back()
            elif key == 'Right' and event and (event.state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK)):
                self.folder_history_forward()
            elif key == 'Up' and event and (event.state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK)):
                self.folder_parent()
            elif not skip_browser:
                self.js("on_key('%s')" % key)
            else:
                if key == 'BackSpace':
                    self.folder_parent()
        elif key in ("Right", "Down", "Page_Down", "space"):
            GObject.idle_add(lambda: self.go(1))
        elif key in ("Left", "Up", "Page_Up", "BackSpace"):
            GObject.idle_add(lambda: self.go(-1))
        elif key == "Home":
            GObject.idle_add(lambda: self.go(1, 0))
        elif key == "End":
            GObject.idle_add(lambda: self.go(-1, len(self.images) - 1))
        elif key in ("z", "Z"):
            self.set_zoom(not self.zoom)
            self.refresh_image()
            self.update_zoomed_views()
        elif key in ("1", "0"):
            self.set_zoom(True)
            self.refresh_image()
            self.update_zoomed_views()
        elif key in ("slash", "asterisk"):
            self.set_zoom(False)
            self.refresh_image()
            self.update_zoomed_views()

    def set_zoom(self, zoom, x_percent=None, y_percent=None):
        self.zoom = zoom
        if x_percent is None:
            x_percent = self.zoom_x_percent
        if y_percent is None:
            y_percent = self.zoom_y_percent
        self.zoom_x_percent = x_percent
        self.zoom_y_percent = y_percent

    def update_zoomed_views(self):
        rect = Gdk.Rectangle()
        rect.width = self.get_max_image_width()
        rect.height = self.get_max_image_height()
        self.scroll_window.size_allocate(rect)
        self.update_zoom_scrolling()

    def get_width(self):
        return self.window.get_window().get_width() if self.window.get_window() else 1

    def get_height(self):
        return self.window.get_window().get_height() if self.window.get_window() else 1

    def mouse_motion(self, widget, event):
        if not self.mousedown_zoomed and not self.mousedown_panning:
            self.set_cursor(Gdk.CursorType.ARROW)
            return

        self.register_action()
        if self.mousedown_zoomed:
            self.set_zoom(True,
                min(1, max(0, event.x - 100) / max(1, self.get_width() - 200)),
                min(1, max(0, event.y - 100) / max(1, self.get_height() - 200)))
            self.update_zoom_scrolling()
        elif self.mousedown_panning:
            ha = self.scroll_window.get_hadjustment()
            ha.set_value(self.scroll_h - (event.x - self.mousedown_x))
            va = self.scroll_window.get_vadjustment()
            va.set_value(self.scroll_v - (event.y - self.mousedown_y))

    def mousedown(self, widget, event):
        if self.mode != "image" or event.button != 1:
            return

        self.mousedown_x = event.x
        self.mousedown_y = event.y

        if self.zoom:
            self.mousedown_panning = True
            self.update_cursor()
            self.register_action()
        else:
            mousedown_time = time.time()
            x = event.x
            y = event.y

            def act():
                if mousedown_time > self.last_mouseup_time:
                    self.mousedown_zoomed = True
                    self.register_action()
                    self.set_zoom(True,
                        min(1, max(0, x - 100) / max(1, self.get_width() - 200)),
                        min(1, max(0, y - 100) / max(1, self.get_height() - 200)))
                    self.refresh_image()
                    self.update_zoomed_views()
                    self.update_cursor()

            GObject.timeout_add(250, act)

    def register_action(self):
        self.last_action_time = time.time()

    def mouseup(self, widget, event):
        self.last_mouseup_time = time.time()
        if self.mode != "image" or event.button != 1:
            return
        if self.last_mouseup_time - self.from_browser_time < 0.2:
            return
        if self.mousedown_zoomed:
            self.set_zoom(False)
            self.refresh_image()
            self.update_zoomed_views()
        elif self.mousedown_panning and (event.x != self.mousedown_x or event.y != self.mousedown_y):
            self.scroll_h = self.scroll_window.get_hadjustment().get_value()
            self.scroll_v = self.scroll_window.get_vadjustment().get_value()
        else:
            self.go(-1 if event.x < 0.5 * self.get_width() else 1)
        self.mousedown_zoomed = False
        self.mousedown_panning = False
        self.update_cursor()

    def scrolled(self, widget, event):
        if self.mode != "image" or self.zoom:
            return
        if event.direction not in (
            Gdk.ScrollDirection.UP, Gdk.ScrollDirection.LEFT, Gdk.ScrollDirection.DOWN, Gdk.ScrollDirection.RIGHT):
            return

        if getattr(self, "wheel_timer", None):
            GObject.source_remove(self.wheel_timer)

        direction = -1 if event.direction in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.LEFT) else 1
        self.wheel_timer = GObject.timeout_add(100, lambda: self.go(direction))

    def pixbuf_from_data(self, data, width, height):
        from gi.repository import Gio
        input_str = Gio.MemoryInputStream.new_from_data(data, None)
        if not self.zoom:
            return GdkPixbuf.Pixbuf.new_from_stream_at_scale(input_str, width, height, True, None)
        else:
            return GdkPixbuf.Pixbuf.new_from_stream(input_str, None)

    def pixbuf_to_b64(self, pixbuf):
        return pixbuf.save_to_bufferv('png', [], [])[1].encode("base64").replace('\n', '')

    def get_cached_thumbnail_path(self, filename, force_cache=False):
        # Use gifs directly - webkit will handle transparency, animation, etc.
        if not force_cache and os.path.splitext(filename)[1].lower() == '.gif':
            return filename

        import hashlib
        import re
        # we append modification time to ensure we're not using outdated cached images
        mtime = os.path.getmtime(filename)
        hash = hashlib.md5(filename + str(mtime)).hexdigest()
        return os.path.join(self.get_thumbs_cache_dir(120), re.sub('[\W_]+', '_', filename)[:80] + '_' + hash + ".jpg")

    def prepare_thumbnail(self, filename, width, height):
        cached = self.get_cached_thumbnail_path(filename)

        def use_pil():
            pil = self.get_pil(filename, width, height)
            format = {".gif": "GIF", ".png": "PNG", ".svg": "PNG"}.get(ext, 'JPEG')
            for format in (format, 'JPEG', 'GIF', 'PNG'):
                try:
                    pil.save(cached, format)
                    if os.path.getsize(cached):
                        break
                except Exception, e:
                    logging.exception('Could not save thumbnail in format %s:' % format)

        def use_pixbuf():
            pixbuf = self.get_pixbuf(filename, True, False, 360, 120)
            pixbuf.savev(cached, 'png', [], [])

        if not os.path.exists(cached):
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
            raise IOError('Could not create thumbnail')
        return cached

    def get_pixbuf(self, filename, force=False, zoom=None, width=None, height=None):
        if zoom is None:
            zoom = self.zoom

        width = width or self.get_max_image_width()
        height = height or self.get_max_image_height()

        while not force and self.current_preparing == (filename, zoom):
            logging.info("Waiting on cache")
            self.preparing_event.wait()
            self.preparing_event.clear()
        if filename in self.pix_cache[zoom]:
            cached = self.pix_cache[zoom][filename]
            if cached[1] == width:
                logging.info("Cache hit: " + filename)
                return cached[0]

        full_meta = None
        if not filename in self.meta_cache:
            full_meta = self.get_meta(filename)
        if filename in self.meta_cache:
            meta = self.meta_cache[filename]
            oriented = not meta[0]
            image_width, image_height = meta[2], meta[3]
        else:
            oriented = True
            image_width = image_height = None

        if oriented:
            enlarge_smaller = self.options['enlarge_smaller']

            try:
                if not image_width and not enlarge_smaller:
                    format, image_width, image_height = GdkPixbuf.Pixbuf.get_file_info(filename)
                if not zoom:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        filename,
                        min(width, image_width if not enlarge_smaller else width),
                        min(height, image_height if not enlarge_smaller else height),
                        True)
                else:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file(filename)
                self.pix_cache[zoom][filename] = pixbuf, width
                logging.debug("Loaded directly")
                return pixbuf
            except GObject.GError, e:
                pass # below we'll use another method

            try:
                if not full_meta:
                    full_meta = self.get_meta(filename)
                preview = full_meta.previews[-1].data
                pixbuf = self.pixbuf_from_data(
                    preview,
                    min(width, image_width if not enlarge_smaller else width),
                    min(height, image_height if not enlarge_smaller else height))
                self.pix_cache[zoom][filename] = pixbuf, width
                logging.debug("Loaded from preview")
                return pixbuf
            except Exception, e:
                pass # below we'll use another method

        pixbuf = self.pil_to_pixbuf(self.get_pil(filename, width, height, zoom))
        self.pix_cache[zoom][filename] = pixbuf, width
        logging.debug("Loaded with PIL")
        return pixbuf

    def get_pil(self, filename, width, height, zoomed_in=False):
        from PIL import Image

        meta = None

        try:
            pil_image = Image.open(filename)
        except IOError:
            import cStringIO
            meta = self.get_meta(filename)
            pil_image = Image.open(cStringIO.StringIO(meta.previews[-1].data))

        if not zoomed_in:
            pil_image.thumbnail((width, height), Image.ANTIALIAS)

        if filename not in self.meta_cache or self.meta_cache[filename][0]: # needs orientation
            try:
                pil_image = self.auto_rotate(meta or self.get_meta(filename), pil_image)
            except Exception:
                logging.exception('Auto-rotation failed for %s' % filename)

        if not zoomed_in and (pil_image.size[0] > width or pil_image.size[1] > height):
            pil_image.thumbnail((width, height), Image.ANTIALIAS)

        return pil_image

    def pil_to_base64(self, pil_image):
        import cStringIO
        output = cStringIO.StringIO()
        pil_image.save(output, "PNG")
        contents = output.getvalue().encode("base64")
        output.close()
        return contents.replace('\n', '')

    def pil_to_pixbuf(self, pil_image):
        import cStringIO
        if pil_image.mode != 'RGB':          # Fix IOError: cannot write mode P as PPM
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

    def needs_orientation(self, meta):
        return 'Exif.Image.Orientation' in meta.keys() and meta['Exif.Image.Orientation'].value != 1

    def needs_rotation(self, meta):
        return 'Exif.Image.Orientation' in meta.keys() and meta['Exif.Image.Orientation'].value in (5, 6, 7, 8)

    def auto_rotate(self, meta, im):
        from PIL import Image
        # We rotate regarding to the EXIF orientation information
        if 'Exif.Image.Orientation' in meta.keys():
            orientation = meta['Exif.Image.Orientation'].value
            if orientation == 1:
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
        else:
            # No EXIF information, the user has to do it
            result = im

        return result

if __name__ == "__main__":
    Ojo()
