import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ARMS AI + MEDAR",
    short_name: "ARMS + MEDAR",
    description: "AI-assisted decision support with explicit data and safety boundaries.",
    start_url: "/product",
    scope: "/",
    display: "standalone",
    background_color: "#0a1424",
    theme_color: "#0a1424",
    icons: [
      { src: "/favicon.ico", sizes: "any", type: "image/x-icon" },
    ],
  };
}