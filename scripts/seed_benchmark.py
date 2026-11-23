import asyncio
from decimal import Decimal
import json
from pathlib import Path

from sqlalchemy import func, select
from redis.asyncio import Redis
from app.core.settings import settings
from app.db.session import AsyncSessionLocal, engine
from app.models.product import Product


async def main():
    async with AsyncSessionLocal() as session:
        before = await session.scalar(select(func.count()).select_from(Product))
        if before > 500:
            raise RuntimeError('More than 500 products exist; no data changed')
        if before == 500:
            print('Already 500 products; dataset and seed manifest preserved')
            await engine.dispose()
            return
        added = []
        for index in range(500 - before):
            product = Product(name=f'Benchmark Product {index + 1:04d}', description='Synthetic product for the 500-product benchmark dataset.', price=Decimal('19.90') + Decimal(index % 100), stock=10 + index % 90)
            session.add(product)
            added.append(product)
        await session.flush()
        ids = [product.id for product in added]
        await session.commit()
    for db in {settings.REDIS_DB, 15}:
        redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=db)
        try:
            await redis.delete('products:list:v1')
        finally:
            await redis.aclose()
    result = dict(previous_count=before, added_count=len(ids), total_count=500, inserted_ids=ids)
    target = Path('docs/data/seed-500.json')
    target.write_text(json.dumps(result, indent=2))
    print(json.dumps({k:v for k,v in result.items() if k != 'inserted_ids'}))
    await engine.dispose()


asyncio.run(main())
