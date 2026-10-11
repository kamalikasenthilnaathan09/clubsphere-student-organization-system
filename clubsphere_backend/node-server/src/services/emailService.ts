export interface EmailPayload {
  to: string | string[];
  subject: string;
  body: string;
  category?: string;
  isAnnouncement?: boolean;
}

export interface EmailResult {
  success: boolean;
  recipientCount: number;
  provider: 'DEMO_MOCK' | 'SMTP';
  deliveredAt: string;
  messageId: string;
}

export async function sendNotificationEmail(payload: EmailPayload): Promise<EmailResult> {
  const recipients = Array.isArray(payload.to) ? payload.to : [payload.to];
  const messageId = `msg-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;

  // In demo development mode, simulate reliable transmission and output structured log
  console.log(`[EMAIL-SERVICE] [${messageId}] Dispatching to ${recipients.length} recipients. Subject: "${payload.subject}"`);

  return {
    success: true,
    recipientCount: recipients.length,
    provider: 'DEMO_MOCK',
    deliveredAt: new Date().toISOString(),
    messageId,
  };
}
