"""MCP Tools for EWS operations."""

from .email_tools import SendEmailTool, ReadEmailsTool, SearchEmailsTool, GetEmailDetailsTool, DeleteEmailTool, MoveEmailTool
from .calendar_tools import CreateAppointmentTool, GetCalendarTool, UpdateAppointmentTool, DeleteAppointmentTool, RespondToMeetingTool
from .contact_tools import CreateContactTool, SearchContactsTool, GetContactsTool, UpdateContactTool, DeleteContactTool
from .task_tools import CreateTaskTool, GetTasksTool, UpdateTaskTool, CompleteTaskTool, DeleteTaskTool

__all__ = [
    # Email tools
    "SendEmailTool",
    "ReadEmailsTool",
    "SearchEmailsTool",
    "GetEmailDetailsTool",
    "DeleteEmailTool",
    "MoveEmailTool",
    # Calendar tools
    "CreateAppointmentTool",
    "GetCalendarTool",
    "UpdateAppointmentTool",
    "DeleteAppointmentTool",
    "RespondToMeetingTool",
    # Contact tools
    "CreateContactTool",
    "SearchContactsTool",
    "GetContactsTool",
    "UpdateContactTool",
    "DeleteContactTool",
    # Task tools
    "CreateTaskTool",
    "GetTasksTool",
    "UpdateTaskTool",
    "CompleteTaskTool",
    "DeleteTaskTool",
]
