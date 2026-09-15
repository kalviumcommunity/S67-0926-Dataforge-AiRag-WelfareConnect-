import { Request, Response } from 'express';
import { DocumentService } from '../services/documentService';

export class CollectionController {
  public static async getCollections(req: Request, res: Response): Promise<void> {
    try {
      const collections = await DocumentService.getCollections();
      res.status(200).json({
        status: 'SUCCESS',
        data: collections,
      });
    } catch (error) {
      res.status(500).json({ status: 'ERROR', message: 'Failed to fetch collections' });
    }
  }

  public static async getCollectionById(req: Request, res: Response): Promise<void> {
    try {
      const id = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
      if (!id) {
        res.status(400).json({ status: 'ERROR', message: 'Collection ID is required' });
        return;
      }
      const collection = await DocumentService.getCollectionById(id);
      if (!collection) {
        res.status(404).json({ status: 'ERROR', message: 'Collection not found' });
        return;
      }
      res.status(200).json({ status: 'SUCCESS', data: collection });
    } catch (error) {
      res.status(500).json({ status: 'ERROR', message: 'Failed to fetch collection' });
    }
  }
}
