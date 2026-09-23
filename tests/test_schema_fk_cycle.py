"""Regression: drop_all must not warn about the alerts<->footprint_entries FK cycle (Bug E1).

models.py defines FootprintEntry.alert_id -> alerts.id AND
alerts.footprint_entry_id -> footprint_entries.id. SQLAlchemy cannot sort the
DROP order for that cycle on backends without ALTER support, raising an
SAWarning (and failing under -W error) at session teardown.
"""
import warnings

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SAWarning

from fusion_server.db.models import Base


def test_drop_all_without_cycle_warning():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    with warnings.catch_warnings():
        warnings.simplefilter("error", SAWarning)
        Base.metadata.drop_all(bind=engine)
