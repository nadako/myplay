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

USED_TAGS = (gst.TAG_TITLE, gst.TAG_ARTIST, gst.TAG_ALBUM)

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
        self._player.get_bus().add_watch(self._bus_watch_cb)

    def _bus_watch_cb(self, bus, message):
        if message.type == gst.MESSAGE_TAG:
            taglist = message.parse_tag()
            for key in taglist.keys():
                if key in USED_TAGS:
                    self._tags[key] = taglist[key]
        elif message.type == gst.MESSAGE_STATE_CHANGED:
            old, new, pending = message.parse_state_changed()
            if old == gst.STATE_READY and new == gst.STATE_PAUSED and pending == gst.STATE_PLAYING:
                self._finish_current()
        elif message.type in (gst.MESSAGE_ERROR, gst.MESSAGE_EOS):
            self._finish_current()
        return True

    def _finish_current(self):
        if self._tags:
            self._callback(self._player.props.uri, self._tags)
            self._tags = {}

        self._player.set_state(gst.STATE_NULL)
        if self._uris:
            self._next()
        else:
            self._idle = True

    def _next(self):
        self._player.props.uri = self._uris.pop(0)
        self._player.set_state(gst.STATE_PLAYING)

    def add(self, uris):
        self._uris.extend(uris)
        if self._idle:
            self._idle = False
            self._next()
