# -*- coding: utf-8 -*-

"""
این نسخه :
1 - به سایت وصل میشه و تعداد مقالات باقیمانده رو میخونه
2 - کد سخت افزاری !!
3- تولید عناوین درست شد
4 - تنظیمات بهم ریخته - تا حدودی درست شد
5- پشتیبانی اوکی
6 - ارسال مقاله با عکس همراه است و درست شد

"""


from quiknote.app import QuikNoteApp
from PySide6.QtWidgets import QApplication
import os, sys
os.environ.setdefault("QT_QUICK_BACKEND", "software")
def main():
    app = QApplication(sys.argv)
    w = QuikNoteApp()
    w.show()
  #  w.showMaximized()   # 👈 اینجا
    sys.exit(app.exec())
if __name__ == "__main__":
    main()
