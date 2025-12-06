
import logging
from logging.handlers import RotatingFileHandler
from .paths import data_dir

def setup_logging(level=logging.INFO):
    log = logging.getLogger()
    if log.handlers: return
    log.setLevel(level)
    fh = RotatingFileHandler(data_dir() / "app.log", maxBytes=512*1024, backupCount=2, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(sh)
