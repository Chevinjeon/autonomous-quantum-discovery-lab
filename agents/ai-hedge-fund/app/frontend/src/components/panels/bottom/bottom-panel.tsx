import { useResizable } from '@/hooks/use-resizable';
import { cn } from '@/lib/utils';
import { X } from 'lucide-react';
import { ReactNode, useEffect } from 'react';
import { Button } from '../../ui/button';
import { TerminalTab } from './tabs';

interface BottomPanelProps {
  children?: ReactNode;
  isCollapsed: boolean;
  onCollapse: () => void;
  onExpand: () => void;
  onToggleCollapse: () => void;
  onHeightChange?: (height: number) => void;
}

export function BottomPanel({
  isCollapsed,
  onToggleCollapse,
  onHeightChange,
}: BottomPanelProps) {
  // Use our custom hooks for vertical resizing
  const { height, isDragging, elementRef, startResize } = useResizable({
    defaultHeight: 300,
    minHeight: 200,
    maxHeight: window.innerHeight,
    side: 'bottom',
  });
  
  // Notify parent component of height changes
  useEffect(() => {
    onHeightChange?.(height);
  }, [height, onHeightChange]);

  if (isCollapsed) {
    return null;
  }

  return (
    <div 
      ref={elementRef}
      className={cn(
        "bg-panel flex flex-col relative border-t bento-card",
        isDragging ? "select-none" : ""
      )}
      style={{ 
        height: `${height}px`,
      }}
    >
      {/* Resize handle - on the top for bottom panel */}
      {!isDragging && (
        <div 
          className="absolute top-0 left-0 right-0 h-1 cursor-ns-resize transition-all duration-150 z-10 hover-bg"
          onMouseDown={startResize}
        />
      )}

      {/* Header with close button */}
      <div className="flex items-center justify-between border-b px-4 py-2">
        <div className="text-sm font-semibold text-primary">Dexter Terminal</div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggleCollapse}
          className="h-6 w-6 text-primary hover-bg"
          aria-label="Close panel"
        >
          <X size={14} />
        </Button>
      </div>

      {/* Dexter Terminal - full width */}
      <div className="flex-1 min-h-0 overflow-hidden p-4">
        <TerminalTab
          className="h-full"
          title="Dexter Terminal"
          subtitle="Your AI assistant for deep financial research."
          filterMode="dexter"
        />
      </div>
    </div>
  );
} 