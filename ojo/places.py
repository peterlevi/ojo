from gi.repository import Gio
import util


class Places:
    def __init__(self, on_change_fn, icon_size=16):
        self.icon_size = icon_size
        self.vm = Gio.VolumeMonitor.get()
        self.on_change_fn = on_change_fn
        for sig in [
            "volume-added",
            "volume-changed",
            "volume-removed",
            "mount-added",
            "mount-changed",
            "mount-removed",
        ]:
            self.vm.connect(sig, self.on_change)

    def on_change(self, *args):
        self.on_change_fn()

    def get_places(self):
        places = []

        places.append({
            'path': '/',
            'label': 'Computer',
            'icon': util.get_icon_path('drive-harddisk', self.icon_size)
        })

        # for drive in self.vm.get_connected_drives():
        #     self.add_drive(drive, places)
        #
        # for volume in self.vm.get_volumes():
        #     if not volume.get_drive():
        #         self.add_volume(volume, places)
        #
        for mount in self.vm.get_mounts():
            # if not mount.get_volume():
            self.add_mount(mount, places)

        return places

    # def add_drive(self, drive, places):
    #     for volume in drive.get_volumes():
    #         self.add_volume(volume, places)
    #
    # def add_volume(self, volume, places):

    def add_mount(self, mount, places):
        places.append({
            'path': mount.get_default_location().get_path(),
            'label': mount.get_name(),
            'icon': self.get_icon(mount),
        })

    def get_icon(self, g_item):
        try:
            icon_name = g_item.get_icon().get_names()[0]
        except:
            icon_name = 'folder'
        return util.get_icon_path(icon_name, self.icon_size)
