import logging

def setup_logger(name, log_file, level=logging.INFO):
    """Function to set up a logger."""
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Create handlers
    stream_handler = logging.StreamHandler(None)
    
    # Add handlers to the logger
    logger.addHandler(stream_handler)

    logger.propagate = True   # prevent root duplication
    return logger
