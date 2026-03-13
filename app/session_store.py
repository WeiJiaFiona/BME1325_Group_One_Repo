from app.schemas import SessionContext


class MemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionContext] = {}

    def save(self, context: SessionContext) -> None:
        self._sessions[context.session_id] = context

    def get(self, session_id: str) -> SessionContext | None:
        return self._sessions.get(session_id)

    def all(self) -> dict[str, SessionContext]:
        return dict(self._sessions)


session_store = MemorySessionStore()

