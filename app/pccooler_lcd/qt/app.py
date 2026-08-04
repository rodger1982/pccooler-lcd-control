from __future__ import annotations

import sys

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from .main_window import MainWindow, branding_path


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PCCOOLER-LCD Control")
    app.setOrganizationName("PCCOOLER-LCD Control")
    logo_path = branding_path("logo.png")
    if logo_path.is_file():
        app.setWindowIcon(QIcon(str(logo_path)))
    splash = None
    splash_path = branding_path("splash.png")
    if splash_path.is_file():
        splash = QSplashScreen(QPixmap(str(splash_path)))
        splash.show()
        app.processEvents()
    window = MainWindow()
    window.show()
    if splash is not None:
        splash.finish(window)
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
