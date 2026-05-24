"""
login_window.py  —  AdwApplicationWindow shown before authentication
"""
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from . import api_client as api
from .async_bridge import run


class LoginWindow(Adw.ApplicationWindow):
    def __init__(self, app, on_success):
        super().__init__(application=app)
        self._on_success = on_success
        self.set_title("MPS AI Agent — Login")
        self.set_default_size(400, 380)
        self.set_resizable(False)

        # Root
        toolbar = Adw.ToolbarView()
        self.set_content(toolbar)

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        toolbar.add_top_bar(header)

        # Body
        clamp = Adw.Clamp(maximum_size=340)
        toolbar.set_content(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        box.set_margin_top(32)
        box.set_margin_bottom(32)
        box.set_margin_start(16)
        box.set_margin_end(16)
        clamp.set_child(box)

        # Logo / title
        icon = Gtk.Image.new_from_icon_name("emblem-system-symbolic")
        icon.set_pixel_size(48)
        box.append(icon)

        title = Gtk.Label(label="<b>MPS AI Agent</b>\nVolunteer Portal")
        title.set_use_markup(True)
        title.set_justify(Gtk.Justification.CENTER)
        box.append(title)

        # Form group
        group = Adw.PreferencesGroup()
        box.append(group)

        self._username = Adw.EntryRow(title="Username")
        self._username.connect("entry-activated", self._on_enter)
        group.add(self._username)

        self._password = Adw.PasswordEntryRow(title="Password")
        self._password.connect("entry-activated", self._on_enter)
        group.add(self._password)

        # Error label (hidden until needed)
        self._error = Gtk.Label(label="")
        self._error.add_css_class("error")
        self._error.set_visible(False)
        box.append(self._error)

        # Login button
        self._btn = Gtk.Button(label="Log In")
        self._btn.add_css_class("suggested-action")
        self._btn.add_css_class("pill")
        self._btn.connect("clicked", self._on_login_clicked)
        box.append(self._btn)

        self._spinner = Gtk.Spinner()
        box.append(self._spinner)

    def _on_enter(self, _widget):
        self._on_login_clicked(None)

    def _on_login_clicked(self, _btn):
        username = self._username.get_text().strip()
        password = self._password.get_text()
        if not username or not password:
            self._show_error("Enter username and password.")
            return
        self._set_busy(True)
        run(
            api.login(username, password),
            on_done=self._login_ok,
            on_error=self._login_fail,
        )

    def _login_ok(self, _result):
        self._set_busy(False)
        self._on_success()

    def _login_fail(self, exc):
        self._set_busy(False)
        detail = getattr(exc, "detail", str(exc))
        if "locked" in str(detail).lower():
            msg = "Account locked — too many failed attempts."
        elif "incorrect" in str(detail).lower() or "401" in str(exc):
            msg = "Incorrect username or password."
        else:
            msg = f"Login failed: {detail}"
        self._show_error(msg)

    def _show_error(self, msg):
        self._error.set_label(msg)
        self._error.set_visible(True)

    def _set_busy(self, busy):
        self._btn.set_sensitive(not busy)
        self._username.set_sensitive(not busy)
        self._password.set_sensitive(not busy)
        if busy:
            self._spinner.start()
        else:
            self._spinner.stop()
