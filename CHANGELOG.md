# Changelog

All notable changes to EWS MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-04

### Added
- Initial release of EWS MCP Server
- Email operations (send, read, search, delete, move)
- Calendar management (create, update, delete, respond to meetings)
- Contact management (full CRUD operations)
- Task management (create, update, complete, delete)
- OAuth2 authentication support
- Basic authentication support
- NTLM authentication support
- Docker containerization
- Rate limiting middleware
- Comprehensive error handling
- Audit logging
- Full test suite
- Complete documentation

### Features
- 21 tools covering all major Exchange operations
- Multi-authentication support (OAuth2, Basic, NTLM)
- Production-ready Docker deployment
- Built-in rate limiting
- Structured logging
- Pydantic validation for all inputs
- Automatic retry logic for connection issues
- Support for autodiscovery and manual configuration

### Documentation
- Complete README with quick start guide
- OAuth2 setup instructions
- Claude Desktop integration guide
- API documentation
- Troubleshooting guide
- Architecture overview
- Deployment guide

### Testing
- Unit tests for all tools
- Authentication tests
- EWS client tests
- Integration test framework
- Mock fixtures for testing
- 80%+ code coverage

## [Unreleased]

### Planned Features
- Folder management tools
- Advanced attachment handling
- Search filters and saved searches
- Webhook support for notifications
- Microsoft Graph API integration
- Caching for improved performance
- Web UI for configuration
- Metrics and monitoring
- Kubernetes deployment manifests
