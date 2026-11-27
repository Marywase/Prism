"""Exercise the actual replay/TUI and terminal guard, with fixture-only replay."""
import errno
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import sys
import termios
import time

binary = str(Path(sys.argv[1]).resolve())
results = []

def check_tty(name, args, *, keys=b'q', env_extra=None, expected_exit=0, expect_screen=True):
    master, slave = pty.openpty()
    before = termios.tcgetattr(slave)
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 120, 0, 0))
    env = {**os.environ, 'TERM': 'xterm-256color', **(env_extra or {})}
    def controlling_terminal():
        os.setsid()
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    process = subprocess.Popen([binary, *args], stdin=slave, stdout=slave, stderr=slave, env=env, preexec_fn=controlling_terminal)
    output = bytearray()
    sent = False
    deadline = time.monotonic() + 20
    try:
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.05)[0]:
                try:
                    output.extend(os.read(master, 65536))
                except OSError as error:
                    if error.errno != errno.EIO:
                        raise
            if not sent and b'Timeline' in output and keys:
                os.write(master, keys)
                sent = True
            if process.poll() is not None:
                while select.select([master], [], [], 0)[0]:
                    try:
                        chunk = os.read(master, 65536)
                        if not chunk: break
                        output.extend(chunk)
                    except OSError:
                        break
                break
        if process.poll() is None:
            process.kill()  # This child was created by this test only.
            raise AssertionError(name + ' timed out')
        assert process.returncode == expected_exit, (name, process.returncode, output[-2000:])
        assert termios.tcgetattr(slave) == before, name + ': terminal attributes not restored'
        if expect_screen:
            for sequence in [b'\x1b[?1049h', b'\x1b[?1049l', b'\x1b[?25l', b'\x1b[?25h']:
                assert sequence in output, (name, sequence, output[-2000:])
        else:
            assert b'\x1b[?1049h' not in output, name
        if name == 'unicode replay':
            assert 'é'.encode() in output
            assert b'panicked' not in output
        results.append({'name': name, 'exit': process.returncode, 'terminal_restored': True})
        print('PASS', name, flush=True)
    finally:
        if process.poll() is None: process.kill()
        process.wait()
        os.close(master)
        os.close(slave)

check_tty('quit after navigation', ['replay', 'fixture', '-i'], keys=b'\t\x1b[Zjsok\x1b[B\x1b[Aq')
check_tty('Escape exit', ['replay', 'fixture', '--interactive'], keys=b'\x1b')
check_tty('unicode replay', ['replay', 'fixture', '-i'], env_extra={'PRISM523_UNICODE': '1'})
check_tty('normal guard return', ['guard', 'normal'])
check_tty('guard error', ['guard', 'error'], expected_exit=1)
check_tty('guard panic unwind', ['guard', 'panic'], expected_exit=101)
check_tty('replay failure before terminal entry', ['replay', 'fixture', '-i'], env_extra={'PRISM523_REPLAY_ERROR': '1'}, expected_exit=1, expect_screen=False)

for args in [['replay', 'fixture'], ['replay', 'fixture', '--output', 'json'], ['replay', 'fixture', '-i']]:
    result = subprocess.run([binary, *args], stdin=subprocess.DEVNULL, capture_output=True, env={**os.environ, 'PRISM523_REPLAY_ERROR': '1'})
    if '-i' in args:
        assert result.returncode == 1 and b'requires a terminal' in result.stderr
    elif 'json' in args:
        assert result.returncode == 0 and json.loads(result.stdout)['status'] == 'interactive_mode_required'
    else:
        assert result.returncode == 0 and b'--interactive' in result.stdout
    assert b'\x1b[?1049h' not in result.stdout + result.stderr
    results.append({'name': 'redirected ' + ' '.join(args), 'exit': result.returncode})
    print('PASS redirected', args, flush=True)
Path(sys.argv[2]).write_text(json.dumps(results, indent=2), encoding='utf-8')
