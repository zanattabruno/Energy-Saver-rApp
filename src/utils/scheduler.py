"""
Scheduling utilities for the Energy Saver rApp.

This module provides scheduling functionality for running optimization
at fixed time intervals.
"""

import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Callable, Optional


class FixedIntervalScheduler:
    """
    Scheduler for running tasks at fixed time intervals.
    
    This scheduler ensures that tasks run at regular intervals regardless
    of how long each task execution takes.
    """
    
    def __init__(self, interval_minutes: int, task_function: Callable[[], int]):
        """
        Initialize the scheduler.
        
        Args:
            interval_minutes (int): Interval in minutes between task executions
            task_function (Callable): Function to execute periodically (should return int exit code)
        """
        self.interval_minutes = interval_minutes
        self.task_function = task_function
        self.logger = logging.getLogger(__name__)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_running = False
        
    def _calculate_next_run_time(self) -> datetime:
        """
        Calculate the next run time aligned to the interval.
        
        Returns:
            datetime: Next scheduled run time
        """
        now = datetime.now()
        
        # Align to the hour and minute boundaries
        if self.interval_minutes >= 60:
            # For intervals >= 1 hour, align to hour boundaries
            minutes_in_hour = now.minute
            next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            return next_hour
        else:
            # For intervals < 1 hour, align to interval boundaries within the hour
            minutes_since_hour = now.minute
            intervals_passed = minutes_since_hour // self.interval_minutes
            next_interval_minute = (intervals_passed + 1) * self.interval_minutes
            
            if next_interval_minute >= 60:
                # Next run is in the next hour
                next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            else:
                # Next run is within the current hour
                next_run = now.replace(minute=next_interval_minute, second=0, microsecond=0)
            
            return next_run
    
    def _scheduler_loop(self) -> None:
        """
        Main scheduler loop that runs in a separate thread.
        """
        self.logger.info(f"Scheduler started with {self.interval_minutes}-minute intervals")
        
        while not self._stop_event.is_set():
            try:
                # Calculate next run time
                next_run = self._calculate_next_run_time()
                now = datetime.now()
                
                # Calculate sleep time
                sleep_seconds = (next_run - now).total_seconds()
                
                if sleep_seconds > 0:
                    self.logger.info(f"Next optimization scheduled for {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # Sleep until next run time, but check for stop event periodically
                    while sleep_seconds > 0 and not self._stop_event.is_set():
                        sleep_time = min(sleep_seconds, 30)  # Check every 30 seconds
                        time.sleep(sleep_time)
                        sleep_seconds -= sleep_time
                
                # Check if we should stop before running the task
                if self._stop_event.is_set():
                    break
                
                # Execute the task
                self.logger.info("Starting scheduled optimization run")
                start_time = datetime.now()
                
                try:
                    exit_code = self.task_function()
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    
                    if exit_code == 0:
                        self.logger.info(f"Scheduled optimization completed successfully in {duration:.1f} seconds")
                    else:
                        self.logger.error(f"Scheduled optimization failed with exit code {exit_code} after {duration:.1f} seconds")
                        
                except Exception as e:
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    self.logger.error(f"Scheduled optimization failed with exception after {duration:.1f} seconds: {e}")
                
            except Exception as e:
                self.logger.error(f"Scheduler loop error: {e}")
                # Sleep a bit before retrying to avoid rapid error loops
                if not self._stop_event.wait(60):  # Wait 1 minute or until stop event
                    continue
                else:
                    break
        
        self.logger.info("Scheduler stopped")
    
    def start(self, run_immediately: bool = False) -> None:
        """
        Start the scheduler.
        
        Args:
            run_immediately (bool): Whether to run the task immediately before starting the schedule
        """
        if self._is_running:
            self.logger.warning("Scheduler is already running")
            return
        
        if self.interval_minutes <= 0:
            self.logger.info("Scheduler interval is 0 or negative, running once and exiting")
            try:
                exit_code = self.task_function()
                if exit_code == 0:
                    self.logger.info("Single optimization run completed successfully")
                else:
                    self.logger.error(f"Single optimization run failed with exit code {exit_code}")
            except Exception as e:
                self.logger.error(f"Single optimization run failed with exception: {e}")
            return
        
        # Run immediately if requested
        if run_immediately:
            self.logger.info("Running initial optimization before starting scheduler")
            try:
                exit_code = self.task_function()
                if exit_code == 0:
                    self.logger.info("Initial optimization completed successfully")
                else:
                    self.logger.error(f"Initial optimization failed with exit code {exit_code}")
            except Exception as e:
                self.logger.error(f"Initial optimization failed with exception: {e}")
        
        # Start the scheduler thread
        self._is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()
        
        self.logger.info("Scheduler thread started")
    
    def stop(self, timeout: float = 30.0) -> bool:
        """
        Stop the scheduler.
        
        Args:
            timeout (float): Maximum time to wait for the scheduler to stop
            
        Returns:
            bool: True if stopped successfully, False if timeout occurred
        """
        if not self._is_running:
            self.logger.info("Scheduler is not running")
            return True
        
        self.logger.info("Stopping scheduler...")
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout)
            if self._thread.is_alive():
                self.logger.warning(f"Scheduler thread did not stop within {timeout} seconds")
                return False
        
        self._is_running = False
        self.logger.info("Scheduler stopped successfully")
        return True
    
    def is_running(self) -> bool:
        """
        Check if the scheduler is currently running.
        
        Returns:
            bool: True if running, False otherwise
        """
        return self._is_running