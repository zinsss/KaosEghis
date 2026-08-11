from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer


def has_local_file_urls(mime_data) -> bool:
    if mime_data is None or not mime_data.hasUrls():
        return False
    urls = mime_data.urls()
    return bool(urls) and all(url.isLocalFile() for url in urls)


class DragHoverSwitchController(QObject):
    def __init__(self, switch_callback, *, hover_ms: int = 350) -> None:
        super().__init__()
        self._switch_callback = switch_callback
        self._pending_index: int | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(max(50, int(hover_ms)))
        self._timer.timeout.connect(self._apply_switch)

    def schedule(self, index: int) -> None:
        if self._pending_index == index and self._timer.isActive():
            return
        self._pending_index = index
        self._timer.start()

    def clear(self) -> None:
        self._pending_index = None
        self._timer.stop()

    def _apply_switch(self) -> None:
        if self._pending_index is None:
            return
        self._switch_callback(self._pending_index)


class TabBarFileHoverFilter(QObject):
    def __init__(self, switch_callback, *, hover_ms: int = 350) -> None:
        super().__init__()
        self._controller = DragHoverSwitchController(
            switch_callback,
            hover_ms=hover_ms,
        )

    def eventFilter(self, watched, event) -> bool:
        event_type = event.type()
        if event_type in (QEvent.Type.DragLeave, QEvent.Type.Drop):
            self._controller.clear()
            return False
        if event_type not in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            return False
        if not has_local_file_urls(event.mimeData()):
            self._controller.clear()
            return False
        index = watched.tabAt(event.position().toPoint())
        if index >= 0:
            self._controller.schedule(index)
        else:
            self._controller.clear()
        return False


class ButtonFileHoverFilter(QObject):
    def __init__(self, switch_callback, page_index: int, *, hover_ms: int = 350) -> None:
        super().__init__()
        self._page_index = page_index
        self._controller = DragHoverSwitchController(
            switch_callback,
            hover_ms=hover_ms,
        )

    def eventFilter(self, watched, event) -> bool:
        event_type = event.type()
        if event_type in (QEvent.Type.DragLeave, QEvent.Type.Drop):
            self._controller.clear()
            return False
        if event_type not in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            return False
        if not has_local_file_urls(event.mimeData()):
            self._controller.clear()
            return False
        self._controller.schedule(self._page_index)
        return False
