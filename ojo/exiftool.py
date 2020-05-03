import json
import logging
import os
import subprocess

from ojo.config import options
from ojo.ojoconfig import get_data_file


class ExifTool(object):

    sentinel = b"{ready}\n"

    def __init__(self):
        path = options.get("exiftool_path")
        if path is None or path == "~bundled~":
            self.executable = get_data_file("ExifTool", "exiftool")
        elif os.path.isfile(path):
            self.executable = path
        else:
            self.executable = "exiftool"
        logging.warning("Using exiftool executable path: %s", self.executable)

    def __enter__(self):
        self.process = subprocess.Popen(
            [self.executable, "-stay_open", "True", "-@", "-"],
            universal_newlines=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        logging.warning("ExifTool Version: %s", self.execute("-ver"))
        return self

    def __exit__(self, exc_type=None, exc_value=None, traceback=None):
        self.process.stdin.write("-stay_open\nFalse\n")
        self.process.stdin.flush()

    def execute(self, *args):
        return subprocess.check_output([self.executable, *args])
        args = args + ("-execute\n",)
        self.process.stdin.write(str.join("\n", args))
        self.process.stdin.flush()
        output = b""
        fd = self.process.stdout.fileno()
        while not output.endswith(self.sentinel):
            output += os.read(fd, 4096)
        return output[: -len(self.sentinel)].decode("utf-8")

    def get_metadata(self, filename, with_print_conversion=True):
        params = ["-j", filename] if with_print_conversion else ["-j", "-n", filename]
        result = self.execute(*params)
        try:
            return json.loads(result)[0]
        except:
            print(filename, 'RESULTS\n---------------------\n{}\n------------------'.format(result))
            logging.exception(
                "Error in ExifTool wrapper while reading metadata for {}:".format(filename)
            )
            raise

    def extract_previews(self, filename, to_folder):
        params = ["-a", "-b", "-W", "{}/%f_%t%-c.%s".format(to_folder), "-preview:all", filename]
        self.execute(*params)
