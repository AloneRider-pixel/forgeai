import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from forgeai.auth import (
    Principal,
    ROLE_OPERATOR,
    ROLE_READER,
    ROLE_REVIEWER,
    require_role,
)
from forgeai.config import get_settings
from forgeai.control_models import (
    ApprovalDecisionRequest,
    ApprovalState,
    EvidenceBatchRequest,
    ExecutionRequest,
    ExecutionResponse,
    JobDetailResponse,
    RetrievalHit,
    RetrievalIndexRequest,
    RetrievalIndexResponse,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    ReviewJobRequest,
    ReviewJobResponse,
)
from forgeai.db import Database
from forgeai.models import (
    AssistedReviewReport,
    AssistedReviewRequest,
    PullRequestRequest,
    PullRequestSnapshot,
    ReviewReport,
)
from forgeai.observability import configure_tracing, metrics_payload, review_span
from forgeai.queue import InMemoryJobQueue, RedisJobQueue, queue_health
from forgeai.repository import ControlPlaneRepository
from forgeai.retrieval import RepositoryRetriever
from forgeai.services.context import collect_context
from forgeai.services.github_client import GitHubAPIError, GitHubClient
from forgeai.services.planner import DeterministicPlanner, OpenAICompatiblePlanner
from forgeai.services.review_engine import build_report
from forgeai.services.review_service import ReviewService
from forgeai.tool_gateway import ToolGateway, ToolPolicyError
from forgeai.webhook import (
    GitHubWebhookService,
    WebhookDispatcher,
    WebhookValidationError,
    verify_signature,
)

settings = get_settings()
configure_tracing(settings)
read_access = require_role(ROLE_READER)
review_access = require_role(ROLE_REVIEWER)
operator_access = require_role(ROLE_OPERATOR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database = Database(settings.database_url, auto_create_schema=settings.auto_create_schema)
    await database.init()
    github = GitHubClient(token=settings.github_token, timeout=settings.http_timeout_seconds)
    queue = RedisJobQueue(settings.redis_url) if settings.redis_url else InMemoryJobQueue()
    service = ReviewService(database, github, settings)
    webhook_service = GitHubWebhookService(database, queue, settings)
    dispatcher = WebhookDispatcher(database, queue, settings)
    retriever = RepositoryRetriever(github, settings)
    stop_event = asyncio.Event()
    app.state.database = database
    app.state.github_client = github
    app.state.job_queue = queue
    app.state.review_service = service
    app.state.retriever = retriever
    app.state.tool_gateway = ToolGateway(github, settings)
    app.state.webhook_service = webhook_service

    local_worker_task = None
    if isinstance(queue, InMemoryJobQueue):

        async def local_worker() -> None:
            while True:
                job_id = await queue.dequeue(timeout=5)
                if not job_id:
                    continue
                try:
                    with review_span(job_id):
                        await service.process(job_id)
                except Exception:
                    continue

        local_worker_task = asyncio.create_task(local_worker())

    dispatcher_task = asyncio.create_task(dispatcher.run_forever(stop_event))
    yield

    stop_event.set()
    dispatcher_task.cancel()
    try:
        await dispatcher_task
    except asyncio.CancelledError:
        pass
    if local_worker_task:
        local_worker_task.cancel()
        try:
            await local_worker_task
        except asyncio.CancelledError:
            pass
    github.close()
    if isinstance(queue, RedisJobQueue):
        await queue.close()
    await database.close()


app = FastAPI(
    title="ForgeAI",
    version="0.6.0",
    description="Production-oriented GitHub pull request risk review platform and control plane.",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "forgeai"}


@app.get("/ready")
async def ready() -> dict[str, str | bool]:
    queue_ok = await queue_health(app.state.job_queue)
    return {
        "status": "ready" if queue_ok else "degraded",
        "service": "forgeai",
        "queue": queue_ok,
    }


@app.get("/metrics")
def metrics() -> Response:
    body, media_type = metrics_payload()
    return Response(content=body, media_type=media_type)


@app.get("/v1/tools")
def list_tools(_: Principal = Depends(read_access)) -> dict[str, object]:
    return {"tools": app.state.tool_gateway.list_tools()}


def _build_report(snapshot: PullRequestSnapshot) -> ReviewReport:
    return build_report(snapshot, settings)


@app.post("/v1/reviews", response_model=ReviewReport)
def create_review(
    request: PullRequestRequest, _: Principal = Depends(read_access)
) -> ReviewReport:
    client: GitHubClient = app.state.github_client
    try:
        snapshot = client.get_pull_request(request.repository, request.pull_request)
    except (GitHubAPIError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _build_report(snapshot)


@app.post("/v1/reviews/assisted", response_model=AssistedReviewReport)
def create_assisted_review(
    request: AssistedReviewRequest, _: Principal = Depends(read_access)
) -> AssistedReviewReport:
    client: GitHubClient = app.state.github_client
    try:
        snapshot, changed_files = client.get_pull_request_bundle(
            request.repository, request.pull_request
        )
        baseline = _build_report(snapshot)
        context = collect_context(
            client,
            snapshot,
            changed_files,
            baseline.findings,
            max_files=request.max_context_files,
            max_chars=request.max_file_chars,
        )
        planner = OpenAICompatiblePlanner(settings) if request.use_llm else DeterministicPlanner()
        plan = planner.plan(baseline, context)
    except (GitHubAPIError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AssistedReviewReport(baseline=baseline, context=context, plan=plan)


@app.post("/v1/jobs", response_model=ReviewJobResponse, status_code=202)
async def create_job(
    request: ReviewJobRequest, _: Principal = Depends(read_access)
) -> ReviewJobResponse:
    service: ReviewService = app.state.review_service
    job_id = await service.create_job(request)
    await app.state.job_queue.enqueue(job_id)
    async with app.state.database.sessions() as session:
        record = await ControlPlaneRepository().get_job(session, job_id)
    return ControlPlaneRepository.to_response(record)


@app.get("/v1/jobs", response_model=list[ReviewJobResponse])
async def list_jobs(_: Principal = Depends(read_access)) -> list[ReviewJobResponse]:
    async with app.state.database.sessions() as session:
        records = await ControlPlaneRepository().list_jobs(session)
    return [ControlPlaneRepository.to_response(record) for record in records]


@app.get("/v1/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: str, _: Principal = Depends(read_access)
) -> JobDetailResponse:
    async with app.state.database.sessions() as session:
        record = await ControlPlaneRepository().get_job(session, job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="review job not found")
    return ControlPlaneRepository.to_detail(record)


@app.post("/v1/jobs/{job_id}/evidence", response_model=JobDetailResponse)
async def ingest_evidence(
    job_id: str,
    request: EvidenceBatchRequest,
    _: Principal = Depends(review_access),
) -> JobDetailResponse:
    try:
        await app.state.review_service.add_evidence_and_recompute_gate(job_id, request.findings)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await get_job(job_id)


@app.post("/v1/jobs/{job_id}/evidence/sarif", response_model=JobDetailResponse)
async def ingest_sarif(
    job_id: str,
    source: str,
    payload: dict[str, object],
    _: Principal = Depends(review_access),
) -> JobDetailResponse:
    from forgeai.control_models import EvidenceSource
    from forgeai.evidence_ingest import parse_sarif

    try:
        evidence_source = EvidenceSource(source)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="source must be codeql or dependency-review"
        ) from exc
    findings = parse_sarif(payload, evidence_source)
    try:
        await app.state.review_service.add_evidence_and_recompute_gate(job_id, findings)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await get_job(job_id)


async def _decide_approval(
    job_id: str,
    state: ApprovalState,
    request: ApprovalDecisionRequest,
    principal: Principal,
) -> JobDetailResponse:
    async with app.state.database.sessions() as session:
        try:
            await ControlPlaneRepository().upsert_approval(
                session, job_id, state, principal.key_id, request.rationale
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await get_job(job_id)


@app.post("/v1/jobs/{job_id}/approval/approve", response_model=JobDetailResponse)
async def approve_job(
    job_id: str,
    request: ApprovalDecisionRequest,
    principal: Principal = Depends(review_access),
) -> JobDetailResponse:
    return await _decide_approval(job_id, ApprovalState.APPROVED, request, principal)


@app.post("/v1/jobs/{job_id}/approval/reject", response_model=JobDetailResponse)
async def reject_job(
    job_id: str,
    request: ApprovalDecisionRequest,
    principal: Principal = Depends(review_access),
) -> JobDetailResponse:
    return await _decide_approval(job_id, ApprovalState.REJECTED, request, principal)


@app.post("/v1/jobs/{job_id}/execute", response_model=ExecutionResponse)
async def execute_tool(
    job_id: str,
    request: ExecutionRequest,
    _: Principal = Depends(operator_access),
) -> ExecutionResponse:
    async with app.state.database.sessions() as session:
        record = await ControlPlaneRepository().get_job(session, job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="review job not found")
    if record.status != "succeeded":
        raise HTTPException(status_code=409, detail="review job must succeed before execution")
    if not record.approval or record.approval.state != ApprovalState.APPROVED.value:
        raise HTTPException(status_code=403, detail="explicit human approval is required")
    arguments = {**request.arguments, "repository": record.repository}
    try:
        result = app.state.tool_gateway.call(request.tool_name, arguments, approved=True)
    except ToolPolicyError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    async with app.state.database.sessions() as session:
        execution_id = await ControlPlaneRepository().create_execution(
            session, job_id, request.tool_name, arguments, "succeeded", result
        )
    return ExecutionResponse(
        execution_id=execution_id,
        job_id=job_id,
        tool_name=request.tool_name,
        status="succeeded",
        response=result,
    )


@app.post("/v1/retrieval/index", response_model=RetrievalIndexResponse)
async def index_repository(
    request: RetrievalIndexRequest,
    _: Principal = Depends(operator_access),
) -> RetrievalIndexResponse:
    documents = await asyncio.to_thread(
        app.state.retriever.index_repository, request.repository, request.ref
    )
    async with app.state.database.sessions() as session:
        count = await ControlPlaneRepository().upsert_repository_documents(
            session, request.repository, request.ref, documents
        )
    mode = "embedding" if app.state.retriever.embeddings.enabled else "lexical-fallback"
    return RetrievalIndexResponse(
        repository=request.repository,
        ref=request.ref,
        documents_indexed=count,
        mode=mode,
    )


@app.post("/v1/retrieval/search", response_model=RetrievalSearchResponse)
async def search_repository(
    request: RetrievalSearchRequest,
    _: Principal = Depends(read_access),
) -> RetrievalSearchResponse:
    async with app.state.database.sessions() as session:
        records = await ControlPlaneRepository().list_repository_documents(
            session, request.repository, request.ref
        )
    documents = [
        {
            "path": record.path,
            "content": record.content,
            "embedding": record.embedding_json,
            "sha": record.sha,
        }
        for record in records
    ]
    results = await asyncio.to_thread(
        app.state.retriever.search, request.query, documents, request.top_k
    )
    hits = [
        RetrievalHit(path=item.path, score=item.score, mode=item.mode, content=item.content)
        for item in results
    ]
    return RetrievalSearchResponse(
        repository=request.repository,
        ref=request.ref,
        query=request.query,
        hits=hits,
    )


@app.post("/v1/webhooks/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_github_delivery: str = Header(..., alias="X-GitHub-Delivery"),
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
) -> JSONResponse:
    body = await request.body()
    if len(body) > 1_000_000:
        raise HTTPException(status_code=413, detail="webhook payload is too large")
    try:
        verify_signature(body, x_hub_signature_256, settings.github_webhook_secret)
    except WebhookValidationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON payload") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="webhook payload must be a JSON object")

    try:
        result = await app.state.webhook_service.ingest(
            x_github_delivery,
            x_github_event,
            payload,
        )
    except WebhookValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    status_code = 202 if result["accepted"] else 200
    return JSONResponse(result, status_code=status_code)


@app.get("/v1/webhooks/github/{delivery_id}")
async def get_webhook_delivery(
    delivery_id: str, _: Principal = Depends(read_access)
) -> dict[str, object]:
    async with app.state.database.sessions() as session:
        record = await ControlPlaneRepository().get_webhook_delivery(session, delivery_id)
    if record is None:
        raise HTTPException(status_code=404, detail="webhook delivery not found")
    return {
        "delivery_id": record.delivery_id,
        "event_type": record.event_type,
        "action": record.action,
        "repository": record.repository,
        "pull_request": record.pull_request,
        "status": record.status,
        "job_id": record.job_id,
        "attempts": record.attempts,
        "last_error": record.last_error,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "completed_at": record.completed_at,
    }


@app.post("/mcp")
async def mcp_gateway(
    message: dict[str, object], _: Principal = Depends(operator_access)
) -> JSONResponse:
    method = message.get("method")
    request_id = message.get("id")
    if method == "tools/list":
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": app.state.tool_gateway.list_tools()},
            }
        )
    if method != "tools/call":
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": "method not found"},
            },
            status_code=400,
        )
    params = message.get("params")
    if not isinstance(params, dict) or not isinstance(params.get("name"), str):
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": "invalid tool call"},
            },
            status_code=400,
        )
    arguments = params.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}
    job_id = arguments.get("job_id")
    if not isinstance(job_id, str):
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": "job_id is required"},
            },
            status_code=400,
        )
    async with app.state.database.sessions() as session:
        record = await ControlPlaneRepository().get_job(session, job_id)
    if record is None or record.status != "succeeded":
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32001, "message": "succeeded review job is required"},
            },
            status_code=409,
        )
    approved = bool(record.approval and record.approval.state == ApprovalState.APPROVED.value)
    safe_args = {key: str(value) for key, value in arguments.items() if key != "job_id"}
    safe_args["repository"] = record.repository
    try:
        result = app.state.tool_gateway.call(str(params["name"]), safe_args, approved=approved)
    except (ToolPolicyError, ValueError) as exc:
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32001, "message": str(exc)},
            },
            status_code=403,
        )
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result})
