"""
Test-session setup: force pygame's dummy video/audio drivers so tests that
touch pygame (display, audio, integration/smoke tests) run headlessly in
CI/sandboxes without a real screen or sound device. Production code
(run_block.py) is never invoked with these env vars set, so real sessions
still use the real drivers.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
