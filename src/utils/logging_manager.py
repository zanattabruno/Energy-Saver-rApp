"""
Logging configuration utilities for the Energy Saver rApp.

This module provides centralized logging setup and configuration.
"""

import logging
import logging.handlers
import sys
from typing import Dict, Any, Optional
from pathlib import Path


class LoggingManager:
    """
    Centralized logging manager for the Energy Saver rApp.
    """
    
    @staticmethod
    def setup_logging(
        level: str = 'INFO',
        log_format: Optional[str] = None,
        log_file: Optional[str] = None,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ) -> logging.Logger:
        """
        Set up logging configuration for the application.
        
        Args:
            level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_format (str, optional): Custom log format string
            log_file (str, optional): Path to log file for file logging
            max_bytes (int): Maximum size of log file before rotation
            backup_count (int): Number of backup log files to keep
            
        Returns:
            logging.Logger: Configured root logger
            
        Raises:
            ValueError: If invalid log level is provided
        """
        # Validate and set log level
        numeric_level = getattr(logging, level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(f'Invalid log level: {level}')
        
        # Default log format
        if log_format is None:
            log_format = '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        
        # Clear any existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Configure root logger
        root_logger.setLevel(numeric_level)
        
        # Create formatter
        formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # File handler with rotation (if log_file is specified)
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        
        # Log the logging configuration
        logger = logging.getLogger(__name__)
        logger.info(f"Logging configured - Level: {level}, Format: {log_format}")
        if log_file:
            logger.info(f"File logging enabled - Path: {log_file}")
        
        return root_logger
    
    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """
        Get a logger with the specified name.
        
        Args:
            name (str): Logger name
            
        Returns:
            logging.Logger: Logger instance
        """
        return logging.getLogger(name)
    
    @staticmethod
    def log_function_entry(logger: logging.Logger, func_name: str, **kwargs) -> None:
        """
        Log function entry with parameters.
        
        Args:
            logger (logging.Logger): Logger instance
            func_name (str): Function name
            **kwargs: Function parameters to log
        """
        if kwargs:
            params = ', '.join([f"{k}={v}" for k, v in kwargs.items()])
            logger.debug(f"Entering {func_name}({params})")
        else:
            logger.debug(f"Entering {func_name}()")
    
    @staticmethod
    def log_function_exit(logger: logging.Logger, func_name: str, result: Any = None) -> None:
        """
        Log function exit with result.
        
        Args:
            logger (logging.Logger): Logger instance
            func_name (str): Function name
            result: Function result to log
        """
        if result is not None:
            logger.debug(f"Exiting {func_name}() -> {type(result).__name__}")
        else:
            logger.debug(f"Exiting {func_name}()")
    
    @staticmethod
    def log_exception(logger: logging.Logger, exception: Exception, context: str = "") -> None:
        """
        Log exception with context.
        
        Args:
            logger (logging.Logger): Logger instance
            exception (Exception): Exception to log
            context (str): Additional context information
        """
        context_msg = f" - Context: {context}" if context else ""
        logger.exception(f"Exception occurred: {type(exception).__name__}: {exception}{context_msg}")


# Decorator for automatic function logging
def log_function_calls(logger_name: Optional[str] = None):
    """
    Decorator to automatically log function entry and exit.
    
    Args:
        logger_name (str, optional): Logger name to use, defaults to module name
        
    Returns:
        Function decorator
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(logger_name or func.__module__)
            func_name = func.__name__
            
            LoggingManager.log_function_entry(logger, func_name, **kwargs)
            try:
                result = func(*args, **kwargs)
                LoggingManager.log_function_exit(logger, func_name, result)
                return result
            except Exception as e:
                LoggingManager.log_exception(logger, e, f"in function {func_name}")
                raise
        
        return wrapper
    return decorator
