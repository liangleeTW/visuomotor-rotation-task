"""
Runnable entry point for one experiment block. Thin wrapper around
vmr.orchestration.main() — the logic lives in the importable package so
it can be exercised by tests; this script is just what a person types.

Flags:
    --subject     Subject ID (creates/resumes data/<subject>/<block>/)
    --block       One of: familiarization, baseline, adaptation, post_adaptation
    --seed        RNG seed for the trial schedule (default: random, then recorded)
    --data-dir    Root directory for session data (default: ./data)
    --windowed    Run in a resizable window instead of fullscreen (for dev)

Usage:
    poetry run python run_block.py --subject S01 --block familiarization
    poetry run python run_block.py --subject S01 --block baseline
    poetry run python run_block.py --subject S01 --block adaptation --windowed
"""

from vmr.orchestration import main

if __name__ == "__main__":
    main()
