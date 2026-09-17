from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from forgeai.config import get_settings
from forgeai.models import PullRequestRequest, ReviewReport
from forgeai.services.analyzer import analyze
from forgeai.services.github_client import GitHubAPIError, GitHubClient
from forgeai.services.risk import calculate_score, gate_decision


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.github_client = GitHubClient(
        token=settings.github_token,
        timeout=settings.http_timeout_seconds,
    )
    yield
    app.state.github_client.close()


app = FastAPI(
    title="ForgeAI",
    version="0.2.0",
    description="Production-oriented GitHub pull request risk review platform.",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "forgeai"}


@app.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready", "service": "forgeai"}


@app.post("/v1/reviews", response_model=ReviewReport)
def create_review(request: PullRequestRequest) -> ReviewReport:
    client: GitHubClient = app.state.github_client
    try:
        snapshot = client.get_pull_request(request.repository, request.pull_request)
    except (GitHubAPIError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    findings, factors = analyze(snapshot)
    score = calculate_score(factors)
    gate = gate_decision(score, settings, findings)

    return ReviewReport(
        snapshot=snapshot,
        risk_score=score,
        gate=gate,
        findings=findings,
        factors=factors,
    )
