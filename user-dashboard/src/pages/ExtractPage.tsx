import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  Link2, Bot, FileJson, Download, Copy, Check, History,
  X, Sparkles, AlertTriangle, ChevronRight, ChevronLeft,
  Globe, Clock, Info, Trash2, Play, Lock, Layers, HelpCircle,
  ChevronDown
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

interface Subscription {
  subscription: { plan: string; status: string } | null;
  trial: { extractions_total: number; extractions_used: number; extractions_remaining: number; days_left: number } | null;
  available_plans: Array<{ key: string; name: string; extractions_per_month: number; features: string[] }>;
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

const SCHEMA_TEMPLATES = [
  {
    name: '🛒 E-commerce Products',
    schema: { selectors: { name: '.product-title', price: '.product-price', image: '.product-image@src', rating: '.product-rating', description: '.product-description' } }
  },
  {
    name: '📰 News Articles',
    schema: { selectors: { title: 'article h1', author: '.author-name', date: '.publish-date', content: 'article .body', url: 'article a@href' } }
  },
  {
    name: '🏠 Real Estate Listings',
    schema: { selectors: { address: '.listing-address', price: '.listing-price', beds: '.beds-count', baths: '.baths-count', sqft: '.sqft-value', image: '.listing-photo@src' } }
  },
  {
    name: '💼 Job Postings',
    schema: { selectors: { title: '.job-title', company: '.company-name', location: '.job-location', salary: '.salary-range', description: '.job-description' } }
  },
  {
    name: '📊 Financial Data',
    schema: { selectors: { symbol: '.stock-symbol', price: '.stock-price', change: '.price-change', volume: '.trade-volume' } }
  },
  {
    name: '🔍 SEO Meta Tags',
    schema: { selectors: { title: 'meta[property="og:title"]@content', description: 'meta[property="og:description"]@content', keywords: 'meta[name="keywords"]@content', image: 'meta[property="og:image"]@content' } }
  },
];

const EXTRACT_OPTIONS = [
  { key: 'markdown', icon: '📝', label: 'Markdown', desc: 'Convert page to clean markdown' },
  { key: 'screenshot', icon: '📸', label: 'Screenshot', desc: 'Capture full-page screenshot' },
  { key: 'links', icon: '🔗', label: 'Links', desc: 'Extract all hyperlinks from the page' },
  { key: 'javascript', icon: '⚡', label: 'JavaScript', desc: 'Enable JS rendering for SPAs' },
  { key: 'waitForSelector', icon: '🎯', label: 'Wait for Element', desc: 'Wait until a specific element appears — great for dynamic content' },
];

const formatNumber = (n: number) => n.toLocaleString();

export const ExtractPage: React.FC = () => {
  const { apiFetch, showError, showSuccess } = useAuth();

  const [url, setUrl] = useState('');
  const [mode, setMode] = useState<Mode>('ai');
  const [schemaDescription, setSchemaDescription] = useState('');
  const [jsonSchema, setJsonSchema] = useState('');

  const [includeMarkdown, setIncludeMarkdown] = useState(true);
  const [includeScreenshots, setIncludeScreenshots] = useState(false);
  const [includeLinks, setIncludeLinks] = useState(true);
  const [includeJavascript, setIncludeJavascript] = useState(false);
  const [waitForSelector, setWaitForSelector] = useState('');

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any | null>(null);
  const [resultError, setResultError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [history, setHistory] = useState<HistoryItem[]>(() => loadHistory());
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);

  const [tutorialOpen, setTutorialOpen] = useState(false);
  const [tutorialStep, setTutorialStep] = useState(0);
  const tourRefs = useRef<Record<string, DOMRect | null>>({});

  // Plan-aware state
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [batchMode, setBatchMode] = useState(false);
  const [batchUrls, setBatchUrls] = useState('');
  const [templateDropdownOpen, setTemplateDropdownOpen] = useState(false);

  // Fetch subscription on mount
  useEffect(() => {
    const fetchSub = async () => {
      try {
        const data = await apiFetch('/api/v1/subscriptions/me');
        setSubscription(data);
      } catch {
        // Silently fail — UI degrades gracefully
      }
    };
    fetchSub();
  }, [apiFetch]);

  const currentPlan = subscription?.subscription?.plan?.toLowerCase() || 'hobby';
  const isHobby = currentPlan === 'hobby' || currentPlan === 'free' || !subscription?.subscription;
  const isPro = currentPlan === 'pro';
  const isEnterprise = currentPlan === 'enterprise' || currentPlan === 'business';
  const canUseAI = !isHobby;
  const canUseBatch = !isHobby;
  const batchLimit = isEnterprise ? 50 : 10;

  // Persist history
  useEffect(() => {
    saveHistory(history);
  }, [history]);

  const activeSchema = useMemo(() => jsonValidate(jsonSchema), [jsonSchema]);

  const handleBeautify = () => {
    setJsonSchema(jsonBeautify(jsonSchema));
  };

  const toggleOption = (key: string) => {
    switch (key) {
      case 'markdown': setIncludeMarkdown(v => !v); break;
      case 'screenshot': setIncludeScreenshots(v => !v); break;
      case 'links': setIncludeLinks(v => !v); break;
      case 'javascript': setIncludeJavascript(v => !v); break;
      case 'waitForSelector':
        if (waitForSelector) {
          setWaitForSelector('');
        } else {
          setWaitForSelector(' ');
        }
        break;
    }
  };

  const isOptionActive = (key: string): boolean => {
    switch (key) {
      case 'markdown': return includeMarkdown;
      case 'screenshot': return includeScreenshots;
      case 'links': return includeLinks;
      case 'javascript': return includeJavascript;
      case 'waitForSelector': return waitForSelector.trim().length > 0;
      default: return false;
    }
  };

  const handleTemplateSelect = (template: typeof SCHEMA_TEMPLATES[number]) => {
    setJsonSchema(JSON.stringify(template.schema, null, 2));
    setTemplateDropdownOpen(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Determine URLs
    let urls: string[] = [];
    if (batchMode && canUseBatch) {
      const lines = batchUrls.split('\n').map(l => l.trim()).filter(Boolean);
      if (lines.length === 0) {
        showError('Please enter at least one URL');
        return;
      }
      if (lines.length > batchLimit) {
        showError(`Maximum ${batchLimit} URLs allowed for your plan`);
        return;
      }
      urls = lines;
    } else {
      if (!url.trim()) {
        showError('Please enter a URL');
        return;
      }
      urls = [url.trim()];
    }

    setLoading(true);
    setResult(null);
    setResultError(null);
    setSelectedHistoryId(null);

    const jobId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const historyEntry: HistoryItem = {
      id: jobId,
      url: urls[0] + (urls.length > 1 ? ` (+${urls.length - 1} more)` : ''),
      mode,
      timestamp: Date.now(),
      status: 'loading',
    };
    setHistory(prev => [historyEntry, ...prev]);

    try {
      let payload: any;
      let endpoint: string;

      const optionsPayload = {
        include_markdown: includeMarkdown,
        include_screenshots: includeScreenshots,
        include_links: includeLinks,
        include_javascript: includeJavascript,
        wait_for_selector: waitForSelector.trim() || undefined,
        timeout_ms: 30000,
      };

      if (mode === 'ai') {
        if (!schemaDescription.trim()) {
          throw new Error('Please describe what you want to extract');
        }
        endpoint = '/api/v1/extract/ai';
        payload = batchMode && urls.length > 1
          ? { urls, prompt: schemaDescription.trim(), ...optionsPayload }
          : { url: urls[0], prompt: schemaDescription.trim(), ...optionsPayload };
      } else {
        if (!jsonSchema.trim()) {
          throw new Error('Please provide a JSON schema');
        }
        const v = jsonValidate(jsonSchema);
        if (!v.ok) throw new Error(v.error || 'Invalid JSON schema');
        endpoint = '/api/v1/extract';
        payload = batchMode && urls.length > 1
          ? { urls, schema: JSON.parse(jsonSchema), ...optionsPayload }
          : { url: urls[0], schema: JSON.parse(jsonSchema), ...optionsPayload };
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

  const hasValidInput = batchMode && canUseBatch
    ? batchUrls.split('\n').map(l => l.trim()).filter(Boolean).length > 0
    : url.trim().length > 0;

  const isSubmitDisabled =
    loading ||
    !hasValidInput ||
    (mode === 'ai' ? !schemaDescription.trim() : !jsonSchema.trim() || !activeSchema.ok);

  const planBadgeColor = isHobby
    ? 'bg-[#14141f] border-[#1c1c2a] text-[#9a9aae]'
    : isPro
    ? 'bg-[#4494ff]/10 border-[#4494ff]/30 text-[#4494ff]'
    : 'bg-[#00d4a0]/10 border-[#00d4a0]/30 text-[#00d4a0]';

  const planLabel = subscription?.subscription
    ? `${subscription.subscription.plan.charAt(0).toUpperCase() + subscription.subscription.plan.slice(1)} Plan`
    : 'Hobby Plan';

  // Usage data
  const usageUsed = subscription?.trial?.extractions_used ?? 0;
  const usageTotal = subscription?.trial?.extractions_total ?? (
    subscription?.available_plans?.find(p => p.key === currentPlan)?.extractions_per_month ?? 1000
  );
  const usagePercent = usageTotal > 0 ? Math.min((usageUsed / usageTotal) * 100, 100) : 0;

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold text-white">Extract</h2>
            <span className={`text-[11px] px-2.5 py-0.5 rounded-full border font-medium ${planBadgeColor}`}>
              {planLabel}
            </span>
          </div>
          <button
            onClick={() => { setTutorialOpen(true); setTutorialStep(0); }}
            className="flex items-center gap-2 bg-[#14141f] hover:bg-[#1c1c2a] border border-[#1c1c2a] text-[#f0f0f5] rounded-lg px-3 py-2 text-sm transition-colors"
          >
            <Sparkles size={16} />
            Try Tutorial
          </button>
        </div>
        <p className="text-[#9a9aae] text-sm mb-3">
          Extract structured data from any web page using AI or JSON schema.
        </p>

        {/* Usage Bar */}
        {subscription && (
          <div className="bg-[#0a0a12] border border-[#1c1c2a] rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-[#9a9aae]">
                {formatNumber(usageUsed)} / {formatNumber(usageTotal)} extractions used
              </span>
              {subscription.trial && (
                <span className="text-xs text-[#00d4a0] flex items-center gap-1">
                  <Clock size={12} />
                  Trial: {subscription.trial.days_left} days left, {formatNumber(subscription.trial.extractions_remaining)} remaining
                </span>
              )}
            </div>
            <div className="w-full h-1.5 bg-[#14141f] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${usagePercent}%`,
                  backgroundColor: usagePercent > 90 ? '#ef4444' : usagePercent > 70 ? '#f59e0b' : '#00d4a0',
                }}
              />
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Form */}
        <div className="lg:col-span-2 space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* URL / Batch Input */}
            <div
              className="bg-[#0a0a12] border border-[#1c1c2a] rounded-xl p-4"
              data-tour="url"
            >
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium text-[#f0f0f5]">
                  <Globe size={14} className="inline mr-1 -mt-0.5 text-[#9a9aae]" />
                  {batchMode ? 'Batch URLs' : 'Target URL'}
                </label>
                <div className="flex items-center bg-[#14141f] rounded-lg p-0.5">
                  <button
                    type="button"
                    onClick={() => setBatchMode(false)}
                    className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                      !batchMode
                        ? 'bg-[#1c1c2a] text-[#f0f0f5]'
                        : 'text-[#5c5c70] hover:text-[#9a9aae]'
                    }`}
                  >
                    <Globe size={12} />
                    Single URL
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (!canUseBatch) return;
                      setBatchMode(true);
                    }}
                    className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-colors relative ${
                      !canUseBatch
                        ? 'text-[#5c5c70] cursor-not-allowed'
                        : batchMode
                        ? 'bg-[#1c1c2a] text-[#f0f0f5]'
                        : 'text-[#5c5c70] hover:text-[#9a9aae]'
                    }`}
                    title={!canUseBatch ? 'Upgrade to Pro for batch mode' : undefined}
                  >
                    {!canUseBatch && <Lock size={10} className="text-[#5c5c70]" />}
                    <Layers size={12} />
                    Batch Mode
                  </button>
                </div>
              </div>

              {batchMode && canUseBatch ? (
                <div>
                  <textarea
                    value={batchUrls}
                    onChange={e => setBatchUrls(e.target.value)}
                    rows={4}
                    placeholder={`Enter one URL per line (max ${batchLimit}):\nhttps://example.com/page1\nhttps://example.com/page2\nhttps://example.com/page3`}
                    className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2.5 text-sm text-[#f0f0f5] placeholder-[#5c5c70] focus:outline-none focus:border-[#00d4a0] transition-colors resize-y font-mono"
                  />
                  <p className="text-xs text-[#5c5c70] mt-1.5">
                    {batchUrls.split('\n').filter(l => l.trim()).length} / {batchLimit} URLs entered
                  </p>
                </div>
              ) : (
                <input
                  type="url"
                  value={url}
                  onChange={e => setUrl(e.target.value)}
                  placeholder="https://example.com/products"
                  required={!batchMode}
                  className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2.5 text-sm text-[#f0f0f5] placeholder-[#5c5c70] focus:outline-none focus:border-[#00d4a0] transition-colors"
                />
              )}

              {!canUseBatch && (
                <div className="flex items-center gap-2 mt-2 text-xs text-[#5c5c70]">
                  <Lock size={12} />
                  <span>
                    Batch mode available with{' '}
                    <button
                      type="button"
                      className="text-[#4494ff] hover:underline"
                      onClick={() => window.location.href = '/dashboard/subscription'}
                    >
                      Pro plan
                    </button>
                  </span>
                </div>
              )}
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
                  onClick={() => {
                    if (!canUseAI) return;
                    setMode('ai');
                  }}
                  className={`flex-1 flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                    !canUseAI
                      ? 'text-[#5c5c70] cursor-not-allowed relative'
                      : mode === 'ai'
                      ? 'bg-[#00d4a0] text-black'
                      : 'text-[#9a9aae] hover:text-[#f0f0f5] hover:bg-[#1c1c2a]'
                  }`}
                >
                  {!canUseAI && <Lock size={14} className="absolute left-3" />}
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
              {!canUseAI && (
                <div className="flex items-center gap-2 mt-2 text-xs text-[#5c5c70]">
                  <Lock size={12} />
                  <span>
                    AI mode requires a{' '}
                    <button
                      type="button"
                      className="text-[#4494ff] hover:underline"
                      onClick={() => window.location.href = '/dashboard/subscription'}
                    >
                      Pro or Enterprise plan
                    </button>
                  </span>
                </div>
              )}
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
                {/* Templates dropdown */}
                <div className="mb-3">
                  <label className="block text-xs text-[#5c5c70] mb-1.5">
                    Quick Templates
                  </label>
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setTemplateDropdownOpen(v => !v)}
                      className="w-full flex items-center justify-between bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-sm text-[#9a9aae] hover:border-[#2a2a3e] transition-colors"
                    >
                      <span>Select a pre-made schema template...</span>
                      <ChevronDown size={14} className={`transition-transform ${templateDropdownOpen ? 'rotate-180' : ''}`} />
                    </button>
                    {templateDropdownOpen && (
                      <div className="absolute z-20 w-full mt-1 bg-[#14141f] border border-[#1c1c2a] rounded-lg shadow-xl overflow-hidden">
                        {SCHEMA_TEMPLATES.map((tpl, i) => (
                          <button
                            key={i}
                            type="button"
                            onClick={() => handleTemplateSelect(tpl)}
                            className="w-full text-left px-3 py-2 text-sm text-[#f0f0f5] hover:bg-[#1c1c2a] transition-colors border-b border-[#1c1c2a] last:border-b-0"
                          >
                            {tpl.name}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

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

            {/* Options — Icon Toggle Buttons */}
            <div
              className="bg-[#0a0a12] border border-[#1c1c2a] rounded-xl p-4"
              data-tour="options"
            >
              <label className="block text-sm font-medium text-[#f0f0f5] mb-3">
                Options
              </label>
              <div className="flex flex-wrap gap-2">
                {EXTRACT_OPTIONS.map(opt => {
                  const active = isOptionActive(opt.key);
                  return (
                    <button
                      key={opt.key}
                      type="button"
                      onClick={() => toggleOption(opt.key)}
                      title={opt.desc}
                      className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm font-medium transition-all ${
                        active
                          ? 'bg-[#00d4a0]/10 border-[#00d4a0]/30 text-[#00d4a0]'
                          : 'bg-[#14141f] border-[#1c1c2a] text-[#9a9aae] hover:border-[#2a2a3e] hover:text-[#b8b8c8]'
                      }`}
                    >
                      <span className="text-base">{opt.icon}</span>
                      {opt.label}
                    </button>
                  );
                })}
              </div>

              {/* Wait for Element sub-input */}
              {isOptionActive('waitForSelector') && waitForSelector.trim().length > 0 && (
                <div className="mt-3">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <label className="text-xs text-[#5c5c70]">CSS Selector</label>
                    <span className="group relative">
                      <HelpCircle size={12} className="text-[#5c5c70] cursor-help" />
                      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 w-56 bg-[#1c1c2a] border border-[#2a2a3e] text-xs text-[#9a9aae] rounded-lg p-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-30">
                        Enter a CSS selector for the element to wait for. The extractor will pause until this element appears in the DOM, useful for SPAs with lazy-loaded content.
                      </span>
                    </span>
                  </div>
                  <input
                    type="text"
                    value={waitForSelector === ' ' ? '' : waitForSelector}
                    onChange={e => setWaitForSelector(e.target.value)}
                    placeholder=".content-loaded"
                    className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-sm text-[#f0f0f5] placeholder-[#5c5c70] focus:outline-none focus:border-[#00d4a0] transition-colors"
                  />
                </div>
              )}
              {isOptionActive('waitForSelector') && waitForSelector.trim().length === 0 && (
                <div className="mt-3">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <label className="text-xs text-[#5c5c70]">CSS Selector</label>
                    <span className="group relative">
                      <HelpCircle size={12} className="text-[#5c5c70] cursor-help" />
                      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 w-56 bg-[#1c1c2a] border border-[#2a2a3e] text-xs text-[#9a9aae] rounded-lg p-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-30">
                        Enter a CSS selector for the element to wait for. The extractor will pause until this element appears in the DOM, useful for SPAs with lazy-loaded content.
                      </span>
                    </span>
                  </div>
                  <input
                    type="text"
                    value={waitForSelector}
                    onChange={e => setWaitForSelector(e.target.value)}
                    placeholder=".content-loaded"
                    className="w-full bg-[#14141f] border border-[#1c1c2a] rounded-lg px-3 py-2 text-sm text-[#f0f0f5] placeholder-[#5c5c70] focus:outline-none focus:border-[#00d4a0] transition-colors"
                  />
                </div>
              )}
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
