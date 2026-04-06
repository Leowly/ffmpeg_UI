# backend/app/core/exceptions.py


class FileProcessingError(Exception):
    def __init__(self, detail: str = ""):
        self.detail = detail
        super().__init__(detail)


class ResourceNotFoundError(Exception):
    def __init__(self, detail: str = ""):
        self.detail = detail
        super().__init__(detail)
