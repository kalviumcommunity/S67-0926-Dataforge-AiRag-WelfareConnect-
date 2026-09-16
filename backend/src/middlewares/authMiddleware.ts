import { Request, Response, NextFunction } from 'express';
import { AuthService, AuthTokenPayload } from '../services/authService';
import { UserRole } from '../models/schema';

// Extend Express Request with authenticated user context
declare global {
  namespace Express {
    interface Request {
      user?: AuthTokenPayload;
    }
  }
}

/**
 * Middleware: Strictly requires a valid JWT Bearer token.
 * Returns 401 Unauthorized if missing, malformed, or expired.
 */
export function authenticateUser(req: Request, res: Response, next: NextFunction): void {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    res.status(401).json({
      status: 'ERROR',
      code: 'AUTH_REQUIRED',
      message: 'Authentication token is required to access this endpoint',
    });
    return;
  }

  const token = authHeader.split(' ')[1];

  try {
    const payload = AuthService.verifyToken(token);
    req.user = payload;
    next();
  } catch (error) {
    res.status(401).json({
      status: 'ERROR',
      code: 'AUTH_EXPIRED_OR_INVALID',
      message: 'Session has expired or token is invalid. Please log in again.',
    });
  }
}

/**
 * Middleware: Optionally extracts JWT Bearer token if provided,
 * allowing public guest queries while identifying authenticated users.
 */
export function optionalAuthenticateUser(req: Request, res: Response, next: NextFunction): void {
  const authHeader = req.headers.authorization;

  if (authHeader && authHeader.startsWith('Bearer ')) {
    const token = authHeader.split(' ')[1];
    try {
      const payload = AuthService.verifyToken(token);
      req.user = payload;
    } catch {
      // Ignored for optional routes
    }
  }

  next();
}

/**
 * Middleware: Enforces Server-Side Role-Based Access Control (RBAC).
 * Returns 403 Forbidden if the user's role is not authorized.
 */
export function requireRole(allowedRoles: UserRole[]) {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (!req.user) {
      res.status(401).json({
        status: 'ERROR',
        code: 'AUTH_REQUIRED',
        message: 'Authentication is required',
      });
      return;
    }

    if (!allowedRoles.includes(req.user.role)) {
      res.status(403).json({
        status: 'ERROR',
        code: 'FORBIDDEN_ROLE',
        message: `Forbidden: Access restricted to roles [${allowedRoles.join(', ')}]. Current role: ${req.user.role}`,
      });
      return;
    }

    next();
  };
}

/**
 * Middleware: Enforces granular permission check.
 */
export function requirePermission(permission: string) {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (!req.user) {
      res.status(401).json({
        status: 'ERROR',
        code: 'AUTH_REQUIRED',
        message: 'Authentication is required',
      });
      return;
    }

    const hasPermission =
      req.user.permissions.includes(permission) || req.user.permissions.includes('admin:all');

    if (!hasPermission) {
      res.status(403).json({
        status: 'ERROR',
        code: 'FORBIDDEN_PERMISSION',
        message: `Forbidden: Missing required permission '${permission}'`,
      });
      return;
    }

    next();
  };
}
