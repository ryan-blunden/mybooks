import base64
import hashlib
import random
import string
from typing import Tuple, TypeVar

from django.db.models import Model

# Generic type variable for model types
ModelType = TypeVar("ModelType", bound=Model)


def strtobool(value: str) -> bool:
    return value.lower() in ("y", "yes", "t", "true", "on", "1")


def is_path_absolute(path):
    return path.startswith("/") or path.startswith("http")


def get_code_verifier() -> Tuple[str, str]:
    code_verifier = "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(random.randint(43, 128)))
    code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8").replace("=", "")
    return code_verifier, code_challenge
