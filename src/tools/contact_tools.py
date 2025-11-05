"""Contact operation tools for EWS MCP Server."""

from typing import Any, Dict
from exchangelib import Contact
from exchangelib.indexed_properties import EmailAddress

from .base import BaseTool
from ..models import CreateContactRequest
from ..exceptions import ToolExecutionError
from ..utils import format_success_response, safe_get


class CreateContactTool(BaseTool):
    """Tool for creating contacts."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "create_contact",
            "description": "Create a new contact in Exchange",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "given_name": {
                        "type": "string",
                        "description": "First name"
                    },
                    "surname": {
                        "type": "string",
                        "description": "Last name"
                    },
                    "email_address": {
                        "type": "string",
                        "description": "Email address"
                    },
                    "phone_number": {
                        "type": "string",
                        "description": "Phone number (optional)"
                    },
                    "company": {
                        "type": "string",
                        "description": "Company name (optional)"
                    },
                    "job_title": {
                        "type": "string",
                        "description": "Job title (optional)"
                    },
                    "department": {
                        "type": "string",
                        "description": "Department (optional)"
                    }
                },
                "required": ["given_name", "surname", "email_address"]
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Create contact."""
        # Validate input
        request = self.validate_input(CreateContactRequest, **kwargs)

        try:
            # Create contact
            contact = Contact(
                account=self.ews_client.account,
                folder=self.ews_client.account.contacts,
                given_name=request.given_name,
                surname=request.surname,
            )

            # Add email address
            contact.email_addresses = [
                EmailAddress(email=request.email_address, label='EmailAddress1')
            ]

            # Set optional fields
            if request.phone_number:
                contact.phone_numbers = [{'label': 'BusinessPhone', 'phone_number': request.phone_number}]

            if request.company:
                contact.company_name = request.company

            if request.job_title:
                contact.job_title = request.job_title

            if request.department:
                contact.department = request.department

            # Save contact
            contact.save()

            self.logger.info(f"Created contact: {request.given_name} {request.surname}")

            return format_success_response(
                "Contact created successfully",
                item_id=contact.id if hasattr(contact, "id") else None,
                display_name=f"{request.given_name} {request.surname}",
                email=request.email_address
            )

        except Exception as e:
            self.logger.error(f"Failed to create contact: {e}")
            raise ToolExecutionError(f"Failed to create contact: {e}")


class SearchContactsTool(BaseTool):
    """Tool for searching contacts."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "search_contacts",
            "description": "Search contacts by name or email",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (name or email)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 50,
                        "maximum": 1000
                    }
                },
                "required": ["query"]
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Search contacts."""
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 50)

        try:
            # Search in contacts folder
            items = self.ews_client.account.contacts.all()

            # Apply filter
            # Note: exchangelib has limited query capabilities for contacts
            # We'll filter in memory for broader compatibility
            contacts = []
            count = 0

            for item in items:
                if count >= max_results:
                    break

                # Check if query matches
                given_name = safe_get(item, "given_name", "")
                surname = safe_get(item, "surname", "")
                display_name = safe_get(item, "display_name", "")
                email_addrs = safe_get(item, "email_addresses", [])

                # Get email from list
                email = ""
                if email_addrs:
                    email = email_addrs[0].email if hasattr(email_addrs[0], 'email') else ""

                # Match query
                query_lower = query.lower()
                if (query_lower in given_name.lower() or
                    query_lower in surname.lower() or
                    query_lower in display_name.lower() or
                    query_lower in email.lower()):

                    contact_data = {
                        "item_id": safe_get(item, "id", "unknown"),
                        "display_name": display_name or f"{given_name} {surname}",
                        "given_name": given_name,
                        "surname": surname,
                        "email": email,
                        "company": safe_get(item, "company_name", ""),
                        "job_title": safe_get(item, "job_title", "")
                    }
                    contacts.append(contact_data)
                    count += 1

            self.logger.info(f"Found {len(contacts)} matching contacts")

            return format_success_response(
                f"Found {len(contacts)} matching contacts",
                contacts=contacts
            )

        except Exception as e:
            self.logger.error(f"Failed to search contacts: {e}")
            raise ToolExecutionError(f"Failed to search contacts: {e}")


class GetContactsTool(BaseTool):
    """Tool for listing all contacts."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "get_contacts",
            "description": "List all contacts",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of contacts to retrieve",
                        "default": 50,
                        "maximum": 1000
                    }
                }
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Get all contacts."""
        max_results = kwargs.get("max_results", 50)

        try:
            # Get contacts
            items = self.ews_client.account.contacts.all()[:max_results]

            contacts = []
            for item in items:
                given_name = safe_get(item, "given_name", "")
                surname = safe_get(item, "surname", "")
                display_name = safe_get(item, "display_name", "")
                email_addrs = safe_get(item, "email_addresses", [])

                email = ""
                if email_addrs:
                    email = email_addrs[0].email if hasattr(email_addrs[0], 'email') else ""

                contact_data = {
                    "item_id": safe_get(item, "id", "unknown"),
                    "display_name": display_name or f"{given_name} {surname}",
                    "given_name": given_name,
                    "surname": surname,
                    "email": email,
                    "company": safe_get(item, "company_name", ""),
                    "job_title": safe_get(item, "job_title", "")
                }
                contacts.append(contact_data)

            self.logger.info(f"Retrieved {len(contacts)} contacts")

            return format_success_response(
                f"Retrieved {len(contacts)} contacts",
                contacts=contacts
            )

        except Exception as e:
            self.logger.error(f"Failed to get contacts: {e}")
            raise ToolExecutionError(f"Failed to get contacts: {e}")


class UpdateContactTool(BaseTool):
    """Tool for updating contacts."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "update_contact",
            "description": "Update an existing contact",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "Contact item ID"
                    },
                    "given_name": {
                        "type": "string",
                        "description": "New first name (optional)"
                    },
                    "surname": {
                        "type": "string",
                        "description": "New last name (optional)"
                    },
                    "email_address": {
                        "type": "string",
                        "description": "New email address (optional)"
                    },
                    "phone_number": {
                        "type": "string",
                        "description": "New phone number (optional)"
                    },
                    "company": {
                        "type": "string",
                        "description": "New company name (optional)"
                    },
                    "job_title": {
                        "type": "string",
                        "description": "New job title (optional)"
                    }
                },
                "required": ["item_id"]
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Update contact."""
        item_id = kwargs.get("item_id")

        try:
            # Get the contact
            contact = self.ews_client.account.contacts.get(id=item_id)

            # Update fields
            if "given_name" in kwargs:
                contact.given_name = kwargs["given_name"]

            if "surname" in kwargs:
                contact.surname = kwargs["surname"]

            if "email_address" in kwargs:
                contact.email_addresses = [
                    EmailAddress(email=kwargs["email_address"], label='EmailAddress1')
                ]

            if "phone_number" in kwargs:
                contact.phone_numbers = [{'label': 'BusinessPhone', 'phone_number': kwargs["phone_number"]}]

            if "company" in kwargs:
                contact.company_name = kwargs["company"]

            if "job_title" in kwargs:
                contact.job_title = kwargs["job_title"]

            # Save changes
            contact.save()

            self.logger.info(f"Updated contact {item_id}")

            return format_success_response(
                "Contact updated successfully",
                item_id=item_id
            )

        except Exception as e:
            self.logger.error(f"Failed to update contact: {e}")
            raise ToolExecutionError(f"Failed to update contact: {e}")


class DeleteContactTool(BaseTool):
    """Tool for deleting contacts."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "delete_contact",
            "description": "Delete a contact",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "Contact item ID to delete"
                    }
                },
                "required": ["item_id"]
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Delete contact."""
        item_id = kwargs.get("item_id")

        try:
            # Get and delete the contact
            contact = self.ews_client.account.contacts.get(id=item_id)
            contact.delete()

            self.logger.info(f"Deleted contact {item_id}")

            return format_success_response(
                "Contact deleted successfully",
                item_id=item_id
            )

        except Exception as e:
            self.logger.error(f"Failed to delete contact: {e}")
            raise ToolExecutionError(f"Failed to delete contact: {e}")
