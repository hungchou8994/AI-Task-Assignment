module.exports = {
  apps: [
    {
      name: 'ai-task-api',
      script: 'venv/bin/uvicorn',
      args: 'app.main:app --host 0.0.0.0 --port 8003',
      cwd: './backend',
      interpreter: 'none', // PM2 will use the binary in 'script' directly
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
