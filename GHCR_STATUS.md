# GitHub Container Registry Status

## Current Status: 🔴 Not Available Yet

Pre-built Docker images are **not yet available** at `ghcr.io/azizmazrou/ews-mcp` because:

1. ✅ GitHub Actions workflows are configured
2. ✅ CI/CD pipeline is ready
3. ⏳ Code is in feature branch (not merged to main yet)
4. ⏳ Images will be published automatically once merged

## Why?

The GitHub Actions workflow (`.github/workflows/docker-publish.yml`) only triggers on:
- Push to `main` or `master` branch
- Version tags (`v1.0.0`, etc.)
- Manual workflow dispatch

Since we're currently on feature branch `claude/build-ews-mcp-server-011CUnS6qXguHKiiwUTtUtpx`, the images haven't been built yet.

## Timeline

**Once the PR is merged to main**:
1. GitHub Actions will automatically trigger
2. Multi-platform images will be built (amd64 + arm64)
3. Images will be published to GHCR
4. Available at: `ghcr.io/azizmazrou/ews-mcp:latest`

Estimated time: **5-10 minutes after merge**

## Workaround: Build Locally

Until images are published, build locally:

### Quick Build

```bash
# Clone repository
git clone https://github.com/azizmazrou/ews-mcp.git
cd ews-mcp

# Build image
docker build -t ews-mcp-server:latest .

# Run (Basic Auth example)
cat > .env <<EOF
EWS_SERVER_URL=https://mail.company.com/EWS/Exchange.asmx
EWS_EMAIL=user@company.com
EWS_AUTH_TYPE=basic
EWS_USERNAME=user@company.com
EWS_PASSWORD=your-password
EOF

docker run -d --name ews-mcp --env-file .env ews-mcp-server:latest
```

### Using Docker Compose

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f
```

## When Will GHCR Images Be Available?

**After merge to main**, you'll be able to:

```bash
# Pull pre-built image (FUTURE - after merge)
docker pull ghcr.io/azizmazrou/ews-mcp:latest

# Run immediately
docker run -d --env-file .env ghcr.io/azizmazrou/ews-mcp:latest
```

## Verify Workflow Status

Once merged, check build status:
1. Go to: https://github.com/azizmazrou/ews-mcp/actions
2. Look for "Build and Publish Docker Image" workflow
3. Verify it completes successfully
4. Check packages: https://github.com/azizmazrou/ews-mcp/pkgs/container/ews-mcp

## Current Build Time

Building locally takes:
- **First build**: ~3-5 minutes
- **Subsequent builds**: ~1-2 minutes (with cache)

## Documentation Updates

All references to `ghcr.io/azizmazrou/ews-mcp:latest` in documentation will work once:
1. Code is merged to main
2. GitHub Actions workflow completes
3. Images are published to GHCR

For now, use local builds as shown above.

## Need Pre-built Images Now?

If you need images immediately, you can:

1. **Fork the repository** and merge to your main branch
2. GitHub Actions will build images for your fork
3. Available at: `ghcr.io/YOUR-USERNAME/ews-mcp:latest`

Or wait for the official merge (recommended).
