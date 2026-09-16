import { describe, it, expect } from 'vitest';
import request from 'supertest';
import { app } from '../src/app';

describe('Authentication & Authorization Suite (RBAC & Audit)', () => {
  let adminToken: string;
  let helpdeskToken: string;
  let citizenToken: string;

  it('1. Citizen can register an account', async () => {
    const res = await request(app).post('/api/v1/auth/register').send({
      email: 'citizen.test@example.com',
      password: 'Password@123',
      fullName: 'Jane Citizen',
    });

    expect(res.status).toBe(201);
    expect(res.body.status).toBe('SUCCESS');
    expect(res.body.data.user.role).toBe('CITIZEN');
    expect(res.body.data).toHaveProperty('token');
    expect(res.body.data).toHaveProperty('expiresIn');

    citizenToken = res.body.data.token;
  });

  it('2. User can log in with valid credentials', async () => {
    // Login as pre-seeded local Dev Administrator
    const res = await request(app).post('/api/v1/auth/login').send({
      email: 'admin.dev@welfareconnect.local',
      password: 'Admin@123456',
    });

    expect(res.status).toBe(200);
    expect(res.body.status).toBe('SUCCESS');
    expect(res.body.data.user.role).toBe('SYSTEM_ADMIN');
    expect(res.body.data.user.permissions).toContain('admin:all');
    expect(res.body.data).toHaveProperty('token');

    adminToken = res.body.data.token;

    // Login as pre-seeded Helpdesk Staff
    const staffRes = await request(app).post('/api/v1/auth/login').send({
      email: 'helpdesk.staff@welfareconnect.local',
      password: 'Staff@123456',
    });

    expect(staffRes.status).toBe(200);
    expect(staffRes.body.data.user.role).toBe('HELPDESK');
    helpdeskToken = staffRes.body.data.token;
  });

  it('3. Login fails with incorrect password', async () => {
    const res = await request(app).post('/api/v1/auth/login').send({
      email: 'admin.dev@welfareconnect.local',
      password: 'WrongPassword!',
    });

    expect(res.status).toBe(401);
    expect(res.body.code).toBe('INVALID_CREDENTIALS');
  });

  it('4. Protected routes reject requests with missing token (401)', async () => {
    const res = await request(app).get('/api/v1/auth/me');
    expect(res.status).toBe(401);
    expect(res.body.code).toBe('AUTH_REQUIRED');
  });

  it('5. Protected routes reject requests with invalid token (401)', async () => {
    const res = await request(app)
      .get('/api/v1/auth/me')
      .set('Authorization', 'Bearer invalid_token_xyz_123');

    expect(res.status).toBe(401);
    expect(res.body.code).toBe('AUTH_EXPIRED_OR_INVALID');
  });

  it('6. Server-side RBAC: Citizen cannot upload or delete documents (403 Forbidden)', async () => {
    const uploadRes = await request(app)
      .post('/api/v1/documents/upload')
      .set('Authorization', `Bearer ${citizenToken}`)
      .send({
        title: 'Unauthorized Policy.pdf',
        collectionId: 'c0000000-0000-4000-8000-000000000001',
      });

    expect(uploadRes.status).toBe(403);
    expect(uploadRes.body.code).toBe('FORBIDDEN_ROLE');

    const deleteRes = await request(app)
      .delete('/api/v1/documents/doc-123')
      .set('Authorization', `Bearer ${citizenToken}`);

    expect(deleteRes.status).toBe(403);
    expect(deleteRes.body.code).toBe('FORBIDDEN_ROLE');
  });

  it('7. Server-side RBAC: Citizen cannot view audit logs (403 Forbidden)', async () => {
    const res = await request(app)
      .get('/api/v1/audit/logs')
      .set('Authorization', `Bearer ${citizenToken}`);

    expect(res.status).toBe(403);
    expect(res.body.code).toBe('FORBIDDEN_ROLE');
  });

  it('8. Server-side RBAC: Helpdesk staff can access query history but cannot delete docs', async () => {
    // Helpdesk access query history
    const historyRes = await request(app)
      .get('/api/v1/query/history')
      .set('Authorization', `Bearer ${helpdeskToken}`);

    expect(historyRes.status).toBe(200);
    expect(historyRes.body.status).toBe('SUCCESS');

    // Helpdesk cannot delete document
    const deleteRes = await request(app)
      .delete('/api/v1/documents/doc-123')
      .set('Authorization', `Bearer ${helpdeskToken}`);

    expect(deleteRes.status).toBe(403);
    expect(deleteRes.body.code).toBe('FORBIDDEN_ROLE');
  });

  it('9. Server-side RBAC: Administrator can upload, archive, and delete documents', async () => {
    // Admin upload
    const uploadRes = await request(app)
      .post('/api/v1/documents/upload')
      .set('Authorization', `Bearer ${adminToken}`)
      .send({
        title: 'Solar Pump Scheme 2026.pdf',
        collectionId: 'c0000000-0000-4000-8000-000000000001',
        department: 'Department of Agriculture',
      });

    expect(uploadRes.status).toBe(202);
    expect(uploadRes.body.status).toBe('ACCEPTED');

    // Admin archive
    const archiveRes = await request(app)
      .post('/api/v1/documents/doc-sample-01/archive')
      .set('Authorization', `Bearer ${adminToken}`);

    expect(archiveRes.status).toBe(200);

    // Admin delete
    const deleteRes = await request(app)
      .delete('/api/v1/documents/doc-sample-01')
      .set('Authorization', `Bearer ${adminToken}`);

    expect(deleteRes.status).toBe(200);
  });

  it('10. Administrator can provision staff accounts', async () => {
    const res = await request(app)
      .post('/api/v1/auth/users')
      .set('Authorization', `Bearer ${adminToken}`)
      .send({
        email: 'operator2@welfareconnect.local',
        password: 'Password@123',
        fullName: 'New Helpdesk Operator',
        role: 'HELPDESK',
        department: 'Regional Citizen Desk',
      });

    expect(res.status).toBe(201);
    expect(res.body.data.role).toBe('HELPDESK');
  });

  it('11. Administrator can view audit event logs', async () => {
    const res = await request(app)
      .get('/api/v1/audit/logs')
      .set('Authorization', `Bearer ${adminToken}`);

    expect(res.status).toBe(200);
    expect(res.body.status).toBe('SUCCESS');
    expect(Array.isArray(res.body.data)).toBe(true);
    expect(res.body.data.length).toBeGreaterThan(0);

    // Verify audit contains recent actions
    const actionTypes = res.body.data.map((e: any) => e.actionType);
    expect(actionTypes).toContain('USER_LOGIN');
    expect(actionTypes).toContain('DOCUMENT_UPLOADED');
  });

  it('12. User can submit feedback and logout', async () => {
    const feedbackRes = await request(app)
      .post('/api/v1/feedback')
      .set('Authorization', `Bearer ${citizenToken}`)
      .send({
        queryId: 'qry-test-01',
        isHelpful: true,
        feedbackCategory: 'Accurate Citation',
        comments: 'Found exact page citation.',
      });

    expect(feedbackRes.status).toBe(201);

    const logoutRes = await request(app).post('/api/v1/auth/logout');
    expect(logoutRes.status).toBe(200);
  });
});
