import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import {
  Sparkles,
  Send,
  Bot,
  User,
  ShieldCheck,
  Zap,
  BarChart2,
  Calendar,
  Wallet,
  Package,
  CheckCircle2,
} from 'lucide-react';

interface ChatMessage {
  id: string;
  sender: 'USER' | 'COPILOT';
  text: string;
  timestamp: string;
  contextSummary?: any;
  model?: string;
}

const SUGGESTED_PROMPTS = [
  { label: "Summarize this month's club performance", intent: 'performance_summary' },
  { label: 'Which volunteer tasks are overdue?', intent: 'task_summary' },
  { label: 'Draft an announcement for our upcoming event', intent: 'draft_announcement' },
  { label: 'Explain current financial ledger health', intent: 'financial_health' },
  { label: 'Advise on merchandise stock reorders', intent: 'inventory_reorder' },
];

export const AiCopilotPage: React.FC = () => {
  const { currentOrg, role } = useAuth();
  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init-1',
      sender: 'COPILOT',
      text: `### 🤖 Welcome to CampusSphere AI Copilot
I am your intelligent operations advisor for **${currentOrg?.name || 'Skyline Student Association'}**.

I have read-only access to your organization's verified database records:
- **Membership:** Roster standing & renewal statuses
- **Ticketing:** Live booking capacity & check-in counts
- **Financial Ledger:** Settled revenues, operating costs, and recorded balance
- **Tasks & Workload:** Committee task boards and overdue deadlines
- **Merchandise:** Variant inventory levels and low-stock buffers

Choose a suggestion below or type your question:`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      model: 'campussphere-deterministic-copilot-v2',
    },
  ]);

  const queryMutation = useMutation({
    mutationFn: ({ p, intent }: { p: string; intent?: string }) => api.queryCopilot(p, intent),
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        {
          id: `msg-${Date.now()}`,
          sender: 'COPILOT',
          text: data.answer,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          contextSummary: data.contextSummary,
          model: data.model,
        },
      ]);
    },
  });

  const handleSend = (textToSend?: string, intent = 'general') => {
    const q = textToSend || prompt;
    if (!q.trim() || queryMutation.isPending) return;

    setMessages((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        sender: 'USER',
        text: q,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);

    setPrompt('');
    queryMutation.mutate({ p: q, intent });
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 flex items-center gap-2.5">
            <Sparkles className="w-6 h-6 text-violet-600" />
            <span>AI Club Operations Copilot</span>
          </h1>
          <p className="text-xs text-slate-600 font-medium mt-1">
            Permission-filtered AI assistant grounded in actual organization data without fabrication.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-teal-700 bg-teal-50 border border-teal-200 px-2.5 py-1 rounded-full flex items-center gap-1.5 shadow-2xs">
            <ShieldCheck className="w-3.5 h-3.5 text-teal-600" />
            <span>TENANT DATA ISOLATION ACTIVE</span>
          </span>
        </div>
      </div>

      {/* Suggested Prompt Chips */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {SUGGESTED_PROMPTS.map((chip, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(chip.label, chip.intent)}
            disabled={queryMutation.isPending}
            className="px-3 py-1.5 rounded-xl bg-white border border-slate-200 hover:border-indigo-400 text-slate-700 hover:text-indigo-600 text-xs font-semibold whitespace-nowrap transition flex items-center gap-1.5 disabled:opacity-50 shadow-2xs"
          >
            <Zap className="w-3 h-3 text-amber-500" />
            <span>{chip.label}</span>
          </button>
        ))}
      </div>

      {/* Chat Messages Container */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 sm:p-6 min-h-[480px] max-h-[600px] overflow-y-auto space-y-4 shadow-sm">
        {messages.map((m) => {
          const isCopilot = m.sender === 'COPILOT';
          return (
            <div
              key={m.id}
              className={`flex gap-3 ${isCopilot ? 'items-start' : 'items-start justify-end'}`}
            >
              {isCopilot && (
                <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-violet-600 to-indigo-600 flex items-center justify-center text-white shrink-0 shadow-md shadow-indigo-500/20">
                  <Bot className="w-4 h-4" />
                </div>
              )}

              <div
                className={`max-w-[85%] rounded-2xl p-4 text-xs leading-relaxed ${
                  isCopilot
                    ? 'bg-slate-50 border border-slate-200/90 text-slate-800'
                    : 'bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-md shadow-indigo-500/20'
                }`}
              >
                <div className="whitespace-pre-line max-w-none text-xs font-normal">
                  {m.text}
                </div>

                <div className={`mt-2 pt-2 border-t flex items-center justify-between text-[10px] ${
                  isCopilot ? 'border-slate-200 text-slate-500' : 'border-white/20 text-indigo-100'
                }`}>
                  <span>{m.timestamp}</span>
                  {m.model && (
                    <span className="font-mono text-indigo-600 font-semibold">Engine: {m.model}</span>
                  )}
                </div>
              </div>

              {!isCopilot && (
                <div className="w-8 h-8 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-700 shrink-0 font-bold">
                  <User className="w-4 h-4" />
                </div>
              )}
            </div>
          );
        })}

        {queryMutation.isPending && (
          <div className="flex gap-3 items-center text-xs text-indigo-600 animate-pulse font-semibold">
            <div className="w-8 h-8 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
              <Bot className="w-4 h-4" />
            </div>
            <span>Analyzing organization records & synthesizing response...</span>
          </div>
        )}
      </div>

      {/* Input Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="flex gap-2"
      >
        <input
          type="text"
          placeholder="Ask a question about your events, ledger balance, tasks or members..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={queryMutation.isPending}
          className="flex-1 px-4 py-3 rounded-2xl bg-white border border-slate-300 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-indigo-500 transition shadow-2xs"
        />
        <button
          type="submit"
          disabled={!prompt.trim() || queryMutation.isPending}
          className="px-5 py-3 rounded-2xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold text-xs shadow-md shadow-indigo-500/20 hover:opacity-95 disabled:opacity-50 transition flex items-center gap-2"
        >
          <Send className="w-4 h-4" />
          <span>Ask Copilot</span>
        </button>
      </form>
    </div>
  );
};
