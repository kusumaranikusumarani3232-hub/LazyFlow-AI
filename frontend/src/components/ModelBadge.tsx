import React from 'react';
import { Cpu, ShieldCheck } from 'lucide-react';
import type { ModelStatus } from '../types';

interface ModelBadgeProps {
  modelStatus: ModelStatus | null;
  onClickPrivacy?: () => void;
}

export const ModelBadge: React.FC<ModelBadgeProps> = ({ modelStatus, onClickPrivacy }) => {
  return (
    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-forest-950/80 border border-forest-500/30 text-xs font-medium text-forest-300 shadow-sm shadow-forest-950/50 backdrop-blur-md">
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-forest-400 opacity-75"></span>
        <span className="relative inline-flex rounded-full h-2 w-2 bg-forest-500"></span>
      </span>
      <Cpu className="w-3.5 h-3.5 text-forest-400" />
      <span className="font-semibold tracking-wide">Open-Weight AI</span>
      <span className="text-forest-600">·</span>
      <span className="text-slate-300">Powered by Backboard</span>
      {modelStatus?.model_name && (
        <span className="hidden sm:inline-block font-mono text-[11px] bg-charcoal-900/90 text-forest-400 px-2 py-0.5 rounded border border-forest-800/40">
          llama-3.1-8b
        </span>
      )}
      {onClickPrivacy && (
        <button
          onClick={onClickPrivacy}
          className="ml-1 text-slate-400 hover:text-white transition-colors flex items-center gap-1 hover:underline"
          title="Zero Content Transmission: View Privacy Policy"
        >
          <ShieldCheck className="w-3.5 h-3.5 text-forest-400" />
          <span className="hidden md:inline text-[11px]">Private</span>
        </button>
      )}
    </div>
  );
};
