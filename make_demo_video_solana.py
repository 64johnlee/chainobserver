"""
Generate a ChainObserver SOLANA demo video using Pillow + ffmpeg.
Output: demo/chainobserver_solana_demo.mp4  (~95s, 1280x720, 30fps)

Adapted from make_demo_video.py (the original ETHGlobal Lisbon / EVM demo).
Same visual style; all data below is REAL — captured live against Solana
mainnet-beta on 2026-09-05 (signature 2GGomDhL7fvshsTGRc6BQYa1pwHJYYcdJKPRcxRDmSoiWjkNjLMpMDe4uz155N6zSt8gR2EMrCtgzmrYE2pEu8Je),
not fabricated for the demo.

Segments:
  0:00-0:05  Title card
  0:05-0:11  The problem (Solana has no revert string)
  0:11-0:14  The one-command solution
  0:14-0:16  Panel appears
  0:16-0:20  Tool 1 — get_solana_transaction
  0:20-0:24  Tool 2 — decode_program_error
  0:24-0:28  Tool 3 — get_program_info
  0:28-0:31  Gemini reasoning
  0:31-0:40  Result card
  0:40-0:46  Failure taxonomy (designed-for categories, honestly labeled)
  0:46-0:56  Architecture diagram
  0:56-1:01  Multi-VM support (EVM + Solana)
  1:01-1:09  Live URLs + closing
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H   = 1280, 720
FPS    = 30
FONT_SIZE = 16
LINE_H = 22
PAD_X, PAD_Y = 36, 36

BG      = (13,  17,  23)
FG      = (220, 220, 220)
DIM     = (100, 100, 100)
PURPLE  = (163, 113, 247)   # ChainObserver brand
CYAN    = (97,  214, 214)   # tool calls
GREEN   = (106, 153,  85)
YELLOW  = (220, 187,  68)
RED     = (240,  71,  71)
ORANGE  = (209, 154, 102)
BORDER  = ( 55,  60,  75)
WHITE   = (255, 255, 255)

# Windows Consolas (Regular/Bold) — this script runs on the dev machine, not
# the Linux path make_demo_video.py used.
FONT_PATH      = r"C:\Windows\Fonts\consola.ttf"
BOLD_FONT_PATH = r"C:\Windows\Fonts\consolab.ttf"
FRAMES_DIR     = Path(r"C:\Users\User\AppData\Local\Temp\co_frames_solana")
OUT_VIDEO      = Path(r"C:\Users\User\chainobserver\demo\chainobserver_solana_demo.mp4")


@dataclass
class Line:
    text:  str
    color: tuple[int, int, int] = field(default_factory=lambda: FG)
    bold:  bool = False

@dataclass
class Segment:
    lines:        list[Line]
    hold_frames:  int = FPS
    typing_speed: int = 1

def _l(text="", color=FG,   bold=False): return Line(text, color, bold)
def _dim(t):    return Line(t, DIM)
def _p(t, b=False): return Line(t, PURPLE, b)
def _c(t, b=False): return Line(t, CYAN, b)
def _g(t, b=False): return Line(t, GREEN, b)
def _y(t):      return Line(t, YELLOW)
def _r(t, b=False): return Line(t, RED, b)
def _o(t):      return Line(t, ORANGE)
def _w(t):      return Line(t, WHITE, True)


SCRIPT: list[Segment] = [

    # ── 0  Title card (5 s) ──────────────────────────────────────────────────
    Segment(lines=[
        _l(),
        _p(" ██████╗██╗  ██╗ █████╗ ██╗███╗  ██╗ ██████╗ ██████╗ ███████╗███████╗██████╗ ", True),
        _p("██╔════╝██║  ██║██╔══██╗██║████╗ ██║██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔══██╗", True),
        _p("██║     ███████║███████║██║██╔██╗██║██║   ██║██████╔╝███████╗█████╗  ██████╔╝", True),
        _p("██║     ██╔══██║██╔══██║██║██║╚████║██║   ██║██╔══██╗╚════██║██╔══╝  ██╔══██╗", True),
        _p("╚██████╗██║  ██║██║  ██║██║██║ ╚███║╚██████╔╝██████╔╝███████║███████╗██║  ██║", True),
        _p(" ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚══╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═╝", True),
        _l(),
        _dim("            AI agent that diagnoses failed transactions — now on Solana"),
        _l(),
        _dim("            Gemini 2.5 Flash  ·  4 Solana MCP tools  ·  Colosseum Crypto World's Fair"),
    ], hold_frames=FPS * 5, typing_speed=999),

    # ── 1  The problem (6 s) ─────────────────────────────────────────────────
    Segment(lines=[
        _l(),
        _y("  The problem:"),
        _l(),
        _dim("  Solana has no revert string. No require(). No gas."),
        _dim("  A failed tx gives you: meta.err, program logs, a compute-unit count."),
        _dim("  Was it a custom program error? Compute budget? Missing account?"),
        _l(),
        _g("  ChainObserver reads the logs.  Gemini finds the root cause."),
        _g("  Same 30-second promise — a genuinely different diagnosis model.", True),
    ], hold_frames=FPS * 6, typing_speed=1),

    # ── 2  One command (3 s) ─────────────────────────────────────────────────
    Segment(lines=[
        _l(),
        _c("  # Paste any failed Solana transaction signature", True),
        _l(),
        _l("  $ chainobserver solana diagnose \\", GREEN),
        _l("      2GGomDhL7fvshsTGRc6BQYa1pwHJYYcdJKPRcxRDmSoiWjkNjLMpMDe4uz155N6zSt8gR2EMrCtgzmrYE2pEu8Je", GREEN),
    ], hold_frames=FPS * 3, typing_speed=1),

    # ── 3  Panel appears (2 s) ──────────────────────────────────────────────
    Segment(lines=[
        _l(),
        _dim("  ╭─────────────────────────────────────────────────────────────────╮"),
        _p(  "  │  ChainObserver · tx 2GGomDhL7…                                   │", True),
        _dim("  │  Cluster: Solana Mainnet Beta · Gemini 2.5 Flash · Solana MCP    │"),
        _dim("  ╰─────────────────────────────────────────────────────────────────╯"),
    ], hold_frames=FPS * 2, typing_speed=2),

    # ── 4  Tool 1 — transaction (4 s) ─────────────────────────────────────
    Segment(lines=[
        _l(),
        _c("  → get_solana_transaction(signature)", True),
        _l(),
        _dim('    success=false'),
        _dim('    fee_lamports=12093    compute_units_consumed=68262'),
        _o('    programs: System, ComputeBudget, SPL Token, +3 unrecognized'),
        _dim('    account_key_count=29   log_message_count=41'),
        _dim('    solscan: https://solscan.io/tx/2GGomDhL7…'),
    ], hold_frames=FPS * 4, typing_speed=1),

    # ── 5  Tool 2 — program error (4 s) ────────────────────────────────────
    Segment(lines=[
        _l(),
        _c("  → decode_program_error(signature)", True),
        _l(),
        _r('    category: custom_program_error', True),
        _r('    custom_error_code: 6000  (0x1770)'),
        _dim('    failed_instruction_index: 3'),
        _dim('    meaning: no Anchor error log found — raw program-defined code'),
    ], hold_frames=FPS * 4, typing_speed=1),

    # ── 6  Tool 3 — program info (4 s) ─────────────────────────────────────
    Segment(lines=[
        _l(),
        _c("  → get_program_info(program_id)", True),
        _l(),
        _dim('    program_id: GnZr2LD3N1F7mr5mNdgN7doBMxFNAF9dKtpoNHGCkrx2'),
        _dim('    owner: BPFLoaderUpgradeab1e111111111111111111111111'),
        _g('    executable: true'),
        _o('    known_name: "" — not in the built-in registry'),
    ], hold_frames=FPS * 4, typing_speed=1),

    # ── 7  Gemini reasoning (3 s) ─────────────────────────────────────────
    Segment(lines=[
        _l(),
        _dim("  Gemini 2.5 Flash reasoning…"),
        _l(),
        _dim('  "Program GnZr2LD3... failed with custom error 6000 at instruction 3.'),
        _dim('   No Anchor log to resolve the code — this is a program-defined'),
        _dim("   error the caller needs the program's IDL or source to interpret.\""),
        _l(),
        _g("  [OK] Diagnosis complete in 86.0s  ·  3 tool calls"),
    ], hold_frames=FPS * 3, typing_speed=1),

    # ── 8  Result card (9 s) ────────────────────────────────────────────
    Segment(lines=[
        _l(),
        _dim("  ╭──────────────────────── ChainObserver Diagnosis ─────────────────────────╮"),
        _l("  │  Cluster      Solana Mainnet Beta                                         │", DIM),
        _r("  │  Root cause   Custom program error 6000 in GnZr2LD3...                    │", True),
        _p("  │  Failure type custom_program_error                                        │", True),
        _g("  │  Confidence   high                                                        │"),
        _l("  │  Affected     GnZr2LD3N1F7mr5mNdgN7doBMxFNAF9dKtpoNHGCkrx2                │", DIM),
        _g("  │  Fix          Consult the program's IDL/source for error code 6000       │", True),
        _l("  │  Explorer     https://solscan.io/tx/2GGomDhL7…                            │", DIM),
        _l("  │  Time         86.0s  ·  3 tool calls                                     │", DIM),
        _dim("  ╰─────────────────────────────────────────────────────────────────────────────╯"),
    ], hold_frames=FPS * 9, typing_speed=2),

    # ── 9  Failure taxonomy (6 s) ──────────────────────────────────────────
    Segment(lines=[
        _l(),
        _y("  Designed to detect (live-verified: custom_program_error above):"),
        _l(),
        _p("  •  custom_program_error       Anchor error logs + raw {\"Custom\": n} codes"),
        _p("  •  compute_budget_exceeded    consumed ≥ 98% of requested/default CU limit"),
        _p("  •  account_not_found          InstructionError: AccountNotFound/Uninitialized"),
        _p("  •  rent_exempt_minimum        InstructionError: InsufficientFundsForRent"),
        _p("  •  instruction_error          MissingRequiredSignature, PrivilegeEscalation, …"),
    ], hold_frames=FPS * 5, typing_speed=1),

    # ── 10  Architecture (10 s) ───────────────────────────────────────────
    Segment(lines=[
        _l(),
        _p("  Architecture", True),
        _l(),
        _dim("  ┌────────────────────────────────────────────────┐"),
        _p(  "  │  SolanaDiagnosisAgent  ·  Gemini 2.5 Flash     │"),
        _dim("  │  shares BaseDiagnosisAgent's tool-loop with EVM │"),
        _dim("  └──────────────────────┬─────────────────────────┘"),
        _dim("                         │ MCP stdio subprocess"),
        _dim("                         ▼"),
        _dim("  ┌──────────────────────────────────────────────────┐"),
        _c(  "  │  ChainObserver Solana MCP Server                 │"),
        _dim("  │  ├─ get_solana_transaction   (getTransaction)     │"),
        _dim("  │  ├─ decode_program_error     (err + logs + Anchor)│"),
        _dim("  │  ├─ get_program_info         (getAccountInfo)     │"),
        _dim("  │  └─ get_compute_budget_analysis (raw ix decode)   │"),
        _dim("  └──────────────────────────────────────────────────┘"),
        _dim("       Solana JSON-RPC — raw httpx, no solana-py/solders dependency"),
    ], hold_frames=FPS * 10, typing_speed=1),

    # ── 11  Multi-VM support (5 s) ─────────────────────────────────────────
    Segment(lines=[
        _l(),
        _p("  One tool, two chain families", True),
        _l(),
        _dim("  chainobserver diagnose 0x...                  # Ethereum, Arbitrum, Base, Optimism, Polygon"),
        _dim("  chainobserver solana diagnose <signature>     # Solana mainnet-beta, devnet, testnet"),
        _l(),
        _dim("  REST:  POST /diagnose         {\"tx_hash\": \"0x...\"}"),
        _dim("  REST:  POST /diagnose/solana  {\"signature\": \"...\"}"),
    ], hold_frames=FPS * 4, typing_speed=1),

    # ── 12  Live URLs + closing (8 s) ─────────────────────────────────────
    Segment(lines=[
        _l(),
        _p("  Try it live", True),
        _l(),
        _g("  https://huggingface.co/spaces/johnlee007/chainobserver", True),
        _l(),
        _dim("  POST /diagnose/solana  {\"signature\": \"...\", \"cluster\": \"mainnet-beta\"}"),
        _dim("  GET  /health"),
        _l(),
        _dim("  github.com/64johnlee/chainobserver  ·  MIT"),
        _l(),
        _p("  Built for Colosseum Crypto World's Fair — Solana · Base · Ethereum L1", True),
        _dim("  Powered by Gemini 2.5 Flash · MCP Protocol · raw Solana JSON-RPC"),
    ], hold_frames=FPS * 7, typing_speed=1),
]


def load_fonts():
    reg  = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    bold = ImageFont.truetype(BOLD_FONT_PATH, FONT_SIZE)
    return reg, bold


def render_frame(lines: list[Line], reg, bold) -> Image.Image:
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Title bar
    draw.rectangle([0, 0, W, 28], fill=(22, 24, 34))
    draw.text((12, 6), "● ● ●  ChainObserver Demo — Solana — Colosseum Crypto World's Fair",
              font=reg, fill=DIM)
    draw.line([(0, 28), (W, 28)], fill=BORDER, width=1)

    max_lines = (H - PAD_Y * 2 - 28) // LINE_H
    visible   = lines[-max_lines:] if len(lines) > max_lines else lines

    y = PAD_Y + 28
    for line in visible:
        f = bold if line.bold else reg
        draw.text((PAD_X, y), line.text, font=f, fill=line.color)
        y += LINE_H

    return img


def generate_frames() -> int:
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    reg, bold = load_fonts()
    frame_idx  = 0
    accumulated: list[Line] = []

    def save(n: int = 1) -> None:
        nonlocal frame_idx
        img = render_frame(accumulated, reg, bold)
        for _ in range(n):
            img.save(FRAMES_DIR / f"frame_{frame_idx:06d}.png")
            frame_idx += 1

    for seg in SCRIPT:
        chunk   = max(1, seg.typing_speed)
        pending = list(seg.lines)
        while pending:
            accumulated.extend(pending[:chunk])
            pending = pending[chunk:]
            save(max(1, FPS // 4))
        save(seg.hold_frames)

    print(f"Generated {frame_idx} frames ({frame_idx / FPS:.0f}s)")
    return frame_idx


def encode_video(frame_count: int) -> None:
    OUT_VIDEO.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", str(FRAMES_DIR / "frame_%06d.png"),
        "-c:v", "libx264", "-preset", "slow", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={W}:{H}",
        str(OUT_VIDEO),
    ]
    print("Encoding video…")
    subprocess.run(cmd, check=True, capture_output=True)
    mb = OUT_VIDEO.stat().st_size / 1_048_576
    print(f"Output: {OUT_VIDEO}  ({mb:.1f} MB, {frame_count / FPS:.0f}s)")


if __name__ == "__main__":
    if FRAMES_DIR.exists():
        shutil.rmtree(FRAMES_DIR)
    n = generate_frames()
    encode_video(n)
