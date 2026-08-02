from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk


THEMES = ("cyber", "amber", "ice", "nasa")


class PCCoolerWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app)
        self.set_title("PCCOOLER LCD")
        self.set_default_size(720, 560)

        self.dashboard_process: subprocess.Popen | None = None
        self.preview_file = Path(tempfile.gettempdir()) / "pccooler-gui-preview.png"
        self.gif_path = ""

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        outer.set_margin_top(16)
        outer.set_margin_bottom(16)
        outer.set_margin_start(16)
        outer.set_margin_end(16)
        self.set_child(outer)

        title = Gtk.Label()
        title.set_markup("<span size='x-large' weight='bold'>PCCOOLER LCD Control</span>")
        title.set_halign(Gtk.Align.START)
        outer.append(title)

        subtitle = Gtk.Label(label="Configure the live Linux dashboard and preview it before sending.")
        subtitle.set_halign(Gtk.Align.START)
        subtitle.add_css_class("dim-label")
        outer.append(subtitle)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        outer.append(content)

        controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        controls.set_hexpand(True)
        content.append(controls)

        preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.append(preview_box)

        self.preview = Gtk.Picture()
        self.preview.set_size_request(320, 240)
        self.preview.set_can_shrink(False)
        self.preview.set_content_fit(Gtk.ContentFit.CONTAIN)
        preview_frame = Gtk.Frame()
        preview_frame.set_child(self.preview)
        preview_box.append(preview_frame)

        self.status = Gtk.Label(label="Ready")
        self.status.set_wrap(True)
        self.status.set_halign(Gtk.Align.START)
        preview_box.append(self.status)

        grid = Gtk.Grid(column_spacing=10, row_spacing=10)
        controls.append(grid)

        row = 0
        grid.attach(Gtk.Label(label="Theme", halign=Gtk.Align.START), 0, row, 1, 1)
        self.theme = Gtk.DropDown.new_from_strings(THEMES)
        self.theme.set_selected(0)
        grid.attach(self.theme, 1, row, 1, 1)
        row += 1

        grid.attach(Gtk.Label(label="Title", halign=Gtk.Align.START), 0, row, 1, 1)
        self.title_entry = Gtk.Entry()
        self.title_entry.set_text("PCCOOLER LINUX")
        grid.attach(self.title_entry, 1, row, 1, 1)
        row += 1

        grid.attach(Gtk.Label(label="Background", halign=Gtk.Align.START), 0, row, 1, 1)
        bg_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.background = Gtk.Entry()
        self.background.set_hexpand(True)
        choose_bg = Gtk.Button(label="Choose…")
        choose_bg.connect("clicked", self.on_choose_background)
        bg_row.append(self.background)
        bg_row.append(choose_bg)
        grid.attach(bg_row, 1, row, 1, 1)
        row += 1

        grid.attach(Gtk.Label(label="Refresh", halign=Gtk.Align.START), 0, row, 1, 1)
        self.interval = Gtk.SpinButton.new_with_range(0.5, 10.0, 0.1)
        self.interval.set_value(1.5)
        self.interval.set_digits(1)
        grid.attach(self.interval, 1, row, 1, 1)
        row += 1

        grid.attach(Gtk.Label(label="Panel opacity", halign=Gtk.Align.START), 0, row, 1, 1)
        self.panel_alpha = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 1)
        self.panel_alpha.set_value(205)
        self.panel_alpha.set_hexpand(True)
        grid.attach(self.panel_alpha, 1, row, 1, 1)
        row += 1

        grid.attach(Gtk.Label(label="Background dim", halign=Gtk.Align.START), 0, row, 1, 1)
        self.overlay_alpha = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 1)
        self.overlay_alpha.set_value(55)
        self.overlay_alpha.set_hexpand(True)
        grid.attach(self.overlay_alpha, 1, row, 1, 1)
        row += 1

        self.color_entries = {}
        defaults = {
            "CPU color": "#00E6BE",
            "Memory color": "#1EAAFF",
            "GPU color": "#00E6BE",
            "Text color": "#EBF2FA",
            "Panel color": "#0D1522",
        }
        for label_text, default in defaults.items():
            grid.attach(Gtk.Label(label=label_text, halign=Gtk.Align.START), 0, row, 1, 1)
            entry = Gtk.Entry()
            entry.set_text(default)
            entry.set_width_chars(9)
            self.color_entries[label_text] = entry
            grid.attach(entry, 1, row, 1, 1)
            row += 1

        self.auto_colors = Gtk.CheckButton(label="Match colors to background")
        self.auto_colors.set_active(False)
        controls.append(self.auto_colors)

        self.gif_background = Gtk.CheckButton(label="Use selected GIF as dashboard background")
        self.gif_background.set_active(False)
        controls.append(self.gif_background)

        gif_speed_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        gif_speed_row.append(Gtk.Label(label="GIF minimum frame delay"))
        self.gif_delay = Gtk.SpinButton.new_with_range(0.04, 1.0, 0.01)
        self.gif_delay.set_value(0.06)
        self.gif_delay.set_digits(2)
        gif_speed_row.append(self.gif_delay)
        controls.append(gif_speed_row)

        gif_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        choose_gif = Gtk.Button(label="Choose GIF…")
        choose_gif.connect("clicked", self.on_choose_gif)
        play_gif = Gtk.Button(label="Play GIF")
        play_gif.connect("clicked", self.on_play_gif)
        screensaver_gif = Gtk.Button(label="Screensaver")
        screensaver_gif.connect("clicked", self.on_screensaver)
        stop_gif = Gtk.Button(label="Stop GIF")
        stop_gif.connect("clicked", self.on_stop_dashboard)
        gif_row.append(choose_gif)
        gif_row.append(play_gif)
        gif_row.append(screensaver_gif)
        gif_row.append(stop_gif)
        controls.append(gif_row)

        button_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        controls.append(button_row)

        preview_button = Gtk.Button(label="Render Preview")
        preview_button.connect("clicked", self.on_preview)
        button_row.append(preview_button)

        send_button = Gtk.Button(label="Send Preview")
        send_button.connect("clicked", self.on_send_preview)
        button_row.append(send_button)

        self.start_button = Gtk.Button(label="Start Dashboard")
        self.start_button.add_css_class("suggested-action")
        self.start_button.connect("clicked", self.on_start_dashboard)
        controls.append(self.start_button)

        self.stop_button = Gtk.Button(label="Stop Dashboard")
        self.stop_button.add_css_class("destructive-action")
        self.stop_button.set_sensitive(False)
        self.stop_button.connect("clicked", self.on_stop_dashboard)
        controls.append(self.stop_button)

        diagnose = Gtk.Button(label="Run Diagnostics")
        diagnose.connect("clicked", self.on_diagnose)
        controls.append(diagnose)

        self.connect("close-request", self.on_close)

    def selected_theme(self) -> str:
        return THEMES[self.theme.get_selected()]

    def base_args(self) -> list[str]:
        args = [
            "pccooler-lcd",
            "dashboard",
            "--theme",
            self.selected_theme(),
            "--title",
            self.title_entry.get_text() or "PCCOOLER LINUX",
            "--interval",
            f"{self.interval.get_value():.1f}",
            "--panel-alpha",
            str(int(self.panel_alpha.get_value())),
            "--overlay-alpha",
            str(int(self.overlay_alpha.get_value())),
        ]
        background = self.background.get_text().strip()
        if background:
            args += ["--background", background]
        if self.gif_background.get_active() and self.gif_path:
            args += [
                "--background-gif", self.gif_path,
                "--gif-min-delay", f"{self.gif_delay.get_value():.2f}",
            ]
        if self.auto_colors.get_active():
            args.append("--auto-colors")
        args += [
            "--cpu-color", self.color_entries["CPU color"].get_text(),
            "--memory-color", self.color_entries["Memory color"].get_text(),
            "--gpu-color", self.color_entries["GPU color"].get_text(),
            "--text-color", self.color_entries["Text color"].get_text(),
            "--panel-color", self.color_entries["Panel color"].get_text(),
        ]
        return args

    def set_status(self, text: str) -> None:
        self.status.set_text(text)

    def on_choose_background(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileDialog(title="Choose Background Image")
        image_filter = Gtk.FileFilter()
        image_filter.set_name("Images")
        image_filter.add_mime_type("image/png")
        image_filter.add_mime_type("image/jpeg")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(image_filter)
        dialog.set_filters(filters)
        dialog.open(self, None, self.background_chosen)

    def background_chosen(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return
        path = file.get_path()
        if path:
            self.background.set_text(path)


    def on_choose_gif(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileDialog(title="Choose Animated GIF")
        gif_filter = Gtk.FileFilter()
        gif_filter.set_name("Animated GIF")
        gif_filter.add_mime_type("image/gif")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(gif_filter)
        dialog.set_filters(filters)
        dialog.open(self, None, self.gif_chosen)

    def gif_chosen(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return
        path = file.get_path()
        if path:
            self.gif_path = path
            self.set_status(f"Selected GIF: {Path(path).name}")

    def on_play_gif(self, _button: Gtk.Button) -> None:
        if not self.gif_path:
            self.set_status("Choose an animated GIF first.")
            return
        self.on_stop_dashboard(None)
        try:
            self.dashboard_process = subprocess.Popen(
                ["pccooler-lcd", "play-gif", self.gif_path, "--min-delay", f"{self.gif_delay.get_value():.2f}", "--png-compression", "0"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as error:
            self.set_status(str(error))
            return
        self.start_button.set_sensitive(False)
        self.stop_button.set_sensitive(True)
        self.set_status(f"Playing GIF: {Path(self.gif_path).name}")
        GLib.timeout_add(1000, self.check_dashboard)


    def on_screensaver(self, _button: Gtk.Button) -> None:
        if not self.gif_path:
            self.set_status("Choose an animated GIF first.")
            return
        self.on_stop_dashboard(None)
        try:
            self.dashboard_process = subprocess.Popen(
                [
                    "pccooler-lcd",
                    "screensaver",
                    self.gif_path,
                    "--min-delay",
                    f"{self.gif_delay.get_value():.2f}",
                    "--png-compression",
                    "0",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as error:
            self.set_status(str(error))
            return
        self.start_button.set_sensitive(False)
        self.stop_button.set_sensitive(True)
        self.set_status(f"Screensaver playing: {Path(self.gif_path).name}")
        GLib.timeout_add(1000, self.check_dashboard)

    def on_preview(self, _button: Gtk.Button) -> None:
        command = self.base_args() + [
            "--count", "1",
            "--preview", str(self.preview_file),
            "--quiet",
        ]
        self.run_command(command, self.preview_complete)

    def preview_complete(self, success: bool, output: str) -> None:
        if success and self.preview_file.exists():
            self.preview.set_filename(str(self.preview_file))
            self.set_status("Preview rendered and sent to the LCD.")
        else:
            self.set_status(output or "Preview failed.")

    def on_send_preview(self, _button: Gtk.Button) -> None:
        if not self.preview_file.exists():
            self.set_status("Render a preview first.")
            return
        self.run_command(
            ["pccooler-lcd", "send-image", str(self.preview_file)],
            lambda success, output: self.set_status(
                "Preview sent successfully." if success else output
            ),
        )

    def on_start_dashboard(self, _button: Gtk.Button) -> None:
        if self.dashboard_process and self.dashboard_process.poll() is None:
            self.set_status("Dashboard is already running.")
            return
        try:
            self.dashboard_process = subprocess.Popen(
                self.base_args() + ["--quiet"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as error:
            self.set_status(str(error))
            return
        self.start_button.set_sensitive(False)
        self.stop_button.set_sensitive(True)
        self.set_status("Dashboard started.")
        GLib.timeout_add(1000, self.check_dashboard)

    def check_dashboard(self) -> bool:
        if not self.dashboard_process:
            return False
        result = self.dashboard_process.poll()
        if result is None:
            return True
        message = ""
        if self.dashboard_process.stderr:
            message = self.dashboard_process.stderr.read().strip()
        self.dashboard_process = None
        self.start_button.set_sensitive(True)
        self.stop_button.set_sensitive(False)
        self.set_status(message or "Dashboard stopped.")
        return False

    def on_stop_dashboard(self, _button: Gtk.Button) -> None:
        if self.dashboard_process and self.dashboard_process.poll() is None:
            self.dashboard_process.terminate()
            try:
                self.dashboard_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.dashboard_process.kill()
        self.dashboard_process = None
        self.start_button.set_sensitive(True)
        self.stop_button.set_sensitive(False)
        self.set_status("Dashboard stopped.")

    def on_diagnose(self, _button: Gtk.Button) -> None:
        self.run_command(
            ["pccooler-lcd", "diagnose"],
            lambda success, output: self.set_status(output),
        )

    def run_command(self, command: list[str], callback) -> None:
        self.set_status("Working…")

        def worker() -> None:
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                output = (completed.stdout + completed.stderr).strip()
                success = completed.returncode == 0
            except (OSError, subprocess.SubprocessError) as error:
                output = str(error)
                success = False
            GLib.idle_add(callback, success, output)

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def on_close(self, *_args):
        self.on_stop_dashboard(None)
        return False


class PCCoolerApplication(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id="io.github.pccooler_lcd.Control",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_activate(self) -> None:
        window = self.props.active_window
        if not window:
            window = PCCoolerWindow(self)
        window.present()


def main() -> None:
    app = PCCoolerApplication()
    raise SystemExit(app.run(None))


if __name__ == "__main__":
    main()
