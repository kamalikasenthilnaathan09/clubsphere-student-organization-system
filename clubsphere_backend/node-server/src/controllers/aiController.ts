import { Request, Response } from 'express';
import { z } from 'zod';
import { processCopilotQuery } from '../services/aiService.js';
import { recordAuditLog } from '../middleware/audit.js';

const aiQuerySchema = z.object({
  prompt: z.string().min(2),
  intent: z.enum(['general', 'performance_summary', 'draft_announcement', 'task_summary', 'financial_health', 'inventory_reorder', 'fundraiser_plan']).default('general'),
});

export async function askCopilot(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const userId = req.user!.id;
  const userRole = req.user!.currentRole || 'MEMBER';
  const data = aiQuerySchema.parse(req.body);

  const copilotResponse = await processCopilotQuery({
    organizationId: orgId,
    userId,
    userRole,
    prompt: data.prompt,
    intent: data.intent,
  });

  await recordAuditLog({
    organizationId: orgId,
    actorUserId: userId,
    action: 'AI_COPILOT_QUERIED',
    entityType: 'AICopilot',
    entityId: orgId,
    details: { prompt: data.prompt.slice(0, 100), intent: data.intent, model: copilotResponse.model },
  });

  res.json(copilotResponse);
}
