import { Router } from 'express';
import { QueryController } from '../controllers/queryController';
import {
  optionalAuthenticateUser,
  authenticateUser,
  requireRole,
} from '../middlewares/authMiddleware';

const router = Router();

// Public / Authenticated search
router.post('/', optionalAuthenticateUser, QueryController.handleQuery);

// Helpdesk Staff and Administrators can view past query sessions and history
router.get(
  '/history',
  authenticateUser,
  requireRole(['HELPDESK', 'SCHEME_ADMIN', 'SYSTEM_ADMIN']),
  (req, res) => {
    res.status(200).json({
      status: 'SUCCESS',
      data: [
        {
          id: 'qry-sample-01',
          questionText: 'What is the land limit for PM-Kisan farmer subsidy?',
          generatedSummary:
            'Small and marginal farmers holding land up to 2 hectares are entitled to income support.',
          isGrounded: true,
          latencyMs: 125,
          createdAt: new Date('2024-03-01'),
        },
      ],
    });
  }
);

export default router;
