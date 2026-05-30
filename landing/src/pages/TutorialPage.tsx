import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

interface Step {
  title: string
  subtitle: string
  description: string
  code: string
  codeLabel: string
  tip?: string
}

const steps: Step[] = [
  {
    title: 'Sign Up',
    subtitle: 'Create your free account',
    description: 'Head to the Kaf Extract dashboard and create a free account. No credit card required — you get 100 extractions per month on the free plan.',
    code: `# Visit the registration page
open https://extract.kafcenter.com/dashboard/register

# Fill in:
#   - Email address
#   - Password (min 8 characters)
#   - Company name (optional)

# You'll receive a verification email.
# Click the link to activate your account.`,
    codeLabel: 'Registration',
    tip: 'You can also sign up using GitHub OAuth for faster onboarding.',
  },
  {
    title: 'Get API Key',
    subtitle: 'Generate your authentication key',
    description: 'Once logged in, navigate to Settings → API Keys and create a new key. Store it securely — you won\'t be able to see it again.',
    code: `# Navigate to: Dashboard → Settings → API Keys
# Click "Create New Key"
# Name: "My First Key"
# Permissions: "Read & Extract"

# Your key will look like:
# kaf_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6

# Store it as an environment variable:
export KAF_API_KEY="kaf_a1b2c3d4e5f6..."

# Verify it works:
curl -H "Authorization: Bearer $KAF_API_KEY" \\
     https://api.kafcenter.com/v1/keys`,
    codeLabel: 'API Key Setup',
    tip: 'Create separate keys for development and production. You can revoke keys at any time.',
  },
  {
    title: 'First Extraction',
    subtitle: 'Extract data with CSS selectors',
    description: 'The simplest way to extract data is with CSS selectors. Define what data you want by targeting HTML elements on the page.',
    code: `curl -X POST https://api.kafcenter.com/v1/extract \\
  -H "Authorization: Bearer $KAF_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "url": "https://news.ycombinator.com",
    "selectors": {
      "title": ".titleline > a",
      "score": ".score",
      "author": ".hnuser"
    }
  }'

# Response:
# {
#   "status": "success",
#   "data": [
#     {"title": "Show HN: ...", "score": "42 points", "author": "pg"}
#   ],
#   "count": 30
# }`,
    codeLabel: 'CSS Extraction',
    tip: 'Use the browser DevTools (F12) to find the right CSS selectors for your target elements.',
  },
  {
    title: 'AI vs Schema',
    subtitle: 'Choose the right extraction method',
    description: 'Kaf Extract offers two methods: CSS selectors for precise targeting, and AI extraction for natural language descriptions. Use AI when you don\'t know the page structure.',
    code: `# CSS Extraction — precise, fast, deterministic
curl -X POST https://api.kafcenter.com/v1/extract \\
  -H "Authorization: Bearer $KAF_API_KEY" \\
  -d '{
    "url": "https://example.com/products",
    "selectors": {
      "name": ".product-title",
      "price": ".price-value"
    }
  }'

# AI Extraction — flexible, adaptive, natural language
curl -X POST https://api.kafcenter.com/v1/extract/ai \\
  -H "Authorization: Bearer $KAF_API_KEY" \\
  -d '{
    "url": "https://example.com/products",
    "prompt": "Extract product names and prices as JSON",
    "format": "json"
  }'`,
    codeLabel: 'Two Methods Compared',
    tip: 'AI extraction is great for prototyping. Switch to CSS selectors in production for speed and reliability.',
  },
  {
    title: 'Export Data',
    subtitle: 'Get your data in the format you need',
    description: 'Extractions return JSON by default, but you can request CSV export or set up webhooks to push data to your systems automatically.',
    code: `# JSON (default) — great for APIs and databases
# Response: {"data": [...], "status": "success"}

# CSV export — add format parameter
curl -X POST https://api.kafcenter.com/v1/extract \\
  -H "Authorization: Bearer $KAF_API_KEY" \\
  -d '{
    "url": "https://example.com",
    "selectors": {"name": ".name", "price": ".price"},
    "format": "csv"
  }'

# Webhook — push results to your server
# Set webhook_url to receive POST callbacks
# when extractions complete.`,
    codeLabel: 'Export Options',
    tip: 'Webhooks are great for long-running extractions. You\'ll get a POST to your URL when the data is ready.',
  },
  {
    title: 'Advanced Features',
    subtitle: 'Schedules, batches, and more',
    description: 'Once you\'re comfortable with basic extractions, explore scheduling for recurring data collection, batch processing for multiple URLs, and proxy rotation for difficult sites.',
    code: `# Schedule — run extraction daily at 9 AM
curl -X POST https://api.kafcenter.com/v1/schedules \\
  -H "Authorization: Bearer $KAF_API_KEY" \\
  -d '{
    "name": "Daily Price Check",
    "url": "https://example.com/pricing",
    "type": "ai",
    "prompt": "Extract all product prices",
    "cron": "0 9 * * *"
  }'

# Batch — extract from multiple URLs
curl -X POST https://api.kafcenter.com/v1/extract/batch \\
  -H "Authorization: Bearer $KAF_API_KEY" \\
  -d '{
    "urls": ["https://site1.com", "https://site2.com"],
    "prompt": "Extract main heading"
  }'`,
    codeLabel: 'Advanced Usage',
    tip: 'Schedules are counted against your monthly extraction limit. Plan accordingly on higher-volume schedules.',
  },
]

export default function TutorialPage() {
  const [currentStep, setCurrentStep] = useState(0)
  const [typingComplete, setTypingComplete] = useState(false)

  useEffect(() => {
    setTypingComplete(false)
    const timer = setTimeout(() => setTypingComplete(true), 2500)
    return () => clearTimeout(timer)
  }, [currentStep])

  const progress = ((currentStep + 1) / steps.length) * 100

  return (
    <div className="pt-24 pb-20">
      <div className="section-container max-w-5xl">
        {/* Header */}
        <div className="mb-8">
          <Link to="/" className="text-sm text-gray-500 hover:text-white transition-colors mb-4 inline-flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            Back to Home
          </Link>
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            Getting <span className="gradient-text">Started</span>
          </h1>
          <p className="text-gray-400 text-lg max-w-2xl">
            Follow this step-by-step guide to go from zero to extracting structured data in minutes.
          </p>
        </div>

        {/* Progress bar */}
        <div className="mb-10">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-gray-500">
              Step {currentStep + 1} of {steps.length}
            </span>
            <span className="text-sm text-[#00d4a0]">{Math.round(progress)}% complete</span>
          </div>
          <div className="h-1.5 bg-[#0f0f18] rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-[#00d4a0] to-[#4494ff] rounded-full progress-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Step indicators */}
        <div className="flex flex-wrap gap-2 mb-10">
          {steps.map((step, i) => (
            <button
              key={i}
              onClick={() => setCurrentStep(i)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all ${
                i === currentStep
                  ? 'bg-[#00d4a0]/20 text-[#00d4a0] border border-[#00d4a0]/30'
                  : i < currentStep
                  ? 'bg-[#0f0f18] text-gray-400 border border-[#1c1c2a]'
                  : 'bg-[#0f0f18] text-gray-600 border border-[#1c1c2a]'
              }`}
            >
              <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
                i < currentStep
                  ? 'bg-[#00d4a0] text-[#06060a]'
                  : i === currentStep
                  ? 'bg-[#00d4a0]/20 text-[#00d4a0] border border-[#00d4a0]'
                  : 'bg-[#1c1c2a] text-gray-600'
              }`}>
                {i < currentStep ? '✓' : i + 1}
              </span>
              <span className="hidden sm:inline">{step.title}</span>
            </button>
          ))}
        </div>

        {/* Step content */}
        <div className="step-content" key={currentStep}>
          <div className="glass-card p-8 mb-6">
            <div className="mb-6">
              <span className="text-sm text-[#00d4a0] font-mono mb-1 block">{steps[currentStep].subtitle}</span>
              <h2 className="text-2xl md:text-3xl font-bold text-white">{steps[currentStep].title}</h2>
            </div>

            <p className="text-gray-400 leading-relaxed mb-6 text-lg">
              {steps[currentStep].description}
            </p>

            {/* Code block with typing animation */}
            <div className="code-block text-left relative overflow-hidden">
              <div className="flex items-center gap-2 mb-4 pb-3 border-b border-[#1c1c2a]">
                <div className="w-3 h-3 rounded-full bg-red-500/60" />
                <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
                <div className="w-3 h-3 rounded-full bg-green-500/60" />
                <span className="ml-2 text-xs text-gray-500">{steps[currentStep].codeLabel}</span>
              </div>
              <pre className="text-sm leading-relaxed overflow-x-auto">
                <code>
                  <span className={typingComplete ? '' : 'typing-animation'} style={{ display: 'inline-block' }}>
                    {steps[currentStep].code}
                  </span>
                </code>
              </pre>
            </div>

            {/* Tip */}
            {steps[currentStep].tip && (
              <div className="mt-6 flex gap-3 p-4 rounded-lg bg-[#4494ff]/10 border border-[#4494ff]/20">
                <span className="text-[#4494ff] text-lg">💡</span>
                <p className="text-sm text-gray-300 leading-relaxed">{steps[currentStep].tip}</p>
              </div>
            )}
          </div>
        </div>

        {/* Navigation */}
        <div className="flex justify-between items-center">
          <button
            onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
            disabled={currentStep === 0}
            className={`btn-secondary ${currentStep === 0 ? 'opacity-40 cursor-not-allowed' : ''}`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            Previous
          </button>

          {currentStep < steps.length - 1 ? (
            <button
              onClick={() => setCurrentStep(currentStep + 1)}
              className="btn-primary"
            >
              Next Step
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
            </button>
          ) : (
            <a href="/dashboard/register" className="btn-primary">
              Start Extracting
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
            </a>
          )}
        </div>

        {/* Quick links */}
        <div className="mt-16 grid md:grid-cols-2 gap-6">
          <Link to="/api-reference" className="glass-card p-6 group">
            <h3 className="font-semibold text-white mb-2 group-hover:text-[#00d4a0] transition-colors">
              📖 Full API Reference
            </h3>
            <p className="text-sm text-gray-400">
              Detailed documentation for every endpoint, parameter, and response format.
            </p>
          </Link>
          <a href="/dashboard/register" className="glass-card p-6 group">
            <h3 className="font-semibold text-white mb-2 group-hover:text-[#00d4a0] transition-colors">
              🚀 Create Free Account
            </h3>
            <p className="text-sm text-gray-400">
              Ready to start? Sign up for free and get 100 extractions per month.
            </p>
          </a>
        </div>
      </div>
    </div>
  )
}
