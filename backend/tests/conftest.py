"""
Pytest fixtures for MemoFlow V3 tests.
Provides an in-memory SQLite session for fast, isolated tests.
"""

import pytest
from sqlmodel import SQLModel, Session, create_engine

from app.models import Deck, Source, Block  # noqa: F401 — ensure models are registered


@pytest.fixture()
def engine():
    """Create a fresh in-memory SQLite engine for each test."""
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    """Provide a session bound to the in-memory engine."""
    with Session(engine) as sess:
        yield sess


@pytest.fixture()
def seed_deck(session):
    """Create a default Deck and return it."""
    deck = Deck(name="Test", path="Test")
    session.add(deck)
    session.commit()
    session.refresh(deck)
    return deck


@pytest.fixture()
def seed_source(session, seed_deck):
    """Create a Source under the seed Deck and return it."""
    source = Source(
        title="Test Source",
        content_hash="abc123",
        original_text="some text",
        source_type="text",
        deck_id=seed_deck.id,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


@pytest.fixture()
def seed_blocks(session, seed_source):
    """Create 3 Blocks under the seed Source and return them."""
    blocks = []
    for i in range(1, 4):
        b = Block(
            source_id=seed_source.id,
            sequence_number=i,
            content=f"Answer {i}",
            quiz=f"Question {i}",
        )
        session.add(b)
        blocks.append(b)
    session.commit()
    for b in blocks:
        session.refresh(b)
    return blocks
