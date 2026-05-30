import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

export default function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  const isHome = location.pathname === '/'

  const navLinks = [
    { label: 'Features', href: isHome ? '#features' : '/#features' },
    { label: 'Pricing', href: isHome ? '#pricing' : '/#pricing' },
    { label: 'API Docs', href: '/api-reference' },
    { label: 'Tutorial', href: '/tutorial' },
  ]

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl bg-[#06060a]/80 border-b border-[#1c1c2a]">
      <div className="section-container">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-3 group">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#00d4a0] to-[#4494ff] flex items-center justify-center">
              <span className="text-[#06060a] font-bold text-sm">K</span>
            </div>
            <span className="font-bold text-white text-lg">
              Kaf <span className="text-[#00d4a0]">Extract</span>
            </span>
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-8">
            {navLinks.map((link) => (
              <Link
                key={link.label}
                to={link.href}
                className="text-sm text-gray-400 hover:text-white transition-colors duration-200"
              >
                {link.label}
              </Link>
            ))}
          </div>

          {/* CTA */}
          <div className="hidden md:flex items-center gap-4">
            <a
              href="/dashboard/login"
              className="text-sm text-gray-400 hover:text-white transition-colors"
            >
              Sign In
            </a>
            <a
              href="/dashboard/register"
              className="btn-primary text-sm !py-2 !px-5"
            >
              Get Started
            </a>
          </div>

          {/* Mobile toggle */}
          <button
            className="md:hidden text-gray-400 hover:text-white"
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {mobileOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div className="md:hidden py-4 border-t border-[#1c1c2a] animate-fade-in">
            {navLinks.map((link) => (
              <Link
                key={link.label}
                to={link.href}
                className="block py-3 text-gray-400 hover:text-white transition-colors"
                onClick={() => setMobileOpen(false)}
              >
                {link.label}
              </Link>
            ))}
            <div className="pt-4 flex flex-col gap-3">
              <a href="/dashboard/login" className="text-gray-400 hover:text-white">
                Sign In
              </a>
              <a href="/dashboard/register" className="btn-primary text-center">
                Get Started
              </a>
            </div>
          </div>
        )}
      </div>
    </nav>
  )
}
