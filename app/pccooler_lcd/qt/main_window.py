from __future__ import annotations

from pathlib import Path
from dataclasses import asdict
import json
import subprocess
import tempfile

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QGraphicsPixmapItem,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QInputDialog,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from PIL import Image, ImageSequence
from PIL.ImageQt import ImageQt

from ..dashboard import collect_stats
from ..layout import (
    Layout,
    Widget,
    WIDGET_DEFAULTS,
    clone_default,
    default_layout,
    load_layout,
    render_layout,
    save_layout,
)
from ..theme_engine import generate_contrast_theme
from ..media import (
    MediaSource,
    MediaError,
    detect_media_type,
    validate_media_path,
)
from ..paths import ensure_tree
from ..settings import load_settings, save_settings
from ..platform import config_dir
from .canvas import DesignScene, DesignView, WidgetGraphicsItem


DARK_STYLE = """
QMainWindow, QWidget {
    background: #171A1F;
    color: #E8EDF2;
}
QDockWidget::title {
    background: #22262D;
    padding: 8px;
    font-weight: 600;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QListWidget {
    background: #22262D;
    border: 1px solid #343A44;
    border-radius: 5px;
    padding: 5px;
}
QPushButton {
    background: #2B313B;
    border: 1px solid #3B4350;
    border-radius: 6px;
    padding: 7px 10px;
}
QPushButton:hover {
    background: #353D49;
}
QPushButton#primary {
    background: #0D7C72;
    border-color: #12A89A;
}
QToolBar {
    background: #20242B;
    border-bottom: 1px solid #343A44;
    spacing: 6px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PCCOOLER-LCD Control 3")
        self.resize(1280, 780)
        self.setStyleSheet(DARK_STYLE)

        self.paths = ensure_tree()
        self.config_dir = self.paths["root"]
        self.layout_library_dir = self.paths["layouts"]
        self.startup_config_path = self.paths["startup"]
        self.settings = load_settings()

        self.layout_model = default_layout()
        self.layout_path: Path | None = None
        self.config_dir = config_dir()
        self.layout_library_dir = self.config_dir / "layouts"
        self.layout_library_dir.mkdir(parents=True, exist_ok=True)
        self.startup_config_path = self.config_dir / "startup.json"
        self.dashboard_process: subprocess.Popen | None = None
        self.preview_path = Path(tempfile.gettempdir()) / "pccooler-qt-preview.png"
        self.media_source = None
        self.failed_media_paths: set[Path] = set()
        self.last_media_warning = ""

        self.scene = DesignScene()
        self.view = DesignView(self.scene)
        self.setCentralWidget(self.view)
        self.scene.selection_changed.connect(self.on_selection_changed)

        self.build_toolbar()
        self.build_widget_library()
        self.build_layout_library()
        self.build_properties_dock()
        self.build_theme_dock()
        self.build_preview_dock()
        self.build_settings_dock()
        self.populate_scene()
        self.load_startup_layout()

        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self.update_preview)
        self.preview_timer.start(100)
        self.statusBar().showMessage("Ready")

    def build_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        actions = [
            ("New", self.new_layout),
            ("Open", self.open_layout),
            ("Save", self.save_layout),
            ("Save As", self.save_layout_as),
            ("Duplicate", self.duplicate_layout),
            ("Preview", self.update_preview),
            ("Send", self.send_preview),
            ("Start", self.start_dashboard),
            ("Stop", self.stop_dashboard),
        ]
        for text, callback in actions:
            action = QAction(text, self)
            action.triggered.connect(callback)
            toolbar.addAction(action)

    def build_widget_library(self):
        dock = QDockWidget("Widget Library", self)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        list_widget = QListWidget()
        for kind in WIDGET_DEFAULTS:
            item = QListWidgetItem(kind.upper())
            item.setData(Qt.UserRole, kind)
            list_widget.addItem(item)
        list_widget.itemDoubleClicked.connect(self.add_widget_from_item)
        dock.setWidget(list_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

    def build_layout_library(self):
        dock = QDockWidget("Layouts", self)
        dock.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
        )

        container = QWidget()
        layout = QVBoxLayout(container)

        self.layout_list = QListWidget()
        self.layout_list.itemDoubleClicked.connect(
            self.load_layout_from_library
        )
        layout.addWidget(self.layout_list)

        button_row = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_to_library)
        button_row.addWidget(save_button)

        duplicate_button = QPushButton("Duplicate")
        duplicate_button.clicked.connect(self.duplicate_layout)
        button_row.addWidget(duplicate_button)

        rename_button = QPushButton("Rename")
        rename_button.clicked.connect(self.rename_library_layout)
        button_row.addWidget(rename_button)

        startup_button = QPushButton("Set Startup")
        startup_button.clicked.connect(self.set_startup_layout)
        button_row.addWidget(startup_button)

        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(self.delete_library_layout)
        button_row.addWidget(delete_button)

        layout.addLayout(button_row)

        dock.setWidget(container)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self.refresh_layout_library()

    def refresh_layout_library(self):
        if not hasattr(self, "layout_list"):
            return
        self.layout_list.clear()
        startup = self.startup_layout_path()
        for path in sorted(
            self.layout_library_dir.glob("*.json")
        ):
            label = path.stem
            if startup and path.resolve() == startup.resolve():
                label = f"★ {label}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, str(path))
            self.layout_list.addItem(item)

    def safe_layout_filename(self, name):
        cleaned = "".join(
            char if char.isalnum() or char in ("-", "_", " ")
            else "_"
            for char in name.strip()
        ).strip()
        cleaned = cleaned.replace(" ", "-")
        return cleaned or "layout"

    def unique_library_path(self, name):
        stem = self.safe_layout_filename(name)
        path = self.layout_library_dir / f"{stem}.json"
        counter = 2
        while path.exists():
            path = self.layout_library_dir / f"{stem}-{counter}.json"
            counter += 1
        return path

    def save_to_library(self):
        self.sync_theme()
        default_name = (
            self.layout_model.name
            or "My Layout"
        )
        name, accepted = QInputDialog.getText(
            self,
            "Save Layout",
            "Layout name:",
            text=default_name,
        )
        if not accepted or not name.strip():
            return

        self.layout_model.name = name.strip()

        existing = None
        for path in self.layout_library_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
            except Exception:
                continue
            if data.get("name") == self.layout_model.name:
                existing = path
                break

        target = existing or self.unique_library_path(name)
        save_layout(self.layout_model, target)
        self.layout_path = target
        self.refresh_layout_library()
        self.statusBar().showMessage(
            f"Saved layout: {self.layout_model.name}",
            3000,
        )

    def load_layout_from_library(self, item):
        path = Path(item.data(Qt.UserRole))
        if not path.is_file():
            self.refresh_layout_library()
            return

        self.layout_model = load_layout(path)
        self.layout_path = path
        self.background_entry.setText(
            self.layout_model.background
        )
        self.background_type.setCurrentIndex(
            {
                "auto": 0,
                "static": 1,
                "gif": 2,
            }.get(self.layout_model.background_type, 0)
        )
        self.background_fit.setCurrentIndex(
            1
            if self.layout_model.background_fit == "contain"
            else 0
        )
        self.overlay_spin.setValue(
            self.layout_model.overlay_alpha
        )
        self.load_media_preview(
            self.layout_model.background,
            notify=True,
        )
        self.populate_scene()
        self.statusBar().showMessage(
            f"Loaded layout: {self.layout_model.name}",
            3000,
        )

    def duplicate_layout(self):
        self.sync_theme()
        source_name = self.layout_model.name or "Layout"
        name, accepted = QInputDialog.getText(
            self,
            "Duplicate Layout",
            "New layout name:",
            text=f"{source_name} Copy",
        )
        if not accepted or not name.strip():
            return

        duplicate_data = json.loads(
            json.dumps(
                {
                    "name": self.layout_model.name,
                    "background": self.layout_model.background,
                    "background_type": self.layout_model.background_type,
                    "background_fit": self.layout_model.background_fit,
                    "background_color": self.layout_model.background_color,
                    "overlay_alpha": self.layout_model.overlay_alpha,
                    "widgets": [
                        vars(widget)
                        for widget in self.layout_model.widgets
                    ],
                }
            )
        )

        from ..layout import Widget, Layout

        duplicate = Layout(
            name=name.strip(),
            background=duplicate_data["background"],
            background_type=duplicate_data["background_type"],
            background_fit=duplicate_data["background_fit"],
            background_color=duplicate_data["background_color"],
            overlay_alpha=duplicate_data["overlay_alpha"],
            widgets=[
                Widget(**widget)
                for widget in duplicate_data["widgets"]
            ],
        )

        target = self.unique_library_path(name)
        save_layout(duplicate, target)
        self.layout_model = duplicate
        self.layout_path = target
        self.refresh_layout_library()
        self.populate_scene()
        self.statusBar().showMessage(
            f"Duplicated layout as: {duplicate.name}",
            3000,
        )

    def rename_library_layout(self):
        item = self.layout_list.currentItem()
        if not item:
            return
        path = Path(item.data(Qt.UserRole))
        if not path.is_file():
            return

        layout_model = load_layout(path)
        name, accepted = QInputDialog.getText(
            self,
            "Rename Layout",
            "New layout name:",
            text=layout_model.name or path.stem,
        )
        if not accepted or not name.strip():
            return

        layout_model.name = name.strip()
        target = self.unique_library_path(name)
        save_layout(layout_model, target)
        path.unlink(missing_ok=True)

        if self.layout_path == path:
            self.layout_path = target
            self.layout_model.name = layout_model.name

        self.refresh_layout_library()
        self.statusBar().showMessage(
            f"Renamed layout to: {layout_model.name}",
            3000,
        )

    def startup_layout_path(self):
        if not self.startup_config_path.is_file():
            return None
        try:
            data = json.loads(
                self.startup_config_path.read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, ValueError):
            return None

        raw_path = data.get("layout")
        if not raw_path:
            return None
        path = Path(raw_path).expanduser()
        return path if path.is_file() else None

    def set_startup_layout(self):
        item = self.layout_list.currentItem()
        if item:
            path = Path(item.data(Qt.UserRole))
        elif self.layout_path:
            path = Path(self.layout_path)
        else:
            QMessageBox.warning(
                self,
                "Startup Layout",
                "Save or select a layout first.",
            )
            return

        if not path.is_file():
            QMessageBox.warning(
                self,
                "Startup Layout",
                "The selected layout file does not exist.",
            )
            return

        self.startup_config_path.write_text(
            json.dumps(
                {
                    "layout": str(path.resolve()),
                    "name": self.layout_model.name,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self.refresh_layout_library()
        self.statusBar().showMessage(
            f"Startup layout: {self.layout_model.name}",
            4000,
        )

    def load_startup_layout(self):
        path = self.startup_layout_path()
        if not path:
            return False

        try:
            self.layout_model = load_layout(path)
        except Exception:
            return False

        self.layout_path = path
        self.background_entry.setText(
            self.layout_model.background
        )
        self.background_type.setCurrentIndex(
            {
                "auto": 0,
                "static": 1,
                "gif": 2,
            }.get(self.layout_model.background_type, 0)
        )
        self.background_fit.setCurrentIndex(
            1
            if self.layout_model.background_fit == "contain"
            else 0
        )
        self.overlay_spin.setValue(
            self.layout_model.overlay_alpha
        )
        self.load_media_preview(
            self.layout_model.background,
            notify=True,
        )
        self.populate_scene()
        self.statusBar().showMessage(
            f"Loaded startup layout: {self.layout_model.name}",
            4000,
        )
        return True

    def delete_library_layout(self):
        item = self.layout_list.currentItem()
        if not item:
            return
        path = Path(item.data(Qt.UserRole))
        answer = QMessageBox.question(
            self,
            "Delete Layout",
            f"Delete '{item.text()}'?",
        )
        if answer != QMessageBox.Yes:
            return

        path.unlink(missing_ok=True)
        if self.layout_path == path:
            self.layout_path = None
        self.refresh_layout_library()
        self.statusBar().showMessage(
            f"Deleted layout: {item.text()}",
            3000,
        )

    def build_properties_dock(self):
        dock = QDockWidget("Properties", self)
        widget = QWidget()
        form = QFormLayout(widget)
        self.property_fields = {}

        for name in ("label", "x", "y", "width", "height", "font_size", "opacity"):
            if name in ("x", "y", "width", "height", "font_size", "opacity"):
                editor = QSpinBox()
                editor.setRange(0, 1000)
            else:
                editor = QLineEdit()
            editor.setProperty("field_name", name)
            if isinstance(editor, QLineEdit):
                editor.editingFinished.connect(self.apply_properties)
            else:
                editor.valueChanged.connect(self.apply_properties)
            form.addRow(name.replace("_", " ").title(), editor)
            self.property_fields[name] = editor

        self.color_buttons = {}
        for name in ("foreground", "accent", "background"):
            button = QPushButton()
            button.clicked.connect(lambda checked=False, n=name: self.choose_widget_color(n))
            form.addRow(name.title(), button)
            self.color_buttons[name] = button

        self.label_check = QCheckBox("Show label")
        self.label_check.toggled.connect(self.apply_properties)
        form.addRow(self.label_check)

        self.border_check = QCheckBox("Show border")
        self.border_check.toggled.connect(self.apply_properties)
        form.addRow(self.border_check)

        self.graph_check = QCheckBox("Show graph / bar")
        self.graph_check.toggled.connect(self.apply_properties)
        form.addRow(self.graph_check)

        self.percentage_check = QCheckBox("Show percentage")
        self.percentage_check.toggled.connect(self.apply_properties)
        form.addRow(self.percentage_check)

        self.temperature_check = QCheckBox("Show temperature")
        self.temperature_check.toggled.connect(self.apply_properties)
        form.addRow(self.temperature_check)

        self.memory_gb_check = QCheckBox("Show memory GB")
        self.memory_gb_check.toggled.connect(self.apply_properties)
        form.addRow(self.memory_gb_check)

        delete_button = QPushButton("Delete Widget")
        delete_button.clicked.connect(self.delete_selected)
        form.addRow(delete_button)

        dock.setWidget(widget)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def build_theme_dock(self):
        dock = QDockWidget("Theme Studio", self)
        widget = QWidget()
        layout = QFormLayout(widget)

        self.background_entry = QLineEdit()
        choose = QPushButton("Choose…")
        choose.clicked.connect(self.choose_background)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.background_entry)
        row_layout.addWidget(choose)
        layout.addRow("Wallpaper", row)

        self.background_type = QComboBox()
        self.background_type.addItems(["Auto detect", "Static image", "Animated GIF", "MP4 / Video"])
        layout.addRow("Type", self.background_type)

        self.background_fit = QComboBox()
        self.background_fit.addItems(["Cover / crop", "Contain / letterbox"])
        layout.addRow("Fit", self.background_fit)

        self.overlay_spin = QSpinBox()
        self.overlay_spin.setRange(0, 255)
        self.overlay_spin.setValue(self.layout_model.overlay_alpha)
        layout.addRow("Background dim", self.overlay_spin)

        contrast = QPushButton("Generate Contrast Theme")
        contrast.setObjectName("primary")
        contrast.clicked.connect(self.generate_theme)
        layout.addRow(contrast)

        self.global_borders = QCheckBox("Borders on all widgets")
        self.global_borders.setChecked(True)
        layout.addRow(self.global_borders)

        self.global_graphs = QCheckBox("Graphs on supported widgets")
        self.global_graphs.setChecked(True)
        layout.addRow(self.global_graphs)

        apply_global = QPushButton("Apply to All Widgets")
        apply_global.clicked.connect(self.apply_global_flags)
        layout.addRow(apply_global)

        dock.setWidget(widget)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def build_preview_dock(self):
        dock = QDockWidget("Live Preview", self)
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.preview_label = QLabel()
        self.preview_label.setFixedSize(320, 240)
        self.preview_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.preview_label)
        dock.setWidget(widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)


    def build_settings_dock(self):
        dock = QDockWidget("Settings", self)
        widget = QWidget()
        form = QFormLayout(widget)

        self.device_entry = QLineEdit(self.settings.device)
        form.addRow("Device", self.device_entry)

        self.refresh_spin = QDoubleSpinBox()
        self.refresh_spin.setRange(0.1, 30.0)
        self.refresh_spin.setDecimals(1)
        self.refresh_spin.setValue(self.settings.refresh_interval)
        form.addRow("Refresh seconds", self.refresh_spin)

        self.video_fps_spin = QDoubleSpinBox()
        self.video_fps_spin.setRange(1.0, 30.0)
        self.video_fps_spin.setDecimals(1)
        self.video_fps_spin.setValue(self.settings.video_fps)
        form.addRow("Video FPS", self.video_fps_spin)

        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_app_settings)
        form.addRow(save_button)

        dock.setWidget(widget)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def save_app_settings(self):
        self.settings.device = self.device_entry.text().strip() or self.settings.device
        self.settings.refresh_interval = self.refresh_spin.value()
        self.settings.video_fps = self.video_fps_spin.value()
        if self.layout_path:
            self.settings.last_layout = str(self.layout_path)
        save_settings(self.settings)
        self.statusBar().showMessage("Settings saved", 3000)

    def populate_scene(self):
        self.scene.clear()
        for widget in self.layout_model.widgets:
            item = WidgetGraphicsItem(widget)
            self.scene.addItem(item)
        self.scene.setSceneRect(0, 0, 320, 240)
        self.update_preview()

    def selected_item(self):
        selected = self.scene.selectedItems()
        return selected[0] if selected else None

    def on_selection_changed(self, item):
        if not isinstance(item, WidgetGraphicsItem):
            return
        widget = item.widget
        for name, editor in self.property_fields.items():
            value = getattr(widget, name)
            if isinstance(editor, QLineEdit):
                editor.setText(str(value))
            else:
                editor.blockSignals(True)
                editor.setValue(int(value))
                editor.blockSignals(False)
        for name, button in self.color_buttons.items():
            color = getattr(widget, name)
            button.setText(color)
            button.setStyleSheet(f"background:{color}; color:white;")
        self.label_check.blockSignals(True)
        self.label_check.setChecked(widget.show_label)
        self.label_check.blockSignals(False)

        self.border_check.blockSignals(True)
        self.border_check.setChecked(widget.show_border)
        self.border_check.blockSignals(False)
        self.graph_check.blockSignals(True)
        self.graph_check.setChecked(widget.show_graph)
        self.graph_check.blockSignals(False)

        self.percentage_check.blockSignals(True)
        self.percentage_check.setChecked(widget.show_percentage)
        self.percentage_check.setEnabled(widget.kind in ("cpu", "memory", "gpu"))
        self.percentage_check.blockSignals(False)

        self.temperature_check.blockSignals(True)
        self.temperature_check.setChecked(widget.show_temperature)
        self.temperature_check.setEnabled(widget.kind in ("cpu", "gpu"))
        self.temperature_check.blockSignals(False)

        self.memory_gb_check.blockSignals(True)
        self.memory_gb_check.setChecked(widget.show_memory_gb)
        self.memory_gb_check.setEnabled(widget.kind == "memory")
        self.memory_gb_check.blockSignals(False)

    def apply_properties(self):
        item = self.selected_item()
        if not isinstance(item, WidgetGraphicsItem):
            return
        widget = item.widget
        for name, editor in self.property_fields.items():
            setattr(widget, name, editor.text() if isinstance(editor, QLineEdit) else editor.value())
        widget.show_label = self.label_check.isChecked()
        widget.show_border = self.border_check.isChecked()
        widget.show_graph = self.graph_check.isChecked()
        widget.show_percentage = self.percentage_check.isChecked()
        widget.show_temperature = self.temperature_check.isChecked()
        widget.show_memory_gb = self.memory_gb_check.isChecked()
        item.setPos(widget.x, widget.y)
        item.refresh_style()
        self.update_preview()

    def choose_widget_color(self, name):
        item = self.selected_item()
        if not isinstance(item, WidgetGraphicsItem):
            return
        current = QColor(getattr(item.widget, name))
        color = QColorDialog.getColor(current, self, f"Choose {name}")
        if color.isValid():
            setattr(item.widget, name, color.name())
            self.on_selection_changed(item)
            item.refresh_style()
            self.update_preview()

    def add_widget_from_item(self, item):
        kind = item.data(Qt.UserRole)
        widget = clone_default(kind)
        widget.x = min(300 - widget.width, 20 + len(self.layout_model.widgets) * 8)
        widget.y = min(220 - widget.height, 20 + len(self.layout_model.widgets) * 6)
        self.layout_model.widgets.append(widget)
        graphics = WidgetGraphicsItem(widget)
        self.scene.addItem(graphics)
        graphics.setSelected(True)
        self.update_preview()

    def delete_selected(self):
        item = self.selected_item()
        if not isinstance(item, WidgetGraphicsItem):
            return
        self.layout_model.widgets.remove(item.widget)
        self.scene.removeItem(item)
        self.update_preview()

    def choose_background(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Wallpaper",
            str(Path.home()),
            "Media (*.png *.jpg *.jpeg *.webp *.gif *.mp4 *.m4v *.mov *.webm)",
        )
        if not path:
            return
        self.background_entry.setText(path)
        lower = path.lower()
        is_gif = lower.endswith(".gif")
        is_video = lower.endswith((".mp4", ".m4v", ".mov", ".webm"))
        self.background_type.setCurrentIndex(
            3 if is_video else (2 if is_gif else 1)
        )
        if self.load_media_preview(path):
            self.generate_theme()

    def load_media_preview(self, path, *, notify=True):
        if self.media_source is not None:
            self.media_source.close()
            self.media_source = None

        resolved, error = validate_media_path(path)
        if resolved is None and error is None:
            return False

        if error:
            if resolved is not None:
                self.failed_media_paths.add(resolved)
            self.last_media_warning = error
            if notify:
                self.statusBar().showMessage(
                    f"{error} — using layout fallback background",
                    10000,
                )
            return False

        assert resolved is not None
        try:
            self.media_source = MediaSource(
                resolved,
                size=(320, 240),
                fit=("cover", "contain")[
                    self.background_fit.currentIndex()
                ],
                fps=self.settings.video_fps,
            )
        except Exception as error:
            self.failed_media_paths.add(resolved)
            self.last_media_warning = str(error)
            if notify:
                self.statusBar().showMessage(
                    f"Could not load media: {error} — using fallback",
                    10000,
                )
            return False

        self.failed_media_paths.discard(resolved)
        self.last_media_warning = ""
        if notify:
            self.statusBar().showMessage(
                f"Loaded {self.media_source.kind} background",
                4000,
            )
        return True

    def load_gif_preview(self, path):
        # Compatibility alias for saved layouts from earlier releases.
        self.load_media_preview(path)

    def sync_theme(self):
        self.layout_model.background = self.background_entry.text().strip()
        selected_type = ("auto", "static", "gif", "video")[self.background_type.currentIndex()]
        if selected_type == "auto" and self.layout_model.background:
            selected_type = detect_media_type(self.layout_model.background)
        self.layout_model.background_type = selected_type
        self.layout_model.background_fit = ("cover", "contain")[self.background_fit.currentIndex()]
        self.layout_model.overlay_alpha = self.overlay_spin.value()

    def generate_theme(self):
        self.sync_theme()
        path = Path(self.layout_model.background).expanduser()
        if not path.is_file():
            self.statusBar().showMessage(
                "Choose a valid wallpaper, GIF, or video first.",
                7000,
            )
            return
        try:
            palette = generate_contrast_theme(path)
        except Exception as error:
            self.statusBar().showMessage(
                f"Theme analysis failed: {error}",
                10000,
            )
            return
        self.overlay_spin.setValue(int(palette["overlay_alpha"]))
        for widget in self.layout_model.widgets:
            widget.foreground = str(palette["text"])
            widget.background = str(palette["panel"])
            widget.opacity = int(palette["panel_opacity"])
            if widget.kind == "cpu":
                widget.accent = str(palette["cpu"])
            elif widget.kind == "memory":
                widget.accent = str(palette["memory"])
            elif widget.kind == "gpu":
                widget.accent = str(palette["gpu"])
            else:
                widget.accent = str(palette["memory"])
        self.populate_scene()
        self.statusBar().showMessage("High-contrast theme applied", 3000)

    def apply_global_flags(self):
        borders = self.global_borders.isChecked()
        graphs = self.global_graphs.isChecked()
        for widget in self.layout_model.widgets:
            widget.show_border = borders
            if widget.kind in ("cpu", "memory", "gpu"):
                widget.show_graph = graphs
        self.populate_scene()

    def update_preview(self):
        self.sync_theme()
        background_frame = None
        resolved, validation_error = validate_media_path(
            self.layout_model.background
        )

        if validation_error:
            if (
                resolved is not None
                and resolved not in self.failed_media_paths
            ):
                self.load_media_preview(resolved, notify=True)
        elif resolved is not None:
            try:
                if (
                    self.media_source is None
                    or self.media_source.path != resolved
                ):
                    self.load_media_preview(resolved, notify=False)
                if self.media_source is not None:
                    background_frame = self.media_source.next_frame(
                        self.preview_timer.interval() / 1000.0
                    )
            except Exception as error:
                self.failed_media_paths.add(resolved)
                self.last_media_warning = str(error)
                if self.media_source is not None:
                    self.media_source.close()
                    self.media_source = None
                self.statusBar().showMessage(
                    f"Media preview stopped: {error} — using fallback",
                    10000,
                )
        elif self.media_source is not None:
            self.media_source.close()
            self.media_source = None

        image = render_layout(
            self.layout_model,
            collect_stats(),
            background_frame=background_frame,
        )
        image.save(self.preview_path)
        self.preview_label.setPixmap(
            QPixmap.fromImage(ImageQt(image))
        )
        return image

    def send_preview(self):
        self.update_preview()
        completed = subprocess.run(
            ["pccooler-lcd", "send-image", str(self.preview_path)],
            capture_output=True,
            text=True,
        )
        if completed.returncode:
            QMessageBox.critical(self, "Send failed", completed.stderr or completed.stdout)
        else:
            self.statusBar().showMessage("Preview sent to LCD", 3000)

    def start_dashboard(self):
        self.stop_dashboard()
        temp_layout = Path(tempfile.gettempdir()) / "pccooler-qt-layout.json"
        self.sync_theme()
        save_layout(self.layout_model, temp_layout)
        command = [
            "pccooler-lcd",
            "layout-dashboard",
            str(temp_layout),
            "--quiet",
        ]
        if self.layout_model.background_type in {"gif", "video"}:
            command = [
                "pccooler-lcd", "media-layout-dashboard", str(temp_layout),
                "--media-fps", str(self.settings.video_fps),
                "--png-compression", "1",
            ]
        else:
            command += ["--interval", str(self.settings.refresh_interval)]

        self.dashboard_process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.statusBar().showMessage("Layout dashboard started")

    def stop_dashboard(self):
        if self.dashboard_process and self.dashboard_process.poll() is None:
            self.dashboard_process.terminate()
        self.dashboard_process = None
        self.statusBar().showMessage("Dashboard stopped")

    def new_layout(self):
        self.layout_model = default_layout()
        self.layout_path = None
        self.background_entry.clear()
        self.populate_scene()

    def open_layout(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Layout", str(Path.home()), "Layout (*.json)")
        if not path:
            return
        self.layout_model = load_layout(path)
        self.layout_path = Path(path)
        self.background_entry.setText(self.layout_model.background)
        self.background_type.setCurrentIndex({"auto": 0, "static": 1, "gif": 2, "video": 3}.get(self.layout_model.background_type, 0))
        self.background_fit.setCurrentIndex(1 if self.layout_model.background_fit == "contain" else 0)
        self.overlay_spin.setValue(self.layout_model.overlay_alpha)
        self.load_media_preview(
            self.layout_model.background,
            notify=True,
        )
        self.populate_scene()

    def save_layout_as(self):
        self.sync_theme()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Layout As",
            str(
                self.layout_library_dir
                / f"{self.safe_layout_filename(self.layout_model.name)}.json"
            ),
            "Layout (*.json)",
        )
        if not path:
            return
        self.layout_path = Path(path)
        save_layout(self.layout_model, self.layout_path)
        self.refresh_layout_library()
        self.statusBar().showMessage(
            f"Saved {self.layout_path}",
            3000,
        )

    def save_layout(self):
        self.sync_theme()
        if not self.layout_path:
            self.layout_path = self.unique_library_path(
                self.layout_model.name or "layout"
            )
        save_layout(self.layout_model, self.layout_path)
        self.refresh_layout_library()
        self.statusBar().showMessage(
            f"Saved {self.layout_path}",
            3000,
        )

    def closeEvent(self, event):
        self.stop_dashboard()
        if self.media_source is not None:
            self.media_source.close()
        super().closeEvent(event)
