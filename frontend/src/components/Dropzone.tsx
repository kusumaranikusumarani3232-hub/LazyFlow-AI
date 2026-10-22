import React, { useState, useRef } from 'react';
import type { ChangeEvent, DragEvent } from 'react';
import { UploadCloud, X, Plus, Sparkles, Tag, FileText, Image as ImageIcon, CheckCircle2 } from 'lucide-react';
import type { UploadFileItem } from '../types';

interface DropzoneProps {
  files: UploadFileItem[];
  onAddFiles: (newFiles: File[]) => void;
  onRemoveFile: (id: string) => void;
  onUpdateDescription: (id: string, description: string) => void;
  onClearFiles: () => void;
  customCategories: string[];
  onAddCategory: (cat: string) => void;
  onRemoveCategory: (cat: string) => void;
  onStartOrganizing: () => void;
  isLoading: boolean;
  onLoadSamples: () => void;
}

export const Dropzone: React.FC<DropzoneProps> = ({
  files,
  onAddFiles,
  onRemoveFile,
  onUpdateDescription,
  onClearFiles,
  customCategories,
  onAddCategory,
  onRemoveCategory,
  onStartOrganizing,
  isLoading,
  onLoadSamples,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [newCatInput, setNewCatInput] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onAddFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onAddFiles(Array.from(e.target.files));
    }
  };

  const handleAddCategorySubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newCatInput.trim()) {
      onAddCategory(newCatInput.trim());
      setNewCatInput('');
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const totalBytes = files.reduce((acc, f) => acc + f.file.size, 0);

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      {/* Upload Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-2xl p-8 sm:p-12 text-center cursor-pointer transition-all ${
          isDragOver
            ? 'border-forest-400 bg-forest-950/40 scale-[1.01]'
            : 'border-slate-800 hover:border-forest-600/60 bg-charcoal-900/60 hover:bg-charcoal-900/90'
        }`}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          multiple
          className="hidden"
        />

        <div className="flex flex-col items-center justify-center space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-forest-950/80 border border-forest-500/30 flex items-center justify-center text-forest-400 shadow-inner shadow-forest-900/50">
            <UploadCloud className="w-8 h-8 animate-pulse" />
          </div>

          <div className="space-y-1">
            <p className="text-lg font-semibold text-white">
              Drag & drop messy files here, or <span className="text-forest-400 underline decoration-forest-500/50 underline-offset-4">browse</span>
            </p>
            <p className="text-xs text-slate-400">
              Supports documents, photos, invoices, spreadsheets, code, audio, and archives (Up to 30 files, 50MB each)
            </p>
          </div>

          {/* Quick sample load button */}
          <div className="pt-2">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onLoadSamples();
              }}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-forest-900/30 text-forest-300 border border-forest-700/40 hover:bg-forest-900/60 transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5 text-forest-400" />
              <span>Load sample messy files</span>
            </button>
          </div>
        </div>
      </div>

      {/* Selected Files Section */}
      {files.length > 0 && (
        <div className="glass-panel rounded-2xl p-6 border border-slate-800/80 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div className="flex items-center gap-2">
              <h2 className="font-semibold text-base text-white">Selected Files</h2>
              <span className="px-2 py-0.5 rounded-full text-xs font-mono bg-forest-950 text-forest-400 border border-forest-800/50">
                {files.length} {files.length === 1 ? 'file' : 'files'} ({formatFileSize(totalBytes)})
              </span>
            </div>

            <button
              onClick={onClearFiles}
              className="text-xs text-slate-400 hover:text-rose-400 transition-colors flex items-center gap-1"
            >
              <X className="w-3.5 h-3.5" />
              <span>Clear all</span>
            </button>
          </div>

          {/* File Items List */}
          <div className="max-h-72 overflow-y-auto space-y-2.5 pr-1">
            {files.map((item) => (
              <div
                key={item.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-xl bg-charcoal-850/80 border border-slate-800/80 text-xs"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <div className="w-8 h-8 rounded-lg bg-charcoal-900 flex items-center justify-center text-slate-400 shrink-0 border border-slate-700/50">
                    {item.file.type.startsWith('image/') ? (
                      <ImageIcon className="w-4 h-4 text-forest-400" />
                    ) : (
                      <FileText className="w-4 h-4 text-slate-300" />
                    )}
                  </div>
                  <div className="truncate">
                    <p className="font-medium text-slate-200 truncate">{item.file.name}</p>
                    <p className="text-[11px] text-slate-500 font-mono">{formatFileSize(item.file.size)}</p>
                  </div>
                </div>

                {/* Optional Hint/Description */}
                <div className="flex items-center gap-2 sm:w-1/2">
                  <input
                    type="text"
                    value={item.description || ''}
                    onChange={(e) => onUpdateDescription(item.id, e.target.value)}
                    placeholder="Optional hint (e.g. 'Oct hosting bill')"
                    className="w-full px-2.5 py-1.5 rounded-lg bg-charcoal-950 border border-slate-800 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-forest-500/50"
                  />
                  <button
                    onClick={() => onRemoveFile(item.id)}
                    className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-950/20 transition-colors shrink-0"
                    title="Remove file"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Custom Categories Selector */}
          <div className="pt-2 border-t border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
                <Tag className="w-3.5 h-3.5 text-forest-400" />
                <span>Custom Target Folders (Optional)</span>
              </label>
              <span className="text-[11px] text-slate-500">
                Default: Documents, Images, Work, Study, Finance, Code, Other
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {customCategories.map((cat) => (
                <span
                  key={cat}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs bg-forest-950/70 border border-forest-600/40 text-forest-300"
                >
                  <span>{cat}</span>
                  <button
                    onClick={() => onRemoveCategory(cat)}
                    className="hover:text-white transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}

              <form onSubmit={handleAddCategorySubmit} className="flex items-center gap-1.5">
                <input
                  type="text"
                  value={newCatInput}
                  onChange={(e) => setNewCatInput(e.target.value)}
                  placeholder="Add custom folder (e.g. Taxes2024)"
                  className="px-2.5 py-1 rounded-lg bg-charcoal-950 border border-slate-800 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-forest-500/50"
                />
                <button
                  type="submit"
                  disabled={!newCatInput.trim()}
                  className="p-1 rounded-lg bg-forest-900/60 hover:bg-forest-800 text-forest-300 border border-forest-700/50 disabled:opacity-40 transition-colors"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </form>
            </div>
          </div>

          {/* Action Button */}
          <div className="pt-4 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <CheckCircle2 className="w-4 h-4 text-forest-400 shrink-0" />
              <span>Zero file content sent. Backboard open-weight AI processes only names & hints.</span>
            </div>

            <button
              onClick={onStartOrganizing}
              disabled={isLoading || files.length === 0}
              className="w-full sm:w-auto px-6 py-3 rounded-xl bg-forest-600 hover:bg-forest-500 disabled:opacity-50 text-white font-semibold text-sm shadow-lg shadow-forest-900/60 transition-all flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Organizing with Llama 3.1...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Organize {files.length} Files with AI</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
