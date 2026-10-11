import { Router } from 'express';
import {
  listTransactions,
  getFinancialSummary,
  createTransaction,
  reverseTransaction,
  listBudgets,
  createOrUpdateBudget,
} from '../controllers/financeController.js';
import { requireAuth, requireOrg, requireRoles } from '../middleware/auth.js';

const router = Router();

router.use(requireAuth, requireOrg);

router.get('/transactions', listTransactions);
router.get('/summary', getFinancialSummary);
router.post('/transactions', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'TREASURER']), createTransaction);
router.post('/transactions/:id/reverse', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'TREASURER']), reverseTransaction);
router.get('/budgets', listBudgets);
router.post('/budgets', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'TREASURER']), createOrUpdateBudget);

export default router;
