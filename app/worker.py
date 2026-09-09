# app/worker.py
import asyncio
from app.store.db import async_session
from app.harness.lifecycle import claim_next_queued_task, execute_task


async def worker_loop():
    print("worker started")
    while True:
        async with async_session() as db:
            task = await claim_next_queued_task(db)
            if task:
                print(f"executing task {task.id}")
                await execute_task(db, task)
                print(f"task {task.id} finished with status {task.status.value}")
            else:
                await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(worker_loop())