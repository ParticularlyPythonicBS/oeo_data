from dotenv import find_dotenv, dotenv_values

from typing import NamedTuple, Optional


def get_required_env_var(env_dict: dict[str, Optional[str]], var_name: str) -> str:
    """
    Retrieves a required environment variable, raising an error if it's missing.
    """
    value = env_dict.get(var_name)
    if value is None:
        raise EnvironmentError(f"Missing required environment variable: {var_name}")
    return value


dotenv_path = find_dotenv()

env = dotenv_values(dotenv_path)

R2_ACCOUNT_ID = get_required_env_var(env, "R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = get_required_env_var(env, "R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = get_required_env_var(env, "R2_SECRET_ACCESS_KEY")
R2_BUCKET = get_required_env_var(env, "R2_BUCKET")

R2_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

MANIFEST_FILE = "manifest.json"
MAX_DIFF_LINES = 500


configTuple = NamedTuple(
    "configTuple",
    [
        ("R2_ACCOUNT_ID", str),
        ("R2_ACCESS_KEY_ID", str),
        ("R2_SECRET_ACCESS_KEY", str),
        ("R2_BUCKET", str),
        ("R2_ENDPOINT_URL", str),
        ("MANIFEST_FILE", str),
        ("MAX_DIFF_LINES", int),
    ],
)

config = configTuple(
    R2_ACCOUNT_ID=R2_ACCOUNT_ID,
    R2_ACCESS_KEY_ID=R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY=R2_SECRET_ACCESS_KEY,
    R2_BUCKET=R2_BUCKET,
    R2_ENDPOINT_URL=R2_ENDPOINT_URL,
    MANIFEST_FILE=MANIFEST_FILE,
    MAX_DIFF_LINES=MAX_DIFF_LINES,
)
