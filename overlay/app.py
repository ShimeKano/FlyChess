"""Windows helper UI and transparent arrow overlay. Does not send mouse/keyboard input."""
import asyncio, json, sys, threading, math
from PySide6.QtCore import Qt, QPoint, Signal, QObject
from PySide6.QtGui import QColor, QPainter, QPen, QPolygon
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QPushButton, QSpinBox, QComboBox, QHBoxLayout, QVBoxLayout, QFormLayout
from websockets.asyncio.client import connect

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
                async with connect("ws://127.0.0.1:8765/overlay") as ws:
                    self.status.emit("Bridge đã kết nối.")
                    async def sender():
                        while True: await ws.send(json.dumps(await self.queue.get()))
                    task=asyncio.create_task(sender())
                    try:
                        async for raw in ws:
                            try: self.message.emit(json.loads(raw))
                            except Exception: pass
                    finally: task.cancel()
            except Exception as exc:
                self.status.emit("Đang chờ bridge: "+str(exc)); await asyncio.sleep(1.5)
    def send(self, payload):
        if self.loop and self.queue: asyncio.run_coroutine_threadsafe(self.queue.put(payload), self.loop)

class ArrowOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setGeometry(QApplication.primaryScreen().virtualGeometry())
        self.a=self.b=None; self.board=(100,100,600,600); self.flipped=False; self.show()
    def set_move(self, uci, board, flipped):
        if len(uci)<4: return
        self.a,self.b=uci[:2],uci[2:4]; self.board=board; self.flipped=flipped; self.update()
    def clear(self): self.a=self.b=None; self.update()
    def center(self, square):
        x,y,w,h=self.board; f=ord(square[0])-97; r=int(square[1])-1
        if self.flipped: f,r=7-f,7-r
        origin=QApplication.primaryScreen().virtualGeometry().topLeft()
        return QPoint(round(x-origin.x()+(f+.5)*w/8),round(y-origin.y()+(7-r+.5)*h/8))
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
        super().__init__(); self.setWindowTitle("FlyChess DROSO-1 · Windows Overlay"); self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint); self.resize(440,470)
        self.bridge=BridgeWorker(); self.arrow=ArrowOverlay(); root=QVBoxLayout(self)
        root.addWidget(QLabel("Overlay hướng dẫn nước đi · không tự click"))
        self.status=QLabel("Đang khởi động bridge…"); root.addWidget(self.status)
        form=QFormLayout(); self.x=self.spin(100); self.y=self.spin(100); self.w=self.spin(600); self.h=self.spin(600)
        form.addRow("Board X (màn hình)",self.x); form.addRow("Board Y (màn hình)",self.y); form.addRow("Chiều rộng",self.w); form.addRow("Chiều cao",self.h)
        self.side=QComboBox(); self.side.addItems(["Trắng ở dưới","Đen ở dưới"]); form.addRow("Hướng bàn cờ",self.side); root.addLayout(form)
        self.fen=QLineEdit("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        root.addWidget(QLabel("FEN chính xác (nhận diện ảnh chưa có)")); root.addWidget(self.fen)
        row=QHBoxLayout(); send=QPushButton("Gửi vị trí → DROSO-1"); send.clicked.connect(self.send_position); row.addWidget(send)
        clear=QPushButton("Xóa mũi tên"); clear.clicked.connect(self.arrow.clear); row.addWidget(clear); root.addLayout(row)
        self.bridge.status.connect(self.status.setText); self.bridge.message.connect(self.on_message)
        root.addWidget(QLabel("Căn X/Y theo góc trên-trái bàn cờ Roblox."))
        root.addWidget(QLabel("Bản đầu yêu cầu nhập FEN thủ công; chưa tự đọc quân."))
    def spin(self, value):
        s=QSpinBox(); s.setRange(-10000,20000); s.setValue(value); return s
    def send_position(self):
        self.bridge.send({"type":"position","fen":self.fen.text().strip(),"requestId":"windows-overlay",
            "board":{"x":self.x.value(),"y":self.y.value(),"w":self.w.value(),"h":self.h.value()},"flipped":self.side.currentIndex()==1})
        self.status.setText("Đã gửi vị trí; đang chờ DROSO-1…")
    def on_message(self, data):
        if data.get("type")=="move":
            b=data.get("board") or {"x":self.x.value(),"y":self.y.value(),"w":self.w.value(),"h":self.h.value()}
            self.arrow.set_move(data.get("uci",""),(b["x"],b["y"],b["w"],b["h"]),bool(data.get("flipped",self.side.currentIndex()==1)))
            self.status.setText("DROSO-1 đề xuất: "+data.get("uci",""))
        elif data.get("type")=="status" and data.get("status")=="error": self.status.setText("Lỗi: "+str(data.get("message","không rõ")))
    def closeEvent(self,event): self.arrow.close(); event.accept()

if __name__=="__main__":
    app=QApplication(sys.argv); panel=ControlPanel(); panel.show(); sys.exit(app.exec())
