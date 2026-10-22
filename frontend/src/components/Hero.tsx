import React from 'react';
import { Sparkles, FolderArchive, ShieldAlert, Cpu, ArrowDown } from 'lucide-react';

interface HeroProps {
  onScrollToUpload: () => void;
}

export const Hero: React.FC<HeroProps> = ({ onScrollToUpload }) => {
  return (
    <section className="relative pt-12 pb-10 overflow-hidden border-b border-forest-900/30">
      {/* Background ambient lighting */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-5xl h-64 bg-forest-600/10 blur-[100px] pointer-events-none rounded-full" />

      <div className="max-w-5xl mx-auto px-4 text-center relative z-10">
        {/* Hackathon banner */}
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-forest-900/40 border border-forest-600/30 text-xs text-forest-300 mb-6 font-medium">
          <Sparkles className="w-3.5 h-3.5 text-forest-400" />
          <span>Hacktoberfest DEV Week Challenge: <strong>“Slow and Steady”</strong></span>
        </div>

        {/* Main Headline */}
        <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-white mb-4">
          Upload the mess. <br className="hidden sm:block" />
          <span className="forest-gradient-text">Let AI do the rest.</span>
        </h1>

        {/* Subtitle */}
        <p className="max-w-2xl mx-auto text-base sm:text-lg text-slate-300 leading-relaxed mb-8">
          Stop wasting hours sorting chaotic Downloads folders. LazyFlow uses verified open-weight AI to categorize files into sensible directories, suggest clean descriptive filenames, and pack everything into a tidy ZIP archive.
        </p>

        {/* Value pillars */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-3xl mx-auto mb-8 text-left">
          <div className="glass-panel p-4 rounded-xl border border-forest-800/40">
            <div className="flex items-center gap-2.5 mb-1.5 text-forest-400 font-semibold text-sm">
              <Cpu className="w-4 h-4" />
              <span>Open-Weight AI</span>
            </div>
            <p className="text-xs text-slate-400 leading-normal">
              Powered by <code className="text-forest-300">Llama 3.1 8B</code> via Backboard's hosted API. Zero vendor lock-in.
            </p>
          </div>

          <div className="glass-panel p-4 rounded-xl border border-forest-800/40">
            <div className="flex items-center gap-2.5 mb-1.5 text-emerald-400 font-semibold text-sm">
              <ShieldAlert className="w-4 h-4" />
              <span>100% Privacy-Preserving</span>
            </div>
            <p className="text-xs text-slate-400 leading-normal">
              File contents are <strong>never</strong> transmitted. AI organizes based strictly on filenames, extensions, and metadata.
            </p>
          </div>

          <div className="glass-panel p-4 rounded-xl border border-forest-800/40">
            <div className="flex items-center gap-2.5 mb-1.5 text-forest-400 font-semibold text-sm">
              <FolderArchive className="w-4 h-4" />
              <span>Instant ZIP Export</span>
            </div>
            <p className="text-xs text-slate-400 leading-normal">
              Review every filename and category first, make adjustments, and download a pristine organized ZIP archive.
            </p>
          </div>
        </div>

        <button
          onClick={onScrollToUpload}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-forest-600 hover:bg-forest-500 text-white font-semibold text-sm shadow-lg shadow-forest-900/60 transition-all hover:scale-[1.02] active:scale-[0.98]"
        >
          <span>Organize Your Files Now</span>
          <ArrowDown className="w-4 h-4 animate-bounce" />
        </button>
      </div>
    </section>
  );
};
