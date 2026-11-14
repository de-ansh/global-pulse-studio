import React, { useState, useEffect } from 'react';
import { X, Download, Film, RefreshCw, AlertTriangle, Volume2, VolumeX, CheckCircle2 } from 'lucide-react';
import { api } from '../../api/client';
import { ProjectProductionPackage } from '../../types';

interface AnimaticModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  projectTitle: string;
  pkg: ProjectProductionPackage;
  hasAi: boolean;
}

export const AnimaticModal: React.FC<AnimaticModalProps> = ({
  isOpen,
  onClose,
  projectId,
  projectTitle,
  pkg,
  hasAi,
}) => {
  const [withAudio, setWithAudio] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const toolchain = pkg.render_toolchain;
  const isAvailable = toolchain ? toolchain.available : true;
  const missingDeps = toolchain ? toolchain.missing : [];

  const slug = (projectTitle || 'animatic')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60) || 'animatic';

  // Revoke object URL on cleanup
  useEffect(() => {
    return () => {
      if (videoUrl) {
        URL.revokeObjectURL(videoUrl);
      }
    };
  }, [videoUrl]);

  const renderAnimatic = async (audioEnabled: boolean) => {
    if (!isAvailable) return;
    setLoading(true);
    setError(null);
    try {
      if (videoUrl) {
        URL.revokeObjectURL(videoUrl);
        setVideoUrl(null);
      }
      const blob = await api.downloadAnimatic(projectId, { withAudio: audioEnabled });
      const url = URL.createObjectURL(blob);
      setVideoUrl(url);
    } catch (err: any) {
      setError(err.message || 'Failed to render draft animatic.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && !videoUrl && !loading && !error && isAvailable) {
      renderAnimatic(withAudio);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleDownload = async () => {
    if (videoUrl) {
      const a = document.createElement('a');
      a.href = videoUrl;
      a.download = `animatic-${slug}.mp4`;
      a.click();
    } else {
      setDownloading(true);
      try {
        const blob = await api.downloadAnimatic(projectId, { withAudio });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `animatic-${slug}.mp4`;
        a.click();
        URL.revokeObjectURL(url);
      } catch (err: any) {
        setError(err.message || 'Download failed.');
      } finally {
        setDownloading(false);
      }
    }
  };

  const handleToggleAudio = (enabled: boolean) => {
    setWithAudio(enabled);
    renderAnimatic(enabled);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl max-h-[92vh] flex flex-col bg-[#0B101B] border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-slate-800 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-950/80 border border-indigo-700/60 flex items-center justify-center text-indigo-400">
              <Film className="w-4 h-4" />
            </div>
            <div>
              <h2 className="font-display font-bold text-base sm:text-lg text-white flex items-center gap-2">
                <span>Draft Animatic Preview</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-950/80 border border-indigo-800/60 text-indigo-300">
                  1080p · H.264
                </span>
              </h2>
              <p className="text-xs text-slate-400 font-mono truncate max-w-lg">
                {projectTitle} · {pkg.included_shots} shots · {pkg.narration.estimated_runtime_timecode}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleDownload}
              disabled={loading || downloading || !isAvailable}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-indigo-600 hover:bg-indigo-500 text-white shadow-sm transition disabled:opacity-50"
            >
              <Download className="w-3.5 h-3.5" />
              <span>{downloading ? 'Saving...' : 'Download .mp4'}</span>
            </button>

            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
              aria-label="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="p-4 sm:p-6 overflow-y-auto space-y-4 flex-1">
          {/* Missing Toolchain Warning */}
          {!isAvailable && (
            <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-800/60 text-amber-200 text-xs font-mono space-y-2">
              <div className="flex items-center gap-2 font-bold text-amber-300">
                <AlertTriangle className="w-4 h-4" />
                <span>Render toolchain dependencies missing: {missingDeps.join(', ')}</span>
              </div>
              <p className="text-slate-300">
                Rendering animatic videos requires <code className="text-amber-300">ffmpeg</code> and{' '}
                <code className="text-amber-300">Pillow</code> in the system environment.
              </p>
              <p className="text-slate-400">
                Install ffmpeg (<code className="text-slate-200">brew install ffmpeg</code>) and Pillow (
                <code className="text-slate-200">pip install 'pillow&gt;=10.0.0'</code>) and restart the backend.
              </p>
            </div>
          )}

          {/* Controls Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs font-mono">
            <div className="flex items-center gap-2">
              <span className="text-slate-400">Audio track:</span>
              <button
                type="button"
                onClick={() => handleToggleAudio(false)}
                disabled={loading || !isAvailable}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border transition ${
                  !withAudio
                    ? 'bg-slate-800 text-slate-100 border-slate-700 shadow-sm'
                    : 'bg-transparent text-slate-400 border-transparent hover:text-slate-200'
                }`}
              >
                <VolumeX className="w-3.5 h-3.5" />
                <span>Silent draft</span>
              </button>

              <button
                type="button"
                onClick={() => handleToggleAudio(true)}
                disabled={loading || !hasAi || !isAvailable}
                title={!hasAi ? 'Requires GPS_GEMINI_API_KEY for TTS synthesis' : undefined}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border transition ${
                  withAudio
                    ? 'bg-cyan-950/70 text-cyan-300 border-cyan-800/60 shadow-sm'
                    : 'bg-transparent text-slate-400 border-transparent hover:text-slate-200 disabled:opacity-40'
                }`}
              >
                <Volume2 className="w-3.5 h-3.5 text-cyan-400" />
                <span>Gemini TTS narration</span>
              </button>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => renderAnimatic(withAudio)}
                disabled={loading || !isAvailable}
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition disabled:opacity-50"
              >
                <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                <span>Re-render</span>
              </button>
            </div>
          </div>

          {/* Player Display */}
          <div className="relative aspect-video w-full rounded-xl bg-black border border-slate-800 flex items-center justify-center overflow-hidden">
            {loading ? (
              <div className="flex flex-col items-center justify-center space-y-3 p-6 text-center">
                <RefreshCw className="w-8 h-8 text-indigo-400 animate-spin" />
                <p className="text-sm font-display font-medium text-slate-200">
                  Synthesizing 1080p storyboard cards & ffmpeg timeline...
                </p>
                <p className="text-xs font-mono text-slate-500">
                  {withAudio ? 'Rendering narration audio with Gemini TTS' : 'Drafting silent pacing animatic'}
                </p>
              </div>
            ) : error ? (
              <div className="p-6 text-center space-y-3 max-w-md">
                <AlertTriangle className="w-8 h-8 text-red-400 mx-auto" />
                <p className="text-sm font-mono text-red-300">{error}</p>
                <button
                  type="button"
                  onClick={() => renderAnimatic(withAudio)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-200 border border-slate-700 text-xs font-mono hover:bg-slate-700"
                >
                  Try Again
                </button>
              </div>
            ) : videoUrl ? (
              <video
                key={videoUrl}
                src={videoUrl}
                controls
                autoPlay
                playsInline
                className="w-full h-full object-contain"
              />
            ) : (
              <div className="p-6 text-center space-y-2">
                <Film className="w-8 h-8 text-slate-600 mx-auto" />
                <p className="text-xs font-mono text-slate-400">Click Re-render to preview the animatic.</p>
              </div>
            )}
          </div>

          {/* Render Metadata */}
          <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono text-slate-400 pt-1">
            <div className="flex flex-wrap gap-2">
              <span className="flex items-center gap-1 text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Verified shots: {pkg.included_shots}/{pkg.total_shots}</span>
              </span>
              {pkg.needs_source_shots > 0 && (
                <span className="text-amber-400">
                  ({pkg.needs_source_shots} blocked beats omitted from render)
                </span>
              )}
            </div>
            <div>
              <span>Format: 1920x1080 @ 30fps · H.264/AAC</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
