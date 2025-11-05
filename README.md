# EWS MCP Server

A complete Model Context Protocol (MCP) server that interfaces with Microsoft Exchange Web Services (EWS), enabling AI assistants to interact with Exchange for email, calendar, contacts, and task operations.

> **📦 Docker Images**: Pre-built images will be available at `ghcr.io/azizmazrou/ews-mcp:latest` once merged to main branch. For now, build locally with `docker build -t ews-mcp-server .` - See [GHCR_STATUS.md](GHCR_STATUS.md) for details.

## Features

- ✅ **Email Operations**: Send, read, search, delete, move emails with attachment support
- ✅ **Calendar Management**: Create, update, delete appointments, respond to meetings
- ✅ **Contact Management**: Full CRUD operations for Exchange contacts
- ✅ **Task Management**: Create and manage Exchange tasks
- ✅ **Multi-Authentication**: Support for OAuth2, Basic Auth, and NTLM
- ✅ **Timezone Support**: Proper handling of timezones (tested with Asia/Riyadh, UTC, etc.)
- ✅ **HTTP/SSE Transport**: Support for both stdio and HTTP/SSE for web clients (n8n compatible)
- ✅ **Docker Ready**: Production-ready containerization with best practices
- ✅ **Rate Limiting**: Built-in rate limiting to prevent API abuse
- ✅ **Error Handling**: Comprehensive error handling and logging
- ✅ **Audit Logging**: Track all operations for compliance

## Quick Start

### Using Pre-built Docker Image (Easiest)

Choose your authentication method:

#### Option 1: Basic Authentication (Fastest Setup - 1 minute)

**Best for**: Testing, on-premises Exchange, quick demos

```bash
# Pull the latest image
docker pull ghcr.io/azizmazrou/ews-mcp:latest

# 3. Create .env file with Basic Auth
cat > .env <<EOF
EWS_SERVER_URL=https://mail.company.com/EWS/Exchange.asmx
EWS_EMAIL=user@company.com
EWS_AUTODISCOVER=false
EWS_AUTH_TYPE=basic
EWS_USERNAME=user@company.com
EWS_PASSWORD=your-password
TIMEZONE=UTC
LOG_LEVEL=INFO
EOF

# 4. Run the container
docker run -d \
  --name ews-mcp-server \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  ghcr.io/azizmazrou/ews-mcp:latest

# View logs - look for "✓ Successfully connected to Exchange"
docker logs -f ews-mcp-server
```

**Or use the pre-configured template**:
```bash
cp .env.basic.example .env
# Edit .env with your credentials
docker run -d --name ews-mcp --env-file .env ghcr.io/azizmazrou/ews-mcp:latest
```

#### Option 2: OAuth2 Authentication (Production - Office 365)

**Best for**: Office 365, production environments, enhanced security

```bash
# Pull the latest image
docker pull ghcr.io/azizmazrou/ews-mcp:latest

# Use pre-configured OAuth2 template
cp .env.oauth2.example .env

# Edit .env with your Azure AD credentials:
# - EWS_CLIENT_ID (from Azure AD app registration)
# - EWS_CLIENT_SECRET (from Azure AD app registration)
# - EWS_TENANT_ID (from Azure AD app registration)
# See OAuth2 Setup section below for detailed instructions

# Run the container
docker run -d \
  --name ews-mcp-server \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  ghcr.io/azizmazrou/ews-mcp:latest

# View logs
docker logs -f ews-mcp-server
```

### Building from Source

```bash
# Clone repository
git clone https://github.com/azizmazrou/ews-mcp.git
cd ews-mcp

# Copy and configure environment
cp .env.example .env
# Edit .env with your Exchange credentials

# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f
```

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run server
python -m src.main
```

## Configuration

Choose your authentication method based on your Exchange setup:

| Auth Method | Use Case | Setup Time | Security |
|-------------|----------|------------|----------|
| **Basic Auth** | Testing, On-premises Exchange | ⚡ 1 minute | ⚠️ Moderate |
| **OAuth2** | Office 365, Production | 🕐 10 minutes | ✅ High |
| **NTLM** | Windows Domain, On-premises | 🕐 5 minutes | ⚠️ Moderate |

### Basic Authentication (Easiest - For Testing/On-Premises)

**Best for**: Quick testing, on-premises Exchange servers, legacy setups

**⚠️ Note**: Basic Auth is being deprecated by Microsoft for Office 365. Use OAuth2 for production Office 365 environments.

#### Quick Setup (30 seconds)

1. **Create `.env` file**:
   ```bash
   cat > .env <<EOF
   # Exchange Server
   EWS_SERVER_URL=https://mail.company.com/EWS/Exchange.asmx
   EWS_EMAIL=user@company.com
   EWS_AUTODISCOVER=false

   # Basic Authentication
   EWS_AUTH_TYPE=basic
   EWS_USERNAME=user@company.com
   EWS_PASSWORD=your-password

   # Server Configuration
   LOG_LEVEL=INFO
   EOF
   ```

2. **Run the server**:
   ```bash
   docker run -d --name ews-mcp --env-file .env ghcr.io/azizmazrou/ews-mcp:latest
   ```

3. **Verify it's working**:
   ```bash
   docker logs ews-mcp
   # Look for "✓ Successfully connected to Exchange"
   ```

That's it! The server is now running with Basic Authentication.

#### Using Pre-configured Template

```bash
# Copy Basic Auth template
cp .env.basic.example .env

# Edit with your credentials
nano .env  # or your preferred editor

# Run
docker run -d --env-file .env ghcr.io/azizmazrou/ews-mcp:latest
```

#### Interactive Setup Script

For an even easier setup, use the interactive script:

```bash
# Run the setup script
./scripts/setup-basic-auth.sh

# Follow the prompts to:
# - Enter your Exchange server
# - Provide email and password
# - Automatically create .env
# - Pull Docker image
# - Start the server
```

#### For On-Premises Exchange

```bash
# Find your EWS endpoint
# Usually: https://mail.yourcompany.com/EWS/Exchange.asmx
# Or: https://exchange.yourcompany.com/EWS/Exchange.asmx

cat > .env <<EOF
EWS_SERVER_URL=https://mail.yourcompany.com/EWS/Exchange.asmx
EWS_EMAIL=user@yourcompany.com
EWS_AUTODISCOVER=false
EWS_AUTH_TYPE=basic
EWS_USERNAME=user@yourcompany.com
EWS_PASSWORD=your-password
LOG_LEVEL=INFO
EOF
```

#### Troubleshooting Basic Auth

**Problem: "Authentication failed"**
- ✅ Verify username and password are correct
- ✅ Check if account requires domain: `DOMAIN\username`
- ✅ Ensure Basic Auth is enabled on Exchange server
- ✅ Try with Outlook Web Access (OWA) first to verify credentials

**Problem: "Connection refused"**
- ✅ Verify EWS_SERVER_URL is correct
- ✅ Test with: `curl https://mail.company.com/EWS/Exchange.asmx`
- ✅ Check firewall/network access
- ✅ Try autodiscovery: Set `EWS_AUTODISCOVER=true`

### OAuth2 Authentication (Recommended for Office 365)

**Best for**: Office 365/Microsoft 365, production environments, modern security

#### Quick Setup (10 minutes)

1. **Use pre-configured template**:
   ```bash
   cp .env.oauth2.example .env
   ```

2. **Register app in Azure AD** (see detailed steps below)

3. **Update `.env` with Azure AD credentials**:
   ```bash
   EWS_SERVER_URL=https://outlook.office365.com/EWS/Exchange.asmx
   EWS_EMAIL=user@company.com
   EWS_AUTH_TYPE=oauth2
   EWS_CLIENT_ID=your-azure-app-client-id
   EWS_CLIENT_SECRET=your-azure-app-client-secret
   EWS_TENANT_ID=your-azure-tenant-id
   ```

4. **Run the server**:
   ```bash
   docker run -d --env-file .env ghcr.io/azizmazrou/ews-mcp:latest
   ```

## OAuth2 Setup (Azure AD)

1. **Register Application in Azure AD**:
   - Go to Azure Portal → Azure Active Directory → App registrations
   - Click "New registration"
   - Name: "EWS MCP Server"
   - Supported account types: "Accounts in this organizational directory only"
   - Click "Register"

2. **Configure API Permissions**:
   - Go to "API permissions"
   - Click "Add a permission"
   - Select "Office 365 Exchange Online"
   - Select "Application permissions"
   - Add: `full_access_as_app` or specific permissions like:
     - `Mail.ReadWrite`
     - `Calendars.ReadWrite`
     - `Contacts.ReadWrite`
     - `Tasks.ReadWrite`
   - Click "Grant admin consent"

3. **Create Client Secret**:
   - Go to "Certificates & secrets"
   - Click "New client secret"
   - Description: "EWS MCP Secret"
   - Expires: Choose appropriate duration
   - Click "Add" and **copy the secret value immediately**

4. **Get IDs**:
   - **Client ID**: From "Overview" page
   - **Tenant ID**: From "Overview" page
   - **Client Secret**: From step 3 above

5. **Update .env**:
   ```bash
   EWS_CLIENT_ID=<your-client-id>
   EWS_CLIENT_SECRET=<your-client-secret>
   EWS_TENANT_ID=<your-tenant-id>
   ```

## Usage with Claude Desktop

Add to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### Using Pre-built Image from GHCR (Recommended)

```json
{
  "mcpServers": {
    "ews": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "--env-file",
        "/absolute/path/to/.env",
        "ghcr.io/azizmazrou/ews-mcp:latest"
      ]
    }
  }
}
```

### Using Locally Built Image

```json
{
  "mcpServers": {
    "ews": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "--env-file",
        "/path/to/ews-mcp/.env",
        "ews-mcp-server"
      ]
    }
  }
}
```

### Using Local Python (Development)

```json
{
  "mcpServers": {
    "ews": {
      "command": "python",
      "args": ["-m", "src.main"],
      "cwd": "/path/to/ews-mcp",
      "env": {
        "EWS_EMAIL": "user@company.com",
        "EWS_AUTH_TYPE": "oauth2",
        "EWS_CLIENT_ID": "your-client-id",
        "EWS_CLIENT_SECRET": "your-secret",
        "EWS_TENANT_ID": "your-tenant"
      }
    }
  }
}
```

## Docker Images

Pre-built Docker images are automatically published to GitHub Container Registry:

```bash
# Pull latest version
docker pull ghcr.io/azizmazrou/ews-mcp:latest

# Pull specific version
docker pull ghcr.io/azizmazrou/ews-mcp:1.0.0

# Pull development version
docker pull ghcr.io/azizmazrou/ews-mcp:main
```

**Available Tags:**
- `latest` - Latest stable release
- `v*.*.*` - Specific version (e.g., `v1.0.0`)
- `main` - Latest commit on main branch
- `sha-<commit>` - Specific commit

**Multi-platform Support:**
- `linux/amd64` - x86_64 systems
- `linux/arm64` - ARM64 systems (Apple Silicon, ARM servers)

## Available Tools

### Email Tools

- **send_email**: Send emails with attachments and CC/BCC
- **read_emails**: Read emails from specified folder
- **search_emails**: Search with advanced filters
- **get_email_details**: Get full email details
- **delete_email**: Delete or permanently remove emails
- **move_email**: Move emails between folders

### Calendar Tools

- **create_appointment**: Schedule meetings with attendees
- **get_calendar**: Retrieve calendar events
- **update_appointment**: Modify existing appointments
- **delete_appointment**: Cancel appointments/meetings
- **respond_to_meeting**: Accept/decline meeting invitations

### Contact Tools

- **create_contact**: Add new contacts
- **search_contacts**: Find contacts by name/email
- **get_contacts**: List all contacts
- **update_contact**: Modify contact information
- **delete_contact**: Remove contacts

### Task Tools

- **create_task**: Create new tasks
- **get_tasks**: List tasks (filter by status)
- **update_task**: Modify task details
- **complete_task**: Mark tasks as complete
- **delete_task**: Remove tasks

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_email_tools.py

# Run only unit tests (skip integration)
pytest -m "not integration"
```

## Development

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run linter
ruff check src/

# Format code
black src/

# Type checking
mypy src/

# Security check
bandit -r src/
```

## Architecture

```
EWS MCP Server
├── MCP Protocol Layer (stdio/SSE)
├── Tool Registry (Email, Calendar, Contacts, Tasks)
├── EWS Client (exchangelib wrapper)
├── Authentication (OAuth2/Basic/NTLM)
├── Middleware (Rate Limiting, Error Handling, Audit)
└── Exchange Web Services API
```

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common issues and solutions.

## Documentation

- [Setup Guide](docs/SETUP.md) - Step-by-step setup instructions
- [Deployment Guide](docs/DEPLOYMENT.md) - Deploy to various platforms
- [GHCR Guide](docs/GHCR.md) - Using pre-built Docker images
- [API Documentation](docs/API.md) - Complete tool reference
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [Architecture Overview](docs/ARCHITECTURE.md) - Technical deep dive

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please read the contributing guidelines before submitting PRs.

## Support

For issues and feature requests, please use the GitHub issue tracker.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.
