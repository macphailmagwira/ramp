from .base_config import BaseConfig
from .dev_config import DevConfig
from .prod_config import ProdConfig
from .staging_config import StagingConfig

base = BaseConfig()

config_var_mapping = {
    "STAGING": StagingConfig,
    "PRODUCTION": ProdConfig,
    "DEVELOPMENT": DevConfig,
}

environment = base.ENVIRONMENT
if environment not in config_var_mapping.keys():
    raise ValueError(f"Environment {environment} not set in environment variables")
config = config_var_mapping[environment]
settings = config()
