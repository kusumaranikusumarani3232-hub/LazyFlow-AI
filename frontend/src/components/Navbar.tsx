import React from 'react';
import { FolderGit2, Shield, Activity, RefreshCw } from 'lucide-react';
import { ModelBadge } from './ModelBadge';
import type { HealthStatus, ModelStatus } from '../types';

interface NavbarProps {
  health: HealthStatus | null;
  modelStatus: ModelStatus | null;
  connectionState: 'connecting' | 'connected' | 'error';
  onOpenPrivacy: () => void;
  onRetryConnection?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  health,
  modelStatus,
  connectionState,
  onOpenPrivacy,
  onRetryConnection,
}) => {
  let statusText = 'Connecting...';
  let statusColor = 'text-amber-400';
  let dotAnimation = 'animate-pulse';
  let tooltip = 'Connecting to backend...';

  if (connectionState === 'error') {
    statusText = 'Backend Offline';
    statusColor = 'text-rose-400';
    dotAnimation = '';
    tooltip = 'Backend is unreachable, cold-starting, or CORS is blocked. Click to retry connection.';
  } else if (connectionState === 'connected' && health) {
    dotAnimation = '';
    if (health.backboard_configured) {
      statusText = 'API Connected';
      statusColor = 'text-forest-400';
      tooltip = `Connected to ${health.app_name} | Model: ${health.model}`;
    } else {
      statusText = 'Config Required';
      statusColor = 'text-amber-400';
      tooltip = 'Backend is online, but BACKBOARD_API_KEY is missing on Render.';
    }
  }

  return (
    <header className="sticky top-0 z-40 w-full border-b border-forest-900/40 bg-charcoal-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Brand Logo & Title */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-forest-600 to-forest-900 flex items-center justify-center shadow-lg shadow-forest-900/50 border border-forest-500/30">
            <FolderGit2 className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-xl tracking-tight text-white">LazyFlow</span>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-forest-500/20 text-forest-400 border border-forest-500/30">AI</span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium hidden sm:block">
              Let AI Handle the Boring Stuff
            </p>
          </div>
        </div>

        {/* Center / Right - Model Badge & Quick Actions */}
        <div className="flex items-center gap-3">
          <ModelBadge modelStatus={modelStatus} onClickPrivacy={onOpenPrivacy} />

          {/* Privacy Button */}
          <button
            onClick={onOpenPrivacy}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:text-white bg-charcoal-900/80 hover:bg-charcoal-850 border border-slate-800 transition-all"
            title="Privacy and Security Architecture"
          >
            <Shield className="w-3.5 h-3.5 text-forest-400" />
            <span className="hidden sm:inline">Privacy Notice</span>
          </button>

          {/* Health indicator dot */}
          <button
            type="button"
            onClick={connectionState === 'error' ? onRetryConnection : undefined}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs bg-charcoal-900/80 border border-slate-800 text-slate-300 transition-all ${
              connectionState === 'error' ? 'hover:bg-rose-950/40 hover:border-rose-800 cursor-pointer' : 'cursor-default'
            }`}
            title={tooltip}
          >
            {connectionState === 'error' ? (
              <RefreshCw className="w-3.5 h-3.5 text-rose-400 animate-spin-slow" />
            ) : (
              <Activity className={`w-3.5 h-3.5 ${statusColor} ${dotAnimation}`} />
            )}
            <span className="hidden md:inline font-mono text-[11px]">
              {statusText}
            </span>
          </button>
        </div>
      </div>
    </header>
  );
};
