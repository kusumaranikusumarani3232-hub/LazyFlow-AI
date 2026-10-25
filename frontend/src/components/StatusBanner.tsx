import React from 'react';
import { AlertCircle, Key, RefreshCw, ServerCrash, X } from 'lucide-react';
import type { HealthStatus } from '../types';

interface StatusBannerProps {
  health: HealthStatus | null;
  connectionState: 'connecting' | 'connected' | 'error';
  connectionError: string | null;
  errorMessage: string | null;
  onClearError: () => void;
  onRetryConnection: () => void;
}

export const StatusBanner: React.FC<StatusBannerProps> = ({
  health,
  connectionState,
  connectionError,
  errorMessage,
  onClearError,
  onRetryConnection,
}) => {
  const isMisconfigured = Boolean(health && !health.backboard_configured);
  const hasConnectionError = connectionState === 'error' && Boolean(connectionError);
  const isWakingUp = connectionState === 'connecting' && Boolean(connectionError);

  if (!isMisconfigured && !hasConnectionError && !isWakingUp && !errorMessage) {
    return null;
  }

  return (
    <div className="max-w-4xl mx-auto space-y-3 px-4">
      {/* Backend Waking Up Notice */}
      {isWakingUp && (
        <div className="p-3.5 rounded-xl bg-blue-950/40 border border-blue-600/40 text-blue-200 text-xs flex items-center justify-between gap-3 shadow-lg animate-pulse">
          <div className="flex items-center gap-2.5">
            <RefreshCw className="w-4 h-4 text-blue-400 animate-spin shrink-0" />
            <p className="text-blue-200 font-medium leading-relaxed">
              {connectionError}
            </p>
          </div>
        </div>
      )}

      {/* Backend Connection Error Alert */}
      {hasConnectionError && (
        <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-600/40 text-amber-200 text-xs flex items-start justify-between gap-3 shadow-lg">
          <div className="flex items-start gap-3">
            <ServerCrash className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-amber-100 mb-0.5">
                Backend Connection Notice
              </h4>
              <p className="text-amber-300/90 leading-relaxed mb-2">
                {connectionError}
              </p>
              <button
                type="button"
                onClick={onRetryConnection}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-amber-600/20 hover:bg-amber-600/30 text-amber-200 border border-amber-500/40 font-medium transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry Connection</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Misconfigured API Key Alert (Backend is alive, but missing BACKBOARD_API_KEY) */}
      {isMisconfigured && (
        <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-600/40 text-amber-200 text-xs flex items-start gap-3 shadow-lg">
          <Key className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="font-semibold text-amber-100 mb-0.5">Backboard API Key Required</h4>
            <p className="text-amber-300/90 leading-relaxed">
              The backend is running, but the Backboard API key is missing. Please set your{' '}
              <code className="bg-amber-900/60 px-1 py-0.5 rounded font-mono text-amber-100">
                BACKBOARD_API_KEY
              </code>{' '}
              in your Render environment variables or <code className="bg-amber-900/60 px-1 py-0.5 rounded font-mono text-amber-100">backend/.env</code>.
            </p>
          </div>
        </div>
      )}

      {/* Operation Error Message Alert */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-600/40 text-rose-200 text-xs flex items-start justify-between gap-3 shadow-lg">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-rose-100 mb-0.5">Operation Notice</h4>
              <p className="text-rose-300/90 leading-relaxed">{errorMessage}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClearError}
            className="p-1 text-rose-400 hover:text-white transition-colors"
            title="Dismiss notice"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
};
