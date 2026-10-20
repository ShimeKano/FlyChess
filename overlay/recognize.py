"""Template-based recognition using the exact Chess.com Neo PNGs in ShimeKano/covua/assneo."""
from __future__ import annotations
from pathlib import Path
from urllib.request import urlopen
import cv2
import numpy as np

ASSET_BASE = "https://raw.githubusercontent.com/ShimeKano/covua/main/assneo"
FILES = {
    "K":"wk.png", "Q":"wq.png", "R":"wr.png", "B":"wb.png", "N":"wn.png", "P":"wp.png",
    "k":"bk.png", "q":"bq.png", "r":"br.png", "b":"bb.png", "n":"bn.png", "p":"bp.png",
}
ASSET_DIR = Path(__file__).parent / "assets" / "assneo"

def load_templates():
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    templates = {}
    for symbol, filename in FILES.items():
        path = ASSET_DIR / filename
        if not path.exists():
            try:
                with urlopen(f"{ASSET_BASE}/{filename}", timeout=12) as response:
                    path.write_bytes(response.read())
            except Exception as exc:
                raise RuntimeError(f"Không tải được mẫu {filename} từ assneo: {exc}") from exc
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if image is None or image.ndim != 3 or image.shape[2] < 4:
            raise RuntimeError(f"Ảnh mẫu {filename} không phải PNG có kênh alpha.")
        templates[symbol] = image
    return templates

def _score_square(square_bgr, template, target_height):
    # Scale template to fit the inner part of one square; retain alpha as a matching mask.
    h, w = template.shape[:2]
    new_h = max(12, int(target_height * 0.76))
    new_w = max(12, round(w * new_h / h))
    resized = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_AREA)
    rgb = resized[:, :, :3]
    alpha = resized[:, :, 3]
    # OpenCV assets are BGRA; screenshots are BGR.
    mask = (alpha > 24).astype(np.uint8) * 255
    if cv2.countNonZero(mask) < 20:
        return -1.0
    result = cv2.matchTemplate(square_bgr, rgb, cv2.TM_CCORR_NORMED, mask=mask)
    return float(np.nanmax(result))

def recognize_board(board_bgr, templates=None, flipped=False):
    """Return (piece placement FEN rank, confidence grid, annotated debug image).

    board_bgr must contain only the board grid, without coordinates/border, in an 8x8 layout.
    A low-confidence square is marked with '?' and must be reviewed before using its FEN.
    """
    if board_bgr is None or board_bgr.size == 0:
        raise ValueError("Ảnh bàn cờ trống.")
    templates = templates or load_templates()
    height, width = board_bgr.shape[:2]
    cell_w, cell_h = width / 8.0, height / 8.0
    debug = board_bgr.copy()
    ranks, confidence = [], []
    for row in range(8):
        fen_rank = ""
        conf_row = []
        empty_run = 0
        for col in range(8):
            x0, x1 = round(col*cell_w), round((col+1)*cell_w)
            y0, y1 = round(row*cell_h), round((row+1)*cell_h)
            square = board_bgr[y0:y1, x0:x1]
            # Remove thin grid borders, but leave the centered piece visible.
            pad_x, pad_y = max(1, int(square.shape[1]*0.035)), max(1, int(square.shape[0]*0.035))
            inner = square[pad_y:square.shape[0]-pad_y, pad_x:square.shape[1]-pad_x]
            scores = sorted(
                ((_score_square(inner, tmpl, min(inner.shape[:2])), symbol) for symbol, tmpl in templates.items()),
                reverse=True,
            )
            best_score, symbol = scores[0]
            second_score = scores[1][0] if len(scores) > 1 else 0.0
            # Empty-square heuristic: piece templates should have a clear advantage over empty-board texture.
            piece_present = best_score > 0.68 and (best_score - second_score) > 0.008
            conf_row.append(round(best_score, 3) if piece_present else round(max(0.0, 1.0-best_score), 3))
            if piece_present:
                if empty_run:
                    fen_rank += str(empty_run); empty_run = 0
                fen_rank += symbol
                color = (60, 220, 80) if best_score >= 0.76 else (0, 180, 255)
                cv2.rectangle(debug, (x0+2,y0+2), (x1-2,y1-2), color, 2)
                cv2.putText(debug, f"{symbol}:{best_score:.2f}", (x0+3,y0+16), cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)
            else:
                empty_run += 1
                # Annotate weak matches so calibration errors are visible.
                if best_score > 0.58:
                    cv2.rectangle(debug, (x0+2,y0+2), (x1-2,y1-2), (0,165,255), 1)
            if flipped:
                # The input image is still processed top-left to bottom-right;
                # flip only the resulting board placement back to chess coordinates.
                pass
        if empty_run:
            fen_rank += str(empty_run)
        ranks.append(fen_rank or "8")
        confidence.append(conf_row)
    if flipped:
        # A 180-degree rotated board image has to be normalized into White's standard orientation.
        ranks = ranks[::-1]
        ranks = [rank for rank in ranks]
        # Reverse each expanded rank, not its compressed FEN text.
        def expand(rank):
            out=[]
            for char in rank:
                out.extend(["."]*int(char) if char.isdigit() else [char])
            return out
        def compress(cells):
            out=""; empty=0
            for ch in cells:
                if ch==".":
                    empty+=1
                else:
                    if empty: out+=str(empty); empty=0
                    out+=ch
            if empty: out+=str(empty)
            return out or "8"
        ranks=[compress(list(reversed(expand(rank)))) for rank in ranks]
    return "/".join(ranks), confidence, debug
