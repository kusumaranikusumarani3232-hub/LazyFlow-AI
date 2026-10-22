import React from 'react';
import { Files, FolderTree, Edit3, EyeOff, Folder } from 'lucide-react';
import type { FileOrganizedItem } from '../types';

interface CategorySummaryProps {
  items: FileOrganizedItem[];
  categoriesSummary: Record<string, number>;
  selectedFilter: string | null;
  onSelectFilter: (category: string | null) => void;
}

export const CategorySummary: React.FC<CategorySummaryProps> = ({
  items,
  categoriesSummary,
  selectedFilter,
  onSelectFilter,
}) => {
  const totalFiles = items.length;
  const activeFiles = items.filter((i) => !i.excluded).length;
  const excludedFiles = items.filter((i) => i.excluded).length;
  const renamedFiles = items.filter(
    (i) => i.suggested_filename.toLowerCase() !== i.original_filename.toLowerCase()
  ).length;
  const folderCount = Object.keys(categoriesSummary).length;

  return (
    <div className="space-y-4">
      {/* 4 Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="glass-panel p-4 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium">Total Files</span>
            <Files className="w-4 h-4 text-forest-400" />
          </div>
          <div className="text-2xl font-bold text-white font-mono">{totalFiles}</div>
          <p className="text-[11px] text-slate-500 mt-1">{activeFiles} approved for ZIP</p>
        </div>

        <div className="glass-panel p-4 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium">Smart Renamed</span>
            <Edit3 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 font-mono">{renamedFiles}</div>
          <p className="text-[11px] text-slate-500 mt-1">Clean descriptive names</p>
        </div>

        <div className="glass-panel p-4 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium">Folders Created</span>
            <FolderTree className="w-4 h-4 text-forest-400" />
          </div>
          <div className="text-2xl font-bold text-forest-300 font-mono">{folderCount}</div>
          <p className="text-[11px] text-slate-500 mt-1">Structured categories</p>
        </div>

        <div className="glass-panel p-4 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium">Excluded Files</span>
            <EyeOff className="w-4 h-4 text-slate-400" />
          </div>
          <div className="text-2xl font-bold text-slate-300 font-mono">{excludedFiles}</div>
          <p className="text-[11px] text-slate-500 mt-1">Skipped by choice</p>
        </div>
      </div>

      {/* Category Filter Chips */}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <span className="text-xs text-slate-400 mr-1 flex items-center gap-1">
          <Folder className="w-3.5 h-3.5 text-forest-400" />
          <span>Filter folder:</span>
        </span>

        <button
          onClick={() => onSelectFilter(null)}
          className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
            selectedFilter === null
              ? 'bg-forest-600 text-white shadow-sm shadow-forest-900/60'
              : 'bg-charcoal-900 text-slate-400 hover:text-white border border-slate-800'
          }`}
        >
          All ({totalFiles})
        </button>

        {Object.entries(categoriesSummary).map(([folder, count]) => {
          const isSelected = selectedFilter === folder;
          return (
            <button
              key={folder}
              onClick={() => onSelectFilter(isSelected ? null : folder)}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
                isSelected
                  ? 'bg-forest-600 text-white shadow-sm shadow-forest-900/60'
                  : 'bg-charcoal-900 text-slate-300 hover:text-white border border-slate-800 hover:border-forest-700/50'
              }`}
            >
              <span>{folder}</span>
              <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
                isSelected ? 'bg-forest-800 text-white' : 'bg-charcoal-800 text-forest-400'
              }`}>
                {count}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
