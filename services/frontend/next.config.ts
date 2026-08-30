import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  //output: 'standalone',  
  // Audio uploads pass through the Next.js proxy before reaching the orchestrator.
  experimental: {
    // ⛔ Disable Lightning CSS
    optimizeCss: false,
    proxyClientMaxBodySize: '100mb',
  },
};

export default nextConfig;
