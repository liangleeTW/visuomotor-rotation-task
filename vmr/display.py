"""
Rendering layer: draws every on-screen element (home, cursor, target,
landmark ring, instruction text, report-entry overlay) for a TrialRunner's
current state.

This module owns "what color/shape goes where"; it never decides *whether*
something should happen (that's TrialRunner) or drives timing (that's
run_block.py's main loop). Kept this way so the trial logic stays
testable without a display, and the display logic is a thin, mechanical
translation of already-decided state.

Flags:
    (none — this module is imported, not run directly)

Usage:
    poetry run pytest tests/test_display.py -v
"""

from __future__ import annotations

import pygame

from vmr import geometry
from vmr.config import ColorsConfig
from vmr.geometry import GeometryParams, Point
from vmr.report_entry import ReportEntryState
from vmr.trial import GOOD, TOO_FAST, TrialPhase, TrialRunner

# Spec-quoted instruction text (Chinese, verbatim from the source PDF).
# See to-decide.md #26/#27 for which trial types get which scope, and the
# two transitions the spec leaves undefined (not invented here).
INSTRUCTION_TEXT: dict[str, list[str]] = {
    "familiarization": [
        "聽到「嗶」聲後朝目標點像射擊動作一樣快速移動",
        "看到目標點變綠色或消失就將手指抬離觸控板回到起始點",
    ],
    "baseline": [
        "聽到「嗶」聲後朝目標點像射擊動作一樣快速移動",
        "看到目標點變綠色或消失就將手指抬離觸控板回到起始點",
        "有些回合會沒有游標，照原本的移動方式動就好",
        "有些回合需要您講出要向哪個數字移動後再執行",
    ],
    "adaptation_report": [
        "請先說出要瞄準的目標後，聽到「嗶」聲再移動",
    ],
    "adaptation_return_to_baseline": [
        "請不要使用剛才學到的調整方式，",
        "像一開始一樣用射擊的方式直接朝目標移動。",
    ],
    "post_exclusion": [
        "請不要使用剛才學到的調整方式，",
        "像一開始一樣用射擊的方式直接朝目標移動。",
    ],
    "post_inclusion": [
        "請使用剛才學到的調整方式，像剛才練習時一樣完成動作。",
    ],
}

INSTRUCTION_FOOTER = "（實驗人員請按 SPACE 繼續 / experimenter: press SPACE to continue）"

# pygame's bundled default font has no CJK glyphs (renders tiny tofu boxes
# for Chinese text) — prefer a real CJK-capable system font, falling back
# to the default only if none of these are installed.
_CJK_FONT_CANDIDATES = ["stheitimedium", "stheitilight", "pingfangtc", "pingfangsc", "songti"]


def _cjk_font(size: int) -> pygame.font.Font:
    available = set(pygame.font.get_fonts())
    for name in _CJK_FONT_CANDIDATES:
        if name in available:
            return pygame.font.SysFont(name, size)
    return pygame.font.SysFont(None, size)


def _ipos(pos: Point) -> tuple[int, int]:
    return (int(round(pos[0])), int(round(pos[1])))


class Renderer:
    def __init__(self, screen: pygame.Surface, colors: ColorsConfig, params: GeometryParams, font=None, small_font=None):
        self.screen = screen
        self.colors = colors
        self.params = params
        self.font = font or _cjk_font(32)
        self.small_font = small_font or _cjk_font(20)

    # -- primitives ---------------------------------------------------------

    def clear(self) -> None:
        self.screen.fill(self.colors.background)

    def draw_home(self) -> None:
        pos = _ipos((self.params.home_x_px, self.params.home_y_px))
        pygame.draw.circle(self.screen, self.colors.home, pos, max(1, int(self.params.home_radius_px)))

    def draw_cursor(self, pos: Point) -> None:
        pygame.draw.circle(self.screen, self.colors.cursor, _ipos(pos), max(1, int(self.params.cursor_radius_px)))

    def draw_target(self, pos: Point, color: tuple[int, int, int]) -> None:
        pygame.draw.circle(self.screen, color, _ipos(pos), max(1, int(self.params.target_radius_px)))

    def draw_landmark_ring(self, target_angle_deg: float) -> None:
        max_mag = self.params.landmark_max_magnitude
        for signed_number in range(-max_mag, max_mag + 1):
            pos = geometry.landmark_position_px(signed_number, target_angle_deg, self.params)
            pygame.draw.circle(self.screen, self.colors.landmark, _ipos(pos), 2)
            label = self.small_font.render(str(signed_number), True, self.colors.landmark)
            self.screen.blit(label, (pos[0] - label.get_width() / 2, pos[1] - label.get_height() / 2 - 10))

    def draw_text_block(self, lines: list[str], color: tuple[int, int, int], center: Point, line_height: int = 40) -> None:
        cx, cy = center
        total_h = len(lines) * line_height
        top = cy - total_h / 2
        for i, line in enumerate(lines):
            surf = self.font.render(line, True, color)
            self.screen.blit(surf, (cx - surf.get_width() / 2, top + i * line_height))

    def draw_report_entry_overlay(self, entry: ReportEntryState) -> None:
        # Echo the number in the ring's own format ("-10"), as it was spoken.
        text = f"回報: {entry.text or '_'}"
        surf = self.small_font.render(text, True, self.colors.instruction_text)
        self.screen.blit(surf, (20, self.screen.get_height() - 40))

    def flip(self) -> None:
        pygame.display.flip()

    # -- composite: one full trial frame -------------------------------------

    def render_trial_frame(self, runner: TrialRunner) -> None:
        self.clear()
        spec = runner.spec

        if runner.phase is TrialPhase.HOME_HOLD:
            self.draw_home()
            if runner.samples:
                s = runner.samples[-1]
                self.draw_cursor((s.raw_x, s.raw_y))

        elif runner.phase is TrialPhase.REPORT_WAIT:
            self.draw_home()
            self.draw_target(runner.target_pos_px, self.colors.target_default)
            self.draw_landmark_ring(spec.target_angle_deg)
            self.draw_report_entry_overlay(runner.report_entry)

        elif runner.phase is TrialPhase.MOVING:
            if runner.movement_onset_timestamp is None:
                self.draw_home()
            self.draw_target(runner.target_pos_px, self.colors.target_default)
            if spec.needs_report:
                self.draw_landmark_ring(spec.target_angle_deg)
            if spec.cursor_visible_during_movement and runner.displayed_pos is not None:
                self.draw_cursor(runner.displayed_pos)

        elif runner.phase in (TrialPhase.END_FEEDBACK, TrialPhase.DONE):
            if runner.end_reason == "hit":
                color = {
                    GOOD: self.colors.hit_good,
                    TOO_FAST: self.colors.hit_too_fast,
                }.get(runner.speed_feedback, self.colors.hit_too_slow)
                self.draw_target(runner.target_pos_px, color)
            # miss (boundary/timeout): target disappears, nothing drawn

    def render_instruction(self, instruction_key: str) -> None:
        self.clear()
        lines = INSTRUCTION_TEXT.get(instruction_key, [])
        center = (self.screen.get_width() / 2, self.screen.get_height() / 2)
        self.draw_text_block(lines, self.colors.instruction_text, center)
        footer = self.small_font.render(INSTRUCTION_FOOTER, True, self.colors.instruction_text)
        self.screen.blit(footer, (center[0] - footer.get_width() / 2, self.screen.get_height() - 60))
