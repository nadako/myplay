#
# This file is part of MyPlay.
#
# Copyright 2010 Dan Korostelev <nadako@gmail.com>
#
# MyPlay is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# MyPlay is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with MyPlay.  If not, see <http://www.gnu.org/licenses/>.
#
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
