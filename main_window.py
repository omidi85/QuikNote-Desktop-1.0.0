from PyQt5.QtWidgets import QMainWindow, QTabWidget
from .tabs.megapost_tab import MegapostTab
from .tabs.product_tab import ProductTab
from .tabs.regular_article_tab import RegularArticleTab

class MainWindow(QMainWindow):
    def __init__(self, state: dict):
        super().__init__()
        self.state = state
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        self._build_tabs()

    def _build_tabs(self):
        self.regular_article_tab = RegularArticleTab(self.state)
        self.tab_widget.addTab(self.regular_article_tab, "مقاله معمولی")

        self.megapost_tab = MegapostTab(self.state)
        self.tab_widget.addTab(self.megapost_tab, "مگاپست")

        self.product_tab = ProductTab(self.state)
        self.tab_widget.addTab(self.product_tab, "محتوای محصول")