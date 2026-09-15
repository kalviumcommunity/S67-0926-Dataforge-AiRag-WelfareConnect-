import { Router } from 'express';
import { CollectionController } from '../controllers/collectionController';

const router = Router();

router.get('/', CollectionController.getCollections);
router.get('/:id', CollectionController.getCollectionById);

export default router;
