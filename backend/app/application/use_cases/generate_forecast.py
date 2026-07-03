from ...domain.entities.forecast import ForecastInput, ForecastResult
from ...domain.repositories.forecast_repository import ForecastRepository
from ...domain.services.forecast_service import ForecastService


class GenerateForecastUseCase:
    def __init__(self, service: ForecastService, repository: ForecastRepository) -> None:
        self._service = service
        self._repository = repository

    def execute(self, data: ForecastInput) -> ForecastResult:
        result = self._service.predict(data)
        self._repository.save(result)
        return result
