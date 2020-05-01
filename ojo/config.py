import os
import logging

from . import util


class dotdict(dict):
    """dot.notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


options = dotdict()
bookmarks = []


def load_options():
    options.clear()
    options.update(load_json("options.json", {}))
    defaults = {
        "folder": util.get_xdg_pictures_folder(),
        "decorated": True,
        "maximized": False,
        "fullscreen": False,
        "enlarge_smaller": False,
        "font_size": "12pt",
        "thumb_height": 180,
        "sort_by": "name",
        "sort_order": "asc",
        "show_hidden": False,
        "show_captions": True,
        "show_folder_thumbs": False,
        "date_format": "%-d %B %Y",
        "show_groups_for": {
            "date": True,
            "exif_date": True,
            "extension": True,
            "name": False,
            "size": True,
        },
        "group_by_size_buckets": [
            [1000, "Bytes"],
            [100 * 1024, "Less than 100 KB"],
            [1 * 1024 * 1024, "100 KB to 1 MB"],
            [2 * 1024 * 1024, "1-2 MB"],
            [5 * 1024 * 1024, "2-5 MB"],
            [10 * 1024 * 1024, "5-10 MB"],
            [20 * 1024 * 1024, "10-20 MB"],
            [50 * 1024 * 1024, "20-50 MB"],
            [100 * 1024 * 1024, "50-100 MB"],
            [1024 * 1024 * 1024, "100 MB - 1 GB"],
            [1e18, "More than 1 GB"],
        ],
    }
    for k, v in defaults.items():
        if not k in options:
            options[k] = v


def get_config_dir():
    return util.makedirs(os.path.expanduser("~/.config/ojo/config/"))


def get_config_file(filename):
    return os.path.join(get_config_dir(), filename)


def save_options():
    save_json("options.json", options)


def load_bookmarks():
    global bookmarks
    bookmarks = load_json("bookmarks.json", [util.get_xdg_pictures_folder()])


def save_bookmarks():
    save_json("bookmarks.json", bookmarks)


def load_json(filename, default_data):
    import json

    try:
        with open(get_config_file(filename)) as f:
            return json.load(f)
    except Exception:
        logging.exception("Could not load options, using defaults")
        save_json(filename, default_data)
        return default_data


def save_json(filename, data):
    import json

    with open(get_config_file(filename), "w") as f:
        json.dump(data, f, ensure_ascii=True, indent=4, sort_keys=True)
