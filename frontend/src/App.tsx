import React, { useState, useEffect, useRef } from 'react';
import { Navbar } from './components/Navbar';
import { Hero } from './components/Hero';
import { Dropzone } from './components/Dropzone';
import { CategorySummary } from './components/CategorySummary';
import { ReviewTable } from './components/ReviewTable';
import { DownloadAction } from './components/DownloadAction';
import { PrivacyModal } from './components/PrivacyModal';
import { StatusBanner } from './components/StatusBanner';

import {
  fetchHealth,
  fetchModelStatus,
  fetchSampleFilesList,
  fetchSampleFileBlob,
  uploadAndOrganize,
  downloadOrganizedZip,
  cleanupSession,
} from './services/api';

import {
  VALID_PNG_BYTES,
  VALID_JPEG_BYTES,
  createClientPdfBlob,
  createClientCsvBlob,
} from './utils/sampleGenerator';

import type {
  HealthStatus,
  ModelStatus,
  UploadFileItem,
  FileOrganizedItem,
  OrganizeResponse,
} from './types';

export const App: React.FC = () => {
  // Diagnostics
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'error'>('connecting');
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isPrivacyOpen, setIsPrivacyOpen] = useState(false);

  // Upload state
  const [files, setFiles] = useState<UploadFileItem[]>([]);
  const [customCategories, setCustomCategories] = useState<string[]>([]);
  const [consentContentAnalysis, setConsentContentAnalysis] = useState(true);
  const [isLoading, setIsLoading] = useState(false);

  // Review & Download state
  const [organizeResult, setOrganizeResult] = useState<OrganizeResponse | null>(null);
  const [items, setItems] = useState<FileOrganizedItem[]>([]);
  const [categoriesSummary, setCategoriesSummary] = useState<Record<string, number>>({});
  const [selectedFilter, setSelectedFilter] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);

  const uploadSectionRef = useRef<HTMLDivElement>(null);

  const checkSystem = async (retryCount = 0) => {
    setConnectionState('connecting');
    if (retryCount === 0) {
      setConnectionError(null);
    }

    try {
      const h = await fetchHealth();
      setHealth(h);
      setConnectionState('connected');
      setConnectionError(null);
    } catch (err: any) {
      console.warn('Backend not responding yet:', err);
      // Auto-retry up to 6 times (every 5 seconds) during Render free tier cold-start wake-up
      const MAX_AUTO_RETRIES = 6;
      if (retryCount < MAX_AUTO_RETRIES) {
        setConnectionState('connecting');
        setConnectionError(
          `Waking up Render backend (attempt ${retryCount + 1}/${MAX_AUTO_RETRIES}). Free instances take up to 50s to spin up...`
        );
        setTimeout(() => {
          checkSystem(retryCount + 1);
        }, 5000);
        return;
      }
      setConnectionState('error');
      setConnectionError(err.message || 'Failed to reach LazyFlow AI backend.');
      return;
    }

    try {
      const m = await fetchModelStatus();
      setModelStatus(m);
    } catch (err: any) {
      console.warn('Model status unavailable:', err);
    }
  };

  // Fetch initial diagnostic data
  useEffect(() => {
    checkSystem();
  }, []);

  const handleScrollToUpload = () => {
    uploadSectionRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleAddFiles = (newFiles: File[]) => {
    setErrorMessage(null);
    const mapped: UploadFileItem[] = newFiles.map((f, i) => ({
      file: f,
      id: `file_${Date.now()}_${i}_${Math.random().toString(36).substr(2, 4)}`,
      description: '',
    }));
    setFiles((prev) => [...prev, ...mapped]);
  };

  const handleRemoveFile = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const handleUpdateDescription = (id: string, description: string) => {
    setFiles((prev) =>
      prev.map((f) => (f.id === id ? { ...f, description } : f))
    );
  };

  const handleClearFiles = () => {
    setFiles([]);
    setErrorMessage(null);
  };

  const handleAddCategory = (cat: string) => {
    if (!customCategories.includes(cat)) {
      setCustomCategories((prev) => [...prev, cat]);
    }
  };

  const handleRemoveCategory = (cat: string) => {
    setCustomCategories((prev) => prev.filter((c) => c !== cat));
  };

  // Load genuine sample messy files with real binary contents
  const handleLoadSamples = async () => {
    setErrorMessage(null);
    try {
      const sampleList = await fetchSampleFilesList();
      const loaded: UploadFileItem[] = [];

      for (let i = 0; i < sampleList.length; i++) {
        const item = sampleList[i];
        const blob = await fetchSampleFileBlob(item.name);
        const f = new File([blob], item.name, { type: item.mime_type, lastModified: Date.now() });
        loaded.push({
          file: f,
          id: `sample_${i + 1}`,
          description: item.hint,
        });
      }

      setFiles(loaded);
    } catch (err: any) {
      console.warn('Could not fetch server samples, generating genuine client binaries:', err);
      // Fallback: generate genuine binary files (valid PDF, PNG, JPEG, CSV)
      const samples = [
        {
          name: 'document.pdf',
          type: 'application/pdf',
          hint: 'Generic name, contains full resume',
          blob: createClientPdfBlob('Alex Morgan - Resume', [
            'Summary: Senior Software Engineer with 6+ years experience.',
            'Experience: Tech Lead building scalable backend microservices.',
            'Education: B.S. in Computer Science - Honors.',
            'Skills: Python, TypeScript, React, Docker, FastAPI.'
          ])
        },
        {
          name: 'file.pdf',
          type: 'application/pdf',
          hint: 'Generic name, contains hosting invoice',
          blob: createClientPdfBlob('INVOICE #INV-2024-889', [
            'Vendor: Cloud Infrastructure & Hosting Services',
            'Bill To: Acme Technologies Inc.',
            'Amount Due: $450.00 USD - Due Date: Nov 15, 2024',
            'Services: Dedicated GPU compute and managed Redis cluster'
          ])
        },
        {
          name: 'notes.docx',
          type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          hint: 'Generic name, CS50 study notes',
          blob: createClientPdfBlob('CS50 Study Notes - Algorithms and Data Structures', [
            'Lecture on binary search trees, time complexity O(log n), and asymptotic runtime analysis.'
          ])
        },
        {
          name: 'apollo_budget.csv',
          type: 'text/csv',
          hint: 'Project Apollo budget export',
          blob: createClientCsvBlob()
        },
        {
          name: 'ambiguous_data.bin',
          type: 'application/octet-stream',
          hint: 'Minimal binary bytes (ambiguous)',
          blob: new Blob([new Uint8Array([0, 1, 2, 3, 4, 5, 6, 7])], { type: 'application/octet-stream' })
        },
        { name: 'IMG_20231012_WA0004.jpg', type: 'image/jpeg', hint: 'Team meetup photo', blob: new Blob([VALID_JPEG_BYTES], { type: 'image/jpeg' }) },
        { name: 'Screenshot 2024-03-01 at 4.22.19 PM.png', type: 'image/png', hint: 'Checkout button UI bug', blob: new Blob([VALID_PNG_BYTES], { type: 'image/png' }) },
      ];

      const fallbackFiles: UploadFileItem[] = samples.map((s, idx) => {
        const f = new File([s.blob], s.name, { type: s.type, lastModified: Date.now() });
        return {
          file: f,
          id: `sample_${idx + 1}`,
          description: s.hint,
        };
      });

      setFiles(fallbackFiles);
    }
  };

  // Trigger AI organization
  const handleStartOrganizing = async () => {
    if (files.length === 0) return;

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const rawFiles = files.map((f) => f.file);
      const descriptionsMap: Record<string, string> = {};
      files.forEach((f) => {
        if (f.description?.trim()) {
          descriptionsMap[f.file.name] = f.description.trim();
        }
      });

      const response = await uploadAndOrganize(
        rawFiles,
        customCategories,
        descriptionsMap,
        consentContentAnalysis
      );
      setOrganizeResult(response);
      setItems(response.items);
      setCategoriesSummary(response.categories_summary);
      setSelectedFilter(null);
    } catch (err: any) {
      console.error('Organization failed:', err);
      setErrorMessage(err.message || 'Failed to organize files with Backboard AI.');
    } finally {
      setIsLoading(false);
    }
  };

  // Review table interactions
  const handleToggleExclude = (id: string) => {
    setItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, excluded: !item.excluded } : item))
    );
  };

  const handleUpdateFilename = (id: string, newName: string) => {
    setItems((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, suggested_filename: newName, user_modified: true } : item
      )
    );
  };

  const handleUpdateFolder = (id: string, newFolder: string) => {
    setItems((prev) => {
      const updated = prev.map((item) =>
        item.id === id ? { ...item, folder: newFolder, category: newFolder, user_modified: true } : item
      );

      // Recompute category summary
      const newSummary: Record<string, number> = {};
      updated.forEach((i) => {
        newSummary[i.folder] = (newSummary[i.folder] || 0) + 1;
      });
      setCategoriesSummary(newSummary);

      return updated;
    });
  };

  const handleToggleAll = (selectAll: boolean) => {
    setItems((prev) => prev.map((item) => ({ ...item, excluded: !selectAll })));
  };

  // ZIP Download
  const handleDownloadZip = async () => {
    if (!organizeResult?.session_id) {
      setErrorMessage('Session expired. Please re-run organization.');
      return;
    }

    setIsDownloading(true);
    setErrorMessage(null);

    try {
      await downloadOrganizedZip(organizeResult.session_id, items);
    } catch (err: any) {
      console.error('Download failed:', err);
      setErrorMessage(err.message || 'Failed to generate organized ZIP archive.');
    } finally {
      setIsDownloading(false);
    }
  };

  // Reset workflow
  const handleReset = async () => {
    if (organizeResult?.session_id) {
      cleanupSession(organizeResult.session_id);
    }
    setOrganizeResult(null);
    setItems([]);
    setCategoriesSummary({});
    setSelectedFilter(null);
    setFiles([]);
    setErrorMessage(null);
  };

  // Gather all unique folders
  const allAvailableFolders = Array.from(
    new Set([
      'Career',
      'Finance',
      'Study',
      'Work',
      'Documents',
      'Images',
      'Code',
      'Other',
      ...customCategories,
      ...items.map((i) => i.folder),
    ])
  );

  return (
    <div className="min-h-screen flex flex-col bg-charcoal-950 text-slate-100">
      {/* Top Navigation */}
      <Navbar
        health={health}
        modelStatus={modelStatus}
        connectionState={connectionState}
        onOpenPrivacy={() => setIsPrivacyOpen(true)}
        onRetryConnection={checkSystem}
      />

      {/* Main Content */}
      <main className="flex-1 pb-20">
        {/* Hero Section */}
        <Hero onScrollToUpload={handleScrollToUpload} />

        {/* Global Alert / Status Banner */}
        <div className="pt-6">
          <StatusBanner
            health={health}
            connectionState={connectionState}
            connectionError={connectionError}
            errorMessage={errorMessage}
            onClearError={() => setErrorMessage(null)}
            onRetryConnection={checkSystem}
          />
        </div>

        {/* Workflow Workspace */}
        <div ref={uploadSectionRef} className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
          {!organizeResult ? (
            /* Upload State */
            <div className="space-y-6">
              <div className="text-center max-w-xl mx-auto mb-2">
                <h2 className="text-2xl font-bold text-white tracking-tight">
                  Upload & Classify Workspace
                </h2>
                <p className="text-xs text-slate-400 mt-1">
                  Add your messy files. Content-aware AI detects resumes, invoices, and notes automatically.
                </p>
              </div>

              <Dropzone
                files={files}
                onAddFiles={handleAddFiles}
                onRemoveFile={handleRemoveFile}
                onUpdateDescription={handleUpdateDescription}
                onClearFiles={handleClearFiles}
                customCategories={customCategories}
                onAddCategory={handleAddCategory}
                onRemoveCategory={handleRemoveCategory}
                onStartOrganizing={handleStartOrganizing}
                isLoading={isLoading}
                onLoadSamples={handleLoadSamples}
                consentContentAnalysis={consentContentAnalysis}
                onToggleConsent={setConsentContentAnalysis}
              />
            </div>
          ) : (
            /* Review & Download State */
            <div className="space-y-6 animate-fade-in">
              {/* Category Summary metrics & filter chips */}
              <CategorySummary
                items={items}
                categoriesSummary={categoriesSummary}
                selectedFilter={selectedFilter}
                onSelectFilter={setSelectedFilter}
              />

              {/* Review Table */}
              <ReviewTable
                items={items}
                onToggleExclude={handleToggleExclude}
                onUpdateFilename={handleUpdateFilename}
                onUpdateFolder={handleUpdateFolder}
                onToggleAll={handleToggleAll}
                selectedFilter={selectedFilter}
                availableFolders={allAvailableFolders}
              />

              {/* Download Bar */}
              <DownloadAction
                items={items}
                onDownload={handleDownloadZip}
                onReset={handleReset}
                isDownloading={isDownloading}
              />
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-charcoal-950/80 py-8 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 space-y-2">
          <div className="flex items-center justify-center gap-2 font-medium text-slate-400">
            <span>LazyFlow AI</span>
            <span>·</span>
            <span>Hacktoberfest DEV Week Challenge “Slow and Steady”</span>
            <span>·</span>
            <span className="text-forest-400">Powered by Backboard & Llama 3.1</span>
          </div>
          <p className="text-[11px] text-slate-600">
            Open-Weight AI · Zero File Content Transmission · Ephemeral Session Storage
          </p>
        </div>
      </footer>

      {/* Privacy Notice Modal */}
      <PrivacyModal
        isOpen={isPrivacyOpen}
        onClose={() => setIsPrivacyOpen(false)}
      />
    </div>
  );
};
export default App;
