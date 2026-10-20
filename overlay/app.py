"""Realtime Windows chessboard capture + transparent move-arrow overlay.
Captures only the user-selected screen region locally; no screenshots are uploaded.
"""
import asyncio, json, sys, threading, math, time
from pathlib import Path

import cv2
import mss
import numpy as np
from PySide6.QtCore import Qt, QPoint, QRect, QTimer, Signal, QObject
from PySide6.QtGui import QColor, QPainter, QPen, QPolygon
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QSpinBox,
    QComboBox, QHBoxLayout, QVBoxLayout, QFormLayout, QRubberBand
)
from websockets.asyncio.client import connect
from recognize import load_templates, recognize_board

BRIDGE_URL = "ws://127.0.0.1:8765/overlay"

class BridgeWorker(QObject):
    message = Signal(dict)
    status = Signal(str)
    def __init__(self):
        super().__init__(); self.loop=None; self.queue=None
        threading.Thread(target=lambda: asyncio.run(self.client()), daemon=True).start()
    async def client(self):
        self.loop=asyncio.get_running_loop(); self.queue=asyncio.Queue()
        while True:
            try:
                async with connect(BRIDGE_URL) as ws:
                    self.status.emit("Bridge localhost đã kết nối.")
                    async def sender():
                        while True: await ws.send(json.dumps(await self.queue.get()))
                    task=asyncio.create_task(sender())
                    try:
                        async for raw in ws:
                            try: self.message.emit(json.loads(raw))
                            except Exception: pass
                    finally:
                        task.cancel()
            except Exception as exc:
                self.status.emit("Đang chờ bridge: "+str(exc)); await asyncio.sleep(1.5)
    def send(self, payload):
        if self.loop and self.queue: asyncio.run_coroutine_threadsafe(self.queue.put(payload), self.loop)

class RegionSelector(QWidget):
    selected = Signal(int, int, int, int)
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.origin = QPoint(); self.rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.setStyleSheet("background: rgba(20,25,30,75);")
        self.show()
    def mousePressEvent(self, event):
        self.origin = event.position().toPoint()
        self.rubber.setGeometry(QRect(self.origin, self.origin)); self.rubber.show()
    def mouseMoveEvent(self, event):
        self.rubber.setGeometry(QRect(self.origin, event.position().toPoint()).normalized())
    def mouseReleaseEvent(self, event):
        rect = self.rubber.geometry().normalized()
        if rect.width() >= 160 and rect.height() >= 160:
            geo = self.geometry()
            self.selected.emit(geo.x()+rect.x(), geo.y()+rect.y(), rect.width(), rect.height())
        self.close()

class ArrowOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.screen_geo=QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(self.screen_geo)
        self.a=self.b=None; self.board=(100,100,600,600); self.flipped=False; self.show()
    def set_move(self, uci, board, flipped):
        if len(uci)<4: return
        self.a,self.b=uci[:2],uci[2:4]; self.board=board; self.flipped=flipped; self.update()
    def clear(self): self.a=self.b=None; self.update()
    def center(self, square):
        x,y,w,h=self.board; f=ord(square[0])-97; r=int(square[1])-1
        if self.flipped: f,r=7-f,7-r
        return QPoint(round(x-self.screen_geo.x()+(f+.5)*w/8),round(y-self.screen_geo.y()+(7-r+.5)*h/8))
    def paintEvent(self, event):
        if not self.a or not self.b: return
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        a,b=self.center(self.a),self.center(self.b)
        p.setPen(QPen(QColor(140,235,90,225),max(5,self.board[2]//90),Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap)); p.drawLine(a,b)
        angle=math.atan2(b.y()-a.y(),b.x()-a.x()); length=max(18,self.board[2]//14)
        left=QPoint(int(b.x()-length*math.cos(angle-.55)),int(b.y()-length*math.sin(angle-.55)))
        right=QPoint(int(b.x()-length*math.cos(angle+.55)),int(b.y()-length*math.sin(angle+.55)))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(140,235,90,230)); p.drawPolygon(QPolygon([b,left,right]))

class ControlPanel(QWidget):
    def __init__(self):
        super().__init__(); self.setWindowTitle("FlyChess DROSO-1 · Realtime Windows Overlay"); self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint); self.resize(460,520)
        self.bridge=BridgeWorker(); self.arrow=ArrowOverlay()
        self.region=None; self.templates=None; self.scan_enabled=False; self.last_signature=None
        self.turn="w"; self.flipped=False; self.board=(100,100,600,600); self.last_scan=0.0
        root=QVBoxLayout(self)
        root.addWidget(QLabel("Realtime overlay · xử lý ảnh cục bộ · không tự click"))
        self.status=QLabel("Đang khởi động bridge…"); self.status.setWordWrap(True); root.addWidget(self.status)
        form=QFormLayout(); self.x=self.spin(100); self.y=self.spin(100); self.w=self.spin(600); self.h=self.spin(600)
        form.addRow("X vùng bàn cờ",self.x); form.addRow("Y vùng bàn cờ",self.y); form.addRow("Chiều rộng",self.w); form.addRow("Chiều cao",self.h)
        self.side=QComboBox(); self.side.addItems(["Trắng ở dưới","Đen ở dưới"]); form.addRow("Hướng bàn cờ",self.side); root.addLayout(form)
        self.turn_box=QComboBox(); self.turn_box.addItems(["Lượt Trắng","Lượt Đen"]); root.addWidget(self.turn_box)
        row=QHBoxLayout()
        select=QPushButton("Khoanh vùng bàn cờ"); select.clicked.connect(self.select_region); row.addWidget(select)
        self.start_button=QPushButton("Bắt đầu realtime"); self.start_button.clicked.connect(self.toggle_scan); row.addWidget(self.start_button)
        root.addLayout(row)
        clear=QPushButton("Xóa mũi tên"); clear.clicked.connect(self.arrow.clear); root.addWidget(clear)
        root.addWidget(QLabel("Cách dùng: khoanh đúng 8×8 ô bàn cờ (không gồm viền/tọa độ), rồi bật realtime."))
        root.addWidget(QLabel("Nhận diện ảnh là heuristic; kiểm tra FEN/nước đi trước khi tin mũi tên."))
        self.bridge.status.connect(self.status.setText); self.bridge.message.connect(self.on_message)
        self.timer=QTimer(self); self.timer.setInterval(350); self.timer.timeout.connect(self.scan_tick)
    def spin(self, value):
        s=QSpinBox(); s.setRange(-10000,20000); s.setValue(value); return s
    def select_region(self):
        self.region=RegionSelector(); self.region.selected.connect(self.region_selected)
    def region_selected(self,x,y,w,h):
        self.board=(x,y,w,h); self.x.setValue(x); self.y.setValue(y); self.w.setValue(w); self.h.setValue(h)
        self.status.setText(f"Đã khoanh vùng: {w}×{h} px. Bật realtime để bắt đầu.")
    def toggle_scan(self):
        if self.scan_enabled:
            self.scan_enabled=False; self.timer.stop(); self.start_button.setText("Bắt đầu realtime")
            self.status.setText("Đã tạm dừng nhận diện."); return
        self.board=(self.x.value(),self.y.value(),self.w.value(),self.h.value())
        if self.board[2] < 160 or self.board[3] < 160:
            self.status.setText("Vùng quá nhỏ. Hãy khoanh lại bàn cờ trước."); return
        self.scan_enabled=True; self.last_signature=None; self.turn="w" if self.turn_box.currentIndex()==0 else "b"
        self.flipped=self.side.currentIndex()==1; self.start_button.setText("Dừng realtime")
        self.status.setText("Đang tải 12 mẫu assneo…")
        threading.Thread(target=self.load_templates_async,daemon=True).start()
    def load_templates_async(self):
        try:
            loaded=load_templates()
            self.templates=loaded
            QTimer.singleShot(0, lambda: self.status.setText("Đã tải mẫu assneo. Đang nhận diện bàn cờ…"))
            QTimer.singleShot(0, self.start_timer_if_ready)
        except Exception as exc:
            QTimer.singleShot(0, lambda: self.status.setText("Lỗi tải mẫu assneo: "+str(exc)))
    def start_timer_if_ready(self):
        if self.scan_enabled and self.templates: self.timer.start()
    def scan_tick(self):
        if not self.scan_enabled or not self.templates: return
        x,y,w,h=self.board
        try:
            with mss.mss() as sct:
                shot=np.array(sct.grab({"left":x,"top":y,"width":w,"height":h}))
            frame=cv2.cvtColor(shot,cv2.COLOR_BGRA2BGR)
            placement, confidence, debug=recognize_board(frame,self.templates,flipped=self.flipped)
            signature=placement
            # Require the same recognized placement twice before sending it to the model.
            if signature == self.last_signature:
                return
            self.last_signature=signature
            # A fresh screen gives piece placement, but cannot reveal castling/en-passant rights.
            fen=f"{placement} {self.turn} - - 0 1"
            self.bridge.send({"type":"position","fen":fen,"requestId":"realtime-overlay",
                "board":{"x":x,"y":y,"w":w,"h":h},"flipped":self.flipped,"source":"local-realtime"})
            self.status.setText(f"Đã nhận diện vị trí mới ({sum(1 for r in placement.split('/') for c in r if c.isalpha())} quân). Đang chờ DROSO-1…")
        except Exception as exc:
            self.status.setText("Lỗi nhận diện: "+str(exc))
    def on_message(self, data):
        if data.get("type")=="move":
            b=data.get("board") or {"x":self.board[0],"y":self.board[1],"w":self.board[2],"h":self.board[3]}
            self.arrow.set_move(data.get("uci",""),(b["x"],b["y"],b["w"],b["h"]),bool(data.get("flipped",self.flipped)))
            self.status.setText("DROSO-1 đề xuất: "+data.get("uci","")+" · kiểm tra trạng thái bàn cờ")
        elif data.get("type")=="status" and data.get("status")=="error":
            self.status.setText("Lỗi: "+str(data.get("message","không rõ")))
    def closeEvent(self,event):
        self.timer.stop(); self.arrow.close(); event.accept()

if __name__=="__main__":
    app=QApplication(sys.argv); panel=ControlPanel(); panel.show(); sys.exit(app.exec())
