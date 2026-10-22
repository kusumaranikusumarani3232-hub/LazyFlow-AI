import React, { useState } from 'react';
import {
  Folder,
  FileText,
  Image as ImageIcon,
  Check,
  Edit2,
  Undo2,
  Search
} from 'lucide-react';
import type { FileOrganizedItem } from '../types';

interface ReviewTableProps {
  items: FileOrganizedItem[];
  onToggleExclude: (id: string) => void;
  onUpdateFilename: (id: string, newName: string) => void;
  onUpdateFolder: (id: string, newFolder: string) => void;
  onToggleAll: (selectAll: boolean) => void;
  selectedFilter: string | null;
  availableFolders: string[];
}

export const ReviewTable: React.FC<ReviewTableProps> = ({
  items,
  onToggleExclude,
  onUpdateFilename,
  onUpdateFolder,
  onToggleAll,
  selectedFilter,
  availableFolders,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [tempFilename, setTempFilename] = useState('');

  // Filter items by selected category and search query
  const filteredItems = items.filter((item) => {
    const matchesFilter = selectedFilter ? item.folder === selectedFilter : true;
    const matchesSearch = searchQuery
      ? item.original_filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.suggested_filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.folder.toLowerCase().includes(searchQuery.toLowerCase())
      : true;
    return matchesFilter && matchesSearch;
  });

  const allActive = items.every((i) => !i.excluded);
  const noneActive = items.every((i) => i.excluded);

  const startEditing = (item: FileOrganizedItem) => {
    setEditingId(item.id);
    setTempFilename(item.suggested_filename);
  };

  const saveEditing = (id: string) => {
    if (tempFilename.trim()) {
      onUpdateFilename(id, tempFilename.trim());
    }
    setEditingId(null);
  };

  const cancelEditing = () => {
    setEditingId(null);
  };

  return (
    <div className="glass-panel rounded-2xl border border-slate-800 overflow-hidden space-y-4">
      {/* Table Header Controls */}
      <div className="p-4 sm:p-5 border-b border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold text-white tracking-tight">Review & Customize</h2>
          <span className="text-xs text-slate-400">
            Showing {filteredItems.length} of {items.length} files
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Search Input */}
          <div className="relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search files..."
              className="pl-9 pr-3 py-1.5 rounded-lg bg-charcoal-900 border border-slate-800 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-forest-500/50 w-44 sm:w-56"
            />
          </div>

          {/* Bulk Select / Deselect */}
          <button
            onClick={() => onToggleAll(noneActive || !allActive)}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-charcoal-900 hover:bg-charcoal-850 border border-slate-800 text-slate-300 hover:text-white transition-colors"
          >
            {allActive ? 'Exclude All' : 'Include All'}
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-800/80 bg-charcoal-900/60 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
              <th className="py-3 px-4 w-12 text-center">Status</th>
              <th className="py-3 px-4">Original Filename</th>
              <th className="py-3 px-4">Destination Folder</th>
              <th className="py-3 px-4">AI Suggested Filename</th>
              <th className="py-3 px-4 hidden md:table-cell">AI Classification Reason</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/40">
            {filteredItems.map((item) => {
              const isEditing = editingId === item.id;
              const isExcluded = item.excluded;

              return (
                <tr
                  key={item.id}
                  className={`transition-colors hover:bg-charcoal-900/40 ${
                    isExcluded ? 'opacity-40 bg-charcoal-950/40' : ''
                  }`}
                >
                  {/* Status checkbox */}
                  <td className="py-3.5 px-4 text-center">
                    <button
                      onClick={() => onToggleExclude(item.id)}
                      className={`w-5 h-5 rounded flex items-center justify-center border transition-colors ${
                        !isExcluded
                          ? 'bg-forest-600 border-forest-500 text-white'
                          : 'bg-charcoal-900 border-slate-700 text-transparent'
                      }`}
                      title={isExcluded ? 'Include in ZIP' : 'Exclude from ZIP'}
                    >
                      <Check className="w-3.5 h-3.5" />
                    </button>
                  </td>

                  {/* Original name */}
                  <td className="py-3.5 px-4 font-mono text-slate-300 max-w-[200px] truncate">
                    <div className="flex items-center gap-2">
                      <span className="text-slate-500 shrink-0">
                        {item.original_filename.match(/\.(jpg|jpeg|png|gif|webp)$/i) ? (
                          <ImageIcon className="w-3.5 h-3.5 text-forest-400" />
                        ) : (
                          <FileText className="w-3.5 h-3.5 text-slate-400" />
                        )}
                      </span>
                      <span className="truncate" title={item.original_filename}>
                        {item.original_filename}
                      </span>
                    </div>
                  </td>

                  {/* Destination folder */}
                  <td className="py-3.5 px-4">
                    <div className="relative inline-flex items-center">
                      <Folder className="w-3.5 h-3.5 text-forest-400 mr-1.5 shrink-0" />
                      <select
                        value={item.folder}
                        onChange={(e) => onUpdateFolder(item.id, e.target.value)}
                        disabled={isExcluded}
                        className="bg-charcoal-900 border border-slate-700/80 rounded px-2 py-1 text-xs text-forest-300 font-medium focus:outline-none focus:border-forest-500 cursor-pointer disabled:cursor-not-allowed"
                      >
                        {availableFolders.map((f) => (
                          <option key={f} value={f} className="bg-charcoal-900 text-slate-200">
                            {f}
                          </option>
                        ))}
                      </select>
                    </div>
                  </td>

                  {/* Suggested filename */}
                  <td className="py-3.5 px-4 max-w-[260px]">
                    {isEditing ? (
                      <div className="flex items-center gap-1.5">
                        <input
                          type="text"
                          value={tempFilename}
                          onChange={(e) => setTempFilename(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') saveEditing(item.id);
                            if (e.key === 'Escape') cancelEditing();
                          }}
                          autoFocus
                          className="w-full px-2 py-1 rounded bg-charcoal-950 border border-forest-500 text-xs font-mono text-white focus:outline-none"
                        />
                        <button
                          onClick={() => saveEditing(item.id)}
                          className="p-1 rounded bg-forest-600 hover:bg-forest-500 text-white shrink-0"
                          title="Save"
                        >
                          <Check className="w-3 h-3" />
                        </button>
                        <button
                          onClick={cancelEditing}
                          className="p-1 rounded bg-charcoal-800 hover:bg-charcoal-700 text-slate-400 shrink-0"
                          title="Cancel"
                        >
                          <Undo2 className="w-3 h-3" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between group">
                        <span
                          className={`font-mono truncate ${
                            item.user_modified
                              ? 'text-amber-300 font-semibold'
                              : 'text-forest-400 font-medium'
                          }`}
                          title={item.suggested_filename}
                        >
                          {item.suggested_filename}
                        </span>
                        {!isExcluded && (
                          <button
                            onClick={() => startEditing(item)}
                            className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-white transition-opacity ml-2 shrink-0"
                            title="Edit filename"
                          >
                            <Edit2 className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    )}
                  </td>

                  {/* Reason */}
                  <td className="py-3.5 px-4 hidden md:table-cell text-slate-400 max-w-[260px] truncate" title={item.reason}>
                    <span className="italic">{item.reason}</span>
                  </td>

                  {/* Exclude / Include toggle */}
                  <td className="py-3.5 px-4 text-right">
                    <button
                      onClick={() => onToggleExclude(item.id)}
                      className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
                        isExcluded
                          ? 'bg-charcoal-900 text-slate-400 hover:text-white border border-slate-800'
                          : 'bg-forest-950/60 text-forest-300 hover:bg-rose-950/50 hover:text-rose-300 border border-forest-800/40'
                      }`}
                    >
                      {isExcluded ? 'Restore' : 'Exclude'}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
