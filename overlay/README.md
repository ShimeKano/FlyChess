# FlyChess Windows overlay — realtime capture prototype

This integration keeps the existing DROSO-1 browser model. A Windows helper can select a screen rectangle, capture that rectangle locally, compare the 8×8 board against the 12 Chess.com Neo PNG templates from `ShimeKano/covua/assneo`, send a FEN placement over localhost, and draw a transparent click-through arrow.

## Run (Windows)

1. Install Node.js 22.20+ or 24.12+, pnpm 10.14+, and Python 3.11+.
2. In the repository root, run `pnpm install --frozen-lockfile` and then `pnpm dev`. Keep the Vite server running.
3. In a second terminal, run `pip install -r overlay/requirements.txt`.
4. Run `overlay\\run.bat`.
5. In the Windows panel, click **Khoanh vùng bàn cờ**, then drag a rectangle around the 8×8 board grid only (exclude the coordinates and outer border).
6. Choose the side at the bottom and the side to move, then click **Bắt đầu realtime**.

The helper samples the selected region about every 350 ms. It only sends a new position when the detected placement changes. Image capture and template matching happen locally; no screenshots are uploaded. The existing browser DROSO-1 engine receives the position through a local WebSocket bridge at `127.0.0.1:8765`. The overlay does not inject clicks or keyboard input.

## Important prototype limitations

- **Not yet verified end-to-end.** This branch has not been built or tested on a Windows desktop.
- Template matching is a first-pass heuristic. Lighting, board themes, scaling, animation, occlusion, and the arrow itself can cause misclassification. Low-confidence positions need a review UI before relying on them.
- The recognized piece placement does not contain full chess state. The current prototype uses a manually selected side-to-move and no castling/en-passant rights; it does not track the full move history. Consequently, DROSO-1 may receive an inaccurate FEN and its move may be wrong or rejected.
- Windows display scaling and multi-monitor coordinates may need calibration.
- The current page validates UCI legality against the supplied FEN, but that does not prove the supplied FEN matches Roblox.
- The standard FlyChess page remains the default route; the bridge page is `/external-overlay`.

Treat this as an engineering prototype, not a reliable autonomous board reader. Before using live, add confidence thresholds/manual correction and maintain game state from observed moves.
