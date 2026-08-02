from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import subprocess
import tempfile
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from .dashboard import collect_stats
from .layout import Layout, Widget, WIDGET_DEFAULTS, clone_default, default_layout, load_layout, render_layout, save_layout
from .theme_engine import generate_contrast_theme


class WidgetChip(Gtk.Frame):
    def __init__(self, widget: Widget, selected_callback, moved_callback):
        super().__init__()
        self.widget_data = widget
        self.selected_callback = selected_callback
        self.moved_callback = moved_callback
        self.drag_origin = (0.0, 0.0)

        label = Gtk.Label(label=widget.label or widget.kind.upper())
        label.set_ellipsize(3)
        self.set_child(label)
        self.set_size_request(widget.width, widget.height)
        self.add_css_class("card")

        click = Gtk.GestureClick()
        click.connect("pressed", self.on_click)
        self.add_controller(click)

        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self.on_drag_begin)
        drag.connect("drag-update", self.on_drag_update)
        drag.connect("drag-end", self.on_drag_end)
        self.add_controller(drag)

    def on_click(self, *_args):
        self.selected_callback(self)

    def on_drag_begin(self, _gesture, _x, _y):
        self.drag_origin = (self.widget_data.x, self.widget_data.y)
        self.selected_callback(self)

    def on_drag_update(self, _gesture, dx, dy):
        x = max(0, min(320 - self.widget_data.width, int(self.drag_origin[0] + dx)))
        y = max(0, min(240 - self.widget_data.height, int(self.drag_origin[1] + dy)))
        self.widget_data.x = x
        self.widget_data.y = y
        parent = self.get_parent()
        if isinstance(parent, Gtk.Fixed):
            parent.move(self, x, y)
        self.moved_callback(self)

    def on_drag_end(self, *_args):
        self.moved_callback(self)


class StudioWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("PCCOOLER-LCD Control — Theme Studio")
        self.set_default_size(1040, 700)

        self.layout = default_layout()
        self.selected_chip: WidgetChip | None = None
        self.dashboard_process = None
        self.preview_path = Path(tempfile.gettempdir()) / "pccooler-studio-preview.png"

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.set_margin_top(10); root.set_margin_bottom(10)
        root.set_margin_start(10); root.set_margin_end(10)
        self.set_child(root)

        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label="PCCOOLER-LCD Control"))
        root.append(header)

        save_btn = Gtk.Button(label="Save Layout")
        save_btn.connect("clicked", self.save_layout_dialog)
        header.pack_end(save_btn)
        load_btn = Gtk.Button(label="Open Layout")
        load_btn.connect("clicked", self.open_layout_dialog)
        header.pack_end(load_btn)

        notebook = Gtk.Notebook()
        notebook.set_hexpand(True); notebook.set_vexpand(True)
        root.append(notebook)

        notebook.append_page(self.build_designer(), Gtk.Label(label="Screen Designer"))
        notebook.append_page(self.build_theme_studio(), Gtk.Label(label="Theme Studio"))
        notebook.append_page(self.build_widget_library(), Gtk.Label(label="Widget Library"))

        self.status = Gtk.Label(label="Ready")
        self.status.set_halign(Gtk.Align.START)
        root.append(self.status)

        self.refresh_canvas()
        GLib.timeout_add_seconds(1, self.refresh_preview)

    def build_designer(self):
        page = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        page.set_margin_top(12); page.set_margin_bottom(12)
        page.set_margin_start(12); page.set_margin_end(12)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        page.append(left)

        self.canvas = Gtk.Fixed()
        self.canvas.set_size_request(640, 480)
        frame = Gtk.Frame()
        frame.set_child(self.canvas)
        left.append(frame)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        left.append(controls)
        preview_btn = Gtk.Button(label="Render Preview")
        preview_btn.connect("clicked", lambda *_: self.render_and_show())
        controls.append(preview_btn)
        send_btn = Gtk.Button(label="Send Preview")
        send_btn.connect("clicked", self.send_preview)
        controls.append(send_btn)
        start_btn = Gtk.Button(label="Start Layout Dashboard")
        start_btn.connect("clicked", self.start_dashboard)
        controls.append(start_btn)
        stop_btn = Gtk.Button(label="Stop")
        stop_btn.connect("clicked", self.stop_dashboard)
        controls.append(stop_btn)

        self.preview = Gtk.Picture()
        self.preview.set_size_request(320, 240)
        left.append(self.preview)

        inspector = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inspector.set_size_request(280, -1)
        page.append(inspector)
        inspector.append(Gtk.Label(label="Widget Inspector", xalign=0))

        self.fields = {}
        for name in ("label", "x", "y", "width", "height", "foreground", "accent", "background", "opacity", "font_size"):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            row.append(Gtk.Label(label=name.replace("_", " ").title(), xalign=0, width_chars=12))
            entry = Gtk.Entry()
            entry.connect("changed", self.inspector_changed, name)
            row.append(entry)
            inspector.append(row)
            self.fields[name] = entry

        self.show_border_check = Gtk.CheckButton(label="Show border")
        self.show_border_check.connect("toggled", self.toggle_widget_option, "show_border")
        inspector.append(self.show_border_check)

        self.show_graph_check = Gtk.CheckButton(label="Show graph/bar")
        self.show_graph_check.connect("toggled", self.toggle_widget_option, "show_graph")
        inspector.append(self.show_graph_check)

        delete = Gtk.Button(label="Delete Widget")
        delete.add_css_class("destructive-action")
        delete.connect("clicked", self.delete_selected)
        inspector.append(delete)
        return page

    def build_theme_studio(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(18); box.set_margin_start(18)

        self.layout_name = Gtk.Entry(text=self.layout.name)
        box.append(Gtk.Label(label="Layout Name", xalign=0))
        box.append(self.layout_name)

        self.bg_entry = Gtk.Entry(text=self.layout.background)
        box.append(Gtk.Label(label="Background Image", xalign=0))
        bgrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bgrow.append(self.bg_entry)
        choose = Gtk.Button(label="Choose…")
        choose.connect("clicked", self.choose_background)
        bgrow.append(choose)
        box.append(bgrow)

        self.background_mode = Gtk.DropDown.new_from_strings(("Auto detect", "Static image", "Animated GIF"))
        self.background_mode.set_selected(0)
        box.append(Gtk.Label(label="Background Type", xalign=0))
        box.append(self.background_mode)

        self.background_fit = Gtk.DropDown.new_from_strings(("Cover / crop", "Contain / letterbox"))
        self.background_fit.set_selected(0)
        box.append(Gtk.Label(label="Background Fit", xalign=0))
        box.append(self.background_fit)

        self.bg_color = Gtk.Entry(text=self.layout.background_color)
        box.append(Gtk.Label(label="Background Color", xalign=0))
        box.append(self.bg_color)

        self.overlay = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 1)
        self.overlay.set_value(self.layout.overlay_alpha)
        box.append(Gtk.Label(label="Background Darkening", xalign=0))
        box.append(self.overlay)

        self.global_borders = Gtk.CheckButton(label="Show borders on all widgets")
        self.global_borders.set_active(True)
        box.append(self.global_borders)

        self.global_graphs = Gtk.CheckButton(label="Show graphs/bars on supported widgets")
        self.global_graphs.set_active(True)
        box.append(self.global_graphs)

        apply_visibility = Gtk.Button(label="Apply Border/Graph Settings to All Widgets")
        apply_visibility.connect("clicked", self.apply_global_visibility)
        box.append(apply_visibility)

        contrast_btn = Gtk.Button(label="Generate High-Contrast Theme")
        contrast_btn.add_css_class("suggested-action")
        contrast_btn.connect("clicked", self.generate_contrast_theme)
        box.append(contrast_btn)

        self.palette_status = Gtk.Label(label="Choose a wallpaper, then generate a readable theme.")
        self.palette_status.set_wrap(True)
        self.palette_status.set_xalign(0)
        box.append(self.palette_status)

        apply_btn = Gtk.Button(label="Apply Theme")
        apply_btn.connect("clicked", self.apply_theme)
        box.append(apply_btn)

        export_btn = Gtk.Button(label="Export Theme Package")
        export_btn.connect("clicked", self.export_theme)
        box.append(export_btn)
        return box

    def build_widget_library(self):
        box = Gtk.FlowBox()
        box.set_selection_mode(Gtk.SelectionMode.NONE)
        box.set_margin_top(18); box.set_margin_start(18)
        descriptions = {
            "clock":"Digital clock", "date":"Date and year", "cpu":"CPU usage and temperature",
            "memory":"RAM usage", "gpu":"GPU usage and temperature", "disk":"Disk usage",
            "network":"Network throughput", "uptime":"System uptime", "text":"Custom text",
            "image":"Static image widget",
        }
        for kind in WIDGET_DEFAULTS:
            button = Gtk.Button()
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            content.append(Gtk.Label(label=kind.upper()))
            content.append(Gtk.Label(label=descriptions[kind], wrap=True))
            button.set_child(content)
            button.set_size_request(180, 90)
            button.connect("clicked", self.add_widget, kind)
            box.insert(button, -1)
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(box)
        return scroll

    def refresh_canvas(self):
        child = self.canvas.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.canvas.remove(child)
            child = next_child
        for widget in self.layout.widgets:
            chip = WidgetChip(widget, self.select_chip, self.widget_moved)
            chip.set_size_request(widget.width * 2, widget.height * 2)
            self.canvas.put(chip, widget.x * 2, widget.y * 2)

    def select_chip(self, chip):
        self.selected_chip = chip
        data = chip.widget_data
        for name, entry in self.fields.items():
            entry.handler_block_by_func(self.inspector_changed)
            entry.set_text(str(getattr(data, name)))
            entry.handler_unblock_by_func(self.inspector_changed)

        self.show_border_check.handler_block_by_func(self.toggle_widget_option)
        self.show_border_check.set_active(bool(data.show_border))
        self.show_border_check.handler_unblock_by_func(self.toggle_widget_option)

        self.show_graph_check.handler_block_by_func(self.toggle_widget_option)
        self.show_graph_check.set_active(bool(data.show_graph))
        self.show_graph_check.handler_unblock_by_func(self.toggle_widget_option)

    def widget_moved(self, chip):
        # canvas is displayed at 2x; drag coordinates need scaling back
        parent = chip.get_parent()
        self.render_and_show()

    def toggle_widget_option(self, check, name):
        if not self.selected_chip:
            return
        setattr(
            self.selected_chip.widget_data,
            name,
            bool(check.get_active()),
        )
        self.render_and_show()

    def inspector_changed(self, entry, name):
        if not self.selected_chip:
            return
        value = entry.get_text()
        data = self.selected_chip.widget_data
        try:
            if name in ("x","y","width","height","opacity","font_size"):
                value = int(value)
            setattr(data, name, value)
        except ValueError:
            return
        self.refresh_canvas()
        self.render_and_show()

    def add_widget(self, _button, kind):
        widget = clone_default(kind)
        widget.x = min(300-widget.width, 20 + len(self.layout.widgets)*8)
        widget.y = min(220-widget.height, 20 + len(self.layout.widgets)*6)
        self.layout.widgets.append(widget)
        self.refresh_canvas()
        self.status.set_text(f"Added {kind} widget")

    def delete_selected(self, *_args):
        if not self.selected_chip:
            return
        self.layout.widgets.remove(self.selected_chip.widget_data)
        self.selected_chip = None
        self.refresh_canvas()
        self.render_and_show()

    def apply_global_visibility(self, *_args):
        borders = bool(self.global_borders.get_active())
        graphs = bool(self.global_graphs.get_active())

        for widget in self.layout.widgets:
            widget.show_border = borders
            if widget.kind in ("cpu", "memory", "gpu"):
                widget.show_graph = graphs

        self.refresh_canvas()
        self.render_and_show()
        self.status.set_text(
            f"Borders {'on' if borders else 'off'}; "
            f"graphs {'on' if graphs else 'off'}"
        )

    def generate_contrast_theme(self, *_args):
        path = Path(self.bg_entry.get_text()).expanduser()
        if not path.is_file():
            self.palette_status.set_text("Choose a valid wallpaper or GIF first.")
            return
    
        try:
            palette = generate_contrast_theme(path)
        except Exception as error:
            self.palette_status.set_text(f"Could not analyze background: {error}")
            return
    
        self.bg_color.set_text(str(palette["background_average"]))
        self.overlay.set_value(int(palette["overlay_alpha"]))
    
        assignments = {
            "cpu": str(palette["cpu"]),
            "memory": str(palette["memory"]),
            "gpu": str(palette["gpu"]),
        }
    
        for widget in self.layout.widgets:
            widget.foreground = str(palette["text"])
            widget.background = str(palette["panel"])
            widget.opacity = int(palette["panel_opacity"])
            if widget.kind in assignments:
                widget.accent = assignments[widget.kind]
            elif widget.kind in ("clock", "date", "network"):
                widget.accent = str(palette["memory"])
            else:
                widget.accent = str(palette["cpu"])
    
        self.palette_status.set_markup(
            "<b>Readable palette applied</b>  "
            f"Text {palette['text']}  Panel {palette['panel']}  "
            f"Accents {palette['cpu']}, {palette['memory']}, {palette['gpu']}"
        )
        self.refresh_canvas()
        self.render_and_show()
    
    def sync_theme_fields(self):
        self.layout.name = self.layout_name.get_text()
        self.layout.background = self.bg_entry.get_text()
        self.layout.background_type = ("auto", "static", "gif")[self.background_mode.get_selected()]
        self.layout.background_fit = ("cover", "contain")[self.background_fit.get_selected()]
        self.layout.background_color = self.bg_color.get_text()
        self.layout.overlay_alpha = int(self.overlay.get_value())

    def apply_theme(self, *_args):
        self.sync_theme_fields()
        self.render_and_show()

    def render_and_show(self):
        self.sync_theme_fields()
        image = render_layout(self.layout, collect_stats())
        image.save(self.preview_path)
        self.preview.set_filename(str(self.preview_path))
        return image

    def refresh_preview(self):
        self.render_and_show()
        return True

    def send_preview(self, *_args):
        self.render_and_show()
        self.run_async(["pccooler-lcd", "send-image", str(self.preview_path)])

    def start_dashboard(self, *_args):
        self.stop_dashboard()
        layout_file = Path(tempfile.gettempdir()) / "pccooler-active-layout.json"
        save_layout(self.layout, layout_file)
        self.dashboard_process = subprocess.Popen(
            ["pccooler-lcd", "layout-dashboard", str(layout_file), "--quiet"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
        )
        self.status.set_text("Layout dashboard started")

    def stop_dashboard(self, *_args):
        if self.dashboard_process and self.dashboard_process.poll() is None:
            self.dashboard_process.terminate()
        self.dashboard_process = None
        self.status.set_text("Dashboard stopped")

    def choose_background(self, *_args):
        dialog = Gtk.FileDialog(title="Choose Background")
        dialog.open(self, None, self.background_chosen)

    def background_chosen(self, dialog, result):
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return
        if file.get_path():
            path = file.get_path()
            self.bg_entry.set_text(path)
            self.background_mode.set_selected(2 if path.lower().endswith(".gif") else 1)
            self.generate_contrast_theme()

    def save_layout_dialog(self, *_args):
        dialog = Gtk.FileDialog(title="Save Layout")
        dialog.set_initial_name("pccooler-layout.json")
        dialog.save(self, None, self.layout_saved)

    def layout_saved(self, dialog, result):
        try:
            file = dialog.save_finish(result)
        except GLib.Error:
            return
        self.apply_theme()
        save_layout(self.layout, file.get_path())
        self.status.set_text(f"Saved {file.get_path()}")

    def open_layout_dialog(self, *_args):
        dialog = Gtk.FileDialog(title="Open Layout")
        dialog.open(self, None, self.layout_opened)

    def layout_opened(self, dialog, result):
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return
        self.layout = load_layout(file.get_path())
        self.layout_name.set_text(self.layout.name)
        self.bg_entry.set_text(self.layout.background)
        self.bg_color.set_text(self.layout.background_color)
        mode_map = {"auto": 0, "static": 1, "gif": 2}
        self.background_mode.set_selected(mode_map.get(self.layout.background_type, 0))
        self.background_fit.set_selected(1 if self.layout.background_fit == "contain" else 0)
        self.overlay.set_value(self.layout.overlay_alpha)
        self.refresh_canvas()
        self.render_and_show()

    def export_theme(self, *_args):
        dialog = Gtk.FileDialog(title="Export Theme")
        dialog.set_initial_name("pccooler-theme.json")
        dialog.save(self, None, self.theme_exported)

    def theme_exported(self, dialog, result):
        try:
            file = dialog.save_finish(result)
        except GLib.Error:
            return
        data = {
            "name": self.layout_name.get_text(),
            "background": self.bg_entry.get_text(),
            "background_type": ("auto", "static", "gif")[self.background_mode.get_selected()],
            "background_fit": ("cover", "contain")[self.background_fit.get_selected()],
            "background_color": self.bg_color.get_text(),
            "overlay_alpha": int(self.overlay.get_value()),
        }
        Path(file.get_path()).write_text(json.dumps(data, indent=2))
        self.status.set_text(f"Exported theme {file.get_path()}")

    def run_async(self, command):
        self.status.set_text("Working…")
        def worker():
            completed = subprocess.run(command, capture_output=True, text=True)
            output = (completed.stdout + completed.stderr).strip()
            GLib.idle_add(self.status.set_text, output or "Complete")
        threading.Thread(target=worker, daemon=True).start()


class StudioApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="io.github.pccooler_lcd.Studio")

    def do_activate(self):
        window = self.props.active_window or StudioWindow(self)
        window.present()


def main():
    app = StudioApplication()
    raise SystemExit(app.run(None))


if __name__ == "__main__":
    main()
