#!/usr/bin/python

import os
import time
from gi.repository import GdkPixbuf
from gi.repository import GExiv2

dir = '/d/Pics/Wallpapers/Favorites'

s = time.time()
i = 0
for i, f in enumerate(os.listdir(dir)):
    try:
        file = os.path.join(dir, f)
        GdkPixbuf.Pixbuf.get_file_info(file)
    except Exception:
        pass
print(i, time.time() - s)

s = time.time()
i = 0
for i, f in enumerate(os.listdir(dir)):
    try:
        file = os.path.join(dir, f)
        meta = GExiv2.Metadata(path=file)
    except Exception:
        pass
print(i, time.time() - s)

