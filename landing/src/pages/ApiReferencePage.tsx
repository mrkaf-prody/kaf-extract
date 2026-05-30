import { useState } from 'react'
import { Link } from 'react-router-dom'

const endpoints = [
  {
    method: 'POST',
    path: '/api/v1/extract',
    title: 'CSS Extraction',
    desc: 'Extract data from a URL using CSS selectors.',
    request: `{
  "url": "https://example.com/products",
  "selectors": {
    "name": ".product-title",
    "price": ".product-price",
    "image": ".product-image@src"
  }
}`,
    response: `{
  "status": "success",
  "data": [
    {
      "name": "Widget Pro",
      "price": "$29.99",
      "image": "https://example.com/img/widget.jpg"
    }
  ],
  "count": 1,
  "url": "https://example.com/products",
  "extracted_at": "2025-01-15T10:30:00Z"
}`,
    headers: `Authorization: Bearer <api_key>
Content-Type: application/json`,
  },
  {
    method: 'POST',
    path: '/api/v1/extract/ai',
    title: 'AI Extraction',
    desc: 'Extract data using natural language descriptions. The AI understands page structure automatically.',
    request: `{
  "url": "https://news.ycombinator.com",
  "prompt": "Extract the top 5 story titles and their URLs",
  "format": "json"
}`,
    response: `{
  "status": "success",
  "data": {
    "stories": [
      {
        "title": "Show HN: Kaf Extract",
        "url": "https://example.com"
      }
    ]
  },
  "model": "gpt-4",
  "tokens_used": 1250
}`,
    headers: `Authorization: Bearer <api_key>
Content-Type: application/json`,
  },
  {
    method: 'GET',
    path: '/api/v1/extract/history',
    title: 'Extraction History',
    desc: 'Retrieve your extraction history with pagination and filtering.',
    request: `GET /api/v1/extract/history?page=1&limit=20&status=success`,
    response: `{
  "extractions": [
    {
      "id": "ext_abc123",
      "url": "https://example.com",
      "type": "ai",
      "status": "success",
      "created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "limit": 20
}`,
    headers: `Authorization: Bearer <api_key>`,
  },
  {
    method: 'GET',
    path: '/api/v1/keys',
    title: 'List API Keys',
    desc: 'List all API keys for your account.',
    request: `GET /api/v1/keys`,
    response: `{
  "keys": [
    {
      "id": "key_abc123",
      "name": "Production",
      "prefix": "kaf_...3x9f",
      "created_at": "2025-01-10T00:00:00Z",
      "last_used_at": "2025-01-15T10:30:00Z"
    }
  ]
}`,
    headers: `Authorization: Bearer <jwt_token>`,
  },
  {
    method: 'POST',
    path: '/api/v1/schedules',
    title: 'Create Schedule',
    desc: 'Schedule recurring extractions to run automatically.',
    request: `{
  "name": "Daily Price Check",
  "url": "https://example.com/pricing",
  "type": "ai",
  "prompt": "Extract all product prices",
  "cron": "0 9 * * *",
  "webhook_url": "https://your-app.com/webhook"
}`,
    response: `{
  "id": "sched_xyz789",
  "name": "Daily Price Check",
  "status": "active",
  "next_run": "2025-01-16T09:00:00Z",
  "cron": "0 9 * * *"
}`,
    headers: `Authorization: Bearer <api_key>
Content-Type: application/json`,
  },
]

const errorCodes = [
  { code: 400, name: 'Bad Request', desc: 'Invalid request parameters or malformed JSON body.' },
  { code: 401, name: 'Unauthorized', desc: 'Missing or invalid API key / JWT token.' },
  { code: 403, name: 'Forbidden', desc: 'API key does not have permission for this action.' },
  { code: 404, name: 'Not Found', desc: 'The requested resource does not exist.' },
  { code: 429, name: 'Rate Limited', desc: 'Too many requests. Check Retry-After header.' },
  { code: 500, name: 'Server Error', desc: 'Internal server error. Contact support if persistent.' },
  { code: 502, name: 'Bad Gateway', desc: 'Target website returned an error or is unreachable.' },
  { code: 504, name: 'Timeout', desc: 'Extraction timed out. Try simplifying the request.' },
]

export default function ApiReferencePage() {
  const [activeEndpoint, setActiveEndpoint] = useState(0)

  return (
    <div className="pt-24 pb-20">
      <div className="section-container max-w-5xl">
        {/* Header */}
        <div className="mb-12">
          <Link to="/" className="text-sm text-gray-500 hover:text-white transition-colors mb-4 inline-flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            Back to Home
          </Link>
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            API <span className="gradient-text">Reference</span>
          </h1>
          <p className="text-gray-400 text-lg max-w-2xl">
            Complete documentation for the Kaf Extract API. Extract structured data from any website with simple HTTP requests.
          </p>
        </div>

        {/* Quick Start */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
            <span className="w-8 h-8 rounded-lg bg-[#00d4a0]/20 flex items-center justify-center text-[#00d4a0] text-sm">⚡</span>
            Quick Start
          </h2>
          <div className="glass-card p-6 space-y-6">
            <div>
              <h3 className="font-semibold text-white mb-3">1. Get your API key</h3>
              <div className="code-block text-sm">
                <pre><code>
                  <span className="text-gray-500"># Sign up and get your API key from the dashboard</span>{'\n'}
                  <span className="text-[#00d4a0]">curl</span> <span className="text-[#4494ff]">https://extract.kafcenter.com/dashboard/register</span>
                </code></pre>
              </div>
            </div>
            <div>
              <h3 className="font-semibold text-white mb-3">2. Make your first extraction</h3>
              <div className="code-block text-sm">
                <pre><code>
                  <span className="text-[#00d4a0]">curl</span> <span className="text-white">-X POST </span><span className="text-[#4494ff]">https://extract.kafcenter.com/v1/extract/ai</span> \{'\n'}
                  <span className="text-white">  -H </span><span className="text-yellow-300">"Authorization: Bearer YOUR_API_KEY"</span> \{'\n'}
                  <span className="text-white">  -H </span><span className="text-yellow-300">"Content-Type: application/json"</span> \{'\n'}
                  <span className="text-white">  -d </span><span className="text-yellow-300">{'\'{"url":"https://example.com","prompt":"Extract page title"}\''}</span>
                </code></pre>
              </div>
            </div>
          </div>
        </section>

        {/* Authentication */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
            <span className="w-8 h-8 rounded-lg bg-[#4494ff]/20 flex items-center justify-center text-[#4494ff] text-sm">🔑</span>
            Authentication
          </h2>
          <div className="glass-card p-6 space-y-4">
            <p className="text-gray-400">
              Kaf Extract supports two authentication methods:
            </p>
            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-[#06060a] rounded-lg p-4 border border-[#1c1c2a]">
                <h4 className="font-semibold text-white mb-2">API Key</h4>
                <p className="text-sm text-gray-400 mb-3">
                  Best for server-to-server integrations. Pass in the <code className="text-[#00d4a0]">Authorization</code> header.
                </p>
                <code className="text-xs text-[#4494ff]">Authorization: Bearer kaf_your_api_key</code>
              </div>
              <div className="bg-[#06060a] rounded-lg p-4 border border-[#1c1c2a]">
                <h4 className="font-semibold text-white mb-2">JWT Token</h4>
                <p className="text-sm text-gray-400 mb-3">
                  Best for browser-based apps. Obtained via the login endpoint. Short-lived tokens.
                </p>
                <code className="text-xs text-[#4494ff]">Authorization: Bearer eyJhbG...</code>
              </div>
            </div>
          </div>
        </section>

        {/* Endpoints */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
            <span className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center text-purple-400 text-sm">📡</span>
            Endpoints
          </h2>

          {/* Endpoint tabs */}
          <div className="flex flex-wrap gap-2 mb-6">
            {endpoints.map((ep, i) => (
              <button
                key={i}
                onClick={() => setActiveEndpoint(i)}
                className={`px-4 py-2 rounded-lg text-sm font-mono transition-all ${
                  activeEndpoint === i
                    ? 'bg-[#00d4a0]/20 text-[#00d4a0] border border-[#00d4a0]/30'
                    : 'bg-[#0f0f18] text-gray-400 border border-[#1c1c2a] hover:border-gray-600'
                }`}
              >
                <span className={`mr-2 font-bold ${
                  ep.method === 'GET' ? 'text-[#4494ff]' : 'text-[#00d4a0]'
                }`}>
                  {ep.method}
                </span>
                {ep.title}
              </button>
            ))}
          </div>

          {/* Active endpoint detail */}
          {endpoints.map((ep, i) => (
            activeEndpoint === i && (
              <div key={i} className="glass-card p-6 space-y-6" style={{ animation: 'fadeInUp 0.4s ease-out' }}>
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                      ep.method === 'GET' ? 'bg-[#4494ff]/20 text-[#4494ff]' : 'bg-[#00d4a0]/20 text-[#00d4a0]'
                    }`}>
                      {ep.method}
                    </span>
                    <code className="text-white font-mono">{ep.path}</code>
                  </div>
                  <p className="text-gray-400">{ep.desc}</p>
                </div>

                <div>
                  <h4 className="text-sm font-semibold text-gray-300 mb-2">Headers</h4>
                  <div className="code-block text-sm">
                    <pre><code>{ep.headers}</code></pre>
                  </div>
                </div>

                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <h4 className="text-sm font-semibold text-gray-300 mb-2">Request</h4>
                    <div className="code-block text-sm">
                      <pre><code>{ep.request}</code></pre>
                    </div>
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-gray-300 mb-2">Response</h4>
                    <div className="code-block text-sm">
                      <pre><code>{ep.response}</code></pre>
                    </div>
                  </div>
                </div>
              </div>
            )
          ))}
        </section>

        {/* SDKs */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
            <span className="w-8 h-8 rounded-lg bg-yellow-500/20 flex items-center justify-center text-yellow-400 text-sm">📦</span>
            SDKs
          </h2>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="glass-card p-6">
              <h3 className="font-semibold text-white mb-3 flex items-center gap-2">
                <span className="text-[#4494ff]">🐍</span> Python
              </h3>
              <div className="code-block text-sm">
                <pre><code>
                  <span className="text-purple-400">pip</span> install kaf-extract{'\n\n'}
                  <span className="text-purple-400">from</span> kaf_extract <span className="text-purple-400">import</span> KafClient{'\n\n'}
                  client = KafClient(api_key=<span className="text-yellow-300">"your_key"</span>){'\n'}
                  result = client.extract_ai({'\n'}
                  {'  '}url=<span className="text-yellow-300">"https://example.com"</span>,{'\n'}
                  {'  '}prompt=<span className="text-yellow-300">"Extract all products"</span>{'\n'}
                  )
                </code></pre>
              </div>
            </div>
            <div className="glass-card p-6">
              <h3 className="font-semibold text-white mb-3 flex items-center gap-2">
                <span className="text-yellow-400">⚡</span> JavaScript
              </h3>
              <div className="code-block text-sm">
                <pre><code>
                  <span className="text-purple-400">npm</span> install kaf-extract{'\n\n'}
                  <span className="text-purple-400">import</span> {'{ KafClient }'} <span className="text-purple-400">from</span> <span className="text-yellow-300">"kaf-extract"</span>{'\n\n'}
                  <span className="text-purple-400">const</span> client = <span className="text-purple-400">new</span> KafClient({'{'}{'\n'}
                  {'  '}apiKey: <span className="text-yellow-300">"your_key"</span>{'\n'}
                  {'}{'}');{'\n\n'}
                  <span className="text-purple-400">const</span> result = <span className="text-purple-400">await</span> client.extractAi({'{'}{'\n'}
                  {'  '}url: <span className="text-yellow-300">"https://example.com"</span>,{'\n'}
                  {'  '}prompt: <span className="text-yellow-300">"Extract all products"</span>{'\n'}
                  {'}{'}');
                </code></pre>
              </div>
            </div>
          </div>
        </section>

        {/* Rate Limits */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
            <span className="w-8 h-8 rounded-lg bg-orange-500/20 flex items-center justify-center text-orange-400 text-sm">⏱️</span>
            Rate Limits
          </h2>
          <div className="glass-card p-6">
            <div className="space-y-4">
              {[
                { plan: 'Free', limit: '10 req/min', extractions: '100/month' },
                { plan: 'Starter', limit: '60 req/min', extractions: '5,000/month' },
                { plan: 'Pro', limit: '300 req/min', extractions: '50,000/month' },
              ].map((item, i) => (
                <div key={i} className="flex items-center justify-between py-3 border-b border-[#1c1c2a] last:border-0">
                  <span className="font-semibold text-white">{item.plan}</span>
                  <div className="flex gap-8">
                    <span className="text-sm text-gray-400">{item.limit}</span>
                    <span className="text-sm text-gray-400">{item.extractions}</span>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-sm text-gray-500 mt-4">
              Rate limit headers are included in every response: <code className="text-[#00d4a0]">X-RateLimit-Remaining</code>, <code className="text-[#00d4a0]">X-RateLimit-Reset</code>
            </p>
          </div>
        </section>

        {/* Error Codes */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
            <span className="w-8 h-8 rounded-lg bg-red-500/20 flex items-center justify-center text-red-400 text-sm">⚠️</span>
            Error Codes
          </h2>
          <div className="glass-card p-6 overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#1c1c2a]">
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-300">Code</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-300">Name</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-300">Description</th>
                </tr>
              </thead>
              <tbody>
                {errorCodes.map((err, i) => (
                  <tr key={i} className="border-b border-[#1c1c2a] last:border-0">
                    <td className="py-3 px-4">
                      <code className={`text-sm font-bold ${
                        err.code < 500 ? 'text-yellow-400' : 'text-red-400'
                      }`}>
                        {err.code}
                      </code>
                    </td>
                    <td className="py-3 px-4 text-sm font-medium text-white">{err.name}</td>
                    <td className="py-3 px-4 text-sm text-gray-400">{err.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Back to home */}
        <div className="text-center">
          <Link to="/" className="btn-secondary">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            Back to Home
          </Link>
        </div>
      </div>
    </div>
  )
}
