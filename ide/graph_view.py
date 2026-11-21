"""Zoomable Qt graph viewer shared by bytecode CFG and call graph."""
from math import ceil, sqrt
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont, QPen
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene

class GraphView(QGraphicsView):
    nodeActivated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = QGraphicsScene(self)
        self.setScene(self.canvas)
        self.setRenderHints(self.renderHints())
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setMinimumHeight(210)
        self.setToolTip('Drag to pan; mouse wheel to zoom; double-click a node to navigate')
        self._nodes = {}

    def set_graph(self, result):
        self.canvas.clear()
        self._nodes = {}
        nodes = result.get('nodes', [])
        edges = result.get('edges', [])
        if not nodes:
            self.canvas.addText('No graph available yet.')
            return
        columns = min(6,max(1,ceil(sqrt(len(nodes)))))
        cell_width, cell_height = 200, 94
        coords = {}
        for index,(key,text) in enumerate(nodes):
            x=(index%columns)*cell_width
            y=(index//columns)*cell_height
            coords[key]=(x,y)
        for source,target,kind in edges:
            if source not in coords or target not in coords:
                continue
            x1,y1=coords[source];x2,y2=coords[target]
            line=self.canvas.addLine(x1+80,y1+38,x2+80,y2,
                                      QPen(QColor('#61788C' if kind=='fallthrough'
                                                  else '#B3A080'),1.3))
            line.setZValue(-1)
        for key,title in nodes:
            x,y=coords[key]
            rect=self.canvas.addRect(x,y,160,38,QPen(QColor('#788696')),
                                     QBrush(QColor('#262D37')))
            rect.setData(0,key)
            label=self.canvas.addText(title[:30],QFont('Consolas',9))
            label.setDefaultTextColor(QColor('#DCE4ED'))
            label.setPos(x+7,y+7)
            label.setData(0,key)
            self._nodes[key]=rect
        self.canvas.setSceneRect(self.canvas.itemsBoundingRect().adjusted(-30,-30,30,30))
        self.resetTransform()
        self.fitInView(self.canvas.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        self.scale(1.15 if event.angleDelta().y()>0 else 1/1.15,
                   1.15 if event.angleDelta().y()>0 else 1/1.15)

    def mouseDoubleClickEvent(self, event):
        item=self.itemAt(event.pos())
        if item is not None and item.data(0) is not None:
            self.nodeActivated.emit(str(item.data(0)))
        else:
            super().mouseDoubleClickEvent(event)
