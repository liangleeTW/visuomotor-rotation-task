"""
Unit tests for vmr.audio.

Flags:
    (none — run with pytest)

Usage:
    poetry run pytest tests/test_audio.py -v
"""

import pytest

from vmr.audio import SoundBank
from vmr.config import AudioConfig

AUDIO_CFG = AudioConfig(go_beep="go_beep.wav", hit_bell="hit_bell.wav", miss_buzz="miss_buzz.wav")


class _FakeSound:
    def __init__(self, path):
        self.path = path
        self.play_calls = 0

    def play(self):
        self.play_calls += 1


class _FakeMixer:
    def __init__(self, fail_on=()):
        self._initialized = False
        self.fail_on = set(fail_on)

    def get_init(self):
        return self._initialized

    def init(self):
        self._initialized = True

    def Sound(self, path):
        for bad in self.fail_on:
            if bad in path:
                raise RuntimeError(f"simulated load failure for {path}")
        return _FakeSound(path)


def test_missing_assets_dir_warns_and_plays_silently(tmp_path):
    empty_dir = tmp_path / "no_audio_here"
    with pytest.warns(UserWarning, match="audio asset missing"):
        bank = SoundBank(AUDIO_CFG, assets_dir=empty_dir, mixer_module=_FakeMixer())
    assert not bank.is_available("go_beep")
    bank.play("go_beep")  # must not raise


def test_existing_files_load_and_play(tmp_path):
    for filename in ("go_beep.wav", "hit_bell.wav", "miss_buzz.wav"):
        (tmp_path / filename).write_bytes(b"not a real wav, just needs to exist")
    fake_mixer = _FakeMixer()
    bank = SoundBank(AUDIO_CFG, assets_dir=tmp_path, mixer_module=fake_mixer)
    assert bank.is_available("go_beep")
    assert bank.is_available("hit_bell")
    assert bank.is_available("miss_buzz")
    bank.play("hit_bell")
    assert bank._sounds["hit_bell"].play_calls == 1


def test_partial_assets_only_missing_ones_are_silent(tmp_path):
    (tmp_path / "go_beep.wav").write_bytes(b"x")
    with pytest.warns(UserWarning):
        bank = SoundBank(AUDIO_CFG, assets_dir=tmp_path, mixer_module=_FakeMixer())
    assert bank.is_available("go_beep")
    assert not bank.is_available("hit_bell")
    assert not bank.is_available("miss_buzz")


def test_unknown_sound_name_raises(tmp_path):
    bank = SoundBank(AUDIO_CFG, assets_dir=tmp_path, mixer_module=_FakeMixer())
    with pytest.raises(KeyError):
        bank.play("explosion")


def test_load_exception_degrades_to_silent(tmp_path):
    (tmp_path / "go_beep.wav").write_bytes(b"x")
    with pytest.warns(UserWarning, match="failed to load"):
        bank = SoundBank(AUDIO_CFG, assets_dir=tmp_path, mixer_module=_FakeMixer(fail_on=["go_beep"]))
    assert not bank.is_available("go_beep")
    bank.play("go_beep")  # must not raise
