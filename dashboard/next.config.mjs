/** @type {import('next').NextConfig} */
const nextConfig = {
  // The dashboard reads generated JSON from disk at build time.
  // No database, no API layer, no client-side fetching.
  output: 'export',
  outputFileTracingRoot: process.cwd(),
};
export default nextConfig;
