import { Request, Response } from 'express';
import { AuditService } from '../services/auditService';

export class AuditController {
  public static async getAuditLogs(req: Request, res: Response): Promise<void> {
    try {
      const limit = req.query.limit ? parseInt(req.query.limit as string, 10) : 50;
      const logs = await AuditService.getAuditLogs(limit);
      res.status(200).json({
        status: 'SUCCESS',
        data: logs,
      });
    } catch (error: any) {
      res.status(500).json({
        status: 'ERROR',
        message: 'Failed to retrieve audit trail logs',
      });
    }
  }
}
