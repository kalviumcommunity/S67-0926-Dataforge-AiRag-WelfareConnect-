import { Router } from 'express';
import { CollectionController } from '../controllers/collectionController';
import { authenticateUser, requireRole } from '../middlewares/authMiddleware';

const router = Router();

// Public: All users can browse active public collections
router.get('/', CollectionController.getCollections);
router.get('/:id', CollectionController.getCollectionById);

// Protected: Only administrators can create collections
router.post('/', authenticateUser, requireRole(['SYSTEM_ADMIN', 'SCHEME_ADMIN']), (req, res) => {
  const { name, department, description } = req.body;
  if (!name || !department) {
    res.status(400).json({ status: 'ERROR', message: 'Name and department are required' });
    return;
  }
  const id = `col-${Date.now()}`;
  res.status(201).json({
    status: 'SUCCESS',
    message: 'Collection created successfully',
    data: { id, name, department, description, isPublic: true },
  });
});

export default router;
