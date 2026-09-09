import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "OAK Gatekeeper",
    short_name: "OAK Gatekeeper",
    description: "OAK Gatekeeper Orbit 3D trading command system.",
    start_url: "/engine",
    display: "standalone",
    background_color: "#07110F",
    theme_color: "#07110F",
    icons: [
      {
        src: "/oak-app-icon-192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/oak-app-icon-512.png",
        sizes: "512x512",
        type: "image/png",
      },
      {
        src: "/oak-app-icon.png",
        sizes: "1024x1024",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
