# FlyChess Windows overlay (initial integration)

This adds an isolated external-position page and a loopback WebSocket relay. It does not modify DROSO-1 weights or replace its inference.

## Current milestone

- `/external-overlay` loads the existing DROSO-1 brain and accepts FEN positions.
- The local relay listens only on `127.0.0.1:8765`.
- A valid UCI move is checked against `chess.js` and sent back to the overlay client.
- No game moves are clicked or submitted automatically.

## Run

1. Install Node.js 22.20+ or 24.12+, and pnpm 10.14+.
2. In the repository root: `pnpm install --frozen-lockfile` then `pnpm dev`.
3. In another terminal: `cd overlay` then `py -3 -m pip install -r requirements.txt` and `py -3 bridge.py`.
4. Open `http://localhost:5180/external-overlay`.
5. Send a `{"type":"position","fen":"...","requestId":"..."}` message from a WebSocket client connected to `ws://127.0.0.1:8765/overlay`.

## Not yet implemented

Automatic chessboard and piece recognition from Roblox screenshots, screen-coordinate arrow drawing, board orientation calibration, and full move-history reconstruction. Until those are implemented and validated, the FEN must be supplied from a trusted source and the displayed move is not an end-to-end Roblox overlay yet.
