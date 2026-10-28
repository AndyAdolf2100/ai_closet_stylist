"""Run once as a deployment Job, before starting any application replicas."""
import asyncio

from .config import Settings
from .engine import Stylist
from .store import Store


async def main():
    settings = Settings.load()
    store = Store(settings.database)
    engine = Stylist(settings, store, None)
    async with engine.checkpoints() as saver:
        await saver.setup()


if __name__ == '__main__':
    asyncio.run(main())
