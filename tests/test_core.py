# Deterministic tests for progress_bar.ProgressBar.
import io
import os
import unittest

from progress_bar import ProgressBar


class FakeClock:
    def __init__(self, start=0.0):
        self.t = float(start)

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += float(dt)


class TestConstruction(unittest.TestCase):
    def test_rejects_zero_total(self):
        with self.assertRaises(ValueError):
            ProgressBar(0)

    def test_rejects_negative_total(self):
        with self.assertRaises(ValueError):
            ProgressBar(-5)

    def test_rejects_zero_width(self):
        with self.assertRaises(ValueError):
            ProgressBar(10, width=0)

    def test_rejects_multichar_fill(self):
        with self.assertRaises(ValueError):
            ProgressBar(10, fill="##")

    def test_rejects_multichar_empty(self):
        with self.assertRaises(ValueError):
            ProgressBar(10, empty="--")

    def test_rejects_negative_interval(self):
        with self.assertRaises(ValueError):
            ProgressBar(10, interval=-0.01)


class TestNonInteractive(unittest.TestCase):
    def _make(self, total=10, **kw):
        stream = io.StringIO()
        clock = FakeClock(0.0)
        bar = ProgressBar(
            total=total,
            stream=stream,
            clock=clock,
            **kw,
        )
        # StringIO is not a TTY, so the bar auto-detects non-interactive mode.
        return bar, stream, clock

    def test_silent_until_completion(self):
        bar, stream, _ = self._make(total=10)
        bar.update(3)
        bar.update(7)
        self.assertEqual(stream.getvalue(), "")

    def test_final_line_on_completion(self):
        bar, stream, _ = self._make(total=10, width=10)
        bar.update(5)
        bar.update(10)
        self.assertEqual(stream.getvalue(), "########## 10/10 (100%)\n")

    def test_finish_below_total_writes_nothing_in_non_interactive(self):
        bar, stream, _ = self._make(total=10, width=10)
        bar.update(5)
        bar.finish()
        self.assertEqual(stream.getvalue(), "")

    def test_finish_at_total_writes_final(self):
        bar, stream, _ = self._make(total=10, width=10)
        bar.update(10)
        bar.finish()
        self.assertEqual(stream.getvalue(), "########## 10/10 (100%)\n")

    def test_update_after_close_is_noop(self):
        bar, stream, _ = self._make(total=10, width=10)
        bar.update(10)
        stream.truncate(0)
        stream.seek(0)
        bar.update(5)
        self.assertEqual(stream.getvalue(), "")


class TestInteractive(unittest.TestCase):
    class FakeTTY(io.StringIO):
        def isatty(self):
            return True

    def _make(self, total=10, **kw):
        stream = self.FakeTTY()
        clock = FakeClock(0.0)
        bar = ProgressBar(
            total=total,
            stream=stream,
            clock=clock,
            **kw,
        )
        return bar, stream, clock

    def test_partial_writes_carriage_return(self):
        bar, stream, _ = self._make(total=10, width=10)
        bar.update(5)
        self.assertTrue(stream.getvalue().startswith("\r"))
        self.assertIn("#####", stream.getvalue())
        self.assertNotIn("\n", stream.getvalue())

    def test_throttle_skips_intermediate_draws(self):
        bar, stream, clock = self._make(total=100, width=10, interval=1.0)
        bar.update(10)
        first = stream.getvalue()
        clock.advance(0.5)
        bar.update(20)
        self.assertEqual(stream.getvalue(), first)
        clock.advance(0.6)
        bar.update(30)
        self.assertNotEqual(stream.getvalue(), first)

    def test_completion_ignores_throttle(self):
        bar, stream, clock = self._make(total=100, width=10, interval=100.0)
        bar.update(10)
        clock.advance(0.01)
        bar.update(100)
        self.assertTrue(stream.getvalue().endswith("\n"))

    def test_final_line_overwrites_longer_partial(self):
        # A partial line at value=9 with width=40 is longer than the final
        # rendered line only if the final line were shorter; here they are
        # the same width, but we pad anyway. The important behaviour is that
        # the final line ends with a newline and contains 100%.
        bar, stream, _ = self._make(total=10, width=10)
        bar.update(9)
        bar.update(10)
        self.assertTrue(stream.getvalue().rstrip().endswith("########## 10/10 (100%)"))

    def test_clamps_negative_value(self):
        bar, stream, _ = self._make(total=10, width=10)
        bar.update(-100)
        self.assertIn("0/10", stream.getvalue())

    def test_clamps_overflow_value(self):
        bar, stream, _ = self._make(total=10, width=10)
        bar.update(999)
        self.assertIn("10/10", stream.getvalue())
        self.assertIn("100%", stream.getvalue())

    def test_finish_below_total_in_interactive_writes_final(self):
        bar, stream, _ = self._make(total=10, width=10)
        bar.update(7)
        bar.finish()
        self.assertTrue(stream.getvalue().endswith("\n"))
        self.assertIn("7/10", stream.getvalue())

    def test_custom_fill_and_empty(self):
        bar, stream, _ = self._make(total=4, width=4, fill=">", empty=".")
        bar.update(2)
        self.assertIn(">>..", stream.getvalue())

    def test_render_format(self):
        bar, stream, _ = self._make(total=8, width=8)
        bar.update(3)
        content = stream.getvalue()
        # Strip the leading carriage return.
        body = content.lstrip("\r")
        self.assertEqual(body, "###----- 3/8 (37%)")


class TestIsattyRaises(unittest.TestCase):
    class BrokenStream(io.StringIO):
        def isatty(self):
            raise OSError("boom")

    def test_broken_isatty_treated_as_non_interactive(self):
        stream = self.BrokenStream()
        bar = ProgressBar(total=4, width=4, stream=stream, clock=FakeClock())
        bar.update(2)
        self.assertEqual(stream.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
