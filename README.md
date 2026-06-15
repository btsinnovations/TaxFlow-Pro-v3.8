# TaxFlow Pro Frontend

**Standalone React Web UI**

This is the frontend-only package. It provides a web interface for uploading and managing bank statements. No Python, no backend code, no OCR models.

## Quick Start

```bash
# Install
bash setup.sh

# Start dev server
bash start.sh
```

Then open http://localhost:5173

## Connecting to a Backend

The frontend needs a TaxFlow Pro backend to process statements. Configure the API URL in `.env`:

```bash
# Copy template
cp .env.example .env

# Edit .env — set your backend URL
VITE_API_BASE_URL=http://localhost:8000/api
```

### Backend Options

| Setup | URL | Use Case |
|-------|-----|----------|
| Same machine | `http://localhost:8000/api` | Running both on one computer |
| Another computer | `http://192.168.1.xxx:8000/api` | LAN access |
| Remote server | `https://api.yourdomain.com/api` | Hosted backend |

## System Requirements

- Node.js 20+
- npm 10+

## Privacy

The frontend itself is just a static web app. All statement processing happens on the **backend server** you configure in `.env`. No data is sent anywhere else.
