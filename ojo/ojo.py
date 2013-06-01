#!/usr/bin/python

import cairo
from gi.repository import Gtk, Gdk, GdkPixbuf, GObject
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
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.add_events(Gdk.EventMask.SCROLL_MASK)

        self.visual = self.screen.get_rgba_visual()
        if self.visual and self.screen.is_composited():
            self.set_visual(self.visual)
        self.set_app_paintable(True)
        self.connect("draw", self.area_draw)

        self.image = Gtk.Image()
        self.add(self.image)

    def main(self):
        self.show(sys.argv[1])
        self.show_all()
        GObject.idle_add(self.after_quick_start)
        Gtk.main()

    def area_draw(self, widget, cr):
        if self.full:
            cr.set_source_rgba(0, 0, 0, 1.0)
        else:
            cr.set_source_rgba(77.0/255, 75.0/255, 69.0/255, 0.90)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

    def show(self, filename=None):
        if filename:
            print filename
        self.current = filename or self.current
        width = self.screen.get_width() if self.full else self.screen.get_width() - 100
        height = self.screen.get_height() if self.full else self.screen.get_height() - 200
        self.pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(self.current, width, height, True)
        self.image.set_from_pixbuf(self.pixbuf)
        #self.set_icon(self.pixbuf)

        if not self.full:
            self.image.set_margin_right(30)
            self.image.set_margin_left(30)
            self.image.set_margin_bottom(30)
            self.image.set_margin_top(30)

            self.real_width = self.pixbuf.get_width() + 60
            self.real_height = self.pixbuf.get_height() + 60
            self.resize(self.real_width, self.real_height)
            self.move((self.screen.get_width() - self.real_width) // 2, (self.screen.get_height() - self.real_height) // 2)
        else:
            self.image.set_margin_right(0)
            self.image.set_margin_left(0)
            self.image.set_margin_bottom(0)
            self.image.set_margin_top(0)


    def go(self, direction):
        try:
            self.position += direction + len(self.images)
            self.position %= len(self.images)
            filename = os.path.join(self.folder, self.images[self.position])
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

    def process_key(self, widget, event):
        key = Gdk.keyval_name(event.keyval)
        if key == 'Escape':
            Gtk.main_quit()
        elif key in ("f", "F", "F11"):
            self.toggle_fullscreen()
            self.show()
        elif key in ("Right", "Left"):
            GObject.idle_add(lambda: self.go(1 if key == "Right" else -1))

    def clicked(self, widget, event):
        self.go(-1 if event.x < 0.5 * self.real_width else 1)

    def scrolled(self, widget, event):
        if event.direction not in (
            Gdk.ScrollDirection.UP, Gdk.ScrollDirection.LEFT, Gdk.ScrollDirection.DOWN, Gdk.ScrollDirection.RIGHT):
            return

        if getattr(self, "wheel_timer", None):
            GObject.source_remove(self.wheel_timer)

        direction = -1 if event.direction in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.LEFT) else 1
        self.wheel_timer = GObject.timeout_add(100, lambda: self.go(direction))

    def after_quick_start(self):
        self.connect("delete-event", Gtk.main_quit)
        self.connect("key-press-event", self.process_key)
        self.connect("focus-out-event", Gtk.main_quit)
        self.connect("button-release-event", self.clicked)
        self.connect("scroll-event", self.scrolled)
        self.folder = os.path.dirname(self.current)
        self.images = os.listdir(self.folder)
        self.position = self.images.index(os.path.basename(self.current))

if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    Ojo().main()