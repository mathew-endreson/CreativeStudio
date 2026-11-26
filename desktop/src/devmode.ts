import { useEffect, useState } from "react";

/** Developer mode: technical details (file locations, the raw environment check) are shown only when it is on.
 *  A per-viewer preference, kept in this browser. */
const KEY = "devmode";

export function isDevMode(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function useDevMode(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(isDevMode);
  useEffect(() => {
    const sync = () => setOn(isDevMode());
    window.addEventListener("devmode", sync);
    return () => window.removeEventListener("devmode", sync);
  }, []);
  const set = (v: boolean) => {
    try {
      localStorage.setItem(KEY, v ? "1" : "0");
    } catch {
      /* private mode: the choice lasts for this session only */
    }
    setOn(v);
    window.dispatchEvent(new Event("devmode"));
  };
  return [on, set];
}
