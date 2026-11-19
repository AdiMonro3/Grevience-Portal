import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";

// Google Identity Services: Google shows its own button and popup, then hands us a
// signed ID token ("credential"). The API verifies it at POST /auth/google.
const GSI_SRC = "https://accounts.google.com/gsi/client";

let clientIdPromise = null;
/** The API decides whether Google sign-in is on (GOOGLE_CLIENT_ID in backend/.env). */
function getGoogleClientId() {
  clientIdPromise ??= api
    .get("/auth/providers")
    .then((res) => res.data.google_client_id || null)
    .catch(() => {
      clientIdPromise = null; // API unreachable: ask again next time
      return null;
    });
  return clientIdPromise;
}

let scriptPromise = null;
function loadGoogleScript() {
  if (window.google?.accounts?.id) return Promise.resolve();
  scriptPromise ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = GSI_SRC;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      script.remove();
      scriptPromise = null;
      reject(new Error("Could not load Google sign-in"));
    };
    document.head.appendChild(script);
  });
  return scriptPromise;
}

// initialize() should run once per page load, so its callback forwards the
// credential to whichever button is mounted right now.
let initializedFor = null;
let activeHandler = null;
function initGoogle(clientId) {
  if (initializedFor === clientId) return;
  window.google.accounts.id.initialize({
    client_id: clientId,
    callback: (response) => activeHandler?.(response.credential),
  });
  initializedFor = clientId;
}

/**
 * "Sign in with Google" button followed by an "or" divider.
 * Renders nothing when the API has no Google client ID configured.
 * `text`: "signin_with" | "signup_with" | "continue_with".
 */
export default function GoogleButton({ text = "signin_with", onCredential }) {
  const containerRef = useRef(null);
  const handlerRef = useRef(onCredential);
  const [state, setState] = useState("loading"); // loading | ready | off | failed | blocked

  useEffect(() => {
    handlerRef.current = onCredential;
  }, [onCredential]);

  useEffect(() => {
    let cancelled = false;
    let checkTimer;
    const handler = (credential) => handlerRef.current?.(credential);

    (async () => {
      const clientId = await getGoogleClientId();
      if (cancelled) return;
      if (!clientId) {
        setState("off");
        return;
      }
      try {
        await loadGoogleScript();
      } catch {
        if (!cancelled) setState("failed");
        return;
      }
      if (cancelled || !containerRef.current) return;
      initGoogle(clientId);
      activeHandler = handler;
      window.google.accounts.id.renderButton(containerRef.current, {
        theme: "outline",
        size: "large",
        shape: "rectangular",
        text,
        logo_alignment: "center",
        width: Math.min(400, containerRef.current.offsetWidth), // Google allows 200-400 px
      });
      setState("ready");

      // Google leaves its button at 0x0 when the client ID is wrong or this web
      // address is not in the client's "Authorized JavaScript origins".
      checkTimer = setTimeout(() => {
        const frame = containerRef.current?.querySelector("iframe");
        if (cancelled || !frame || frame.offsetHeight > 0) return;
        console.warn(
          `Google sign-in button did not load. Check GOOGLE_CLIENT_ID and add ${window.location.origin} ` +
            "to the OAuth client's Authorized JavaScript origins.",
        );
        setState("blocked");
      }, 6000);
    })();

    return () => {
      cancelled = true;
      clearTimeout(checkTimer);
      if (activeHandler === handler) activeHandler = null;
    };
  }, [text]);

  if (state === "off") return null;
  if (state === "failed" || state === "blocked") {
    return (
      <p className="rounded-lg bg-slate-50 px-3 py-2 text-center text-xs text-slate-500">
        {state === "failed"
          ? "Google sign-in could not load (no internet?)."
          : "Google sign-in is not set up for this web address."}{" "}
        Use your email and password instead.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      <div ref={containerRef} className="flex min-h-10 justify-center" />
      <div className="flex items-center gap-3 text-xs text-slate-400">
        <span className="h-px flex-1 bg-slate-200" />
        or
        <span className="h-px flex-1 bg-slate-200" />
      </div>
    </div>
  );
}
