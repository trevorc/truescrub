import abc
import argparse
import concurrent.futures
import json
import logging
import os
import threading
import types
from concurrent.futures import Future, ThreadPoolExecutor
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    NoReturn,
    Optional,
    Protocol,
    Type,
    TypedDict,
    TypeVar,
    Union,
    cast,
)

import waitress.server
from flask import Flask
from werkzeug.middleware.shared_data import SharedDataMiddleware

import truescrub
from truescrub import db
from truescrub.api import app
from truescrub.queue_consumer import QueueConsumer, QueueItem
from truescrub.updater import Updater


# A TypedDict for game state messages
class GameStateMessage(TypedDict, total=False):
    """Message containing a game state to process."""
    command: str
    game_state: Dict[str, Any]
    game_state_id: int

# Type for generic Future
T = TypeVar('T')

# Type definitions for Flask app with state_writer
if TYPE_CHECKING:
    from flask import Flask

    class FlaskWithStateWriter(Protocol):
        """Protocol defining Flask application with state_writer attribute."""
        state_writer: 'GameStateWriter'

        # Include necessary methods from Flask that we use
        def __call__(self, *args: Any, **kwargs: Any) -> Any: ...

    # Use Protocol structural typing to make existing Flask app compatible
    FlaskApp = Union[Flask, FlaskWithStateWriter]

# Define a protocol for services that can be called
class CallableService(Protocol):
    def __call__(self) -> None: ...


LOG_LEVEL = os.environ.get("TRUESCRUB_LOG_LEVEL", "DEBUG")
logging.basicConfig(
    format="%(asctime)s.%(msecs).3dZ\t" "%(name)s\t%(levelname)s\t%(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    level=LOG_LEVEL,
)
logger = logging.getLogger(__name__)

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument(
    "-a", "--addr", metavar="HOST", default="0.0.0.0", help="Bind to this address."
)
arg_parser.add_argument(
    "-p",
    "--port",
    metavar="PORT",
    type=int,
    default=9000,
    help="Listen on this TCP port.",
)
arg_parser.add_argument(
    "-c", "--recalculate", action="store_true", help="Recalculate rankings."
)
arg_parser.add_argument(
    "-s", "--serve-htdocs", action="store_true", help="Serve static files."
)


class Service(CallableService, metaclass=abc.ABCMeta):
    """Base abstract service class for all services in the application."""

    @abc.abstractmethod
    def stop(self) -> Optional[bool]:
        """Stop the service.

        Returns:
            Optional[bool]: True if stopped successfully, False otherwise
        """
        pass

    @abc.abstractmethod
    def __call__(self) -> None:
        """Run the service."""
        pass

    def __enter__(self) -> "Service":
        """Context manager entry method.

        Returns:
            Service: The service instance
        """
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[types.TracebackType],
    ) -> Optional[bool]:
        """Context manager exit method that stops the service.

        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Traceback if an exception was raised

        Returns:
            Optional[bool]: Result of calling stop()
        """
        logger.info("stopping %s", self)
        return self.stop()

    def __str__(self) -> str:
        """Get string representation of the service.

        Returns:
            str: The service's class name
        """
        return type(self).__name__


class GameStateWriter(QueueConsumer):
    """Service that writes game states to the database."""

    def __init__(self, updater: Updater) -> None:
        """Initialize the game state writer.

        Args:
            updater: The updater instance to notify when game states are written
        """
        super().__init__()
        self.updater = updater

    def process_messages(self, messages: List[QueueItem]) -> None:
        """Process game state messages.

        Args:
            messages: List of messages to process
        """
        max_game_state = 0
        with db.get_game_db() as game_db:
            logger.debug("saving %d game states", len(messages))
            for message in messages:
                if isinstance(message, dict) and "game_state" in message:
                    game_state_msg = cast(GameStateMessage, message)
                    game_state_str = json.dumps(game_state_msg["game_state"])
                    game_state_id = db.insert_game_state(game_db, game_state_str)
                    logger.debug("saved game_state with id %d", game_state_id)
                    max_game_state = max(game_state_id, max_game_state)
            game_db.commit()
            self.updater.send_message(command="process", game_state_id=max_game_state)


class StateWriterService(Service):
    """Service wrapper for GameStateWriter."""

    def __init__(self, state_writer: GameStateWriter) -> None:
        """Initialize the state writer service.

        Args:
            state_writer: The GameStateWriter instance to run
        """
        self.state_writer = state_writer

    def __call__(self) -> None:
        """Run the state writer."""
        logger.info("running %s", self)
        self.state_writer.run()

    def stop(self) -> Optional[bool]:
        """Stop the state writer.

        Returns:
            Optional[bool]: None as this implementation doesn't return a success flag
        """
        self.state_writer.stop()
        return None


class UpdaterService(Service):
    """Service wrapper for Updater."""

    def __init__(self, updater: Updater) -> None:
        """Initialize the updater service.

        Args:
            updater: The Updater instance to run
        """
        self.updater = updater

    def __call__(self) -> None:
        """Run the updater."""
        logger.info("running %s", self)
        self.updater.run()

    def stop(self) -> Optional[bool]:
        """Stop the updater.

        Returns:
            Optional[bool]: None as this implementation doesn't return a success flag
        """
        self.updater.stop()
        return None


class WaitressService(Service):
    """Service that runs a Waitress WSGI server."""

    def __init__(self, app: Flask, host: str, port: int) -> None:
        """Initialize the waitress service.

        Args:
            app: The Flask application to serve
            host: The host address to bind to
            port: The port to listen on
        """
        self.server = waitress.server.create_server(
            app, host=host, port=port, _start=False
        )
        self.host = host
        self.port = port
        logger.info("listening on %s:%s", host, port)

    def __call__(self) -> None:
        """Run the waitress server."""
        logger.info("running %s", self)
        self.server.accept_connections()
        self.server.run()

    def stop(self) -> Optional[bool]:
        """Stop the waitress server.

        Returns:
            Optional[bool]: None as this implementation doesn't return a success flag
        """
        if self.server is not None:
            logger.debug("closing server")
            self.server.close()
        return None


def wait_on_futures(futures: Dict[Future[Any], Service]) -> bool:
    """Wait for futures to complete.

    Args:
        futures: Dictionary mapping futures to their services

    Returns:
        bool: True if all futures completed, False otherwise
    """
    for future in futures:
        future.cancel()
    logger.debug("waiting on remaining futures")
    done, not_done = concurrent.futures.wait(futures, timeout=4.0)
    if len(not_done) == 0:
        logger.info("canceling watchdog timer")
        return True
    logger.warning(
        "some futures did not complete: %s",
        [str(futures[future]) for future in not_done],
    )
    return False


class Watchdog:
    """Watchdog timer that forcibly exits the process if futures don't complete."""

    def __init__(self, futures: Dict[Future[Any], Service], interval: float) -> None:
        """Initialize the watchdog.

        Args:
            futures: Dictionary mapping futures to their services
            interval: Timeout interval in seconds
        """
        self.futures = futures
        self.timer = threading.Timer(interval, self.shutdown)

    def __enter__(self) -> "Watchdog":
        """Context manager entry.

        Returns:
            Watchdog: This watchdog instance
        """
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[types.TracebackType],
    ) -> None:
        """Context manager exit that triggers the watchdog timer on exception.

        Args:
            exc_type: Exception type if an exception was raised
            exc_value: Exception value if an exception was raised
            traceback: Traceback if an exception was raised
        """
        if exc_type is None:
            return

        logger.info("triggering watchdog timer due to %s", exc_type.__name__)
        self.timer.start()
        if wait_on_futures(self.futures):
            self.timer.cancel()

    @staticmethod
    def shutdown() -> NoReturn:
        """Force exit the process."""
        logger.error("forcibly exiting process")
        os._exit(-1)


def main() -> None:
    """Main entry point for the application."""
    args = arg_parser.parse_args()
    executor = ThreadPoolExecutor(max_workers=3)
    futures: Dict[Future[None], Service] = {}
    updater = Updater()
    state_writer = GameStateWriter(updater)
    db.initialize_dbs()

    if args.recalculate:
        updater.send_message(command="recalculate")
        updater.stop()
        updater.run()
        return

    if args.serve_htdocs:
        # Create the SharedDataMiddleware to serve static files
        # The app.wsgi_app attribute is actually dynamic, so this works at runtime
        # We need to use type: ignore to let mypy know this is intentional
        app.wsgi_app = SharedDataMiddleware(  # type: ignore[method-assign,assignment]
            app.wsgi_app,
            {"/htdocs": (truescrub.__name__, "htdocs")},
            cache_timeout=3600 * 24 * 14,
        )

    with Watchdog(futures, interval=8.0), UpdaterService(
        updater
    ) as updater_service, WaitressService(
        app, host=args.addr, port=args.port
    ) as waitress_service, StateWriterService(
        state_writer
    ) as state_writer_service:

        # Add the state writer to the Flask application
        # Cast to FlaskWithStateWriter to allow setting state_writer attribute
        if TYPE_CHECKING:
            flask_app = cast(FlaskWithStateWriter, app)
            flask_app.state_writer = state_writer
        else:
            app.state_writer = state_writer

        # Submit services to the executor using __call__ method which is callable
        futures[executor.submit(updater_service)] = updater_service
        futures[executor.submit(state_writer_service)] = state_writer_service
        futures[executor.submit(waitress_service)] = waitress_service

        # Wait for futures to complete
        for future in concurrent.futures.as_completed(futures):
            if future.exception() is not None:
                logger.fatal(
                    'future %s failed with "%s"', futures[future], future.exception()
                )
            else:
                logger.info("future %s has completed", futures[future])
            future.result()
    logger.info("exiting")
