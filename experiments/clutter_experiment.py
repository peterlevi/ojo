#!/usr/bin/env python2
#! -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
from gi.repository import GObject, Gtk, Gdk, GtkClutter, Clutter, GdkPixbuf, Cogl, WebKit
import cairo
import sys
import os

def get_texture(img):
    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(img, 800, 600, True)

    t = Clutter.Texture()
    t.set_from_rgb_data(pixbuf.get_pixels(),
                        pixbuf.get_has_alpha(),
                        pixbuf.get_width(),
                        pixbuf.get_height(),
                        pixbuf.get_rowstride(),
                        4 if pixbuf.get_has_alpha() else 3,
                        Clutter.TextureFlags.NONE)
    return t

#    image = Gtk.Image()
#    image.set_from_pixbuf(pixbuf)
#    return GtkClutter.Actor.new_with_contents(image)

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
    #    Clutter.init(sys.argv)
        Gtk.init(sys.argv)
        GtkClutter.init(sys.argv)

        window = Gtk.Window()
        window.resize(800, 600)
        window.set_title("Clutter tests window")          # Window's title
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

        embed = GtkClutter.Embed()
        make_transparent(embed)
        box.add(embed)

        stage = embed.get_stage()
    #    stage = Clutter.Stage()     # Create the Stage
        color = Clutter.Color.new(77, 75, 69, 0.9 * 255)
        stage.set_use_alpha(True)
        stage.set_color(color)
        #stage.set_opacity(128)
        stage.set_size(800, 600)
        stage.set_title("Clutter tests stage")          # Window's title
        #stage.set_fullscreen(True)

        layout = Clutter.BinLayout()
        stage.set_layout_manager(layout)
#
        folder = '/d/Pics/Wallpapers/Favorites/'
        images = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.jpg')]
        self.current = images[1]

        self.current_texture = get_texture(self.current)
        stage.add_actor(self.current_texture)

        web_view = WebKit.WebView()
        web_view.set_transparent(True)
        make_transparent(web_view)
        web_view.set_can_focus(True)
        web_view.load_string("<html><body style='background: rgba(100, 0, 0, 0.5); color: white;'>AAAAAAAAAAA</body></html>", "text/html", "UTF-8", "file://" + os.path.dirname(__file__) + "/")
        web_view_actor = GtkClutter.Actor.new_with_contents(web_view)
#        web_view_actor.set_width(800)
        make_transparent(web_view_actor.get_widget())
        layout.add(web_view_actor, Clutter.BinAlignment.FILL, Clutter.BinAlignment.END)
#        web_view_actor.set_opacity(0)
#        web_view_actor.animatev(Clutter.AnimationMode.EASE_OUT_SINE, 1000, ["opacity"], [255])

        #    stage.show_all()
        window.show_all()

        def go(*args):
            self.current = images[(images.index(self.current) + 1) % len(images)]
            nextt = get_texture(self.current)
            nextt.set_opacity(0)
            nextt.set_x((stage.get_width() - nextt.get_width()) / 2)
            nextt.set_y((stage.get_height() - nextt.get_height()) / 2)
            stage.add_actor(nextt)
            def a():
                a1 = self.current_texture.animatev(Clutter.AnimationMode.EASE_OUT_SINE, 250, ["opacity"], [0])
                nextt.animatev(Clutter.AnimationMode.EASE_OUT_SINE, 250, ["opacity"], [255])
                previoust = self.current_texture
                self.current_texture = nextt
                a1.connect('completed', lambda x: previoust.destroy())
                stage.raise_child(web_view_actor, None)
            GObject.idle_add(a)

        stage.connect('button-press-event', go)

    #    Clutter.main()                   # Start the application
        Gtk.main()                   # Start the application

Cl().main()