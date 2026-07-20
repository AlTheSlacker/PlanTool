import pytest

from engine.references import ReferenceService
from engine.rows import RowService
from engine.storage import Storage


@pytest.fixture
def store(tmp_path):
    storage = Storage(tmp_path)
    storage.init_plan("test plan", "standard")
    yield storage
    storage.close()


@pytest.fixture
def rows(store):
    return RowService(store)


@pytest.fixture
def refs(store, rows):
    return ReferenceService(store, rows)


PAPER = """A Study of Widget Settling

Abstract
We measure widget settling behaviour under load.

Introduction
Widgets have long been assumed to settle quickly.

Methods
We applied a step input and recorded the response with a high-
speed camera at 10 kHz.

Results
The measured settling time was 40 ms under nominal load.
Peak overshoot reached 12 percent.

Limitations
All measurements were taken at room temperature. Behaviour above
60 C was not characterised and should not be extrapolated.

Conclusion
Widgets settle in 40 ms.
"""
