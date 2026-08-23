import ee

from app.core.config import settings

_initialized = False


def get_ee():
    global _initialized
    if not _initialized:
        try:
            ee.Initialize(project=settings.gee_project_id)
        except Exception as exc:
            raise RuntimeError(
                "Earth Engine not authenticated on this machine. Run "
                "`.venv/bin/earthengine authenticate` once, then retry."
            ) from exc
        _initialized = True
    return ee
