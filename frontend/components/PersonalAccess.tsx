"use client";
import { useEffect, useState } from "react";
export function PersonalAccess() {
  const [unlocked, setUnlocked] = useState(false);
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState("");
  useEffect(() => { setUnlocked(Boolean(sessionStorage.getItem("personal-access-token"))); }, []);
  return <div className="px-4 pb-2 text-sm">
    <button className="underline" onClick={() => { if (unlocked) { sessionStorage.removeItem("personal-access-token"); setUnlocked(false); } else setOpen(!open); }}>{unlocked ? "Lock personal access" : "Unlock personal access"}</button>
    {open && <form className="mt-2 flex gap-2" onSubmit={event => { event.preventDefault(); sessionStorage.setItem("personal-access-token", token); setToken(""); setUnlocked(true); setOpen(false); }}>
      <input aria-label="Personal access token" type="password" autoComplete="current-password" required value={token} onChange={event => setToken(event.target.value)} className="rounded border p-2" />
      <button className="rounded bg-moss px-3 text-white">Unlock</button>
    </form>}
  </div>;
}
