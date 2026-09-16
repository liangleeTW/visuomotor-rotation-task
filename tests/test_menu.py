"""
Unit tests for vmr.menu.

Flags:
    (none — run with pytest)

Usage:
    poetry run pytest tests/test_menu.py -v
"""

import pygame
import pytest

from vmr.menu import (
    BLOCKS,
    MenuSelection,
    TextEntryState,
    draw_menu,
    draw_text_entry,
    existing_trial_count,
    handle_menu_key,
    handle_text_entry_key,
    session_paths,
)


def make_key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


# ---------------------------------------------------------------------------
# MenuSelection / handle_menu_key
# ---------------------------------------------------------------------------


def test_menu_starts_at_first_option():
    sel = MenuSelection()
    assert sel.selected == BLOCKS[0]


def test_menu_down_wraps_around():
    sel = MenuSelection()
    for _ in range(len(BLOCKS)):
        sel.move(1)
    assert sel.selected == BLOCKS[0]


def test_menu_up_from_first_wraps_to_last():
    sel = MenuSelection()
    sel.move(-1)
    assert sel.selected == BLOCKS[-1]


def test_handle_menu_key_navigation_and_confirm():
    sel = MenuSelection()
    assert handle_menu_key(sel, pygame.K_DOWN) is None
    assert sel.selected == BLOCKS[1]
    assert handle_menu_key(sel, pygame.K_UP) is None
    assert sel.selected == BLOCKS[0]
    result = handle_menu_key(sel, pygame.K_RETURN)
    assert result == BLOCKS[0]


def test_handle_menu_key_ignores_unrelated_keys():
    sel = MenuSelection()
    assert handle_menu_key(sel, pygame.K_a) is None
    assert sel.selected == BLOCKS[0]


# ---------------------------------------------------------------------------
# TextEntryState / handle_text_entry_key
# ---------------------------------------------------------------------------


def test_text_entry_typing_and_backspace():
    state = TextEntryState()
    for ch in "S01":
        state.input_char(ch)
    assert state.text == "S01"
    state.backspace()
    assert state.text == "S0"


def test_text_entry_confirm_requires_nonempty():
    state = TextEntryState()
    assert handle_text_entry_key(state, make_key_event(pygame.K_RETURN)) is False
    state.input_char("X")
    assert handle_text_entry_key(state, make_key_event(pygame.K_RETURN)) is True


def test_handle_text_entry_key_appends_unicode_and_backspaces():
    state = TextEntryState()
    handle_text_entry_key(state, make_key_event(pygame.K_a, unicode="a"))
    handle_text_entry_key(state, make_key_event(pygame.K_b, unicode="b"))
    assert state.text == "ab"
    handle_text_entry_key(state, make_key_event(pygame.K_BACKSPACE))
    assert state.text == "a"


def test_text_entry_clear():
    state = TextEntryState("abc")
    state.clear()
    assert state.text == ""


# ---------------------------------------------------------------------------
# session_paths / existing_trial_count
# ---------------------------------------------------------------------------


def test_session_paths_layout(tmp_path):
    paths = session_paths(tmp_path, "S01", "baseline")
    assert paths.trials_csv == tmp_path / "S01" / "baseline" / "trials.csv"
    assert paths.samples_csv == tmp_path / "S01" / "baseline" / "samples.csv"
    assert paths.schedule_csv == tmp_path / "S01" / "baseline" / "schedule.csv"
    assert paths.config_snapshot_yaml == tmp_path / "S01" / "baseline" / "config_snapshot.yaml"


def test_existing_trial_count_zero_when_missing(tmp_path):
    assert existing_trial_count(tmp_path / "nope.csv") == 0


def test_existing_trial_count_counts_data_rows(tmp_path):
    path = tmp_path / "trials.csv"
    path.write_text("a,b,c\n1,2,3\n4,5,6\n")
    assert existing_trial_count(path) == 2


def test_existing_trial_count_header_only_is_zero(tmp_path):
    path = tmp_path / "trials.csv"
    path.write_text("a,b,c\n")
    assert existing_trial_count(path) == 0


# ---------------------------------------------------------------------------
# rendering smoke tests (headless, via tests/conftest.py dummy drivers)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def pygame_session():
    pygame.init()
    pygame.font.init()
    yield
    pygame.quit()


def test_draw_menu_smoke():
    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.SysFont(None, 32)
    sel = MenuSelection()
    draw_menu(screen, font, sel)  # must not raise
    pixel = screen.get_at((400, 300))
    assert pixel is not None


def test_draw_text_entry_smoke():
    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.SysFont(None, 32)
    state = TextEntryState("S01")
    draw_text_entry(screen, font, "Enter subject ID:", state)  # must not raise
