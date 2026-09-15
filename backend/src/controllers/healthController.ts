import { Request, Response } from 'express';
import { HealthService } from '../services/healthService';

export class HealthController {
  public static getHealth(req: Request, res: Response): void {
    const health = HealthService.getHealth();
    res.status(200).json(health);
  }
}
