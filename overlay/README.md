# FlyChess Windows overlay — first scaffold

This integration preserves the existing DROSO-1 brain and uses the existing browser model. It adds a local-only relay and a transparent, click-through Windows arrow layer.

## Run

1. Install Node.js 22.20+ or 24.12+, and pnpm 10.14+.
2. In the repository root, run `pnpm install --frozen-lockfile` then `pnpm dev` and keep it running.
3. Run `overlay\\run.bat`.
4. In the Windows control panel, enter the exact FEN and configure board X/Y/width/height to match the Roblox board on screen.
5. Press **Gửi vị trí → DROSO-1**. The existing browser-loaded DROSO-1 returns a UCI move and the Windows layer draws the arrow.

The bridge listens only on `127.0.0.1:8765`. It does not expose a cloud service. The overlay does not inject clicks or keyboard input.

## Current limitations

- Board/piece recognition from Roblox screenshots is not implemented yet. The current MVP requires a valid FEN entered by the user.
- You must manually set the board's screen rectangle and orientation.
- FEN alone does not encode full move history/repetition state. Special moves and repetition-aware search may differ without history.
- The local browser route is `/external-overlay`. The standard FlyChess page remains the default route.
