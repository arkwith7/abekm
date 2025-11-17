# Office Generator Service

Modern Office document generator service powered by Node.js. Currently supports PowerPoint (PPTX) generation with PptxGenJS. Architecture designed for future expansion to DOCX and XLSX.

## Features

- ✅ **PowerPoint (PPTX)** - Full support with charts, themes, and advanced layouts
- 🚧 **Word (DOCX)** - Planned (Python python-docx recommended for now)
- 🚧 **Excel (XLSX)** - Planned (Python openpyxl recommended for now)

## Quick Start

### Prerequisites

- Node.js >= 18.0.0
- npm >= 9.0.0

### Installation

```bash
npm install
```

### Configuration

```bash
cp .env.example .env
# Edit .env with your settings
```

### Run

```bash
# Development
npm run dev

# Production
npm start
```

### Test

```bash
npm test
```

## API Endpoints

### PPTX Generation

**POST** `/api/pptx/generate`

Request body:
```json
{
  "deck_spec": {
    "topic": "My Presentation",
    "max_slides": 10,
    "slides": [
      {
        "title": "Title Slide",
        "key_message": "Subtitle here",
        "bullets": [],
        "layout": "title"
      },
      {
        "title": "Content",
        "key_message": "Key point",
        "bullets": ["Point 1", "Point 2", "Point 3"],
        "diagram": {
          "type": "chart",
          "chart": {
            "type": "bar",
            "title": "Sales",
            "categories": ["Q1", "Q2", "Q3"],
            "series": [{ "data": [10, 20, 30] }]
          }
        }
      }
    ]
  },
  "options": {
    "template_style": "business",
    "include_charts": true
  }
}
```

Response: PPTX file download

### Health Check

**GET** `/health`

Response:
```json
{
  "status": "ok",
  "service": "office-generator",
  "version": "1.0.0",
  "uptime": 12345
}
```

## Architecture

```
office-generator-service/
├── src/
│   ├── routes/          # API endpoints (pptx, docx, xlsx)
│   ├── generators/      # Document generation engines
│   │   └── pptx/       # PptxGenJS implementation
│   ├── schemas/         # JSON schemas & validators
│   ├── utils/           # Logger, errors, metrics
│   ├── middleware/      # Request ID, auth, error handling
│   └── config/          # Themes, environment config
├── tests/               # Jest tests
└── server.js            # Express server entry point
```

## Integration with Python Backend

Add to your Python `requirements.txt`:
```python
httpx>=0.25.0  # For async HTTP calls
```

Example Python integration:
```python
import httpx

async def generate_pptx(deck_spec: dict) -> bytes:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:3001/api/pptx/generate",
            json={"deck_spec": deck_spec, "options": {"template_style": "business"}},
            timeout=60.0
        )
        return response.content
```

## Docker Deployment

```bash
docker build -t office-generator:latest .
docker run -p 3001:3001 --env-file .env office-generator:latest
```

## License

MIT
