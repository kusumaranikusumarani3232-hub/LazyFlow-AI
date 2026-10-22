import React from 'react';
import { AlertCircle, Key, X } from 'lucide-react';
import type { HealthStatus } from '../types';

interface StatusBannerProps {
  health: HealthStatus | null;
  errorMessage: string | null;
  onClearError: () => void;
}

export const StatusBanner: React.FC<StatusBannerProps> = ({
  health,
  errorMessage,
  onClearError,
}) => {
  const isMisconfigured = health && !health.backboard_configured;

  if (!isMisconfigured && !errorMessage) return null;

  return (
    <div className="max-w-4xl mx-auto space-y-3 px-4">
      {/* Misconfigured API Key Alert */}
      {isMisconfigured && (
        <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-600/40 text-amber-200 text-xs flex items-start gap-3 shadow-lg">
          <Key className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="font-semibold text-amber-100 mb-0.5">Backboard API Key Required</h4>
            <p className="text-amber-300/90 leading-relaxed">
              Backboard API key is not configured or is missing. Please set your <code className="bg-amber-900/60 px-1 py-0.5 rounded font-mono text-amber-100">BACKBOARD_API_KEY</code> in <code className="bg-amber-900/60 px-1 py-0.5 rounded font-mono text-amber-100">backend/.env</code>.
            </p>
          </div>
        </div>
      )}

      {/* Error Message Alert */}
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
            onClick={onClearError}
            className="p-1 text-rose-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
};
