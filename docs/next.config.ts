import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  basePath: "/policyengine-api-v2-alpha",
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
