import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

interface Plan {
  key: string
  name: string
  price_cents: number
  price_display: string
  billing_period: string
  extractions_per_month: number
  features: string[]
  highlight: boolean
}

interface Feature {
  key: string
  name: string
  description: string
  category: string
}

const featureIcons: Record<string, string> = {
  'AI Extraction': '🤖',
  'CSS Selectors': '🎯',
  'Smart Parsing': '🧠',
  'Auto Retry': '🔄',
  'Scheduling': '⏰',
  'Webhooks': '🔗',
  'Proxy Rotation': '🌐',
  'Rate Limiting': '⚡',
  'Data Export': '📤',
  'API Keys': '🔑',
  'Batch Processing': '📦',
  'Real-time': '⏱️',
  'Monitoring': '📊',
  'Templates': '📋',
  'History': '📜',
  'Team Access': '👥',
}

const defaultFeatures: Feature[] = [
  { key: 'ai', name: 'AI Extraction', description: 'Extract data using natural language descriptions. Our AI understands page structure automatically.', category: 'Core' },
  { key: 'css', name: 'CSS Selectors', description: 'Use familiar CSS selectors for precise data targeting. Full selector syntax supported.', category: 'Core' },
  { key: 'parsing', name: 'Smart Parsing', description: 'Automatic data type detection and formatting. Dates, numbers, and prices parsed correctly.', category: 'Core' },
  { key: 'retry', name: 'Auto Retry', description: 'Automatic retry with exponential backoff for failed requests. Never miss data due to transient errors.', category: 'Reliability' },
  { key: 'proxy', name: 'Proxy Rotation', description: 'Built-in proxy pool with automatic rotation. Avoid IP blocks and rate limits.', category: 'Reliability' },
  { key: 'schedule', name: 'Scheduling', description: 'Schedule extractions to run automatically. Monitor changes and get notified.', category: 'Automation' },
  { key: 'webhooks', name: 'Webhooks', description: 'Get real-time notifications when extractions complete. Integrate with your existing workflows.', category: 'Automation' },
  { key: 'batch', name: 'Batch Processing', description: 'Process thousands of URLs in a single request. Parallel execution for maximum speed.', category: 'Scale' },
  { key: 'export', name: 'Data Export', description: 'Export data in JSON, CSV, or integrate directly with your database via webhooks.', category: 'Integration' },
]

const defaultPlans: Plan[] = [
  { key: 'hobby', name: 'Hobby', price_cents: 0, price_display: 'Free', billing_period: 'month', extractions_per_month: 1000, features: ['1,000 extractions/month', 'CSS selectors', 'JSON export', 'Community support'], highlight: false },
  { key: 'pro', name: 'Pro', price_cents: 2900, price_display: '$29', billing_period: 'month', extractions_per_month: 50000, features: ['50,000 extractions/month', 'AI-powered extraction', 'Batch processing', 'Priority support', 'Export formats'], highlight: true },
  { key: 'enterprise', name: 'Enterprise', price_cents: 19900, price_display: '$199', billing_period: 'month', extractions_per_month: 500000, features: ['500,000 extractions/month', 'Everything in Pro', 'Custom integrations', 'Dedicated support', 'SLA guarantee', 'SSO'], highlight: false },
]

export default function LandingPage() {
  const [plans, setPlans] = useState<Plan[]>(defaultPlans)
  const [features, setFeatures] = useState<Feature[]>(defaultFeatures)

  useEffect(() => {
    fetch('/api/v1/public/plans')
      .then(r => r.ok ? r.json() : defaultPlans)
      .then(data => { if (Array.isArray(data) && data.length > 0) setPlans(data) })
      .catch(() => {})

    fetch('/api/v1/public/features')
      .then(r => r.ok ? r.json() : defaultFeatures)
      .then(data => { if (Array.isArray(data) && data.length > 0) setFeatures(data) })
      .catch(() => {})
  }, [])

  // Group features by category
  const grouped = features.reduce<Record<string, Feature[]>>((acc, f) => {
    const cat = f.category || 'Other'
    if (!acc[cat]) acc[cat] = []
    acc[cat].push(f)
    return acc
  }, {})

  return (
    <>
      {/* Hero */}
      <section className="pt-40 pb-28 relative overflow-hidden">
        <div className="section-container text-center">
          <div className="animate-fade-in-up stagger-1 mb-6">
            <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[#00d4a0]/30 bg-[#00d4a0]/10 text-[#00d4a0] text-sm font-medium">
              <span className="w-2 h-2 rounded-full bg-[#00d4a0] animate-pulse" />
              Live — Extracting data from 10,000+ sites
            </span>
          </div>

          <h1 className="animate-fade-in-up stagger-2 text-4xl md:text-6xl lg:text-7xl font-bold tracking-tight leading-tight mb-6">
            Turn Any Website Into
            <br />
            <span className="gradient-text">Structured Data</span>
          </h1>

          <p className="animate-fade-in-up stagger-3 text-lg md:text-xl text-gray-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            One API call. No brittle selectors. Extract clean, structured data from any website
            using AI-powered extraction that adapts when pages change.
          </p>

          <div className="animate-fade-in-up stagger-4 flex flex-col sm:flex-row gap-4 justify-center">
            <a href="/dashboard/register" className="btn-primary text-base">
              Get Started Free
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
            </a>
            <Link to="/api-reference" className="btn-secondary text-base">
              View API Docs
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
            </Link>
          </div>

          {/* Code preview */}
          <div className="animate-fade-in-up stagger-5 mt-16 max-w-3xl mx-auto">
            <div className="code-block text-left">
              <div className="flex items-center gap-2 mb-4 pb-3 border-b border-[#1c1c2a]">
                <div className="w-3 h-3 rounded-full bg-red-500/60" />
                <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
                <div className="w-3 h-3 rounded-full bg-green-500/60" />
                <span className="ml-2 text-xs text-gray-500">extract.sh</span>
              </div>
              <pre className="text-sm leading-relaxed overflow-x-auto">
                <code>
                  <span className="text-gray-500">$ </span>
                  <span className="text-[#00d4a0]">curl</span>
                  <span className="text-white"> -X POST </span>
                  <span className="text-[#4494ff]">https://extract.kafcenter.com/v1/extract/ai</span>
                  <span className="text-white"> \</span>{'\n'}
                  <span className="text-white">  -H </span>
                  <span className="text-yellow-300">"Authorization: Bearer YOUR_API_KEY"</span>
                  <span className="text-white"> \</span>{'\n'}
                  <span className="text-white">  -H </span>
                  <span className="text-yellow-300">"Content-Type: application/json"</span>
                  <span className="text-white"> \</span>{'\n'}
                  <span className="text-white">  -d </span>
                  <span className="text-yellow-300">{'\'{"url":"https://example.com","prompt":"Extract all product names and prices"}\''}</span>
                </code>
              </pre>
            </div>
          </div>
        </div>
      </section>

      {/* Social Proof */}
      <section className="py-16 border-y border-[#1c1c2a]">
        <div className="section-container">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            {[
              { value: '64+', label: 'Active Users' },
              { value: '99.9%', label: 'Uptime' },
              { value: '<2s', label: 'Avg Response' },
              { value: '1M+', label: 'Extractions' },
            ].map((stat, i) => (
              <div key={i} className={`animate-fade-in-up stagger-${i + 1}`}>
                <div className="text-3xl md:text-4xl font-bold gradient-text mb-2">{stat.value}</div>
                <div className="text-sm text-gray-500">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Problem */}
      <section className="py-32">
        <div className="section-container">
          <div className="text-center mb-20">
            <h2 className="text-3xl md:text-4xl font-bold mb-5">
              Web Scraping Is <span className="text-red-400">Broken</span>
            </h2>
            <p className="text-gray-400 max-w-xl mx-auto">
              Traditional scrapers fail constantly, require constant maintenance, and produce inconsistent data.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-10">
            {[
              {
                icon: '💔',
                title: 'Scrapers Break',
                desc: 'CSS selectors break every time a site updates. You spend more time fixing scrapers than using the data.',
              },
              {
                icon: '⏳',
                title: 'Weeks of Dev Time',
                desc: 'Building reliable scrapers takes weeks. Proxy rotation, retry logic, parsing — it all adds up.',
              },
              {
                icon: '📉',
                title: 'Data Quality Drifts',
                desc: 'Inconsistent formatting, missing fields, and parsing errors make your data unreliable.',
              },
            ].map((item, i) => (
              <div key={i} className="glass-card p-8">
                <div className="text-4xl mb-4">{item.icon}</div>
                <h3 className="text-xl font-semibold text-white mb-3">{item.title}</h3>
                <p className="text-gray-400 leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-32 bg-[#0a0a12]/50">
        <div className="section-container">
          <div className="text-center mb-20">
            <h2 className="text-3xl md:text-4xl font-bold mb-5">
              How It <span className="gradient-text">Works</span>
            </h2>
            <p className="text-gray-400 max-w-xl mx-auto">
              Three simple steps to structured data. No selectors, no parsing, no maintenance.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-10">
            {[
              {
                step: '01',
                title: 'Describe',
                desc: 'Tell our AI what data you want using natural language. "Extract all product names and prices" is all you need.',
                color: '#00d4a0',
              },
              {
                step: '02',
                title: 'Extract',
                desc: 'Our system navigates the page, handles JavaScript rendering, and intelligently extracts the data you requested.',
                color: '#4494ff',
              },
              {
                step: '03',
                title: 'Receive JSON',
                desc: 'Get clean, structured JSON data ready to use. Consistent formatting, typed fields, and validated output.',
                color: '#a855f7',
              },
            ].map((item, i) => (
              <div key={i} className="relative">
                <div className="glass-card p-8 text-center">
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center text-xl font-bold mb-4 mx-auto"
                    style={{ background: `${item.color}20`, color: item.color }}
                  >
                    {item.step}
                  </div>
                  <h3 className="text-xl font-semibold text-white mb-3">{item.title}</h3>
                  <p className="text-gray-400 leading-relaxed">{item.desc}</p>
                </div>
                {i < 2 && (
                  <div className="hidden md:block absolute top-1/2 -right-4 w-8 h-0.5 bg-gradient-to-r from-[#1c1c2a] to-transparent" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Live Demo */}
      <section className="py-32">
        <div className="section-container">
          <div className="text-center mb-20">
            <h2 className="text-3xl md:text-4xl font-bold mb-5">
              See It In <span className="gradient-text">Action</span>
            </h2>
            <p className="text-gray-400 max-w-xl mx-auto">
              One API call returns clean, structured data from any website.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8 max-w-5xl mx-auto">
            {/* Request */}
            <div className="code-block text-left">
              <div className="flex items-center gap-2 mb-4 pb-3 border-b border-[#1c1c2a]">
                <div className="w-3 h-3 rounded-full bg-[#00d4a0]/60" />
                <span className="text-xs text-gray-500">Request</span>
              </div>
              <pre className="text-sm leading-relaxed overflow-x-auto">
                <code>
                  <span className="text-purple-400">POST</span>
                  <span className="text-white"> /v1/extract/ai</span>{'\n\n'}
                  <span className="text-gray-500">{'{'}</span>{'\n'}
                  <span className="text-[#4494ff]">  "url"</span>
                  <span className="text-white">: </span>
                  <span className="text-yellow-300">"https://news.ycombinator.com"</span>
                  <span className="text-white">,</span>{'\n'}
                  <span className="text-[#4494ff]">  "prompt"</span>
                  <span className="text-white">: </span>
                  <span className="text-yellow-300">"top 5 stories with titles and URLs"</span>{'\n'}
                  <span className="text-gray-500">{'}'}</span>
                </code>
              </pre>
            </div>

            {/* Response */}
            <div className="code-block text-left">
              <div className="flex items-center gap-2 mb-4 pb-3 border-b border-[#1c1c2a]">
                <div className="w-3 h-3 rounded-full bg-green-500/60" />
                <span className="text-xs text-gray-500">Response</span>
              </div>
              <pre className="text-sm leading-relaxed overflow-x-auto">
                <code>
                  <span className="text-gray-500">{'{'}</span>{'\n'}
                  <span className="text-[#4494ff]">  "data"</span>
                  <span className="text-white">: [</span>{'\n'}
                  <span className="text-white">    {'{'}</span>{'\n'}
                  <span className="text-[#4494ff]">      "title"</span>
                  <span className="text-white">: </span>
                  <span className="text-yellow-300">"Show HN: ..."</span>
                  <span className="text-white">,</span>{'\n'}
                  <span className="text-[#4494ff]">      "url"</span>
                  <span className="text-white">: </span>
                  <span className="text-yellow-300">"https://..."</span>{'\n'}
                  <span className="text-white">    {'}'}</span>{'\n'}
                  <span className="text-white">  ],</span>{'\n'}
                  <span className="text-[#4494ff]">  "status"</span>
                  <span className="text-white">: </span>
                  <span className="text-[#00d4a0]">"success"</span>{'\n'}
                  <span className="text-gray-500">{'}'}</span>
                </code>
              </pre>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-32 bg-[#0a0a12]/50">
        <div className="section-container">
          <div className="text-center mb-20">
            <h2 className="text-3xl md:text-4xl font-bold mb-5">
              Everything You <span className="gradient-text">Need</span>
            </h2>
            <p className="text-gray-400 max-w-xl mx-auto text-lg">
              From a single URL to millions — extract, automate, and integrate web data your way.
            </p>
          </div>

          {/* Benefit-oriented feature groups */}
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-10">
            {[
              {
                icon: '🧠',
                title: 'AI-Powered Extraction',
                desc: 'Just describe what you want in plain English. Our AI understands page structure, navigates dynamic content, and returns clean structured data — no selectors needed.',
                tag: 'Most Popular',
              },
              {
                icon: '🎯',
                title: 'CSS Selector Precision',
                desc: 'For developers who want full control. Target exact elements with familiar CSS syntax. Extract text, attributes, HTML, and more with pixel-perfect accuracy.',
                tag: null,
              },
              {
                icon: '⚡',
                title: 'Batch Processing',
                desc: 'Process up to 50 URLs in a single API call. Parallel execution delivers results in seconds, not minutes. Perfect for large-scale data collection.',
                tag: 'Pro & Enterprise',
              },
              {
                icon: '⏰',
                title: 'Scheduled Monitoring',
                desc: 'Set it and forget it. Schedule extractions to run hourly, daily, or weekly. Get notified when data changes. Track competitors automatically.',
                tag: null,
              },
              {
                icon: '🔗',
                title: 'Webhook Integrations',
                desc: 'Get instant notifications when extractions complete. HMAC-SHA256 signed payloads. Integrate with Slack, Teams, Zapier, or your own pipeline.',
                tag: null,
              },
              {
                icon: '📊',
                title: 'Usage Dashboard',
                desc: 'Real-time visibility into your extraction activity. Track usage against your plan limits, view history, and export data — all from one clean dashboard.',
                tag: null,
              },
              {
                icon: '🐍',
                title: 'SDKs & API Access',
                desc: 'Full REST API with 43+ endpoints. Official Python and JavaScript SDKs. Interactive API docs with try-it-out. Get started in under 5 minutes.',
                tag: null,
              },
              {
                icon: '🔐',
                title: 'Enterprise Security',
                desc: 'Two-factor authentication, API key management, role-based team access, and SOC-2 compliant infrastructure. Your data stays yours.',
                tag: null,
              },
              {
                icon: '🚀',
                title: '99.9% Uptime SLA',
                desc: 'Built on enterprise-grade infrastructure with automatic failover. Sub-2-second average response times. We handle the hard parts so you can focus on your data.',
                tag: null,
              },
            ].map((feature, i) => (
              <div key={i} className="glass-card p-8 group relative overflow-hidden">
                {feature.tag && (
                  <span className="absolute top-4 right-4 text-[10px] font-bold uppercase tracking-wider text-[#00d4a0] bg-[#00d4a0]/10 px-2 py-0.5 rounded-full">
                    {feature.tag}
                  </span>
                )}
                <div className="text-3xl mb-4">{feature.icon}</div>
                <h3 className="text-lg font-semibold text-white mb-3">{feature.title}</h3>
                <p className="text-gray-400 leading-relaxed text-sm">{feature.desc}</p>
              </div>
            ))}
          </div>

          {/* Dynamic features from API — supplementary */}
          {Object.keys(grouped).length > 0 && (
            <div className="mt-20 text-center">
              <p className="text-sm text-gray-500 mb-6">
                {features.length} feature flags available • Fully configurable per plan
              </p>
              <div className="flex flex-wrap justify-center gap-3 max-w-3xl mx-auto">
                {features.slice(0, 12).map((f) => (
                  <span key={f.key} className="text-xs px-3 py-1.5 rounded-full border border-[#1c1c2a] text-gray-500 hover:text-[#00d4a0] hover:border-[#00d4a0]/30 transition-colors cursor-default">
                    {f.name}
                  </span>
                ))}
                {features.length > 12 && (
                  <span className="text-xs px-3 py-1.5 rounded-full border border-[#1c1c2a] text-gray-600">
                    +{features.length - 12} more
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Use Cases */}
      <section className="py-32">
        <div className="section-container">
          <div className="text-center mb-20">
            <h2 className="text-3xl md:text-4xl font-bold mb-5">
              Built For <span className="gradient-text">Every Use Case</span>
            </h2>
            <p className="text-gray-400 max-w-xl mx-auto">
              From price monitoring to content aggregation, Kaf Extract handles it all.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-10">
            {[
              { icon: '💰', title: 'Price Monitoring', desc: 'Track competitor pricing across thousands of products. Get alerts when prices change.' },
              { icon: '📰', title: 'Content Aggregation', desc: 'Aggregate news, articles, and content from multiple sources into a single feed.' },
              { icon: '🏠', title: 'Real Estate', desc: 'Extract property listings, prices, and details from real estate platforms.' },
              { icon: '💼', title: 'Job Boards', desc: 'Monitor job postings across multiple platforms. Track salary trends and requirements.' },
              { icon: '📊', title: 'Financial Data', desc: 'Extract market data, stock prices, and financial reports from public sources.' },
              { icon: '🔍', title: 'SEO Monitoring', desc: 'Track SERP rankings, meta descriptions, and on-page SEO elements at scale.' },
            ].map((item, i) => (
              <div key={i} className="glass-card p-6 group hover:border-[#00d4a0]/30">
                <div className="text-3xl mb-4">{item.icon}</div>
                <h3 className="text-lg font-semibold text-white mb-2">{item.title}</h3>
                <p className="text-sm text-gray-400 leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-32 bg-[#0a0a12]/50">
        <div className="section-container">
          <div className="text-center mb-20">
            <h2 className="text-3xl md:text-4xl font-bold mb-5">
              Simple, <span className="gradient-text">Transparent</span> Pricing
            </h2>
            <p className="text-gray-400 max-w-xl mx-auto">
              Start free. Scale as you grow. No hidden fees.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {plans.map((plan) => (
              <div
                key={plan.key}
                className={`glass-card p-8 relative ${
                  plan.highlight ? 'border-[#00d4a0]/50 animate-pulse-glow' : ''
                }`}
              >
                {plan.highlight && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="bg-[#00d4a0] text-[#06060a] text-xs font-bold px-4 py-1 rounded-full">
                      POPULAR
                    </span>
                  </div>
                )}
                <h3 className="text-xl font-semibold text-white mb-2">{plan.name}</h3>
                <div className="mb-4">
                  <span className="text-4xl font-bold text-white">{plan.price_display}</span>
                  <span className="text-gray-500">/{plan.billing_period}</span>
                </div>
                <p className="text-sm text-gray-400 mb-6">
                  {plan.extractions_per_month.toLocaleString()} extractions/month
                </p>
                <ul className="space-y-3 mb-8">
                  {plan.features.map((f, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm text-gray-300">
                      <svg className="w-4 h-4 text-[#00d4a0] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      {f}
                    </li>
                  ))}
                </ul>
                <a
                  href="/dashboard/register"
                  className={plan.highlight ? 'btn-primary w-full justify-center' : 'btn-secondary w-full justify-center'}
                >
                  Get Started
                </a>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-32">
        <div className="section-container text-center">
          <div className="glass-card p-20 max-w-3xl mx-auto relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-[#00d4a0]/10 to-[#4494ff]/10" />
            <div className="relative">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Ready to Start <span className="gradient-text">Extracting</span>?
              </h2>
              <p className="text-gray-400 max-w-lg mx-auto mb-8">
                Join 64+ developers who trust Kaf Extract for their web data needs. 
                Start with 100 free extractions — no credit card required.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <a href="/dashboard/register" className="btn-primary text-base">
                  Start Free Trial
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
                </a>
                <Link to="/tutorial" className="btn-secondary text-base">
                  View Tutorial
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  )
}
