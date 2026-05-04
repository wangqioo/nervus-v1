from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
import uvicorn

from infra import nats_client, postgres_client, redis_client
from infra.mdns import start_mdns, stop_mdns
from infra.settings import Settings
from nervus_platform.apps.registry import AppRegistry
from nervus_platform.apps.routes import router as apps_router
from nervus_platform.config.routes import router as config_router
from nervus_platform.config.service import ConfigService
from nervus_platform.models.service import ModelService
from nervus_platform.models.routes import router as models_router
from nervus_platform.events.service import EventService
from nervus_platform.events.routes import router as events_router
from nervus_platform.knowledge.service import KnowledgeService
from nervus_platform.knowledge.routes import router as knowledge_router
from router.fast_router import FastRouter
from router.semantic_router import SemanticRouter
from router.dynamic_router import DynamicRouter
from executor.flow_executor import FlowExecutor
from executor.flow_loader import FlowLoader
from executor.embedding_pipeline import init_pipeline, EmbeddingPipeline
from api import notify_api, status_api

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [arbor-core] %(levelname)s %(message)s",
)
logger = logging.getLogger("nervus.arbor")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Arbor Core Platform v0.1 starting...")
    settings = Settings.from_env()
    app.state.settings = settings

    await nats_client.connect(settings.nats_url)
    await redis_client.connect(settings.redis_url)
    await postgres_client.connect(settings.postgres_url)

    app.state.config_service = ConfigService(settings.config_dir)

    app.state.app_registry = AppRegistry()
    await app.state.app_registry.init(postgres_client.pool)

    models_config = str(Path(settings.config_dir) / "models.json")
    app.state.model_service = ModelService(settings.llm_url, models_config_path=models_config)

    app.state.event_service = EventService()
    await app.state.event_service.init(postgres_client.pool)

    app.state.knowledge_service = KnowledgeService()
    await app.state.knowledge_service.init(postgres_client.pool)
    app.state.knowledge_service.set_model_service(app.state.model_service)

    model_svc = app.state.model_service
    embedding_pipeline = init_pipeline(postgres_client.pool, model_svc)
    await embedding_pipeline.start()
    app.state.embedding_pipeline = embedding_pipeline

    flow_loader = FlowLoader(settings.flows_dir)
    flow_loader.load_all()
    flow_executor = FlowExecutor(app.state.app_registry)
    fast_router = FastRouter(app.state.app_registry, flow_executor)
    fast_router.load_flows(flow_loader.flows)
    semantic_router = SemanticRouter(app.state.app_registry, flow_executor, model_service=model_svc)
    dynamic_router = DynamicRouter(app.state.app_registry, flow_executor, model_service=model_svc)
    app.state.fast_router = fast_router
    app.state.semantic_router = semantic_router
    app.state.dynamic_router = dynamic_router

    asyncio.create_task(start_bus_listener())
    asyncio.create_task(start_heartbeat_watcher())
    start_mdns(port=settings.app_port)

    logger.info("Arbor Core Platform v0.1 ready")
    yield

    logger.info("Arbor Core Platform v0.1 shutting down...")
    await app.state.embedding_pipeline.stop()
    stop_mdns()
    await nats_client.disconnect()
    await redis_client.disconnect()
    await postgres_client.disconnect()


app = FastAPI(
    title="Nervus Arbor Core Platform",
    description="Nervus platform core services",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(config_router, prefix="/config", tags=["Config"])
app.include_router(apps_router, prefix="/apps", tags=["Apps"])
app.include_router(models_router, prefix="/models", tags=["Models"])
app.include_router(events_router, prefix="/events", tags=["Events"])
app.include_router(knowledge_router, prefix="/platform/knowledge", tags=["Knowledge"])
app.include_router(notify_api.router, prefix="/notify", tags=["Notify"])
app.include_router(status_api.router, prefix="", tags=["Status"])


@app.get("/flows", tags=["Flows"])
async def list_flows(request: Request):
    fast: FastRouter = request.app.state.fast_router
    flows = list(fast._flows.values())
    return {"count": len(flows), "flows": flows}


@app.post("/flows/reload", tags=["Flows"])
async def reload_flows(request: Request):
    settings: Settings = request.app.state.settings
    loader = FlowLoader(settings.flows_dir)
    loader.load_all()
    fast: FastRouter = request.app.state.fast_router
    fast.load_flows(loader.flows)
    return {"status": "ok", "count": len(loader.flows)}


async def start_bus_listener():
    nc = nats_client.client
    if nc is None:
        logger.error("NATS is not connected; bus listener not started")
        return

    event_service: EventService = app.state.event_service
    fast_router: FastRouter = app.state.fast_router
    semantic_router: SemanticRouter = app.state.semantic_router
    dynamic_router: DynamicRouter = app.state.dynamic_router

    async def on_event(msg):
        try:
            data = json.loads(msg.data.decode())
            logger.debug("received bus event %s: %s", msg.subject, data)

            await event_service.ingest(
                subject=msg.subject,
                payload=data,
                source_app=data.get("source_app", "bus"),
            )

            event_envelope = {"subject": msg.subject, "payload": data}
            if await fast_router.route(msg.subject, event_envelope):
                return
            if await semantic_router.route(msg.subject, event_envelope):
                return
            await dynamic_router.route(msg.subject, event_envelope)
        except Exception:
            logger.exception("failed to process bus event")

    for subject in ["media.>", "meeting.>", "health.>", "context.>", "memory.>", "knowledge.>", "system.>", "schedule.>"]:
        await nc.subscribe(subject, cb=on_event)
        logger.info("subscribed to %s", subject)


async def start_heartbeat_watcher():
    registry: AppRegistry = app.state.app_registry
    while True:
        await asyncio.sleep(60)
        try:
            n = await registry.mark_offline_stale(timeout_seconds=120)
            if n:
                logger.info("heartbeat watcher: marked %s app(s) offline", n)
        except Exception:
            logger.exception("heartbeat watcher error")


if __name__ == "__main__":
    port = int(os.getenv("ARBOR_PORT", os.getenv("APP_PORT", "8090")))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info", access_log=False)
