import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { PanelBottom, PanelLeft, PanelRight, Settings, Sparkles, Moon, Sun } from 'lucide-react';
import { useTheme } from 'next-themes';

interface TopBarProps {
  isLeftCollapsed: boolean;
  isRightCollapsed: boolean;
  isBottomCollapsed: boolean;
  onToggleLeft: () => void;
  onToggleRight: () => void;
  onToggleBottom: () => void;
  onSettingsClick: () => void;
}

export function TopBar({
  isLeftCollapsed,
  isRightCollapsed,
  isBottomCollapsed,
  onToggleLeft,
  onToggleRight,
  onToggleBottom,
  onSettingsClick,
}: TopBarProps) {
  const { resolvedTheme, setTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  return (
    <div className="absolute top-0 left-0 right-0 z-40 flex items-center justify-between gap-3 py-2 px-3 bg-panel/70 backdrop-blur-xl border-b bento-card">
      <div className="flex items-center gap-3 text-sm text-muted-foreground">
        <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-white/70 text-primary shadow-sm">
          <Sparkles size={14} />
        </span>
        <div className="hidden sm:block">
          SynQubi — Let the agents research, debate, and converge on a portfolio recommendation.
        </div>
        <div className="sm:hidden">SynQubi</div>
      </div>
      {/* Left Sidebar Toggle */}
      <div className="flex items-center gap-0">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setTheme(isDark ? 'light' : 'dark')}
          className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors"
          aria-label="Toggle theme"
          title={isDark ? 'Switch to Day Mode' : 'Switch to Night Mode'}
        >
          {isDark ? <Sun size={16} /> : <Moon size={16} />}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleLeft}
          className={cn(
            "h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors",
            !isLeftCollapsed && "text-foreground"
          )}
          aria-label="Toggle left sidebar"
          title="Toggle Left Side Bar (⌘B)"
        >
          <PanelLeft size={16} />
        </Button>

      {/* Bottom Panel Toggle */}
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleBottom}
          className={cn(
            "h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors",
            !isBottomCollapsed && "text-foreground"
          )}
          aria-label="Toggle bottom panel"
          title="Toggle Bottom Panel (⌘J)"
        >
          <PanelBottom size={16} />
        </Button>

      {/* Right Sidebar Toggle */}
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleRight}
          className={cn(
            "h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors",
            !isRightCollapsed && "text-foreground"
          )}
          aria-label="Toggle right sidebar"
          title="Toggle Right Side Bar (⌘I)"
        >
          <PanelRight size={16} />
        </Button>

      {/* Divider */}
        <div className="w-px h-5 bg-ramp-grey-700 mx-1" />

      {/* Settings */}
        <Button
          variant="ghost"
          size="sm"
          onClick={onSettingsClick}
          className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors"
          aria-label="Open settings"
          title="Open Settings (⌘,)"
        >
          <Settings size={16} />
        </Button>
      </div>
    </div>
  );
} 