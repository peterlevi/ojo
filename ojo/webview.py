import gi
gi.require_version('WebKit', '3.0')
from gi.repository import WebKit, GObject

import logging
import util
import ojoconfig


class WebView:
    def __init__(self):
        self.web_view = None
        self.is_loaded = False
        self.js_queue = []

    def add_to(self, widget):
        if not self.web_view:
            raise Exception('add_to called when WebView not yet loaded')
        widget.add(self.web_view)

    def grab_focus(self):
        if self.web_view:
            self.web_view.grab_focus()

    def js(self, command=None, commands=None):
        all_commands = []
        if command:
            all_commands.append(command)
        if commands:
            all_commands += commands

        if self.is_loaded:
            def _do_queue():
                while self.js_queue:
                    queued = self.js_queue.pop(0)
                    self.web_view.execute_script(queued)
                for cmd in all_commands:
                    self.web_view.execute_script(cmd)
            GObject.idle_add(_do_queue)
        else:
            for cmd in all_commands:
                logging.debug('Postponing js: ' + cmd)
                self.js_queue.append(cmd)
            GObject.timeout_add(100, lambda: self.js())

    def load(self, html_filename, on_load_fn=None, on_action_fn=None):
        with open(ojoconfig.get_data_file(html_filename)) as f:
            html = f.read()

        self.web_view = WebKit.WebView()
        self.web_view.set_transparent(True)
        self.web_view.set_can_focus(True)

        def nav(wv, command):
            logging.debug('Received command: ' + command)
            if on_action_fn:
                if command:
                    command = command[command.index('|') + 1:]
                    index = command.index(':')
                    action = command[:index]
                    argument = command[index + 1:]
                    on_action_fn(action, argument)

        self.web_view.connect("status-bar-text-changed", nav)

        def _on_load(*args):
            self.is_loaded = True
            if on_load_fn:
                on_load_fn()

        self.web_view.connect('document-load-finished', _on_load)
        self.web_view.load_string(
            html, "text/html", "UTF-8", util.path2url(ojoconfig.get_data_path()) + '/')

        util.make_transparent(self.web_view)
        self.web_view.set_visible(True)

