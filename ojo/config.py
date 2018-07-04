import os
import logging

import util


class dotdict(dict):
    """dot.notation access to dictionary attributes"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__
    

options = dotdict()
bookmarks = []
        

def load_options():
    options.clear()
    options.update(load_json('options.json', {}))
    defaults = {
        'folder': util.get_xdg_pictures_folder(),

        'decorated': True,
        'maximized': False,
        'fullscreen': False,

        'enlarge_smaller': False,

        'thumb_height': 120,

        'sort_by': 'name',
        'sort_order': 'asc',
        'show_hidden': False,
        'show_captions': False,

        'date_format': '%d %B %Y',
    }
    for k, v in defaults.items():
        if not k in options:
            options[k] = v


def get_config_dir():
    return util.makedirs(os.path.expanduser('~/.config/ojo/config/'))


def get_config_file(filename):
    return os.path.join(get_config_dir(), filename)


def save_options():
    save_json('options.json', options)


def load_bookmarks():
    global bookmarks
    bookmarks = load_json('bookmarks.json',
                          [util.get_xdg_pictures_folder()])


def save_bookmarks():
    save_json('bookmarks.json', bookmarks)


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
    with open(get_config_file(filename), 'w') as f:
        json.dump(data, f, ensure_ascii=True, indent=4)

