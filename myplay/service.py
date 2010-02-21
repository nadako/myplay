import dbus.mainloop.glib
import dbus.service
import gobject
from myplay.player import Player
from myplay.common import BUS_NAME, OBJECT_PATH


IDLE_TIMEOUT = 5 # idle timeout before quitting service


class Application(object):
    
    def __init__(self):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self._timeout_id = 0
        self._player = Player(self.idle_callback)
        self._bus_name_ = dbus.service.BusName(BUS_NAME, dbus.SessionBus()) # store a reference
        self._player.add_to_connection(self._bus_name_.get_bus(), OBJECT_PATH)
        self._loop = gobject.MainLoop()
    
    def run(self):
        self._loop.run()

    def quit(self):
        self._loop.quit()

    def idle_callback(self, player, idle):
        if not idle and self._timeout_id:
            gobject.source_remove(self._timeout_id)
            self._timeout_id = 0
        elif idle and not self._timeout_id:
            self._timeout_id = gobject.timeout_add_seconds(IDLE_TIMEOUT, self.quit)

def main():
    app = Application()
    app.run()
