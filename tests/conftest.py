import pytest

from engine.briefs import BriefComposer
from engine.catalogue import CatalogueService
from engine.conflicts import ConflictService
from engine.behaviours import BehaviourService
from engine.findings import FindingService
from engine.gaps import GapEngine
from engine.gates import GateEngine
from engine.graph import LinkGraph
from engine.references import ReferenceService
from engine.attachments import AttachmentService
from engine.rows import RowService
from engine.storage import Storage
from engine.tasks import TaskGraphService
from engine.validation import ValidationService
from engine.warnings import WarningService


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
def conflicts(store, rows):
    return ConflictService(store, rows)


@pytest.fixture
def warns(store):
    return WarningService(store)


@pytest.fixture
def gate(store, rows, conflicts, warns, findings):
    return GateEngine(
        store, rows, conflicts, warns, gaps=GapEngine(store, rows), findings=findings
    )


@pytest.fixture
def refs(store, rows):
    return ReferenceService(store, rows)


@pytest.fixture
def graph(store):
    return LinkGraph(store)


@pytest.fixture
def validation(store, rows, graph, conflicts):
    return ValidationService(store, rows, graph, conflicts)


@pytest.fixture
def findings(store, rows):
    return FindingService(store, rows)


@pytest.fixture
def tasks(store, rows, graph, findings):
    return TaskGraphService(store, rows, graph=graph, findings=findings)


@pytest.fixture
def attachments(store, rows):
    return AttachmentService(store, rows)


@pytest.fixture
def behaviours(store):
    return BehaviourService(store)


@pytest.fixture
def briefs(store, tasks, graph, attachments):
    return BriefComposer(store, tasks, graph=graph, attachments=attachments)


@pytest.fixture
def catalogue(store, rows):
    return CatalogueService(store, rows)


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
