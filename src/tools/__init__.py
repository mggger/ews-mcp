"""MCP Tools for EWS operations."""

from .email_tools import SendEmailTool, ReadEmailsTool, SearchEmailsTool, GetEmailDetailsTool, DeleteEmailTool, MoveEmailTool, UpdateEmailTool
from .calendar_tools import CreateAppointmentTool, GetCalendarTool, UpdateAppointmentTool, DeleteAppointmentTool, RespondToMeetingTool, CheckAvailabilityTool
from .contact_tools import CreateContactTool, SearchContactsTool, GetContactsTool, UpdateContactTool, DeleteContactTool, ResolveNamesTool
from .task_tools import CreateTaskTool, GetTasksTool, UpdateTaskTool, CompleteTaskTool, DeleteTaskTool
from .attachment_tools import ListAttachmentsTool, DownloadAttachmentTool
from .search_tools import AdvancedSearchTool
from .folder_tools import ListFoldersTool

__all__ = [
    # Email tools
    "SendEmailTool",
    "ReadEmailsTool",
    "SearchEmailsTool",
    "GetEmailDetailsTool",
    "DeleteEmailTool",
    "MoveEmailTool",
    "UpdateEmailTool",
    # Calendar tools
    "CreateAppointmentTool",
    "GetCalendarTool",
    "UpdateAppointmentTool",
    "DeleteAppointmentTool",
    "RespondToMeetingTool",
    "CheckAvailabilityTool",
    # Contact tools
    "CreateContactTool",
    "SearchContactsTool",
    "GetContactsTool",
    "UpdateContactTool",
    "DeleteContactTool",
    "ResolveNamesTool",
    # Task tools
    "CreateTaskTool",
    "GetTasksTool",
    "UpdateTaskTool",
    "CompleteTaskTool",
    "DeleteTaskTool",
    # Attachment tools
    "ListAttachmentsTool",
    "DownloadAttachmentTool",
    # Search tools
    "AdvancedSearchTool",
    # Folder tools
    "ListFoldersTool",
]
