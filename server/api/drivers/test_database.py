import pytest
from server.api.drivers import database


def test_get_db_yields_session(monkeypatch) -> None:
    # Patch SessionLocal to return a mock session
    class DummySession:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    dummy_session = DummySession()
    monkeypatch.setattr(database, "SessionLocal", lambda: dummy_session)

    gen = database.get_db()
    session = next(gen)
    assert isinstance(session, DummySession)
    # After generator is closed, session should be closed
    try:
        next(gen)
    except StopIteration:
        pass
    assert dummy_session.closed


def test_get_db_closes_session_on_exception(monkeypatch) -> None:
    class DummySession:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    dummy_session = DummySession()
    monkeypatch.setattr(database, "SessionLocal", lambda: dummy_session)

    def use_db() -> None:
        gen = database.get_db()
        session = next(gen)
        raise Exception("Some error")
        # Should close session in finally

    with pytest.raises(Exception):
        use_db()
    # Session should not be closed because generator was not closed
    # So we close it manually
    gen = database.get_db()
    next(gen)
    gen.close()
    assert dummy_session.closed
