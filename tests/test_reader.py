import time

import numpy as np

from maplelens import reader
from maplelens.readers import Reading

JOB = (42, (0, 0, 800, 600), 5.0, frozenset())
READING = Reading(5.0, None, None, None, None)


def _wait(r, timeout=20.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = r.take()
        if got is not None:
            return got
        time.sleep(0.02)
    raise AssertionError("no answer")


def test_inline_reader_answers_at_once():
    r = reader.InlineReader(work=repr)
    r.ask(JOB)
    assert r.take() == repr(JOB)
    assert r.take() is None


def test_inline_reader_returns_the_error():
    r = reader.InlineReader(work=int)
    r.ask(JOB)
    assert isinstance(r.take(), TypeError)


def test_process_reader_round_trip():
    r = reader.ProcessReader(work=repr)
    try:
        r.ask(JOB)
        r.ask((1, 2, 3, 4))  # busy: ignored
        assert _wait(r) == repr(JOB)
        time.sleep(0.5)
        assert r.take() is None
    finally:
        r.close()


def test_process_reader_returns_the_childs_error():
    r = reader.ProcessReader(work=int)
    try:
        r.ask(JOB)
        assert isinstance(_wait(r), TypeError)
    finally:
        r.close()


def test_process_reader_restarts_a_dead_child():
    r = reader.ProcessReader(work=repr)
    try:
        r.ask(JOB)
        assert _wait(r) == repr(JOB)
        r._proc.kill()
        r._proc.join()
        r.ask(JOB)
        assert _wait(r) == repr(JOB)
    finally:
        r.close()


def test_process_reader_gives_up_on_a_stuck_child():
    r = reader.ProcessReader(work=time.sleep, stuck_s=0.5)
    try:
        r.ask(60)
        time.sleep(1)
        old = r._proc
        r.ask(60)
        assert r._proc.pid != old.pid
        assert not old.is_alive()
    finally:
        r.close()


def test_process_reader_answers_every_tick():
    r = reader.ProcessReader(work=repr)
    try:
        got = []
        end = time.monotonic() + 20
        i = 0
        while time.monotonic() < end and len(got) < 4:
            r.ask(i)
            a = r.take()
            if a is not None:
                got.append(a)
            elif got:
                raise AssertionError("a tick was skipped")
            i += 1
            time.sleep(0.3)
        assert len(got) == 4
        n = int(got[1])  # jobs asked while the child started were ignored; after that, no gaps
        assert got[1:] == [repr(n + k) for k in range(3)]
    finally:
        r.close()


def test_read_game_trims_the_black_bars(monkeypatch):
    frame = np.zeros((600, 800, 3), np.uint8)
    frame[50:550] = 60
    seen = []
    monkeypatch.setattr(reader.capture, "grab", lambda hwnd, r: frame)
    monkeypatch.setattr(
        reader, "read_all", lambda f, now, due=None: seen.append(f.shape) or READING
    )
    assert reader.read_game(JOB) == ((0, 50, 800, 500), READING)
    assert seen == [(500, 800, 3)]
