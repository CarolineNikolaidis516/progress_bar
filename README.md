# progress_bar

A progress bar for Python that writes nothing when stdout is redirected to a file or pipe, and animates normally on a TTY.

```python
from progress_bar import ProgressBar

bar = ProgressBar(total=100, width=40)
for i in range(100):
    bar.update(i + 1)
bar.finish()
```

## Why

Progress bars are useful on a terminal and garbage in a log file. Most libraries either unconditionally emit carriage-return animation (so `python script.py > log.txt` produces megabytes of `\r` noise) or require the caller to detect redirection themselves. This library does the detection once at construction time via `os.isatty(stream)` and stays silent until completion when stdout is not a TTY. The trade-off: a redirected run gets exactly one summary line at the end instead of live progress, which is the right thing for logs.

## Edge cases

- `update()` clamps values below 0 and above `total` rather than raising. If you need strict bounds checking, validate before calling.
- Completion (`value >= total`) bypasses the draw-interval throttle so the final line is always written promptly. This means the clock never delays completion.
- A stream whose `isatty()` raises is treated as non-interactive. This keeps the bar from crashing on exotic stream wrappers.
- Detection happens at construction. If you swap `sys.stdout` after creating the bar, the bar keeps its original mode.

## Exported names

`ProgressBar` — the only public class. Constructor arguments: `total`, `width=40`, `fill="#"`, `empty="-"`, `stream=None` (defaults to `sys.stdout`), `interval=0.1` (minimum seconds between interactive redraws), `clock=None` (a zero-arg callable returning a float; defaults to `time.monotonic`). Methods: `update(value)`, `finish()`.

## Tests

```
PYTHONPATH=src python -m unittest discover -s tests
```
