"""Repository pattern abstractions for database entities."""


class ReportRepository:
    """CRUD operations for Report entities."""

    def create(self) -> None:  # noqa: B027
        """Create a new report record."""
        raise NotImplementedError

    def get(self, report_id: int) -> None:
        """Retrieve a report by primary key."""
        raise NotImplementedError

    def list_all(self) -> list[object]:
        """Return all reports."""
        raise NotImplementedError

    def delete(self, report_id: int) -> None:  # noqa: B027
        """Delete a report by primary key."""
        raise NotImplementedError
