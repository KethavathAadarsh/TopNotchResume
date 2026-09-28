// GITHUB_PAGES=true (set by the Pages workflow) builds a static export served
// from https://<user>.github.io/<repo>/ — otherwise a standalone server for Docker.
const isPages = process.env.GITHUB_PAGES === "true";
const basePath = isPages ? process.env.NEXT_BASE_PATH || "" : "";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: isPages ? "export" : "standalone",
  basePath,
  trailingSlash: isPages,
  images: { unoptimized: isPages },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
};

export default nextConfig;
