"""Advanced search tools for EWS MCP Server."""

from typing import Any, Dict, List
from exchangelib.queryset import Q

from .base import BaseTool
from ..exceptions import ToolExecutionError
from ..utils import format_success_response, safe_get, truncate_text, parse_datetime_tz_aware


class AdvancedSearchTool(BaseTool):
    """Tool for complex multi-criteria searches."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "advanced_search",
            "description": "Perform complex searches across mailbox with multiple criteria and filters",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "search_filter": {
                        "type": "object",
                        "description": "Search criteria object with filters",
                        "properties": {
                            "keywords": {
                                "type": "string",
                                "description": "Keywords to search in subject and body"
                            },
                            "from_address": {
                                "type": "string",
                                "description": "Sender email address"
                            },
                            "to_address": {
                                "type": "string",
                                "description": "Recipient email address"
                            },
                            "subject": {
                                "type": "string",
                                "description": "Subject contains text"
                            },
                            "body": {
                                "type": "string",
                                "description": "Body contains text"
                            },
                            "has_attachments": {
                                "type": "boolean",
                                "description": "Filter by attachment presence"
                            },
                            "importance": {
                                "type": "string",
                                "enum": ["Low", "Normal", "High"],
                                "description": "Email importance level"
                            },
                            "categories": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Email categories"
                            },
                            "is_read": {
                                "type": "boolean",
                                "description": "Read status"
                            },
                            "start_date": {
                                "type": "string",
                                "description": "Start date (ISO 8601 format)"
                            },
                            "end_date": {
                                "type": "string",
                                "description": "End date (ISO 8601 format)"
                            }
                        }
                    },
                    "search_scope": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Folders to search (e.g., ['inbox', 'sent', 'drafts'])",
                        "default": ["inbox"]
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 250,
                        "maximum": 1000
                    },
                    "sort_by": {
                        "type": "string",
                        "enum": ["datetime_received", "datetime_sent", "from", "subject", "importance"],
                        "description": "Sort field",
                        "default": "datetime_received"
                    },
                    "sort_order": {
                        "type": "string",
                        "enum": ["ascending", "descending"],
                        "description": "Sort order",
                        "default": "descending"
                    }
                },
                "required": ["search_filter", "search_scope"]
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Perform advanced search."""
        search_filter = kwargs.get("search_filter", {})
        search_scope = kwargs.get("search_scope", ["inbox"])
        max_results = kwargs.get("max_results", 250)
        sort_by = kwargs.get("sort_by", "datetime_received")
        sort_order = kwargs.get("sort_order", "descending")

        if not search_filter:
            raise ToolExecutionError("search_filter is required and cannot be empty")

        if not search_scope:
            raise ToolExecutionError("search_scope is required and cannot be empty")

        try:
            # Map folder names to folder objects
            folder_map = {
                "inbox": self.ews_client.account.inbox,
                "sent": self.ews_client.account.sent,
                "drafts": self.ews_client.account.drafts,
                "deleted": self.ews_client.account.trash,
                "junk": self.ews_client.account.junk
            }

            # Get folders to search
            folders = []
            for folder_name in search_scope:
                folder = folder_map.get(folder_name.lower())
                if folder:
                    folders.append(folder)
                else:
                    self.logger.warning(f"Unknown folder: {folder_name}, skipping")

            if not folders:
                raise ToolExecutionError(f"No valid folders found in search_scope: {search_scope}")

            # Build query filters
            q_filters = []

            # Keywords (search in subject and body)
            if search_filter.get("keywords"):
                keywords = search_filter["keywords"]
                q_filters.append(
                    Q(subject__contains=keywords) | Q(body__contains=keywords)
                )

            # From address
            if search_filter.get("from_address"):
                q_filters.append(Q(sender=search_filter["from_address"]))

            # To address
            if search_filter.get("to_address"):
                q_filters.append(Q(to_recipients__contains=search_filter["to_address"]))

            # Subject
            if search_filter.get("subject"):
                q_filters.append(Q(subject__contains=search_filter["subject"]))

            # Body
            if search_filter.get("body"):
                q_filters.append(Q(body__contains=search_filter["body"]))

            # Has attachments
            if "has_attachments" in search_filter:
                q_filters.append(Q(has_attachments=search_filter["has_attachments"]))

            # Importance
            if search_filter.get("importance"):
                q_filters.append(Q(importance=search_filter["importance"]))

            # Categories
            if search_filter.get("categories"):
                # Categories filter - at least one category matches
                q_filters.append(Q(categories__contains=search_filter["categories"]))

            # Is read
            if "is_read" in search_filter:
                q_filters.append(Q(is_read=search_filter["is_read"]))

            # Date range
            if search_filter.get("start_date"):
                start_date = parse_datetime_tz_aware(search_filter["start_date"])
                if start_date:
                    q_filters.append(Q(datetime_received__gte=start_date))

            if search_filter.get("end_date"):
                end_date = parse_datetime_tz_aware(search_filter["end_date"])
                if end_date:
                    q_filters.append(Q(datetime_received__lte=end_date))

            # Combine filters with AND
            if not q_filters:
                raise ToolExecutionError("No valid search filters provided")

            combined_filter = q_filters[0]
            for q_filter in q_filters[1:]:
                combined_filter &= q_filter

            # Search across all specified folders
            all_results = []
            for folder in folders:
                try:
                    query = folder.filter(combined_filter)

                    # Apply sorting
                    sort_field = sort_by if sort_by.startswith('-') or sort_by.startswith('+') else sort_by
                    if sort_order == "descending" and not sort_field.startswith('-'):
                        sort_field = f"-{sort_field}"

                    query = query.order_by(sort_field)

                    # Fetch results (limit per folder)
                    results_per_folder = max_results // len(folders) if len(folders) > 1 else max_results
                    for email in query[:results_per_folder]:
                        all_results.append({
                            "message_id": safe_get(email, 'id', ''),
                            "subject": safe_get(email, 'subject', ''),
                            "from": safe_get(email, 'sender', {}).email_address if hasattr(safe_get(email, 'sender', {}), 'email_address') else '',
                            "to": [r.email_address for r in safe_get(email, 'to_recipients', []) if hasattr(r, 'email_address')],
                            "received_time": safe_get(email, 'datetime_received', '').isoformat() if safe_get(email, 'datetime_received') else None,
                            "is_read": safe_get(email, 'is_read', False),
                            "has_attachments": safe_get(email, 'has_attachments', False),
                            "importance": safe_get(email, 'importance', 'Normal'),
                            "categories": safe_get(email, 'categories', []),
                            "body_preview": truncate_text(safe_get(email, 'text_body', ''), 200),
                            "folder": folder.name
                        })

                except Exception as e:
                    self.logger.warning(f"Error searching folder {folder.name}: {e}")
                    continue

            # Sort all results if we searched multiple folders
            if len(folders) > 1:
                reverse = (sort_order == "descending")
                if sort_by == "datetime_received":
                    all_results.sort(key=lambda x: x.get("received_time", ""), reverse=reverse)
                elif sort_by == "subject":
                    all_results.sort(key=lambda x: x.get("subject", ""), reverse=reverse)
                elif sort_by == "from":
                    all_results.sort(key=lambda x: x.get("from", ""), reverse=reverse)

            # Limit total results
            all_results = all_results[:max_results]

            self.logger.info(f"Advanced search found {len(all_results)} result(s)")

            return format_success_response(
                f"Found {len(all_results)} result(s)",
                results=all_results,
                count=len(all_results),
                search_filter=search_filter,
                folders_searched=search_scope
            )

        except ToolExecutionError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to perform advanced search: {e}")
            raise ToolExecutionError(f"Failed to perform advanced search: {e}")
