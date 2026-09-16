"""
Preloads and plays the task's sound effects (go beep, hit bell, miss buzz).

Missing sound files are a warning, not a crash: the audio assets aren't
committed yet (to be added later), and a silent `play()` no-op lets the
whole experiment be built, tested, and even piloted (with no audio
feedback) before the files exist.

Flags:
    (none — this module is imported, not run directly)

Usage:
    from vmr.audio import SoundBank
    bank = SoundBank(cfg.audio, assets_dir="assets/audio")
    bank.play("go_beep")
"""

from __future__ import annotations

import warnings
from pathlib import Path

from vmr.config import AudioConfig

DEFAULT_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "audio"


class SoundBank:
    """Loads the three named sounds from `assets_dir`. Any sound whose
    file is missing plays as silence with a one-time warning, rather than
    raising — see module docstring."""

    def __init__(self, audio_cfg: AudioConfig, assets_dir: str | Path | None = None, mixer_module=None):
        if mixer_module is None:
            import pygame.mixer as mixer_module  # noqa: PLC0415
        self._mixer = mixer_module
        self._assets_dir = Path(assets_dir) if assets_dir is not None else DEFAULT_ASSETS_DIR
        self._sounds: dict[str, object | None] = {}

        if not self._mixer.get_init():
            self._mixer.init()

        for name, filename in (
            ("go_beep", audio_cfg.go_beep),
            ("hit_bell", audio_cfg.hit_bell),
            ("miss_buzz", audio_cfg.miss_buzz),
        ):
            self._sounds[name] = self._load(name, filename)

    def _load(self, name: str, filename: str):
        path = self._assets_dir / filename
        if not path.exists():
            warnings.warn(
                f"audio asset missing for '{name}': {path} — this sound "
                "will be silent until the file is added",
                stacklevel=3,
            )
            return None
        try:
            return self._mixer.Sound(str(path))
        except Exception as e:  # pragma: no cover - depends on local audio hardware/codecs
            warnings.warn(f"failed to load audio asset '{name}' from {path}: {e}", stacklevel=3)
            return None

    def play(self, name: str) -> None:
        if name not in self._sounds:
            raise KeyError(f"unknown sound name: {name!r} (expected one of {list(self._sounds)})")
        sound = self._sounds[name]
        if sound is not None:
            sound.play()

    def is_available(self, name: str) -> bool:
        return self._sounds.get(name) is not None
