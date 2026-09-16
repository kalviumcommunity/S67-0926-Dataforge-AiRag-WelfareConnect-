import { Router } from 'express';
import { DocumentController } from '../controllers/documentController';
import { authenticateUser, requireRole } from '../middlewares/authMiddleware';

const router = Router();

// Public / Authenticated read
router.get('/', DocumentController.getDocuments);

// Administrator-only privileged actions
router.post(
  '/upload',
  authenticateUser,
  requireRole(['SYSTEM_ADMIN', 'SCHEME_ADMIN']),
  DocumentController.uploadDocument
);

router.post(
  '/:id/archive',
  authenticateUser,
  requireRole(['SYSTEM_ADMIN', 'SCHEME_ADMIN']),
  DocumentController.archiveDocument
);

router.delete(
  '/:id',
  authenticateUser,
  requireRole(['SYSTEM_ADMIN', 'SCHEME_ADMIN']),
  DocumentController.deleteDocument
);

export default router;
