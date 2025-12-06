# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Callable, Iterable, Mapping, Optional
from PySide6.QtCore import QObject, QThread, Signal

class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(Exception)
    finished = Signal()
    progress = Signal(object)

class Worker(QThread):
    """
    Worker ساده و ایمن: فقط QThread + Signals.
    استفاده:
        w = Worker(target=fn, args=(...), kwargs={...})
        w.signals.result.connect(...)
        w.signals.error.connect(...)
        w.signals.finished.connect(...)
        w.start()
    """
    def __init__(
        self,
        fn: Optional[Callable[..., Any]] = None,
        *args: Iterable[Any],
        **kwargs: Mapping[str, Any],
    ):
        super().__init__()
        target = kwargs.pop("target", None)
        args_tuple = kwargs.pop("args", None)
        kwargs_dict = kwargs.pop("kwargs", None)

        self._fn: Optional[Callable[..., Any]] = fn or target
        if self._fn is None:
            raise ValueError("Worker needs a function: pass fn or target")

        self._args = tuple(args_tuple) if args_tuple is not None else tuple(args)
        self._kwargs = dict(kwargs)
        if kwargs_dict is not None:
            self._kwargs.update(dict(kwargs_dict))

        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            out = self._fn(*self._args, **self._kwargs)
            self.signals.result.emit(out)
        except Exception as e:  # noqa: BLE001
            self.signals.error.emit(e)
        finally:
            self.signals.finished.emit()
