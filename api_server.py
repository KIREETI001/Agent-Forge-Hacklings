from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent_core import classify_route, route_and_scrape_with_sponsors_streaming, run_pipeline, scrape_and_score_with_sponsors_streaming

app = FastAPI(title="Agent-Forge Person B API", version="1.0.0")


class ScrapeRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Admissions or student-life query to run through the collectors")
    use_fallback: bool = Field(default=True, description="Skip the TokenRouter summary and return the deterministic merge")


class ScoreRequest(BaseModel):
    student_rp: float = Field(..., ge=0, description="Student rank points")
    interest: str = Field(..., min_length=1, description="Interest label such as Computing")
    use_fallback: bool = Field(default=True, description="Return the pre-seeded local dataset immediately")


class RouteRequest(BaseModel):
    raw_text: str = Field(..., min_length=1, description="Freeform student prompt to route through Kimi and TokenRouter")
    use_fallback: bool = Field(default=True, description="Use pre-seeded data and skip live scraping")


class ScrapeResponse(BaseModel):
    status: str
    message: str
    query: str
    data: list[dict[str, Any]]
    summary: str | None = None
    events: list[dict[str, Any]]


class ScoreResponse(BaseModel):
    status: str
    data: list[dict[str, Any]]
    trace: dict[str, Any]
    progress: float | None = None


class RouteResponse(BaseModel):
    status: str
    branch: str
    intent: dict[str, Any]
    route_plan: dict[str, bool]
    data: list[dict[str, Any]]
    summary: str | None = None
    trace: dict[str, Any]
    progress: float | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/scrape", response_model=ScrapeResponse)
def scrape(payload: ScrapeRequest) -> ScrapeResponse:
    try:
        result = run_pipeline(payload.query, use_fallback=payload.use_fallback)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ScrapeResponse(
        status=result["status"],
        message=result["message"],
        query=result["query"],
        data=result["data"],
        summary=result.get("summary"),
        events=result["events"],
    )


@app.post("/score")
def score(payload: ScoreRequest) -> ScoreResponse:
    try:
        last_event: dict[str, Any] | None = None
        for event in scrape_and_score_with_sponsors_streaming(payload.student_rp, payload.interest, payload.use_fallback):
            last_event = event
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if last_event is None:
        raise HTTPException(status_code=500, detail="Pipeline produced no response")

    return ScoreResponse(
        status=str(last_event.get("status", "unknown")),
        data=list(last_event.get("data", [])),
        trace=dict(last_event.get("trace", {})),
        progress=last_event.get("progress"),
    )


@app.post("/orchestrate", response_model=RouteResponse)
def orchestrate(payload: RouteRequest) -> RouteResponse:
    try:
        last_event: dict[str, Any] | None = None
        for event in route_and_scrape_with_sponsors_streaming(payload.raw_text, payload.use_fallback):
            last_event = event
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if last_event is None:
        raise HTTPException(status_code=500, detail="Pipeline produced no response")

    return RouteResponse(
        status=str(last_event.get("status", "unknown")),
        branch=str(last_event.get("branch", classify_route(payload.raw_text).get("branch", "EVALUATE"))),
        intent=dict(last_event.get("intent", classify_route(payload.raw_text))),
        route_plan=dict(last_event.get("route_plan", {})),
        data=list(last_event.get("data", [])),
        summary=last_event.get("summary"),
        trace=dict(last_event.get("trace", {})),
        progress=last_event.get("progress"),
    )
