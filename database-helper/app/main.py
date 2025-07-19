import logging
from app.consumer import start_consumer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("=== Starting Database Helper Application ===")
    logger.info("Application version: 0.1.0")
    logger.info("Python environment initialized")
    
    try:
        logger.info("Starting consumer...")
        start_consumer()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application failed to start: {e}", exc_info=True)
        raise
    finally:
        logger.info("=== Application shutdown complete ===")