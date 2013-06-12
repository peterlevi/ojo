#!/usr/bin/python
# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
### BEGIN LICENSE
# Copyright (c) 2012, Peter Levi <peterlevi@peterlevi.com>
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


import cairo
from gi.repository import Gtk, Gdk, GdkPixbuf, GObject, Gio, WebKit
from pyexiv2 import ImageMetadata
import os
import sys

class Ojo(Gtk.Window):
    def __init__(self):
        super(Ojo, self).__init__()
        self.full = False
        self.screen = self.get_screen()
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_decorated(False)
        #self.maximize()

        self.visual = self.screen.get_rgba_visual()
        if self.visual and self.screen.is_composited():
            self.set_visual(self.visual)
        self.set_app_paintable(True)
        self.connect("draw", self.area_draw)

        self.box = Gtk.VBox()
        self.box.set_visible(True)
        self.image = Gtk.Image()
        self.image.set_visible(True)
        self.box.add(self.image)
        self.add(self.box)

        self.set_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.SCROLL_MASK)

    def main(self):
        path = os.path.realpath(sys.argv[1])
        print "Started with: " + path
        if os.path.isfile(path):
            self.mode = 'image'
            self.show(path)
            GObject.idle_add(self.after_quick_start)
        else:
            self.mode = 'folder'
            self.current = os.path.join(path, 'none')
            self.after_quick_start()
            self.set_mode('folder')
            self.show(self.images[0], True)

        self.set_visible(True)
        Gtk.main()

    def area_draw(self, widget, cr):
        if self.full:# and self.mode == "image":
            cr.set_source_rgba(0, 0, 0, 1.0)
        else:
            cr.set_source_rgba(77.0/255, 75.0/255, 69.0/255, 0.9)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

    def update_browser(self, file):
        self.web_view.execute_script("select('%s')" % file)

    def show(self, filename=None, force_resize=False):
        if filename:
            print filename
        self.current = filename or self.current
        self.set_title(self.current)
        if getattr(self, "web_view", None):
            self.update_browser(self.current)
        if self.mode == 'image' or force_resize:
            width = self.screen.get_width() if self.full else self.screen.get_width() - 150
            height = self.screen.get_height() if self.full else self.screen.get_height() - 150
            try:
                self.pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(self.current, width, height, True)
            except GObject.GError:
                self.pixbuf = self.pixbuf_from_data(self.attempt_preview_data(self.current), width, height)
            self.image.set_from_pixbuf(self.pixbuf)
            self.update_margins(force_resize)

    def attempt_preview_data(self, img):
        meta = ImageMetadata(img)
        meta.read()
        return meta.previews[-1].data

    def set_margins(self, margin):
        self.box.set_margin_right(margin)
        self.box.set_margin_left(margin)
        self.box.set_margin_bottom(margin)
        self.box.set_margin_top(margin)

    def update_margins(self, force_resize=False):
        if self.mode == 'folder':
            self.set_margins(15)
        elif self.full:
            self.set_margins(0)
        else:
            self.set_margins(30)

        if self.mode == "image" or force_resize:
            self.real_width = self.pixbuf.get_width() + 60
            self.real_height = self.pixbuf.get_height() + 60
            self.resize(self.real_width, self.real_height)
            self.move((self.screen.get_width() - self.real_width) // 2,
                (self.screen.get_height() - self.real_height) // 2)

    def go(self, direction):
        filename = None
        try:
            position = self.images.index(self.current)
            position = (position + direction + len(self.images)) % len(self.images)
            filename = self.images[position]
            self.show(filename)
            return
        except Exception, ex:
            print str(ex), filename
            GObject.idle_add(lambda: self.go(direction))

    def toggle_fullscreen(self, full=None):
        if full is None:
            full = not self.full
        self.full = full
        if self.full:
            self.fullscreen()
        else:
            self.unfullscreen()
        self.update_cursor()
        self.update_margins()

    def update_cursor(self):
        if self.get_window():
            self.get_window().set_cursor(Gdk.Cursor.new_for_display(Gdk.Display.get_default(),
                Gdk.CursorType.BLANK_CURSOR if self.full and self.mode == 'image' else Gdk.CursorType.ARROW))

    def set_mode(self, mode):
        self.mode = mode
        if self.mode == 'image':
            self.show()
        self.image.set_visible(self.mode == 'image')
        self.browser.set_visible(self.mode == 'folder')
        self.update_cursor()
        self.update_margins()

    def process_key(self, widget, event):
        key = Gdk.keyval_name(event.keyval)
        print key
        if key == 'Escape':
            Gtk.main_quit()
        elif key in ("f", "F", "F11"):
            self.toggle_fullscreen()
            self.show()
        elif key == 'Return':
            modes = ["image", "folder"]
            self.set_mode(modes[(modes.index(self.mode) + 1) % len(modes)])
        elif self.mode == 'folder':
            self.web_view.execute_script("on_key('%s')" % key)
        elif key in ("Right", "Down", "Page_Down", "space"):
            GObject.idle_add(lambda: self.go(1))
        elif key in ("Left", "Up", "Page_Up", "BackSpace"):
            GObject.idle_add(lambda: self.go(-1))

    def clicked(self, widget, event):
        import time
        if self.mode != "image":
            return
        if time.time() - self.from_browser_time < 0.2:
            return
        if event.button == 1:
            self.go(-1 if event.x < 0.5 * self.real_width else 1)

    def scrolled(self, widget, event):
        if self.mode != "image":
            return
        if event.direction not in (
            Gdk.ScrollDirection.UP, Gdk.ScrollDirection.LEFT, Gdk.ScrollDirection.DOWN, Gdk.ScrollDirection.RIGHT):
            return

        if getattr(self, "wheel_timer", None):
            GObject.source_remove(self.wheel_timer)

        direction = -1 if event.direction in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.LEFT) else 1
        self.wheel_timer = GObject.timeout_add(100, lambda: self.go(direction))

    def after_quick_start(self):
        self.mode = "image"
        self.from_browser_time = 0

        self.browser = Gtk.ScrolledWindow()
        self.browser.set_visible(False)
        rgba = Gdk.RGBA()
        rgba.parse('rgba(0, 0, 0, 0)')
        self.browser.override_background_color(Gtk.StateFlags.NORMAL, rgba)
        self.box.add(self.browser)

        self.connect("delete-event", Gtk.main_quit)
        self.connect("key-press-event", self.process_key)
        #self.connect("focus-out-event", Gtk.main_quit)
        self.connect("button-release-event", self.clicked)
        self.connect("scroll-event", self.scrolled)
        self.folder = os.path.dirname(self.current)
        self.images = filter(os.path.isfile, map(lambda f: os.path.join(self.folder, f), sorted(os.listdir(self.folder))))

        GObject.idle_add(self.render_browser)

    def render_browser(self):
        with open(os.path.join(os.path.dirname(os.path.normpath(__file__)), 'browse.html')) as f:
            html = f.read()

        self.web_view = WebKit.WebView()
        self.web_view.set_transparent(True)

        def nav(wv, wf, req, action, policy):
            import urllib
            import re
            import time

            url = action.get_original_uri()
            if not url.startswith('ojo:') and not url.startswith('ojo-select:'):
                return False
            self.current = urllib.unquote(re.sub('^ojo.*:', '', url))
            if url.startswith('ojo:'):
                def _do():
                    self.show()
                    self.from_browser_time = time.time()
                    self.set_mode("image")
                GObject.idle_add(_do)
            policy.ignore()
            return True
        self.web_view.connect("navigation-policy-decision-requested", nav)

        self.web_view.connect('document-load-finished', lambda wf, data: self.prepare_thumbs()) # Load page

        self.web_view.load_string(html, "text/html", "UTF-8", "file://" + os.path.dirname(__file__) + "/")
        self.web_view.set_visible(True)
        rgba = Gdk.RGBA()
        rgba.parse('rgba(0, 0, 0, 0)')
        self.web_view.override_background_color(Gtk.StateFlags.NORMAL, rgba)
        self.browser.add(self.web_view)

    def add_thumb(self, img):
        try:
            b64 = self.b64(img)
            self.web_view.execute_script(
                "add_image('%s', '%s', %s)" %
                (img, b64, 'true' if img==self.current else 'false'))
            if img == self.current:
                self.update_browser(img)
        except Exception, e:
            print str(e)

    def prepare_thumbs(self, position=None, images=None):
        if not position:
            position = self.images.index(self.current)
            images = self.images[position:] + self.images[:position]
            position = 0
        if position < len(images):
            self.add_thumb(images[position])
            GObject.idle_add(lambda: self.prepare_thumbs(position + 1, images))

    def pixbuf_from_data(self, data, width, height):
        input_str = Gio.MemoryInputStream.new_from_data(data, None)
        pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(input_str, width, height, True, None)
        return pixbuf

    def b64(self, img, width=500, height=120):
        from PIL import Image
        import cStringIO
        meta = ImageMetadata(img)
        meta.read()
        try:
            pil_image = Image.open(img)
        except IOError:
            pil_image = Image.open(cStringIO.StringIO(meta.previews[-1].data))
        pil_image = self.auto_rotate(meta, pil_image)
        pil_image.thumbnail((width, height), Image.ANTIALIAS)
        output = cStringIO.StringIO()
        pil_image.save(output, "PNG")
        contents = output.getvalue().encode("base64")
        output.close()
        return contents.replace('\n', '')

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
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    Ojo().main()
