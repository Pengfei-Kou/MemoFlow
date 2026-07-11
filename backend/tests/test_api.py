"""
API integration tests using FastAPI TestClient + in-memory SQLite.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_session
from app.models import Deck, Source, Block  # noqa: F401
import app.database as db_module


@pytest.fixture()
def client():
    """
    Provide a TestClient wired to an in-memory SQLite database.
    Overrides both the engine (for lifespan create_all) and the session dependency.
    """
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Patch the module-level engine so create_db_and_tables uses our test engine
    original_engine = db_module.engine
    db_module.engine = test_engine

    def _override_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as c:
        yield c, test_engine

    app.dependency_overrides.clear()
    db_module.engine = original_engine


def _seed_data(engine):
    """Insert a Deck + Source + 2 Blocks for review tests."""
    with Session(engine) as session:
        deck = Deck(name="Test", path="Test")
        session.add(deck)
        session.flush()

        source = Source(
            title="Test Source",
            content_hash="hash123",
            original_text="some text",
            source_type="text",
            deck_id=deck.id,
        )
        session.add(source)
        session.flush()

        for i in range(1, 3):
            block = Block(
                source_id=source.id,
                sequence_number=i,
                content=f"Answer {i}",
                quiz=f"Question {i}",
            )
            session.add(block)

        session.commit()
        return deck.id, source.id


class TestDecksAPI:
    """Tests for /api/decks endpoints."""

    def test_create_deck(self, client):
        c, _ = client
        resp = c.post("/api/decks", json={
            "name": "English",
            "parser_config": {"strategy": "sentence_en_zh", "source_lang": "English", "target_lang": "Chinese"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "English"
        assert data["path"] == "English"
        assert data["id"] is not None

    def test_list_decks(self, client):
        c, _ = client
        c.post("/api/decks", json={"name": "A"})
        c.post("/api/decks", json={"name": "B"})
        resp = c.get("/api/decks")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_delete_deck(self, client):
        c, _ = client
        create_resp = c.post("/api/decks", json={"name": "ToDelete"})
        deck_id = create_resp.json()["id"]
        resp = c.delete(f"/api/decks/{deck_id}")
        assert resp.status_code == 200
        # Confirm it's gone
        resp2 = c.get(f"/api/decks/{deck_id}")
        assert resp2.status_code == 404

    def test_delete_nonexistent_deck(self, client):
        c, _ = client
        resp = c.delete("/api/decks/99999")
        assert resp.status_code == 404


class TestReviewAPI:
    """Tests for /api/review endpoints."""

    def test_next_review_empty(self, client):
        """No cards → block is None."""
        c, _ = client
        resp = c.get("/api/review/next")
        assert resp.status_code == 200
        data = resp.json()
        assert data["block"] is None
        assert data["remaining"] == 0

    def test_next_review_with_new_cards(self, client):
        """Seeded new cards (no next_review) should appear as new."""
        c, engine = client
        _seed_data(engine)
        resp = c.get("/api/review/next")
        assert resp.status_code == 200
        data = resp.json()
        assert data["block"] is not None
        assert data["is_new"] is True

    def test_submit_review(self, client):
        """Submit a review and check schedule updates + review log append."""
        c, engine = client
        _seed_data(engine)

        # Get a card first
        next_resp = c.get("/api/review/next")
        block_id = next_resp.json()["block"]["id"]

        # Submit review with quality=5 (Easy)
        resp = c.post(f"/api/review/{block_id}", json={"quality": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_interval"] >= 0  # 具体间隔由调度算法（FSRS/SM-2）决定
        assert data["next_review"] is not None

        # 追加式复习日志应落表
        from sqlmodel import select
        from app.models import ReviewLog
        with Session(engine) as session:
            logs = session.exec(
                select(ReviewLog).where(ReviewLog.block_id == block_id)
            ).all()
        assert len(logs) == 1
        assert logs[0].quality == 5

    def test_submit_review_nonexistent(self, client):
        c, _ = client
        resp = c.post("/api/review/99999", json={"quality": 5})
        assert resp.status_code == 404


class TestSourcesAPI:
    """Tests for /api/sources endpoints."""

    def test_delete_source_cascade(self, client):
        """Deleting a source should cascade-delete its blocks."""
        c, engine = client
        _, source_id = _seed_data(engine)

        # Verify blocks exist
        resp = c.get("/api/blocks")
        assert len(resp.json()) == 2

        # Delete source
        resp = c.delete(f"/api/sources/{source_id}")
        assert resp.status_code == 200

        # Blocks should be gone
        resp = c.get("/api/blocks")
        assert len(resp.json()) == 0

    def test_list_sources(self, client):
        c, engine = client
        _seed_data(engine)
        resp = c.get("/api/sources")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestBlocksAPI:
    """Tests for /api/blocks endpoints."""

    def test_list_blocks(self, client):
        c, engine = client
        _seed_data(engine)
        resp = c.get("/api/blocks")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_update_block(self, client):
        c, engine = client
        _seed_data(engine)
        blocks = c.get("/api/blocks").json()
        block_id = blocks[0]["id"]

        resp = c.put(f"/api/blocks/{block_id}", json={"content": "Updated Answer"})
        assert resp.status_code == 200
        assert resp.json()["content"] == "Updated Answer"

    def test_delete_block(self, client):
        c, engine = client
        _seed_data(engine)
        blocks = c.get("/api/blocks").json()
        block_id = blocks[0]["id"]

        resp = c.delete(f"/api/blocks/{block_id}")
        assert resp.status_code == 200

        # Should have one less block
        remaining = c.get("/api/blocks").json()
        assert len(remaining) == 1


class TestStatsAPI:
    """Tests for /api/stats endpoints."""

    def test_stats_empty(self, client):
        c, _ = client
        resp = c.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_stats_with_data(self, client):
        c, engine = client
        _seed_data(engine)
        resp = c.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["new"] == 2  # no reviews yet → all new

    def test_history(self, client):
        c, _ = client
        resp = c.get("/api/stats/history?days=7")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestHealthAPI:
    """Tests for /api/health endpoint."""

    def test_health(self, client):
        c, _ = client
        resp = c.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"


class TestTodaySummaryAPI:
    """Tests for /api/stats/today endpoint."""

    def test_today_empty(self, client):
        c, _ = client
        resp = c.get("/api/stats/today")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"reviewed": 0, "again": 0, "retention": None}

    def test_today_after_reviews(self, client):
        c, engine = client
        _seed_data(engine)
        ids = [b["id"] for b in c.get("/api/blocks").json()]
        c.post(f"/api/review/{ids[0]}", json={"quality": 4})
        c.post(f"/api/review/{ids[1]}", json={"quality": 1})
        data = c.get("/api/stats/today").json()
        assert data["reviewed"] == 2
        assert data["again"] == 1
        assert data["retention"] == 0.5
