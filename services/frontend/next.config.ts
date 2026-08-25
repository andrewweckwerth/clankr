import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  //output: 'standalone',  
  experimental: {
    // ⛔ Disable Lightning CSS
    optimizeCss: false,
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://orchestrator:8000/api/:path*',
      },
    ];
  },
};

export default nextConfig;
