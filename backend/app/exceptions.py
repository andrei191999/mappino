"""Custom exceptions for the Peppol Tools API."""

from fastapi import HTTPException, status


class PeppolAPIException(HTTPException):
    """Base exception for Peppol API errors."""

    def __init__(self, detail: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        super().__init__(status_code=status_code, detail=detail)


class ValidationError(PeppolAPIException):
    """Raised when validation fails due to invalid input."""

    def __init__(self, detail: str):
        super().__init__(detail=detail, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class TransformationError(PeppolAPIException):
    """Raised when XSLT transformation fails."""

    def __init__(self, detail: str):
        super().__init__(detail=detail, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class MapperNotFoundError(PeppolAPIException):
    """Raised when requested XSL mapper is not found."""

    def __init__(self, mapper_name: str):
        super().__init__(
            detail=f"Mapper not found: {mapper_name}",
            status_code=status.HTTP_404_NOT_FOUND
        )


class SchemeNotFoundError(PeppolAPIException):
    """Raised when ICD scheme is not found."""

    def __init__(self, icd: str):
        super().__init__(
            detail=f"Scheme not found: {icd}",
            status_code=status.HTTP_404_NOT_FOUND
        )


class LookupError(PeppolAPIException):
    """Raised when Peppol lookup fails."""

    def __init__(self, detail: str):
        super().__init__(detail=detail, status_code=status.HTTP_502_BAD_GATEWAY)


class ExternalServiceError(PeppolAPIException):
    """Raised when external service (Helger, Peppol Directory) fails."""

    def __init__(self, service: str, detail: str):
        super().__init__(
            detail=f"{service} service error: {detail}",
            status_code=status.HTTP_502_BAD_GATEWAY
        )


class XMLParseError(PeppolAPIException):
    """Raised when XML parsing fails."""

    def __init__(self, detail: str):
        super().__init__(detail=f"XML parse error: {detail}", status_code=status.HTTP_400_BAD_REQUEST)
