import { Request, Response } from 'express';
import { AuthService } from '../services/authService';

export class AuthController {
  public static async register(req: Request, res: Response): Promise<void> {
    try {
      const { email, password, fullName } = req.body;

      if (!email || !password || !fullName) {
        res.status(400).json({
          status: 'ERROR',
          message: 'email, password, and fullName are required fields',
        });
        return;
      }

      if (password.length < 8) {
        res.status(400).json({
          status: 'ERROR',
          message: 'Password must be at least 8 characters long',
        });
        return;
      }

      const session = await AuthService.registerCitizen({ email, password, fullName });
      res.status(201).json({
        status: 'SUCCESS',
        message: 'Citizen account registered successfully',
        data: session,
      });
    } catch (error: any) {
      res.status(400).json({
        status: 'ERROR',
        message: error.message || 'Registration failed',
      });
    }
  }

  public static async login(req: Request, res: Response): Promise<void> {
    try {
      const { email, password } = req.body;

      if (!email || !password) {
        res.status(400).json({
          status: 'ERROR',
          message: 'email and password are required',
        });
        return;
      }

      const clientIp = req.ip || req.socket.remoteAddress || '127.0.0.1';
      const session = await AuthService.login(email, password, clientIp);

      res.status(200).json({
        status: 'SUCCESS',
        message: 'Login successful',
        data: session,
      });
    } catch (error: any) {
      res.status(401).json({
        status: 'ERROR',
        code: 'INVALID_CREDENTIALS',
        message: error.message || 'Invalid email or password',
      });
    }
  }

  public static async getProfile(req: Request, res: Response): Promise<void> {
    try {
      if (!req.user) {
        res.status(401).json({ status: 'ERROR', message: 'Unauthorized' });
        return;
      }

      const user = AuthService.getUserById(req.user.userId);
      if (!user) {
        res.status(404).json({ status: 'ERROR', message: 'User not found' });
        return;
      }

      res.status(200).json({
        status: 'SUCCESS',
        data: {
          id: user.id,
          email: user.email,
          fullName: user.fullName,
          role: req.user.role,
          department: user.department,
          permissions: req.user.permissions,
        },
      });
    } catch (error: any) {
      res.status(500).json({ status: 'ERROR', message: 'Failed to fetch user profile' });
    }
  }

  public static async createStaffAccount(req: Request, res: Response): Promise<void> {
    try {
      if (!req.user) {
        res.status(401).json({ status: 'ERROR', message: 'Unauthorized' });
        return;
      }

      const { email, password, fullName, role, department } = req.body;

      if (!email || !password || !fullName || !role) {
        res.status(400).json({
          status: 'ERROR',
          message:
            'email, password, fullName, and role (HELPDESK, SCHEME_ADMIN, SYSTEM_ADMIN) are required',
        });
        return;
      }

      const newUser = await AuthService.createStaffAccount(req.user.userId, {
        email,
        password,
        fullName,
        role,
        department,
      });

      res.status(201).json({
        status: 'SUCCESS',
        message: 'Staff account created successfully by administrator',
        data: {
          id: newUser.id,
          email: newUser.email,
          fullName: newUser.fullName,
          role,
          department: newUser.department,
        },
      });
    } catch (error: any) {
      res.status(400).json({
        status: 'ERROR',
        message: error.message || 'Failed to create staff account',
      });
    }
  }

  public static logout(req: Request, res: Response): void {
    // Stateless JWT logout is handled on client by discarding token; server confirms invalidation
    res.status(200).json({
      status: 'SUCCESS',
      message: 'Logged out successfully. Session terminated.',
    });
  }
}
