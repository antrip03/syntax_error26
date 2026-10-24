from .chunk import Chunk
from .event import Event
from .flat import Flat

REGISTRY = {"flat": Flat, "chunk": Chunk, "event": Event}


def get(name, **kw):
    return REGISTRY[name](**kw)
