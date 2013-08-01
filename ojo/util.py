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


def get_parent(file):
    parent = os.path.realpath(os.path.join(file, '..'))
    return parent if parent != file else None


def get_xdg_pictures_folder():
    import subprocess
    import logging
    try:
        return subprocess.check_output(['xdg-user-dir', 'PICTURES']).split('\n')[0]
    except Exception:
        logging.exception("Could not get path to Pictures folder")
        return os.path.expanduser('~/Pictures')


def makedirs(path):
    import logging
    if not os.path.isdir(path):
        logging.info("Creating folder %s" % path)
        os.makedirs(path)
    return path


def path2url(path):
    import urllib
    return 'file://' + urllib.pathname2url(path)


def url2path(url):
    import urllib
    return urllib.url2pathname(url)[7:]


if __name__ == "__main__":
    print get_folder_icon('/', 24)

