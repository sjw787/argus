from mangum import Mangum
from argus.api.app import create_app

handler = Mangum(create_app(), lifespan="off")
