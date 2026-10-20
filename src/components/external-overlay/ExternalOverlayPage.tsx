import { useEffect, useRef, useState } from "react";
import { Chess } from "chess.js";
import { getFlyEngine } from "@/ai/fly/engine";
import { FLY_LEVELS } from "@/ai/bots/levels";
import "@/components/external-overlay/external-overlay.css";

type Incoming = { type: "position"; fen: string; history?: string[]; halfMoves?: number; remainingMs?: number | null; seen?: Record<string, number>; requestId?: string };
type Outgoing = { type: "move"; fen: string; uci: string; requestId?: string } | { type: "status"; status: string; message?: string };

export function ExternalOverlayPage() {
  const [status, setStatus] = useState("Đang kết nối bridge cục bộ…");
  const [fen, setFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [uci, setUci] = useState("");
  const [level, setLevel] = useState("thinker");
  const [connected, setConnected] = useState(false);
  const socket = useRef<WebSocket | null>(null);
  const busy = useRef(false);

  useEffect(() => {
    let stopped = false;
    let retry: number | undefined;
    const connect = () => {
      if (stopped) return;
      const ws = new WebSocket("ws://127.0.0.1:8765/browser");
      socket.current = ws;
      ws.onopen = () => { setConnected(true); setStatus("Đã kết nối. Đang khởi tạo DROSO-1…"); ws.send(JSON.stringify({type:"status",status:"browser-ready"})); };
      ws.onclose = () => { setConnected(false); setStatus("Mất kết nối bridge; đang thử kết nối lại…"); if (!stopped) retry = window.setTimeout(connect, 1500); };
      ws.onerror = () => setStatus("Không kết nối được bridge. Hãy chạy overlay/run.bat.");
      ws.onmessage = async (event) => {
        let message: Incoming;
        try { message = JSON.parse(String(event.data)); } catch { return; }
        if (message.type !== "position" || busy.current) return;
        busy.current = true;
        setFen(message.fen);
        setUci("");
        try {
          const chess = new Chess(message.fen);
          if (chess.isGameOver()) throw new Error("Vị trí đã kết thúc ván.");
          const selected = FLY_LEVELS.find(x => x.id === level) ?? FLY_LEVELS[2];
          await getFlyEngine().init();
          const result = await getFlyEngine().think(message.fen, { ...selected.plan, temperature: 0, seen: message.seen }, false, true);
          const move = result.decision.move;
          if (!/^[a-h][1-8][a-h][1-8][qrbn]?$/.test(move)) throw new Error("DROSO-1 trả về nước đi không hợp lệ.");
          // Validate the chosen UCI against chess.js before sending it to the overlay.
          const played = chess.move({from:move.slice(0,2),to:move.slice(2,4),promotion:move[4]});
          if (!played) throw new Error("Nước đi không hợp lệ với FEN đã nhận.");
          setUci(move);
          const reply: Outgoing = {type:"move",fen:message.fen,uci:move,requestId:message.requestId};
          ws.send(JSON.stringify(reply));
          setStatus("Đã tính nước đi bằng DROSO-1.");
        } catch (error) {
          const messageText = error instanceof Error ? error.message : String(error);
          setStatus("Lỗi: " + messageText);
          ws.send(JSON.stringify({type:"status",status:"error",message:messageText,requestId:message.requestId}));
        } finally { busy.current = false; }
      };
    };
    connect();
    return () => { stopped = true; if (retry) window.clearTimeout(retry); socket.current?.close(); };
  }, [level]);

  const sendTest = () => {
    try {
      const chess = new Chess(fen);
      if (chess.isGameOver()) { setStatus("Vị trí đã kết thúc ván."); return; }
      socket.current?.send(JSON.stringify({type:"position",fen,halfMoves:0,requestId:"manual-"+Date.now()}));
      setStatus("Đã gửi FEN cho DROSO-1…");
    } catch { setStatus("FEN không hợp lệ."); }
  };

  return <main className="external-overlay">
    <header><div><h1>FlyChess · External Overlay</h1><p>DROSO-1 nguyên bản · Chỉ hướng dẫn, không tự click</p></div><span className={connected ? "pill online" : "pill"}>{connected ? "BRIDGE ONLINE" : "OFFLINE"}</span></header>
    <section className="panel">
      <label htmlFor="fly-level">Mức tìm kiếm</label>
      <select id="fly-level" value={level} onChange={e=>setLevel(e.target.value)}><option value="scout">Scout · 64 simulations</option><option value="tactician">Tactician · 128 simulations</option><option value="thinker">Thinker · 256 simulations</option></select>
      <label htmlFor="fen">FEN vị trí bàn cờ (dùng để kiểm tra kết nối)</label>
      <textarea id="fen" value={fen} onChange={e=>setFen(e.target.value)} spellCheck={false}/>
      <button onClick={sendTest}>Tính nước đi thử</button>
      <div className="status">{status}</div>
      {uci && <div className="move"><small>NƯỚC ĐI UCI</small><strong>{uci.slice(0,2)} → {uci.slice(2,4)}{uci[4] ? " = "+uci[4].toUpperCase() : ""}</strong><span>Đã kiểm tra tính hợp lệ trước khi gửi.</span></div>}
    </section>
    <p className="note">Đây là trang cầu nối thử nghiệm. Việc tự đọc quân từ ảnh Roblox chưa được bật; hiện tại chỉ xử lý FEN được gửi vào bridge. Không dùng kết quả khi FEN chưa khớp hoàn toàn với bàn cờ.</p>
  </main>;
}
