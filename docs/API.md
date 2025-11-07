# API Documentation

Complete reference for all EWS MCP Server tools.

## Email Tools

### send_email

Send an email through Exchange with optional attachments and CC/BCC.

**Input Schema:**
```json
{
  "to": ["recipient@example.com"],
  "subject": "Email Subject",
  "body": "Email body (HTML supported)",
  "cc": ["cc@example.com"],           // Optional
  "bcc": ["bcc@example.com"],         // Optional
  "importance": "Normal",             // Optional: Low, Normal, High
  "attachments": ["/path/to/file"]    // Optional
}
```

**Response:**
```json
{
  "success": true,
  "message": "Email sent successfully",
  "message_id": "AAMkAGI...",
  "sent_time": "2025-01-04T10:00:00",
  "recipients": ["recipient@example.com"]
}
```

### read_emails

Read emails from a specified folder.

**Input Schema:**
```json
{
  "folder": "inbox",          // inbox, sent, drafts, deleted, junk
  "max_results": 50,          // Max: 1000
  "unread_only": false
}
```

**Response:**
```json
{
  "success": true,
  "message": "Retrieved 10 emails",
  "emails": [
    {
      "message_id": "AAMkAGI...",
      "subject": "Meeting Tomorrow",
      "from": "sender@example.com",
      "received_time": "2025-01-04T09:30:00",
      "is_read": false,
      "has_attachments": true,
      "preview": "Please review the attached..."
    }
  ],
  "total_count": 10,
  "folder": "inbox"
}
```

### search_emails

Search emails with advanced filters.

**Input Schema:**
```json
{
  "folder": "inbox",
  "subject_contains": "report",
  "from_address": "boss@example.com",
  "has_attachments": true,
  "is_read": false,
  "start_date": "2025-01-01T00:00:00",
  "end_date": "2025-01-31T23:59:59",
  "max_results": 50
}
```

### get_email_details

Get full details of a specific email.

**Input Schema:**
```json
{
  "message_id": "AAMkAGI..."
}
```

**Response:**
```json
{
  "success": true,
  "message": "Email details retrieved",
  "email": {
    "message_id": "AAMkAGI...",
    "subject": "Project Update",
    "from": "sender@example.com",
    "to": ["you@example.com"],
    "cc": ["team@example.com"],
    "body": "Full email body text",
    "body_html": "<html>...</html>",
    "received_time": "2025-01-04T09:00:00",
    "sent_time": "2025-01-04T08:58:00",
    "is_read": true,
    "has_attachments": true,
    "importance": "High",
    "attachments": ["report.pdf", "data.xlsx"]
  }
}
```

### delete_email

Delete an email (soft delete to trash or permanent delete).

**Input Schema:**
```json
{
  "message_id": "AAMkAGI...",
  "permanent": false    // true for hard delete
}
```

### move_email

Move an email to a different folder.

**Input Schema:**
```json
{
  "message_id": "AAMkAGI...",
  "destination_folder": "sent"    // inbox, sent, drafts, deleted, junk
}
```

### update_email

Update email properties such as read status, flags, categories, and importance.

**Input Schema:**
```json
{
  "message_id": "AAMkAGI...",
  "is_read": true,                         // Optional: mark as read/unread
  "categories": ["Important", "Work"],     // Optional: email categories/labels
  "flag_status": "Flagged",                // Optional: NotFlagged, Flagged, Complete
  "importance": "High"                     // Optional: Low, Normal, High
}
```

**Response:**
```json
{
  "success": true,
  "message": "Email updated successfully",
  "message_id": "AAMkAGI...",
  "updates": {
    "is_read": true,
    "categories": ["Important", "Work"],
    "flag_status": "Flagged",
    "importance": "High"
  }
}
```

### list_attachments

List all attachments for a specific email message.

**Input Schema:**
```json
{
  "message_id": "AAMkAGI...",
  "include_inline": true        // Optional: include inline images
}
```

**Response:**
```json
{
  "success": true,
  "message": "Found 2 attachment(s)",
  "message_id": "AAMkAGI...",
  "count": 2,
  "attachments": [
    {
      "id": "AAMkAGI1AAAA=",
      "name": "report.pdf",
      "size": 245760,
      "content_type": "application/pdf",
      "is_inline": false,
      "content_id": null
    },
    {
      "id": "AAMkAGI2AAAA=",
      "name": "logo.png",
      "size": 8192,
      "content_type": "image/png",
      "is_inline": true,
      "content_id": "image001"
    }
  ]
}
```

### download_attachment

Download an email attachment as base64 or save to file.

**Input Schema:**
```json
{
  "message_id": "AAMkAGI...",
  "attachment_id": "AAMkAGI1AAAA=",
  "return_as": "base64",           // base64 or file_path
  "save_path": "/path/to/file"     // Required if return_as is file_path
}
```

**Response (base64):**
```json
{
  "success": true,
  "message": "Attachment downloaded successfully",
  "message_id": "AAMkAGI...",
  "attachment_id": "AAMkAGI1AAAA=",
  "name": "report.pdf",
  "size": 245760,
  "content_type": "application/pdf",
  "content_base64": "JVBERi0xLjQKJeLjz9MKMy..."
}
```

**Response (file_path):**
```json
{
  "success": true,
  "message": "Attachment saved successfully",
  "message_id": "AAMkAGI...",
  "attachment_id": "AAMkAGI1AAAA=",
  "name": "report.pdf",
  "size": 245760,
  "content_type": "application/pdf",
  "file_path": "/downloads/report.pdf"
}
```

## Calendar Tools

### create_appointment

Create a calendar appointment or meeting.

**Input Schema:**
```json
{
  "subject": "Team Standup",
  "start_time": "2025-01-05T10:00:00",
  "end_time": "2025-01-05T10:30:00",
  "location": "Conference Room A",
  "body": "Daily standup meeting",
  "attendees": ["team1@example.com", "team2@example.com"],
  "is_all_day": false,
  "reminder_minutes": 15
}
```

**Response:**
```json
{
  "success": true,
  "message": "Appointment created successfully",
  "item_id": "AAMkAGV...",
  "subject": "Team Standup",
  "start_time": "2025-01-05T10:00:00",
  "end_time": "2025-01-05T10:30:00"
}
```

### get_calendar

Retrieve calendar events for a date range.

**Input Schema:**
```json
{
  "start_date": "2025-01-01T00:00:00",    // Optional, defaults to today
  "end_date": "2025-01-07T23:59:59",      // Optional, defaults to +7 days
  "max_results": 50
}
```

**Response:**
```json
{
  "success": true,
  "message": "Retrieved 5 events",
  "events": [
    {
      "item_id": "AAMkAGV...",
      "subject": "Team Meeting",
      "start": "2025-01-05T10:00:00",
      "end": "2025-01-05T11:00:00",
      "location": "Room A",
      "organizer": "manager@example.com",
      "is_all_day": false,
      "attendees": ["you@example.com", "colleague@example.com"]
    }
  ],
  "start_date": "2025-01-01T00:00:00",
  "end_date": "2025-01-07T23:59:59"
}
```

### update_appointment

Update an existing appointment.

**Input Schema:**
```json
{
  "item_id": "AAMkAGV...",
  "subject": "Updated Meeting Title",
  "start_time": "2025-01-05T11:00:00",
  "end_time": "2025-01-05T12:00:00",
  "location": "Room B",
  "body": "Updated description"
}
```

### delete_appointment

Delete a calendar appointment.

**Input Schema:**
```json
{
  "item_id": "AAMkAGV...",
  "send_cancellation": true    // Send cancellation to attendees
}
```

### respond_to_meeting

Respond to a meeting invitation.

**Input Schema:**
```json
{
  "item_id": "AAMkAGV...",
  "response": "Accept",        // Accept, Tentative, Decline
  "message": "I'll be there"   // Optional response message
}
```

### check_availability

Get free/busy information for one or more users in a specified time range.

**Input Schema:**
```json
{
  "email_addresses": ["user1@example.com", "user2@example.com"],
  "start_time": "2025-01-15T09:00:00+00:00",
  "end_time": "2025-01-15T17:00:00+00:00",
  "interval_minutes": 30        // Optional: time slot granularity (15-1440)
}
```

**Response:**
```json
{
  "success": true,
  "message": "Availability retrieved for 2 user(s)",
  "availability": [
    {
      "email": "user1@example.com",
      "view_type": "Detailed",
      "merged_free_busy": "00002222000011110000",
      "free_busy_legend": {
        "0": "Free",
        "1": "Tentative",
        "2": "Busy",
        "3": "OutOfOffice",
        "4": "NoData"
      },
      "calendar_events": [
        {
          "start": "2025-01-15T10:00:00+00:00",
          "end": "2025-01-15T11:00:00+00:00",
          "busy_type": "Busy",
          "details": null
        }
      ]
    }
  ],
  "time_range": {
    "start": "2025-01-15T09:00:00+00:00",
    "end": "2025-01-15T17:00:00+00:00",
    "interval_minutes": 30
  }
}
```

## Contact Tools

### create_contact

Create a new contact in Exchange.

**Input Schema:**
```json
{
  "given_name": "John",
  "surname": "Doe",
  "email_address": "john.doe@example.com",
  "phone_number": "+1-555-0100",
  "company": "Acme Corp",
  "job_title": "Software Engineer",
  "department": "Engineering"
}
```

### search_contacts

Search contacts by name or email.

**Input Schema:**
```json
{
  "query": "john",
  "max_results": 50
}
```

### get_contacts

List all contacts.

**Input Schema:**
```json
{
  "max_results": 50
}
```

### update_contact

Update an existing contact.

**Input Schema:**
```json
{
  "item_id": "AAMkAGU...",
  "given_name": "Jane",
  "job_title": "Senior Engineer",
  "phone_number": "+1-555-0101"
}
```

### delete_contact

Delete a contact.

**Input Schema:**
```json
{
  "item_id": "AAMkAGU..."
}
```

### resolve_names

Resolve partial names or email addresses to full contact information from Active Directory or Contacts.

**Input Schema:**
```json
{
  "name_query": "john",                  // Partial name or email to resolve
  "return_full_info": false,             // Optional: return detailed contact info
  "search_scope": "All"                  // Optional: Contacts, ActiveDirectory, All
}
```

**Response:**
```json
{
  "success": true,
  "message": "Found 2 match(es) for 'john'",
  "query": "john",
  "count": 2,
  "results": [
    {
      "name": "John Doe",
      "email": "john.doe@example.com",
      "routing_type": "SMTP",
      "mailbox_type": "Mailbox"
    },
    {
      "name": "Johnny Smith",
      "email": "johnny.smith@example.com",
      "routing_type": "SMTP",
      "mailbox_type": "Mailbox",
      "contact_details": {          // Only if return_full_info is true
        "given_name": "Johnny",
        "surname": "Smith",
        "company": "Acme Corp",
        "job_title": "Manager",
        "phone_numbers": ["+1-555-0200"],
        "department": "Sales"
      }
    }
  ]
}
```

## Task Tools

### create_task

Create a new task.

**Input Schema:**
```json
{
  "subject": "Complete project report",
  "body": "Q4 financial report",
  "due_date": "2025-01-31T17:00:00",
  "start_date": "2025-01-15T09:00:00",
  "importance": "High",
  "reminder_time": "2025-01-30T09:00:00"
}
```

### get_tasks

List tasks with optional filtering.

**Input Schema:**
```json
{
  "include_completed": false,
  "max_results": 50
}
```

**Response:**
```json
{
  "success": true,
  "message": "Retrieved 3 tasks",
  "tasks": [
    {
      "item_id": "AAMkAGT...",
      "subject": "Complete report",
      "status": "InProgress",
      "percent_complete": 50,
      "is_complete": false,
      "due_date": "2025-01-31T17:00:00",
      "importance": "High"
    }
  ]
}
```

### update_task

Update an existing task.

**Input Schema:**
```json
{
  "item_id": "AAMkAGT...",
  "subject": "Updated task name",
  "percent_complete": 75,
  "importance": "Normal"
}
```

### complete_task

Mark a task as complete.

**Input Schema:**
```json
{
  "item_id": "AAMkAGT..."
}
```

### delete_task

Delete a task.

**Input Schema:**
```json
{
  "item_id": "AAMkAGT..."
}
```

## Search Tools

### advanced_search

Perform complex multi-criteria searches across multiple mailbox folders with extensive filtering options.

**Input Schema:**
```json
{
  "search_filter": {
    "keywords": "quarterly report",        // Search in subject and body
    "from_address": "boss@example.com",
    "to_address": "team@example.com",
    "subject": "Q4",
    "body": "financial",
    "has_attachments": true,
    "importance": "High",
    "categories": ["Work", "Important"],
    "is_read": false,
    "start_date": "2025-01-01T00:00:00+00:00",
    "end_date": "2025-01-31T23:59:59+00:00"
  },
  "search_scope": ["inbox", "sent"],      // Folders to search
  "max_results": 100,                      // Max: 1000
  "sort_by": "datetime_received",          // datetime_received, datetime_sent, from, subject, importance
  "sort_order": "descending"               // ascending or descending
}
```

**Response:**
```json
{
  "success": true,
  "message": "Found 15 result(s)",
  "count": 15,
  "results": [
    {
      "message_id": "AAMkAGI...",
      "subject": "Q4 Quarterly Report - Financial Results",
      "from": "boss@example.com",
      "to": ["team@example.com"],
      "received_time": "2025-01-15T14:30:00+00:00",
      "is_read": false,
      "has_attachments": true,
      "importance": "High",
      "categories": ["Work", "Important"],
      "body_preview": "Please review the attached quarterly financial report...",
      "folder": "inbox"
    }
  ],
  "search_filter": { /* original search criteria */ },
  "folders_searched": ["inbox", "sent"]
}
```

## Folder Tools

### list_folders

Get mailbox folder hierarchy with configurable depth and details.

**Input Schema:**
```json
{
  "parent_folder": "root",         // root, inbox, sent, drafts, deleted, junk, calendar, contacts, tasks
  "depth": 2,                      // 1-10: folder tree traversal depth
  "include_hidden": false,         // Include system/hidden folders
  "include_counts": true           // Include item and unread counts
}
```

**Response:**
```json
{
  "success": true,
  "message": "Listed 12 folder(s)",
  "total_folders": 12,
  "parent_folder": "root",
  "depth": 2,
  "folder_tree": {
    "id": "AAMkAGF...",
    "name": "Root",
    "parent_folder_id": "",
    "folder_class": "IPF",
    "child_folder_count": 4,
    "total_count": 0,
    "unread_count": 0,
    "children": [
      {
        "id": "AAMkAGI...",
        "name": "Inbox",
        "parent_folder_id": "AAMkAGF...",
        "folder_class": "IPF.Note",
        "child_folder_count": 3,
        "total_count": 245,
        "unread_count": 12,
        "children": [
          {
            "id": "AAMkAGJ...",
            "name": "Projects",
            "parent_folder_id": "AAMkAGI...",
            "folder_class": "IPF.Note",
            "child_folder_count": 0,
            "total_count": 48,
            "unread_count": 5
          }
        ]
      },
      {
        "id": "AAMkAGK...",
        "name": "Sent Items",
        "parent_folder_id": "AAMkAGF...",
        "folder_class": "IPF.Note",
        "child_folder_count": 0,
        "total_count": 532,
        "unread_count": 0
      }
    ]
  }
}
```

## Error Responses

All tools return error responses in the following format:

```json
{
  "success": false,
  "error": "Error description",
  "error_type": "ValidationError",
  "is_retryable": false
}
```

### Common Error Types

- `ValidationError`: Invalid input parameters
- `AuthenticationError`: Authentication failed
- `ConnectionError`: Cannot connect to Exchange
- `RateLimitError`: Too many requests
- `ToolExecutionError`: Tool execution failed

## Rate Limiting

Default: 25 requests per minute per user

When rate limited, you'll receive:
```json
{
  "success": false,
  "error": "Rate limit exceeded: maximum 25 requests per minute",
  "error_type": "RateLimitError",
  "is_retryable": true
}
```
