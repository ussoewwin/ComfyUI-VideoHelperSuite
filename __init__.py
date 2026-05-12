# Force max upload size to 1GB (remains effective even after ComfyUI updates reset cli_args)
def _force_max_upload_1gb():
    _1gb = 1024 * 1024 * 1024
    try:
        from comfy import cli_args
        cli_args.args.max_upload_size = 1024
        import server
        inst = getattr(server.PromptServer, "instance", None)
        if inst is not None and getattr(inst, "app", None) is not None:
            setattr(inst.app, "_client_max_size", _1gb)
        try:
            import comfy_api.feature_flags as ff
            ff.SERVER_FEATURE_FLAGS["max_upload_size"] = _1gb
        except Exception:
            pass
    except Exception:
        pass

_force_max_upload_1gb()

from .videohelpersuite.nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
import folder_paths
from .videohelpersuite.server import server
from .videohelpersuite import documentation
from .videohelpersuite import latent_preview

WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
documentation.format_descriptions(NODE_CLASS_MAPPINGS)
