import { Router } from 'express';
import { FeedbackController } from '../controllers/feedbackController';
import { optionalAuthenticateUser } from '../middlewares/authMiddleware';

const router = Router();

// Allows both authenticated and guest feedback
router.post('/', optionalAuthenticateUser, FeedbackController.submitFeedback);

export default router;
