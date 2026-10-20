"""Local-only WebSocket relay for FlyChess external overlay. No cloud server."""
import asyncio
import json
import logging
from websockets.asyncio.server import serve

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
clients = {"browser": set(), "overlay": set()}

async def handler(websocket):
    path = websocket.request.path.rstrip("/")
    role = path.rsplit("/", 1)[-1]
    origin = websocket.request.headers.get("Origin")
    if origin and origin not in {"http://localhost:5180", "http://127.0.0.1:5180"}:
        await websocket.close(code=1008, reason="origin not allowed")
        return
    if role not in clients:
        await websocket.close(code=1008, reason="unknown role")
        return
    # Bind only to loopback in main(), and permit only the two known endpoints.
    clients[role].add(websocket)
    logging.info("%s connected", role)
    try:
        async for raw in websocket:
            if len(raw) > 128_000:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict) or data.get("type") not in {"position", "move", "status"}:
                continue
            target = "browser" if role == "overlay" else "overlay"
            message = json.dumps(data, separators=(",", ":"))
            for peer in tuple(clients[target]):
                try:
                    await peer.send(message)
                except Exception:
                    clients[target].discard(peer)
    finally:
        clients[role].discard(websocket)
        logging.info("%s disconnected", role)

async def main():
    async with serve(handler, "127.0.0.1", 8765, max_size=128_000, origins=None):
        logging.info("Bridge listening only on 127.0.0.1:8765")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
