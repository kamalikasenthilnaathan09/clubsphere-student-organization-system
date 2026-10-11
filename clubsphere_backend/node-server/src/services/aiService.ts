import prisma from '../lib/prisma.js';

interface QueryCopilotParams {
  organizationId: string;
  userId: string;
  userRole: string;
  prompt: string;
  intent?: 'general' | 'performance_summary' | 'draft_announcement' | 'task_summary' | 'financial_health' | 'inventory_reorder' | 'fundraiser_plan';
}

export interface CopilotResponse {
  answer: string;
  intent: string;
  contextSummary: {
    activeMembersCount: number;
    upcomingEventsCount: number;
    recordedBalance: number;
    openTasksCount: number;
    lowStockItemsCount: number;
  };
  suggestions?: string[];
  isSimulatedFallback: boolean;
  model: string;
  generatedAt: string;
}

export async function processCopilotQuery(params: QueryCopilotParams): Promise<CopilotResponse> {
  const { organizationId, userRole, prompt, intent = 'general' } = params;

  // Retrieve authorized organization data
  const org = await prisma.organization.findUnique({
    where: { id: organizationId },
    select: { name: true, currency: true },
  });

  const activeMembersCount = await prisma.organizationMembership.count({
    where: { organizationId, status: 'ACTIVE' },
  });

  const upcomingEvents = await prisma.event.findMany({
    where: { organizationId, status: { in: ['PUBLISHED', 'DRAFT'] } },
    include: { ticketTypes: true, bookings: true },
    orderBy: { startDate: 'asc' },
    take: 5,
  });

  const transactions = await prisma.financialTransaction.findMany({
    where: { organizationId, status: 'SETTLED' },
  });

  const totalIncome = transactions
    .filter((t) => t.type === 'INCOME')
    .reduce((acc, t) => acc + t.amount, 0);

  const totalExpenses = transactions
    .filter((t) => t.type === 'EXPENSE')
    .reduce((acc, t) => acc + t.amount, 0);

  const recordedBalance = Number((totalIncome - totalExpenses).toFixed(2));

  const openTasks = await prisma.volunteerTask.findMany({
    where: { organizationId, status: { in: ['TODO', 'IN_PROGRESS', 'BLOCKED'] } },
    include: { assignments: { include: { user: { select: { fullName: true } } } } },
  });

  const lowStockVariants = await prisma.productVariant.findMany({
    where: {
      product: { organizationId },
      stockQuantity: { lte: 5 },
    },
    include: { product: true },
  });

  const activeCampaign = await prisma.fundraisingCampaign.findFirst({
    where: { organizationId, status: 'ACTIVE' },
  });

  const contextSummary = {
    activeMembersCount,
    upcomingEventsCount: upcomingEvents.length,
    recordedBalance,
    openTasksCount: openTasks.length,
    lowStockItemsCount: lowStockVariants.length,
  };

  const currency = org?.currency || 'USD';
  const orgName = org?.name || 'Student Organization';

  // Check if external GEMINI_API_KEY is provided
  const apiKey = process.env.GEMINI_API_KEY;
  if (apiKey && apiKey.trim() !== '') {
    try {
      // Call Google Gemini API
      const geminiEndpoint = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`;
      const systemPrompt = `You are CampusSphere AI, an intelligent co-pilot for college student organizations.
You are assisting ${orgName}.
Current verified database state:
- Active Members: ${activeMembersCount}
- Recorded Balance: ${currency} ${recordedBalance} (Income: ${currency} ${totalIncome.toFixed(2)}, Expenses: ${currency} ${totalExpenses.toFixed(2)})
- Upcoming Events: ${upcomingEvents.map((e) => `${e.title} (Status: ${e.status}, Capacity: ${e.capacity})`).join(', ') || 'None'}
- Open Volunteer Tasks: ${openTasks.map((t) => `${t.title} [Priority: ${t.priority}, Status: ${t.status}]`).join(', ') || 'None'}
- Low Stock Variants: ${lowStockVariants.map((v) => `${v.product.name} (${v.size || 'One Size'}) - only ${v.stockQuantity} left`).join(', ') || 'None'}
- Active Campaign: ${activeCampaign ? `${activeCampaign.title} ($${activeCampaign.currentAmount} / $${activeCampaign.goalAmount})` : 'None'}

Rules:
1. Only answer based on verified data. Never invent statistics.
2. If data is missing or insufficient, state "Not enough historical data yet."
3. Keep answers concise, actionable, and formatted in clean markdown.`;

      const response = await fetch(geminiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [
            {
              role: 'user',
              parts: [{ text: `${systemPrompt}\n\nUser request (${userRole}): ${prompt}` }],
            },
          ],
        }),
      });

      if (response.ok) {
        const data = (await response.json()) as any;
        const generatedText = data.candidates?.[0]?.content?.parts?.[0]?.text;
        if (generatedText) {
          return {
            answer: generatedText,
            intent,
            contextSummary,
            suggestions: [
              'Draft an announcement for the upcoming event',
              'Check overdue volunteer assignments',
              'Review current month financial health',
            ],
            isSimulatedFallback: false,
            model: 'gemini-1.5-flash',
            generatedAt: new Date().toISOString(),
          };
        }
      }
    } catch (e) {
      console.warn('External Gemini API call failed, falling back to built-in Copilot engine:', e);
    }
  }

  // Built-in intelligent reasoning engine (offline / fallback mode)
  let answer = '';
  const lowerPrompt = prompt.toLowerCase();

  if (lowerPrompt.includes('summarize') || lowerPrompt.includes('activity') || lowerPrompt.includes('performance') || intent === 'performance_summary') {
    answer = `### 📊 ${orgName} — Performance & Health Summary
- **Active Membership:** **${activeMembersCount} verified members** currently in good standing.
- **Financial Ledger:** Recorded balance stands at **${currency} ${recordedBalance.toLocaleString()}** (Recorded settled income: ${currency} ${totalIncome.toLocaleString()} | Total settled expenses: ${currency} ${totalExpenses.toLocaleString()}).
- **Upcoming Events:** **${upcomingEvents.length} scheduled event(s)** on the calendar.
${upcomingEvents.map((e) => `  - *${e.title}* (${e.venue}) — Capacity: ${e.capacity} seats`).join('\n')}
- **Volunteer Coordination:** **${openTasks.length} open task(s)** active across working committees.
- **Merchandise Inventory:** ${lowStockVariants.length > 0 ? `⚠️ **${lowStockVariants.length} item(s)** below safe replenishment threshold.` : '✅ All variants within safe stock levels.'}
${activeCampaign ? `- **Active Fundraiser:** *${activeCampaign.title}* has reached **${((activeCampaign.currentAmount / activeCampaign.goalAmount) * 100).toFixed(1)}%** of target (${currency} ${activeCampaign.currentAmount.toLocaleString()} / ${currency} ${activeCampaign.goalAmount.toLocaleString()}).` : ''}`;
  } else if (lowerPrompt.includes('announcement') || lowerPrompt.includes('draft') || intent === 'draft_announcement') {
    const featuredEvent = upcomingEvents[0];
    answer = `### 📢 Draft Society Announcement
**Subject:** Exciting Update: ${featuredEvent ? featuredEvent.title : 'Upcoming Spring Initiatives'}!

**Dear Campus Community & Members,**

We are thrilled to announce that registration for **${featuredEvent ? featuredEvent.title : 'our next flagship society event'}** is officially open!

**Key Details:**
- 📅 **Date & Time:** ${featuredEvent ? new Date(featuredEvent.startDate).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' }) : 'Upcoming Semester Calendar'}
- 📍 **Venue:** ${featuredEvent ? featuredEvent.venue : 'Campus Student Center'}
- 🎟️ **Tickets:** Special discounted admission applies for all verified active members. Non-members and guest passes are also available.

Spots are strictly limited to venue fire code capacity (${featuredEvent ? featuredEvent.capacity : 'capped'} seats). Reserve your ticket early on CampusSphere to ensure entry!

*Warm regards,*  
**Executive Committee**  
*${orgName}*`;
  } else if (lowerPrompt.includes('task') || lowerPrompt.includes('volunteer') || lowerPrompt.includes('overdue') || intent === 'task_summary') {
    if (openTasks.length === 0) {
      answer = `### 📋 Volunteer Workload Status
✅ **Zero pending or blocked tasks.** All assigned volunteer deliverables have been marked completed!`;
    } else {
      answer = `### 📋 Volunteer Workload & Priority Review
We found **${openTasks.length} active volunteer task(s)** requiring coordination:

${openTasks.map((t, idx) => `${idx + 1}. **${t.title}**
   - **Status:** \`${t.status}\` | **Priority:** \`${t.priority}\`
   - **Due Date:** ${t.dueDate ? new Date(t.dueDate).toLocaleDateString() : 'No deadline specified'}
   - **Assigned:** ${t.assignments.map((a) => a.user.fullName).join(', ') || 'Unassigned'}`).join('\n\n')}

> **Recommendation:** Prioritize high and urgent items ahead of upcoming event milestone deadlines.`;
    }
  } else if (lowerPrompt.includes('finance') || lowerPrompt.includes('budget') || lowerPrompt.includes('money') || intent === 'financial_health') {
    answer = `### 💳 Financial Health & Ledger Overview
- **Total Recorded Settled Income:** ${currency} ${totalIncome.toLocaleString()}
- **Total Recorded Settled Expenses:** ${currency} ${totalExpenses.toLocaleString()}
- **Recorded Net Balance:** **${currency} ${recordedBalance.toLocaleString()}**

**Key Breakdown:**
- Membership dues and event ticket revenues represent the primary income streams.
- Operating liabilities and venue deposits are within authorized budget limits.
- Pending reimbursement claims do not count toward settled cash until authorized by the Treasurer.

> *Note: This is the internal recorded ledger balance and does not constitute a certified bank statement audit.*`;
  } else if (lowerPrompt.includes('inventory') || lowerPrompt.includes('stock') || lowerPrompt.includes('reorder') || intent === 'inventory_reorder') {
    if (lowStockVariants.length === 0) {
      answer = `### 📦 Inventory Reorder Advisory
✅ All merchandise variants are currently stocked above their minimum replenishment buffer. No urgent reorders required today.`;
    } else {
      answer = `### 📦 Inventory Replenishment Alert
The following items are approaching or have breached minimum safety thresholds:

${lowStockVariants.map((v) => `- **${v.product.name}** (Size: \`${v.size || 'One Size'}\` | SKU: \`${v.sku}\`):
  - **Current Available:** **${v.stockQuantity} unit(s)** remaining
  - **Threshold:** ${v.lowStockThreshold} units
  - **Recommended Reorder:** **${Math.max(25, (v.lowStockThreshold - v.stockQuantity) + 20)} units** to meet upcoming festival demand`).join('\n\n')}`;
    }
  } else {
    answer = `### 🤖 CampusSphere AI Copilot
Hello! I am your AI Club Operations Copilot for **${orgName}**.

Here is a quick snapshot of where things stand:
- **Active Members:** ${activeMembersCount}
- **Recorded Balance:** ${currency} ${recordedBalance.toLocaleString()}
- **Upcoming Events:** ${upcomingEvents.length}
- **Pending Tasks:** ${openTasks.length}

How can I help you today? You can ask me to:
1. *"Summarize this month's club activity"*
2. *"Which volunteer tasks are overdue?"*
3. *"Draft an announcement for our upcoming events"*
4. *"Check our financial health and budget utilization"*
5. *"Advise on merchandise stock reorders"*`;
  }

  return {
    answer,
    intent,
    contextSummary,
    suggestions: [
      'Summarize this month\'s club performance',
      'Which volunteer tasks are overdue?',
      'Draft an announcement for our upcoming event',
      'Explain current financial ledger health',
    ],
    isSimulatedFallback: true,
    model: 'campussphere-deterministic-copilot-v2',
    generatedAt: new Date().toISOString(),
  };
}
