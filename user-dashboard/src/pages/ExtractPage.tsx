import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  Link2, Bot, FileJson, Download, Copy, Check, History,
  X, Sparkles, AlertTriangle, ChevronRight, ChevronLeft,
  Globe, Clock, Info, Trash2, Play
} from 'lucide-react';

type Mode = 'ai' | 'schema';

interface HistoryItem {
  id: string;
  url: string;
  mode: Mode;
  timestamp: number;
  status: 'loading' | 'success' | 'error';
  result?: any;
  error?: string;
}

const HISTORY_KEY = 'kaf_extract_history';

const loadHistory = (): HistoryItem[] => {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
};

const saveHistory = (items: HistoryItem[]) => {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, 200)));
  } catch {}
};

const jsonBeautify = (input: string) => {
  try {
    return JSON.stringify(JSON.parse(input), null, 2);
  } catch {
    return input;
  }
};

const jsonValidate = (input: string): { ok: boolean; error?: string } => {
  try {
    JSON.parse(input);
    return { ok: true };
  } catch (e: any) {
    return { ok: false, error: e?.message || 'Invalid JSON' };
  }
};

const downloadJson = (data: any, filename: string) => {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
};

const TUTORIAL_STEPS = [
  {
    target: '[data-tour="url"]',
    title: 'Enter a URL',
    body: 'Paste the website URL you want to extract data from. We\'ll fetch and process the page.',
    placement: 'bottom' as const,
  },
  {
    target: '[data-tour="mode"]',
    title: 'Choose Extraction Mode',
    body: 'Pick AI (Natural Language) to describe what you want, or Schema (JSON) for structured field rules.',
    placement: 'bottom' as const,
  },
  {
    target: '[data-tour="ai-input"]',
    title: 'Describe what to extract',
    body: 'In AI mode, write a plain-English description like "Get all product names and prices".',
    placement: 'left' as const,
  },
  {
    target: '[data-tour="options"]',
    title: 'Toggle options',
    body: 'Choose whether to include markdown, screenshots, or page links in the output.',
    placement: 'top' as const,
  },
  {
    target: '[data-tour="submit"]',
    title: 'Start Extraction',
    body: 'Hit Run Extraction. We\'ll process the page and return structured results in seconds.',
    placement: 'top' as const,
  },
];

export const ExtractPage: React.FC = () => {
  const { apiFetch, showError, showSuccess } = useAuth();

  const [url, setUrl] = useState('');
  const [mode, setMode] = useState<Mode>('ai');
  const [schemaDescription, setSchemaDescription] = useState('');
  const [jsonSchema, setJsonSchema] = useState('');

  const [includeMarkdown, setIncludeMarkdown] = useState(true);
  const [includeScreenshots, setIncludeScreenshots] = useState(false);
  const [includeLinks, setIncludeLinks] = useState(true);
  const [waitForSelector, setWaitForSelector] = useState('');
  const [timeoutMs, setTimeoutMs] = useState(30000);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any | null>(null);
  const [resultError, setResultError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [history, setHistory] = useState<HistoryItem[]>(() => loadHistory());
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);

  const [tutorialOpen, setTutorialOpen] = useState(false);
  const [tutorialStep, setTutorialStep] = useState(0);
  const tourRefs = useRef<Record<string, DOMRect | null>>({});

  // Persist history
  useEffect(() => {
    saveHistory(history);
  }, [history]);

  const activeSchema = useMemo(() => jsonValidate(jsonSchema), [jsonSchema]);

  const handleBeautify = () => {
    setJsonSchema(jsonBeautify(jsonSchema));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) {
      showError('Please enter a URL');
      return;
    }
    const trimmedUrl = url.trim();
    setLoading(true);
    setResult(null);
    setResultError(null);
    setSelectedHistoryId(null);

    const jobId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const historyEntry: HistoryItem = {
      id: jobId,
      url: trimmedUrl,
      mode,
      timestamp: Date.now(),
      status: 'loading',
    };
    setHistory(prev => [historyEntry, ...prev]);

    try {
      let payload: any;
      let endpoint: string;

      if (mode === 'ai') {
        if (!schemaDescription.trim()) {
          throw new Error('Please describe what you want to extract');
        }
        endpoint = '/api/v1/extract/ai';
        payload = {
          url: trimmedUrl,
          prompt: schemaDescription.trim(),
          include_markdown: includeMarkdown,
          include_screenshots: includeScreenshots,
          include_links: includeLinks,
          wait_for_selector: waitForSelector.trim() || undefined,
          timeout_ms: timeoutMs,
        };
      } else {
        if (!jsonSchema.trim()) {
          throw new Error('Please provide a JSON schema');
        }
        const v = jsonValidate(jsonSchema);
        if (!v.ok) throw new Error(v.error || 'Invalid JSON schema');
        endpoint = '/api/v1/extract';
        payload = {
          url: trimmedUrl,
          schema: JSON.parse(jsonSchema),
          include_markdown: includeMarkdown,
          include_screenshots: includeScreenshots,
          include_links: includeLinks,
          wait_for_selector: waitForSelector.trim() || undefined,
          timeout_ms: timeoutMs,
        };
      }

      const data = await apiFetch(endpoint, {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      setResult(data);
      setHistory(prev =>
        prev.map(h =>
          h.id === jobId ? { ...h, status: 'success', result: data } : h
        )
      );
      showSuccess('Extraction completed');
    } catch (err: any) {
      const msg = err?.message || 'Extraction failed';
      setResultError(msg);
      setHistory(prev =>
        prev.map(h =>
          h.id === jobId ? { ...h, status: 'error', error: msg } : h
        )
      );
      showError(msg);
    } finally {
      setLoading(false);
    }
  };

  const copyResult = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(result, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      showSuccess('Copied to clipboard');
    } catch {
      showError('Failed to copy');
    }
  };

  const handleHistoryClick = (item: HistoryItem) => {
    setSelectedHistoryId(item.id);
    setUrl(item.url);
    setMode(item.mode);
    if (item.mode === 'ai') {
      setSchemaDescription('');
      setJsonSchema('');
    }
    if (item.result) {
      setResult(item.result);
      setResultError(null);
    } else if (item.error) {
      setResult(null);
      setResultError(item.error);
    } else {
      setResult(null);
      setResultError(null);
    }
  };

  const removeHistoryItem = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setHistory(prev => prev.filter(h => h.id !== id));
    if (selectedHistoryId === id) {
      setSelectedHistoryId(null);
      setResult(null);
      setResultError(null);
    }
  };

  const clearHistory = () => {
    if (!confirm('Clear all extraction history?')) return;
    setHistory([]);
    setSelectedHistoryId(null);
    setResult(null);
    setResultError(null);
  };

  // Tutorial logic
  useEffect(() => {
    if (!tutorialOpen) return;
    const step = TUTORIAL_STEPS[tutorialStep];
    if (!step) return;
    const el = document.querySelector(step.target) as HTMLElement | null;
    if (el) {
      tourRefs.current[step.target] = el.getBoundingClientRect();
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [tutorialOpen, tutorialStep]);

  const TutorialOverlay = () => {
    if (!tutorialOpen) return null;
    const step = TUTORIAL_STEPS[tutorialStep];
    const rect = tourRefs.current[step.target];
    const next = () => {
      if (tutorialStep < TUTORIAL_STEPS.length - 1) setTutorialStep(s => s + 1);
      else setTutorialOpen(false);
    };
    const prev = () => setTutorialStep(s => Math.max(0, s - 1));
    const close = () => setTutorialOpen(false);

    return (
      <div className="fixed inset-0 z-[100]" onClick={close}>
        {/* Dark backdrop with cutout */}
        <div className="absolute inset-0 bg-black/60" />
        {rect && (
          <div
            className="absolute bg-transparent shadow-[0_0_0_9999px_rgba(0,0,0,0.6)] rounded-lg transition-all duration-300"
            style={{
              top: rect.top - 6,
              left: rect.left - 6,
              width: rect.width + 12,
              height: rect.height + 12,
            }}
            onClick={e => e.stopPropagation()}
          />
        )}
        {/* Tooltip card */}
        <div
          className="absolute z-[101] bg-[#14141f] border border-[#1c1c2a] rounded-xl p-4 w-72 shadow-2xl transition-all duration-300"
          style={{
            top: rect
              ? step.placement === 'top'
                ? rect.top - 160
                : step.placement === 'bottom'
                ? rect.bottom + 12
                : rect.top + rect.height / 2 - 80
              : '50%',
            left: rect
              ? step.placement === 'left'
                ? rect.left - 300
                : rect.left + rect.width / 2 - 144
              : '50%',
          }}
        >
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-semibold text-white">{step.title}</h4>
            <button onClick={close} className="text-[#5c5c70] hover:text-white">
              <X size={14} />
            </button>
          </div>
          <p className="text-xs text-[#9a9aae] mb-4">{step.body}</p>
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-[#5c5c70]">
              {tutorialStep + 1} / {TUTORIAL_STEPS.length}
            </span>
            <div className="flex gap-2">
              {tutorialStep > 0 && (
                <button
                  onClick={prev}
                  className="flex items-center gap-1 px-2 py-1 rounded text-xs text-[#9a9aae] hover:bg-[#1c1c2a] transition-colors"
                >
                  <ChevronLeft size={12} /> Back
                </button>
              )}
              <button
                onClick={next}
                className="flex items-center gap-1 px-3 py-1 rounded text-xs bg-[#00d4a0] text-black font-medium hover:bg-[#00b88a] transition-colors"
              >
                {tutorialStep === TUTORIAL_STEPS.length - 1 ? 'Finish' : 'Next'}
                {tutorialStep < TUTORIAL_STEPS.length - 1 && <ChevronRight size={12} />}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const isSubmitDisabled =
    loading ||
    !url.trim() ||
    (mode === 'ai' ? !schemaDescription.trim() : !jsonSchema.trim() || !activeSchema.ok);

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white mb-1">No-Code Extract</h2>
          <p className="text-slate-400 text-sm">
            Extract structured data from any web page using AI or JSON schema.
          </p>
        </div>
        <button
          onClick={() => { setTutorialOpen(true); setTutorialStep(0); }}
          className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 rounded-lg px-3 py-2 text-sm transition-colors"
        >
          <Sparkles size={16} />
          Try Tutorial
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Form */}
        <div className="lg:col-span-2 space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* URL */}
            <div
              className="bg-[#0a0a12] border border-[#1c1c2a] rounded-xl p-4"
              data-tour="url"
            >
              <label className="block text-sm font-medium text-[#f0f0f5] mb-2">
                <Globe size={14} className="inline mr-1 -mt-0.5 text-[#9a9aae]" />
                Target URL
              </label>
              <input
                type="url"
                value={url}
                onChange={e => setUrl(e.target.value)}
                placeholder="https://example.com/products"
                required
                className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2.5 text-sm text-[#f0f0f5] placeholder-[#5c5c70] focus:outline-none focus:border-[#00d4a0] transition-colors"
              />
            </div>

            {/* Mode Toggle */}
            <div
              className="bg-[#0a0a12] border border-[#1c1c2a] rounded-xl p-4"
              data-tour="mode"
            >
              <label className="block text-sm font-medium text-[#f0f0f5] mb-2">
                Extraction Mode
              </label>
              <div className="flex bg-[#14141f] rounded-lg p-1 gap-1">
                <button
                  type="button"
                  onClick={() => setMode('ai')}
                  className={`flex-1 flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                    mode === 'ai'
                      ? 'bg-[#00d4a0] text-black'
                      : 'text-[#9a9aae] hover:text-[#f0f0f5] hover:bg-[#1c1c2a]'
                  }`}
                >
                  <Bot size={16} />
                  AI (Natural Language)
                </button>
                <button
                  type="button"
                  onClick={() => setMode('schema')}
                  className={`flex-1 flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                    mode === 'schema'
                      ? 'bg-[#00d4a0] text-black'
                      : 'text-[#9a9aae] hover:text-[#f0f0f5] hover:bg-[#1c1c2a]'
                  }`}
                >
                  <FileJson size={16} />
                  Schema (JSON)
                </button>
              </div>
            </div>

            {/* Mode-specific inputs */}
            {mode === 'ai' ? (
              <div
                className="bg-[#0a0a12] border border-[#1c1c2a] rounded-xl p-4"
                data-tour="ai-input"
              >
                <label className="block text-sm font-medium text-[#f0f0f5] mb-2">
                  What do you want to extract?
                </label>
                <textarea
                  value={schemaDescription}
                  onChange={e => setSchemaDescription(e.target.value)}
                  rows={5}
                  placeholder={`Describe the data you need, e.g.:\n"Extract all product names, prices, and image URLs from the product grid."`}
                  className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2.5 text-sm text-[#f0f0f5] placeholder-[#5c5c70] focus:outline-none focus:border-[#00d4a0] transition-colors resize-y"
                />
                <p className="text-xs text-[#5c5c70] mt-2">
                  The AI will use this description to decide what fields to extract from the page.
                </p>
              </div>
            ) : (
              <div className="bg-[#0a0a12] border border-[#1c1c2a] rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-[#f0f0f5]">
                    JSON Schema
                  </label>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={handleBeautify}
                      className="text-xs text-[#9a9aae] hover:text-[#00d4a0] transition-colors"
                    >
                      Beautify
                    </button>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full border ${
                        activeSchema.ok
                          ? 'text-green-400 border-green-500/30 bg-green-500/10'
                          : jsonSchema.trim()
                          ? 'text-red-400 border-red-500/30 bg-red-500/10'
                          : 'text-[#5c5c70] border-[#1c1c2a] bg-[#14141f]'
                      }`}
                    >
                      {activeSchema.ok ? 'Valid JSON' : jsonSchema.trim() ? 'Invalid JSON' : 'Empty'}
                    </span>
                  </div>
                </div>
                <textarea
                  value={jsonSchema}
                  onChange={e => setJsonSchema(e.target.value)}
                  rows={10}
                  placeholder={`{\n  "type": "object",\n  "properties": {\n    "title": { "type": "string" }\n  }\n}`}
                  className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2.5 text-sm text-[#f0f0f5] placeholder-[#5c5c70] focus:outline-none focus:border-[#00d4a0] transition-colors resize-y font-mono"
                />
                {jsonSchema.trim() && !activeSchema.ok && (
                  <p className="text-xs text-red-400 mt-2">{activeSchema.error}</p>
                )}
                <p className="text-xs text-[#5c5c70] mt-2">
                  Define the structure of the data you want. The backend will enforce this schema during extraction.
                </p>
              </div>
            )}

            {/* Options */}
            <div
              className="bg-[#0a0a12] border border-[#1c1c2a] rounded-xl p-4"
              data-tour="options"
            >
              <label className="block text-sm font-medium text-[#f0f0f5] mb-3">
                Options
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
                <label className="flex items-center gap-2 text-sm text-[#9a9aae] cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={includeMarkdown}
                    onChange={e => setIncludeMarkdown(e.target.checked)}
                    className="accent-[#00d4a0] w-4 h-4 rounded border-[#1c1c2a]"
                  />
                  Include markdown
                </label>
                <label className="flex items-center gap-2 text-sm text-[#9a9aae] cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={includeScreenshots}
                    onChange={e => setIncludeScreenshots(e.target.checked)}
                    className="accent-[#00d4a0] w-4 h-4 rounded border-[#1c1c2a]"
                  />
                  Include screenshots
                </label>
                <label className="flex items-center gap-2 text-sm text-[#9a9aae] cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={includeLinks}
                    onChange={e => setIncludeLinks(e.target.checked)}
                    className="accent-[#00d4a0] w-4 h-4 rounded border-[#1c1c2a]"
                  />
                  Include links
                </label>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-[#5c5c70] mb-1">
                    Wait for selector (optional)
                  </label>
                  <input
                    type="text"
                    value={waitForSelector}
                    onChange={e => setWaitForSelector(e.target.value)}
                    placeholder=".content-loaded"
                    className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-sm text-[#f0f0f5] placeholder-[#5c5c70] focus:outline-none focus:border-[#00d4a0] transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-xs text-[#5c5c70] mb-1">
                    Timeout (ms)
                  </label>
                  <input
                    type="number"
                    min={1000}
                    max={120000}
                    step={1000}
                    value={timeoutMs}
                    onChange={e => setTimeoutMs(Number(e.target.value))}
                    className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-sm text-[#f0f0f5] placeholder-[#5c5c70] focus:outline-none focus:border-[#00d4a0] transition-colors"
                  />
                </div>
              </div>
            </div>

            {/* Submit */}
            <div className="flex items-center gap-3" data-tour="submit">
              <button
                type="submit"
                disabled={isSubmitDisabled}
                className="flex items-center gap-2 bg-[#00d4a0] hover:bg-[#00b88a] disabled:bg-[#00d4a0]/30 disabled:text-black/50 disabled:cursor-not-allowed text-black rounded-lg px-5 py-2.5 text-sm font-semibold transition-colors"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin inline-block" />
                    Extracting...
                  </span>
                ) : (
                  <>
                    <Play size={16} />
                    Run Extraction
                  </>
                )}
              </button>
              {mode === 'schema' && !activeSchema.ok && jsonSchema.trim() && (
                <span className="text-xs text-red-400 flex items-center gap-1">
                  <AlertTriangle size={12} />
                  Fix schema errors before submitting
                </span>
              )}
            </div>
          </form>

          {/* Result */}
          {(result || resultError) && (
            <div className="bg-[#0a0a12] border border-[#1c1c2a] rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-[#f0f0f5]">
                  {resultError ? 'Extraction Error' : 'Result'}
                </h3>
                <div className="flex items-center gap-2">
                  {!resultError && result && (
                    <>
                      <button
                        onClick={copyResult}
                        className="flex items-center gap-1 text-xs text-[#9a9aae] hover:text-[#00d4a0] bg-[#14141f] border border-[#1c1c2a] rounded px-2 py-1 transition-colors"
                      >
                        {copied ? <Check size={12} /> : <Copy size={12} />}
                        {copied ? 'Copied' : 'Copy'}
                      </button>
                      <button
                        onClick={() => downloadJson(result, `extract-${Date.now()}.json`)}
                        className="flex items-center gap-1 text-xs text-[#9a9aae] hover:text-[#00d4a0] bg-[#14141f] border border-[#1c1c2a] rounded px-2 py-1 transition-colors"
                      >
                        <Download size={12} />
                        Download
                      </button>
                    </>
                  )}
                </div>
              </div>
              {resultError ? (
                <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-sm text-red-300 flex items-start gap-2">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                  <span>{resultError}</span>
                </div>
              ) : (
                <pre className="bg-[#14141f] border border-[#1c1c2a] rounded-lg p-3 overflow-x-auto text-xs text-[#b8b8c8] max-h-96 overflow-y-auto">
                  {JSON.stringify(result, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>

        {/* Right: History */}
        <div className="lg:col-span-1">
          <div className="bg-[#0a0a12] border border-[#1c1c2a] rounded-xl p-4 h-full">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-[#f0f0f5] flex items-center gap-2">
                <History size={16} className="text-[#9a9aae]" />
                History
              </h3>
              {history.length > 0 && (
                <button
                  onClick={clearHistory}
                  className="text-[10px] text-[#5c5c70] hover:text-red-400 flex items-center gap-1 transition-colors"
                >
                  <Trash2 size={12} />
                  Clear
                </button>
              )}
            </div>
            {history.length === 0 ? (
              <div className="text-center py-8">
                <Clock size={32} className="text-[#1c1c2a] mx-auto mb-2" />
                <p className="text-xs text-[#5c5c70]">No extractions yet.</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[70vh] overflow-y-auto pr-1">
                {history.map(item => (
                  <button
                    key={item.id}
                    onClick={() => handleHistoryClick(item)}
                    className={`w-full text-left rounded-lg border px-3 py-2.5 transition-colors group relative ${
                      selectedHistoryId === item.id
                        ? 'bg-[rgba(0,212,160,0.08)] border-[#00d4a0]/30'
                        : 'bg-[#14141f] border-[#1c1c2a] hover:border-[#2a2a3e]'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <Link2 size={12} className="text-[#5c5c70] shrink-0" />
                        <span className="text-xs text-[#f0f0f5] truncate font-medium">
                          {item.url.replace(/^https?:\/\//, '').slice(0, 40)}
                          {item.url.replace(/^https?:\/\//, '').length > 40 ? '…' : ''}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0 ml-2">
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded-full border ${
                            item.mode === 'ai'
                              ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                              : 'bg-orange-500/10 text-orange-400 border-orange-500/20'
                          }`}
                        >
                          {item.mode === 'ai' ? 'AI' : 'Schema'}
                        </span>
                        {item.status === 'loading' && (
                          <span className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
                        )}
                        {item.status === 'success' && (
                          <span className="w-2 h-2 rounded-full bg-green-400" />
                        )}
                        {item.status === 'error' && (
                          <span className="w-2 h-2 rounded-full bg-red-400" />
                        )}
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-[#5c5c70]">
                        {new Date(item.timestamp).toLocaleString()}
                      </span>
                      <button
                        onClick={e => removeHistoryItem(item.id, e)}
                        className="opacity-0 group-hover:opacity-100 text-[#5c5c70] hover:text-red-400 transition-opacity"
                        title="Remove"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </button>
                ))}
              </div>
            )}
            <div className="mt-3 pt-3 border-t border-[#1c1c2a]">
              <div className="flex items-start gap-2 text-[#5c5c70]">
                <Info size={12} className="mt-0.5 shrink-0" />
                <p className="text-[10px] leading-relaxed">
                  History is stored locally in your browser. It is not synced with the server.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <TutorialOverlay />
    </div>
  );
};
