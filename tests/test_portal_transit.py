from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

if QApplication.instance() is None:
    QApplication([])

from desktop_pet.pet.portal_transit import PortalTransit
from desktop_pet.pet.window import PetWindow


def test_portal_transforms_payload_and_calls_midpoint_before_finished():
    pet = PetWindow("xiaofeixue")
    events = []
    assert pet.begin_portal_departure(
        {"kind": "file", "label": "brief.md", "stage": "received"},
        lambda: events.append("midpoint"), lambda: events.append("finished"),
    )

    pet._advance_portal(PortalTransit("departure").duration)

    assert events == ["midpoint", "finished"]
    assert pet._portal is None
    assert pet._work_item["label"] == "brief.md"


def test_cancelled_portal_does_not_run_stale_callbacks():
    pet = PetWindow("xiaofeixue")
    events = []
    assert pet.begin_portal_departure({"label": "old"}, lambda: events.append("old"), events.append)
    pet.cancel_portal()
    assert pet.begin_portal_arrival({"label": "new"}, lambda: events.append("new"))

    pet._advance_portal(PortalTransit("arrival").duration)

    assert events == ["new"]


def test_portal_direction_has_inverse_scale_progression():
    departure = PortalTransit("departure")
    arrival = PortalTransit("arrival")

    assert departure.transform(0.2)[0] > departure.transform(0.8)[0]
    assert arrival.transform(0.2)[0] < arrival.transform(0.8)[0]
