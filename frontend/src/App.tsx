import React, { useState, useEffect } from 'react';
import { Navbar, ActiveTab } from './components/Navbar';
import { EventRadar } from './components/radar/EventRadar';
import { IndiaDesk } from './components/india/IndiaDesk';
import { WarRoom } from './components/warroom/WarRoom';
import { StoryStudio } from './components/studio/StoryStudio';
import { SourcesManager } from './components/sources/SourcesManager';
import { Toast, ToastMessage } from './components/Toast';
import { EventCluster, Project, Source, SourceCreate } from './types';
import { api } from './api/client';

const TABS: ActiveTab[] = ['radar', 'warroom', 'studio', 'sources']; // old #/india links fall back to Discover
const CLUSTER_PAGE = 50;

// URL hash mirrors the view (#/warroom/proj_123) so refresh, bookmarks and back/forward work.
const parseHash = (): { tab: ActiveTab; projectId: string | null } => {
  const [, tab, projectId] = window.location.hash.split('/');
  return {
    tab: TABS.includes(tab as ActiveTab) ? (tab as ActiveTab) : 'radar',
    projectId: projectId ? decodeURIComponent(projectId) : null,
  };
};

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>(() => parseHash().tab);
  const [clusters, setClusters] = useState<EventCluster[]>([]);
  const [loadingClusters, setLoadingClusters] = useState(false);
  const [hasMoreClusters, setHasMoreClusters] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(() => parseHash().projectId);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [loadingSources, setLoadingSources] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [isRefreshingDossier, setIsRefreshingDossier] = useState(false);
  const [isGeneratingOutline, setIsGeneratingOutline] = useState(false);
  const [isFindingContradictions, setIsFindingContradictions] = useState(false);
  const [isSeeding, setIsSeeding] = useState(false);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [indiaFocus, setIndiaFocus] = useState(false);

  const addToast = (type: 'success' | 'error' | 'info', title: string, description?: string) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, title, description }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Initial Data Load
  const fetchClusters = async () => {
    setLoadingClusters(true);
    try {
      const data = await api.getClusters({ limit: CLUSTER_PAGE });
      setClusters(data);
      setHasMoreClusters(data.length === CLUSTER_PAGE);
    } catch (err: any) {
      console.error('Failed to load clusters:', err);
      addToast('error', 'Cluster Retrieval Failed', err.message);
    } finally {
      setLoadingClusters(false);
    }
  };

  const loadMoreClusters = async () => {
    try {
      const data = await api.getClusters({ limit: CLUSTER_PAGE, offset: clusters.length });
      setClusters((prev) => [...prev, ...data.filter((c) => !prev.some((p) => p.id === c.id))]);
      setHasMoreClusters(data.length === CLUSTER_PAGE);
    } catch (err: any) {
      addToast('error', 'Cluster Retrieval Failed', err.message);
    }
  };

  const fetchProjects = async (selectLatestId?: string) => {
    try {
      const data = await api.getProjects();
      setProjects(data);
      if (selectLatestId) {
        setActiveProjectId(selectLatestId);
      } else if (!activeProjectId && data.length > 0) {
        setActiveProjectId(data[0].id);
      }
    } catch (err: any) {
      console.error('Failed to load projects:', err);
      addToast('error', 'Project List Failed', err.message);
    }
  };

  const fetchSources = async () => {
    setLoadingSources(true);
    try {
      const data = await api.getSources();
      setSources(data);
      // Auto-seed only on first visit, so a user who deliberately removed every source doesn't get them back.
      let firstVisit = true;
      try {
        firstVisit = !localStorage.getItem('gps_sources_seeded');
      } catch {
        // storage unavailable: fall back to seeding once per page load
      }
      if (data.length === 0 && firstVisit) {
        handleSeedDefaults();
      }
    } catch (err: any) {
      console.error('Failed to load sources:', err);
      addToast('error', 'Source List Failed', err.message);
    } finally {
      setLoadingSources(false);
    }
  };

  useEffect(() => {
    fetchClusters();
    fetchProjects();
    fetchSources();
    const onHashChange = () => {
      const { tab, projectId } = parseHash();
      setActiveTab(tab);
      if (projectId) setActiveProjectId(projectId);
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  useEffect(() => {
    const hash = `#/${activeTab}${activeProjectId ? `/${encodeURIComponent(activeProjectId)}` : ''}`;
    if (window.location.hash !== hash) window.location.hash = hash;
  }, [activeTab, activeProjectId]);

  // Fetch full details of active project whenever activeProjectId changes
  useEffect(() => {
    if (!activeProjectId) {
      setActiveProject(null);
      return;
    }

    // Ignore responses for a project the user has already switched away from.
    let current = true;
    api
      .getProject(activeProjectId)
      .then((data) => current && setActiveProject(data))
      .catch((err) => {
        if (!current) return;
        console.error('Failed to fetch full project details:', err);
        addToast('error', 'Project Load Error', err.message);
      });
    return () => {
      current = false;
    };
  }, [activeProjectId]);

  // Actions
  const handleScan = async () => {
    setIsScanning(true);
    try {
      const summary = await api.scanFeeds();
      addToast(
        'success',
        'News Fetched',
        `${summary.new_articles_ingested} new articles, ${summary.clusters_created_or_updated} stories updated.`
      );
      await fetchClusters();
      await fetchSources();
    } catch (err: any) {
      console.error('Feed scan failed:', err);
      addToast('error', 'Feed Scan Failed', err.message);
    } finally {
      setIsScanning(false);
    }
  };

  // Create a project with its dossier and outline; roll the project back if synthesis fails.
  const createInitializedProject = async (data: Parameters<typeof api.createProject>[0]) => {
    const newProj = await api.createProject(data);
    try {
      await api.generateDossier(newProj.id);
      await api.generateOutline(newProj.id);
    } catch (err) {
      await api.deleteProject(newProj.id).catch(() => undefined);
      throw err;
    }
    return newProj;
  };

  const handleCreateProjectFromCluster = async (cluster: EventCluster) => {
    const existing = projects.find((p) => p.cluster_id === cluster.id);
    if (existing) {
      setActiveProjectId(existing.id);
      setActiveTab('warroom');
      addToast('info', 'Project Reopened', `You already have a project on "${existing.title}".`);
      return;
    }
    setIsCreatingProject(true);
    try {
      const newProj = await createInitializedProject({
        title: cluster.headline,
        cluster_id: cluster.id,
        target_duration_mins: 18,
      });
      await fetchProjects(newProj.id);
      setActiveTab('warroom');
      addToast('success', 'Project Created', `Now researching "${newProj.title}".`);
    } catch (err: any) {
      console.error('Failed to create project:', err);
      addToast('error', 'Creation Failed', err.message);
    } finally {
      setIsCreatingProject(false);
    }
  };

  const handleNewProjectPrompt = async () => {
    const title = window.prompt('Enter Documentary Essay Project Title:');
    if (!title || !title.trim()) return;

    try {
      const newProj = await createInitializedProject({
        title: title.trim(),
        target_duration_mins: 18,
      });
      await fetchProjects(newProj.id);
      setActiveTab('warroom');
      addToast('success', 'Project Created', `Now researching "${newProj.title}".`);
    } catch (err: any) {
      console.error('Failed to create project:', err);
      addToast('error', 'Creation Failed', err.message);
    }
  };

  const handleRefreshDossier = async () => {
    if (!activeProject) return;
    setIsRefreshingDossier(true);
    try {
      await api.generateDossier(activeProject.id);
      const updated = await api.getProject(activeProject.id);
      setActiveProject(updated);
      addToast('success', 'Research Updated', 'Timeline, stakeholders and sources refreshed.');
    } catch (err: any) {
      console.error('Failed to refresh dossier:', err);
      addToast('error', 'Dossier Synthesis Failed', err.message);
    } finally {
      setIsRefreshingDossier(false);
    }
  };

  const handleFindContradictions = async () => {
    if (!activeProject) return;
    setIsFindingContradictions(true);
    try {
      const dossier = await api.findContradictions(activeProject.id);
      setActiveProject(await api.getProject(activeProject.id));
      addToast(
        dossier.contradictions.length ? 'success' : 'info',
        'Reports Compared',
        dossier.contradictions.length
          ? `${dossier.contradictions.length} verified disagreement(s) found.`
          : 'No factual disagreements found between the reports.'
      );
    } catch (err: any) {
      addToast('error', 'Comparison Failed', err.message);
    } finally {
      setIsFindingContradictions(false);
    }
  };

  const handleRefreshOutline = async () => {
    if (!activeProject) return;
    setIsGeneratingOutline(true);
    try {
      await api.generateOutline(activeProject.id);
      const updated = await api.getProject(activeProject.id);
      setActiveProject(updated);
      addToast('success', 'Outline Updated', 'Five-act outline refreshed.');
    } catch (err: any) {
      console.error('Failed to generate outline:', err);
      addToast('error', 'Outline Generation Failed', err.message);
    } finally {
      setIsGeneratingOutline(false);
    }
  };

  const handleSelectAngle = async (angleTitle: string) => {
    if (!activeProject) return;
    try {
      await api.updateProject(activeProject.id, { selected_angle: angleTitle });
      // Re-generate outline calibrated to this lens
      await api.generateOutline(activeProject.id);
      const updated = await api.getProject(activeProject.id);
      setActiveProject(updated);
      addToast('success', 'Angle Selected', angleTitle);
    } catch (err: any) {
      console.error('Failed to set angle:', err);
      addToast('error', 'Angle Selection Failed', err.message);
    }
  };

  const handleUpdateDuration = async (mins: number) => {
    if (!activeProject) return;
    try {
      await api.updateProject(activeProject.id, { target_duration_mins: mins });
      await api.generateOutline(activeProject.id);
      const updated = await api.getProject(activeProject.id);
      setActiveProject(updated);
      addToast('info', 'Length Updated', `Target length is now ${mins} minutes.`);
    } catch (err: any) {
      console.error('Failed to update duration:', err);
      addToast('error', 'Runtime Update Failed', err.message);
    }
  };

  const handleSeedDefaults = async () => {
    setIsSeeding(true);
    try {
      const data = await api.seedSources();
      setSources(data);
      try {
        localStorage.setItem('gps_sources_seeded', '1');
      } catch {
        // ignore: only affects first-visit auto-seeding
      }
      addToast('success', 'Default Feeds Added', `${data.length} news feeds are set up.`);
    } catch (err: any) {
      console.error('Failed to seed feeds:', err);
      addToast('error', 'Seeding Failed', err.message);
    } finally {
      setIsSeeding(false);
    }
  };

  const handleCreateSource = async (sourceData: SourceCreate) => {
    const newSrc = await api.createSource(sourceData);
    setSources((prev) => [...prev, newSrc]);
    addToast('success', 'Source Added', `Registered "${newSrc.name}".`);
  };

  const handleUpdateSource = async (sourceId: string, { id: _id, ...data }: SourceCreate) => {
    const updated = await api.updateSource(sourceId, data);
    setSources((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    addToast('success', 'Source Updated', updated.name);
  };

  const handleToggleSource = async (source: Source) => {
    try {
      const updated = await api.updateSource(source.id, { is_active: !source.is_active });
      setSources((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      addToast('info', updated.is_active ? 'Source Resumed' : 'Source Paused', updated.name);
    } catch (err: any) {
      addToast('error', 'Source Update Failed', err.message);
    }
  };

  const handleDeleteSource = async (source: Source) => {
    if (!window.confirm(`Delete "${source.name}" and all its ingested articles?`)) return;
    try {
      await api.deleteSource(source.id);
      setSources((prev) => prev.filter((s) => s.id !== source.id));
      addToast('success', 'Source Deleted', source.name);
      fetchClusters(); // its articles (and clusters only it covered) are gone
    } catch (err: any) {
      addToast('error', 'Source Deletion Failed', err.message);
    }
  };

  const handleDeleteProject = async () => {
    if (!activeProject) return;
    if (!window.confirm(`Delete project "${activeProject.title}"? This cannot be undone.`)) return;
    try {
      await api.deleteProject(activeProject.id);
      const remaining = projects.filter((p) => p.id !== activeProject.id);
      setProjects(remaining);
      setActiveProjectId(remaining[0]?.id ?? null);
      addToast('success', 'Project Deleted', activeProject.title);
    } catch (err: any) {
      addToast('error', 'Project Deletion Failed', err.message);
    }
  };

  return (
    <div className="min-h-screen bg-[#070B12] text-slate-100 flex flex-col bg-grid-pattern selection:bg-cyan-500/20 selection:text-cyan-200">
      {/* Top HUD Navigation Header */}
      <Navbar
        activeTab={activeTab}
        onTabChange={(t) => setActiveTab(t)}
        isScanning={isScanning}
        onScan={handleScan}
        projects={projects}
        activeProject={activeProject}
        onSelectProject={(id) => setActiveProjectId(id)}
        onNewProject={handleNewProjectPrompt}
        onDeleteProject={handleDeleteProject}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8 space-y-4">
        {activeTab === 'radar' && (
          <div role="group" aria-label="Story filter" className="inline-flex p-1 rounded-xl bg-slate-900/80 border border-slate-800 text-xs">
            {[
              { on: false, label: 'All stories' },
              { on: true, label: 'India focus' },
            ].map(({ on, label }) => (
              <button
                key={label}
                onClick={() => setIndiaFocus(on)}
                aria-pressed={indiaFocus === on}
                className={`px-3 py-1.5 rounded-lg transition ${indiaFocus === on ? 'bg-slate-700 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'}`}
              >
                {label}
              </button>
            ))}
          </div>
        )}

        {activeTab === 'radar' && !indiaFocus && (
          <EventRadar
            clusters={clusters}
            loading={loadingClusters}
            onRefresh={fetchClusters}
            hasMore={hasMoreClusters}
            onLoadMore={loadMoreClusters}
            onOpenWarRoom={handleCreateProjectFromCluster}
            isCreatingProject={isCreatingProject}
            onScanFeeds={handleScan}
            isScanning={isScanning}
          />
        )}

        {activeTab === 'radar' && indiaFocus && (
          <IndiaDesk
            onOpenWarRoom={handleCreateProjectFromCluster}
            isCreatingProject={isCreatingProject}
            onScanFeeds={handleScan}
            isScanning={isScanning}
          />
        )}

        {activeTab === 'warroom' && (
          <WarRoom
            project={activeProject}
            onRefreshDossier={handleRefreshDossier}
            isRefreshing={isRefreshingDossier}
            onProceedToStudio={() => setActiveTab('studio')}
            onUpdateDuration={handleUpdateDuration}
            onSwitchToRadar={() => setActiveTab('radar')}
            onFindContradictions={handleFindContradictions}
            isFindingContradictions={isFindingContradictions}
          />
        )}

        {activeTab === 'studio' && (
          <StoryStudio
            project={activeProject}
            onRefreshOutline={handleRefreshOutline}
            isGeneratingOutline={isGeneratingOutline}
            onSelectAngle={handleSelectAngle}
            onSwitchToRadar={() => setActiveTab('radar')}
          />
        )}

        {activeTab === 'sources' && (
          <SourcesManager
            sources={sources}
            loading={loadingSources}
            onRefresh={fetchSources}
            onSeedDefaults={handleSeedDefaults}
            isSeeding={isSeeding}
            onCreateSource={handleCreateSource}
            onUpdateSource={handleUpdateSource}
            onToggleSource={handleToggleSource}
            onDeleteSource={handleDeleteSource}
          />
        )}
      </main>

      <footer className="mt-auto border-t border-slate-900 px-6 py-4 text-[11px] text-slate-500 flex items-center justify-between gap-2 max-w-7xl mx-auto w-full">
        <span>Global Pulse Studio</span>
        <a href="/docs" target="_blank" rel="noreferrer" className="hover:text-slate-300">API docs</a>
      </footer>

      {/* Feedback Toasts */}
      <Toast toasts={toasts} onDismiss={removeToast} />
    </div>
  );
};

export default App;
