from domain.models import DashboardSummary
from repositories.interfaces import IDashboardRepository


class DashboardService:
    """Business logic layer TASK-B — tipis (cuma passthrough) karena semua
    agregasi berat sudah dilakukan di level SQL (DashboardRepository), bukan
    di-loop ulang di Python."""

    def __init__(self, dashboard_repository: IDashboardRepository):
        self._repo = dashboard_repository

    def get_summary(self) -> DashboardSummary:
        return self._repo.get_summary()
