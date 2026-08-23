"""Tests for cli/setup.py — browser-profile child-process transport.

P1-10 fail-closed remediation (F-3): upstream interpolated profile_name
directly into the `python -c` source spliced into subprocess.run, so a name
containing a quote became executable code and a trailing backslash broke the
child outright (both falsified pre-fix — see PORTING-NOTES P1-10 "Fail-closed
remediation"). The name now crosses out-of-band as argv[1].
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from hyperresearch.cli import setup as setup_mod
from hyperresearch.cli.setup import (
    _PROFILE_CREATE_SCRIPT,
    _create_profile_interactive,
    _profile_create_command,
)

HOSTILE_NAMES = [
    # Closes the string and call, injects a statement, re-opens a valid call.
    'x"); print("INJECTED-CODE-EXECUTION"); profiler.create_profile("y',
    # Trailing backslash: escaped the closing quote of the spliced literal.
    "research\\",
    "semi;colon",
    'quote"name',
    "${PATH} and `backticks` and 'single'",
]


def test_child_script_is_valid_python_with_no_name_hole():
    """The shipped child script parses standalone and carries no leftover
    interpolation hole — the name can only arrive via sys.argv."""
    compile(_PROFILE_CREATE_SCRIPT, "<profile-create-script>", "exec")
    assert "{profile_name}" not in _PROFILE_CREATE_SCRIPT
    assert "sys.argv[1]" in _PROFILE_CREATE_SCRIPT


@pytest.mark.parametrize("name", HOSTILE_NAMES)
def test_command_builder_passes_name_out_of_band(name):
    """The hostile name rides as its own argv element, never inside the
    script source."""
    argv = _profile_create_command(name)
    assert argv[1] == "-c"
    assert argv[2] == _PROFILE_CREATE_SCRIPT
    assert argv[3] == name  # exact round-trip, no quoting/mangling
    assert name not in argv[2]


def test_argv_transport_delivers_hostile_payload_as_data():
    """The transport contract the fix relies on: `python -c SCRIPT x` hands
    x to the child as sys.argv[1] — data, never parsed as code."""
    payload = HOSTILE_NAMES[0]
    proc = subprocess.run(
        [sys.executable, "-c", "import sys; print(repr(sys.argv[1]))", payload],
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout.strip() == repr(payload)


@pytest.mark.parametrize("name", HOSTILE_NAMES)
def test_hostile_profile_name_travels_as_data(tmp_path, monkeypatch, capfd, name):
    """End-to-end: run the real child command against a stubbed crawl4ai and
    prove a hostile name reaches create_profile() as pure data — nothing from
    it executes as code."""
    fake_pkg = tmp_path / "fakecrawl"
    (fake_pkg / "crawl4ai").mkdir(parents=True)
    (fake_pkg / "crawl4ai" / "__init__.py").write_text(
        "class BrowserProfiler:\n"
        "    async def create_profile(self, profile_name):\n"
        "        print(f'PROFILE_PATH={profile_name}')\n"
        "        return profile_name\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(fake_pkg))
    monkeypatch.setattr(setup_mod.Prompt, "ask", staticmethod(lambda *a, **k: name))
    monkeypatch.setattr(setup_mod.Confirm, "ask", staticmethod(lambda *a, **k: True))

    result = _create_profile_interactive()

    assert result == name  # child exited 0 and handed the name back intact
    captured = capfd.readouterr().out
    assert f"PROFILE_PATH={name}" in captured
    # The injection payload's marker never executed as a bare statement.
    assert "INJECTED-CODE-EXECUTION:" not in captured
