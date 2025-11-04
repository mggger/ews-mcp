"""Base class for all MCP tools."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Type
from pydantic import BaseModel, ValidationError as PydanticValidationError
import logging

from ..ews_client import EWSClient
from ..exceptions import ValidationError, ToolExecutionError
from ..utils import format_error_response


class BaseTool(ABC):
    """Base class for all MCP tools."""

    def __init__(self, ews_client: EWSClient):
        self.ews_client = ews_client
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Return tool schema for MCP registration."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute tool operation."""
        pass

    def validate_input(self, model: Type[BaseModel], **kwargs) -> BaseModel:
        """Validate input using Pydantic model."""
        try:
            return model(**kwargs)
        except PydanticValidationError as e:
            self.logger.error(f"Validation error: {e}")
            raise ValidationError(f"Invalid input: {e}")

    async def safe_execute(self, **kwargs) -> Dict[str, Any]:
        """Execute with error handling."""
        try:
            return await self.execute(**kwargs)
        except ValidationError as e:
            return format_error_response(e, "Validation failed")
        except ToolExecutionError as e:
            return format_error_response(e, "Execution failed")
        except Exception as e:
            self.logger.exception("Unexpected error in tool execution")
            return format_error_response(e, "Unexpected error")
