import type { NextConfig } from "next";

if (process.env.NODE_ENV === "production" && !process.env.NEXT_PUBLIC_API_BASE) {
  throw new Error("NEXT_PUBLIC_API_BASE is required for production builds");
}

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
