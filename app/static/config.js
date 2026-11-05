// RetailDesk frontend configuration.
//
// API_BASE = the base URL of the FastAPI backend, WITHOUT a trailing slash.
//
//  * Leave it as "" (empty) when this UI is served BY FastAPI itself
//    (local run, Docker, or a single Render service) — calls stay same-origin.
//  * When this UI is hosted separately on Vercel, set it to your backend URL,
//    e.g.  window.API_BASE = "https://retaildesk-api.onrender.com";
//
// This is the ONLY value you need to change for a split Vercel + Render setup.
window.API_BASE = "";
