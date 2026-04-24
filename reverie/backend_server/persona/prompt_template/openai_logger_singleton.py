import os
import re
import threading
import time

from openai_cost_logger import OpenAICostLogger, DEFAULT_LOG_PATH
import openai_cost_logger.openai_cost_logger as openai_cost_logger_module


""" Metaclass for creating singletons."""
class Singleton(type):
    _instance = None
    _lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    # We have not every built an instance before.  Build one now.
                    instance = super().__call__(*args, **kwargs)
                    cls._instance = instance
                else:
                    instance = cls._instance 
        return instance
    

_WINDOWS_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


def _safe_path_component(value: str) -> str:
    cleaned = _WINDOWS_INVALID_FILENAME_CHARS.sub("-", str(value or "experiment"))
    cleaned = cleaned.strip().strip(".")
    return cleaned or "experiment"


def _safe_strftime(fmt: str) -> str:
    rendered = time.strftime(fmt)
    if os.name == "nt":
        rendered = rendered.replace(":", "-")
    return rendered


def _patch_cost_logger_for_windows() -> None:
    if os.name == "nt":
        openai_cost_logger_module.strftime = _safe_strftime


"""Singleton class for the OpenAICostLogger class."""
class OpenAICostLogger_Singleton(metaclass=Singleton):
    def __init__(self, experiment_name: str, cost_upperbound: float, log_folder: str = DEFAULT_LOG_PATH):
        """Initializes the OpenAICostLogger_Singleton class.

        Args:
            experiment_name (str): the name of the experiment.
            log_folder (str): the folder where the logs will be stored.
            cost_upperbound (float): the upperbound of the cost.
        """
        self.__cost_logger = None
        _patch_cost_logger_for_windows()
        try:
            self.__cost_logger = OpenAICostLogger(
                experiment_name=_safe_path_component(experiment_name),
                cost_upperbound=cost_upperbound,
                log_folder=log_folder
            )
        except OSError as exc:
            print(f"(cost_logger): disabled logging due to file setup error: {exc}")
        self.lock = threading.Lock() # Lock to ensure thread safety when updating the cost logger.
        
    
    def update_cost(self, response: dict, input_cost: float, output_cost: float = 0):
        """Updates the cost logger with the response, input cost, and output cost.

        Args:
            response (dict): the response from the model.
            input_cost (float): the cost of the input per million tokens.
            output_cost (float, optional): the cost of the output per million tokens.. Defaults to 0.
        """
        with self.lock:
            if self.__cost_logger is None:
                return
            self.__cost_logger.update_cost(
                response=response,
                input_cost=input_cost,
                output_cost=output_cost
            )
