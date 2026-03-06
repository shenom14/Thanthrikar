import logging
import sys

def setup_logger(name: str) -> logging.Logger:
    """
    Standardized logger setup for all microservices and agents.
    Outputs structured logs with timestamps and module names.
    
    Args:
        name (str): The name of the module invoking the logger (usually `__name__`).
        
    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)
    
    # Prevent attaching multiple handlers if already set up
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Standard Stream Handler
        handler = logging.StreamHandler(sys.stdout)
        
        # Standard Formatter
        formatter = logging.Formatter(
            '%(asctime)s - [%(levelname)s] - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger
