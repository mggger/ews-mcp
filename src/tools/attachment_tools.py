"""Attachment management tools for EWS MCP Server."""

from typing import Any, Dict, List
import base64
from pathlib import Path

from .base import BaseTool
from ..exceptions import ToolExecutionError
from ..utils import format_success_response, safe_get


class ListAttachmentsTool(BaseTool):
    """Tool for listing email attachments."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "list_attachments",
            "description": "List all attachments for a specific email message",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Email message ID"
                    },
                    "include_inline": {
                        "type": "boolean",
                        "description": "Include inline attachments (images embedded in email)",
                        "default": True
                    }
                },
                "required": ["message_id"]
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """List attachments for an email."""
        message_id = kwargs.get("message_id")
        include_inline = kwargs.get("include_inline", True)

        if not message_id:
            raise ToolExecutionError("message_id is required")

        try:
            # Find the message across common folders
            message = None
            folders_to_search = [
                self.ews_client.account.inbox,
                self.ews_client.account.sent,
                self.ews_client.account.drafts
            ]

            for folder in folders_to_search:
                try:
                    message = folder.get(id=message_id)
                    if message:
                        break
                except Exception:
                    continue

            if not message:
                raise ToolExecutionError(f"Message not found: {message_id}")

            # List attachments
            attachments = []
            if hasattr(message, 'attachments') and message.attachments:
                for attachment in message.attachments:
                    # Check if it's inline and whether to include it
                    is_inline = safe_get(attachment, 'is_inline', False)

                    if not include_inline and is_inline:
                        continue

                    attachment_info = {
                        "id": safe_get(attachment, 'attachment_id', {}).get('id', ''),
                        "name": safe_get(attachment, 'name', 'unnamed'),
                        "size": safe_get(attachment, 'size', 0),
                        "content_type": safe_get(attachment, 'content_type', 'application/octet-stream'),
                        "is_inline": is_inline,
                        "content_id": safe_get(attachment, 'content_id')
                    }
                    attachments.append(attachment_info)

            self.logger.info(f"Found {len(attachments)} attachment(s) for message {message_id}")

            return format_success_response(
                f"Found {len(attachments)} attachment(s)",
                message_id=message_id,
                attachments=attachments,
                count=len(attachments)
            )

        except ToolExecutionError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to list attachments: {e}")
            raise ToolExecutionError(f"Failed to list attachments: {e}")


class DownloadAttachmentTool(BaseTool):
    """Tool for downloading email attachments."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "download_attachment",
            "description": "Download an email attachment by message ID and attachment ID",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Email message ID"
                    },
                    "attachment_id": {
                        "type": "string",
                        "description": "Attachment ID (from list_attachments)"
                    },
                    "return_as": {
                        "type": "string",
                        "enum": ["base64", "file_path"],
                        "description": "Return format: base64 encoded string or file path",
                        "default": "base64"
                    },
                    "save_path": {
                        "type": "string",
                        "description": "File path to save attachment (required if return_as is 'file_path')"
                    }
                },
                "required": ["message_id", "attachment_id"]
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Download an attachment."""
        message_id = kwargs.get("message_id")
        attachment_id = kwargs.get("attachment_id")
        return_as = kwargs.get("return_as", "base64")
        save_path = kwargs.get("save_path")

        if not message_id:
            raise ToolExecutionError("message_id is required")

        if not attachment_id:
            raise ToolExecutionError("attachment_id is required")

        if return_as == "file_path" and not save_path:
            raise ToolExecutionError("save_path is required when return_as is 'file_path'")

        try:
            # Find the message across common folders
            message = None
            folders_to_search = [
                self.ews_client.account.inbox,
                self.ews_client.account.sent,
                self.ews_client.account.drafts
            ]

            for folder in folders_to_search:
                try:
                    message = folder.get(id=message_id)
                    if message:
                        break
                except Exception:
                    continue

            if not message:
                raise ToolExecutionError(f"Message not found: {message_id}")

            # Find the attachment
            attachment = None
            if hasattr(message, 'attachments') and message.attachments:
                for att in message.attachments:
                    att_id = safe_get(att, 'attachment_id', {})
                    if isinstance(att_id, dict):
                        att_id = att_id.get('id', '')

                    if str(att_id) == str(attachment_id):
                        attachment = att
                        break

            if not attachment:
                raise ToolExecutionError(f"Attachment not found: {attachment_id}")

            # Get attachment content
            content = safe_get(attachment, 'content', b'')
            if not content:
                raise ToolExecutionError("Attachment content is empty")

            attachment_name = safe_get(attachment, 'name', 'attachment')

            # Return based on format
            if return_as == "base64":
                # Encode content as base64
                content_b64 = base64.b64encode(content).decode('utf-8')

                self.logger.info(f"Downloaded attachment {attachment_name} ({len(content)} bytes)")

                return format_success_response(
                    "Attachment downloaded successfully",
                    message_id=message_id,
                    attachment_id=attachment_id,
                    name=attachment_name,
                    size=len(content),
                    content_type=safe_get(attachment, 'content_type', 'application/octet-stream'),
                    content_base64=content_b64
                )

            elif return_as == "file_path":
                # Save to file
                file_path = Path(save_path)

                # Create parent directories if they don't exist
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # Write content to file
                with open(file_path, 'wb') as f:
                    f.write(content)

                self.logger.info(f"Saved attachment {attachment_name} to {file_path}")

                return format_success_response(
                    "Attachment saved successfully",
                    message_id=message_id,
                    attachment_id=attachment_id,
                    name=attachment_name,
                    size=len(content),
                    content_type=safe_get(attachment, 'content_type', 'application/octet-stream'),
                    file_path=str(file_path)
                )

        except ToolExecutionError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to download attachment: {e}")
            raise ToolExecutionError(f"Failed to download attachment: {e}")
