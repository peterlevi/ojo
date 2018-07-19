from gi.repository import Gtk, Gdk, GdkPixbuf, GObject, WebKit


def make_transparent(widget, color='rgba(0, 0, 0, 0)'):
    rgba = Gdk.RGBA()
    rgba.parse(color)
    widget.override_background_color(Gtk.StateFlags.NORMAL, rgba)


w = Gtk.Window()

visual = w.get_screen().get_rgba_visual()
if visual and w.get_screen().is_composited():
    w.set_visual(visual)

o = Gtk.Overlay()
o.set_visible(True)
w.add(o)
image = Gtk.Image.new_from_file('data/icons/scalable/apps/ojo.svg')
image.set_visible(True)
scroll_window = Gtk.ScrolledWindow()
scroll_window.set_visible(True)
scroll_window.add_with_viewport(image)
scroll_window.set_min_content_width(300)
scroll_window.set_min_content_height(300)
o.add(scroll_window)

b = Gtk.Button('AAAAAA')
b.set_visible(True)
b.set_halign(Gtk.Align.CENTER)
b.set_valign(Gtk.Align.CENTER)
make_transparent(b)
o.add_overlay(b)

web_view = WebKit.WebView()
web_view.set_transparent(True)
web_view.set_can_focus(True)
web_view.set_halign(Gtk.Align.FILL)
web_view.set_valign(Gtk.Align.START)
web_view.load_string("<html><body style='color: red; background-color: rgba(130, 40, 20, 0.2); font-size: 40px;'>WebView here</body></html>", 'text/html', 'UTF-8', 'file:///')
web_view.set_visible(True)
make_transparent(web_view)

# scroll_window2 = Gtk.ScrolledWindow()
# scroll_window2.set_visible(True)
# scroll_window2.add_with_viewport(web_view)
# scroll_window2.set_min_content_width(300)
# scroll_window2.set_min_content_height(80)
# scroll_window2.set_halign(Gtk.Align.FILL)
# scroll_window2.set_valign(Gtk.Align.START)
#make_transparent(scroll_window2)
#make_transparent(scroll_window2.get_child())
# scroll_window2.set_visible(True)

o.add_overlay(web_view)

web_view.set_visible(True)

w.show()
w.connect('destroy', Gtk.main_quit)
b.connect('clicked', lambda w: web_view.set_visible(not web_view.get_visible()))
Gtk.main()