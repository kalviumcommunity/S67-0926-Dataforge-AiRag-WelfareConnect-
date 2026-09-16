import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { env } from '../config/env';
import { User, UserRole } from '../models/schema';
import { AuditService } from './auditService';

export interface AuthTokenPayload {
  userId: string;
  email: string;
  role: UserRole;
  permissions: string[];
}

export interface AuthSessionResponse {
  user: {
    id: string;
    email: string;
    fullName: string;
    role: UserRole;
    department?: string | null;
    permissions: string[];
  };
  token: string;
  expiresIn: string;
}

// Role Permissions Matrix
export const ROLE_PERMISSIONS: Record<UserRole, string[]> = {
  SYSTEM_ADMIN: ['admin:all', 'users:manage', 'audit:read', 'docs:all', 'collections:manage'],
  SCHEME_ADMIN: [
    'docs:upload',
    'docs:process',
    'docs:archive',
    'docs:delete',
    'collections:manage',
    'audit:read',
  ],
  HELPDESK: [
    'query:execute',
    'citations:preview',
    'feedback:submit',
    'history:read',
    'eligibility:check',
  ],
  CITIZEN: ['query:execute', 'citations:preview', 'feedback:submit'],
};

// In-memory catalog of users for local development / testing
const usersStore: Map<string, User & { permissions: string[] }> = new Map();

// Initialize Dev Admin in store
const initialHashedPassword = bcrypt.hashSync('Admin@123456', 10);
usersStore.set('admin.dev@welfareconnect.local', {
  id: 'b0000000-0000-4000-8000-000000000001',
  roleId: 'a0000000-0000-4000-8000-000000000001',
  email: 'admin.dev@welfareconnect.local',
  passwordHash: initialHashedPassword,
  fullName: 'Local Development Administrator',
  department: 'Department of Information Technology & Digital Services',
  isActive: true,
  createdAt: new Date('2024-01-01'),
  updatedAt: new Date('2024-01-01'),
  permissions: ROLE_PERMISSIONS.SYSTEM_ADMIN,
});

// Initialize Sample Helpdesk Staff
usersStore.set('helpdesk.staff@welfareconnect.local', {
  id: 'b0000000-0000-4000-8000-000000000002',
  roleId: 'a0000000-0000-4000-8000-000000000003',
  email: 'helpdesk.staff@welfareconnect.local',
  passwordHash: bcrypt.hashSync('Staff@123456', 10),
  fullName: 'Frontline Helpdesk Officer',
  department: 'Citizen Helpdesk Services',
  isActive: true,
  createdAt: new Date('2024-01-02'),
  updatedAt: new Date('2024-01-02'),
  permissions: ROLE_PERMISSIONS.HELPDESK,
});

export class AuthService {
  public static async registerCitizen(params: {
    email: string;
    password: string;
    fullName: string;
  }): Promise<AuthSessionResponse> {
    const existing = usersStore.get(params.email.toLowerCase());
    if (existing) {
      throw new Error('User with this email already exists');
    }

    const salt = await bcrypt.genSalt(10);
    const passwordHash = await bcrypt.hash(params.password, salt);

    const userId = `usr-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    const userRole: UserRole = 'CITIZEN';
    const permissions = ROLE_PERMISSIONS[userRole];

    const newUser = {
      id: userId,
      roleId: 'a0000000-0000-4000-8000-000000000004',
      email: params.email.toLowerCase(),
      passwordHash,
      fullName: params.fullName,
      department: 'Public Citizen',
      isActive: true,
      createdAt: new Date(),
      updatedAt: new Date(),
      permissions,
    };

    usersStore.set(newUser.email, newUser);

    await AuditService.logEvent({
      actorUserId: userId,
      actionType: 'USER_LOGIN',
      entityTable: 'users',
      entityId: userId,
      metadata: { action: 'CITIZEN_REGISTERED' },
    });

    const token = this.generateToken({
      userId: newUser.id,
      email: newUser.email,
      role: userRole,
      permissions,
    });

    return {
      user: {
        id: newUser.id,
        email: newUser.email,
        fullName: newUser.fullName,
        role: userRole,
        department: newUser.department,
        permissions,
      },
      token,
      expiresIn: env.JWT_EXPIRES_IN,
    };
  }

  public static async createStaffAccount(
    adminUserId: string,
    params: {
      email: string;
      password: string;
      fullName: string;
      role: 'HELPDESK' | 'SCHEME_ADMIN' | 'SYSTEM_ADMIN';
      department?: string;
    }
  ): Promise<User> {
    const existing = usersStore.get(params.email.toLowerCase());
    if (existing) {
      throw new Error('User with this email already exists');
    }

    const salt = await bcrypt.genSalt(10);
    const passwordHash = await bcrypt.hash(params.password, salt);

    const userId = `usr-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    const permissions = ROLE_PERMISSIONS[params.role];

    const newUser = {
      id: userId,
      roleId: `role-${params.role.toLowerCase()}`,
      email: params.email.toLowerCase(),
      passwordHash,
      fullName: params.fullName,
      department: params.department || 'General Administration',
      isActive: true,
      createdAt: new Date(),
      updatedAt: new Date(),
      permissions,
    };

    usersStore.set(newUser.email, newUser);

    await AuditService.logEvent({
      actorUserId: adminUserId,
      actionType: 'USER_LOGIN',
      entityTable: 'users',
      entityId: userId,
      metadata: { action: 'STAFF_ACCOUNT_CREATED', targetRole: params.role },
    });

    return newUser;
  }

  public static async login(
    email: string,
    password: string,
    ipAddress = '127.0.0.1'
  ): Promise<AuthSessionResponse> {
    const user = usersStore.get(email.toLowerCase());
    if (!user || !user.isActive) {
      throw new Error('Invalid email or password');
    }

    const isMatch = await bcrypt.compare(password, user.passwordHash);
    if (!isMatch) {
      throw new Error('Invalid email or password');
    }

    // Determine user role from permissions
    let role: UserRole = 'CITIZEN';
    if (user.permissions.includes('admin:all')) role = 'SYSTEM_ADMIN';
    else if (user.permissions.includes('docs:upload')) role = 'SCHEME_ADMIN';
    else if (user.permissions.includes('eligibility:check')) role = 'HELPDESK';

    const token = this.generateToken({
      userId: user.id,
      email: user.email,
      role,
      permissions: user.permissions,
    });

    await AuditService.logEvent({
      actorUserId: user.id,
      actionType: 'USER_LOGIN',
      entityTable: 'users',
      entityId: user.id,
      clientIpMasked: ipAddress,
      metadata: { loginSuccess: true, role },
    });

    return {
      user: {
        id: user.id,
        email: user.email,
        fullName: user.fullName,
        role,
        department: user.department,
        permissions: user.permissions,
      },
      token,
      expiresIn: env.JWT_EXPIRES_IN,
    };
  }

  public static generateToken(payload: AuthTokenPayload): string {
    return jwt.sign(payload, env.JWT_SECRET, {
      expiresIn: env.JWT_EXPIRES_IN as jwt.SignOptions['expiresIn'],
    });
  }

  public static verifyToken(token: string): AuthTokenPayload {
    return jwt.verify(token, env.JWT_SECRET) as AuthTokenPayload;
  }

  public static getUserById(id: string): (User & { permissions: string[] }) | null {
    for (const u of usersStore.values()) {
      if (u.id === id) return u;
    }
    return null;
  }
}
