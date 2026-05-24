"""
widgets/vetter_view.py
Vetter panel: review queue of submitted cases, view letter drafts,
approve (vetter-pass) or return with comment (vetter-return).
"""
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, GLib

from .. import api_client as api
from ..async_bridge import run


class VetterPanel(Gtk.Box):
    """
    Full-width panel for vetter role.
    Left: queue of cases pending vetting
    Right: letter read-only view + approve/return actions
    """

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._cases  = []
        self._case   = None
        self._letter = None

        # ── Left: queue list ──────────────────────────────────────────────────
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        left_box.set_size_request(320, -1)
        self.append(left_box)

        queue_hdr = Gtk.Label(label="Cases for vetting")
        queue_hdr.add_css_class("title-4")
        queue_hdr.set_margin_top(12); queue_hdr.set_margin_start(12)
        queue_hdr.set_margin_bottom(8)
        queue_hdr.set_halign(Gtk.Align.START)
        left_box.append(queue_hdr)

        refresh_btn = Gtk.Button(label="Refresh queue")
        refresh_btn.add_css_class("flat")
        refresh_btn.set_margin_start(8); refresh_btn.set_margin_end(8)
        refresh_btn.set_margin_bottom(4)
        refresh_btn.connect("clicked", self._load_queue)
        left_box.append(refresh_btn)

        q_scroll = Gtk.ScrolledWindow(vexpand=True)
        q_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        left_box.append(q_scroll)

        self._queue_list = Gtk.ListBox()
        self._queue_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._queue_list.add_css_class("navigation-sidebar")
        self._queue_list.connect("row-selected", self._on_queue_row_selected)
        q_scroll.set_child(self._queue_list)

        empty_lbl = Gtk.Label(label="Queue is empty  —  all cases vetted!")
        empty_lbl.add_css_class("dim-label")
        empty_lbl.set_margin_top(32)
        self._queue_list.set_placeholder(empty_lbl)

        self.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        # ── Right: letter review ──────────────────────────────────────────────
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True)
        right_box.set_margin_top(8); right_box.set_margin_bottom(8)
        right_box.set_margin_start(8); right_box.set_margin_end(8)
        self.append(right_box)

        self._case_header = Gtk.Label(label="Select a case from the queue")
        self._case_header.set_halign(Gtk.Align.START)
        self._case_header.add_css_class("title-3")
        right_box.append(self._case_header)

        self._resident_lbl = Gtk.Label(label="")
        self._resident_lbl.set_halign(Gtk.Align.START)
        self._resident_lbl.add_css_class("caption")
        right_box.append(self._resident_lbl)

        right_box.append(Gtk.Separator())

        # Letter content (read-only for vetter)
        letter_lbl = Gtk.Label(label="Draft letter:")
        letter_lbl.set_halign(Gtk.Align.START)
        right_box.append(letter_lbl)

        letter_scroll = Gtk.ScrolledWindow(vexpand=True)
        letter_scroll.set_min_content_height(300)
        letter_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._letter_buf = Gtk.TextBuffer()
        self._letter_view = Gtk.TextView(buffer=self._letter_buf)
        self._letter_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._letter_view.set_editable(False)
        self._letter_view.set_left_margin(8); self._letter_view.set_right_margin(8)
        self._letter_view.set_top_margin(8); self._letter_view.set_bottom_margin(8)
        letter_scroll.set_child(self._letter_view)
        right_box.append(letter_scroll)

        # Return comment
        return_lbl = Gtk.Label(label="Comment for volunteer (required when returning):")
        return_lbl.set_halign(Gtk.Align.START)
        right_box.append(return_lbl)
        self._comment_entry = Gtk.Entry()
        self._comment_entry.set_placeholder_text("e.g. Please add the reference number from the last rejection letter")
        right_box.append(self._comment_entry)

        # Action buttons
        action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        action_row.set_halign(Gtk.Align.END)
        right_box.append(action_row)

        self._copy_btn = Gtk.Button(label="Copy to Clipboard")
        self._copy_btn.add_css_class("pill")
        self._copy_btn.set_sensitive(False)
        self._copy_btn.connect("clicked", self._on_copy)
        action_row.append(self._copy_btn)

        self._return_btn = Gtk.Button(label="Return to volunteer")
        self._return_btn.add_css_class("destructive-action")
        self._return_btn.set_sensitive(False)
        self._return_btn.connect("clicked", self._on_return)
        action_row.append(self._return_btn)

        self._pass_btn = Gtk.Button(label="Approve draft")
        self._pass_btn.add_css_class("suggested-action")
        self._pass_btn.set_sensitive(False)
        self._pass_btn.connect("clicked", self._on_approve)
        action_row.append(self._pass_btn)

        self._status_lbl = Gtk.Label(label="")
        self._status_lbl.add_css_class("caption")
        right_box.append(self._status_lbl)

        # Initial load
        self._load_queue()

    # ── Queue ─────────────────────────────────────────────────────────────────

    def _load_queue(self, *_):
        run(api.get_vetter_queue(), on_done=self._populate_queue)

    def _populate_queue(self, cases):
        self._cases = cases
        child = self._queue_list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self._queue_list.remove(child)
            child = nxt
        for case in cases:
            row = self._build_queue_row(case)
            row._case = case
            self._queue_list.append(row)

    def _build_queue_row(self, case):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(8); box.set_margin_bottom(8)
        box.set_margin_start(12); box.set_margin_end(12)
        row.set_child(box)

        agency    = case.get("agency", "")
        case_type = case.get("case_type", "")
        urgency   = case.get("urgency", "normal")

        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.append(top_box)

        lbl = Gtk.Label(label=agency + " — " + case_type)
        lbl.set_halign(Gtk.Align.START)
        lbl.add_css_class("body")
        top_box.append(lbl)

        if urgency == "urgent":
            urg_lbl = Gtk.Label(label="URGENT")
            urg_lbl.add_css_class("error")
            urg_lbl.add_css_class("caption")
            top_box.append(urg_lbl)

        res = case.get("resident", {}) or {}
        res_lbl = Gtk.Label(label=res.get("name", "") + "  " + res.get("nric_masked", ""))
        res_lbl.set_halign(Gtk.Align.START)
        res_lbl.add_css_class("caption")
        res_lbl.add_css_class("dim-label")
        box.append(res_lbl)

        return row

    def _on_queue_row_selected(self, listbox, row):
        if row is None:
            return
        case = getattr(row, "_case", None)
        if case:
            self._load_case(case)

    # ── Case / Letter ─────────────────────────────────────────────────────────

    def _load_case(self, case):
        self._case = case
        self._letter = None
        self._letter_buf.set_text("")
        self._status_lbl.set_label("")
        self._comment_entry.set_text("")

        agency    = case.get("agency", "")
        case_type = case.get("case_type", "")
        self._case_header.set_label(agency + " — " + case_type)

        res = case.get("resident", {}) or {}
        self._resident_lbl.set_label(
            res.get("name", "") + "  |  " + res.get("nric_masked", "")
        )

        letter_id = case.get("letter_id")
        if letter_id:
            run(api.get_letter(letter_id),
                on_done=self._populate_letter, on_error=self._on_err)
        else:
            self._status_lbl.set_label("No letter draft found.")
            self._set_actions_sensitive(False)

    def _populate_letter(self, letter):
        self._letter = letter
        content = letter.get("draft_content") or letter.get("final_content") or ""
        self._letter_buf.set_text(content)
        self._set_actions_sensitive(True)

    def _set_actions_sensitive(self, enabled):
        self._pass_btn.set_sensitive(enabled)
        self._return_btn.set_sensitive(enabled)
        self._copy_btn.set_sensitive(enabled)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_copy(self, _btn):
        buf  = self._letter_buf
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(text)
        self._copy_btn.set_label("Copied!")
        GLib.timeout_add(2000, lambda: (self._copy_btn.set_label("Copy to Clipboard"), False)[1])

    def _on_approve(self, _btn):
        if not self._case:
            return
        self._set_actions_sensitive(False)
        self._status_lbl.set_label("Approving...")
        run(api.vetter_pass(self._case["id"]),
            on_done=self._on_action_done, on_error=self._on_err)

    def _on_return(self, _btn):
        if not self._case:
            return
        comment = self._comment_entry.get_text().strip()
        if not comment:
            self._status_lbl.set_label("Enter a comment before returning to volunteer.")
            return
        self._set_actions_sensitive(False)
        self._status_lbl.set_label("Returning...")
        run(api.vetter_return(self._case["id"], comment),
            on_done=self._on_action_done, on_error=self._on_err)

    def _on_action_done(self, _result):
        self._status_lbl.set_label("Done.")
        self._case   = None
        self._letter = None
        self._letter_buf.set_text("")
        self._case_header.set_label("Select a case from the queue")
        self._resident_lbl.set_label("")
        self._set_actions_sensitive(False)
        # Reload queue
        GLib.timeout_add(500, self._load_queue)

    def _on_err(self, exc):
        self._status_lbl.set_label("Error: " + str(getattr(exc, "detail", exc)))
        self._set_actions_sensitive(True)
