import logging
from discord.ext import commands

def setup_logger(name, log_file, level=logging.INFO):
    """Function to set up a logger."""
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Create handlers
    file_handler = logging.FileHandler(log_file)
    stream_handler = logging.StreamHandler()
    
    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)


    logger.propagate = False   # prevent root duplication
    return logger
