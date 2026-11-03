// Minimal adapter for UI to call real routes, keeping MOCK mode switch
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

export async function createExperiment(text) {
  if (USE_MOCK) {
    // return mock id
    return {id: "mock-id"};
  }
  const res = await fetch(`${API_BASE}/api/experiments`, {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({text})});
  if (!res.ok) throw new Error(`create failed ${res.status}`);
  return await res.json();
}
export async function getExperiment(id) {
  if (USE_MOCK) return {status:"success", result:{mock:true}};
  const res = await fetch(`${API_BASE}/api/experiments/${id}`);
  if (!res.ok) throw new Error(`get failed ${res.status}`);
  return await res.json();
}
export function subscribeExperiment(id, onEvent) {
  if (USE_MOCK) {
    setTimeout(()=>onEvent({type:"stage_completed", stage:"mock"}), 100);
    return {close:()=>{}};
  }
  const ws = new WebSocket(`${API_BASE.replace(/^http/, "ws")}/ws/experiments/${id}`);
  ws.onmessage = (ev) => {
    try { onEvent(JSON.parse(ev.data)); } catch(e){}
  };
  return ws;
}
