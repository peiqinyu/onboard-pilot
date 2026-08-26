import logging
# Configure logging
# logging.basicConfig(format="%(levelname)s: %(name)s: %(message)s")
logging.basicConfig(format="[%(levelname)s]: %(message)s")
logger = logging.getLogger(__name__)
# Enable your desired logger level (e.g., DEBUG to see all logs)
logger.setLevel(logging.DEBUG)
