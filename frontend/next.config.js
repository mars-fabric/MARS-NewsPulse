/** @type {import('next').NextConfig} */
const path = require('path');
const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Framing policy. X_FRAME_OPTIONS: SAMEORIGIN | DENY | "" (disables header).
// FRAME_ANCESTORS: CSP frame-ancestors value (e.g. "'self' https://mars.example.com").
// If FRAME_ANCESTORS is unset, it's derived from X_FRAME_OPTIONS.
const xFrameOptions = process.env.X_FRAME_OPTIONS ?? 'SAMEORIGIN';
const frameAncestors =
  process.env.FRAME_ANCESTORS ??
  (xFrameOptions === 'DENY' ? "'none'" : xFrameOptions === 'SAMEORIGIN' ? "'self'" : '');

const nextConfig = {
  // Disable strict mode to prevent double-render in dev (a common lag source)
  reactStrictMode: false,

  // Disable the "X-Powered-By" header
  poweredByHeader: false,

  // Allow external hosts in development
  allowedDevOrigins: ['100.88.49.58'],

  // Explicitly set turbopack root to avoid conflicts with multiple lockfiles
  turbopack: {
    root: path.resolve(__dirname),
  },

  async headers() {
    const framingHeaders = [];
    if (xFrameOptions) {
      framingHeaders.push({ key: 'X-Frame-Options', value: xFrameOptions });
    }
    if (frameAncestors) {
      framingHeaders.push({
        key: 'Content-Security-Policy',
        value: `frame-ancestors ${frameAncestors}`,
      });
    }
    return framingHeaders.length
      ? [{ source: '/(.*)', headers: framingHeaders }]
      : [];
  },

  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: '/ws/:path*',
        destination: `${backendUrl}/ws/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
