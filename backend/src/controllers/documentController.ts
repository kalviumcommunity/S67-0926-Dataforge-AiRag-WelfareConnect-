import { Request, Response } from 'express';
import { DocumentService } from '../services/documentService';
import { TaskQueue } from '../workers/taskQueue';

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
}
