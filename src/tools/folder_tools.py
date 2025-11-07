"""Folder management tools for EWS MCP Server."""

from typing import Any, Dict, List

from .base import BaseTool
from ..exceptions import ToolExecutionError
from ..utils import format_success_response, safe_get


class ListFoldersTool(BaseTool):
    """Tool for listing mailbox folder hierarchy."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "list_folders",
            "description": "Get mailbox folder hierarchy with folder details",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "parent_folder": {
                        "type": "string",
                        "description": "Parent folder to start from (default: root)",
                        "default": "root",
                        "enum": ["root", "inbox", "sent", "drafts", "deleted", "junk", "calendar", "contacts", "tasks"]
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Maximum depth to traverse (1-10)",
                        "default": 2,
                        "minimum": 1,
                        "maximum": 10
                    },
                    "include_hidden": {
                        "type": "boolean",
                        "description": "Include hidden folders",
                        "default": False
                    },
                    "include_counts": {
                        "type": "boolean",
                        "description": "Include item counts for each folder",
                        "default": True
                    }
                }
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """List folders recursively."""
        parent_folder_name = kwargs.get("parent_folder", "root").lower()
        depth = kwargs.get("depth", 2)
        include_hidden = kwargs.get("include_hidden", False)
        include_counts = kwargs.get("include_counts", True)

        # Validate depth
        if depth < 1 or depth > 10:
            raise ToolExecutionError("depth must be between 1 and 10")

        try:
            # Get the parent folder
            folder_map = {
                "root": self.ews_client.account.root,
                "inbox": self.ews_client.account.inbox,
                "sent": self.ews_client.account.sent,
                "drafts": self.ews_client.account.drafts,
                "deleted": self.ews_client.account.trash,
                "junk": self.ews_client.account.junk,
                "calendar": self.ews_client.account.calendar,
                "contacts": self.ews_client.account.contacts,
                "tasks": self.ews_client.account.tasks
            }

            parent_folder = folder_map.get(parent_folder_name)
            if not parent_folder:
                raise ToolExecutionError(f"Unknown parent folder: {parent_folder_name}")

            # Recursively list folders
            def list_folder_tree(folder, current_depth, max_depth):
                """Recursively list folder tree."""
                if current_depth > max_depth:
                    return None

                # Get folder info
                folder_info = {
                    "id": safe_get(folder, 'id', ''),
                    "name": safe_get(folder, 'name', ''),
                    "parent_folder_id": safe_get(folder, 'parent_folder_id', ''),
                    "folder_class": safe_get(folder, 'folder_class', ''),
                    "child_folder_count": safe_get(folder, 'child_folder_count', 0)
                }

                # Add counts if requested
                if include_counts:
                    try:
                        folder_info["total_count"] = safe_get(folder, 'total_count', 0)
                        folder_info["unread_count"] = safe_get(folder, 'unread_count', 0)
                    except Exception:
                        folder_info["total_count"] = 0
                        folder_info["unread_count"] = 0

                # Get child folders
                children = []
                try:
                    if hasattr(folder, 'children') and folder.children:
                        for child in folder.children:
                            # Skip hidden folders if not requested
                            if not include_hidden:
                                child_class = safe_get(child, 'folder_class', '')
                                if child_class and 'IPF.Note' not in child_class and 'IPF.Appointment' not in child_class and 'IPF.Contact' not in child_class and 'IPF.Task' not in child_class:
                                    # This might be a hidden/system folder
                                    pass

                            child_info = list_folder_tree(child, current_depth + 1, max_depth)
                            if child_info:
                                children.append(child_info)
                except Exception as e:
                    self.logger.warning(f"Error listing children of folder {folder_info['name']}: {e}")

                if children:
                    folder_info["children"] = children

                return folder_info

            # Build folder tree
            folder_tree = list_folder_tree(parent_folder, 1, depth)

            # Count total folders
            def count_folders(tree):
                """Count total folders in tree."""
                count = 1
                if "children" in tree:
                    for child in tree["children"]:
                        count += count_folders(child)
                return count

            total_folders = count_folders(folder_tree) if folder_tree else 0

            self.logger.info(f"Listed {total_folders} folder(s) from {parent_folder_name}")

            return format_success_response(
                f"Listed {total_folders} folder(s)",
                folder_tree=folder_tree,
                total_folders=total_folders,
                parent_folder=parent_folder_name,
                depth=depth
            )

        except ToolExecutionError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to list folders: {e}")
            raise ToolExecutionError(f"Failed to list folders: {e}")
