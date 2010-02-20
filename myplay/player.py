import cPickle as pickle
import os

import dbus.service
import gst
from xdg.BaseDirectory import save_data_path

from myplay.common import OBJECT_INTERFACE
from myplay.common import STATE_READY, STATE_PAUSED, STATE_PLAYING

GST_PLAY_FLAG_AUDIO = 1 << 1

class Player(dbus.service.Object):
    
    def __init__(self):
        dbus.service.Object.__init__(self)
        
        self._player = gst.element_factory_make('playbin2', 'player')
        self._player.set_property('flags', GST_PLAY_FLAG_AUDIO)
        player_bus = self._player.get_bus()
        player_bus.add_signal_watch()
        player_bus.connect('message', self._on_player_message)

        self._playlist_path = os.path.join(save_data_path('myplay'), 'playlist')
        self._init_playlist()

        self._current = -1
        self._state = STATE_READY
    
    def _on_player_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self._player.set_state(gst.STATE_NULL)
            self._next_track()

    def _init_playlist(self):
        self._playlist = []
        if os.path.exists(self._playlist_path):
            try:
                self._playlist = pickle.load(open(self._playlist_path, 'rb'))
            except:
                pass
    
    def _save_playlist(self):
        if self._playlist:
            pickle.dump(self._playlist, open(self._playlist_path, 'wb'))
        elif os.path.exists(self._playlist_path):
            os.unlink(self._playlist_path)

    @dbus.service.method(OBJECT_INTERFACE, in_signature='as')
    def add(self, uris):
        for uri in uris:
            self._playlist.append(str(uri))
        self._save_playlist()
        self.added(uris)
    
    @dbus.service.method(OBJECT_INTERFACE, in_signature='au')
    def remove(self, positions):
        self._playlist = [uri for i, uri in enumerate(self._playlist) if i not in positions]
        self._save_playlist()
        self.removed(positions)

    @dbus.service.method(OBJECT_INTERFACE, out_signature='as')
    def list(self):
        return tuple(self._playlist)

    @dbus.service.method(OBJECT_INTERFACE)
    def clear(self):
        self._playlist[:] = []
        self._save_playlist()
        self.cleared()

    @dbus.service.signal(OBJECT_INTERFACE, signature='as')
    def added(self, uris):
        pass

    @dbus.service.signal(OBJECT_INTERFACE, signature='au')
    def removed(self, positions):
        pass

    @dbus.service.signal(OBJECT_INTERFACE)
    def cleared(self):
        pass

    @dbus.service.method(OBJECT_INTERFACE, out_signature='i')
    def get_current(self):
        return self._current

    @dbus.service.method(OBJECT_INTERFACE, in_signature='i')
    def set_current(self, position):
        if self._current != position:
            self._current = position
            self.current_changed(position)

    @dbus.service.signal(OBJECT_INTERFACE, signature='i')
    def current_changed(self, position):
        pass

    @dbus.service.method(OBJECT_INTERFACE, out_signature='u')
    def get_state(self):
        return self._state

    @dbus.service.method(OBJECT_INTERFACE, in_signature='u')
    def set_state(self, state):
        old = self._state
        if state != old:
            self._state = state
            self.state_changed(old, state)
    
    @dbus.service.signal(OBJECT_INTERFACE, signature='uu')
    def state_changed(self, old, new):
        pass

    def _change_state(self, new):
        old = self._state
        if new != old:
            self._state = new
            self.state_changed(old, new)

    @dbus.service.method(OBJECT_INTERFACE)
    def play(self):
        if self._state == STATE_READY and self._current != -1:
            self._player.set_property('uri', self._playlist[self._current])
            self._player.set_state(gst.STATE_PLAYING)
            self._change_state(STATE_PLAYING)
        elif self._state == STATE_PAUSED:
            self._player.set_state(gst.STATE_PLAYING)
            self._change_state(STATE_PLAYING)
    
    @dbus.service.method(OBJECT_INTERFACE)
    def pause(self):
        if self._state == STATE_PLAYING:
            self._player.set_state(gst.STATE_PAUSED)
            self._change_state(STATE_PAUSED)
    
    @dbus.service.method(OBJECT_INTERFACE)
    def stop(self):
        if self._state in (STATE_PLAYING, STATE_PAUSED):
            self._player.set_state(gst.STATE_NULL)
            self._change_state(STATE_READY)

    def _next_track(self):
        if self._current != (len(self._playlist) - 1):
            self._current += 1
            self._player.set_property('uri', self._playlist[self._current])
            self._player.set_state(gst.STATE_PLAYING)
            self.current_changed(self._current)
        else:
            self._current = -1
            self.current_changed(-1)
            self._change_state(STATE_READY)
