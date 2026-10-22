import React from 'react';
import { Download, RefreshCw, AlertTriangle } from 'lucide-react';
import type { FileOrganizedItem } from '../types';

interface DownloadActionProps {
  items: FileOrganizedItem[];
  onDownload: () => void;
  onReset: () => void;
  isDownloading: boolean;
}

export const DownloadAction: React.FC<DownloadActionProps> = ({
  items,
  onDownload,
  onReset,
  isDownloading,
}) => {
  const activeCount = items.filter((i) => !i.excluded).length;
  const excludedCount = items.filter((i) => i.excluded).length;

  return (
    <div className="glass-panel p-5 sm:p-6 rounded-2xl border border-forest-500/30 shadow-xl shadow-forest-950/40 flex flex-col sm:flex-row items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-forest-950/80 border border-forest-500/40 flex items-center justify-center text-forest-400 shrink-0">
          <Download className="w-6 h-6 animate-pulse" />
        </div>
        <div>
          <h3 className="font-bold text-white text-base">Ready to Export Archive</h3>
          <p className="text-xs text-slate-400">
            {activeCount > 0 ? (
              <span>
                Packaging <strong className="text-forest-300 font-mono">{activeCount}</strong> files into neat folders.
                {excludedCount > 0 && ` (${excludedCount} excluded)`}
              </span>
            ) : (
              <span className="text-amber-400 flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" />
                No files selected. Please include at least one file.
              </span>
            )}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3 w-full sm:w-auto">
        <button
          onClick={onReset}
          className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-300 hover:text-white bg-charcoal-900 hover:bg-charcoal-850 border border-slate-800 transition-colors flex items-center justify-center gap-1.5 w-1/3 sm:w-auto"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Start Over</span>
        </button>

        <button
          onClick={onDownload}
          disabled={isDownloading || activeCount === 0}
          className="px-6 py-2.5 rounded-xl bg-forest-600 hover:bg-forest-500 disabled:opacity-50 text-white font-bold text-sm shadow-lg shadow-forest-900/60 transition-all flex items-center justify-center gap-2 flex-1 sm:flex-initial"
        >
          {isDownloading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Packaging ZIP...</span>
            </>
          ) : (
            <>
              <Download className="w-4 h-4" />
              <span>Download Organized ZIP</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
