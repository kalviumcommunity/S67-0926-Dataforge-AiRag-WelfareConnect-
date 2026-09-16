import { Router } from 'express';
import { AuthController } from '../controllers/authController';
import { authenticateUser, requireRole } from '../middlewares/authMiddleware';

const router = Router();

// Public auth routes
router.post('/register', AuthController.register);
router.post('/login', AuthController.login);
router.post('/logout', AuthController.logout);

// Protected routes
router.get('/me', authenticateUser, AuthController.getProfile);

// Administrator-only: provision staff and operator accounts
router.post(
  '/users',
  authenticateUser,
  requireRole(['SYSTEM_ADMIN', 'SCHEME_ADMIN']),
  AuthController.createStaffAccount
);

export default router;
