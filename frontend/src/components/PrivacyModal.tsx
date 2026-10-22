import React from 'react';
import { X, ShieldCheck, Lock, EyeOff, Globe2, Trash2 } from 'lucide-react';

interface PrivacyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const PrivacyModal: React.FC<PrivacyModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-2xl bg-charcoal-900 border border-forest-500/30 rounded-2xl p-6 sm:p-8 shadow-2xl shadow-forest-950/80 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-forest-950 border border-forest-500/40 flex items-center justify-center text-forest-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Privacy & AI Data Transparency</h2>
              <p className="text-xs text-slate-400">How LazyFlow AI handles your data</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-charcoal-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="space-y-5 text-xs text-slate-300 leading-relaxed">
          {/* Rule 1: No file contents sent */}
          <div className="flex gap-3.5 p-3.5 rounded-xl bg-charcoal-950/60 border border-forest-900/40">
            <EyeOff className="w-5 h-5 text-forest-400 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-white text-sm mb-1">Zero File Content Transmission</h4>
              <p className="text-slate-400">
                LazyFlow AI <strong>never transmits file contents</strong> to any AI model or third-party service. Only the metadata—such as original filename, file extension, byte size, and optional user hints—is sent for classification and renaming.
              </p>
            </div>
          </div>

          {/* Rule 2: Hosted open-weight model */}
          <div className="flex gap-3.5 p-3.5 rounded-xl bg-charcoal-950/60 border border-forest-900/40">
            <Globe2 className="w-5 h-5 text-forest-400 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-white text-sm mb-1">Open-Weight AI via Backboard API</h4>
              <p className="text-slate-400">
                Inference runs on the verified open-weight model <code className="text-forest-300">meta-llama/llama-3.1-8b-instruct</code> via <strong>Backboard.io's hosted API</strong>. This requires an active internet connection. We do not claim local offline execution for the AI inference layer.
              </p>
            </div>
          </div>

          {/* Rule 3: Ephemeral temporary storage */}
          <div className="flex gap-3.5 p-3.5 rounded-xl bg-charcoal-950/60 border border-forest-900/40">
            <Trash2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-white text-sm mb-1">Ephemeral Session Storage & Automatic Purging</h4>
              <p className="text-slate-400">
                Uploaded files are stored in a temporary isolated session folder on the backend server solely to package your final organized ZIP archive. Once the ZIP is created, or when the session expires, temporary storage is completely wiped.
              </p>
            </div>
          </div>

          {/* Rule 4: Open innovation */}
          <div className="flex gap-3.5 p-3.5 rounded-xl bg-charcoal-950/60 border border-forest-900/40">
            <Lock className="w-5 h-5 text-forest-400 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-white text-sm mb-1">Why Open Innovation Matters</h4>
              <p className="text-slate-400">
                By leveraging open-weight models like Meta Llama 3.1 through Backboard, developers avoid proprietary vendor lock-in, maintain inspectable prompts and parameters, and benefit from accessible, low-cost AI compute without sacrificing categorization quality.
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 pt-4 border-t border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-forest-600 hover:bg-forest-500 text-white font-semibold text-xs transition-colors"
          >
            I Understand
          </button>
        </div>
      </div>
    </div>
  );
};
