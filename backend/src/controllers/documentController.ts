import { Request, Response } from 'express';
import { DocumentService } from '../services/documentService';
import { TaskQueue } from '../workers/taskQueue';
import { AuditService } from '../services/auditService';

export class DocumentController {
  public static async getDocuments(req: Request, res: Response): Promise<void> {
    try {
      const collectionId = req.query.collectionId as string | undefined;
      const documents = await DocumentService.getDocuments(collectionId);
      res.status(200).json({
        status: 'SUCCESS',
        data: documents,
      });
    } catch (error) {
      res.status(500).json({ status: 'ERROR', message: 'Failed to fetch documents' });
    }
  }

  public static async uploadDocument(req: Request, res: Response): Promise<void> {
    try {
      const { title, collectionId, department, notificationNumber } = req.body;

      if (!title || !collectionId) {
        res.status(400).json({
          status: 'ERROR',
          message: 'Title and collectionId are required fields',
        });
        return;
      }

      const documentId = `doc-${Date.now()}`;
      const versionId = `ver-${Date.now()}`;

      // Enqueue background processing job
      const jobId = await TaskQueue.enqueue('DOCUMENT_INGESTION', {
        versionId,
        documentId,
        storagePath: `raw/${collectionId}/${documentId}/${versionId}/original.pdf`,
        collectionId,
      });

      // Log privileged audit action
      await AuditService.logEvent({
        actorUserId: req.user?.userId,
        actionType: 'DOCUMENT_UPLOADED',
        entityTable: 'documents',
        entityId: documentId,
        metadata: { title, collectionId, versionId, jobId },
      });

      res.status(202).json({
        status: 'ACCEPTED',
        message: 'Document upload accepted for background processing and indexing',
        documentId,
        versionId,
        jobId,
        trackingUrl: `/api/v1/documents/${documentId}/status`,
      });
    } catch (error) {
      res.status(500).json({ status: 'ERROR', message: 'Failed to process document upload' });
    }
  }

  public static async archiveDocument(req: Request, res: Response): Promise<void> {
    try {
      const id = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;

      if (!id) {
        res.status(400).json({ status: 'ERROR', message: 'Document ID is required' });
        return;
      }

      await AuditService.logEvent({
        actorUserId: req.user?.userId,
        actionType: 'DOCUMENT_ARCHIVED',
        entityTable: 'documents',
        entityId: id,
        metadata: { status: 'ARCHIVED' },
      });

      res.status(200).json({
        status: 'SUCCESS',
        message: `Document ${id} successfully archived`,
      });
    } catch (error) {
      res.status(500).json({ status: 'ERROR', message: 'Failed to archive document' });
    }
  }

  public static async deleteDocument(req: Request, res: Response): Promise<void> {
    try {
      const id = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;

      if (!id) {
        res.status(400).json({ status: 'ERROR', message: 'Document ID is required' });
        return;
      }

      await AuditService.logEvent({
        actorUserId: req.user?.userId,
        actionType: 'DOCUMENT_DELETED',
        entityTable: 'documents',
        entityId: id,
        metadata: { isDeleted: true },
      });

      res.status(200).json({
        status: 'SUCCESS',
        message: `Document ${id} successfully marked as deleted`,
      });
    } catch (error) {
      res.status(500).json({ status: 'ERROR', message: 'Failed to delete document' });
    }
  }
}
