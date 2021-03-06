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
import glib
import gst

from myplay.common import OBJECT_IFACE, CURRENT_UNSET, STATE_READY, STATE_PLAYING, STATE_PAUSED
from myplay.tagscanner import TagScanner

GST_PLAY_FLAG_AUDIO = 1 << 1

class InvalidPosition(dbus.service.DBusException):
    _dbus_error_name = 'org.nadako.myplay.InvalidPosition'

class InvalidLength(dbus.service.DBusException):
    _dbus_error_name = 'org.nadako.myplay.InvalidLength'

class EmptySequence(dbus.service.DBusException):
    _dbus_error_name = 'org.nadako.myplay.EmptySequence'

class Player(dbus.service.Object):
    
    @dbus.service.method(OBJECT_IFACE, out_signature='a(sa{ss})')
    def List(self):
        res = []
        for uri in self._playlist:
            res.append((uri, self._tags.get(uri, {})))
        return tuple(res)
    
    @dbus.service.method(OBJECT_IFACE, in_signature='asu')
    def Add(self, uris, position):
        if not uris:
            raise EmptySequence
        if position < 0 or position > len(self._playlist):
            raise InvalidPosition(position)

        uris = [str(uri) for uri in uris]
        self._playlist[position:position] = uris
        self._save_playlist()
        
        add_info = [(uri, self._tags.get(uri, {})) for uri in uris]
        self.Added(add_info, position)

        no_tags = [uri for uri, tag in add_info if not tag]
        if no_tags:
            self._tag_scanner.add(no_tags)
    
    @dbus.service.method(OBJECT_IFACE, in_signature='au')
    def Remove(self, positions):
        if not positions:
            raise EmptySequence
        playlist_len = len(self._playlist)
        for pos in positions:
            if pos < 0 or pos >= playlist_len:
                raise InvalidPosition(pos)

        self._playlist[:] = [uri for i, uri in enumerate(self._playlist) if i not in positions]
        self._save_playlist()
        self.Removed(positions)

        if self._current in positions:
            self.SetCurrent(CURRENT_UNSET)
    
    @dbus.service.method(OBJECT_IFACE)
    def Clear(self):
        self._playlist[:] = []
        self._save_playlist()
        self.Cleared()
        self.SetCurrent(CURRENT_UNSET)
    
    @dbus.service.method(OBJECT_IFACE, in_signature='au')
    def Reorder(self, positions):
        if not positions:
            raise EmptySequence
        playlist_len = len(self._playlist)
        if len(positions) != playlist_len:
            raise InvalidLength(self._playlist)

        new_playlist = []
        for pos in positions:
            if pos < 0 or pos >= playlist_len:
                raise InvalidPosition(pos)
            new_playlist.append(self._playlist[pos])

        self._playlist[:] = new_playlist
        self._save_playlist()

        self.Reordered(positions)
    
        if self._current != CURRENT_UNSET:
            self._change_current(positions.index(self._current), True)

    @dbus.service.method(OBJECT_IFACE, out_signature='i')
    def GetCurrent(self):
        return self._current

    @dbus.service.method(OBJECT_IFACE, in_signature='ib')
    def SetCurrent(self, position, play=False):
        if position < 0 or position >= len(self._playlist):
            if not (position == CURRENT_UNSET and not play):
                raise InvalidPosition()
        self._change_current(int(position))
        if play:
            self.Play()

    @dbus.service.method(OBJECT_IFACE)
    def Next(self):
        if self._current != CURRENT_UNSET and not self._current_is_last():
            self._change_current(self._current + 1)
    
    @dbus.service.method(OBJECT_IFACE)
    def Previous(self):
        if self._current != CURRENT_UNSET and not self._current_is_first():
            self._change_current(self._current - 1)
    
    @dbus.service.method(OBJECT_IFACE)
    def Play(self):
        if self._state != STATE_PLAYING:
            if self._current == CURRENT_UNSET:
                if self._playlist:
                    self._change_current(0)
                else:
                    return
            if self._state == STATE_READY:
                self._player.set_property('uri', self._playlist[self._current])
            self._player.set_state(gst.STATE_PLAYING)
            self._change_state(STATE_PLAYING)

    @dbus.service.method(OBJECT_IFACE)
    def Pause(self):
        if self._state == STATE_PLAYING:
            self._player.set_state(gst.STATE_PAUSED)
            self._change_state(STATE_PAUSED)
    
    @dbus.service.method(OBJECT_IFACE)
    def Stop(self):
        if self._state != STATE_READY:
            self._player.set_state(gst.STATE_NULL)
            self._player.set_property('uri', '')
            self._change_state(STATE_READY)

    @dbus.service.method(OBJECT_IFACE, out_signature='u')
    def GetState(self):
        return self._state

    @dbus.service.signal(OBJECT_IFACE, signature='a(sa{ss})i')
    def Added(self, tracks, position):
        pass
    
    @dbus.service.signal(OBJECT_IFACE, signature='au')
    def Removed(self, positions):
        pass
    
    @dbus.service.signal(OBJECT_IFACE)
    def Cleared(self):
        pass
    
    @dbus.service.signal(OBJECT_IFACE, signature='au')
    def Reordered(self, positions):
        pass
    
    @dbus.service.signal(OBJECT_IFACE, signature='ii')
    def CurrentChanged(self, old_position, new_position):
        pass
    
    @dbus.service.signal(OBJECT_IFACE, signature='uu')
    def StateChanged(self, old_state, new_state):
        pass

    @dbus.service.signal(OBJECT_IFACE, signature='sa{ss}')
    def TagChanged(self, uri, tag_dict):
        pass

    def __init__(self, idle_callback=None):
        super(Player, self).__init__()
        
        self._tag_scanner = TagScanner(self._on_tag_scanned)
        self._tags = {}
        
        data_dir = os.path.join(glib.get_user_data_dir(), 'myplay')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        
        self._playlist_path = os.path.join(data_dir, 'playlist')

        self._init_playlist()
        if self._playlist:
            self._tag_scanner.add(self._playlist)
        
        self._player = gst.element_factory_make('playbin2', 'player')
        self._player.set_property('flags', GST_PLAY_FLAG_AUDIO)
        player_bus = self._player.get_bus()
        player_bus.add_signal_watch()
        player_bus.connect('message', self._on_player_message)

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

    def _current_is_last(self):
        if not self._playlist:
            # check so this function won't return True on empty playlist 
            return False
        return self._current == (len(self._playlist) - 1)

    def _current_is_first(self):
        return self._current == 0
    
    def _on_player_message(self, element, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            if not self._current_is_last():
                self.Next()
            else:
                self.Stop()

    def _on_tag_scanned(self, uri, tag):
        if not (uri in self._tags and self._tags[uri] == tag):
            self._tags[uri] = tag
            self.TagChanged(uri, tag)
    
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
            self.StateChanged(old, new)
            if new == STATE_READY:
                self.idle = True
            else:
                self.idle = False

    def _change_current(self, new, reorder=False):
        old = self._current
        if old != new:
            self._current = new
            self._save_playlist()
            self.CurrentChanged(old, new)
            if not reorder:
                if self._state == STATE_PAUSED or new == CURRENT_UNSET:
                    self.Stop()
                elif self._state == STATE_PLAYING:
                    # reset player without changing player state
                    self._player.set_state(gst.STATE_NULL)
                    self._player.set_property('uri', self._playlist[new])
                    self._player.set_state(gst.STATE_PLAYING)
