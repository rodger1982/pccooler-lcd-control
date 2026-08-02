from __future__ import annotations

from dataclasses import asdict
from typing import Callable

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from ..layout import Widget


class WidgetGraphicsItem(QGraphicsRectItem):
    changed = Signal()

    def __init__(self, widget: Widget):
        super().__init__(0, 0, widget.width, widget.height)
        self.widget = widget
        self.setPos(widget.x, widget.y)
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.label = QGraphicsSimpleTextItem(widget.label or widget.kind.upper(), self)
        self.label.setPos(6, 4)
        self.refresh_style()

    def refresh_style(self):
        self.setRect(0, 0, max(8, self.widget.width), max(8, self.widget.height))
        self.setBrush(QBrush(QColor(self.widget.background)))
        pen = QPen(QColor(self.widget.accent))
        pen.setWidth(1 if self.widget.show_border else 0)
        self.setPen(pen)
        self.label.setText(self.widget.label or self.widget.kind.upper())
        self.label.setBrush(QBrush(QColor(self.widget.foreground)))

    def itemChange(self, change, value):
        result = super().itemChange(change, value)
        if change == QGraphicsItem.ItemPositionHasChanged:
            pos = self.pos()
            self.widget.x = max(0, min(320 - self.widget.width, int(pos.x())))
            self.widget.y = max(0, min(240 - self.widget.height, int(pos.y())))
        return result


class DesignScene(QGraphicsScene):
    selection_changed = Signal(object)

    def __init__(self):
        super().__init__(0, 0, 320, 240)
        self.setBackgroundBrush(QBrush(QColor("#07101A")))
        self.selectionChanged.connect(self._emit_selection)

    def _emit_selection(self):
        selected = self.selectedItems()
        self.selection_changed.emit(selected[0] if selected else None)


class DesignView(QGraphicsView):
    def __init__(self, scene: DesignScene):
        super().__init__(scene)
        self.setRenderHints(self.renderHints())
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.scale(2.0, 2.0)
        self.setMinimumSize(660, 500)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
            event.accept()
            return
        super().wheelEvent(event)
