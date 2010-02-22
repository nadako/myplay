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
import dbus
import dbus.mainloop.glib
import os
import gio
import gtk
import gst

from myplay.common import BUS_NAME, OBJECT_IFACE, OBJECT_PATH
from myplay.common import STATE_READY, STATE_PLAYING, STATE_PAUSED, CURRENT_UNSET

DND_REODER = 0
DND_ADD = 1

COL_CURRENT = 0
COL_URI = 1
COL_DISPLAY_PATH = 2
COL_TITLE = 3
COL_ARTIST = 4
COL_ALBUM = 5

class Application(object):

    def __init__(self):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()
        proxy = bus.get_object(BUS_NAME, OBJECT_PATH, follow_name_owner_changes=True)
        self._player = dbus.Interface(proxy, OBJECT_IFACE)
        bus.add_signal_receiver(self.on_added_signal, 'added', OBJECT_IFACE)
        bus.add_signal_receiver(self.on_removed_signal, 'removed', OBJECT_IFACE)
        bus.add_signal_receiver(self.on_cleared_signal, 'cleared', OBJECT_IFACE)
        bus.add_signal_receiver(self.on_reordered_signal, 'reordered', OBJECT_IFACE)
        bus.add_signal_receiver(self.on_current_changed_signal, 'current_changed', OBJECT_IFACE)
        bus.add_signal_receiver(self.on_state_changed_signal, 'state_changed', OBJECT_IFACE)
        bus.add_signal_receiver(self.on_tag_changed_signal, 'tag_changed', OBJECT_IFACE)
        
        builder = gtk.Builder()
        builder.add_from_file(os.path.join(os.path.dirname(__file__), 'gui.ui'))
        builder.connect_signals(self)
        self._window = builder.get_object('main_window')
        self._play_pause_button = builder.get_object('play_pause_button')
        self._playlist_view = builder.get_object('playlist_view')
        
        selection = self._playlist_view.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        selection.connect('changed', self.on_selection_changed)
        
        self._playlist_view.enable_model_drag_source(
            gtk.gdk.BUTTON1_MASK,
            [('positions', gtk.TARGET_SAME_WIDGET, DND_REODER)],
            gtk.gdk.ACTION_DEFAULT|gtk.gdk.ACTION_MOVE)
        self._playlist_view.connect('drag-data-get', self.on_drag_data_get)

        self._playlist_view.enable_model_drag_dest(
            [('positions', gtk.TARGET_SAME_WIDGET, DND_REODER),
             ('text/uri-list', 0, DND_ADD)],
            gtk.gdk.ACTION_DEFAULT)
        self._playlist_view.connect('drag-data-received', self.on_drag_data_received)
        
        self._playlist_store = builder.get_object('playlist_store')

        self._playlist_store.connect('row-inserted', self._update_clear_button)
        self._playlist_store.connect('row-deleted', self._update_clear_button)

        self._actions = {
            'next': builder.get_object('next_action'),
            'previous': builder.get_object('previous_action'),
            'play': builder.get_object('play_action'),
            'pause': builder.get_object('pause_action'),
            'stop': builder.get_object('stop_action'),
            'remove': builder.get_object('remove_action'),
            'clear': builder.get_object('clear_action'),
        }

        self._initialize_ui()

    def on_selection_changed(self, selection):
        if selection.count_selected_rows():
            self._actions['remove'].set_sensitive(True)
        else:
            self._actions['remove'].set_sensitive(False)
    
    def _initialize_ui(self):
        self._update_state(self._player.get_state())
        self._update_playlist(self._player.list(), self._player.get_current())
        self._set_current(self._player.get_current())

    def _update_clear_button(self, *args):
        if self._get_playlist_length():
            self._actions['clear'].set_sensitive(True)
        else:
            self._actions['clear'].set_sensitive(False)
    
    def _update_state(self, state):
        a = self._actions
        if state == STATE_READY:
            a['play'].set_sensitive(True)
            a['pause'].set_sensitive(False)
            a['stop'].set_sensitive(False)
            self._play_pause_button.set_related_action(a['play'])
        elif state == STATE_PLAYING:
            a['play'].set_sensitive(False)
            a['pause'].set_sensitive(True)
            a['stop'].set_sensitive(True)
            self._play_pause_button.set_related_action(a['pause'])
        elif state == STATE_PAUSED:
            a['play'].set_sensitive(True)
            a['pause'].set_sensitive(False)
            a['stop'].set_sensitive(True)
            self._play_pause_button.set_related_action(a['play'])
    
    def _get_path_or_uri(self, uri):
        if uri.startswith('file://'):
            return gio.File(uri=uri).get_path() or uri
        return uri
    
    def _update_playlist(self, list, current):
        self._playlist_store.clear()
        for i, track in enumerate(list):
            row = self._make_row(*track)
            row[COL_CURRENT] = (i == current) and 'gtk-media-play' or None
            self._playlist_store.append(row)

    def _get_playlist_length(self):
        return self._playlist_store.iter_n_children(None)

    def _set_current(self, value):
        def func(model, path, iter):
            model.set(iter, COL_CURRENT, 'gtk-media-play' if (path[0] == value) else None)
        self._playlist_store.foreach(func)
        playlist_len = self._get_playlist_length()
        if value == CURRENT_UNSET or playlist_len == 0:
            self._actions['next'].set_sensitive(False)
            self._actions['previous'].set_sensitive(False)
        elif value == 0:
            self._actions['previous'].set_sensitive(False)
            self._actions['next'].set_sensitive(True)
        elif value == (playlist_len - 1):
            self._actions['previous'].set_sensitive(True)
            self._actions['next'].set_sensitive(False)
        else: 
            self._actions['previous'].set_sensitive(True)
            self._actions['next'].set_sensitive(True)
    
    def run(self):
        self._window.present()
        gtk.main()

    def quit(self):
        gtk.main_quit()

    def on_tag_changed_signal(self, uri, tag):
        def func(model, path, iter):
            row_uri, row_path = model.get(iter, 1, 2)
            if row_uri == uri:
                cols = (
                    COL_TITLE, tag.get(gst.TAG_TITLE) or row_path,
                    COL_ARTIST, tag.get(gst.TAG_ARTIST),
                    COL_ALBUM, tag.get(gst.TAG_ALBUM),
                )
                model.set(iter, *cols)
        self._playlist_store.foreach(func)

    def on_state_changed_signal(self, old_state, new_state):
        self._update_state(new_state)
    
    def on_current_changed_signal(self, old_current, new_current):
        self._set_current(new_current)

    def _make_row(self, uri, tag):
        uri = str(uri)
        path = self._get_path_or_uri(uri)
        title = tag.get(gst.TAG_TITLE) or path
        artist = tag.get(gst.TAG_ARTIST)
        album = tag.get(gst.TAG_ALBUM)
        return [None, uri, path, title, artist, album]

    def on_added_signal(self, tracks, position):
        first, tracks = tracks[0], tracks[1:]
        if position == self._get_playlist_length():
            iter = self._playlist_store.append(self._make_row(*first))
        else:
            before = self._playlist_store.get_iter((position, ))
            iter = self._playlist_store.insert_before(before, self._make_row(*first))
        for track in tracks:
            iter = self._playlist_store.insert_after(iter, self._make_row(*track))
    
    def on_removed_signal(self, positions):
        iters = []
        for pos in positions:
            iters.append(self._playlist_store.get_iter((pos, )))
        for iter in iters:
            self._playlist_store.remove(iter)
    
    def on_cleared_signal(self):
        self._playlist_store.clear()
    
    def on_reordered_signal(self, positions):
        self._playlist_store.reorder([int(p) for p in positions])

    def on_add_action_activate(self, action):
        dialog = gtk.FileChooserDialog('Add files', self._window)
        dialog.add_button('Add', gtk.RESPONSE_OK)
        dialog.set_select_multiple(True)
        dialog.set_local_only(False)
        if dialog.run() == gtk.RESPONSE_OK:
            self._player.add(dialog.get_uris(), self._get_playlist_length())
        dialog.destroy()

    def on_remove_action_activate(self, action):
        selection = self._playlist_view.get_selection()
        paths = selection.get_selected_rows()[1]
        if paths:
            self._player.remove([i[0] for i in paths])

    def on_clear_action_activate(self, action):
        self._player.clear()

    def on_previous_action_activate(self, action):
        self._player.previous()
    
    def on_next_action_activate(self, action):
        self._player.next()

    def on_play_action_activate(self, action):
        self._player.play()

    def on_pause_action_activate(self, action):
        self._player.pause()

    def on_stop_action_activate(self, action):
        self._player.stop()

    def on_playlist_view_row_activated(self, view, path, column):
        self._player.set_current_and_play(path[0])

    def on_playlist_view_key_press_event(self, view, event):
        if gtk.gdk.keyval_name(event.keyval) == 'Delete':
            self._actions['remove'].activate()
            return True
        return False

    def on_drag_data_get(self, view, context, selection, info, timestamp):
        paths = view.get_selection().get_selected_rows()[1]
        s = ' '.join(str(p[0]) for p in paths)
        selection.set('positions', 8, s)

    def on_drag_data_received(self, view, context, x, y, selection, info, timestamp):
        drop_info = view.get_dest_row_at_pos(x, y)
        if drop_info:
            path, place = drop_info
            position = path[0]
            if place in (gtk.TREE_VIEW_DROP_AFTER, gtk.TREE_VIEW_DROP_INTO_OR_AFTER):
                position += 1
        else:
            position = -1

        if info == DND_REODER:
            positions = range(self._get_playlist_length())
            moved = [int(i) for i in selection.data.split(' ')]
            for p in moved:
                positions[p] = None
            positions[position:position] =  moved
            positions = [p for p in positions if p is not None]
            self._player.reorder(positions)
        elif info == DND_ADD:
            self._player.add(selection.get_uris(), position)

    def on_main_window_destroy(self, window):
        self.quit()

def main():
    app = Application()
    app.run()
