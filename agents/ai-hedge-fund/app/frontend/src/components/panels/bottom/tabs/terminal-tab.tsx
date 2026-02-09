import { useFlowContext } from '@/contexts/flow-context';
import { MessageItem, useNodeContext } from '@/contexts/node-context';
import { cn } from '@/lib/utils';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useEffect, useMemo, useRef, useState } from 'react';
import { getDisplayName } from './output-tab-utils';

interface TerminalTabProps {
  className?: string;
  title?: string;
  subtitle?: string;
  filterMode?: 'all' | 'dexter' | 'non-dexter';
}

type CliLine = {
  key: string;
  timestamp: string | null;
  agentId: string;
  ticker: string | null;
  message: string;
  analysis: MessageItem['analysis'];
  displayName?: string;
};

export function TerminalTab({
  className,
  title = 'Terminal',
  subtitle,
  filterMode = 'all',
}: TerminalTabProps) {
  const { currentFlowId } = useFlowContext();
  const { getAgentNodeDataForFlow } = useNodeContext();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [prompt, setPrompt] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [localLines, setLocalLines] = useState<CliLine[]>([]);

  const agentData = getAgentNodeDataForFlow(currentFlowId?.toString() || null);

  const cliLines = useMemo(() => {
    const lines: CliLine[] = [];
    Object.entries(agentData).forEach(([agentId, data]) => {
      data.messages.forEach((msg, idx) => {
        lines.push({
          key: `${agentId}-${msg.timestamp}-${idx}`,
          timestamp: msg.timestamp || null,
          agentId,
          ticker: msg.ticker,
          message: msg.message,
          analysis: msg.analysis,
        });
      });
    });

    const merged = [...lines, ...localLines];

    const filtered = merged.filter((line) => {
      const isDexter = line.agentId.toLowerCase().includes('dexter');
      if (filterMode === 'dexter') return isDexter || line.agentId === 'dexter_user';
      if (filterMode === 'non-dexter') return !isDexter;
      return true;
    });

    return filtered.sort((a, b) => {
      const timeA = a.timestamp ? new Date(a.timestamp).getTime() : 0;
      const timeB = b.timestamp ? new Date(b.timestamp).getTime() : 0;
      return timeA - timeB;
    });
  }, [agentData, filterMode, localLines]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [cliLines.length]);

  const sendPrompt = async () => {
    const trimmed = prompt.trim();
    if (!trimmed || isSending) return;
    const timestamp = new Date().toISOString();
    const userLine: CliLine = {
      key: `dexter_user-${timestamp}`,
      timestamp,
      agentId: 'dexter_user',
      ticker: null,
      message: trimmed,
      analysis: {},
      displayName: 'You',
    };

    setLocalLines((prev) => [...prev, userLine]);
    setPrompt('');
    setIsSending(true);

    try {
      const response = await api.dexterChat({ prompt: trimmed });
      const dexterTimestamp = new Date().toISOString();
      setLocalLines((prev) => [
        ...prev,
        {
          key: `dexter-${dexterTimestamp}`,
          timestamp: dexterTimestamp,
          agentId: 'dexter_terminal',
          ticker: null,
          message: response.response,
          analysis: {},
          displayName: 'Dexter',
        },
      ]);
    } catch (error) {
      const dexterTimestamp = new Date().toISOString();
      setLocalLines((prev) => [
        ...prev,
        {
          key: `dexter-error-${dexterTimestamp}`,
          timestamp: dexterTimestamp,
          agentId: 'dexter_terminal',
          ticker: null,
          message: '⚠️ Dexter could not respond. Please try again.',
          analysis: {},
          displayName: 'Dexter',
        },
      ]);
      console.error(error);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className={cn("h-full bento-card flex flex-col overflow-hidden", className)}>
      <div className="flex items-start justify-between border-b border-border/60 px-3 py-2 shrink-0">
        <div>
          <div className="text-sm font-semibold text-primary">{title}</div>
          {subtitle ? <div className="text-xs text-muted-foreground">{subtitle}</div> : null}
        </div>
        <div className="text-xs text-muted-foreground">⌘J to toggle</div>
      </div>
      <div ref={containerRef} className="flex-1 min-h-0 rounded-md p-3 font-mono text-sm overflow-auto story-scroll">
        {cliLines.length === 0 && filterMode === 'dexter' ? (
          <div className="space-y-3 text-muted-foreground">
            <pre className="text-[#258bff] whitespace-pre leading-tight">
{`══════════════════════════════════════════════════
║          Welcome to Dexter v3.0.2              ║
══════════════════════════════════════════════════`}
            </pre>
            <pre className="text-[#258bff] font-bold whitespace-pre leading-tight" style={{ fontSize: '0.65rem' }}>
{`██████╗ ███████╗██╗  ██╗████████╗███████╗██████╗
██╔══██╗██╔════╝╚██╗██╔╝╚══██╔══╝██╔════╝██╔══██╗
██║  ██║█████╗   ╚███╔╝    ██║   █████╗  ██████╔╝
██║  ██║██╔══╝   ██╔██╗    ██║   ██╔══╝  ██╔══██╗
██████╔╝███████╗██╔╝ ██╗   ██║   ███████╗██║  ██║
╚═════╝ ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝`}
            </pre>
            <div>Your AI assistant for deep financial research.</div>
            <div className="text-[#a6a6a6]">Type below to start a conversation.</div>
          </div>
        ) : cliLines.length === 0 ? (
          <div className="text-muted-foreground">No CLI output yet — start a run and let the story stream 📜.</div>
        ) : (
          <div className="space-y-2">
            {cliLines.map((line) => {
              const timeLabel = line.timestamp
                ? new Date(line.timestamp).toLocaleTimeString()
                : '--:--:--';
              const displayName = line.displayName || getDisplayName(line.agentId);

              return (
                <div key={line.key} className="whitespace-pre-wrap">
                  <span className="text-muted-foreground">[{timeLabel}]</span>{' '}
                  <span className="text-primary">{displayName}</span>
                  {line.ticker ? <span className="text-muted-foreground"> [{line.ticker}]</span> : null}
                  <span className="text-muted-foreground">:</span>{' '}
                  <span className="text-foreground">{line.message}</span>
                  {line.analysis && Object.keys(line.analysis).length > 0 && (
                    <div className="pl-5 text-muted-foreground">
                      {Object.entries(line.analysis).map(([ticker, analysis]) => (
                        <div key={`${line.key}-${ticker}`} className="whitespace-pre-wrap">
                          <span className="text-primary">{ticker}:</span> {analysis}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
        </div>
        )}
      </div>
      {filterMode === 'dexter' ? (
        <div className="border-t border-border/60 px-3 py-2 shrink-0">
          <div className="flex items-center gap-2">
            <Input
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  sendPrompt();
                }
              }}
              placeholder="Ask Dexter anything…"
              className="h-9"
              disabled={isSending}
            />
            <Button
              onClick={sendPrompt}
              disabled={isSending || !prompt.trim()}
              className="h-9"
            >
              {isSending ? 'Sending…' : 'Send'}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
} 