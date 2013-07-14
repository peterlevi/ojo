import os

def get_folder_icon_name(path):
    try:
        from gi.repository import Gio
        f = Gio.File.new_for_path(os.path.normpath(os.path.expanduser(path)))
        query_info = f.query_info("standard::icon", Gio.FileQueryInfoFlags.NONE, None)
        return query_info.get_attribute_object("standard::icon").get_names()[0]
    except Exception:
        return "folder"

def get_folder_icon(path, size):
    from gi.repository import Gtk
    name = get_folder_icon_name(path)
    try:
        return get_icon_path(name, size)
    except Exception:
        return get_icon_path('folder', size)

def get_icon_path(icon_name, size):
    from gi.repository import Gtk
    return Gtk.IconTheme.get_default().lookup_icon(icon_name, size, 0).get_filename()

if __name__ == "__main__":
    print get_folder_icon('/', 24)

