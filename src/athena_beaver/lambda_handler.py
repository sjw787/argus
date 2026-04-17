from mangum import Mangum
from athena_beaver.api.app import create_app

handler = Mangum(create_app(), lifespan="off")
