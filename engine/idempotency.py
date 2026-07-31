"""The only place the engine builds an idempotency key.

`decisions:43` — a replayed key returns the original receipt and never duplicates. That
mechanism only works if the key answers the question it exists to answer: **is this the
same operation I already performed?**

**What went wrong, and why it took a whole build to notice.** Twenty-one call sites built
their key by hand as a formatted string, and every one of them appended `now()`. The
timestamp was there to make each key unique — which cancels the only thing the key does.
A key that is never the same twice can never detect a repeat, so `write_atomic`'s replay
path was unreachable from most of the engine, and the guarantee `decisions:43` describes
was being carried by a string that guaranteed the opposite.

The bug survived because the clock hid it. On Windows the system clock updates about every
16 milliseconds: `now()` called 2000 times in a loop returned the *same* value 2000 times.
So the timestamp did not even deliver the uniqueness it was added for — two operations
inside one tick collided, the second was treated as a replay, wrote nothing, and returned
the first one's receipt reporting success. Silent wrong answer, surfacing as an
intermittent test failure that got more frequent as the code got faster.

**Nobody copied a mistake.** Twenty-one authors each independently did the obvious thing at
the point of least attention. That is the signature of a missing owner, and it is the same
signature as eight spellings of `created_at` (F27) and six differently-named parent foreign
keys asserting one relation (F28). Duplication first; the wrong idea second.

**So the rule is enforced here rather than stated.** `key()` refuses a timestamp element
outright, and `tests/test_idempotency.py` refuses a hand-built key literal anywhere in
`engine/`. Whether a value *is* a timestamp is asked of `engine/clock.py`, which already
owns that question — this module does not get its own date regex, for exactly the reason
it exists.

**How to choose the elements.** Name *what* is being done, never *when*. Almost always the
answer is already in the data:

- composing a brief -> the task and its serve count
- finalizing -> the plan and its version
- a state-machine event -> the entity and the target state

Where a caller legitimately repeats an operation with no natural discriminator, give it one
that means something — a supersession count, an attempt number — rather than reaching for
the clock. If a caller genuinely cannot distinguish two attempts, they *are* the same
operation, and collapsing them is correct behaviour rather than a bug to route around.
"""

from __future__ import annotations

from datetime import datetime

from engine.clock import is_storage_form

#: Separator between key elements. Elements are `str()`-ed, so this must not appear inside one, or
#: two different operations could spell the same key — the failure this module prevents,
#: arriving through the back door.
SEPARATOR = ":"


class InvalidIdempotencyKey(ValueError):
    """A key was built from something that cannot identify an operation."""


def key(operation: str, *subjects: object) -> str:
    """The idempotency key naming one operation.

    `operation` is the verb (`compose`, `finalize`, `register_spike`); `subjects` identify
    which one. Two calls describing the same operation must produce the same key — that is
    the entire contract, and it is why a timestamp is refused rather than discouraged.
    """
    if not operation or not operation.strip():
        raise InvalidIdempotencyKey("an idempotency key needs an operation name")

    rendered = [operation.strip()]
    for subject in subjects:
        if subject is None:
            # An explicit absence is a fact about the operation — a plan-level
            # attachment has no scope key — and it must still occupy its position, or
            # `("a", None, "b")` and `("a", "b")` would spell the same key. `""` stays
            # refused: an empty string is what a failed lookup returns, and None is
            # something a caller has to write on purpose.
            rendered.append("none")
            continue
        if isinstance(subject, datetime):
            raise InvalidIdempotencyKey(
                f"{operation!r}: a timestamp cannot identify an operation. A key built "
                "from the clock is never equal to itself, so a repeat is never detected "
                "— name what the operation acts on instead (see this module's docstring)"
            )
        text = str(subject).strip()
        if not text:
            raise InvalidIdempotencyKey(
                f"{operation!r}: an empty key element cannot identify anything; a missing "
                "id silently merges two operations into one"
            )
        if is_storage_form(text):
            raise InvalidIdempotencyKey(
                f"{operation!r}: {text!r} is a timestamp. A key built from the clock is "
                "never equal to itself, so a repeat is never detected — name what the "
                "operation acts on instead (see this module's docstring)"
            )
        if SEPARATOR in text and len(subjects) > 1:
            # One element containing the separator can impersonate two. Refs
            # (`contracts:40`) are the legitimate exception and are passed alone or as the
            # only such element, so this only fires on genuinely ambiguous keys.
            rendered.append(text.replace(SEPARATOR, "_"))
            continue
        rendered.append(text)
    return SEPARATOR.join(rendered)


# A `within()` helper stood here, building a key from a time bucket so that repeats
# inside a window collapsed to one. It was never called by the engine. Deleted
# 2026-07-22: a time window is a guess about how fast a caller might legitimately
# retry, and a key that changes on its own schedule detects a repeat or misses one
# depending on where the clock happened to fall. If an operation has no natural
# discriminator, find the flag the data already carries — do not invent a window.
