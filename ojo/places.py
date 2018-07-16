from gi.repository import Gio, GObject
import os
import util


class Places:
    VOLUME_MONITOR_SIGNALS = [
        "volume-added",
        "volume-changed",
        "volume-removed",
        "mount-added",
        "mount-changed",
        "mount-removed",
    ]

    def __init__(self, on_change, icon_size=16):
        self.icon_size = icon_size
        self.on_change_fn = on_change
        self.places = []
        self.vm = None

        def _init_vm():
            self.vm = Gio.VolumeMonitor.get()
            for sig in Places.VOLUME_MONITOR_SIGNALS:
                self.vm.connect(sig, self.on_change)
            self.refresh_places()

        GObject.idle_add(_init_vm)

    def on_change(self, *args):
        GObject.idle_add(self.refresh_places)

    def get_places(self):
        return self.places

    def refresh_places(self, *args):
        # similar logic to how Nautilus does it
        # (https://github.com/GNOME/nautilus/blob/master/src/gtk/nautilusgtkplacesview.c)

        self.places = []

        for drive in self.vm.get_connected_drives():
            self.add_drive(drive)

        for volume in self.vm.get_volumes():
            if not volume.get_drive():
                self.add_volume(volume)

        for mount in self.vm.get_mounts():
            if not mount.is_shadowed():
                self.add_mount(mount)

        self.places.sort(key=lambda p: p['label'].lower())

        self.places.insert(0, {
            'path': '/',
            'label': 'Computer',
            'icon': util.get_icon_path('drive-harddisk', self.icon_size)
        })

        self.places.insert(0, {
            'path': os.path.expanduser('~'),
            'label': 'Home',
            'icon': util.get_icon_path('user-home', self.icon_size)
        })

        self.on_change_fn()

    def add_drive(self, drive):
        for volume in drive.get_volumes():
            self.add_volume(volume)

    def add_volume(self, volume):
        mount = volume.get_mount()
        if not mount:  # TODO Nautilus here also uses "or mount.is_shadowed()"?
            if volume.can_mount():
                volume_id = volume.get_identifier(Gio.VOLUME_IDENTIFIER_KIND_UNIX_DEVICE)
                self.places.append({
                    'label': volume.get_name(),
                    'not_mounted': True,
                    'mount_id': volume_id,
                    'icon': self.get_icon(volume)
                })

    def add_mount(self, mount):
        path = mount.get_default_location().get_path()
        self.places.append({
            'path': path,
            'label': mount.get_name(),
            'icon': self.get_icon(mount),
            'can_unmount': mount.can_unmount(),
            'unmount_id': None if not mount.can_unmount() else path,
        })

    def get_icon(self, g_item):
        try:
            icon_name = g_item.get_icon().get_names()[0]
        except:
            icon_name = 'drive-harddisk'
        return util.get_icon_path(icon_name, self.icon_size, fallback='drive-harddisk')

    def mount_volume(self, volume_id, on_mount, on_mount_argument=None):
        def _on_mounted(volume, *args):
            import time
            import os
            path = volume.get_mount().get_default_location().get_path()

            # wait up to 2 sec for the mount path to be readable
            wait_start = time.time()
            while time.time() - wait_start < 2:
                try:
                    os.listdir(path)
                    break
                except:
                    time.sleep(0.2)

            on_mount(path, on_mount_argument)

        def _go():
            for volume in self.vm.get_volumes():
                if volume.get_identifier(Gio.VOLUME_IDENTIFIER_KIND_UNIX_DEVICE) == volume_id:
                    volume.mount(
                        Gio.MountMountFlags.NONE,
                        None,
                        None,
                        _on_mounted,
                        None)

        GObject.idle_add(_go)

    def unmount_mount(self, mount_path, on_unmount=None):
        def _go():
            for mount in self.vm.get_mounts():
                if not mount.is_shadowed() and mount.get_default_location().get_path() == mount_path:

                    def _on_unmount(*args):
                        success = True
                        for mount in self.vm.get_mounts():
                            if not mount.is_shadowed() and mount.get_default_location().get_path() == mount_path:
                                success = False
                        if on_unmount:
                            on_unmount(mount_path, success)

                    mount.unmount_with_operation(Gio.MountUnmountFlags.NONE, None, None, _on_unmount)

        GObject.idle_add(_go)
