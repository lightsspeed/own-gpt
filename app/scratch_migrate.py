import asyncio
from app.core.database import engine, Base
from app.models.chat import ChatSession, ChatMessage  # Import models to register them

async def main():
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
            print("Tables created successfully!")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
