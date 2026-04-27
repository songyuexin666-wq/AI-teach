import os
import platform
from pathlib import Path


def get_default_cache_root() -> str:
    if platform.system().lower() == "windows":
        return r"D:\hf_cache"
    return str(Path.home() / "hf_cache")


def _normalize_path(path_value: str | None) -> str | None:
    if not path_value:
        return None
    return os.path.abspath(os.path.normpath(os.path.expanduser(path_value)))


def _looks_like_datalab_models_dir(path_value: str) -> bool:
    normalized = path_value.replace("/", os.sep).replace("\\", os.sep).lower()
    suffix = os.path.join("datalab", "datalab", "cache", "models").lower()
    return normalized.endswith(suffix)


def _iter_candidate_roots() -> list[str]:
    candidates: list[str] = []
    for env_name in ("DATALAB_CACHE_HOME", "MARKER_MODEL_CACHE", "HF_HOME"):
        value = _normalize_path(os.getenv(env_name))
        if value:
            if _looks_like_datalab_models_dir(value):
                value = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(value))))
            if value not in candidates:
                candidates.append(value)

    default_root = _normalize_path(get_default_cache_root())
    if default_root and default_root not in candidates:
        candidates.append(default_root)

    local_appdata = os.getenv("LOCALAPPDATA")
    local_appdata = _normalize_path(local_appdata)
    if local_appdata and local_appdata not in candidates:
        candidates.append(local_appdata)

    return candidates


def get_datalab_models_root(cache_root: str) -> str:
    if _looks_like_datalab_models_dir(cache_root):
        return cache_root
    return os.path.join(cache_root, "datalab", "datalab", "Cache", "models")


def has_local_datalab_model(cache_root: str, model_name: str) -> bool:
    model_root = os.path.join(get_datalab_models_root(cache_root), model_name)
    if not os.path.isdir(model_root):
        return False
    return any(True for _ in os.scandir(model_root))


def _version_sort_key(version_name: str) -> tuple:
    parts = version_name.split("_")
    normalized = []
    for part in parts:
        if part.isdigit():
            normalized.append(int(part))
        else:
            normalized.append(part)
    return tuple(normalized)


def get_model_versions(cache_root: str, model_name: str) -> list[str]:
    model_root = os.path.join(get_datalab_models_root(cache_root), model_name)
    if not os.path.isdir(model_root):
        return []

    versions = []
    for entry in os.scandir(model_root):
        if entry.is_dir():
            versions.append(entry.name)
    versions.sort(key=_version_sort_key, reverse=True)
    return versions


def get_complete_text_recognition_version(cache_root: str) -> str | None:
    required_files = {
        "model.safetensors",
        "config.json",
        "manifest.json",
    }

    for version in get_model_versions(cache_root, "text_recognition"):
        version_dir = os.path.join(
            get_datalab_models_root(cache_root),
            "text_recognition",
            version,
        )
        existing_files = {entry.name for entry in os.scandir(version_dir) if entry.is_file()}
        if required_files.issubset(existing_files) and len(existing_files) >= 8:
            return version
    return None


def parse_checkpoint_version(checkpoint: str | None) -> str | None:
    if not checkpoint:
        return None
    normalized = checkpoint.rstrip("/").split("/")
    if not normalized:
        return None
    return normalized[-1]


def get_requested_text_recognition_version() -> str | None:
    env_checkpoint = os.getenv("RECOGNITION_MODEL_CHECKPOINT")
    env_version = parse_checkpoint_version(env_checkpoint)
    if env_version:
        return env_version

    try:
        from surya.settings import settings as surya_settings

        return parse_checkpoint_version(surya_settings.RECOGNITION_MODEL_CHECKPOINT)
    except Exception:
        return None


def get_compatible_text_recognition_version(cache_root: str) -> str | None:
    requested_version = get_requested_text_recognition_version()
    if requested_version:
        version_dir = os.path.join(
            get_datalab_models_root(cache_root),
            "text_recognition",
            requested_version,
        )
        if os.path.isdir(version_dir):
            existing_files = {entry.name for entry in os.scandir(version_dir) if entry.is_file()}
            required_files = {
                "model.safetensors",
                "config.json",
                "manifest.json",
            }
            if required_files.issubset(existing_files) and len(existing_files) >= 8:
                return requested_version
        return get_complete_text_recognition_version(cache_root)

    return get_complete_text_recognition_version(cache_root)


def resolve_local_cache_root() -> str:
    for root in _iter_candidate_roots():
        if has_local_datalab_model(root, "text_recognition"):
            return root

    explicit_root = (
        _normalize_path(os.getenv("DATALAB_CACHE_HOME"))
        or _normalize_path(os.getenv("MARKER_MODEL_CACHE"))
        or _normalize_path(os.getenv("HF_HOME"))
    )
    if explicit_root:
        if _looks_like_datalab_models_dir(explicit_root):
            return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(explicit_root))))
        return explicit_root

    return _normalize_path(get_default_cache_root()) or get_default_cache_root()


def configure_local_model_environment() -> str:
    cache_root = resolve_local_cache_root()
    recognition_version = get_compatible_text_recognition_version(cache_root)

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["HF_HOME"] = cache_root
    os.environ["MARKER_MODEL_CACHE"] = cache_root
    os.environ["HUGGINGFACE_HUB_CACHE"] = os.path.join(cache_root, "hub")
    os.environ["TORCH_HOME"] = os.path.join(cache_root, "torch")
    os.environ["XDG_CACHE_HOME"] = cache_root
    if recognition_version:
        os.environ["RECOGNITION_MODEL_CHECKPOINT"] = f"s3://text_recognition/{recognition_version}"

    return cache_root


def ensure_required_local_models(cache_root: str) -> None:
    version = get_compatible_text_recognition_version(cache_root)
    if not version:
        expected = get_datalab_models_root(cache_root)
        requested = get_requested_text_recognition_version()
        if requested:
            raise RuntimeError(
                f"未找到与当前 surya/marker 版本兼容的本地 text_recognition 模型: {requested}。"
                f" 请确认模型完整位于: {os.path.join(expected, requested)}"
            )
        raise RuntimeError(
            "未找到本地 text_recognition 模型，已阻止联网下载。"
            f" 请确认模型位于: {expected}"
        )
