import { Router } from 'express';
import { QueryController } from '../controllers/queryController';

const router = Router();

router.post('/', QueryController.handleQuery);

export default router;
