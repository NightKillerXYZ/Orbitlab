"""In-memory job store."""
from __future__ import annotations
import uuid, time, asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class Job:
    id: str
    text: str
    status: str = "queued"  # queued, running, success, failed
    result: Optional[Dict[str,Any]] = None
    error: Optional[Dict[str,Any]] = None
    events: List[Dict[str,Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

class JobStore:
    def __init__(self):
        self.jobs: Dict[str, Job] = {}
        self._listeners: Dict[str, List[asyncio.Queue]] = {}
    def create(self, text: str) -> Job:
        jid=str(uuid.uuid4())
        job=Job(id=jid, text=text)
        self.jobs[jid]=job
        self._listeners[jid]=[]
        return job
    def get(self, jid: str) -> Optional[Job]:
        return self.jobs.get(jid)
    def update(self, jid: str, **kwargs):
        job=self.jobs.get(jid)
        if not job:
            return
        for k,v in kwargs.items():
            setattr(job,k,v)
        job.updated_at=time.time()
    def add_event(self, jid: str, event: Dict[str,Any]):
        job=self.jobs.get(jid)
        if not job:
            return
        job.events.append(event)
        # notify listeners
        for q in self._listeners.get(jid, []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass
    def subscribe(self, jid: str) -> asyncio.Queue:
        q=asyncio.Queue()
        if jid not in self._listeners:
            self._listeners[jid]=[]
        self._listeners[jid].append(q)
        # replay existing events
        job=self.jobs.get(jid)
        if job:
            for ev in job.events:
                q.put_nowait(ev)
            # if job already finished, send final
            if job.status in ("success","failed"):
                q.put_nowait({"type":"final","result":job.result,"error":job.error})
        return q
    def unsubscribe(self, jid: str, q: asyncio.Queue):
        if jid in self._listeners:
            try:
                self._listeners[jid].remove(q)
            except ValueError:
                pass

store=JobStore()
