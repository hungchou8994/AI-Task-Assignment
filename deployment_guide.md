# Hướng dẫn deploy Linux bằng PM2 (không dùng Docker)

Tài liệu này cập nhật theo implementation hiện tại của repo và file `ecosystem.config.cjs`.

## 1) Yêu cầu hệ thống

- Node.js 18+ (khuyến nghị 20+)
- Python 3.10+ (khuyến nghị 3.12)
- PostgreSQL (khuyến nghị 16)
- PM2 cài global:

```bash
npm install -g pm2
```

## 2) Chuẩn bị backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Cấu hình `.env`

Copy mẫu:

```bash
cp .env.example .env
```

Các biến quan trọng:

- `DATABASE_URL=postgresql://...`
- `AI_AGENT_PROVIDER=gemini` hoặc `openai`
- `GEMINI_API_KEY=...` (khi dùng Gemini)
- `OPENAI_API_KEY=...` (khi dùng OpenAI-compatible)
- `SESSION_SECRET_KEY=...` (khuyến nghị bắt buộc cho production)
- `CORS_ALLOWED_ORIGINS=["http://<server>:3003"]`

### Chạy migration

```bash
alembic upgrade head
```

## 3) Chuẩn bị frontend

```bash
cd ../frontend
npm ci
npm run build
```

## 4) Chạy bằng PM2

Repo đã có sẵn `ecosystem.config.cjs` (không cần tự tạo lại) với cấu hình mặc định:

- Backend: `ai-task-api` chạy trên port `8003`
- Frontend: `ai-task-frontend` serve `dist` trên port `3003`

Trích cấu hình hiện tại:

```javascript
module.exports = {
  apps: [
    {
      name: 'ai-task-api',
      script: 'venv/bin/uvicorn',
      args: 'app.main:app --host 0.0.0.0 --port 8003',
      cwd: './backend',
      interpreter: 'none',
      env: {
        PYTHONPATH: '.',
      },
    },
    {
      name: 'ai-task-frontend',
      script: 'pm2',
      args: 'serve dist 3003 --spa',
      cwd: './frontend',
    }
  ],
};
```

Khởi chạy:

```bash
pm2 start ecosystem.config.cjs
pm2 status
```

## 5) Kiểm tra sau deploy

```bash
curl http://127.0.0.1:8003/api/health
```

- Frontend: `http://<server>:3003`
- Backend API: `http://<server>:8003`
- Swagger: `http://<server>:8003/docs`

## 6) Lưu cấu hình PM2 sau reboot

```bash
pm2 save
pm2 startup
```

## 7) Lệnh vận hành thường dùng

```bash
pm2 logs ai-task-api --lines 200
pm2 logs ai-task-frontend --lines 200
pm2 restart ai-task-api
pm2 restart ai-task-frontend
```

## Ghi chú

- Nếu đổi port, sửa trực tiếp trong `ecosystem.config.cjs`.
- Frontend và backend đang chạy khác port; cần cấu hình reverse proxy hoặc CORS phù hợp.
