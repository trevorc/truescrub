import abc
import logging
import queue
from typing import Any, List, TypedDict, Union


# Message type definition
class Message(TypedDict, total=False):
    """Type representing a message that can be passed through the queue."""
    command: str
    game_state_id: int

QUEUE_DONE = object()
logger = logging.getLogger(__name__)


# A type alias for queue items - either a message dictionary or the QUEUE_DONE marker
QueueItem = Union[Message, object]

class QueueConsumer(metaclass=abc.ABCMeta):
    """
    Abstract base class for queue consumers that process messages from a queue.

    Implementations must override the process_messages method to handle
    specific message types.
    """

    def __init__(self) -> None:
        """Initialize a new queue consumer with an empty message queue."""
        self._message_queue: queue.Queue[QueueItem] = queue.Queue()

    def _drain_queue(self) -> List[QueueItem]:
        """
        Drain all available messages from the queue.

        Returns:
            A list of messages from the queue
        """
        messages: List[QueueItem] = [self._message_queue.get()]
        try:
            while True:
                messages.append(self._message_queue.get_nowait())
        except queue.Empty:
            return messages

    def send_message(self, **message: Any) -> None:
        """
        Send a message to this consumer's queue.

        Args:
            **message: Keyword arguments that form the message
        """
        logger.debug(
            "sending %s message to %s", next(iter(message.keys())), type(self).__name__
        )
        self._message_queue.put(message)

    def run(self) -> None:
        """
        Run the consumer, processing messages from the queue until stopped.

        Continues running until a QUEUE_DONE object is received.
        """
        logger.debug("%s waiting on queue", type(self).__name__)
        done: bool = False

        while not done:
            messages: List[QueueItem] = self._drain_queue()
            if QUEUE_DONE in messages:
                logger.info("%s got done message", type(self).__name__)
                del messages[messages.index(QUEUE_DONE):]
                if len(messages) == 0:
                    return
                done = True
            self.process_messages(messages)

    def stop(self) -> None:
        """Stop the consumer by sending a QUEUE_DONE message."""
        self._message_queue.put(QUEUE_DONE)

    @abc.abstractmethod
    def process_messages(self, messages: List[QueueItem]) -> None:
        """
        Process messages from the queue.

        Args:
            messages: A list of messages to process
        """
        pass
