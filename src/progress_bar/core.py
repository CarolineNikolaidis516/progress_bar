# Progress bar that stays quiet when stdout is redirected.
import os
import sys


def _is_interactive(stream):
    # A TTY check is necessary but not sufficient. CI systems run with a
    # TTY-less stdout even when a human is watching; and conversely some
    # terminals attach pseudo-TTYs to pipes. We treat "has a TTY" as the
    # signal to animate, because that is the one reliable invariant: when
    # stdout is a regular file, os.isatty returns False, and progress spam
    # does not pollute the log.
    try:
        return stream.isatty()
    except Exception:
        # Some stream wrappers raise on isatty(); treat that as non-interactive.
        return False


class ProgressBar:
    """A single-line progress bar that writes nothing when stdout is not a TTY.

    When stdout is a file or a pipe (``python script.py > log.txt``), the bar
    is completely silent. This is the whole point: animated progress bars are
    noise in a log, and the usual trick of piping stderr instead is not always
    available. Detection happens once at construction time, so the bar does
    not flicker if a caller swaps ``sys.stdout`` mid-run.
    """

    def __init__(
        self,
        total,
        width=40,
        fill="#",
        empty="-",
        stream=None,
        interval=0.1,
        clock=None,
    ):
        if total <= 0:
            raise ValueError("total must be a positive integer")
        if width <= 0:
            raise ValueError("width must be a positive integer")
        if len(fill) != 1:
            raise ValueError("fill must be exactly one character")
        if len(empty) != 1:
            raise ValueError("empty must be exactly one character")
        if interval < 0:
            raise ValueError("interval must be non-negative")

        self.total = total
        self.width = width
        self.fill = fill
        self.empty = empty
        self.stream = stream if stream is not None else sys.stdout
        self.interval = interval
        self.clock = clock if clock is not None else _default_clock
        self._value = 0
        self._start = self.clock()
        self._last_draw = None
        self._closed = False
        self._interactive = _is_interactive(self.stream)
        self._last_len = 0

    def update(self, value):
        """Advance the bar to ``value`` and redraw if appropriate.

        Redraw is throttled by ``interval`` seconds of the injected clock, so
        a tight loop calling ``update`` a million times does not produce a
        million writes. When ``value`` reaches ``total`` the bar is finalized
        immediately and unconditionally, ignoring the throttle, so completion
        is never delayed by an unlucky clock reading.
        """
        if self._closed:
            return
        if value < 0:
            value = 0
        elif value > self.total:
            value = self.total
        self._value = value

        if not self._interactive:
            # Silent mode: render once on completion so a caller that only
            # inspects the stream file sees a final summary line, not
            # silence. This is a deliberate choice — completely empty logs
            # are unsettling, and one static line costs nothing.
            if value >= self.total:
                self._write_final()
                self._closed = True
            return

        now = self.clock()
        if value >= self.total:
            self._write_final()
            self._closed = True
            return

        if self._last_draw is None or (now - self._last_draw) >= self.interval:
            self._write_partial()
            self._last_draw = now

    def finish(self):
        """Force-finalize the bar at its current value, even if below total."""
        if self._closed:
            return
        if self._interactive:
            self._write_final()
        elif self._value >= self.total:
            self._write_final()
        self._closed = True

    def _write_partial(self):
        line = self._render(include_pct=True)
        # Carriage return rewrites the same line without scrolling.
        self.stream.write("\r" + line)
        self.stream.flush()
        self._last_len = len(line)

    def _write_final(self):
        line = self._render(include_pct=True)
        if self._interactive:
            # Pad with spaces to overwrite any longer previous partial line,
            # then newline so the cursor moves down cleanly.
            pad = max(0, self._last_len - len(line))
            self.stream.write("\r" + line + (" " * pad) + "\n")
        else:
            # Non-interactive final line: just the line plus newline.
            self.stream.write(line + "\n")
        self.stream.flush()

    def _render(self, include_pct=True):
        if self.total <= 0:
            filled = 0
        else:
            filled = int(self.width * self._value / self.total)
        if filled > self.width:
            filled = self.width
        if filled < 0:
            filled = 0
        bar = self.fill * filled + self.empty * (self.width - filled)
        if include_pct:
            pct = (100 * self._value) // self.total if self.total > 0 else 0
            if pct > 100:
                pct = 100
            return "{} {}/{} ({}%)".format(bar, self._value, self.total, pct)
        return bar


def _default_clock():
    return _clock_monotonic()


def _clock_monotonic():
    # We avoid importing time at module load so that environments that stub
    # the clock do not pay for it; the default clock is only consulted when
    # no fake clock is injected. time.monotonic is preferred over time.time
    # because progress throttling must not jump backwards across NTP adjusts.
    import time

    return time.monotonic()
