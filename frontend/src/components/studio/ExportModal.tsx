import React, { useState, useEffect } from 'react';
import { X, Copy, Check, Download, FileText, ShieldCheck } from 'lucide-react';
import { api } from '../../api/client';

interface ExportModalProps {
  markdown: string | null;
  projectTitle: string;
  projectId?: string;
  onClose: () => void;
}

export const ExportModal: React.FC<ExportModalProps> = ({
  markdown,
  projectTitle,
  projectId,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<'brief' | 'sourcesheet'>('brief');
  const [sourceSheetMd, setSourceSheetMd] = useState<string | null>(null);
  const [loadingSourceSheet, setLoadingSourceSheet] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (activeTab === 'sourcesheet' && !sourceSheetMd && projectId) {
      setLoadingSourceSheet(true);
      api.getSourceSheet(projectId)
        .then((res) => setSourceSheetMd(res.markdown))
        .catch((err) => setSourceSheetMd(`# Error loading source sheet\n\n${err.message}`))
        .finally(() => setLoadingSourceSheet(false));
    }
  }, [activeTab, sourceSheetMd, projectId]);

  if (!markdown) return null;

  const currentContent = activeTab === 'brief' ? markdown : (sourceSheetMd || 'Loading source sheet...');

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(currentContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy markdown:', err);
    }
  };

  const handleDownload = () => {
    const blob = new Blob([currentContent], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const slug = projectTitle.toLowerCase().replace(/[^a-z0-9]+/g, '-');
    a.href = url;
    a.download = activeTab === 'brief' ? `${slug}-brief.md` : `${slug}-source-sheet.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl max-h-[90vh] flex flex-col bg-[#0B101B] border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-purple-950/80 border border-purple-700/60 flex items-center justify-center text-purple-400">
              {activeTab === 'brief' ? <FileText className="w-4 h-4" /> : <ShieldCheck className="w-4 h-4 text-emerald-400" />}
            </div>
            <div>
              <h2 className="font-display font-bold text-lg text-white">
                {activeTab === 'brief' ? 'Export Documentary Script Brief' : 'Export Fact-Check Source Sheet'}
              </h2>
              <p className="text-xs text-slate-400 font-mono">
                {activeTab === 'brief'
                  ? 'Formatted Markdown for scriptwriters and video editors'
                  : 'Timecode citation index, archive URLs, and verified quotes for legal & editorial review'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              disabled={loadingSourceSheet}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copied!' : 'Copy'}</span>
            </button>

            <button
              onClick={handleDownload}
              disabled={loadingSourceSheet}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-purple-600 hover:bg-purple-500 text-white shadow-sm transition"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download .md</span>
            </button>

            <button
              onClick={onClose}
              aria-label="Close"
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition ml-2"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Tab Switcher */}
        {projectId && (
          <div className="px-5 py-2.5 bg-slate-950/90 border-b border-slate-800 flex items-center gap-2">
            <button
              onClick={() => setActiveTab('brief')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-mono transition ${
                activeTab === 'brief'
                  ? 'bg-purple-950/70 text-purple-300 border border-purple-800/60 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Full Script Brief</span>
            </button>
            <button
              onClick={() => setActiveTab('sourcesheet')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-mono transition ${
                activeTab === 'sourcesheet'
                  ? 'bg-emerald-950/70 text-emerald-300 border border-emerald-800/60 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Fact-Check Source Sheet</span>
            </button>
          </div>
        )}

        {/* Markdown Content Viewer */}
        <div className="flex-1 overflow-y-auto p-5 bg-slate-950/70 font-mono text-xs leading-relaxed text-slate-300">
          {loadingSourceSheet ? (
            <div className="flex items-center justify-center p-12 text-slate-500">
              Generating Fact-Check & Citation Source Sheet...
            </div>
          ) : (
            <pre className="whitespace-pre-wrap select-all">{currentContent}</pre>
          )}
        </div>
      </div>
    </div>
  );
};
