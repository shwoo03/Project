# Burp Suite MCP Web Interface

Burp Suite의 보안 테스팅 기능을 웹 브라우저에서 사용할 수 있게 해주는 통합 웹 인터페이스입니다.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Burp Suite with MCP extension enabled
- Docker (optional)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy environment file
copy .env.example .env

# Run the server
python main.py
# Server runs on http://localhost:10006
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
# Server runs on http://localhost:10007
```

### Docker Setup

```bash
# Build and run all services
docker-compose up -d
```

## 📁 Project Structure

```
burp-web-interface/
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── core/
│   │   ├── config.py           # Settings
│   │   └── mcp_client.py       # Burp MCP client
│   ├── routers/
│   │   ├── proxy.py            # Proxy history API
│   │   ├── repeater.py         # Repeater API
│   │   ├── intruder.py         # Intruder API
│   │   ├── scanner.py          # Scanner API
│   │   └── collaborator.py     # Collaborator API
│   └── models/
│       └── request.py          # Pydantic models
├── frontend/
│   └── (React + TypeScript)
├── docker-compose.yml
└── README.md
```

## 🔧 Configuration

Edit `.env` file in the backend directory:

```env
# Burp Suite MCP Configuration
BURP_MCP_HOST=localhost
BURP_MCP_PORT=9999
```

## 📚 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/proxy/history` | Get proxy history |
| `GET /api/proxy/request/{id}` | Get request details |
| `POST /api/repeater/send` | Send HTTP request |
| `POST /api/intruder/attack` | Start Intruder attack |
| `POST /api/scanner/scan` | Start vulnerability scan |
| `POST /api/collaborator/payload` | Generate Collaborator payload |

## 🛡️ Features

- **Proxy History Viewer**: Browse all intercepted HTTP requests
- **Repeater**: Edit and resend HTTP requests
- **Intruder**: Automated attack configuration
- **Scanner**: Vulnerability scanning
- **Collaborator**: Out-of-band testing

## 📄 License

MIT License
