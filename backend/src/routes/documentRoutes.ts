import { Router } from 'express';
import { DocumentController } from '../controllers/documentController';

const router = Router();

router.get('/', DocumentController.getDocuments);
router.post('/upload', DocumentController.uploadDocument);

export default router;
