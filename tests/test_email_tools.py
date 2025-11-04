"""Tests for email tools."""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.tools.email_tools import (
    SendEmailTool,
    ReadEmailsTool,
    SearchEmailsTool,
    GetEmailDetailsTool,
    DeleteEmailTool,
    MoveEmailTool
)


@pytest.mark.asyncio
async def test_send_email_tool(mock_ews_client, sample_email):
    """Test sending email."""
    tool = SendEmailTool(mock_ews_client)

    # Mock message
    with patch('src.tools.email_tools.Message') as mock_message:
        mock_msg = MagicMock()
        mock_msg.id = "test-message-id"
        mock_message.return_value = mock_msg

        result = await tool.execute(**sample_email)

        assert result["success"] is True
        assert "sent successfully" in result["message"].lower()
        mock_msg.send.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_validation_error(mock_ews_client):
    """Test send email with invalid input."""
    tool = SendEmailTool(mock_ews_client)

    with pytest.raises(Exception):
        await tool.execute(
            to=[],  # Empty recipients should fail
            subject="",
            body=""
        )


@pytest.mark.asyncio
async def test_read_emails_tool(mock_ews_client):
    """Test reading emails."""
    tool = ReadEmailsTool(mock_ews_client)

    # Mock inbox items
    mock_email = MagicMock()
    mock_email.id = "email-1"
    mock_email.subject = "Test Subject"
    mock_email.sender.email_address = "sender@example.com"
    mock_email.datetime_received = "2025-01-01T10:00:00"
    mock_email.is_read = False
    mock_email.has_attachments = False
    mock_email.text_body = "Test body"

    mock_ews_client.account.inbox.all.return_value.order_by.return_value = [mock_email]

    result = await tool.execute(folder="inbox", max_results=10)

    assert result["success"] is True
    assert len(result["emails"]) > 0
    assert result["emails"][0]["subject"] == "Test Subject"


@pytest.mark.asyncio
async def test_search_emails_tool(mock_ews_client):
    """Test searching emails."""
    tool = SearchEmailsTool(mock_ews_client)

    # Mock search results
    mock_email = MagicMock()
    mock_email.id = "email-1"
    mock_email.subject = "Important Email"
    mock_email.sender.email_address = "important@example.com"

    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = [mock_email]

    mock_ews_client.account.inbox.all.return_value = mock_query

    result = await tool.execute(
        folder="inbox",
        subject_contains="Important"
    )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_delete_email_tool(mock_ews_client):
    """Test deleting email."""
    tool = DeleteEmailTool(mock_ews_client)

    # Mock email
    mock_email = MagicMock()
    mock_ews_client.account.inbox.get.return_value = mock_email

    result = await tool.execute(message_id="test-id", permanent=False)

    assert result["success"] is True
    mock_email.soft_delete.assert_called_once()


@pytest.mark.asyncio
async def test_move_email_tool(mock_ews_client):
    """Test moving email."""
    tool = MoveEmailTool(mock_ews_client)

    # Mock email
    mock_email = MagicMock()
    mock_ews_client.account.inbox.get.return_value = mock_email

    result = await tool.execute(
        message_id="test-id",
        destination_folder="sent"
    )

    assert result["success"] is True
    mock_email.move.assert_called_once()
