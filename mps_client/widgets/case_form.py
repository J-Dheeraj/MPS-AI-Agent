"""widgets/case_form.py -- New Case dialog"""
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
from .. import api_client as api
from ..async_bridge import run

AGENCIES  = ["HDB", "CPF", "MSF", "MOH", "MOM", "ICA", "OTHER"]
URGENCIES = ["normal", "urgent"]


class CaseFormDialog(Adw.Dialog):
    def __init__(self, session_id, on_case_created):
        super().__init__()
        self._session_id = session_id
        self._cb         = on_case_created
        self._resident   = None
        self._timer_id   = 0
        self.set_title("New Case")
        self.set_presentation_mode(Adw.DialogPresentationMode.BOTTOM_SHEET)
        toolbar = Adw.ToolbarView()
        self.set_child(toolbar)
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda _: self.close())
        header.pack_start(cancel)
        self._create_btn = Gtk.Button(label="Create")
        self._create_btn.add_css_class("suggested-action")
        self._create_btn.set_sensitive(False)
        self._create_btn.connect("clicked", self._on_create_clicked)
        header.pack_end(self._create_btn)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        toolbar.set_content(scroll)
        clamp = Adw.Clamp(maximum_size=520)
        scroll.set_child(clamp)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(16); box.set_margin_bottom(16)
        box.set_margin_start(16); box.set_margin_end(16)
        clamp.set_child(box)
        # Resident search
        rg = Adw.PreferencesGroup(title="Resident")
        box.append(rg)
        self._res_search = Adw.EntryRow(title="Search name / NRIC (e.g. S****567A)")
        self._res_search.connect("changed", self._on_search_changed)
        rg.add(self._res_search)
        self._res_list = Gtk.ListBox()
        self._res_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._res_list.add_css_class("boxed-list")
        self._res_list.connect("row-activated", self._on_row_activated)
        self._res_list.set_visible(False)
        box.append(self._res_list)
        # New resident form
        self._new_rg = Adw.PreferencesGroup(title="Register New Resident")
        self._new_rg.set_visible(False)
        box.append(self._new_rg)
        self._res_name    = Adw.EntryRow(title="Full name")
        self._res_nric    = Adw.EntryRow(title="NRIC masked (e.g. S****567A)")
        self._res_contact = Adw.EntryRow(title="Contact number")
        for r in (self._res_name, self._res_nric, self._res_contact):
            self._new_rg.add(r)
        nb = Gtk.Button(label="Register as new resident")
        nb.add_css_class("flat")
        nb.connect("clicked", lambda _: self._new_rg.set_visible(True))
        box.append(nb)
        self._res_lbl = Gtk.Label(label="No resident selected")
        self._res_lbl.add_css_class("caption")
        self._res_lbl.set_halign(Gtk.Align.START)
        box.append(self._res_lbl)
        # Case details
        cg = Adw.PreferencesGroup(title="Case Details")
        box.append(cg)
        self._agency_row = Adw.ComboRow(title="Agency")
        am = Gtk.StringList()
        for a in AGENCIES: am.append(a)
        self._agency_row.set_model(am)
        cg.add(self._agency_row)
        self._case_type = Adw.EntryRow(title="Brief issue description")
        cg.add(self._case_type)
        self._urgency_row = Adw.ComboRow(title="Urgency")
        um = Gtk.StringList()
        for u in URGENCIES: um.append(u)
        self._urgency_row.set_model(um)
        cg.add(self._urgency_row)
        self._reappeal_row = Adw.SwitchRow(title="Re-appeal",
                                           subtitle="Same issue rejected before")
        cg.add(self._reappeal_row)
        self._error = Gtk.Label(label="")
        self._error.add_css_class("error")
        self._error.set_visible(False)
        box.append(self._error)
        self._spinner = Gtk.Spinner()
        box.append(self._spinner)

    def _on_search_changed(self, row):
        q = row.get_text().strip()
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = 0
        if len(q) < 2:
            self._res_list.set_visible(False)
            return
        self._timer_id = GLib.timeout_add(300, self._fire_search, q)

    def _fire_search(self, q):
        self._timer_id = 0
        run(api.search_residents(q), on_done=self._show_results)
        return False

    def _show_results(self, results):
        child = self._res_list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self._res_list.remove(child)
            child = nxt
        if not results:
            self._res_list.set_visible(False)
            return
        for r in results[:8]:
            lbl = Gtk.Label(
                label=r.get("name","") + "  |  " + r.get("nric_masked","") + "  |  " + r.get("contact",""),
                xalign=0)
            lbl.set_margin_top(8); lbl.set_margin_bottom(8); lbl.set_margin_start(12)
            lbl._r = r
            self._res_list.append(lbl)
        self._res_list.set_visible(True)

    def _on_row_activated(self, lb, row):
        child = row.get_child()
        r = getattr(child, "_r", None)
        if r:
            self._pick(r)

    def _pick(self, r):
        self._resident = r
        self._res_list.set_visible(False)
        self._new_rg.set_visible(False)
        self._res_lbl.set_label("Selected: " + r["name"] + " (" + r["nric_masked"] + ")")
        self._create_btn.set_sensitive(True)

    def _on_create_clicked(self, _btn):
        if self._new_rg.get_visible() and self._resident is None:
            self._register_then_create()
        else:
            self._do_create()

    def _register_then_create(self):
        name    = self._res_name.get_text().strip()
        nric    = self._res_nric.get_text().strip()
        contact = self._res_contact.get_text().strip()
        if not name or not nric:
            self._show_error("Name and masked NRIC required.")
            return
        if "*" not in nric:
            self._show_error("NRIC must be masked (e.g. S****567A).")
            return
        self._set_busy(True)
        run(api.create_resident(name, nric, contact),
            on_done=self._on_new_res, on_error=self._on_err)

    def _on_new_res(self, resident):
        self._pick(resident)
        self._do_create()

    def _do_create(self):
        self._set_busy(True)
        agency    = AGENCIES[self._agency_row.get_selected()]
        case_type = self._case_type.get_text().strip() or agency
        urgency   = URGENCIES[self._urgency_row.get_selected()]
        run(api.create_case(
                session_id=self._session_id,
                resident_id=self._resident["id"],
                case_type=case_type, agency=agency, urgency=urgency,
                is_new_issue=not self._reappeal_row.get_active()),
            on_done=self._on_case_done, on_error=self._on_err)

    def _on_case_done(self, case):
        self._set_busy(False)
        self.close()
        self._cb(case)

    def _on_err(self, exc):
        self._set_busy(False)
        self._show_error(str(getattr(exc, "detail", exc)))

    def _show_error(self, msg):
        self._error.set_label(msg)
        self._error.set_visible(True)

    def _set_busy(self, busy):
        self._create_btn.set_sensitive(not busy)
        self._spinner.start() if busy else self._spinner.stop()
