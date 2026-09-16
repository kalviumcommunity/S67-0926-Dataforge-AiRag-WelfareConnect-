import { Request, Response } from 'express';
import { AuditService } from '../services/auditService';

export class FeedbackController {
  public static async submitFeedback(req: Request, res: Response): Promise<void> {
    try {
      const { queryId, isHelpful, feedbackCategory, comments } = req.body;

      if (!queryId || typeof isHelpful !== 'boolean') {
        res.status(400).json({
          status: 'ERROR',
          message: 'queryId and boolean isHelpful are required',
        });
        return;
      }

      const feedbackId = `fbk-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;

      await AuditService.logEvent({
        actorUserId: req.user?.userId,
        actionType: 'FEEDBACK_SUBMITTED',
        entityTable: 'user_feedback',
        entityId: feedbackId,
        metadata: { queryId, isHelpful, feedbackCategory, comments },
      });

      res.status(201).json({
        status: 'SUCCESS',
        message: 'Feedback submitted successfully',
        data: {
          id: feedbackId,
          queryId,
          isHelpful,
          feedbackCategory,
          comments,
        },
      });
    } catch (error) {
      res.status(500).json({ status: 'ERROR', message: 'Failed to submit feedback' });
    }
  }
}
