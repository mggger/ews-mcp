"""Email operation tools for EWS MCP Server."""

from typing import Any, Dict, List
from datetime import datetime
from exchangelib import Message, Mailbox, FileAttachment, HTMLBody
from exchangelib.queryset import Q

from .base import BaseTool
from ..models import SendEmailRequest, EmailSearchRequest, EmailDetails
from ..exceptions import ToolExecutionError
from ..utils import format_success_response, safe_get, truncate_text, parse_datetime_tz_aware


class SendEmailTool(BaseTool):
    """Tool for sending emails."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "send_email",
            "description": "Send an email through Exchange with optional attachments and CC/BCC",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Recipient email addresses"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body (HTML supported)"
                    },
                    "cc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "CC recipients (optional)"
                    },
                    "bcc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "BCC recipients (optional)"
                    },
                    "importance": {
                        "type": "string",
                        "enum": ["Low", "Normal", "High"],
                        "description": "Email importance level (optional)"
                    },
                    "attachments": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Attachment file paths (optional)"
                    }
                },
                "required": ["to", "subject", "body"]
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Send email via EWS."""
        # Validate input
        request = self.validate_input(SendEmailRequest, **kwargs)

        try:
            # Create message
            message = Message(
                account=self.ews_client.account,
                subject=request.subject,
                body=HTMLBody(request.body),
                to_recipients=[Mailbox(email_address=email) for email in request.to]
            )

            # Add CC recipients
            if request.cc:
                message.cc_recipients = [Mailbox(email_address=email) for email in request.cc]

            # Add BCC recipients
            if request.bcc:
                message.bcc_recipients = [Mailbox(email_address=email) for email in request.bcc]

            # Set importance
            message.importance = request.importance.value

            # Add attachments if provided (must save before sending when attachments are present)
            if request.attachments:
                for file_path in request.attachments:
                    try:
                        with open(file_path, 'rb') as f:
                            content = f.read()
                            attachment = FileAttachment(
                                name=file_path.split('/')[-1],
                                content=content
                            )
                            message.attach(attachment)
                    except Exception as e:
                        self.logger.warning(f"Failed to attach file {file_path}: {e}")

                # Save message with attachments first (required for attachments to be included)
                message.save()
                # Then send
                message.send()
            else:
                # Send directly if no attachments
                message.send()
            self.logger.info(f"Email sent successfully to {', '.join(request.to)}")

            return format_success_response(
                "Email sent successfully",
                message_id=message.id if hasattr(message, 'id') else None,
                sent_time=datetime.now().isoformat(),
                recipients=request.to
            )

        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            raise ToolExecutionError(f"Failed to send email: {e}")


class ReadEmailsTool(BaseTool):
    """Tool for reading emails from inbox."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "read_emails",
            "description": "Read emails from a specified folder (default: inbox)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "description": "Folder name (inbox, sent, drafts, etc.)",
                        "default": "inbox"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of emails to retrieve",
                        "default": 50,
                        "maximum": 1000
                    },
                    "unread_only": {
                        "type": "boolean",
                        "description": "Only return unread emails",
                        "default": False
                    }
                }
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Read emails from folder."""
        folder_name = kwargs.get("folder", "inbox").lower()
        max_results = kwargs.get("max_results", 50)
        unread_only = kwargs.get("unread_only", False)

        try:
            # Get folder
            folder_map = {
                "inbox": self.ews_client.account.inbox,
                "sent": self.ews_client.account.sent,
                "drafts": self.ews_client.account.drafts,
                "deleted": self.ews_client.account.trash,
                "junk": self.ews_client.account.junk
            }

            folder = folder_map.get(folder_name, self.ews_client.account.inbox)

            # Build query
            items = folder.all().order_by('-datetime_received')

            if unread_only:
                items = items.filter(is_read=False)

            # Fetch emails
            emails = []
            for item in items[:max_results]:
                # Get sender email safely
                sender = safe_get(item, "sender", None)
                from_email = ""
                if sender and hasattr(sender, "email_address"):
                    from_email = sender.email_address or ""

                # Get text body safely
                text_body = safe_get(item, "text_body", "") or ""

                email_data = {
                    "message_id": safe_get(item, "id", "unknown"),
                    "subject": safe_get(item, "subject", "") or "",
                    "from": from_email,
                    "received_time": safe_get(item, "datetime_received", datetime.now()).isoformat(),
                    "is_read": safe_get(item, "is_read", False),
                    "has_attachments": safe_get(item, "has_attachments", False),
                    "preview": truncate_text(text_body, 200)
                }
                emails.append(email_data)

            self.logger.info(f"Retrieved {len(emails)} emails from {folder_name}")

            return format_success_response(
                f"Retrieved {len(emails)} emails",
                emails=emails,
                total_count=len(emails),
                folder=folder_name
            )

        except Exception as e:
            self.logger.error(f"Failed to read emails: {e}")
            raise ToolExecutionError(f"Failed to read emails: {e}")


class SearchEmailsTool(BaseTool):
    """Tool for searching emails with filters."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "search_emails",
            "description": "Search emails with various filters (subject, sender, date range, etc.)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "description": "Folder to search in",
                        "default": "inbox"
                    },
                    "subject_contains": {
                        "type": "string",
                        "description": "Filter by subject containing text"
                    },
                    "from_address": {
                        "type": "string",
                        "description": "Filter by sender email address"
                    },
                    "has_attachments": {
                        "type": "boolean",
                        "description": "Filter by attachment presence"
                    },
                    "is_read": {
                        "type": "boolean",
                        "description": "Filter by read status"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date (ISO 8601 format)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date (ISO 8601 format)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 50,
                        "maximum": 1000
                    }
                }
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Search emails with filters."""
        from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
        from exchangelib.errors import ErrorTimeoutExpired
        import socket

        try:
            # Warn if no date range provided
            if not kwargs.get("start_date") and not kwargs.get("end_date"):
                self.logger.warning(
                    "Searching without date range may be slow for large mailboxes. "
                    "Consider adding start_date/end_date for better performance."
                )

            # Get folder
            folder_name = kwargs.get("folder", "inbox").lower()
            folder_map = {
                "inbox": self.ews_client.account.inbox,
                "sent": self.ews_client.account.sent,
                "drafts": self.ews_client.account.drafts,
                "deleted": self.ews_client.account.trash
            }
            folder = folder_map.get(folder_name, self.ews_client.account.inbox)

            # Build query
            query = folder.all()

            # Apply filters
            if kwargs.get("subject_contains"):
                query = query.filter(subject__contains=kwargs["subject_contains"])

            if kwargs.get("from_address"):
                query = query.filter(sender=kwargs["from_address"])

            if kwargs.get("has_attachments") is not None:
                query = query.filter(has_attachments=kwargs["has_attachments"])

            if kwargs.get("is_read") is not None:
                query = query.filter(is_read=kwargs["is_read"])

            if kwargs.get("start_date"):
                start = parse_datetime_tz_aware(kwargs["start_date"])
                query = query.filter(datetime_received__gte=start)

            if kwargs.get("end_date"):
                end = parse_datetime_tz_aware(kwargs["end_date"])
                query = query.filter(datetime_received__lte=end)

            # Order and limit
            query = query.order_by('-datetime_received')
            max_results = kwargs.get("max_results", 50)

            # Retry wrapper for EWS query execution
            @retry(
                stop=stop_after_attempt(2),
                wait=wait_exponential(multiplier=2, min=4, max=10),
                retry=retry_if_exception_type((ErrorTimeoutExpired, socket.timeout))
            )
            def execute_query():
                """Execute EWS query with retry logic."""
                results = []
                for item in query[:max_results]:
                    # Get sender email safely
                    sender = safe_get(item, "sender", None)
                    from_email = ""
                    if sender and hasattr(sender, "email_address"):
                        from_email = sender.email_address or ""

                    # Get text body safely
                    text_body = safe_get(item, "text_body", "") or ""

                    email_data = {
                        "message_id": safe_get(item, "id", "unknown"),
                        "subject": safe_get(item, "subject", "") or "",
                        "from": from_email,
                        "received_time": safe_get(item, "datetime_received", datetime.now()).isoformat(),
                        "is_read": safe_get(item, "is_read", False),
                        "has_attachments": safe_get(item, "has_attachments", False),
                        "preview": truncate_text(text_body, 200)
                    }
                    results.append(email_data)
                return results

            # Execute with retry
            emails = execute_query()

            self.logger.info(f"Found {len(emails)} emails matching search criteria")

            return format_success_response(
                f"Found {len(emails)} matching emails",
                emails=emails,
                total_count=len(emails)
            )

        except (ErrorTimeoutExpired, socket.timeout) as e:
            self.logger.error(f"Search timed out: {e}")
            # Provide helpful error message with suggestions
            error_msg = (
                f"Search timed out. Try these optimizations:\n"
                f"1. Add a date range (start_date and end_date)\n"
                f"2. Reduce max_results (currently {kwargs.get('max_results', 50)})\n"
                f"3. Add more specific filters\n"
                f"4. Increase REQUEST_TIMEOUT in .env (current: {self.ews_client.config.request_timeout}s)\n"
                f"Example: search_emails(subject_contains='Re: xxx', start_date='2024-11-01', max_results=20)"
            )
            raise ToolExecutionError(error_msg)
        except Exception as e:
            self.logger.error(f"Failed to search emails: {e}")
            raise ToolExecutionError(f"Failed to search emails: {e}")


class GetEmailDetailsTool(BaseTool):
    """Tool for getting full email details."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "get_email_details",
            "description": "Get full details of a specific email by ID",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Email message ID"
                    }
                },
                "required": ["message_id"]
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Get email details."""
        message_id = kwargs.get("message_id")

        try:
            # Find message
            item = self.ews_client.account.inbox.get(id=message_id)

            # Get sender email safely
            sender = safe_get(item, "sender", None)
            from_email = ""
            if sender and hasattr(sender, "email_address"):
                from_email = sender.email_address or ""

            # Get recipients safely
            to_recipients = safe_get(item, "to_recipients", []) or []
            to_emails = [r.email_address for r in to_recipients if r and hasattr(r, "email_address") and r.email_address]

            cc_recipients = safe_get(item, "cc_recipients", []) or []
            cc_emails = [r.email_address for r in cc_recipients if r and hasattr(r, "email_address") and r.email_address]

            # Get attachments safely
            attachments = safe_get(item, "attachments", []) or []
            attachment_names = [att.name for att in attachments if att and hasattr(att, "name") and att.name]

            email_details = {
                "message_id": safe_get(item, "id", "unknown"),
                "subject": safe_get(item, "subject", "") or "",
                "from": from_email,
                "to": to_emails,
                "cc": cc_emails,
                "body": safe_get(item, "text_body", "") or "",
                "body_html": str(safe_get(item, "body", "") or ""),
                "received_time": safe_get(item, "datetime_received", datetime.now()).isoformat(),
                "sent_time": safe_get(item, "datetime_sent", datetime.now()).isoformat(),
                "is_read": safe_get(item, "is_read", False),
                "has_attachments": safe_get(item, "has_attachments", False),
                "importance": safe_get(item, "importance", "Normal") or "Normal",
                "attachments": attachment_names
            }

            return format_success_response(
                "Email details retrieved",
                email=email_details
            )

        except Exception as e:
            self.logger.error(f"Failed to get email details: {e}")
            raise ToolExecutionError(f"Failed to get email details: {e}")


class DeleteEmailTool(BaseTool):
    """Tool for deleting emails."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "delete_email",
            "description": "Delete an email by ID (moves to trash)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Email message ID to delete"
                    },
                    "permanent": {
                        "type": "boolean",
                        "description": "Permanently delete (hard delete)",
                        "default": False
                    }
                },
                "required": ["message_id"]
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Delete email."""
        message_id = kwargs.get("message_id")
        permanent = kwargs.get("permanent", False)

        try:
            # Find and delete message
            item = self.ews_client.account.inbox.get(id=message_id)

            if permanent:
                item.delete()
                action = "permanently deleted"
            else:
                item.soft_delete()
                action = "moved to trash"

            self.logger.info(f"Email {message_id} {action}")

            return format_success_response(
                f"Email {action}",
                message_id=message_id
            )

        except Exception as e:
            self.logger.error(f"Failed to delete email: {e}")
            raise ToolExecutionError(f"Failed to delete email: {e}")


class MoveEmailTool(BaseTool):
    """Tool for moving emails between folders."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "move_email",
            "description": "Move an email to a different folder",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Email message ID to move"
                    },
                    "destination_folder": {
                        "type": "string",
                        "description": "Destination folder (inbox, sent, drafts, deleted, junk)"
                    }
                },
                "required": ["message_id", "destination_folder"]
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Move email to folder."""
        message_id = kwargs.get("message_id")
        dest_folder_name = kwargs.get("destination_folder", "").lower()

        try:
            # Get destination folder
            folder_map = {
                "inbox": self.ews_client.account.inbox,
                "sent": self.ews_client.account.sent,
                "drafts": self.ews_client.account.drafts,
                "deleted": self.ews_client.account.trash,
                "junk": self.ews_client.account.junk
            }

            dest_folder = folder_map.get(dest_folder_name)
            if not dest_folder:
                raise ToolExecutionError(f"Unknown folder: {dest_folder_name}")

            # Find and move message
            item = self.ews_client.account.inbox.get(id=message_id)
            item.move(dest_folder)

            self.logger.info(f"Email {message_id} moved to {dest_folder_name}")

            return format_success_response(
                f"Email moved to {dest_folder_name}",
                message_id=message_id
            )

        except Exception as e:
            self.logger.error(f"Failed to move email: {e}")
            raise ToolExecutionError(f"Failed to move email: {e}")


class UpdateEmailTool(BaseTool):
    """Tool for updating email properties."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "update_email",
            "description": "Update email properties (read status, flags, categories, importance)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Email message ID"
                    },
                    "is_read": {
                        "type": "boolean",
                        "description": "Mark as read (true) or unread (false)"
                    },
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Email categories (labels)"
                    },
                    "flag_status": {
                        "type": "string",
                        "enum": ["NotFlagged", "Flagged", "Complete"],
                        "description": "Flag status"
                    },
                    "importance": {
                        "type": "string",
                        "enum": ["Low", "Normal", "High"],
                        "description": "Email importance level"
                    }
                },
                "required": ["message_id"]
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Update email properties."""
        message_id = kwargs.get("message_id")

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

            # Track what was updated
            updates = {}

            # Update read status
            if "is_read" in kwargs:
                message.is_read = kwargs["is_read"]
                updates["is_read"] = kwargs["is_read"]

            # Update categories
            if "categories" in kwargs:
                message.categories = kwargs["categories"]
                updates["categories"] = kwargs["categories"]

            # Update flag status
            if "flag_status" in kwargs:
                message.flag.flag_status = kwargs["flag_status"]
                updates["flag_status"] = kwargs["flag_status"]

            # Update importance
            if "importance" in kwargs:
                message.importance = kwargs["importance"]
                updates["importance"] = kwargs["importance"]

            # Save changes
            message.save()

            self.logger.info(f"Email {message_id} updated: {updates}")

            return format_success_response(
                "Email updated successfully",
                message_id=message_id,
                updates=updates
            )

        except ToolExecutionError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to update email: {e}")
            raise ToolExecutionError(f"Failed to update email: {e}")


class CopyEmailTool(BaseTool):
    """Tool for copying emails to another folder."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "copy_email",
            "description": "Copy an email to another folder (keeping original in current location)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Email message ID to copy"
                    },
                    "destination_folder": {
                        "type": "string",
                        "description": "Destination folder name",
                        "enum": ["inbox", "sent", "drafts", "deleted", "junk", "archive"]
                    },
                    "destination_folder_id": {
                        "type": "string",
                        "description": "Destination folder ID (alternative to destination_folder)"
                    }
                },
                "required": ["message_id"]
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Copy email to another folder."""
        message_id = kwargs.get("message_id")
        destination_folder_name = kwargs.get("destination_folder")
        destination_folder_id = kwargs.get("destination_folder_id")

        if not message_id:
            raise ToolExecutionError("message_id is required")

        if not destination_folder_name and not destination_folder_id:
            raise ToolExecutionError("Either destination_folder or destination_folder_id is required")

        try:
            # Find the message in various folders
            message = None
            source_folder_name = None

            folders_to_search = [
                ("inbox", self.ews_client.account.inbox),
                ("sent", self.ews_client.account.sent),
                ("drafts", self.ews_client.account.drafts),
                ("deleted", self.ews_client.account.trash),
                ("junk", self.ews_client.account.junk)
            ]

            for folder_name, folder in folders_to_search:
                try:
                    message = folder.get(id=message_id)
                    if message:
                        source_folder_name = folder_name
                        break
                except Exception:
                    continue

            if not message:
                raise ToolExecutionError(f"Message not found: {message_id}")

            # Get destination folder
            if destination_folder_name:
                folder_map = {
                    "inbox": self.ews_client.account.inbox,
                    "sent": self.ews_client.account.sent,
                    "drafts": self.ews_client.account.drafts,
                    "deleted": self.ews_client.account.trash,
                    "junk": self.ews_client.account.junk,
                    "archive": self.ews_client.account.archive
                }

                destination_folder = folder_map.get(destination_folder_name.lower())
                if not destination_folder:
                    raise ToolExecutionError(f"Unknown destination folder: {destination_folder_name}")
                dest_name = destination_folder_name
            else:
                # Find folder by ID
                def find_folder_by_id(parent, target_id):
                    """Recursively search for folder by ID."""
                    if safe_get(parent, 'id', '') == target_id:
                        return parent

                    if hasattr(parent, 'children') and parent.children:
                        for child in parent.children:
                            result = find_folder_by_id(child, target_id)
                            if result:
                                return result
                    return None

                destination_folder = find_folder_by_id(self.ews_client.account.root, destination_folder_id)
                if not destination_folder:
                    raise ToolExecutionError(f"Destination folder not found: {destination_folder_id}")
                dest_name = safe_get(destination_folder, 'name', 'Unknown')

            # Copy the message (exchangelib uses .copy() method)
            copied_message = message.copy(to_folder=destination_folder)

            subject = safe_get(message, 'subject', 'No Subject')

            self.logger.info(f"Copied email '{subject}' from {source_folder_name} to {dest_name}")

            return format_success_response(
                f"Email copied from {source_folder_name} to {dest_name}",
                message_id=message_id,
                copied_message_id=safe_get(copied_message, 'id', '') if copied_message else '',
                subject=subject,
                source_folder=source_folder_name,
                destination_folder=dest_name
            )

        except ToolExecutionError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to copy email: {e}")
            raise ToolExecutionError(f"Failed to copy email: {e}")
