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
import ConfigParser

import dbus
import dbus.mainloop.glib
import os
import gio
import glib
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
        bus.add_signal_receiver(self.on_added_signal, 'Added', OBJECT_IFACE)
        bus.add_signal_receiver(self.on_removed_signal, 'Removed', OBJECT_IFACE)
        bus.add_signal_receiver(self.on_cleared_signal, 'Cleared', OBJECT_IFACE)
        bus.add_signal_receiver(self.on_reordered_signal, 'Reordered', OBJECT_IFACE)
        bus.add_signal_receiver(self.on_current_changed_signal, 'CurrentChanged', OBJECT_IFACE)
        bus.add_signal_receiver(self.on_state_changed_signal, 'StateChanged', OBJECT_IFACE)
        bus.add_signal_receiver(self.on_tag_changed_signal, 'TagChanged', OBJECT_IFACE)
        
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

        config_dir = os.path.join(glib.get_user_config_dir(), 'myplay')
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        self._window_config_path = os.path.join(config_dir, 'window.cfg')

        self._initialize_ui()

    def on_selection_changed(self, selection):
        if selection.count_selected_rows():
            self._actions['remove'].set_sensitive(True)
        else:
            self._actions['remove'].set_sensitive(False)
    
    def _load_window_config(self):
        self._window_config = {
            'x': 0,
            'y': 0,
            'width': 500,
            'height': 600,
            'maximized': False
        }

        if os.path.exists(self._window_config_path):
            cp = ConfigParser.RawConfigParser()
            cp.read(self._window_config_path)
            if cp.has_section('window'):
                try:
                    x = cp.getint('window', 'x')
                    y = cp.getint('window', 'y')
                    width = cp.getint('window', 'width')
                    height = cp.getint('window', 'height')
                    maximized = cp.getboolean('window', 'maximized')
                except:
                    pass
                else:
                    self._window_config['x'] = x
                    self._window_config['y'] = y
                    self._window_config['width'] = width
                    self._window_config['height'] = height
                    self._window_config['maximized'] = maximized
    
    def _save_window_config(self):
        cp = ConfigParser.RawConfigParser()
        cp.add_section('window')
        cp.set('window', 'x', self._window_config['x'])
        cp.set('window', 'y', self._window_config['y'])
        cp.set('window', 'width', self._window_config['width'])
        cp.set('window', 'height', self._window_config['height'])
        cp.set('window', 'maximized', self._window_config['maximized'])
        cp.write(open(self._window_config_path, 'w'))
    
    def _initialize_ui(self):
        self._load_window_config()
        self._window.move(self._window_config['x'], self._window_config['y'])
        self._window.set_default_size(self._window_config['width'], self._window_config['height'])
        if self._window_config['maximized']:
            self._window.maximize()

        self._update_state(self._player.GetState())
        current = self._player.GetCurrent()
        self._update_playlist(self._player.List(), current)
        self._set_current(current)

    def _update_clear_button(self, *args):
        if self._get_playlist_length():
            self._actions['clear'].set_sensitive(True)
        else:
            self._actions['clear'].set_sensitive(False)
    
    def _update_state(self, state):
        a = self._actions
        if state == STATE_READY:
            a['play'].set_sensitive(bool(self._get_playlist_length()))
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
        if self._player.GetState() != STATE_PLAYING:
            self._actions['play'].set_sensitive(True)
    
    def on_removed_signal(self, positions):
        iters = []
        for pos in positions:
            iters.append(self._playlist_store.get_iter((pos, )))
        for iter in iters:
            self._playlist_store.remove(iter)
        if not self._get_playlist_length():
            self._actions['play'].set_sensitive(False)
    
    def on_cleared_signal(self):
        self._playlist_store.clear()
        self._actions['play'].set_sensitive(False)
    
    def on_reordered_signal(self, positions):
        self._playlist_store.reorder([int(p) for p in positions])

    def on_add_action_activate(self, action):
        dialog = gtk.FileChooserDialog('Add files', self._window)
        dialog.add_button('Add', gtk.RESPONSE_OK)
        dialog.set_select_multiple(True)
        dialog.set_local_only(False)
        if dialog.run() == gtk.RESPONSE_OK:
            self._player.Add(dialog.get_uris(), self._get_playlist_length())
        dialog.destroy()

    def on_remove_action_activate(self, action):
        selection = self._playlist_view.get_selection()
        paths = selection.get_selected_rows()[1]
        if paths:
            self._player.Remove([i[0] for i in paths])

    def on_clear_action_activate(self, action):
        self._player.Clear()

    def on_previous_action_activate(self, action):
        self._player.Previous()
    
    def on_next_action_activate(self, action):
        self._player.Next()

    def on_play_action_activate(self, action):
        self._player.Play()

    def on_pause_action_activate(self, action):
        self._player.Pause()

    def on_stop_action_activate(self, action):
        self._player.Stop()

    def on_playlist_view_row_activated(self, view, path, column):
        self._player.SetCurrentAndPlay(path[0])

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
            self._player.Reorder(positions)
        elif info == DND_ADD:
            self._player.Add(selection.get_uris(), position)

    def on_main_window_configure_event(self, window, event):
        if not self._window_config['maximized']:
            self._window_config['x'] = event.x
            self._window_config['y'] = event.y
            self._window_config['width'] = event.width
            self._window_config['height'] = event.height
    
    def on_main_window_state_event(self, window, event):
        self._window_config['maximized'] = bool(event.new_window_state & gtk.gdk.WINDOW_STATE_MAXIMIZED)
        
    def on_main_window_destroy(self, window):
        self._save_window_config()
        self.quit()

def main():
    app = Application()
    app.run()
