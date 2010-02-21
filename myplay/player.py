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
import os
import cPickle as pickle

import dbus.service
import gst
from xdg.BaseDirectory import save_data_path

from myplay.common import OBJECT_IFACE, CURRENT_UNSET, STATE_READY, STATE_PLAYING, STATE_PAUSED

GST_PLAY_FLAG_AUDIO = 1 << 1

class InvalidPlaylistPosition(dbus.service.DBusException):
    _dbus_error_name = 'org.nadako.myplay.InvalidPlaylistPosition'

class InvalidPlaylistLength(dbus.service.DBusException):
    _dbus_error_name = 'org.nadako.myplay.InvalidPlaylistLength'

class Player(dbus.service.Object):
    
    @dbus.service.method(OBJECT_IFACE, out_signature='as')
    def list(self):
        return tuple(self._playlist)
    
    @dbus.service.method(OBJECT_IFACE, in_signature='asi')
    def add(self, uris, position):
        if (position != -1) and (position < 0) or (position > len(self._playlist)):
            raise InvalidPlaylistPosition(position)
        if uris:
            self._playlist[position:position] = [str(uri) for uri in uris]
            self._save_playlist()
            self.added(uris, position)
    
    @dbus.service.method(OBJECT_IFACE, in_signature='au')
    def remove(self, positions):
        playlist_len = len(self._playlist)
        remove_current = False
        for pos in positions:
            if (pos < 0) or (pos >= playlist_len):
                raise InvalidPlaylistPosition(pos)
            if pos == self._current:
                remove_current = True
        self._playlist = [uri for i, uri in enumerate(self._playlist) if i not in positions]
        self._save_playlist()
        self.removed(positions)
        if remove_current:
            self.set_current(CURRENT_UNSET)
            if self._state == STATE_PLAYING:
                self.stop()
    
    @dbus.service.method(OBJECT_IFACE)
    def clear(self):
        self._playlist[:] = []
        self._save_playlist()
        self.cleared()
    
    @dbus.service.method(OBJECT_IFACE, in_signature='au')
    def reorder(self, positions):
        playlist_len = len(self._playlist)
        if len(positions) != playlist_len:
            raise InvalidPlaylistLength(self._playlist)
        new_playlist = []
        for pos in positions:
            if (pos < 0) or (pos >= playlist_len):
                raise InvalidPlaylistPosition(pos)
            new_playlist.append(self._playlist[pos])
        self._playlist[:] = new_playlist
        self._save_playlist()
        self.reordered(positions)
    
    @dbus.service.method(OBJECT_IFACE, out_signature='i')
    def get_current(self):
        return self._current
    
    @dbus.service.method(OBJECT_IFACE, in_signature='i')
    def set_current(self, position):
        if (position != CURRENT_UNSET) and (position < 0 or position >= len(self._playlist)):
            raise InvalidPlaylistPosition()
        self._change_current(position)
    
    @dbus.service.method(OBJECT_IFACE)
    def next(self):
        if (self._current != CURRENT_UNSET) and self._current != (len(self._playlist) - 1):
            self._change_current(self._current + 1)
    
    @dbus.service.method(OBJECT_IFACE)
    def previous(self):
        if (self._current != CURRENT_UNSET) and (self._current != 0):
            self._change_current(self._current - 1)
    
    @dbus.service.method(OBJECT_IFACE)
    def play(self):
        if self._state in (STATE_READY, STATE_PAUSED):
            if self._state == STATE_READY:
                self._player.set_property('uri', self._playlist[self._current])
            self._player.set_state(gst.STATE_PLAYING)
            self._change_state(STATE_PLAYING)
    
    @dbus.service.method(OBJECT_IFACE, in_signature='u')
    def set_current_and_play(self, position):
        self.set_current(position)
        self.play()

    @dbus.service.method(OBJECT_IFACE)
    def pause(self):
        if self._state == STATE_PLAYING:
            self._player.set_state(gst.STATE_PAUSED)
            self._change_state(STATE_PAUSED)
    
    @dbus.service.method(OBJECT_IFACE)
    def stop(self):
        if self._state in (STATE_PLAYING, STATE_PAUSED):
            self._player.set_state(gst.STATE_READY)
            self._player.set_property('uri', '')
            self._change_state(STATE_READY)

    @dbus.service.method(OBJECT_IFACE, out_signature='u')
    def get_state(self):
        return self._state

    @dbus.service.signal(OBJECT_IFACE, signature='asi')
    def added(self, uris, position):
        pass
    
    @dbus.service.signal(OBJECT_IFACE, signature='au')
    def removed(self, positions):
        pass
    
    @dbus.service.signal(OBJECT_IFACE)
    def cleared(self):
        pass
    
    @dbus.service.signal(OBJECT_IFACE, signature='au')
    def reordered(self, positions):
        pass
    
    @dbus.service.signal(OBJECT_IFACE, signature='ii')
    def current_changed(self, old_position, new_position):
        pass
    
    @dbus.service.signal(OBJECT_IFACE, signature='uu')
    def state_changed(self, old_state, new_state):
        pass

    def __init__(self, idle_callback=None):
        super(Player, self).__init__()
        
        self._playlist_path = os.path.join(save_data_path('myplay'), 'playlist')
        self._init_playlist()
        
        self._player = gst.element_factory_make('playbin2', 'player')
        self._player.set_property('flags', GST_PLAY_FLAG_AUDIO)
        player_bus = self._player.get_bus()
        player_bus.add_signal_watch()
        player_bus.connect('message', self.on_player_message)

        self._state = STATE_READY
        self._idle_callback = idle_callback
        self.idle = True
    
    @apply
    def idle():
        def fget(self):
            return getattr(self, '_idle', False)
        def fset(self, value):
            setattr(self, '_idle', value)
            if self._idle_callback is not None:
                self._idle_callback(self, value)
        return property(fget, fset)
    
    def on_player_message(self, element, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            if self._current != (len(self._playlist) - 1):
                self.next()
            else:
                self.stop()

    def _init_playlist(self):
        self._playlist = []
        self._current = CURRENT_UNSET
        if os.path.exists(self._playlist_path):
            try:
                data = pickle.load(open(self._playlist_path, 'rb'))
                self._playlist = data['playlist']
                self._current = data['current']
            except:
                pass
    
    def _save_playlist(self):
        if self._playlist:
            data = {'playlist': self._playlist, 'current': self._current}
            pickle.dump(data, open(self._playlist_path, 'wb'))
        elif os.path.exists(self._playlist_path):
            os.unlink(self._playlist_path)

    def _change_state(self, new):
        old = self._state
        if new != old:
            self._state = new
            self.state_changed(old, new)
            if new == STATE_READY:
                self.idle = True
            else:
                self.idle = False

    def _change_current(self, new):
        old = self._current
        if new != old:
            newstate = None
            if new == CURRENT_UNSET:
                self._player.set_state(gst.STATE_READY)
                self._player.set_property('uri', '')
            else:
                if self._state in (STATE_PLAYING, STATE_PAUSED):
                    self._player.set_state(gst.STATE_READY)
                    self._player.set_property('uri', self._playlist[new])
                    if self._state == STATE_PAUSED:
                        self._player.set_state(gst.STATE_READY)
                        newstate = STATE_READY
                    else:
                        self._player.set_state(gst.STATE_PLAYING)
            self._current = int(new)
            self._save_playlist()
            self.current_changed(old, new)
            if newstate is not None:
                self._change_state(newstate)
