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
import os
import sys
import time
import logging
import optparse
import gettext
from gettext import gettext as _
from collections import OrderedDict

import gi
gi.require_version('WebKit', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GObject

import util
from util import _u
import ojoconfig
from metadata import metadata
import config
from config import options
from imaging import (
    get_pil,
    get_size,
    auto_rotate_pixbuf,
    pil_to_pixbuf,
    pixbuf_from_data,
    is_image,
)

gettext.textdomain('ojo')

LEVELS = (logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG)

THUMBHEIGHTS = [80, 120, 180, 240, 320, 480]

CACHE_SIZE = 50

killed = False


def kill(*args):
    global killed
    killed = True


class Ojo():
    def parse_command_line(self):
        # Support for command line options.
        parser = optparse.OptionParser(
            version="%%prog %s" % ojoconfig.__version__, usage=(_("ojo [options]")))
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
        config.load_options()

        if len(self.command_args) >= 1 and os.path.exists(self.command_args[0]):
            path = os.path.realpath(self.command_args[0])
        else:
            path = options['folder'].encode('utf-8')
        logging.info("Started with: %s" % path)
        if not os.path.exists(path):
            logging.warning("%s does not exist, reverting to %s" %
                            (path, util.get_xdg_pictures_folder()))
            path = util.get_xdg_pictures_folder()

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

        self.window.set_decorated(options['decorated'])
        if options['maximized']:
            self.window.maximize()

        self.pix_cache = {False: OrderedDict(), True: OrderedDict()}  # keyed by "zoomed" property
        self.current_preparing = None
        self.manually_resized = False

        self.set_zoom(False, 0.5, 0.5)
        self.mode = 'image' if os.path.isfile(path) else 'folder'
        self.is_in_search = False
        self.last_action_time = 0
        self.last_folder_change_time = time.time()
        self.shown = None
        self.toggle_fullscreen(options['fullscreen'], first_run=True)
        if options['fullscreen']:
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
            self.selected = self.images[0] if self.images else self.get_parent_folder()
            self.last_automatic_resize = time.time()
            self.window.resize(*self.get_recommended_size())

        self.window.set_visible(True)

        GObject.threads_init()
        Gdk.threads_init()
        Gdk.threads_enter()
        Gtk.main()
        Gdk.threads_leave()

    def show_error(self, error_msg):
        if self.mode == 'image':
            dialog = Gtk.MessageDialog(
                self.window,
                Gtk.DialogFlags.MODAL,
                Gtk.MessageType.ERROR,
                Gtk.ButtonsType.OK,
                error_msg)
            dialog.set_title("Oops")
            dialog.run()
            dialog.destroy()
        else:
            self.js('show_error("Oops: %s")' % error_msg)

    def safe(self, fn):
        def safe_fn(*args, **kwargs):
            try:
                fn(*args, **kwargs)
            except OSError, e:
                logging.exception('OSError:')
                self.show_error('%s %s' % (e.message, os.strerror(e.errno)))
            except Exception, e:
                logging.exception('Exception:')
                self.show_error(e.message)
        return safe_fn

    def js(self, command):
        if hasattr(self, "web_view_loaded"):
            GObject.idle_add(lambda: self.web_view.execute_script(command))
        else:
            GObject.timeout_add(100, lambda: self.js(command))

    def select_in_browser(self, path):
        if path:
            self.js("select('%s')" %
                    (path if self.is_command(path) else util.path2url(path)))
        else:
            self.js("goto_visible(true)")

    def update_zoom_scrolling(self):
        if self.zoom:
            if not self.zoom_x_percent is None:
                ha = self.scroll_window.get_hadjustment()
                ha.set_value(self.zoom_x_percent * (
                        ha.get_upper() - ha.get_page_size() - ha.get_lower()))
                self.zoom_x_percent = None
            if not self.zoom_y_percent is None:
                va = self.scroll_window.get_vadjustment()
                va.set_value(self.zoom_y_percent * (
                        va.get_upper() - va.get_page_size() - va.get_lower()))
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

    def get_image_list(self):
        images = filter(
            is_image,
            map(lambda f: os.path.join(self.folder, f), os.listdir(self.folder)))
        if not options['show_hidden']:
            images = filter(lambda f: not os.path.basename(f).startswith('.'), images)

        if options['sort_by'] == 'extension':
            key = lambda f: (os.path.splitext(f)[1] + '_' + os.path.basename(f)).lower()
        elif options['sort_by'] == 'name':
            key = lambda f: os.path.basename(f).lower()
        elif options['sort_by'] == 'date':
            key = lambda f: os.stat(f).st_mtime
        elif options['sort_by'] == 'exif_date':
            import datetime
            default = datetime.datetime(1900, 1, 1)

            def _exif_date(f):
                m = metadata.get(f)
                if not m:
                    return default
                return m['exif'].get('Exif.Photo.DateTimeOriginal', default)

            dates = {image: _exif_date(image) for image in images}
            key = lambda f: dates[f]
        elif options['sort_by'] == 'size':
            key = lambda f: os.stat(f).st_size
        else:
            key = lambda f: f

        images = sorted(images, key=key)
        if options['sort_order'] == 'desc':
            images = list(reversed(images))

        return images

    def get_group_key(self, image, sort_by=None):
        if not sort_by:
            sort_by = options['sort_by']

        if sort_by == 'extension':
            ext = os.path.splitext(image)[1][1:].upper()
            return ext if ext else 'No extension'
        elif sort_by == 'date':
            import datetime
            ts = os.stat(image).st_mtime
            return datetime.datetime.fromtimestamp(ts).strftime(options['date_format'])
        elif sort_by == 'exif_date':
            m = metadata.get(image)
            if not m:
                return 'No EXIF date'
            d = m['exif'].get('Exif.Photo.DateTimeOriginal', None)
            if not d:
                return 'No EXIF date'
            return d.strftime(options['date_format'])
        elif sort_by == 'name':
            return os.path.basename(image)[0].upper()
        elif sort_by == 'size':
            size = os.stat(image).st_size
            buckets = options['group_by_size_buckets']
            return next(b[1] for b in buckets if b[0] > size)
        else:
            return None

    def toggle_hidden(self, key):
        options['show_hidden'] = key == 'true'
        config.save_options()
        self.change_to_folder(self.folder, self.folder_history_position)

    def toggle_groups(self, key):
        options['show_groups_for'][options['sort_by']] = key == 'true'
        config.save_options()
        self.change_to_folder(self.folder, self.folder_history_position)

    def toggle_captions(self, key):
        options['show_captions'] = key == 'true'
        config.save_options()
        self.refresh_category(self.build_options_category())
        self.js('toggle_captions(%s)' % key)

    def sort(self, key):
        if key in ('asc', 'desc'):
            options['sort_order'] = key
        else:
            options['sort_by'] = key
            m = {
                'extension': 'asc',
                'name': 'asc',
                'date': 'asc',
                'exif_date': 'asc',
                'size': 'desc'
            }
            options['sort_order'] = m[key]
        config.save_options()
        self.change_to_folder(self.folder, self.folder_history_position)

    def set_folder(self, path, modify_history_position=None, bypass_search=False):
        path = os.path.realpath(path)
        options['folder'] = path
        config.save_options()
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
        self.images = self.get_image_list()
        self.search_text = ""
        self.toggle_search(False, bypass_search)

    def get_back_folder(self):
        i = self.folder_history_position
        if i < len(self.folder_history) - 1:
            return self.folder_history[i + 1]
        else:
            return None

    def folder_history_back(self):
        if self.folder_history_position < len(self.folder_history) - 1:
            self.change_to_folder(
                self.get_back_folder(),
                modify_history_position=self.folder_history_position + 1)

    def get_forward_folder(self):
        i = self.folder_history_position
        if i > 0:
            return self.folder_history[i - 1]
        else:
            return None

    def folder_history_forward(self):
        if self.folder_history_position > 0:
            self.change_to_folder(
                self.get_forward_folder(),
                modify_history_position=self.folder_history_position - 1)

    def get_parent_folder(self):
        return util.get_parent(self.folder)

    def folder_parent(self):
        if self.get_parent_folder():
            self.change_to_folder(self.get_parent_folder())

    def change_to_folder(self, path, modify_history_position=None):
        import threading

        def _go():
            # make sure we fail early if there are permission issues:
            os.listdir(path)

            self.thumbs.reset_queues()
            self.pix_cache[False].clear()
            self.pix_cache[True].clear()

            # TODO: we may want to call metadata.clear_cache() here, or use a LRU policy for it

            import gc
            collected = gc.collect()
            logging.debug("GC collected: %d" % collected)

            old_folder = self.folder
            self.set_folder(path, modify_history_position, bypass_search=True)
            self.selected = old_folder if self.folder == util.get_parent(old_folder) else \
                self.images[0] if self.images else self.get_parent_folder()
            self.set_mode("folder")
            self.last_folder_change_time = time.time()
            self.render_folder_view()

        self.show_loading_folder_msg()
        threading.Timer(0, _go).start()

    def check_kill(self):
        global killed
        if killed:
            logging.info('Killed, quitting...')
            self.exit()
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
        options['maximized'] = event.new_window_state & Gdk.WindowState.MAXIMIZED != 0
        config.save_options()

    def after_quick_start(self):
        import signal
        signal.signal(signal.SIGINT, kill)
        signal.signal(signal.SIGTERM, kill)
        signal.signal(signal.SIGQUIT, kill)

        self.check_kill()
        self.folder_history = []
        self.folder_history_position = 0

        try:
            self.show_loading_folder_msg()
            self.set_folder(os.path.dirname(self.selected))
        except OSError as e:
            logging.exception('Could not open %s' % self.selected)
            self.selected = util.get_xdg_pictures_folder()
            self.set_folder(self.selected)

        self.update_cursor()
        self.from_browser_time = 0

        self.browser = Gtk.ScrolledWindow()
        self.browser.set_visible(False)
        self.make_transparent(self.browser)
        self.box.add(self.browser)

        self.window.connect("delete-event", self.exit)
        self.window.connect("key-press-event", self.safe(self.process_key))
        if "--quit-on-focus-out" in sys.argv:
            self.window.connect("focus-out-event", self.exit)
        self.window.connect("button-press-event", self.mousedown)
        self.last_mouseup_time = 0
        self.window.connect("button-release-event", self.mouseup)
        self.window.connect("scroll-event", self.scrolled)
        self.window.connect('motion-notify-event', self.mouse_motion)

        self.window.connect('configure-event', self.resized)
        self.window.connect('window-state-event', self.window_state_changed)

        config.load_bookmarks()

        GObject.idle_add(self.render_browser)

        self.start_cache_thread()
        if self.mode == "image":
            self.cache_around()

        import thumbs
        self.thumbs = thumbs.Thumbs(ojo=self)
        self.thumbs.start()

    def show_loading_folder_msg(self):
        if options['sort_by'] == 'exif_date':
            self.js('show_spinner("Sorting by EXIF date, please wait...")')
        else:
            self.js('show_spinner("Listing folder...")')

    def filter_hidden(self, files):
        return files if options['show_hidden'] else filter(
            lambda f: not os.path.basename(f).startswith('.'), files)

    def make_transparent(self, widget, color='rgba(0, 0, 0, 0)'):
        rgba = Gdk.RGBA()
        rgba.parse(color)
        widget.override_background_color(Gtk.StateFlags.NORMAL, rgba)

    def update_selected_info(self, filename):
        if self.selected != filename or not os.path.isfile(filename):
            return
        meta = metadata.get(filename)
        if meta:
            rok = not meta['needs_rotation']
            self.js("set_dimensions('%s', '%s', '%d x %d')" % (
                util.path2url(filename),
                self.safe_basename(filename),
                meta['width' if rok else 'height'],
                meta['height' if rok else 'width']))

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

                GObject.idle_add(self.safe(_do))
        elif action == 'ojo-priority':
            files = json.loads(argument)
            self.thumbs.priority_thumbs(
                map(lambda f: util.url2path(f.encode('utf-8')), files))
        elif action == 'ojo-handle-key':
            self.process_key(key=argument, skip_browser=True)
        elif action == 'ojo-folder-up':
            self.folder_parent()
        elif action == "ojo-search":
            self.search_text = argument
            if self.search_text:
                self.toggle_search(True)

    def render_browser(self):
        from gi.repository import WebKit

        with open(ojoconfig.get_data_file('browse.html')) as f:
            html = f.read()

        self.web_view = WebKit.WebView()
        self.web_view.set_transparent(True)
        self.web_view.set_can_focus(True)

        def nav(wv, command):
            logging.debug('Received command: ' + command)
            if command:
                command = command[command.index('|') + 1:]
                index = command.index(':')
                action = command[:index]
                argument = command[index + 1:]
                self.safe(self.on_js_action)(action, argument)

        self.web_view.connect("status-bar-text-changed", nav)

        self.web_view.connect('document-load-finished',
                              lambda wf, data: self.render_folder_view())
        self.web_view.load_string(
            html, "text/html", "UTF-8", util.path2url(ojoconfig.get_data_path()) + '/')

        self.make_transparent(self.web_view)
        self.web_view.set_visible(True)
        self.browser.add(self.web_view)
        self.web_view.grab_focus()

    def get_parent_folder_item(self):
        if self.folder == '/':
            return None
        else:
            return dict(
                self.get_folder_item(self.get_parent_folder(), group='Subfolders'),
                label='..',
                filename='..'
            )

    def get_folder_item(self, path, group='', label=None):
        return {
            'label': label or _u(os.path.basename(path) or path),
            'path': util.path2url(path),
            'filename': os.path.basename(path) or path,
            'icon': util.path2url(util.get_folder_icon(path, 16)),
            'group': group,
        }

    def get_command_item(self, command, path, icon, group='', label='', nofocus=False):
        icon_url = None
        if icon:
            try:
                icon_url = util.path2url(util.get_icon_path(icon, 16))
            except Exception:
                logging.exception('Could not get icon %s' % icon)
                icon_url = None
        return {
            'label': label,
            'path': command,
            'filename': os.path.basename(path) if path else label,
            'group': group,
            'icon': icon_url,
            'nofocus': nofocus,
        }

    def get_navigation_folder(self, key):
        m = {
            'back': self.get_back_folder,
            'forward': self.get_forward_folder,
            'up': self.get_parent_folder
        }
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
            'hidden': self.toggle_hidden,
            'groups': self.toggle_groups,
            'captions': self.toggle_captions,
        }
        m[parts[0]](*parts[1:])

    def get_crumbs(self):
        folder = self.folder
        crumbs = []
        while folder:
            crumbs.insert(0, {
                "path": util.path2url(folder),
                "name": os.path.basename(folder) or '/'
            })
            folder = util.get_parent(folder)
        return crumbs

    def add_bookmark(self):
        if _u(self.folder) not in config.bookmarks:
            config.bookmarks.append(_u(self.folder))
            config.save_bookmarks()
            self.refresh_category(self.build_bookmarks_category())
            self.selected = 'command:remove-bookmark'
            self.select_in_browser(self.selected)

    def remove_bookmark(self):
        if _u(self.folder) in config.bookmarks:
            config.bookmarks.remove(_u(self.folder))
            config.save_bookmarks()
            self.refresh_category(self.build_bookmarks_category())
            self.selected = 'command:add-bookmark'
            self.select_in_browser(self.selected)

    def build_bookmarks_category(self):
        bookmark_items = [self.get_folder_item(b, group='Bookmarks') for b in
                          sorted(config.bookmarks,
                                 key=lambda p: os.path.basename(p).lower())
                          if os.path.isdir(b)]
        if _u(self.folder) in config.bookmarks:
            bookmark_items.append(
                self.get_command_item(
                    'command:remove-bookmark', None,
                    icon='remove',
                    group='Bookmarks',
                    label='Remove current'))
        else:
            bookmark_items.append(self.get_command_item(
                'command:add-bookmark', None,
                icon='add',
                group='Bookmarks',
                label='Add current'))
        bookmarks_category = {'label': 'Bookmarks', 'items': bookmark_items}
        return bookmarks_category

    def build_options_category(self):
        items = []

        by = options['sort_by']
        order = options['sort_order']
        mapby = {
            'extension': 'type',
            'name': 'name',
            'date': 'file date',
            'exif_date': 'EXIF date',
            'size': 'file size',
        }
        mapord = {
            "desc": {
                'extension': 'Z to A',
                'name': 'Z to A',
                'date': 'newest at top',
                'exif_date': 'newest at top',
                'size': 'big at top',
            },
            "asc": {
                'extension': 'A to Z',
                'name': 'A to Z',
                'date': 'oldest at top',
                'exif_date': 'oldest at top',
                'size': 'small at top'
            }
        }
        for sort in ('name', 'extension', 'date', 'exif_date', 'size'):
            if sort != by:
                items.append(self.get_command_item(
                    'command:sort:' + sort, None, None,
                    group='Options',
                    label='Sort by ' + mapby[sort]))
            else:
                items.append(self.get_command_item(
                    None, None, None,
                    group='Options',
                    label='Sort by %s, %s' % (mapby[by], mapord[order][by])))

        if order == 'asc':
            m = {
                'extension': 'Z to A',
                'name': 'Z to A',
                'date': 'Newest at top',
                'exif_date': 'Newest at top',
                'size': 'Big at top'
            }
            items.append(self.get_command_item(
                'command:sort:desc', None, None,
                group='Options',
                label='Order: ' + m[by]))
        else:
            m = {
                'extension': 'A to Z',
                'name': 'A to Z',
                'date': 'Oldest at top',
                'exif_date': 'Oldest at top',
                'size': 'Small at top'
            }
            items.append(self.get_command_item(
                'command:sort:asc', None, None,
                group='Options',
                label=m[by]))

        if options['show_groups_for'].get(by, False):
            items.append(self.get_command_item(
                'command:groups:false', None, None,
                group='Options',
                label='Hide group labels for this sorting'))
        else:
            items.append(self.get_command_item(
                'command:groups:true', None, None,
                group='Options',
                label='Show group labels for this sorting'))

        if options['show_hidden']:
            items.append(self.get_command_item(
                'command:hidden:false', None, None,
                group='Options',
                label='Hide hidden files'))
        else:
            items.append(self.get_command_item(
                'command:hidden:true', None, None,
                group='Options',
                label='Show hidden files'))

        if options['show_captions']:
            items.append(self.get_command_item(
                'command:captions:false', None, None,
                group='Options',
                label='Hide captions'))
        else:
            items.append(self.get_command_item(
                'command:captions:true', None, None,
                group='Options',
                label='Show captions'))

        return {
            'label': 'Options',
            'items': items
        }

    def refresh_category(self, category):
        import json
        self.js('refresh_category(%s)' % json.dumps(category))

    def safe_basename(self, img):
        return os.path.basename(img).replace("'", "\\'")

    def render_folder_view(self):
        self.web_view_loaded = True
        self.loading_folder = True
        thread_change_time = self.last_folder_change_time
        thread_folder = self.folder
        thumbh = options['thumb_height']
        self.js("set_thumb_height(%d)" % thumbh)
        self.js("change_folder('%s')" % util.path2url(self.folder))

        import threading
        import json

        def _prepare_thread():
            folder_info = self.build_folder_info()

            if self.last_folder_change_time != thread_change_time or thread_folder != self.folder:
                return
            self.js("render_folders(%s)" % json.dumps(folder_info))
            self.select_in_browser(self.selected)

            pos = self.images.index(
                self.selected) if self.selected in self.images else 0
            self.thumbs.priority_thumbs([
                x[1] for x in
                sorted(enumerate(self.images), key=lambda (i, f): abs(i - pos))
                if not os.path.exists(self.thumbs.get_cached_thumbnail_path(x[1]))
            ])

            self.js("set_image_count(%d)" % len(self.images))
            if self.selected:
                self.update_selected_info(self.selected)

            last_group = None
            for img in self.images:
                group = None
                groups_enabled = options.get('show_groups_for', {}).get(options['sort_by'], False)
                if groups_enabled:
                    group = self.get_group_key(img, options['sort_by'])
                    if group != last_group:
                        self.js("add_group('%s', %s)" % (group, 'true' if last_group is None else 'false'))
                        last_group = group

                if self.last_folder_change_time != thread_change_time or thread_folder != self.folder:
                    return
                self.js("add_image_div('%s', '%s', %s, %s, '%s')" % (
                    util.path2url(img),
                    self.safe_basename(img),
                    'true' if img == self.selected else 'false',
                    'true' if options['show_captions'] else 'false',
                    util._str(group) if group else '',
                ))
                time.sleep(0.001)
                cached = self.thumbs.get_cached_thumbnail_path(img)
                if os.path.exists(cached):
                    self.thumb_ready(img, thumb_path=cached)
                else:
                    try:
                        meta = metadata.get(img)
                        w, h = meta['width'], meta['height']
                        needs_rotation = meta['needs_rotation']
                    except Exception:
                        try:
                            # image without metadata, try to just get the size
                            w, h = get_size(img)
                            needs_rotation = False
                        except Exception:
                            continue

                    thumb_width = \
                        (float(w) * min(h, thumbh) / h) if not needs_rotation else \
                        (float(h) * min(w, thumbh) / w)
                    self.js("set_dimensions('%s', '%s', '%d x %d', %d)" % (
                        util.path2url(img),
                        self.safe_basename(img),
                        w if not needs_rotation else h,
                        h if not needs_rotation else w,
                        thumb_width))

            self.select_in_browser(self.selected)

            self.loading_folder = False

        prepare_thread = threading.Thread(target=_prepare_thread)
        prepare_thread.daemon = True
        prepare_thread.start()

    def build_folder_info(self):
        parent_folder = self.get_parent_folder()

        nav_items = [
            self.get_command_item(
                'command:back' if self.get_back_folder() else None,
                self.get_back_folder(), 'back',
                group='Navigate', nofocus=True),
            self.get_command_item(
                'command:forward' if self.get_forward_folder() else None,
                self.get_forward_folder(), 'forward',
                group='Navigate', nofocus=True),
            self.get_command_item(
                'command:up' if parent_folder else None,
                parent_folder, 'up',
                group='Navigate', nofocus=True)
        ]

        categories = [{
            'label': 'Navigate',
            'no_labels': True,
            'items': nav_items,
        }]

        # Subfolders
        subfolders = self.filter_hidden([
            os.path.join(self.folder, f) for f in sorted(os.listdir(self.folder))
            if os.path.isdir(os.path.join(self.folder, f))
        ])

        parent_item = self.get_parent_folder_item()
        special_items = [parent_item] if parent_item else []
        subfolder_items = special_items + \
                          [self.get_folder_item(sub, group='Subfolders') for sub in subfolders]

        if subfolder_items:
            categories.append({
                'label': 'Subfolders',
                'items': subfolder_items
            })
        # # Siblings - TODO disabled for now, they look too similar to subfolders and confuse
        # if parent_folder:
        #     siblings = self.filter_hidden([
        #         os.path.join(parent_folder, f) for f in sorted(os.listdir(parent_folder))
        #         if os.path.isdir(os.path.join(parent_folder, f))])
        #     pos = siblings.index(self.folder)
        #     if pos + 1 < len(siblings):
        #         categories.append({
        #             'label': 'Next folder',
        #             'items': [self.get_folder_item(siblings[pos + 1])]
        #         })
        #
        # Bookmarks
        categories.append(self.build_bookmarks_category())
        # Options
        categories.append(self.build_options_category())

        folder_info = {
            'crumbs': self.get_crumbs(),
            'categories': categories
        }

        return folder_info

    def cache_around(self):
        if not hasattr(self, "images") or not self.images:
            return
        pos = self.images.index(
            self.selected) if self.selected in self.images else 0
        for i in [1, -1]:
            if pos + i < 0 or pos + i >= len(self.images):
                continue
            f = self.images[pos + i]
            if f not in self.pix_cache[self.zoom]:
                logging.info("Caching around: file %s, zoomed %s" %
                             (f, self.zoom))
                self.cache_queue.put((f, self.zoom))

    def start_cache_thread(self):
        import threading
        import Queue
        self.cache_queue = Queue.Queue()
        self.preparing_event = threading.Event()

        def _reduce_to_latest(cached, count):
            while len(cached) > count:
                cached.popitem(last=False)

        def _queue_thread():
            logging.info("Starting cache thread")
            while True:
                if len(self.pix_cache[False]) > CACHE_SIZE:
                    _reduce_to_latest(self.pix_cache[False], CACHE_SIZE / 2)
                if len(self.pix_cache[True]) > CACHE_SIZE:
                    _reduce_to_latest(self.pix_cache[True], CACHE_SIZE / 2)

                path, zoom = self.cache_queue.get()

                try:
                    if path not in self.pix_cache[zoom]:
                        logging.debug(
                            "Cache thread loads file %s, zoomed %s" % (path, zoom))
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

    def thumb_ready(self, img, thumb_path):
        self.js("add_image('%s', '%s')" %
                (util.path2url(img), util.path2url(thumb_path)))
        if img == self.selected:
            self.select_in_browser(img)

    def thumb_failed(self, img, error_msg):
        self.js("remove_image_div('%s')" % util.path2url(img))
        logging.warning("Could not add thumb for " + img)

    def set_margins(self, margin):
        self.margin = margin

        def _f():
            self.scroll_window.set_margin_right(margin)
            self.scroll_window.set_margin_left(margin)
            self.scroll_window.set_margin_bottom(margin)
            self.scroll_window.set_margin_top(margin)

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
        if options['fullscreen']:
            return self.window.get_screen().get_width()
        elif self.manually_resized:
            self.last_windowed_image_width = \
                self.window.get_window().get_width() - 2 * self.margin
            return self.last_windowed_image_width
        elif options['maximized']:
            if self.window.get_window():
                return self.window.get_window().get_width() - 2 * self.margin
            else:
                return self.window.get_screen().get_width() - 40 - 2 * self.margin
        else:
            self.last_windowed_image_width = self.get_recommended_size()[0] - 2 * self.margin
            return self.last_windowed_image_width

    def get_max_image_height(self):
        if options['fullscreen']:
            return self.window.get_screen().get_height()
        elif self.manually_resized:
            self.last_windowed_image_height = \
                self.window.get_window().get_height() - 2 * self.margin
            return self.last_windowed_image_height
        elif options['maximized']:
            if self.window.get_window():
                return self.window.get_window().get_height() - 2 * self.margin
            else:
                return self.window.get_screen().get_height() - 40 - 2 * self.margin
        else:
            self.last_windowed_image_height = self.get_recommended_size()[1] - 2 * self.margin
            return self.last_windowed_image_height

    def increase_size(self):
        if self.manually_resized or self.zoom or options['fullscreen']:
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
            [f for f in self.images
             if os.path.basename(f).lower().find(search) >= 0
             or (self.get_group_key(f) or '').find(search) >= 0]
        filename = None
        position = start_position - direction if start_position is not None \
            else applicable.index(self.selected)
        position = max(0, min(len(applicable) - 1, position + direction))
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
            full = not options['fullscreen']
        options['fullscreen'] = full
        config.save_options()

        self.pix_cache[False].clear()

        if not first_run and self.shown:
            width = height = None
            if not options['fullscreen']:
                width = getattr(self, "last_windowed_image_width", None)
                height = getattr(self, "last_windowed_image_height", None)
            # caches the new image before we start changing sizes
            self.get_pixbuf(self.shown, force=True, width=width, height=height)
            self.box.set_visible(False)

        self.update_margins()
        if options['fullscreen']:
            self.window.fullscreen()
        elif not first_run:
            self.window.unfullscreen()
        self.last_automatic_resize = time.time()

        self.update_cursor()
        self.js('toggle_fullscreen(' + ('true' if full else 'false') + ')')
        self.js('setTimeout(scroll_to_selected, 100)')

    def update_margins(self):
        if options['fullscreen']:
            self.make_transparent(
                self.window,
                color='rgba(77, 75, 69, 1)' if self.mode == 'folder' else 'rgba(0, 0, 0, 1)')
            self.set_margins(0)
        else:
            self.make_transparent(
                self.window,
                # Note: for non-fullscreen browsing transparency:
                # color='rgba(77, 75, 69, 0.9)' if self.mode == 'folder' else 'rgba(77, 75, 69, 0.9)')
                color='rgba(77, 75, 69, 1)' if self.mode == 'folder' else 'rgba(77, 75, 69, 0.9)')
            self.set_margins(15)

    def update_cursor(self):
        if self.mousedown_zoomed:
            self.set_cursor(Gdk.CursorType.HAND1)
        elif self.mousedown_panning:
            self.set_cursor(Gdk.CursorType.HAND1)
        elif options['fullscreen'] and self.mode == 'image':
            self.set_cursor(Gdk.CursorType.BLANK_CURSOR)
        else:
            self.set_cursor(Gdk.CursorType.ARROW)

    def set_cursor(self, cursor):
        if self.window.get_window() and (
                not self.window.get_window().get_cursor()
                or cursor != self.window.get_window().get_cursor().get_cursor_type()):
            self.window.get_window().set_cursor(
                Gdk.Cursor.new_for_display(Gdk.Display.get_default(), cursor))

    def set_mode(self, mode):
        def _go():
            self.mode = mode
            if self.mode == "image" and self.selected != self.shown:
                self.show(self.selected)
            elif self.mode == "folder":
                self.shown = None
                self.window.set_title(self.folder)
                if hasattr(self, 'web_view'):
                    self.web_view.grab_focus()

            self.update_cursor()
            self.scroll_window.set_visible(self.mode == 'image')
            self.image.set_visible(self.mode == 'image')
            self.browser.set_visible(self.mode == 'folder')
            self.update_margins()
            self.js("set_mode('%s')" % self.mode)

            if self.mode == 'folder' and not self.manually_resized:
                self.resize_and_center(*self.get_recommended_size())

        GObject.idle_add(_go)

    def exit(self, *args):
        """
        Makes sure we'll exit regardless of GTK/multithreading/multiprocessing hiccups
        """
        import threading

        def _exit(*args):
            self.thumbs.stop()
            GObject.idle_add(Gtk.main_quit)

        # attempt a standard exit
        threading.Timer(0, _exit).start()

        # if failed, suicide with SIGKILL after 2 seconds
        def _suicide():
            import os
            import logging
            logging.warning('Exiting via suicide')
            os.kill(os.getpid(), 9)

        suicide_timer = threading.Timer(2, _suicide)
        suicide_timer.daemon = True
        suicide_timer.start()

    def check_letter_shortcut(self, event, hw_keycodes, mask=0):
        return (
            event and
            (mask == event.state == 0 or (event.state & mask != 0)) and
            event.hardware_keycode in hw_keycodes
        )

    def toggle_search(self, visible, bypass_search=False):
        self.is_in_search = visible
        self.js("toggle_search(%s, %s)" % ('true' if visible else 'false',
                                           'true' if bypass_search else 'false'))

    def process_key(self, widget=None, event=None, key=None, skip_browser=False):
        if event:
            # prevent processing duplicate events that happen sometimes when focusing web_view
            if event.time == getattr(self, 'last_key_event_time', None):
                return
            setattr(self, 'last_key_event_time', event.time)

        key = key or Gdk.keyval_name(event.keyval)
        if key == 'Escape' and (self.mode == 'image' or skip_browser):
            if self.mode == 'folder' and self.is_in_search:
                self.toggle_search(False)
            else:
                self.exit()
        elif key == "F11":
            self.toggle_fullscreen()
        elif key == 'F5':
            if event and event.state & Gdk.ModifierType.CONTROL_MASK and self.mode == "folder":
                self.thumbs.clear_thumbnails(self.folder)
            self.show(self.selected if self.mode == 'image' else self.folder)
        elif key == 'Return':
            if self.mode == 'image':
                self.set_mode('folder')
            else:
                prev = self.selected  # save selected from before the action, as it might change it
                self.show()
                if os.path.isfile(prev):
                    self.set_mode('image')
        elif self.mode == 'folder':
            if hasattr(self, 'web_view'):
                self.web_view.grab_focus()

            if key == 'Left' and event and (event.state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK)):
                self.folder_history_back()
            elif key == 'Right' and event and (
                    event.state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK)):
                self.folder_history_forward()
            elif key == 'Up' and event and (event.state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK)):
                self.folder_parent()
            elif (key == 'plus' or key == 'equal') and event and (event.state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK)):
                self.increase_thumb_height()
            elif key == 'minus' and event and (event.state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK)):
                self.decrease_thumb_height()
            elif self.check_letter_shortcut(event, [41], mask=Gdk.ModifierType.CONTROL_MASK):  # Ctrl-F
                self.toggle_search(True)
            elif key in ('Tab', 'ISO_Left_Tab'):
                self.js("on_key('%s')" % 'Tab')
            elif not skip_browser:
                self.js("on_key('%s')" % key)
            elif key == 'BackSpace':
                if not self.is_in_search:
                    self.folder_parent()

        elif key in ("Right", "Down", "Page_Down"):
            GObject.idle_add(lambda: self.go(1))
        elif key in ("Left", "Up", "Page_Up"):
            GObject.idle_add(lambda: self.go(-1))
        elif key == "Home":
            GObject.idle_add(lambda: self.go(1, 0))
        elif key == "End":
            GObject.idle_add(lambda: self.go(-1, len(self.images) - 1))
        elif self.check_letter_shortcut(event, [52]):  # Z
            self.set_zoom(not self.zoom)
            self.refresh_image()
            self.update_zoomed_views()
        elif self.check_letter_shortcut(event, [10, 19]):  # 1, 0
            self.set_zoom(True)
            self.refresh_image()
            self.update_zoomed_views()
        elif key in ("slash", "asterisk"):
            self.set_zoom(False)
            self.refresh_image()
            self.update_zoomed_views()

    def increase_thumb_height(self):
        bigger = [th for th in THUMBHEIGHTS if th > options['thumb_height']]
        if bigger:
            options['thumb_height'] = bigger[0]
            self.change_to_folder(self.folder)

    def decrease_thumb_height(self):
        smaller = [th for th in THUMBHEIGHTS if th < options['thumb_height']]
        if smaller:
            options['thumb_height'] = smaller[-1]
            self.change_to_folder(self.folder)

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
            self.set_zoom(
                True,
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
                    self.set_zoom(
                        True,
                        min(1, max(0, x - 100) / max(1, self.get_width() - 200)),
                        min(1, max(0, y - 100) / max(1, self.get_height() - 200)))
                    self.refresh_image()
                    self.update_zoomed_views()
                    self.update_cursor()

            GObject.timeout_add(20, act)

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
        self.mousedown_zoomed = False
        self.mousedown_panning = False
        self.update_cursor()

    def scrolled(self, widget, event):
        if self.mode != "image" or self.zoom:
            return
        if event.direction not in (
                Gdk.ScrollDirection.UP,
                Gdk.ScrollDirection.LEFT,
                Gdk.ScrollDirection.DOWN,
                Gdk.ScrollDirection.RIGHT):
            return

        wheel_timer = getattr(self, "wheel_timer", None)
        if wheel_timer:
            GObject.source_remove(wheel_timer)

        direction = -1 if event.direction in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.LEFT) \
            else 1
        self.wheel_timer = GObject.timeout_add(100, lambda: self.go(direction))

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

        orientation = None
        image_width = image_height = None
        meta = metadata.get(filename)
        if meta:
            orientation = meta['orientation']
            image_width, image_height = meta['width'], meta['height']

        enlarge_smaller = options['enlarge_smaller']
        if not image_width:
            format, image_width, image_height = GdkPixbuf.Pixbuf.get_file_info(filename)

        pixbuf = None

        if not pixbuf:
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(filename)
                logging.debug("Loaded directly")
            except GObject.GError:
                pass  # below we'll use another method

        if not pixbuf:
            try:
                full_meta = meta.get('full_meta',
                                     metadata.get_full(filename))
                preview = full_meta.previews[-1].data
                pixbuf = pixbuf_from_data(preview)
                logging.debug("Loaded from preview")
            except Exception, e:
                pass  # below we'll use another method

        if not pixbuf:
            pixbuf = pil_to_pixbuf(get_pil(filename))
            logging.debug("Loaded with PIL")

        pixbuf = auto_rotate_pixbuf(orientation, pixbuf)
        if orientation in (5, 6, 7, 8):
            # needs rotation
            image_width, image_height = image_height, image_width

        if not zoom:
            target_width = image_width if zoom else (
                width if enlarge_smaller else min(width, image_width))
            target_height = image_height if zoom else (
                height if enlarge_smaller else min(height, image_height))

            if float(target_width) / target_height < float(image_width) / image_height:
                pixbuf = pixbuf.scale_simple(
                    target_width,
                    int(float(target_width) * image_height / image_width),
                    GdkPixbuf.InterpType.BILINEAR)
            else:
                pixbuf = pixbuf.scale_simple(
                    int(float(target_height) * image_width / image_height),
                    target_height,
                    GdkPixbuf.InterpType.BILINEAR)
        if filename in self.pix_cache[zoom]:
            del self.pix_cache[zoom][filename]  # we use OrderedDict for LRU, this makes sure filename will now be last
        self.pix_cache[zoom][filename] = pixbuf, width, time.time()

        return pixbuf


if __name__ == "__main__":
    Ojo()
