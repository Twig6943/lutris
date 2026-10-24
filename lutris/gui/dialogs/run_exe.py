import os
from gettext import gettext as _
from typing import TYPE_CHECKING, cast

from gi.repository import GLib, Gtk

from lutris.database import games as games_db
from lutris.gui.dialogs import ModelessDialog
from lutris.util import system
from lutris.util.linux import LINUX_SYSTEM

if TYPE_CHECKING:
    from lutris.gui.application import LutrisApplication


class RunExeDialog(ModelessDialog):
    def __init__(self, filename: str, parent: Gtk.Window | None = None) -> None:
        super().__init__(title=_("Open Windows executable"), parent=parent, border_width=12)
        self.filename = filename
        # Detect if it's a URI (has scheme other than file)
        self.is_uri = False
        if isinstance(filename, str):
            if filename.startswith("file://"):
                self.is_uri = False
            elif "://" in filename:
                self.is_uri = True
            elif ":" in filename and not os.path.isabs(filename) and not filename.startswith(("/dev/", "~")):
                scheme = filename.split(":", 1)[0]
                if scheme and scheme.replace("-", "").replace("+", "").replace(".", "").isalnum() and len(scheme) > 1:
                    self.is_uri = True
        self.set_default_size(480, 360)

        self.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        self.run_button = self.add_default_button(_("Run"), Gtk.ResponseType.OK)
        self.run_button.set_sensitive(False)

        content = self.get_content_area()
        content.set_spacing(12)
        content.add(Gtk.Label(label=os.path.basename(filename) if not self.is_uri else filename, xalign=0, wrap=True))
        if self.is_uri:
            content.add(Gtk.Label(label=_("Select the game whose Wine prefix should open this URI."), xalign=0, wrap=True))
        else:
            content.add(Gtk.Label(label=_("Select the game whose Wine prefix should run this file."), xalign=0, wrap=True))

        portal_dir = os.path.join(GLib.get_user_runtime_dir(), "doc")
        if LINUX_SYSTEM.is_flatpak() and not self.is_uri and system.path_contains(portal_dir, filename):
            content.add(
                Gtk.Label(
                    label=_(
                        "Other files in its folder may not be accessible."
                        "If it needs those files, move the folder to a location accessible to Lutris."
                    ),
                    xalign=0,
                    wrap=True,
                )
            )

        store = Gtk.ListStore(str, str)
        store.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        for game in games_db.get_games(filters={"installed": 1, "runner": "wine"}):
            if game["configpath"]:
                store.append([str(game["id"]), game["name"]])
        self.games = Gtk.TreeView(model=store, headers_visible=False, search_column=1)
        self.games.append_column(Gtk.TreeViewColumn(_("Game"), Gtk.CellRendererText(), text=1))
        self.games.get_selection().connect("changed", self.on_selection_changed)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.add(self.games)
        content.pack_start(scroll, True, True, 0)
        if not store:
            content.add(Gtk.Label(label=_("No installed Wine games were found."), xalign=0))
        self.show_all()

    def on_selection_changed(self, selection: Gtk.TreeSelection) -> None:
        _model, selected = selection.get_selected()
        self.run_button.set_sensitive(selected is not None)

    def on_response(self, dialog: Gtk.Dialog, response: Gtk.ResponseType) -> None:
        if response != Gtk.ResponseType.OK:
            super().on_response(dialog, response)
            return
        model, selected = self.games.get_selection().get_selected()
        if selected is None or not self.run_button.get_sensitive():
            return
        application = cast("LutrisApplication", self.get_application())
        if self.is_uri:
            if application.run_executable(model[selected][0], self.filename, is_uri=True):
                self.run_button.set_sensitive(False)
                self.destroy()
            return
        if application.run_executable(model[selected][0], self.filename):
            self.run_button.set_sensitive(False)
            self.destroy()
