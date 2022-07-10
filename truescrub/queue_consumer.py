import abc
import queue
import logging


QUEUE_DONE = object()
logger = logging.getLogger(__name__)


class QueueConsumer(metaclass=abc.ABCMeta):
  def __init__(self):
    self._message_queue = queue.Queue()

  def _drain_queue(self):
    messages = [self._message_queue.get()]
    try:
      while True:
        messages.append(self._message_queue.get_nowait())
    except queue.Empty:
      return messages

  def send_message(self, **message):
    logger.debug('sending %s message to %s',
                 next(iter(message.keys())), type(self).__name__)
    self._message_queue.put(message)

  def run(self):
    logger.debug('%s waiting on queue', type(self).__name__)
    done = False

    while not done:
      messages = self._drain_queue()
      if QUEUE_DONE in messages:
        logger.info('%s got done message', type(self).__name__)
        del messages[messages.index(QUEUE_DONE):]
        if len(messages) == 0:
          return
        done = True
      self.process_messages(messages)

  def stop(self):
    self._message_queue.put(QUEUE_DONE)

  @abc.abstractmethod
  def process_messages(self, messages):
    pass
