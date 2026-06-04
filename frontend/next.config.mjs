/** @type {import('next').NextConfig} */
const nextConfig = {
  // Do not 308-strip trailing slashes before applying rewrites. Without this,
  // `/api/knowledge/` is redirected to `/api/knowledge`, then proxied to the
  // backend without a slash, which FastAPI 307-redirects to an absolute
  // cross-origin URL (`http://host:8000/knowledge/`) — triggering a CORS
  // failure in the browser. Keeping the slash lets the proxy pass straight through.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
