'use client';

import { useState, useRef, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { api } from '@/lib/api';
import { Bot, X, Send, Loader2, User, Sparkles } from 'lucide-react';
type QueryType = 'entity' | 'temporal' | 'situation' | 'action';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

const QUERY_TYPES: { value: QueryType; label: string; placeholder: string }[] = [
  { value: 'entity',    label: 'About',     placeholder: 'Tell me about [name]…' },
  { value: 'temporal',  label: 'Who now',   placeholder: 'Who should I reach out to this week?' },
  { value: 'situation', label: 'Prep',      placeholder: 'I have a meeting with [name] about…' },
  { value: 'action',    label: 'Draft',     placeholder: 'Draft a follow-up to [name] about…' },
];

const STARTER_PROMPTS = [
  { queryType: 'temporal' as QueryType, text: 'Who needs my attention this week?' },
  { queryType: 'entity' as QueryType, text: 'Tell me about my top investor…' },
  { queryType: 'situation' as QueryType, text: 'Prep me for my next important meeting' },
  { queryType: 'action' as QueryType, text: 'Who should I re-engage that I\'ve been ignoring?' },
];

function renderText(text: string) {
  // Simple markdown-like rendering: split on double newlines for paragraphs,
  // handle **bold** and bullet lines starting with -/•
  const paragraphs = text.split(/\n\n+/);
  return (
    <div className="space-y-1.5">
      {paragraphs.map((para, i) => {
        const lines = para.split('\n');
        const isList = lines.every(l => /^[-•*]/.test(l.trim()) || l.trim() === '');
        if (isList) {
          return (
            <ul key={i} className="list-disc pl-4 space-y-0.5">
              {lines.filter(l => l.trim()).map((line, j) => (
                <li key={j} className="text-xs">{line.replace(/^[-•*]\s*/, '')}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i} className="text-xs leading-relaxed">
            {para.split(/(\*\*[^*]+\*\*)/).map((seg, j) =>
              seg.startsWith('**') ? (
                <strong key={j} className="font-semibold text-white">{seg.slice(2, -2)}</strong>
              ) : seg
            )}
          </p>
        );
      })}
    </div>
  );
}

export default function MrEliteChatbot() {
  const { data: session } = useSession();
  const orgId = (session?.user as any)?.org_id;

  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [queryType, setQueryType] = useState<QueryType>('entity');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async (text?: string) => {
    const content = (text ?? input).trim();
    if (!content || loading || !orgId) return;

    const userMsg: Message = { role: 'user', content };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const data = await api.chat.send(orgId, content, queryType, messages.slice(-6));
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
    } catch {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: 'Sorry, I ran into an error. Please try again.' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const currentType = QUERY_TYPES.find(t => t.value === queryType)!;

  return (
    <>
      {/* FAB button */}
      <button
        onClick={() => setOpen(o => !o)}
        className={`fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 rounded-full shadow-lg transition-all duration-200
          ${open
            ? 'bg-slate-700 text-white'
            : 'bg-indigo-600 hover:bg-indigo-500 text-white'
          }`}
        title="Ask Mr. Elite"
      >
        {open ? <X className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
        <span className="text-sm font-medium">{open ? 'Close' : 'Mr. Elite'}</span>
      </button>

      {/* Chat Panel */}
      {open && (
        <div className="fixed bottom-20 right-6 z-50 w-[380px] max-h-[600px] flex flex-col rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl overflow-hidden">

          {/* Header */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-800 shrink-0">
            <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center shrink-0">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Mr. Elite</p>
              <p className="text-[10px] text-slate-500">Relationship Intelligence</p>
            </div>
            <button
              onClick={() => setMessages([])}
              className="ml-auto text-[10px] text-slate-600 hover:text-slate-400 transition-colors"
            >
              Clear
            </button>
          </div>

          {/* Query type selector */}
          <div className="flex items-center gap-1 px-3 py-2 border-b border-slate-800 shrink-0">
            {QUERY_TYPES.map(t => (
              <button
                key={t.value}
                onClick={() => setQueryType(t.value)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors
                  ${queryType === t.value
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800'
                  }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
            {messages.length === 0 ? (
              <div className="space-y-2 pt-2">
                <p className="text-xs text-slate-500 text-center">Ask about your relationships</p>
                <div className="grid grid-cols-1 gap-1.5">
                  {STARTER_PROMPTS.map((p, i) => (
                    <button
                      key={i}
                      onClick={() => { setQueryType(p.queryType); send(p.text); }}
                      className="text-left text-[11px] text-slate-400 bg-slate-800 hover:bg-slate-700 rounded-lg px-3 py-2 transition-colors"
                    >
                      {p.text}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, i) => (
                <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {msg.role === 'assistant' && (
                    <div className="w-6 h-6 rounded-full bg-indigo-600/30 flex items-center justify-center shrink-0 mt-0.5">
                      <Bot className="w-3 h-3 text-indigo-400" />
                    </div>
                  )}
                  <div
                    className={`max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed
                      ${msg.role === 'user'
                        ? 'bg-indigo-600 text-white rounded-tr-sm'
                        : 'bg-slate-800 text-slate-300 rounded-tl-sm'
                      }`}
                  >
                    {msg.role === 'assistant' ? renderText(msg.content) : msg.content}
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-6 h-6 rounded-full bg-slate-700 flex items-center justify-center shrink-0 mt-0.5">
                      <User className="w-3 h-3 text-slate-400" />
                    </div>
                  )}
                </div>
              ))
            )}
            {loading && (
              <div className="flex gap-2 justify-start">
                <div className="w-6 h-6 rounded-full bg-indigo-600/30 flex items-center justify-center shrink-0">
                  <Bot className="w-3 h-3 text-indigo-400" />
                </div>
                <div className="bg-slate-800 rounded-xl rounded-tl-sm px-3 py-2">
                  <Loader2 className="w-3.5 h-3.5 text-slate-400 animate-spin" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="shrink-0 border-t border-slate-800 p-3">
            <div className="flex items-end gap-2 bg-slate-800 rounded-xl px-3 py-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={currentType.placeholder}
                rows={1}
                className="flex-1 bg-transparent text-xs text-white placeholder-slate-500 resize-none outline-none max-h-20 scrollbar-hide"
                style={{ lineHeight: '1.5' }}
              />
              <button
                onClick={() => send()}
                disabled={!input.trim() || loading}
                className="p-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-colors shrink-0"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
            <p className="text-[10px] text-slate-600 mt-1.5 text-center">
              Shift+Enter for new line · Enter to send
            </p>
          </div>
        </div>
      )}
    </>
  );
}
