#!/usr/bin/env python2
#! -*- coding: utf-8 -*-
from gi.repository import GObject, Gtk, GtkClutter, Clutter, GdkPixbuf, Cogl
import sys
import os

def get_texture(img):
    t = Clutter.Texture()
    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(img, 800, 600, True)
    t.set_from_rgb_data(pixbuf.get_pixels(),
                        pixbuf.get_has_alpha(),
                        pixbuf.get_width(),
                        pixbuf.get_height(),
                        pixbuf.get_rowstride(),
                        4 if pixbuf.get_has_alpha() else 3,
                        Clutter.TextureFlags.NONE)
    return t

global current
global t
current = None
t = None

if __name__ == '__main__':
    Clutter.init(sys.argv)
    stage = Clutter.Stage()     # Create the Stage
    stage.set_size(800, 600)
    stage.set_title("Clutter tests")          # Window's title
    stage.connect('destroy', lambda x: Clutter.main_quit())  # Connect signal 'destroy'

    folder = '/media/data/Pics/Wallpapers/'
    images = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.jpg')]
    current = images[0]

    t = get_texture(current)
    stage.add_actor(t)
    stage.show_all()

    def go(*args):
        global current
        global t
        current = images[(images.index(current) + 1) % len(images)]
        nextt = get_texture(current)
        nextt.set_opacity(0)
        stage.add_actor(nextt)
        t.animatev(Clutter.AnimationMode.EASE_OUT_SINE, 300, ["opacity"], [0])
        nextt.animatev(Clutter.AnimationMode.EASE_OUT_SINE, 300, ["opacity"], [255])
        previoust = t
        t = nextt
        GObject.timeout_add(1000, lambda: previoust.destroy())

    stage.connect('button-press-event', go)

    Clutter.main()                   # Start the application