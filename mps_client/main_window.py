"""
main_window.py  --  AdwApplicationWindow for authenticated volunteers
Layout:
  Left panel:  session status bar + case list + New Case button
  Right panel: LetterView (streaming draft + copy button)
  Top bar:     user info + policy Q&A button + logout
"""
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from . import api_client as api
from .async_bridge import run
from .widgets.case_form import CaseFormDialog
from .widgets.letter_view import LetterView
from .widgets.vetter_view import VetterPanel


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app, on_logout):
        super().__init__(application=app)
        self._on_logout   = on_logout
        self._session     = None
        self._cases       = []
        self._refresh_id  = 0

        self.set_title("MPS AI Agent")
        self.set_default_size(1100, 700)

        # ── Root ──────────────────────────────────────────────────────────────
        toolbar = Adw.ToolbarView()
        self.set_content(toolbar)

        # Header bar
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_box.set_halign(Gtk.Align.CENTER)
        title_lbl = Gtk.Label(label="MPS AI Agent")
        title_lbl.add_css_class("title-4")
        title_box.append(title_lbl)
        header.set_title_widget(title_box)

        # Header right: user name + logout
        self._user_lbl = Gtk.Label(label=api.auth.full_name + " (" + api.auth.role + ")")
        self._user_lbl.add_css_class("caption")
        header.pack_end(self._user_lbl)

        logout_btn = Gtk.Button(label="Logout")
        logout_btn.add_css_class("flat")
        logout_btn.connect("clicked", self._on_logout_clicked)
        header.pack_end(logout_btn)

        # Header left: Q&A button
        qa_btn = Gtk.Button(label="Policy Q&A")
        qa_btn.add_css_class("flat")
        qa_btn.connect("clicked", self._open_qa_panel)
        header.pack_start(qa_btn)

        # ── Body: split pane ──────────────────────────────────────────────────
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(340)
        toolbar.set_content(paned)

        # ── Left panel: session + case list ───────────────────────────────────
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        paned.set_start_child(left_box)
        paned.set_shrink_start_child(False)

        # Session status banner
        self._session_banner = Adw.Banner(title="Loading session...")
        self._session_banner.set_revealed(True)
        left_box.append(self._session_banner)

        # New case button
        new_case_btn = Gtk.Button(label="+ New Case")
        new_case_btn.add_css_class("suggested-action")
        new_case_btn.set_margin_top(8)
        new_case_btn.set_margin_start(8)
        new_case_btn.set_margin_end(8)
        new_case_btn.set_margin_bottom(4)
        new_case_btn.connect("clicked", self._on_new_case)
        left_box.append(new_case_btn)

        # Case list
        case_scroll = Gtk.ScrolledWindow(vexpand=True)
        case_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        left_box.append(case_scroll)

        self._case_list = Gtk.ListBox()
        self._case_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._case_list.add_css_class("navigation-sidebar")
        self._case_list.connect("row-selected", self._on_case_selected)
        case_scroll.set_child(self._case_list)

        self._empty_label = Gtk.Label(label="No cases yet.  Click + New Case to begin.")
        self._empty_label.set_justify(Gtk.Justification.CENTER)
        self._empty_label.add_css_class("dim-label")
        self._empty_label.set_margin_top(32)
        self._case_list.set_placeholder(self._empty_label)

        # Refresh button at bottom
        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.add_css_class("flat")
        refresh_btn.set_margin_start(8); refresh_btn.set_margin_end(8)
        refresh_btn.set_margin_bottom(8)
        refresh_btn.connect("clicked", self._refresh)
        left_box.append(refresh_btn)

        # ── Right panel: letter view ──────────────────────────────────────────
        right_scroll = Gtk.ScrolledWindow()
        right_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        paned.set_end_child(right_scroll)

        if api.auth.role in ("vetter", "admin"):
            self._letter_view = None
            self._vetter_panel = VetterPanel()
            right_scroll.set_child(self._vetter_panel)
        else:
            self._vetter_panel = None
            self._letter_view = LetterView(on_submitted=self._on_case_submitted)
    
        right_scroll.set_child(self._letter_view)

        # ── Q&A overlay (hidden) ──────────────────────────────────────────────
        self._qa_overlay = self._build_qa_panel()

        # Initial load
        self._refresh()
        # Auto-refresh every 60 s
        self._refresh_id = GLib.timeout_add_seconds(60, self._auto_refresh)

    def _build_qa_panel(self):
        """Build the policy Q&A slide-over panel (hidden by default)."""
        dlg = Adw.Dialog()
        dlg.set_title("Policy Q&A")
        dlg.set_presentation_mode(Adw.DialogPresentationMode.FLOATING)

        toolbar = Adw.ToolbarView()
        dlg.set_child(toolbar)
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(8); box.set_margin_bottom(8)
        box.set_margin_start(8); box.set_margin_end(8)
        box.set_size_request(480, 500)
        toolbar.set_content(box)

        q_lbl = Gtk.Label(label="Ask a policy question:")
        q_lbl.set_halign(Gtk.Align.START)
        box.append(q_lbl)

        qa_entry = Gtk.Entry()
        qa_entry.set_placeholder_text("e.g. What is the income ceiling for HDB BTO?")
        box.append(qa_entry)

        qa_btn = Gtk.Button(label="Ask")
        qa_btn.add_css_class("suggested-action")
        box.append(qa_btn)

        qa_spinner = Gtk.Spinner()
        box.append(qa_spinner)

        ans_scroll = Gtk.ScrolledWindow(vexpand=True)
        ans_scroll.set_min_content_height(300)
        ans_buf = Gtk.TextBuffer()
        ans_view = Gtk.TextView(buffer=ans_buf)
        ans_view.set_wrap_mode(Gtk.WrapMode.WORD)
        ans_view.set_editable(False)
        ans_view.set_left_margin(8); ans_view.set_right_margin(8)
        ans_view.set_top_margin(8); ans_view.set_bottom_margin(8)
        ans_scroll.set_child(ans_view)
        box.append(ans_scroll)

        def on_ask(_btn):
            q = qa_entry.get_text().strip()
            if not q:
                return
            ans_buf.set_text("")
            qa_btn.set_sensitive(False)
            qa_spinner.start()
            run(api.stream_qa(
                question=q,
                on_chunk=lambda text: (
                    ans_buf.insert(ans_buf.get_end_iter(), text)
                ),
                on_done=lambda: (
                    qa_btn.set_sensitive(True),
                    qa_spinner.stop(),
                ),
                on_error=lambda msg: (
                    ans_buf.set_text("Error: " + str(msg)),
                    qa_btn.set_sensitive(True),
                    qa_spinner.stop(),
                ),
            ))

        qa_btn.connect("clicked", on_ask)
        qa_entry.connect("activate", on_ask)

        return dlg

    # ── Session ───────────────────────────────────────────────────────────────

    def _refresh(self, *_):
        run(api.get_current_session(),
            on_done=self._on_session_loaded,
            on_error=lambda _: self._session_banner.set_title("Could not reach server"))
        run(api.get_my_cases(),
            on_done=self._populate_cases)

    def _auto_refresh(self):
        self._refresh()
        return True  # keep timer alive

    def _on_session_loaded(self, session):
        self._session = session
        if session is None:
            self._session_banner.set_title("No active session tonight")
        else:
            date     = session.get("date", "")
            total    = session.get("total_cases", 0)
            complete = session.get("completed_cases", 0)
            self._session_banner.set_title(
                date + "  —  " + str(complete) + "/" + str(total) + " cases done"
            )

    # ── Cases ─────────────────────────────────────────────────────────────────

    def _populate_cases(self, cases):
        self._cases = cases

        # Clear existing rows
        child = self._case_list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self._case_list.remove(child)
            child = nxt

        for case in cases:
            row = self._build_case_row(case)
            row._case = case
            self._case_list.append(row)

    def _build_case_row(self, case):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(8); box.set_margin_bottom(8)
        box.set_margin_start(12); box.set_margin_end(12)
        row.set_child(box)

        agency    = case.get("agency", "")
        case_type = case.get("case_type", "")
        status    = case.get("status", "")

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.append(top)

        name_lbl = Gtk.Label(label=agency + " — " + case_type)
        name_lbl.set_halign(Gtk.Align.START)
        name_lbl.add_css_class("body")
        top.append(name_lbl)

        status_lbl = Gtk.Label(label=status)
        status_lbl.set_halign(Gtk.Align.END)
        status_lbl.set_hexpand(True)
        status_lbl.add_css_class("caption")
        if status == "returned":
            status_lbl.add_css_class("error")
        elif status == "drafted":
            status_lbl.add_css_class("warning")
        elif status == "vetted":
            status_lbl.add_css_class("success")
        top.append(status_lbl)

        res = case.get("resident", {}) or {}
        res_lbl = Gtk.Label(
            label=res.get("name", "") + "  " + res.get("nric_masked", "")
        )
        res_lbl.set_halign(Gtk.Align.START)
        res_lbl.add_css_class("caption")
        res_lbl.add_css_class("dim-label")
        box.append(res_lbl)

        return row

    def _on_case_selected(self, listbox, row):
        if row is None:
            return
        case = getattr(row, "_case", None)
        if case:
            self._letter_view.load_case(case)

    def _on_case_submitted(self, case_id):
        """Called when volunteer submits a case — refresh list."""
        self._refresh()

    # ── New Case ──────────────────────────────────────────────────────────────

    def _on_new_case(self, _btn):
        if self._session is None:
            dialog = Adw.AlertDialog(
                heading="No Active Session",
                body="There is no active MPS session tonight. Ask an admin to open one.",
            )
            dialog.add_response("ok", "OK")
            dialog.present(self)
            return

        dlg = CaseFormDialog(
            session_id=self._session["id"],
            on_case_created=self._on_new_case_created,
        )
        dlg.present(self)

    def _on_new_case_created(self, case):
        self._refresh()
        # Select the new case
        GLib.timeout_add(500, self._select_case_by_id, case["id"])

    def _select_case_by_id(self, case_id):
        child = self._case_list.get_first_child()
        while child:
            c = getattr(child, "_case", {})
            if c.get("id") == case_id:
                self._case_list.select_row(child)
                break
            child = child.get_next_sibling()
        return False

    # ── Q&A ───────────────────────────────────────────────────────────────────

    def _open_qa_panel(self, _btn):
        self._qa_overlay.present(self)

    # ── Logout ────────────────────────────────────────────────────────────────

    def _on_logout_clicked(self, _btn):
        if self._refresh_id:
            GLib.source_remove(self._refresh_id)
            self._refresh_id = 0
        run(api.logout())
        self._on_logout()
