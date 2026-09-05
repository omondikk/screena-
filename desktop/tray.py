from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon
from PySide6.QtCore import QTimer

class SystemTray:
    def __init__(self):
        self.tray = None
        self.menu = None
        self.setup_tray()
    
    def setup_tray(self):
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self._create_icon())
        self.tray.setToolTip("CrossSync Clipboard")
        
        self.menu = QMenu()
        status_action = QMenu("Status: Connected", self.menu)
        status_action.setEnabled(False)
        self.menu.addAction(status_action)
        self.menu.addSeparator()
        
        sync_action = QMenu("Sync Now", self.menu)
        sync_action.triggered.connect(self.manual_sync)
        self.menu.addAction(sync_action)
        
        self.menu.addSeparator()
        quit_action = QMenu("Quit", self.menu)
        quit_action.triggered.connect(self.quit)
        self.menu.addAction(quit_action)
        
        self.tray.setContextMenu(self.menu)
    
    def _create_icon(self):
        return QIcon.fromTheme("clipboard")
    
    def show(self):
        self.tray.show()
    
    def show_notification(self, title: str, message: str):
        self.tray.showMessage(title, message, QSystemTrayIcon.Information, 3000)
    
    def manual_sync(self):
        self.show_notification("Sync", "Manual sync triggered")
    
    def quit(self):
        from PySide6.QtWidgets import QApplication
        QApplication.quit()