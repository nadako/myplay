import os
import gtk
import dbus
import dbus.mainloop.glib
import gio

from myplay.common import BUS_NAME, OBJECT_PATH, OBJECT_INTERFACE
from myplay.common import STATE_READY, STATE_PAUSED, STATE_PLAYING

class Application(object):
    
    def __init__(self):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()
        proxy = bus.get_object(BUS_NAME, OBJECT_PATH, follow_name_owner_changes=True)
        self._player = dbus.Interface(proxy, OBJECT_INTERFACE)

        bus.add_signal_receiver(self.on_added_signal, 'added', OBJECT_INTERFACE)
        bus.add_signal_receiver(self.on_cleared_signal, 'cleared', OBJECT_INTERFACE)
        bus.add_signal_receiver(self.on_removed_signal, 'removed', OBJECT_INTERFACE)
        bus.add_signal_receiver(self.on_current_changed_signal, 'current_changed', OBJECT_INTERFACE)
        bus.add_signal_receiver(self.on_state_changed_signal, 'state_changed', OBJECT_INTERFACE)

        builder = gtk.Builder()
        builder.add_from_file(os.path.join(os.path.dirname(__file__), 'gui.ui'))
        builder.connect_signals(self)
        self._window = builder.get_object('main_window')
        self._playlist_store = builder.get_object('playlist_store')
        self._playlist_view = builder.get_object('playlist_view')
        self._playlist_view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self._playlist_view.enable_model_drag_dest([('text/uri-list', 0, 0)], gtk.gdk.ACTION_DEFAULT)
        self._playlist_view.connect('drag-data-received', self.on_drag_data_received)
        self._play_action = builder.get_object('play_action')
        self._pause_action = builder.get_object('pause_action')
        self._stop_action = builder.get_object('stop_action')
        
        self._update_playlist_store()
        self._update_control_actions(self._player.get_state())

  
    def on_drag_data_received(self, view, context, x, y, selection, info, timestamp):
        uris = [uri for uri in selection.data.split('\r\n') if uri]
        self._player.add(uris)

    def _append_uri(self, uri):
        f = gio.File(uri=uri)
        path = f.get_path() or uri
        self._playlist_store.append((None, path))
    
    def _clear_current(self):
        def func(model, path, iter):
            model.set(iter, 0, None)
        self._playlist_store.foreach(func)
    
    def _set_current(self, position):
        self._clear_current()
        if position != -1:
            iter = self._playlist_store.get_iter((position, ))
            self._playlist_store.set(iter, 0, gtk.STOCK_MEDIA_PLAY)
    
    def _update_playlist_store(self):
        self._playlist_store.clear()
        for uri in self._player.list():
            self._append_uri(uri)
        self._set_current(self._player.get_current())
    
    def _update_control_actions(self, state):
        if state == STATE_READY:
            self._play_action.set_sensitive(True)
            self._pause_action.set_sensitive(False)
            self._stop_action.set_sensitive(False)
        elif state == STATE_PLAYING:
            self._play_action.set_sensitive(False)
            self._pause_action.set_sensitive(True)
            self._stop_action.set_sensitive(True)
        else:
            self._play_action.set_sensitive(True)
            self._pause_action.set_sensitive(False)
            self._stop_action.set_sensitive(True)
    
    def on_state_changed_signal(self, old, new):
        self._update_control_actions(new)
    
    def on_added_signal(self, uris):
        for uri in uris:
            self._append_uri(uri)

    def on_cleared_signal(self):
        self._playlist_store.clear()

    def on_removed_signal(self, positions):
        iters = []
        for pos in positions:
            iters.append(self._playlist_store.get_iter((pos, )))
        for iter in iters:
            self._playlist_store.remove(iter)

    def on_current_changed_signal(self, position):
        self._set_current(position)

    def on_add_action_activate(self, action):
        dialog = gtk.FileChooserDialog('Add files', self._window)
        dialog.add_button('Add', gtk.RESPONSE_OK)
        dialog.set_select_multiple(True)
        if dialog.run() == gtk.RESPONSE_OK:
            self._player.add(dialog.get_uris())
        dialog.destroy()
    
    def on_remove_action_activate(self, action):
        sel = self._playlist_view.get_selection()
        store, paths = sel.get_selected_rows()
        positions = [i[0] for i in paths]
        self._player.remove(positions)
    
    def on_clear_action_activate(self, action):
        self._player.clear()
    
    def on_playlist_view_row_activated(self, view, path, column):
        self._player.set_current(path[0])

    def on_play_action_activate(self, action):
        self._player.play()

    def on_pause_action_activate(self, action):
        self._player.pause()
    
    def on_stop_action_activate(self, action):
        self._player.stop()

    def on_main_window_destroy(self, window):
        self.quit()
    
    def run(self):
        self._window.present()
        gtk.main()
    
    def quit(self):
        self._window.hide()
        gtk.main_quit()
    

def main():
    app = Application()
    app.run()
