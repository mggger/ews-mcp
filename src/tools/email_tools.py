"""Email operation tools for EWS MCP Server."""

from typing import Any, Dict, List
from datetime import datetime
from exchangelib import Message, Mailbox, FileAttachment, HTMLBody, Body, Folder
from exchangelib.queryset import Q
import re
import os
from pathlib import Path

from .base import BaseTool
from ..models import SendEmailRequest, EmailSearchRequest, EmailDetails
from ..exceptions import ToolExecutionError
from ..utils import format_success_response, safe_get, truncate_text, parse_datetime_tz_aware, find_message_across_folders


async def resolve_folder(ews_client, folder_identifier: str):
    """
    Resolve folder from name, path, or ID.

    Supports:
    - Standard names: inbox, sent, drafts, deleted, junk
    - Folder paths: Inbox/CC, Inbox/Projects/2024
    - Folder IDs: AAMkADc3MWUy...
    - Custom folder names: CC, Archive, Projects
    """
    folder_identifier = folder_identifier.strip()

    # Standard folders map (lowercase for matching)
    folder_map = {
        "inbox": ews_client.account.inbox,
        "sent": ews_client.account.sent,
        "drafts": ews_client.account.drafts,
        "deleted": ews_client.account.trash,
        "junk": ews_client.account.junk,
        "trash": ews_client.account.trash,
        "calendar": ews_client.account.calendar,
        "contacts": ews_client.account.contacts,
        "tasks": ews_client.account.tasks
    }

    # Try 1: Standard folder name (case-insensitive)
    folder_lower = folder_identifier.lower()
    if folder_lower in folder_map:
        return folder_map[folder_lower]

    # Try 2: Folder ID (starts with AAM or similar Exchange ID pattern)
    # Note: Direct folder ID access requires navigating the folder tree to find matching ID
    # This is a TODO for future enhancement - for now, use folder paths or names
    if len(folder_identifier) > 50 and not '/' in folder_identifier:
        # Folder ID detection - try to find in tree
        def find_folder_by_id(parent, target_id):
            """Recursively search for folder by ID."""
            try:
                if safe_get(parent, 'id', '') == target_id:
                    return parent
                if hasattr(parent, 'children') and parent.children:
                    for child in parent.children:
                        result = find_folder_by_id(child, target_id)
                        if result:
                            return result
            except Exception:
                pass
            return None

        # Search root tree for folder ID
        found_folder = find_folder_by_id(ews_client.account.root, folder_identifier)
        if found_folder:
            return found_folder

    # Try 3: Folder path (e.g., "Inbox/CC" or "Inbox/Projects/2024")
    if '/' in folder_identifier:
        parts = folder_identifier.split('/')
        parent_name = parts[0].strip().lower()

        # Start from a known parent folder
        if parent_name in folder_map:
            current_folder = folder_map[parent_name]
        else:
            # Default to inbox if parent not recognized
            current_folder = ews_client.account.inbox

        # Navigate through subfolders
        for subfolder_name in parts[1:]:
            subfolder_name = subfolder_name.strip()
            found = False

            try:
                for child in current_folder.children:
                    if safe_get(child, 'name', '').lower() == subfolder_name.lower():
                        current_folder = child
                        found = True
                        break
            except Exception as e:
                raise ToolExecutionError(
                    f"Error accessing subfolders of '{current_folder.name}': {e}"
                )

            if not found:
                raise ToolExecutionError(
                    f"Subfolder '{subfolder_name}' not found under '{current_folder.name}'"
                )

        return current_folder

    # Try 4: Search for custom folder by name (recursively under inbox)
    def search_folder_tree(parent, target_name, max_depth=3, current_depth=0):
        """Recursively search for folder by name."""
        if current_depth >= max_depth:
            return None

        try:
            for child in parent.children:
                child_name = safe_get(child, 'name', '')
                if child_name.lower() == target_name.lower():
                    return child
                # Recurse into subfolders
                found = search_folder_tree(child, target_name, max_depth, current_depth + 1)
                if found:
                    return found
        except Exception:
            pass

        return None

    # Search under inbox first (most common location for custom folders)
    custom_folder = search_folder_tree(ews_client.account.inbox, folder_identifier)
    if custom_folder:
        return custom_folder

    # Search under root as fallback
    custom_folder = search_folder_tree(ews_client.account.root, folder_identifier)
    if custom_folder:
        return custom_folder

    # If all methods fail, provide helpful error
    raise ToolExecutionError(
        f"Folder '{folder_identifier}' not found. "
        f"Available standard folders: {', '.join(folder_map.keys())}. "
        f"For custom folders, use full path (e.g., 'Inbox/CC') or get folder ID from list_folders."
    )


class SendEmailTool(BaseTool):
    """Tool for sending emails."""

    def _apply_email_template(self, user_content: str) -> str:
        """
        Apply HTML email template to user content.
        
        Args:
            user_content: User's email content (can be plain text or HTML)
            
        Returns:
            Complete HTML email with template applied
        """
        # Get template path
        template_path = Path(__file__).parent.parent.parent / "templates" / "email_template.html"
        
        try:
            # Read template
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            
            # If user content is plain text, wrap in paragraph tags
            if not re.search(r'<[^>]+>', user_content):
                user_content = f"<p>{user_content.replace(chr(10), '</p><p>')}</p>"
            
            # Replace placeholder with user content
            html_content = template.replace('{{EMAIL_CONTENT}}', user_content)
            
            return html_content
            
        except FileNotFoundError:
            self.logger.warning(f"Email template not found at {template_path}, using content as-is")
            return user_content
        except Exception as e:
            self.logger.error(f"Error applying email template: {e}")
            return user_content

    def _attach_signature_image(self, message: Message) -> None:
        """
        Attach signature image (mick.png) as inline content.
        
        Args:
            message: Exchange message object to attach image to
        """
        # Get image path
        image_path = Path(__file__).parent.parent.parent / "mick.png"
        
        if not image_path.exists():
            self.logger.warning(f"Signature image not found at {image_path}")
            return
        
        try:
            # Read image file
            with open(image_path, 'rb') as f:
                image_content = f.read()
            
            # Create inline attachment with Content-ID
            inline_attachment = FileAttachment(
                name='mick.png',
                content=image_content,
                is_inline=True,
                content_id='mick_signature'
            )
            
            message.attach(inline_attachment)
            self.logger.info(f"Attached inline signature image: mick.png ({len(image_content)} bytes)")
            
        except Exception as e:
            self.logger.error(f"Failed to attach signature image: {e}")

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "send_email",
            "description": "Send an email through Exchange with optional attachments and CC/BCC. Automatically uses professional HTML template with signature. Supports distribution lists (directory names).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Recipients: email addresses (user@domain.com), display names (John Doe), or distribution list names (Team-All, Marketing-Group)"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content (plain text or HTML)"
                    },
                    "cc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "CC recipients: email addresses, display names, or distribution list names (optional)"
                    },
                    "bcc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "BCC recipients: email addresses, display names, or distribution list names (optional)"
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

    def _resolve_recipients(self, recipients: List[str]) -> List[Mailbox]:
        """
        Resolve recipients which can be:
        - Email addresses (user@domain.com) - used directly without resolution
        - Display names (John Doe) - resolved via directory
        - Distribution list names (Team-All, Marketing-Group, accounts) - resolved and expanded
        
        Returns list of Mailbox objects ready for sending.
        """
        resolved_mailboxes = []
        
        for recipient in recipients:
            recipient = recipient.strip()
            
            # 如果包含 @，说明已经是邮箱地址，直接使用，不需要解析
            if '@' in recipient:
                resolved_mailboxes.append(Mailbox(email_address=recipient))
                self.logger.info(f"Using email address directly: '{recipient}'")
                continue
            
            # 不包含 @，需要通过目录解析（可能是显示名或分发列表）
            try:
                self.logger.info(f"Resolving recipient: '{recipient}'")
                
                # Try multiple search scopes to find the recipient
                resolved = None
                for search_scope in ['ActiveDirectory', 'ActiveDirectoryContacts', None]:
                    try:
                        self.logger.debug(f"Trying resolve_names with scope: {search_scope}")
                        resolve_kwargs = {
                            'names': [recipient],
                            'return_full_contact_data': True
                        }
                        if search_scope:
                            resolve_kwargs['search_scope'] = search_scope
                        
                        resolved = self.ews_client.account.protocol.resolve_names(**resolve_kwargs)
                        
                        if resolved and len(resolved) > 0:
                            self.logger.info(f"Found {len(resolved)} result(s) with scope: {search_scope}")
                            break
                    except Exception as e:
                        self.logger.debug(f"Scope {search_scope} failed: {e}")
                        continue
                
                if resolved and len(resolved) > 0:
                    # Filter for exact name match (case-insensitive)
                    exact_matches = []
                    for item in resolved:
                        if isinstance(item, tuple) and len(item) >= 1:
                            mb = item[0]
                            mb_name = getattr(mb, 'name', '')
                            mb_email = getattr(mb, 'email_address', '')
                            
                            # Check for exact match on name or email prefix
                            if mb_name and mb_name.lower() == recipient.lower():
                                exact_matches.append(item)
                                self.logger.debug(f"Exact match: {mb_name} <{mb_email}>")
                            elif mb_email and mb_email.lower().startswith(recipient.lower() + '@'):
                                exact_matches.append(item)
                                self.logger.debug(f"Email prefix match: {mb_name} <{mb_email}>")
                            else:
                                self.logger.debug(f"Partial match (ignored): {mb_name} <{mb_email}>")
                    
                    if len(exact_matches) == 0:
                        self.logger.warning(f"Found {len(resolved)} results but no exact match for '{recipient}', using first result")
                        exact_matches = resolved[:1]
                    elif len(exact_matches) > 1:
                        self.logger.info(f"Found {len(exact_matches)} exact matches for '{recipient}', using first")
                    
                    # Process exact matches only
                    for idx, item in enumerate(exact_matches):
                        self.logger.debug(f"=== Resolution item #{idx+1} ===")
                        self.logger.debug(f"Type: {type(item)}")
                        
                        # exchangelib returns tuples: (Mailbox, Contact)
                        mailbox = None
                        if isinstance(item, tuple) and len(item) >= 1:
                            # First element is the Mailbox
                            mailbox = item[0]
                            self.logger.debug(f"Extracted mailbox from tuple[0]: {type(mailbox)}")
                        elif hasattr(item, 'mailbox'):
                            mailbox = item.mailbox
                            self.logger.debug(f"Got mailbox via .mailbox")
                        else:
                            mailbox = item
                            self.logger.debug(f"Using item as mailbox directly")
                        
                        if mailbox is None:
                            self.logger.warning(f"Could not extract mailbox from item")
                            continue
                        
                        # Get mailbox properties
                        mailbox_type = getattr(mailbox, 'mailbox_type', None)
                        email_address = getattr(mailbox, 'email_address', None)
                        name = getattr(mailbox, 'name', None)
                        
                        self.logger.info(f"Resolved '{recipient}' -> Name: {name}, Type: {mailbox_type}, Email: {email_address}")
                        
                        if mailbox_type in ('PublicDL', 'PrivateDL', 'GroupMailbox'):
                            # This is a distribution list - try to expand it
                            self.logger.info(f"✓ Detected distribution list: {recipient} (Type: {mailbox_type})")
                            
                            if not email_address:
                                self.logger.error(f"Distribution list has no email address!")
                                raise ToolExecutionError(f"Distribution list '{recipient}' has no email address")
                            
                            try:
                                # Use ExpandDL to get members
                                self.logger.info(f"Expanding DL: {email_address}")
                                members = list(self.ews_client.account.protocol.expand_dl(email_address))
                                
                                self.logger.info(f"✓ Expansion successful! Found {len(members)} members")
                                
                                if len(members) > 0:
                                    for member in members:
                                        member_mailbox = member.mailbox if hasattr(member, 'mailbox') else member
                                        member_email = getattr(member_mailbox, 'email_address', None)
                                        member_name = getattr(member_mailbox, 'name', None)
                                        
                                        if member_email:
                                            resolved_mailboxes.append(Mailbox(email_address=member_email))
                                            self.logger.debug(f"  + Member: {member_name} <{member_email}>")
                                        else:
                                            self.logger.warning(f"  - Skipped member with no email: {member_name}")
                                    
                                    self.logger.info(f"✓ Added {len(members)} members from '{recipient}'")
                                else:
                                    # No members found, use DL address directly
                                    self.logger.warning(f"No members in DL '{recipient}', using DL address directly")
                                    resolved_mailboxes.append(Mailbox(email_address=email_address))
                                    
                            except Exception as e:
                                self.logger.error(f"✗ Failed to expand DL '{recipient}': {e}")
                                # Fall back to using the DL address directly
                                self.logger.info(f"Fallback: Using DL address directly: {email_address}")
                                resolved_mailboxes.append(Mailbox(email_address=email_address))
                        else:
                            # Regular mailbox or contact
                            if email_address:
                                resolved_mailboxes.append(Mailbox(email_address=email_address))
                                self.logger.info(f"✓ Added mailbox: {name} <{email_address}>")
                            else:
                                self.logger.warning(f"Resolved item has no email address: {name}")
                else:
                    # Could not resolve - not found in directory
                    self.logger.error(f"✗ Could not resolve '{recipient}' - not found in directory")
                    raise ToolExecutionError(
                        f"Could not resolve recipient '{recipient}'. "
                        f"Please check: (1) Name is correct, (2) Distribution list exists in directory, "
                        f"(3) Or provide full email address (user@domain.com)"
                    )
                        
            except ToolExecutionError:
                raise
            except Exception as e:
                self.logger.error(f"✗ Failed to resolve '{recipient}': {e}")
                raise ToolExecutionError(f"Could not resolve recipient '{recipient}': {e}")
        
        if not resolved_mailboxes:
            raise ToolExecutionError("No valid recipients found after resolution")
        
        self.logger.info(f"✓ Total resolved recipients: {len(resolved_mailboxes)}")
        return resolved_mailboxes

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Send email via EWS."""
        # Validate input
        request = self.validate_input(SendEmailRequest, **kwargs)

        try:
            # Resolve all recipients (handles emails, names, and distribution lists)
            self.logger.info("Resolving recipients...")
            resolved_to = self._resolve_recipients(request.to)
            resolved_cc = self._resolve_recipients(request.cc or []) if request.cc else []
            resolved_bcc = self._resolve_recipients(request.bcc or []) if request.bcc else []
            
            self.logger.info(f"Resolved {len(request.to)} TO recipient(s) to {len(resolved_to)} email(s)")
            if request.cc:
                self.logger.info(f"Resolved {len(request.cc)} CC recipient(s) to {len(resolved_cc)} email(s)")
            if request.bcc:
                self.logger.info(f"Resolved {len(request.bcc)} BCC recipient(s) to {len(resolved_bcc)} email(s)")

            # Clean and prepare email body
            email_body = request.body.strip()

            # Strip CDATA wrapper if present (CDATA is XML syntax, not needed for Exchange)
            if email_body.startswith('<![CDATA[') and email_body.endswith(']]>'):
                email_body = email_body[9:-3].strip()  # Remove <![CDATA[ and ]]>
                self.logger.info("Stripped CDATA wrapper from email body")

            # Validate body is not empty after processing
            if not email_body:
                raise ToolExecutionError("Email body is empty after processing")

            # Always apply HTML template with signature
            email_body = self._apply_email_template(email_body)
            is_html = True  # Template is always HTML
            self.logger.info("Applied HTML email template with signature")

            # Log body details for debugging
            body_type = "HTML" if is_html else "Plain Text"
            self.logger.info(f"Email body: {body_type}, {len(email_body)} characters, "
                           f"{len(email_body.encode('utf-8'))} bytes (UTF-8)")

            # Create message with appropriate body type
            # CRITICAL: Use HTMLBody for HTML, Body for plain text
            # Using wrong type causes Exchange to strip content!
            if is_html:
                message = Message(
                    account=self.ews_client.account,
                    subject=request.subject,
                    body=HTMLBody(email_body),
                    to_recipients=resolved_to
                )
                self.logger.info("Using HTMLBody for HTML content")
            else:
                message = Message(
                    account=self.ews_client.account,
                    subject=request.subject,
                    body=Body(email_body),
                    to_recipients=resolved_to
                )
                self.logger.info("Using Body (plain text) for non-HTML content")

            # Add CC recipients
            if resolved_cc:
                message.cc_recipients = resolved_cc

            # Add BCC recipients
            if resolved_bcc:
                message.bcc_recipients = resolved_bcc

            # Set importance
            message.importance = request.importance.value

            # CRITICAL: Verify body was set correctly BEFORE attaching/sending
            if not message.body or len(str(message.body).strip()) == 0:
                raise ToolExecutionError(
                    f"Message body is empty after creation! Original body length: {len(email_body)}, "
                    f"Message body: {message.body}"
                )
            self.logger.info(f"Verified message body set correctly: {len(str(message.body))} characters")

            # Always attach inline signature image (template includes it)
            self._attach_signature_image(message)

            # Add attachments if provided
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
                        self.logger.info(f"Attached file: {file_path.split('/')[-1]} ({len(content)} bytes)")
                    except Exception as e:
                        self.logger.error(f"Failed to attach file {file_path}: {e}")
                        raise ToolExecutionError(f"Failed to attach file {file_path}: {e}")

            # Send message (with or without attachments)
            # Note: send_and_save() sends the message and saves a copy to Sent Items
            message.send_and_save()
            
            attachment_info = f" with {len(request.attachments)} attachment(s)" if request.attachments else ""
            total_recipients = len(resolved_to) + len(resolved_cc) + len(resolved_bcc)
            self.logger.info(f"✅ Email sent successfully to {total_recipients} recipient(s){attachment_info}")

            return format_success_response(
                "Email sent successfully",
                message_id=message.id if hasattr(message, 'id') else None,
                sent_time=datetime.now().isoformat(),
                original_recipients={
                    "to": request.to,
                    "cc": request.cc or [],
                    "bcc": request.bcc or []
                },
                resolved_recipients={
                    "to": [m.email_address for m in resolved_to],
                    "cc": [m.email_address for m in resolved_cc],
                    "bcc": [m.email_address for m in resolved_bcc]
                },
                total_recipients=total_recipients,
                attachments=len(request.attachments) if request.attachments else 0
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
                        "description": "Folder name (standard names: inbox, sent, drafts; paths: Inbox/CC; or folder ID)",
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
        folder_name = kwargs.get("folder", "inbox")
        max_results = kwargs.get("max_results", 50)
        unread_only = kwargs.get("unread_only", False)

        try:
            # Get folder - supports standard names, paths, and folder IDs
            folder = await resolve_folder(self.ews_client, folder_name)
            self.logger.info(f"Resolved folder '{folder_name}' to: {safe_get(folder, 'name', folder_name)}")

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
                        "description": "Folder to search in (standard names: inbox, sent, drafts; paths: Inbox/CC; or folder ID)",
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
            # Auto-add date range to prevent timeouts in large mailboxes
            if not kwargs.get("start_date") and not kwargs.get("end_date"):
                # If no other specific filters are provided, enforce a default date range
                has_filters = (
                    kwargs.get("subject_contains") or
                    kwargs.get("from_address") or
                    kwargs.get("has_attachments") is not None or
                    kwargs.get("is_read") is not None
                )

                if not has_filters:
                    # No filters at all - default to last 30 days to prevent timeout
                    from datetime import timedelta
                    default_days_back = 30
                    auto_start_date = datetime.now() - timedelta(days=default_days_back)
                    kwargs["start_date"] = auto_start_date.isoformat()
                    self.logger.info(
                        f"No filters or date range provided. Automatically limiting search to last {default_days_back} days "
                        f"to prevent timeout. Specify start_date/end_date to search a different range."
                    )
                else:
                    # Has filters but no date range - warn but allow
                    self.logger.warning(
                        "Searching without date range may be slow for large mailboxes. "
                        "Consider adding start_date/end_date for better performance."
                    )

            # Get folder - supports standard names, paths, and folder IDs
            folder_name = kwargs.get("folder", "inbox")
            folder = await resolve_folder(self.ews_client, folder_name)
            self.logger.info(f"Resolved folder '{folder_name}' to: {safe_get(folder, 'name', folder_name)}")

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
            # Find message across all folders (including custom subfolders)
            item = find_message_across_folders(self.ews_client, message_id)

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
            # Find message across all folders (including custom subfolders)
            item = find_message_across_folders(self.ews_client, message_id)

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

            # Find message across all folders (including custom subfolders)
            item = find_message_across_folders(self.ews_client, message_id)
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
