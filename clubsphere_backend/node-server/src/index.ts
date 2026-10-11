import 'express-async-errors';
import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';
import dotenv from 'dotenv';

dotenv.config();

import { authenticate } from './middleware/auth.js';
import { errorHandler } from './middleware/errorHandler.js';

import authRoutes from './routes/authRoutes.js';
import orgRoutes from './routes/orgRoutes.js';
import memberRoutes from './routes/memberRoutes.js';
import eventRoutes from './routes/eventRoutes.js';
import announcementRoutes from './routes/announcementRoutes.js';
import merchRoutes from './routes/merchRoutes.js';
import volunteerRoutes from './routes/volunteerRoutes.js';
import financeRoutes from './routes/financeRoutes.js';
import analyticsRoutes from './routes/analyticsRoutes.js';
import aiRoutes from './routes/aiRoutes.js';
import auditRoutes from './routes/auditRoutes.js';
import notificationRoutes from './routes/notificationRoutes.js';

const app = express();
const PORT = process.env.PORT || 5000;

// Security & utility middleware
app.use(helmet({
  crossOriginResourcePolicy: false,
}));
app.use(cors({
  origin: '*',
  credentials: true,
}));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(morgan('dev'));

// Global authentication extractor
app.use(authenticate);

// Health check
app.get('/api/health', (_req, res) => {
  res.json({
    status: 'online',
    platform: 'CampusSphere AI API Server',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
    database: 'SQLite (Prisma ORM)',
    demoMode: true,
  });
});

// Domain API routes
app.use('/api/auth', authRoutes);
app.use('/api/organizations', orgRoutes);
app.use('/api/members', memberRoutes);
app.use('/api/events', eventRoutes);
app.use('/api/announcements', announcementRoutes);
app.use('/api/merchandise', merchRoutes);
app.use('/api/volunteers', volunteerRoutes);
app.use('/api/finance', financeRoutes);
app.use('/api/analytics', analyticsRoutes);
app.use('/api/ai', aiRoutes);
app.use('/api/audit-logs', auditRoutes);
app.use('/api/notifications', notificationRoutes);

// Centralized error handling
app.use(errorHandler);

export default app;

if (process.env.NODE_ENV !== 'test') {
  app.listen(PORT, () => {
    console.log(`=======================================================`);
    console.log(`🚀 CampusSphere AI Server listening on port ${PORT}`);
    console.log(`📡 Health Check: http://localhost:${PORT}/api/health`);
    console.log(`🔐 Demo Accounts: http://localhost:${PORT}/api/auth/demo-accounts`);
    console.log(`=======================================================`);
  });
}
