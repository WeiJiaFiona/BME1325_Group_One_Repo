/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Optimize build performance
  typescript: {
    // Type checking is done separately, skip during build for faster deployments
    ignoreBuildErrors: false,
  },
  eslint: {
    // Skip ESLint during build to speed up deployment
    // ESLint can be run separately with `npm run lint`
    ignoreDuringBuilds: true,
  },
  // Optimize output
  swcMinify: true,
}

module.exports = nextConfig

