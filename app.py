import os
from mr_service.records import Config
from mr_service.service import service
from flask import g


if __name__ == '__main__':

    config = Config(
        os.environ["PORT"],
        os.environ["SPARQL_QUERY"],
        os.environ["SPARQL_UPDATE"]
    )

    app = service(config)

    app.run(
        port=int(config.PORT),
        debug=True
    )
