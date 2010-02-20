import dbus.mainloop.glib
import dbus.service
import gobject
from myplay.player import Player
from myplay.common import BUS_NAME, OBJECT_PATH

def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    player = Player()
    player._bus_name_ = dbus.service.BusName(BUS_NAME, dbus.SessionBus())
    player.add_to_connection(player._bus_name_.get_bus(), OBJECT_PATH)
    gobject.MainLoop().run()
