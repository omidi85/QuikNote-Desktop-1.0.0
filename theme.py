from PySide6.QtGui import QPalette, QColor


def apply_theme(app, mode: str = "dark"):
    if app is None:
        return
    mode = (mode or "dark").lower()
    if mode == "light":
        bg = QColor("#f0f4f8")
        text = QColor("#333333")
        panel = QColor("#ffffff")
        accent = QColor("#007bff")
        success = QColor("#28a745")
        p = QPalette()
        p.setColor(QPalette.Window, bg)
        p.setColor(QPalette.WindowText, text)
        p.setColor(QPalette.Base, panel)
        p.setColor(QPalette.Text, text)
        p.setColor(QPalette.Button, panel)
        p.setColor(QPalette.ButtonText, text)
        p.setColor(QPalette.Highlight, accent)
        p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        app.setPalette(p)
        app.setStyleSheet("""
            QWidget { background-color: #f0f4f8; color: #333333; font-family: 'Segoe UI', sans-serif; }
            QLabel { color: #333333; }
            QLineEdit, QTextEdit { background-color: #ffffff; border: 1px solid #ced4da; border-radius: 4px; padding: 8px; min-height: 30px; }
            QPushButton { background-color: #007bff; color: white; border: none; border-radius: 4px; padding: 8px 16px; }
            QPushButton:hover { background-color: #0069d9; }
            QPushButton:pressed { background-color: #005cbf; }
            QProgressBar { background-color: #e9ecef; border: 1px solid #ced4da; border-radius: 4px; text-align: center; }
            QProgressBar::chunk { background-color: #007bff; }
            QComboBox { background-color: #ffffff; border: 1px solid #ced4da; border-radius: 4px; padding: 8px; min-height: 30px; }
            QComboBox::drop-down { subcontrol-position: right; width: 20px; border-left: 1px solid #ced4da; }
            QToolButton { background: transparent; border: none; color: #333333; }
            QToolButton:checked { background: #e2e6ea; border-radius: 4px; }
            QToolButton:hover { background: #dee2e6; border-radius: 4px; }
            .credit-label { background-color: #28a745; color: white; border-radius: 20px; padding: 5px 10px; font-weight: bold; }
            QGroupBox { border: 1px solid #ced4da; border-radius: 4px; padding: 10px; background-color: #ffffff; }
            .support-ticket { border: 1px solid #ced4da; border-radius: 4px; padding: 10px; margin-bottom: 10px; }
            .support-ticket-admin { background-color: #e6f4ea; }
        """)
    else:
        bg = QColor("#1a1d21")
        text = QColor("#d1d5da")
        panel = QColor("#212529")
        accent = QColor("#0366d6")
        success = QColor("#28a745")
        p = QPalette()
        p.setColor(QPalette.Window, bg)
        p.setColor(QPalette.WindowText, text)
        p.setColor(QPalette.Base, panel)
        p.setColor(QPalette.Text, text)
        p.setColor(QPalette.Button, panel)
        p.setColor(QPalette.ButtonText, text)
        p.setColor(QPalette.Highlight, accent)
        p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        app.setPalette(p)
        app.setStyleSheet("""
            QWidget { color: #d1d5da; font-family: 'Segoe UI', sans-serif; }
            QLabel { color: #d1d5da; }
            QLineEdit, QTextEdit { background-color: #212529; border: 1px solid #343a40; border-radius: 4px; padding: 8px; min-height: 30px; color: #d1d5da; }
            QPushButton { background-color: #0366d6; color: white; border: none; border-radius: 4px; padding: 8px 16px; }
            QPushButton:hover { background-color: #0353b3; }
            QPushButton:pressed { background-color: #03408f; }
            QProgressBar { background-color: #343a40; border: 1px solid #495057; border-radius: 4px; text-align: center; color: #d1d5da; }
            QProgressBar::chunk { background-color: #0366d6; }
            QComboBox { background-color: #212529; border: 1px solid #343a40; border-radius: 4px; padding: 8px; min-height: 30px; color: #d1d5da; }
            QComboBox::drop-down { subcontrol-position: right; width: 20px; border-left: 1px solid #343a40; }
            QToolButton { background: transparent; border: none; color: #d1d5da; }
            QToolButton:checked { background: #2c313a; border-radius: 4px; }
            QToolButton:hover { background: #343a40; border-radius: 4px; }
            .credit-label { background-color: #28a745; color: white; border-radius: 20px; padding: 5px 10px; font-weight: bold; }
            QGroupBox { border: 1px solid #495057; border-radius: 4px; padding: 10px; background-color: #212529; }
            .support-ticket { border: 1px solid #495057; border-radius: 4px; padding: 10px; margin-bottom: 10px; }
            .support-ticket-admin { background-color: #2d4739; }
        """)