#!/usr/bin/env python2
#! -*- coding: utf-8 -*-
from gi.repository import GObject, Gtk, Gdk, GdkPixbuf, WebKit
import cairo
import sys
import os

def b64(img):
    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(img, 800, 600, True)
    return pixbuf.save_to_bufferv('png', [], [])[1].encode("base64").replace('\n', '')

def make_transparent(widget):
    rgba = Gdk.RGBA()
    rgba.parse('rgba(0, 0, 0, 0)')
    widget.override_background_color(Gtk.StateFlags.NORMAL, rgba)

def area_draw(widget, cr):
    cr.set_source_rgba(77.0/255, 75.0/255, 69.0/255, 0.9)
    cr.set_operator(cairo.OPERATOR_SOURCE)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)

class Cl:
    def main(self):
        Gtk.init(sys.argv)

        window = Gtk.Window()
        window.resize(800, 600)
        window.set_title("Webkit tests window")          # Window's title
        window.move(100, 100)
        window.connect('destroy', lambda x: Gtk.main_quit())  # Connect signal 'destroy'
        window.set_decorated(False)

        self.screen = window.get_screen()

        self.visual = self.screen.get_rgba_visual()
        if self.visual and self.screen.is_composited():
            window.set_visual(self.visual)
        window.set_app_paintable(True)
        window.connect("draw", area_draw)

        box = Gtk.VBox()
        box.set_margin_top(30)
        box.set_margin_bottom(30)
        box.set_margin_left(30)
        box.set_margin_right(30)
        make_transparent(box)
        window.add(box)

        folder = '/d/Pics/Wallpapers/Favorites/'
        images = sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.jpg'))
        self.current = images[0]

        self.web_view = WebKit.WebView()
        self.web_view.set_transparent(True)
        make_transparent(self.web_view)
        self.web_view.set_can_focus(True)
        self.web_view.load_string("<html><body style='background: rgba(0, 0, 0, 0); color: white;'><img id='i' src='data:image/png;base64," +
                                  b64(self.current) + "'/></body></html>", "text/html", "UTF-8", "file://" + os.path.dirname(__file__) + "/")
        box.add(self.web_view)

        window.show_all()

        def go(*args):
            self.current = images[(images.index(self.current) + 1) % len(images)]
            nextt = b64(self.current)
            self.web_view.execute_script("document.getElementById('i').setAttribute('src', 'data:image/png;base64," + nextt + "')")
#            self.web_view.execute_script("document.getElementById('i').setAttribute('src', '" + self.current + "')")

        window.connect('button-press-event', go)

        Gtk.main()                   # Start the application

Cl().main()