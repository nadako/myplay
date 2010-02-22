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
import gst
import gobject


USED_TAGS = set([gst.TAG_TITLE, gst.TAG_ARTIST, gst.TAG_ALBUM])
GST_PLAY_FLAG_AUDIO = 1 << 1


class TagScanner(object):
    """Asynchronous tag scanner
    
    Create it, passing a callback function with (uri_string, tags_dict) signature.
    Then use it calling the "add(uris)" function.
    
    It works by creating a GStreamer playbin2 pipeline and loading files until they
    can be played, while collecting their tags. After a file is loaded, it invokes
    given callback passing uri and collected tags to it.

    The tags_dict, passed to the callback is safe to use without copying, as it's
    not used by tag scanner any longer after callback has been called.

    """
    
    def __init__(self, callback):
        self._uris = []
        self._tags = {}
        self._idle = True
        self._callback = callback

        self._player = gst.element_factory_make('playbin2')
        self._player.set_property('flags', GST_PLAY_FLAG_AUDIO)
        self._player.set_property('audio-sink', gst.element_factory_make('fakesink'))

        bus = self._player.get_bus()
        bus.add_signal_watch()
        bus.connect('message::tag', self._on_tag_message)
        bus.connect('message::element', self._on_element_message)

    def _check_uri(self, uri):
        self._player.set_state(gst.STATE_NULL)
        self._player.set_property('uri', uri)
        self._player.set_state(gst.STATE_PAUSED)

    def _on_tag_message(self, bus, message):
        info = self._tags.setdefault(self._player.get_property('uri'), {})
        tags = message.parse_tag()
        for key in tags.keys():
            if (key not in USED_TAGS) or (key in info and info[key] == tags[key]):
                continue
            info[key] = tags[key]

    def _on_element_message(self, bus, message):
        if message.structure.has_name('playbin2-stream-changed'):
            uri = self._player.get_property('uri')
            if uri in self._tags:
                self._callback(uri, self._tags[uri])
                del self._tags[uri]
            if self._uris:
                self._next()
            else:
                self._idle = True

    def _next(self):
        self._check_uri(self._uris.pop(0))
        return False

    def add(self, uris):
        self._uris.extend(uris)
        if self._idle:
            self._idle = False
            gobject.idle_add(self._next)
