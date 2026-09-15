import { Request, Response } from 'express';
import { SearchService } from '../services/searchService';
import { QueryRequest } from '../models/types';

export class QueryController {
  public static async handleQuery(req: Request, res: Response): Promise<void> {
    try {
      const { queryText, collectionIds, filters } = req.body;

      if (!queryText || typeof queryText !== 'string' || !queryText.trim()) {
        res.status(400).json({
          status: 'ERROR',
          message: 'queryText is required and cannot be empty',
        });
        return;
      }

      const requestPayload: QueryRequest = {
        queryText: queryText.trim(),
        collectionIds,
        filters,
      };

      const result = await SearchService.executeQuery(requestPayload);
      res.status(200).json(result);
    } catch (error) {
      res.status(500).json({
        status: 'ERROR',
        message: 'Internal server error while processing query',
      });
    }
  }
}
