#!/usr/bin/python

import cairo
from gi.repository import Gtk, Gdk, GdkPixbuf, GObject, WebKit
import os
import sys

class Ojo(Gtk.Window):
    def __init__(self):
        super(Ojo, self).__init__()
        self.full = False
        self.screen = self.get_screen()
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_decorated(False)
        self.maximize()

        self.visual = self.screen.get_rgba_visual()
        if self.visual and self.screen.is_composited():
            self.set_visual(self.visual)
        self.set_app_paintable(True)
        self.connect("draw", self.area_draw)

        self.box = Gtk.VBox()
        self.image = Gtk.Image()
        self.box.add(self.image)
        self.add(self.box)

        self.set_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.SCROLL_MASK)

    def main(self):
        self.show(os.path.normpath(sys.argv[1]))
        self.show_all()
        GObject.idle_add(self.after_quick_start)
        Gtk.main()

    def area_draw(self, widget, cr):
        if self.full:
            cr.set_source_rgba(0, 0, 0, 1.0)
        else:
            cr.set_source_rgba(77.0/255, 75.0/255, 69.0/255, 0.9)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

    def show(self, filename=None):
        if filename:
            print filename
        self.current = filename or self.current
        self.set_title(self.current)
        width = self.screen.get_width() if self.full else self.screen.get_width() - 100
        height = self.screen.get_height() if self.full else self.screen.get_height() - 200
        self.pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(self.current, width, height, True)
        self.image.set_from_pixbuf(self.pixbuf)
        #self.set_icon(self.pixbuf)

        if not self.full:
            self.box.set_margin_right(30)
            self.box.set_margin_left(30)
            self.box.set_margin_bottom(30)
            self.box.set_margin_top(30)

            self.real_width = self.pixbuf.get_width() + 60
            self.real_height = self.pixbuf.get_height() + 60
            self.resize(self.real_width, self.real_height)
            self.move(
                (self.screen.get_width() - self.real_width) // 2,
                (self.screen.get_height() - self.real_height) // 2)
        else:
            self.box.set_margin_right(0)
            self.box.set_margin_left(0)
            self.box.set_margin_bottom(0)
            self.box.set_margin_top(0)


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
            self.get_window().set_cursor(Gdk.Cursor.new_for_display(Gdk.Display.get_default(), Gdk.CursorType.BLANK_CURSOR))
            self.fullscreen()
        else:
            self.get_window().set_cursor(Gdk.Cursor.new_for_display(Gdk.Display.get_default(), Gdk.CursorType.ARROW))
            self.unfullscreen()

    def set_mode(self, mode):
        self.mode = mode
        self.image.set_visible(self.mode == 'image')
        self.browser.set_visible(self.mode == 'folder')

    def process_key(self, widget, event):
        key = Gdk.keyval_name(event.keyval)
        if key == 'Escape':
            Gtk.main_quit()
        elif key in ("f", "F", "F11"):
            self.toggle_fullscreen()
            self.show()
        elif key in ("Right", "Left") and self.mode == "image":
            GObject.idle_add(lambda: self.go(1 if key == "Right" else -1))
        elif key == 'Return':
            modes = ["image", "folder"]
            self.set_mode(modes[(modes.index(self.mode) + 1) % len(modes)])
        else:
            return False

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
        self.images = filter(self.is_image, map(lambda f: os.path.join(self.folder, f), sorted(os.listdir(self.folder))))
        print self.images

        self.thumbs = {}
        GObject.idle_add(self.render_browser)

    def is_image(self, filename):
        return filename.lower().endswith(('.jpg', '.jpeg', '.gif', '.png', '.tiff', '.svg', '.bmp'))

    def render_browser(self):
        with open(os.path.join(os.path.dirname(os.path.normpath(__file__)), 'browse.html')) as f:
            html = f.read()

        self.web_view = WebKit.WebView()
        self.web_view.set_transparent(True)

        def nav(wv, wf, req, action, policy):
            import urllib
            import re
            import time
            if not action.get_original_uri().startswith('ojo:'):
                return False
            self.show(urllib.unquote(re.sub('^ojo:', '', action.get_original_uri())))
            self.from_browser_time = time.time()
            self.set_mode("image")
            policy.ignore()
            return True
        self.web_view.connect("navigation-policy-decision-requested", nav)

        self.web_view.load_string(html, "text/html", "UTF-8", "file://")
        self.web_view.set_visible(True)
        rgba = Gdk.RGBA()
        rgba.parse('rgba(0, 0, 0, 0)')
        self.web_view.override_background_color(Gtk.StateFlags.NORMAL, rgba)
        self.browser.add(self.web_view)

        GObject.idle_add(self.prepare_thumbs)

    def prepare_thumbs(self):
        for img in self.images:
            if not img in self.thumbs:
                self.thumbs[img] = True
                try:
                    b64 = self.b64(img).replace('\n', '')
                    self.web_view.execute_script("add_image('%s', '%s', %s)" % (img, b64, 'true' if img==self.current else 'false'))
                except Exception, e:
                    print str(e)
                GObject.idle_add(self.prepare_thumbs)
                return

    def b64(self, img):
        from PIL import Image
        import StringIO
        x = Image.open(img)
        x.thumbnail((100000, 100))
        output = StringIO.StringIO()
        x.save(output, "PNG")
        contents = output.getvalue().encode("base64")
        output.close()
        return contents

if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    Ojo().main()