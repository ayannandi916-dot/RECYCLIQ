import pytest

from app.database import dependencies

class MockDBSession:
    def __init__(self):
        self.closed = False
        self.rolled_back = False

    def close(self):
        self.closed = True

    def rollback(self):
        self.rolled_back = True



# 1. Database session is created and yielded
def test_get_db_yields_session(monkeypatch):

    mock_db = MockDBSession()

    monkeypatch.setattr(
        dependencies,
        "SessionLocal",
        lambda: mock_db
    )

    generator = dependencies.get_db()

    db = next(generator)

    assert db is mock_db
    assert mock_db.closed is False

    generator.close()

    assert mock_db.closed is True


# 2. Database session closes after normal execution
def test_get_db_closes_session(monkeypatch):

    mock_db = MockDBSession()

    monkeypatch.setattr(
        dependencies,
        "SessionLocal",
        lambda: mock_db
    )

    generator = dependencies.get_db()

    next(generator)

    with pytest.raises(StopIteration):
        next(generator)

    assert mock_db.closed is True
    

# 3. Database session closes when an exception occurs
def test_get_db_closes_session_on_exception(monkeypatch):

    mock_db = MockDBSession()

    monkeypatch.setattr(
        dependencies,
        "SessionLocal",
        lambda: mock_db
    )

    generator = dependencies.get_db()

    next(generator)

    with pytest.raises(RuntimeError):
        generator.throw(RuntimeError("Database operation failed"))

    assert mock_db.closed is True
    assert mock_db.rolled_back is True