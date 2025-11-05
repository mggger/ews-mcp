"""Calendar operation tools for EWS MCP Server."""

from typing import Any, Dict
from datetime import datetime, timedelta
from exchangelib import CalendarItem, Mailbox, Attendee

from .base import BaseTool
from ..models import CreateAppointmentRequest, MeetingResponse
from ..exceptions import ToolExecutionError
from ..utils import format_success_response, safe_get, parse_datetime_tz_aware, make_tz_aware


class CreateAppointmentTool(BaseTool):
    """Tool for creating calendar appointments."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "create_appointment",
            "description": "Create a calendar appointment or meeting with attendees",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "Appointment subject"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time (ISO 8601 format)"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time (ISO 8601 format)"
                    },
                    "location": {
                        "type": "string",
                        "description": "Meeting location (optional)"
                    },
                    "body": {
                        "type": "string",
                        "description": "Appointment body (optional)"
                    },
                    "attendees": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Attendee email addresses (optional)"
                    },
                    "is_all_day": {
                        "type": "boolean",
                        "description": "All day event (optional)",
                        "default": False
                    },
                    "reminder_minutes": {
                        "type": "integer",
                        "description": "Reminder minutes before (optional)",
                        "default": 15
                    }
                },
                "required": ["subject", "start_time", "end_time"]
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Create calendar appointment."""
        # Parse datetime strings as timezone-aware
        kwargs["start_time"] = parse_datetime_tz_aware(kwargs["start_time"])
        kwargs["end_time"] = parse_datetime_tz_aware(kwargs["end_time"])

        # Validate input
        request = self.validate_input(CreateAppointmentRequest, **kwargs)

        try:
            # Create calendar item
            item = CalendarItem(
                account=self.ews_client.account,
                folder=self.ews_client.account.calendar,
                subject=request.subject,
                start=request.start_time,
                end=request.end_time,
                is_all_day=request.is_all_day
            )

            # Set optional fields
            if request.location:
                item.location = request.location

            if request.body:
                item.body = request.body

            if request.reminder_minutes is not None:
                item.reminder_is_set = True
                item.reminder_minutes_before_start = request.reminder_minutes

            # Add attendees
            if request.attendees:
                item.required_attendees = [
                    Attendee(mailbox=Mailbox(email_address=email))
                    for email in request.attendees
                ]

            # Save the appointment
            item.save()

            self.logger.info(f"Created appointment: {request.subject}")

            return format_success_response(
                "Appointment created successfully",
                item_id=item.id if hasattr(item, "id") else None,
                subject=request.subject,
                start_time=request.start_time.isoformat(),
                end_time=request.end_time.isoformat()
            )

        except Exception as e:
            self.logger.error(f"Failed to create appointment: {e}")
            raise ToolExecutionError(f"Failed to create appointment: {e}")


class GetCalendarTool(BaseTool):
    """Tool for retrieving calendar events."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "get_calendar",
            "description": "Retrieve calendar events for a date range",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date (ISO 8601 format, optional, defaults to today)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date (ISO 8601 format, optional, defaults to 7 days from start)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of events to retrieve",
                        "default": 50,
                        "maximum": 1000
                    }
                }
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Get calendar events."""
        try:
            # Parse dates as timezone-aware
            start_date = kwargs.get("start_date")
            if start_date:
                start_date = parse_datetime_tz_aware(start_date)
            else:
                start_date = make_tz_aware(datetime.now())

            end_date = kwargs.get("end_date")
            if end_date:
                end_date = parse_datetime_tz_aware(end_date)
            else:
                end_date = start_date + timedelta(days=7)

            max_results = kwargs.get("max_results", 50)

            # Query calendar
            items = self.ews_client.account.calendar.view(
                start=start_date,
                end=end_date
            ).order_by('start')

            # Format events
            events = []
            for item in items[:max_results]:
                event_data = {
                    "item_id": safe_get(item, "id", "unknown"),
                    "subject": safe_get(item, "subject", ""),
                    "start": safe_get(item, "start", datetime.now()).isoformat(),
                    "end": safe_get(item, "end", datetime.now()).isoformat(),
                    "location": safe_get(item, "location", ""),
                    "organizer": safe_get(item, "organizer", {}).email_address if hasattr(item, "organizer") else "",
                    "is_all_day": safe_get(item, "is_all_day", False),
                    "attendees": [
                        att.mailbox.email_address
                        for att in safe_get(item, "required_attendees", [])
                    ]
                }
                events.append(event_data)

            self.logger.info(f"Retrieved {len(events)} calendar events")

            return format_success_response(
                f"Retrieved {len(events)} events",
                events=events,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat()
            )

        except Exception as e:
            self.logger.error(f"Failed to get calendar: {e}")
            raise ToolExecutionError(f"Failed to get calendar: {e}")


class UpdateAppointmentTool(BaseTool):
    """Tool for updating calendar appointments."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "update_appointment",
            "description": "Update an existing calendar appointment",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "Appointment item ID"
                    },
                    "subject": {
                        "type": "string",
                        "description": "New subject (optional)"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "New start time (ISO 8601 format, optional)"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "New end time (ISO 8601 format, optional)"
                    },
                    "location": {
                        "type": "string",
                        "description": "New location (optional)"
                    },
                    "body": {
                        "type": "string",
                        "description": "New body (optional)"
                    }
                },
                "required": ["item_id"]
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Update appointment."""
        item_id = kwargs.get("item_id")

        try:
            # Get the appointment
            item = self.ews_client.account.calendar.get(id=item_id)

            # Update fields
            if "subject" in kwargs:
                item.subject = kwargs["subject"]

            if "start_time" in kwargs:
                item.start = parse_datetime_tz_aware(kwargs["start_time"])

            if "end_time" in kwargs:
                item.end = parse_datetime_tz_aware(kwargs["end_time"])

            if "location" in kwargs:
                item.location = kwargs["location"]

            if "body" in kwargs:
                item.body = kwargs["body"]

            # Save changes
            item.save()

            self.logger.info(f"Updated appointment {item_id}")

            return format_success_response(
                "Appointment updated successfully",
                item_id=item_id
            )

        except Exception as e:
            self.logger.error(f"Failed to update appointment: {e}")
            raise ToolExecutionError(f"Failed to update appointment: {e}")


class DeleteAppointmentTool(BaseTool):
    """Tool for deleting calendar appointments."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "delete_appointment",
            "description": "Delete a calendar appointment",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "Appointment item ID to delete"
                    },
                    "send_cancellation": {
                        "type": "boolean",
                        "description": "Send cancellation to attendees (for meetings)",
                        "default": True
                    }
                },
                "required": ["item_id"]
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Delete appointment."""
        item_id = kwargs.get("item_id")
        send_cancellation = kwargs.get("send_cancellation", True)

        try:
            # Get and delete the appointment
            item = self.ews_client.account.calendar.get(id=item_id)

            if send_cancellation and hasattr(item, "required_attendees") and item.required_attendees:
                item.cancel()
            else:
                item.delete()

            self.logger.info(f"Deleted appointment {item_id}")

            return format_success_response(
                "Appointment deleted successfully",
                item_id=item_id
            )

        except Exception as e:
            self.logger.error(f"Failed to delete appointment: {e}")
            raise ToolExecutionError(f"Failed to delete appointment: {e}")


class RespondToMeetingTool(BaseTool):
    """Tool for responding to meeting invitations."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "respond_to_meeting",
            "description": "Accept, tentatively accept, or decline a meeting invitation",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "Meeting invitation item ID"
                    },
                    "response": {
                        "type": "string",
                        "enum": ["Accept", "Tentative", "Decline"],
                        "description": "Response type"
                    },
                    "message": {
                        "type": "string",
                        "description": "Optional response message"
                    }
                },
                "required": ["item_id", "response"]
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Respond to meeting invitation."""
        item_id = kwargs.get("item_id")
        response = kwargs.get("response")
        message = kwargs.get("message", "")

        try:
            # Get the meeting request
            item = self.ews_client.account.calendar.get(id=item_id)

            # Send response
            if response == "Accept":
                item.accept(body=message)
                action = "accepted"
            elif response == "Tentative":
                item.tentatively_accept(body=message)
                action = "tentatively accepted"
            elif response == "Decline":
                item.decline(body=message)
                action = "declined"
            else:
                raise ToolExecutionError(f"Invalid response: {response}")

            self.logger.info(f"Meeting {item_id} {action}")

            return format_success_response(
                f"Meeting {action}",
                item_id=item_id,
                response=response
            )

        except Exception as e:
            self.logger.error(f"Failed to respond to meeting: {e}")
            raise ToolExecutionError(f"Failed to respond to meeting: {e}")
