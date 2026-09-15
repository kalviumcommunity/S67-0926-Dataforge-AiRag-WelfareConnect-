import { app } from './app';
import { env } from './config/env';

const server = app.listen(env.PORT, () => {
  console.log(`=======================================================`);
  console.log(`🚀 ${env.APP_NAME} Backend Service Running`);
  console.log(`📡 Port: ${env.PORT}`);
  console.log(`🌍 Environment: ${env.NODE_ENV}`);
  console.log(`🩺 Health Check: http://localhost:${env.PORT}/health`);
  console.log(`🔗 API Base: http://localhost:${env.PORT}${env.API_PREFIX}`);
  console.log(`=======================================================`);
});

process.on('SIGTERM', () => {
  console.log('SIGTERM signal received: closing HTTP server');
  server.close(() => {
    console.log('HTTP server closed');
  });
});
