import { Router } from 'express';
import { AuditController } from '../controllers/auditController';
import { authenticateUser, requireRole } from '../middlewares/authMiddleware';

const router = Router();

// Only Administrators can inspect audit trails
router.get(
  '/logs',
  authenticateUser,
  requireRole(['SYSTEM_ADMIN', 'SCHEME_ADMIN']),
  AuditController.getAuditLogs
);

export default router;
